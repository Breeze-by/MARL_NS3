"""Metered episode evidence shared by formal PPO, VAL and locked TEST."""
from collections import Counter
import math
import pickle
import time
import traceback
import numpy as np
import torch
from diagnose import make_env, observed_row, append, plain, dump, ROBOTS
from multi_robot_exploration.joint import JointTraditionalPolicy, slot_mask, choice_to_slot
from multi_robot_exploration.ppo import encode


class Episode:
    def __init__(self, row, pose, serial, config, ledger, output, policy_kind, fatal_idle=False):
        output.mkdir(parents=True, exist_ok=False)
        self.output, self.config, self.ledger = output, config, ledger
        self.row, self.pose, self.policy_kind = row, pose, policy_kind
        self.fatal_idle = fatal_idle
        self.env = make_env(row, pose, serial, config, ledger)
        self.records, self.grids, self.costs, self.terms = [], [], [], Counter()
        self.nonforced = np.zeros(3, dtype=int)
        self.idle_seconds = dict.fromkeys(ROBOTS, 0.)
        self.sustained_idle, self.started = 0., time.monotonic()
        self.terminated = self.truncated = False
        self.info = {}
        dump(output/'case.json', dict(map=row['name'], split=row['split'], seed=pose['seed'],
            positions=pose['positions'], serial=serial, policy=policy_kind))
        try:
            self.observation, receipt = self.env.reset()
            dump(output/'initial-observed.json', observed_row(self.observation))
            dump(output/'reset-receipt.json', receipt)
        except BaseException as error:
            dump(output/'first-failure.json', dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
            try:
                self.finish('reset_failure')
            except BaseException as stop_error:
                dump(output/'stop-failure.json', dict(type=type(stop_error).__name__, message=str(stop_error), traceback=traceback.format_exc()))
            raise

    def step(self, model, deterministic, bootstrap):
        env, before = self.env, self.observation
        self.grids.append(np.asarray(before['map']['cells'], dtype=np.int16).copy())
        started = time.monotonic()
        if self.policy_kind == 'traditional':
            action = JointTraditionalPolicy().select(before)
            masks = np.stack([slot_mask(before, i, action.choices[:i]) for i in range(3)])
            record = dict(action=action, inputs=encode(before), masks=masks,
                slots=np.array([choice_to_slot(c) for c in action.choices]), value=None,
                logprob=None, entropy=None, choice_rows=int((masks.sum(axis=1) > 1).sum()))
        else:
            record = model.act(before, deterministic=deterministic)
            if not all(math.isfinite(record[k]) for k in ('value', 'logprob', 'entropy')):
                raise ValueError('Nonfinite policy output')
        inference_s = time.monotonic()-started
        # Intent is durable before executing. A failed attempt is never promoted
        # to a successful transition merely to fill a rollout buffer.
        append(self.output/'intents.jsonl', dict(attempt=len(self.records)+1,
            action=record['action'].choices, masks=record['masks'], inputs=record['inputs'],
            value=record['value'], logprob=record['logprob'], entropy=record['entropy'],
            inference_wall_s=inference_s, observation=observed_row(before)))
        begin_sim = env.backend.sim
        trace_index, event_index = len(env.backend.trajectory), len(env.backend.event_log)
        step_started = time.monotonic()
        observation, reward, terminated, truncated, info = env.step(record['action'])
        self.costs.append(time.monotonic()-step_started)
        self.info, self.terminated, self.truncated = info, terminated, truncated
        self.observation = observation
        if (info['rejected_actions'] and self.policy_kind != 'traditional') or not info['bootstrap_valid']:
            raise RuntimeError('Illegal RL action or untrustworthy final observation: '+str(info))
        if info['minimum_pair_m'] < self.config['backend']['min_pair_m']-1e-9:
            raise RuntimeError('Physical pair safety violated')
        next_value = 0.
        if bootstrap and not terminated:
            with torch.no_grad():
                _, value = model(torch.from_numpy(model.encode(observation))[None])
            next_value = float(value[0])
            if not math.isfinite(next_value):
                raise ValueError('Nonfinite bootstrap value')
        record.update(reward=reward, terminated=terminated, truncated=truncated, next_value=next_value)
        self.records.append(record)
        self.nonforced += record['masks'].sum(axis=1) > 1
        self.terms.update(info['reward_terms'])
        elapsed = env.backend.sim-begin_sim
        events = env.backend.event_log[event_index:]
        accepted = {e['robot'] for e in events if e['kind'] == 'accepted'}
        legal_idle = False
        for i, robot in enumerate(ROBOTS):
            # Original per-row valid_counts precedes reservations. Only this
            # actually sampled conditional mask defines a joint opportunity.
            if record['masks'][i, :15].any():
                legal_idle = True
                if robot not in accepted:
                    self.idle_seconds[robot] += elapsed
        trace = env.backend.trajectory[trace_index:]
        rotation = sum(abs(t['velocities'][r][2])*self.config['backend']['physics_dt'] for t in trace for r in ROBOTS)
        no_progress = not np.any(np.asarray(observation['map']['cells']) != self.grids[-1])
        self.sustained_idle = self.sustained_idle+elapsed if legal_idle and no_progress and info['reward_terms']['path_m'] < .01 and rotation < .01 else 0.
        append(self.output/'decisions.jsonl', dict(decision=len(self.records), sim=env.backend.sim,
            choices=record['action'].choices, conditional_options=record['masks'].sum(axis=1),
            raw_valid_counts=before['valid_counts'], value=record['value'], next_value=next_value,
            logprob=record['logprob'], entropy=record['entropy'], inference_wall_s=inference_s,
            step_wall_s=self.costs[-1], sustained_idle_sim_s=self.sustained_idle, actual_events=events, **info))
        self.ledger.flush('episode_transition', policy=self.policy_kind, map=self.row['name'],
            seed=self.pose['seed'], decision=len(self.records))
        if self.fatal_idle and self.sustained_idle >= 50.:
            raise RuntimeError('Registered sustained idle with a true joint goal opportunity')
        return record

    def finish(self, reason):
        env = self.env
        if env.allocator is not None and not env.done:
            env.allocator.stop(reason)
        stopped = env.backend.stop(reason) if hasattr(env.backend, 'goals') else False
        if hasattr(self, 'observation'):
            self.grids.append(np.asarray(self.observation['map']['cells'], dtype=np.int16).copy())
            dump(self.output/'last-observed.json', observed_row(self.observation))
        if self.grids:
            np.savez_compressed(self.output/'observed-grids.npz', cells=np.stack(self.grids))
        with (self.output/'records.pkl').open('wb') as stream:
            pickle.dump(self.records, stream)
        dump(self.output/'trajectory.json', getattr(env.backend, 'trajectory', []))
        events = getattr(env.backend, 'event_log', [])
        dump(self.output/'navigation.json', events)
        if hasattr(env.backend, 'local'):
            np.savez_compressed(self.output/'final-local-maps.npz', **env.backend.local)
        accepts = Counter(e['robot'] for e in events if e['kind'] == 'accepted')
        successes = Counter(e['robot'] for e in events if e['kind'] == 'terminal' and e['status'] == 'succeeded')
        started_goals = {e['uuid']: e['sim'] for e in events if e['kind'] == 'accepted'}
        aborts = []
        for event in events:
            if event['kind'] == 'terminal' and event['status'] == 'aborted':
                age = event['sim']-started_goals[event['uuid']]
                cause = ('no_route_in_own_inflated_observed_map' if abs(age) < 1e-8 else
                         'original_90sim_navigation_timeout' if age >= self.config['backend']['navigation_timeout_sim_s']-1e-8 else
                         'unclassified_abort')
                aborts.append(dict(uuid=event['uuid'], robot=event['robot'], age_sim_s=age, derived_cause=cause))
        paths = getattr(env.backend, 'paths', dict.fromkeys(ROBOTS, 0.))
        info = self.info
        result = dict(map=self.row['name'], family=self.row['family'], split=self.row['split'], seed=self.pose['seed'],
            policy=self.policy_kind, actual_joint=len(self.records), raw_terminated=self.terminated,
            raw_truncated=self.truncated, raw_reason=info.get('reason'), end_reason=info.get('reason') or reason,
            externally_cut=not(self.terminated or self.truncated),
            initial_coverage=getattr(env, 'initial_coverage', None),
            coverage=env.backend.coverage() if hasattr(env.backend, 'shared') else None,
            coverage_times=getattr(env.backend, 'coverage_times', {}),
            natural_complete=bool(self.terminated and info.get('reason') == 'natural_complete' and stopped),
            reward_total=getattr(env, 'reward_total', 0.), reward_terms=dict(self.terms),
            paths_m=paths, maximum_robot_path_m=max(paths.values()), accepted=dict(accepts), successes=dict(successes),
            all_robot_participation=all(accepts[r] >= 1 and paths[r] >= 1. for r in ROBOTS),
            net_displacement_m={r: float(np.linalg.norm(np.asarray(env.backend.poses[r][:2])-p))
                                for r, p in zip(ROBOTS, self.pose['positions'])} if hasattr(env.backend, 'poses') else {},
            nonforced_per_head=self.nonforced.tolist(), conditional_idle_opportunity_seconds=self.idle_seconds,
            navigation_terminals=dict(Counter(e['status'] for e in events if e['kind'] == 'terminal')),
            minimum_pair_m=(env.backend.minimum_pair if hasattr(env.backend, 'minimum_pair') and math.isfinite(env.backend.minimum_pair) else None),
            safe_blocks=getattr(env.backend, 'safe_blocks', None), last_error_info=getattr(env, 'last_error_info', None),
            rejected_joint_decisions=sum(bool(r['rejections']) for r in env.steps) if hasattr(env, 'steps') else 0,
            rejected_robot_actions=sum(len(r['rejections']) for r in env.steps) if hasattr(env, 'steps') else 0,
            abort_causes_derived=aborts,
            metrics=info.get('metrics'), step_wall_mean_s=None if not self.costs else float(np.mean(self.costs)),
            wall_seconds=time.monotonic()-self.started, stop_verified_kinematic=stopped, physical_stop_verified=False)
        dump(self.output/'summary.json', plain(result))
        self.ledger.flush('episode_end', map=self.row['name'], seed=self.pose['seed'],
            reason=result['end_reason'], valid_transitions=len(self.records), stopped=stopped)
        if not stopped:
            raise RuntimeError('Kinematic stop could not be verified')
        return result

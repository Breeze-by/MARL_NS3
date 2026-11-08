"""One registered VAL-only fixed-RL01 diagnosis; no optimizer or TEST rollout."""
import argparse
from collections import Counter
from collections.abc import Mapping
import json
import math
from pathlib import Path
import pickle
import sys
import time
import traceback
import numpy as np
import torch

from maps import HERE, WORKSPACE, PROJECT, ROOT, ROI, dump, sha
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend, ROBOTS
from multi_robot_exploration.rl_env import RLEnvironment
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint, gae, clipped_surrogate


def plain(value):
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def append(path, value):
    with path.open('a') as stream:
        stream.write(json.dumps(plain(value), allow_nan=False)+'\n')


def verify_lock(lock_path=None):
    lock = json.loads((lock_path or HERE/'P1_LOCK.json').read_text())
    for path, expected in lock['sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError('Registered P1 file changed: '+path)
    return lock


def make_env(row, pose, serial, config, ledger):
    with ledger.call('world_projection_build', map=row['name']):
        world = ProjectedWorld(ROOT/row['source'], ROOT/'base-01-econ/assets/gazebo_models',
            row['variant'], reference_positions=row['reference_positions'])
    if not np.allclose(world.bounds, ROI, atol=1e-10) or int(world.reference_free.sum()) != row['reference_cells']:
        raise ValueError('Registered fixed ROI/reference mismatch')
    backend = KinematicBackend(world, dict(config['backend'], initial_positions=pose['positions']), ledger, pose['seed'])
    backend.episode = serial  # Unique episode/goal UUID scope, not physical state.
    return RLEnvironment(backend, None, config, ledger)


def observed_row(observation):
    result = dict(observation)
    result['map'] = {k: v for k, v in observation['map'].items() if k != 'cells'}
    return plain(result)


def gradient_probe(model, records, config, ledger):
    if not records:
        return None
    boundaries = [r['truncated'] for r in records]
    boundaries[-1] = True  # Probe batch ends here; retain real flags in raw log.
    adv, returns = gae([r['reward'] for r in records], [r['value'] for r in records],
        [r['next_value'] for r in records], [r['terminated'] for r in records], boundaries,
        config['gamma'], config['gae_lambda'])
    inputs = torch.from_numpy(np.stack([r['inputs'] for r in records]))
    slots = torch.from_numpy(np.stack([r['slots'] for r in records]))
    masks = torch.from_numpy(np.stack([r['masks'] for r in records]))
    old = torch.tensor([r['logprob'] for r in records])
    advantages = torch.from_numpy(adv)
    advantages = (advantages-advantages.mean())/(advantages.std(unbiased=False)+1e-8)
    logprob, entropy, values = model.recompute(inputs, slots, masks)
    ratio = (logprob-old).exp()
    actor_loss = -clipped_surrogate(ratio, advantages, config['clip']).mean()
    critic_loss = .5*(torch.from_numpy(returns)-values).square().mean()
    loss = actor_loss+config['value_coefficient']*critic_loss-config['entropy_coefficient']*entropy.mean()
    if not torch.isfinite(loss):
        raise ValueError('Nonfinite fixed-weight gradient probe')
    model.zero_grad()
    loss.backward()
    ledger.add('diagnostic_gradient_backward')
    gradients = model.actor.weight.grad.reshape(3, 17, -1).norm(dim=(1, 2))
    if not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()):
        raise ValueError('Nonfinite diagnostic gradient')
    result = dict(actor_loss=float(actor_loss.detach()), critic_loss=float(critic_loss.detach()),
        per_head_actor_weight_gradient=gradients.tolist(),
        critic_gradient=float(model.critic.weight.grad.norm()),
        approx_kl=float(((ratio-1)-(logprob-old)).mean().detach()),
        entropy=float(entropy.mean().detach()),
        deterministic_sample_probe_only=True, optimizer_steps=0, parameter_change=0.)
    model.zero_grad()
    ledger.flush('fixed_weight_gradient_probe', **result)
    return result


def episode(model, row, pose, serial, config, ledger, output, wall_deadline):
    output.mkdir(exist_ok=False)
    dump(output/'case.json', dict(map=row['name'], split=row['split'], pose_seed=pose['seed'],
        positions=pose['positions'], serial=serial, max_joint=config['diagnostic']['max_joint_per_episode']))
    env = make_env(row, pose, serial, config, ledger)
    records, grids, rewards, step_wall, nonforced = [], [], Counter(), [], np.zeros(3, dtype=int)
    idle_opportunity_seconds = dict.fromkeys(ROBOTS, 0.)
    start = time.monotonic()
    error = None
    sustained_idle = 0.
    terminated = truncated = False
    info = {}
    try:
        observation, _ = env.reset()
        dump(output/'initial-observed.json', observed_row(observation))
        dump(output/'initial-state.json', dict(coverage=env.initial_coverage, poses=plain(env.backend.poses),
            reference_cells=row['reference_cells'], valid_counts=observation['valid_counts']))
        for decision in range(config['diagnostic']['max_joint_per_episode']):
            if time.monotonic() >= wall_deadline:
                raise TimeoutError('P2 registered wall budget exceeded')
            before = observation
            grids.append(np.asarray(before['map']['cells'], dtype=np.int16).copy())
            forward_start = time.monotonic()
            record = model.act(before, deterministic=True)
            inference_s = time.monotonic()-forward_start
            if not all(math.isfinite(record[k]) for k in ('logprob', 'value', 'entropy')):
                raise ValueError('Nonfinite fixed-policy output')
            nonforced += record['masks'].sum(axis=1) > 1
            begin_sim = env.backend.sim
            trace_index, event_index = len(env.backend.trajectory), len(env.backend.event_log)
            tick_start = time.monotonic()
            observation, reward, terminated, truncated, info = env.step(record['action'])
            step_wall.append(time.monotonic()-tick_start)
            if info['rejected_actions'] or not info['bootstrap_valid']:
                raise RuntimeError('RL illegal action or invalid bootstrap: '+str(info))
            if info['minimum_pair_m'] < config['backend']['min_pair_m']-1e-9:
                raise RuntimeError('Physical pair separation violated')
            next_value = 0.
            if not terminated:
                with torch.no_grad():
                    _, value = model(torch.from_numpy(model.encode(observation))[None])
                next_value = float(value[0])
            record.update(reward=reward, terminated=terminated, truncated=truncated, next_value=next_value)
            records.append(record)
            rewards.update(info['reward_terms'])
            elapsed = env.backend.sim-begin_sim
            events = env.backend.event_log[event_index:]
            accepted = {e['robot'] for e in events if e['kind'] == 'accepted'}
            for index, robot in enumerate(ROBOTS):
                if before['robots'][index]['state'] == 'idle' and before['valid_counts'][index] and robot not in accepted:
                    idle_opportunity_seconds[robot] += elapsed
            trace = env.backend.trajectory[trace_index:]
            translation = info['reward_terms']['path_m']
            rotation = sum(abs(t['velocities'][r][2])*config['backend']['physics_dt'] for t in trace for r in ROBOTS)
            legal_idle = any(r['state'] == 'idle' and n for r, n in zip(before['robots'], before['valid_counts']))
            no_progress = info['reward_terms']['new_free_m2'] == 0. and not np.any(np.asarray(observation['map']['cells']) != grids[-1])
            sustained_idle = sustained_idle+elapsed if legal_idle and no_progress and translation < .01 and rotation < .01 else 0.
            append(output/'decisions.jsonl', dict(decision=decision+1, sim=env.backend.sim, action=record['action'].choices,
                conditional_options=record['masks'].sum(axis=1), nonforced=record['masks'].sum(axis=1)>1,
                value=record['value'], next_value=next_value, logprob=record['logprob'], entropy=record['entropy'],
                inference_wall_s=inference_s, step_wall_s=step_wall[-1], observation=observed_row(before),
                actual_events=events, sustained_idle_sim_s=sustained_idle, **info))
            ledger.flush('diagnostic_joint', map=row['name'], seed=pose['seed'], decision=decision+1)
            if sustained_idle >= 50.:
                raise RuntimeError('Registered sustained all-robot idle with legal candidate')
            if terminated or truncated:
                break
        grids.append(np.asarray(observation['map']['cells'], dtype=np.int16).copy())
        probe = gradient_probe(model, records, config, ledger)
    except BaseException as failure:
        error = dict(type=type(failure).__name__, message=str(failure), traceback=traceback.format_exc())
        dump(output/'first-failure.json', error)
        raise
    finally:
        if not env.done and env.allocator is not None:
            env.allocator.stop('p2_failure' if error else 'p2_resource_cap')
        stopped = env.backend.stop('p2_failure' if error else 'p2_end') if hasattr(env.backend, 'goals') else False
        dump(output/'trajectory.json', env.backend.trajectory if hasattr(env.backend, 'trajectory') else [])
        dump(output/'navigation.json', env.backend.event_log if hasattr(env.backend, 'event_log') else [])
        if records:
            np.savez_compressed(output/'observed-grids.npz', cells=np.stack(grids))
            # Contains policy-received inputs, conditional masks and old logprobs;
            # never a truth reference or private backend object.
            with (output/'records.pkl').open('wb') as stream:
                pickle.dump(records, stream)
        ledger.flush('diagnostic_case_stop', map=row['name'], seed=pose['seed'], error=error, stopped=stopped)
    events = env.backend.event_log
    accepts = Counter(e['robot'] for e in events if e['kind'] == 'accepted')
    successes = Counter(e['robot'] for e in events if e['kind'] == 'terminal' and e['status'] == 'succeeded')
    summary = dict(map=row['name'], seed=pose['seed'], actual_joint=len(records),
        raw_terminated=terminated, raw_truncated=truncated, raw_reason=info.get('reason'),
        end_reason=info.get('reason') or 'external_diagnostic_resource_cap',
        initial_coverage=env.initial_coverage, final_coverage=env.backend.coverage(),
        coverage_times=env.backend.coverage_times, fixed_reference_cells=row['reference_cells'],
        paths_m=env.backend.paths, nonforced_per_head=nonforced.tolist(),
        reward_total=env.reward_total, reward_terms=dict(rewards), accepted=dict(accepts), successes=dict(successes),
        all_robot_participation=all(accepts[r] >= 1 and env.backend.paths[r] >= 1. for r in ROBOTS),
        idle_opportunity_seconds=idle_opportunity_seconds,
        minimum_pair_m=env.backend.minimum_pair, safe_blocks=env.backend.safe_blocks,
        navigation_terminals=dict(Counter(e['status'] for e in events if e['kind'] == 'terminal')),
        gradient_probe=probe, stop_verified_kinematic=stopped, physical_stop_verified=False,
        step_wall_mean_s=float(np.mean(step_wall)), step_wall_median_s=float(np.median(step_wall)),
        wall_seconds=time.monotonic()-start)
    dump(output/'summary.json', plain(summary))
    if not stopped:
        raise RuntimeError('Kinematic stop failed')
    return summary


def run(output):
    lock = verify_lock()
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((HERE/'config.json').read_text())
    maps = json.loads((ROOT/lock['maps_manifest']).read_text())
    cases = [(row, p) for row in maps if row['split'] == 'VAL' for p in row['positions']]
    if len(cases) != config['diagnostic']['max_episodes']:
        raise ValueError('P2 case table mismatch')
    ledger = Ledger(output/'ledger.jsonl', 'p2_fixed_rl01_val')
    torch.set_num_threads(config['torch_threads'])
    model = ActorCritic(ledger, config['hidden'])
    checkpoint = ROOT/'rl-01/runs/formal-01/case/final.pt'
    if sha(checkpoint) != '415139fa922f1af23f343f98b53720be971736c6e71eb8ee9ba28835e10f72b4':
        raise ValueError('RL01 model identity mismatch')
    load_checkpoint(checkpoint, model)
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    dump(output/'binding.json', dict(lock_sha256=sha(HERE/'P1_LOCK.json'), checkpoint_sha256=sha(checkpoint),
         deterministic=True, cases=[(r['name'], p['seed']) for r, p in cases], config=config))
    start = time.monotonic()
    deadline = start+config['diagnostic']['wall_seconds']
    summaries = []
    try:
        for serial, (row, pose) in enumerate(cases):
            result = episode(model, row, pose, serial, config, ledger,
                             output/f'{serial:02d}-{row["name"]}-{pose["seed"]}', deadline)
            summaries.append(result)
            print(json.dumps(plain(result), allow_nan=False), flush=True)
        if not all(torch.equal(before[k], v) for k, v in model.state_dict().items()):
            raise ValueError('Fixed diagnostic model parameters changed')
        if ledger.counts['env_step'] > config['diagnostic']['max_total_joint']:
            raise ValueError('Diagnostic joint budget exceeded')
    except BaseException as failure:
        dump(output/'first-failure.json', dict(type=type(failure).__name__, message=str(failure), traceback=traceback.format_exc()))
        ledger.flush('p2_failure')
        raise
    ledger.flush('p2_complete')
    dump(output/'summary.json', dict(status='CONTROLLED DIAGNOSIS COMPLETE', cases=summaries,
        actual_joint=ledger.counts['env_step'], counts=dict(ledger.counts), optimizer_step=0,
        model_weights_unchanged=True, wall_seconds=time.monotonic()-start,
        formal_joint=0, test_episodes=0, gazebo_run=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    run(parser.parse_args().output.resolve())

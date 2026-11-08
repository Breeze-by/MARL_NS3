"""P0-P4 only. No formal training, Gazebo, ROS, communication or evaluation runs."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import traceback
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator, JointAction, TraditionalPolicy, KEEP, WAIT
from multi_robot_exploration.environment import AllocationEnvironment
from multi_robot_exploration.joint import slot_mask, candidate_mask, choice_to_slot, JointTraditionalPolicy
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend, ROBOTS, route
from multi_robot_exploration.rl_env import RLEnvironment, reward_value
from multi_robot_exploration.ppo import ActorCritic, encode, gae, clipped_surrogate, update, save_checkpoint, load_checkpoint


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def fixture(count):
    robots = [dict(id=r, pose=(float(i), 0., 0.), velocity=(0., 0., 0.), state='idle',
                   target=None, task_token=0, last_success=None, goal_duration_s=None) for i, r in enumerate(ROBOTS)]
    candidates = [dict(index=i, robot=ROBOTS[i//5], position=(float(i)*.4, 2.), valid=True,
                       reachable=True, path_cost_estimate_m=3., information_gain_proxy_m2=.1,
                       traditional_score=float(15-i), traditional_eligible=True, local_map_valid=True)
                  for i in range(count)]
    return dict(decision_id=1, map_version=1, trigger=None, halted=None,
                map=dict(cells=np.zeros((20, 20), dtype=np.int16), resolution=.05, origin=(0., 0.), stamp=0.),
                robots=robots, candidates=candidates,
                action_mask=tuple(tuple(c['robot']==r for c in candidates) for r in ROBOTS))


def probability_gates(model, ledger):
    evidence = []
    for count in (0, 1, 15):
        obs = fixture(count)
        action = model.act(obs)
        inputs = torch.from_numpy(action['inputs'][None])
        slots = torch.from_numpy(action['slots'][None])
        masks = torch.from_numpy(action['masks'][None])
        logprob, entropy, value = model.recompute(inputs, slots, masks)
        assert np.isclose(float(logprob[0].detach()), action['logprob'], atol=1e-6)
        assert torch.isfinite(value).all() and torch.isfinite(entropy).all()
        prefix = []
        for row in range(3):
            assert np.array_equal(slot_mask(obs, row, prefix), action['masks'][row])
            assert action['masks'][row, action['slots'][row]]
            prefix.append(action['action'].choices[row])
        evidence.append(dict(candidate_count=count, choices=prefix, logprob=action['logprob']))
    # The independently supplied BASE02 WAIT counterexample, now common gate PASS.
    obs = fixture(0)
    obs['candidates'] = [dict(robot='tb1', position=(1., 1.), traditional_eligible=True, local_map_valid=True),
                         dict(robot='tb2', position=(1.1, 1.), traditional_eligible=True, local_map_valid=True)]
    obs['action_mask'] = ((True, False), (False, True), (False, False))
    allocator = Allocator()
    allocator.decision_id = allocator.map_version = 1
    assert slot_mask(obs, 1, [0]).sum() == 1 and slot_mask(obs, 1, [0])[16]
    proposals, rejected = allocator.apply(obs, JointAction(1, 1, (0, WAIT, WAIT)))
    assert set(proposals) == {'tb1'} and rejected == {}
    # Two candidates left after the first reservation: explicit probability sum.
    obs = fixture(15)
    obs['candidates'][5]['position'] = obs['candidates'][0]['position']
    chosen = model.act(obs, deterministic=True)
    logits, _ = model(torch.from_numpy(chosen['inputs'][None]))
    manual = 0.
    for row, choice in enumerate(chosen['action'].choices):
        allowed = slot_mask(obs, row, chosen['action'].choices[:row])
        legal_logits = logits[0, row, torch.from_numpy(allowed)]
        manual += float((logits[0, row, choice_to_slot(choice)]-torch.logsumexp(legal_logits, 0)).detach())
    assert np.isclose(manual, chosen['logprob'], atol=1e-6)
    # Active task can only KEEP, no fresh goal or task cancellation.
    obs['robots'][1]['state'] = 'active'
    assert slot_mask(obs, 1, [0]).tolist() == [False]*15+[True, False]
    # Same sampling seed reproduces masks, action, likelihood (two real forwards).
    torch.manual_seed(711)
    first = model.act(obs)
    torch.manual_seed(711)
    second = model.act(obs)
    assert first['action'] == second['action'] and first['logprob'] == second['logprob']
    # Encoder ignores private evaluator/backend fields entirely for actor and critic.
    original = encode(obs)
    poisoned = dict(obs, truth=np.full((20, 20), 123), reference_coverage=.99, future_gain=1e9)
    assert np.array_equal(original, encode(poisoned))
    # Same physical received map, alternate ROS origin/extent with unknown padding.
    base = fixture(1)
    base['map'] = dict(cells=np.array([[0, 0, 100], [-1, 0, -1]], dtype=np.int16),
                       resolution=.05, origin=(-1., 1.), stamp=0.)
    padded = dict(base)
    padded['map'] = dict(base['map'], cells=np.pad(base['map']['cells'], ((4, 7), (6, 3)), constant_values=-1),
                         origin=(-1.3, .8))
    assert np.array_equal(encode(base), encode(padded))
    # True static-mask actions are rejected, no post-selection replacement.
    allocator = Allocator()
    allocator.decision_id = allocator.map_version = 1
    obs = fixture(1)
    _, invalid = allocator.apply(obs, JointAction(1, 1, (WAIT, WAIT, WAIT)))
    assert invalid == {'tb1': 'wait_with_available_work'}
    return dict(variable_candidates=evidence, joint_wait_fixed=True, conditional_logprob_manual=manual,
                same_seed=True, busy_keep=True, encoder_extra_truth_ignored=True,
                metric_roi_padding_origin_equivalence=True)


def numeric_gates():
    # Episode 0 truncates after step1; next step is another episode and must not leak back.
    adv, returns = gae([1., 2., 100.], [3., 4., 1.], [4., 5., 9.],
                       [False, False, True], [False, True, False], gamma=.9, lam=.8)
    expected1 = 2+.9*5-4
    expected0 = 1+.9*4-3+.9*.8*expected1
    assert np.allclose(adv, [expected0, expected1, 99.])
    assert np.allclose(returns, adv+np.array([3., 4., 1.]))
    ratio = torch.tensor([1.5, .5, 1.5, .5])
    advantage = torch.tensor([2., 2., -2., -2.])
    assert torch.allclose(clipped_surrogate(ratio, advantage), torch.tensor([2.4, 1., -3., -1.6]))
    return dict(gae=adv.tolist(), terminal_bootstrap_zero=True, truncated_final_observation_bootstrap=True,
                episode_advantage_chain_reset=True, clipping_positive_negative=True)


def geometry_gates(world, ledger):
    # The planner must not cross an observed wall, unknown cells or a diagonal corner.
    blocked = np.zeros((40, 40), dtype=np.int16)
    blocked[:, 20] = 100
    unknown = np.zeros((40, 40), dtype=np.int16)
    unknown[:, 20] = -1
    corner = np.full((3, 3), -1, dtype=np.int16)
    corner[0, 0] = corner[1, 1] = 0
    with ledger.call('fixture_route_checks'):
        assert route(blocked, (20, 5), (20, 35), .05) is None
        assert route(unknown, (20, 5), (20, 35), .05) is None
        assert route(corner, (0, 0), (1, 1), .05) is None
        free = np.zeros((40, 40), dtype=np.int16)
        path = route(free, (5, 5), (30, 30), .05)
        assert len(path) == 26
    assert all(world.clear(p) for p in ((5., 4.), (-4.5, 4.), (6., -1.5)))
    assert not world.clear(world.position(tuple(np.argwhere(world.obstacles)[0])))
    return dict(observed_wall_blocks=True, unknown_blocks=True, no_diagonal_corner_cut=True,
                free_route_cells=len(path), declared_spawns_clear=True)


def trajectory_gates(backend, config):
    samples = backend.trajectory
    maxima = dict(linear=0., angular=0.)
    for previous, current in zip(samples, samples[1:]):
        dt = current['sim']-previous['sim']
        for robot in ROBOTS:
            if dt > 0:
                distance = np.linalg.norm(np.array(current['poses'][robot][:2])-previous['poses'][robot][:2])
                from multi_robot_exploration.rl_backend import angle
                turn = abs(angle(current['poses'][robot][2]-previous['poses'][robot][2]))
                maxima['linear'] = max(maxima['linear'], distance/dt)
                maxima['angular'] = max(maxima['angular'], turn/dt)
                assert distance <= config['max_linear_m_s']*dt+1e-8
                assert turn <= config['max_angular_rad_s']*dt+1e-8
            assert backend.world.clear(current['poses'][robot], config['radius_m'])
    assert backend.minimum_pair >= config['min_pair_m']
    for event in backend.events:
        if event['kind'] == 'terminal' and event['status'] == 'succeeded':
            # Source lifecycle success has occurred only through backend arrival branch;
            # full trace plus terminal target receipts are preserved for audit.
            assert event['token'] > 0
    return dict(samples=len(samples), max_linear_m_s=float(maxima['linear']),
                max_angular_rad_s=float(maxima['angular']), minimum_pair_m=backend.minimum_pair,
                no_observed_collision=True)


class WaitBackend:
    """Controlled contract fixture: tb1 waits, tb2 has a real active-task receipt."""
    def __init__(self, ledger):
        self.ledger = ledger
        self.time = 0.

    def snapshot(self, events=()):
        return dict(sim=self.time, map=dict(cells=np.zeros((8, 8)), resolution=.05, origin=(0., 0.), stamp=self.time),
                    robots={r: dict(pose=(.1, .1, 0.), stamp=self.time, velocity=(0., 0., 0.)) for r in ROBOTS},
                    events=events)

    def reset(self):
        with self.ledger.call('fixture_backend_reset'):
            self.time = 0.
            return dict(episode_id='controlled', world_reset=True, slam_reset=True, navigation_cleared=True,
                        snapshot=self.snapshot())

    def goal_valid(self, *args):
        self.ledger.add('fixture_backend_goal_valid')
        return True

    def advance(self, proposals, duration):
        with self.ledger.call('fixture_backend_advance'):
            self.time += duration
            return self.snapshot()

    def stop(self, reason):
        with self.ledger.call('fixture_backend_stop'):
            return True


def lifecycle_gates(ledger):
    env = AllocationEnvironment(WaitBackend(ledger), None)
    with ledger.call('fixture_env_reset'):
        obs, _ = env.reset()
    r = env.allocator.robots['tb2']
    r.state, r.target, r.token, r.started = 'active', (.2, .2), 1, 0.
    env.observation = env.allocator.get_observation()
    for index in range(6):
        obs = env.observation
        with ledger.call('fixture_env_step'):
            _, _, terminated, truncated, _ = env.step(JointAction(obs['decision_id'], obs['map_version'], (WAIT, KEEP, WAIT)))
        assert not terminated and not truncated
        assert env.allocator.robots['tb2'].token == 1
    assert env.allocator.finish('tb2', 1, 'succeeded')
    assert not env.allocator.finish('tb2', 0, 'succeeded')
    with ledger.call('fixture_backend_manual_stop'):
        env.backend.stop('fixture_end')
    return dict(single_robot_wait_does_not_end_active_peers=True, keep_no_resubmission=True,
                stale_result_no_ownership=True)


def run(case, initial):
    case.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(case/'ledger.jsonl', 'gate')
    evidence = dict(status='RUNNING', formal_training_steps=0)
    config = json.loads((HERE/'config.json').read_text())
    previous_steps = 0
    for previous in case.parent.glob('gate-*/ledger.jsonl'):
        if previous == case/'ledger.jsonl':
            continue
        for line in previous.read_text().splitlines():
            previous_steps += json.loads(line)['delta'].get('env_step', 0)
    remaining_steps = config['gate_joint_steps_max']-previous_steps
    prior_summary = case.parent/'preflight-ledger-summary.json'
    if prior_summary.exists():
        previous_steps = max(previous_steps, json.loads(prior_summary.read_text())['genuine_A_joint_steps'])
        remaining_steps = config['gate_joint_steps_max']-previous_steps
    if remaining_steps <= 0:
        raise RuntimeError('All genuine gate-step budget already consumed')
    evidence['previous_genuine_gate_steps'] = previous_steps
    evidence['source_sha256'] = {str(p.relative_to(WORKSPACE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*WORKSPACE.glob('src/multi_robot_exploration/multi_robot_exploration/*.py'),
                  HERE/'gates.py', HERE/'config.json']}
    torch.set_num_threads(config['torch_threads'])
    torch.manual_seed(config['training_seed'])
    np.random.seed(config['training_seed'])
    random.seed(config['training_seed'])
    try:
        assets = WORKSPACE.parents[1]/'base-01-econ/assets/gazebo_models'
        with ledger.call('world_projection_build'):
            world = ProjectedWorld(WORKSPACE/'src/multi_robot/worlds/my_world.world', assets, 'A')
        evidence['scene'] = dict(bounds=world.bounds, origin=world.origin, shape=world.shape,
                                 source_boxes=world.source_boxes, excluded_meshes=world.excluded_meshes,
                                 reference_cells=int(world.reference_free.sum()),
                                 reference_scope='fixed .25m-clearance 4-connected components containing declared starts')
        evidence['geometry'] = geometry_gates(world, ledger)
        model = ActorCritic(ledger, config['hidden'])
        if not initial.exists():
            save_checkpoint(initial, model, purpose='genuine untouched initialization before first policy forward',
                            config=config, task_roi=world.bounds, source_commit='672ef4ada610c8acaaa8881ec3af023393c31881')
        else:
            load_checkpoint(initial, model, restore_rng=True)
        evidence['initial_sha256'] = hashlib.sha256(initial.read_bytes()).hexdigest()
        # All gate forwards/updates operate on this disposable model clone.
        evidence['probability'] = probability_gates(model, ledger)
        evidence['numerics'] = numeric_gates()
        evidence['lifecycle'] = lifecycle_gates(ledger)
        env = RLEnvironment(KinematicBackend(world, config['backend'], ledger, config['training_seed']), None, config, ledger)
        observation, _ = env.reset()
        evidence['initial_observation'] = dict(coverage=env.initial_coverage,
                                             candidates=len(observation['candidates']),
                                             valid_counts=observation['valid_counts'])
        assert env.initial_coverage < .95, 'Initial stationary state already completes this task'
        # Real sensor cannot label every true cell: unknown occupancy stays private.
        assert np.count_nonzero(observation['map']['cells'] < 0) > 0
        rollout, decisions = [], []
        multi_choice = 0
        for index in range(remaining_steps):
            record = model.act(observation)
            multi_choice += record['choice_rows'] > 0
            before_pose = {r: env.backend.poses[r].copy() for r in ROBOTS}
            next_observation, reward, terminated, truncated, info = env.step(record['action'])
            assert not info['rejected_actions'], 'Policy action rejected by shared allocator gate'
            assert info['minimum_pair_m'] >= config['backend']['min_pair_m']-1e-8
            assert all(np.linalg.norm(env.backend.poses[r][:2]-before_pose[r][:2]) <=
                       config['backend']['max_linear_m_s']*config['step_sim_seconds']+1e-8 for r in ROBOTS)
            assert info['bootstrap_valid'], 'No credible bootstrap for environment failure'
            if terminated:
                next_value = 0.
            else:
                with torch.no_grad():
                    _, next_values = model(torch.from_numpy(model.encode(next_observation))[None])
                next_value = float(next_values[0])
            record.update(reward=reward, next_value=next_value, terminated=terminated, truncated=truncated)
            rollout.append(record)
            ledger.add('gate_rollout_unique_samples')
            ledger.flush('gate_rollout_sample', decision=index, choice_rows=record['choice_rows'])
            decisions.append(dict(decision=index, choices=record['action'].choices, choice_rows=record['choice_rows'],
                                  reward=reward, sim=env.backend.sim, coverage=info['coverage'],
                                  terminated=terminated, truncated=truncated, reason=info['reason'],
                                  paths_m=info['paths_m']))
            with (case/'decisions.jsonl').open('a') as stream:
                stream.write(json.dumps(decisions[-1], allow_nan=False)+'\n')
            observation = next_observation
            if terminated or truncated:
                break
        evidence['genuine_rollout'] = decisions
        evidence['genuine_nonforced_decisions'] = multi_choice
        evidence['physical_trace'] = trajectory_gates(env.backend, config['backend'])
        assert multi_choice > 0, 'No genuine legal target-choice alternatives: TRAINING ENVIRONMENT BLOCKED'
        adv, ret = gae([r['reward'] for r in rollout], [r['value'] for r in rollout],
                       [r['next_value'] for r in rollout], [r['terminated'] for r in rollout],
                       [r['truncated'] for r in rollout], config['gamma'], config['gae_lambda'])
        for item, a, v in zip(rollout, adv, ret):
            item.update(advantage=float(a), **{'return': float(v)})
        optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
        before = {k: v.detach().clone() for k, v in model.state_dict().items()}
        gate_config = dict(config, epochs=1, minibatch=len(rollout))
        evidence['clone_updates'] = update(model, optimizer, rollout, gate_config, ledger, np.random.default_rng(713))
        diagnostic = evidence['clone_updates'][0]
        assert diagnostic['actor_head_gradient'] > 0 and diagnostic['actor_head_weight_change'] > 0
        assert diagnostic['critic_gradient'] > 0
        assert any(not torch.equal(before[k], value) for k, value in model.state_dict().items())
        save_checkpoint(case/'gate-clone-updated.pt', model, optimizer, purpose='gate only; never formal initialization')
        reloaded = ActorCritic(ledger, config['hidden'])
        load_checkpoint(case/'gate-clone-updated.pt', reloaded)
        assert all(torch.equal(model.state_dict()[k], value) for k, value in reloaded.state_dict().items())
        first = model.act(observation, deterministic=True)
        second = reloaded.act(observation, deterministic=True)
        assert first['action'] == second['action'] and first['logprob'] == second['logprob'] and first['value'] == second['value']
        # Freeze the last measured map: replaying no movement gives no area gain.
        weights = config['reward']
        for seconds in (0., 5., 25.):
            terms = dict(new_free_m2=0., sim_seconds=seconds, path_m=0., duplicate_new_m2=0.,
                         stationary_no_progress_seconds=seconds, first_complete=0.)
            assert reward_value(terms, weights) <= 0
        evidence['reward_no_repeat_area_or_wait_gain'] = True
        if not env.done:
            env.allocator.stop('gate_budget')
            assert env.backend.stop('gate_budget')
        write(case/'trajectory.json', env.backend.trajectory)
        # Validate a complete reset receipt and actual maps/history/clock/goals reset.
        reset_observation, _ = env.reset()
        assert env.backend.sim == 0 and env.decisions == 0 and not env.backend.goals and not env.allocator.history
        assert reset_observation['valid_counts'] == evidence['initial_observation']['valid_counts']
        assert env.backend.stop('gate_final')
        np.savez_compressed(case/'scene-and-observation.npz', obstacles=world.obstacles,
                            lidar_obstacles=world.lidar_obstacles, reference=world.reference_free,
                            observed=observation['map']['cells'], origin=world.origin)
        write(case/'post-reset-trajectory.json', env.backend.trajectory)
        evidence['status'] = 'P0-P4 CANDIDATE PASS; independent review required before formal training'
    except Exception as error:
        evidence['status'] = 'BLOCKED'
        evidence['first_failure'] = f'{type(error).__name__}: {error}'
        evidence['traceback'] = traceback.format_exc()
        if 'env' in locals() and hasattr(env.backend, 'goals'):
            evidence['stop_after_failure'] = env.backend.stop('gate_failure')
            write(case/'failure-trajectory.json', env.backend.trajectory)
        raise
    finally:
        ledger.flush('gate_end')
        evidence['ledger_totals'] = dict(ledger.counts)
        write(case/'result.json', evidence)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--initial', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.initial)

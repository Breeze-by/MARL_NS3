"""Fixed-budget RL01 driver. Do not run train before independent P0-P4 review."""
import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import pickle
import resource
import sys
import time
import traceback
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import KEEP, WAIT
from multi_robot_exploration.joint import JointTraditionalPolicy
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend
from multi_robot_exploration.rl_env import RLEnvironment
from multi_robot_exploration.ppo import ActorCritic, PPOPolicy, encode, gae, update, save_checkpoint, load_checkpoint
from completion import validate_development_checkpoint


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def append(path, value):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(value, allow_nan=False)+'\n')


def plain(value):
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(plain(item) for item in value)
    if isinstance(value, np.ndarray):
        return value.copy()
    return value


def make_env(config, ledger, variant, seed):
    with ledger.call('world_projection_build', variant=variant):
        world = ProjectedWorld(WORKSPACE/'src/multi_robot/worlds/my_world.world',
                               WORKSPACE.parents[1]/'base-01-econ/assets/gazebo_models', variant)
    if not np.allclose(world.bounds, config['task_roi'], atol=1e-10):
        raise ValueError('Task ROI differs from predeclared configuration')
    return RLEnvironment(KinematicBackend(world, config['backend'], ledger, seed), None, config, ledger)


def next_value(model, observation, terminated):
    if terminated:
        return 0.
    with torch.no_grad():
        _, value = model(torch.from_numpy(model.encode(observation))[None])
    return float(value[0])


def train(case, initial):
    case.mkdir(parents=True, exist_ok=False)
    config = json.loads((HERE/'config.json').read_text())
    dump(case/'config.json', config)
    ledger = Ledger(case/'ledger.jsonl', 'formal')
    torch.set_num_threads(config['torch_threads'])
    model = ActorCritic(ledger, config['hidden'])
    load_checkpoint(initial, model, restore_rng=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    rng = np.random.default_rng(config['training_seed'])
    env = make_env(config, ledger, config['train_map'], config['training_seed'])
    start = time.monotonic()
    rollout, nonforced, completed, episode = [], 0, 0, 0
    before_actor = model.actor.weight.detach().clone()
    source_identity = {str(path.relative_to(WORKSPACE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*WORKSPACE.glob('src/multi_robot_exploration/multi_robot_exploration/*.py'), HERE/'config.json', HERE/'run.py']}
    dump(case/'source-identity.json', source_identity)
    error = None
    try:
        observation, _ = env.reset()
        for decision in range(config['formal_joint_decisions']):
            record = model.act(observation)
            ledger.add('formal_joint_decisions_attempted')
            observation, reward, terminated, truncated, info = env.step(record['action'])
            if info['rejected_actions'] or not info['bootstrap_valid']:
                raise RuntimeError('Invalid sampled action or untrustworthy final observation: '+str(info))
            record.update(reward=reward, terminated=terminated, truncated=truncated,
                          next_value=next_value(model, observation, terminated))
            rollout.append(record)
            nonforced += record['choice_rows'] > 0
            completed += 1
            ledger.add('formal_rollout_unique_samples')
            ledger.flush('formal_rollout_sample', decision=completed, choice_rows=record['choice_rows'])
            append(case/'decisions.jsonl', dict(decision=completed, episode=episode,
                   choices=record['action'].choices, choice_rows=record['choice_rows'], reward=reward,
                   coverage=info['coverage'], sim=env.backend.sim, paths_m=info['paths_m'],
                   terminated=terminated, truncated=truncated, reason=info['reason'],
                   keep_count=record['action'].choices.count(KEEP), wait_count=record['action'].choices.count(WAIT)))
            if terminated or truncated:
                append(case/'episodes.jsonl', dict(episode=episode, decisions=env.decisions, **info))
                dump(case/f'episode-{episode:04d}-trajectory.json', env.backend.trajectory)
                dump(case/f'episode-{episode:04d}-navigation.json', env.backend.event_log)
                episode += 1
            if len(rollout) == config['rollout'] or completed == config['formal_joint_decisions']:
                advantages, returns = gae([r['reward'] for r in rollout], [r['value'] for r in rollout],
                    [r['next_value'] for r in rollout], [r['terminated'] for r in rollout],
                    [r['truncated'] for r in rollout], config['gamma'], config['gae_lambda'])
                for item, advantage, target in zip(rollout, advantages, returns):
                    item.update(advantage=float(advantage), **{'return': float(target)})
                diagnostics = update(model, optimizer, rollout, config, ledger, rng)
                for item in diagnostics:
                    append(case/'updates.jsonl', dict(after_joint_decisions=completed, **item))
                rollout.clear()
            if completed % config['checkpoint_interval'] == 0:
                save_checkpoint(case/f'checkpoint-{completed:05d}.pt', model, optimizer,
                                config=config, task_roi=config['task_roi'], joint_decisions=completed,
                                source_sha256=source_identity, fixed_development_checkpoint=True)
            if (terminated or truncated) and completed < config['formal_joint_decisions']:
                observation, _ = env.reset()
        if nonforced == 0 or float((model.actor.weight.detach()-before_actor).norm()) == 0:
            raise RuntimeError('No actual goal-choice learning update')
        validate_development_checkpoint(dict(metadata=dict(failure=None, joint_decisions=completed, config=config),
                                            optimizer=optimizer.state_dict()), config)
    except BaseException as failure:
        error = dict(type=type(failure).__name__, message=str(failure), traceback=traceback.format_exc())
        dump(case/'first-failure.json', error)
        raise
    finally:
        if env.allocator is not None:
            env.allocator.stop('formal_end' if error is None else 'formal_failure')
        if hasattr(env.backend, 'goals'):
            stopped = env.backend.stop('formal_end' if error is None else 'formal_failure')
            dump(case/'last-trajectory.json', env.backend.trajectory)
            dump(case/'last-navigation.json', env.backend.event_log)
        else:
            stopped = False
        save_checkpoint(case/('final.pt' if error is None else 'failed.pt'), model, optimizer,
                        config=config, task_roi=config['task_roi'], joint_decisions=completed,
                        source_sha256=source_identity, failure=error, initial_sha256=hashlib.sha256(initial.read_bytes()).hexdigest())
        ledger.flush('formal_end', error=error)
        dump(case/'summary.json', dict(status='BOUNDED TRAINING PASS' if error is None and stopped else 'FAIL',
              actual_joint_decisions=completed, nonforced_decisions=nonforced,
              choice_fraction=nonforced/max(1, completed), actor_head_weight_change=float((model.actor.weight.detach()-before_actor).norm()),
              wall_seconds=time.monotonic()-start, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              threads=torch.get_num_threads(), stop_verified=stopped, ledger_totals=dict(ledger.counts)))


def evaluate(case, initial, trained):
    case.mkdir(parents=True, exist_ok=False)
    config = json.loads((HERE/'config.json').read_text())
    dump(case/'config.json', config)
    ledger = Ledger(case/'ledger.jsonl', 'evaluation')
    torch.set_num_threads(config['torch_threads'])
    initial_model, trained_model = ActorCritic(ledger), ActorCritic(ledger)
    load_checkpoint(initial, initial_model)
    metadata = load_checkpoint(trained, trained_model)
    validate_development_checkpoint(torch.load(trained, map_location='cpu', weights_only=False), config)
    if metadata['config'] != config or metadata['failure'] is not None:
        raise ValueError('Evaluation checkpoint/config is not the fixed successful development result')
    policies = dict(initial=PPOPolicy(initial_model), trained=PPOPolicy(trained_model), traditional=JointTraditionalPolicy())
    saved_states, rows = [], []
    for variant in config['evaluation_maps']:
        for seed in config['evaluation_seeds']:
            for name in config['evaluation_policies']:
                label = f'{variant}-{seed}-{name}'
                env = make_env(config, ledger, variant, seed)
                observation, _ = env.reset()
                episode_states, infer_seconds, choices_rows = [], 0., []
                try:
                    while not env.done:
                        if name == 'initial' and len(saved_states) < 400:
                            saved_states.append(plain(observation))
                        start = time.perf_counter()
                        action = policies[name].select(observation)
                        infer_seconds += time.perf_counter()-start
                        choices_rows.append(action.choices)
                        ledger.add('evaluation_joint_decisions_attempted')
                        observation, reward, terminated, truncated, info = env.step(action)
                        append(case/f'{label}-decisions.jsonl', dict(choices=action.choices,
                               decision=env.decisions, reward=reward, coverage=info['coverage'],
                               sim=env.backend.sim, terminated=terminated, truncated=truncated,
                               rejections=info['rejected_actions'], reason=info['reason']))
                        if name != 'traditional' and info['rejected_actions']:
                            raise RuntimeError('Learned/masked policy failed common allocator gate')
                    rows.append(dict(case=label, map=variant, seed=seed, policy=name,
                                     decisions=env.decisions, inference_total_seconds=infer_seconds,
                                     inference_mean_seconds=infer_seconds/max(1, env.decisions), **info))
                    dump(case/f'{label}-trajectory.json', env.backend.trajectory)
                    dump(case/f'{label}-navigation.json', env.backend.event_log)
                    dump(case/'results.json', rows)
                finally:
                    if not env.done:
                        env.allocator.stop('evaluation_error')
                        env.backend.stop('evaluation_error')
    # Preplanned offline replay: same observed states, no additional environment step.
    differences = []
    with (case/'initial-observed-states.pkl').open('wb') as stream:
        pickle.dump(saved_states, stream)
    ledger.phase = 'evaluation_offline_replay'
    for index, observation in enumerate(saved_states):
        original = initial_model.act(observation, deterministic=True)
        learned = trained_model.act(observation, deterministic=True)
        differences.append(dict(state=index, nonforced=original['choice_rows'] > 0,
                                initial=original['action'].choices, trained=learned['action'].choices,
                                changed=original['action'].choices != learned['action'].choices))
    dump(case/'behavior-replay.json', differences)
    ledger.flush('evaluation_end')
    dump(case/'summary.json', dict(episodes=len(rows), ledger_totals=dict(ledger.counts),
                                  scientific_status='NO SCIENTIFIC PASS; development only',
                                  replay_states=len(saved_states), changed_states=sum(r['changed'] for r in differences)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('train', 'evaluate'))
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--initial', type=Path, required=True)
    parser.add_argument('--trained', type=Path)
    args = parser.parse_args()
    if args.mode == 'train':
        train(args.case, args.initial)
    else:
        if args.trained is None:
            parser.error('--trained is required for evaluate')
        evaluate(args.case, args.initial, args.trained)

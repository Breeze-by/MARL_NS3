"""Registered two-condition PPO driver; never selects or visits TEST."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time
import traceback
import numpy as np
import torch

from maps import HERE, WORKSPACE, PROJECT, ROOT, dump, sha
from diagnose import verify_lock, append, plain
from execution import Episode
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint, save_checkpoint, gae, update


class SharedStageFatal(RuntimeError):
    pass


def check_budget(deadline, fatal_path):
    if fatal_path.exists():
        raise SharedStageFatal('Another formal run has stopped the shared stage: '+str(fatal_path))
    if time.monotonic() >= deadline:
        raise TimeoutError('Registered per-run formal and validation wall budget reached')


def save_fatal(path, failure):
    # Two authorized processes share exactly this first-fatal signal; keep the
    # original cause if both fail. This is not a retry or job framework.
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(failure, indent=2)+'\n')


def validate_checkpoint(path, run_summary):
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    metadata = checkpoint['metadata']
    completed = metadata['joint_decisions']
    if run_summary['status'] != 'BOUNDED TRAINING PASS' or run_summary['actual_joint_decisions'] != 4096:
        raise ValueError('Checkpoint parent did not finish its registered run')
    if completed not in (1024, 2048, 3072, 4096) or metadata.get('failure') is not None:
        raise ValueError('Checkpoint is not a registered successful-parent candidate')
    expected = completed//256*8
    steps = {int(s['step']) for s in checkpoint['optimizer']['state'].values()}
    if steps != {expected} or not all(torch.isfinite(p).all() for p in checkpoint['model'].values()):
        raise ValueError('Checkpoint optimizer or parameter identity mismatch')
    return checkpoint


def validation(model, maps, config, output, after_joint, deadline, fatal_path):
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(output/'ledger.jsonl', 'formal_validation')
    previous_ledger = model.ledger
    model.ledger = ledger
    before = {k: p.detach().clone() for k, p in model.state_dict().items()}
    results, active = [], None
    try:
        for index, row in enumerate(r for r in maps if r['split'] == 'VAL'):
            check_budget(deadline, fatal_path)
            pose = next(p for p in row['positions'] if p['seed'] == 201)
            active = Episode(row, pose, 100000+after_joint*10+index, config, ledger,
                             output/f'{index:02d}-{row["name"]}-201', 'rl', fatal_idle=True)
            while not active.env.done:
                check_budget(deadline, fatal_path)
                active.step(model, deterministic=True, bootstrap=False)
            closed, active = active, None
            results.append(closed.finish('validation_end'))
        if not all(torch.equal(before[k], p) for k, p in model.state_dict().items()):
            raise ValueError('Validation changed model parameters')
    except BaseException as error:
        dump(output/'first-failure.json', dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
        raise
    finally:
        model.ledger = previous_ledger
        if active is not None:
            active.finish('validation_failure')
        ledger.flush('validation_end', completed_cases=len(results))
    result = dict(after_joint_decisions=after_joint, cases=results, counts=dict(ledger.counts),
        natural_complete_rate=sum(r['natural_complete'] for r in results)/3,
        mean_coverage=float(np.mean([r['coverage'] for r in results])),
        penalty_T95_mean=float(np.mean([r['coverage_times'].get('0.95', 500.) for r in results])),
        total_path_m=sum(sum(r['paths_m'].values()) for r in results),
        optimizer_steps=0, model_weights_unchanged=True)
    dump(output/'summary.json', result)
    return result


def train(run_number, output):
    verify_lock()
    seal = json.loads((HERE/'P3_LOCK.json').read_text())
    for path, expected in seal['sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError('Formal source changed after registration: '+path)
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((HERE/'config.json').read_text())
    seed = config['run_seeds'][run_number-1]
    config.update(training_seed=seed, initialization='rl01_weights_only' if run_number == 1 else 'independent_random')
    maps = json.loads((ROOT/seal['maps_manifest']).read_text())
    pairs = [(r, p) for r in maps if r['split'] == 'TRAIN' for p in r['positions']]
    if len(pairs) != 32:
        raise ValueError('TRAIN map/position balance differs from registered corpus')
    fatal_path = output.parent/'FORMAL_FATAL.json'
    if fatal_path.exists():
        raise SharedStageFatal('Shared formal stage already closed')
    ledger = Ledger(output/'ledger.jsonl', f'formal_run_{run_number}')
    torch.set_num_threads(config['torch_threads'])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    model = ActorCritic(ledger, config['hidden'])
    warm = ROOT/'rl-01/runs/formal-01/case/final.pt'
    if run_number == 1:
        if sha(warm) != '415139fa922f1af23f343f98b53720be971736c6e71eb8ee9ba28835e10f72b4':
            raise ValueError('Warm-start model identity mismatch')
        load_checkpoint(warm, model, restore_rng=False)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    rng = np.random.default_rng(seed+23)
    map_rng = np.random.default_rng(seed+17)
    order = list(map_rng.permutation(len(pairs)))
    cursor = 0
    start = time.monotonic()
    deadline = start+config['formal_wall_seconds_per_run']
    metadata = dict(config=config, task_roi=config['task_roi'], run_number=run_number,
        p3_lock_sha256=sha(HERE/'P3_LOCK.json'), source_commit=seal['source_commit_before_seal'],
        runtime_commit=subprocess.check_output(['git', '-C', str(WORKSPACE), 'rev-parse', 'HEAD'], text=True).strip(),
        initialization=config['initialization'], initial_source_sha256=sha(warm) if run_number == 1 else None)
    dump(output/'binding.json', metadata)
    save_checkpoint(output/'initial.pt', model, optimizer, joint_decisions=0, failure=None, **metadata)
    initial_actor = model.actor.weight.detach().clone()
    initial_critic = model.critic.weight.detach().clone()
    head_gradients = []

    def capture_head_gradient(gradient):
        head_gradients.append(gradient.detach().reshape(3, 17, -1).norm(dim=(1, 2)).tolist())

    handle = model.actor.weight.register_hook(capture_head_gradient)
    completed, serial, active = 0, 0, None
    rollout, validations, summaries = [], [], []
    nonforced = np.zeros(3, dtype=int)
    error, resource_cut = None, False
    try:
        while completed < config['formal_joint_decisions']:
            check_budget(deadline, fatal_path)
            if active is None:
                if cursor == len(order):
                    order, cursor = list(map_rng.permutation(len(pairs))), 0
                row, pose = pairs[order[cursor]]
                cursor += 1
                active = Episode(row, pose, serial, config, ledger, output/'episodes'/f'{serial:05d}', 'rl', fatal_idle=True)
                serial += 1
            ledger.add('formal_joint_decisions_attempted')
            record = active.step(model, deterministic=False, bootstrap=True)
            rollout.append(record)
            completed += 1
            nonforced += record['masks'].sum(axis=1) > 1
            ledger.add('formal_rollout_unique_samples')
            ledger.flush('formal_sample', joint=completed, episode=serial-1)
            if active.env.done:
                closed, active = active, None
                result = closed.finish('formal_episode_end')
                summaries.append(result)
                append(output/'episodes.jsonl', dict(episode=serial-1, **result))
            if len(rollout) == config['rollout'] or completed == config['formal_joint_decisions']:
                check_budget(deadline, fatal_path)
                advantages, returns = gae([r['reward'] for r in rollout], [r['value'] for r in rollout],
                    [r['next_value'] for r in rollout], [r['terminated'] for r in rollout],
                    [r['truncated'] for r in rollout], config['gamma'], config['gae_lambda'])
                for record, advantage, target in zip(rollout, advantages, returns):
                    record.update(advantage=float(advantage), **{'return': float(target)})
                np.savez_compressed(output/f'rollout-{completed:05d}.npz',
                    **{k: np.stack([r[k] for r in rollout]) for k in ('inputs', 'masks', 'slots')},
                    **{k: np.array([r[k] for r in rollout]) for k in
                       ('reward', 'value', 'next_value', 'logprob', 'terminated', 'truncated', 'advantage', 'return')})
                before_actor = model.actor.weight.detach().clone()
                head_gradients.clear()
                diagnostics = update(model, optimizer, rollout, config, ledger, rng)
                if len(head_gradients) != len(diagnostics):
                    raise RuntimeError('Actor gradient telemetry missed an actual optimizer minibatch')
                changes = (model.actor.weight.detach()-before_actor).reshape(3, 17, -1).norm(dim=(1, 2)).tolist()
                for diagnostic, gradients in zip(diagnostics, head_gradients):
                    append(output/'updates.jsonl', dict(after_joint_decisions=completed,
                        per_head_actor_weight_gradient=gradients, **diagnostic))
                append(output/'rollouts.jsonl', dict(after_joint_decisions=completed,
                    actual_unique_samples=len(rollout), per_head_actor_weight_change=changes,
                    nonforced_per_head=np.stack([r['masks'].sum(axis=1) > 1 for r in rollout]).sum(axis=0)))
                rollout.clear()
            if completed % config['checkpoint_interval'] == 0:
                checkpoint = output/f'checkpoint-{completed:05d}.pt'
                save_checkpoint(checkpoint, model, optimizer, joint_decisions=completed, failure=None, **metadata)
                result = validation(model, maps, config, output/'validation'/f'{completed:05d}',
                    completed, deadline, fatal_path)
                result['checkpoint_sha256'] = sha(checkpoint)
                validations.append(result)
                append(output/'validation.jsonl', result)
        steps = {int(s['step']) for s in optimizer.state_dict()['state'].values()}
        if completed != 4096 or steps != {128} or ledger.counts['env_step'] != 4096 or ledger.counts['optimizer_step'] != 128:
            raise RuntimeError('Registered formal update budget incomplete')
    except BaseException as failure:
        error = dict(run_number=run_number, type=type(failure).__name__, message=str(failure),
                     traceback=traceback.format_exc(), actual_joint_decisions=completed)
        resource_cut = isinstance(failure, TimeoutError)
        dump(output/'first-failure.json', error)
        if not resource_cut:
            save_fatal(fatal_path, error)
        raise
    finally:
        if active is not None:
            closed, active = active, None
            try:
                result = closed.finish('formal_resource_wall' if resource_cut else 'formal_failure' if error else 'formal_global_budget_partial_tail')
                summaries.append(result)
                append(output/'episodes.jsonl', dict(episode=serial-1, **result))
            except BaseException as stop_failure:
                stop_error = dict(run_number=run_number, type=type(stop_failure).__name__, message=str(stop_failure), traceback=traceback.format_exc())
                dump(output/'stop-failure.json', stop_error)
                if error is None:
                    error = stop_error
                save_fatal(fatal_path, stop_error)
        handle.remove()
        status = 'RESOURCE TRUNCATED' if resource_cut else 'FAIL' if error else 'BOUNDED TRAINING PASS'
        save_checkpoint(output/('final.pt' if error is None else 'failed.pt'), model, optimizer,
                        joint_decisions=completed, failure=error, **metadata)
        ledger.flush('formal_end', status=status, actual_joint=completed)
        result = dict(status=status, run_number=run_number, initialization=config['initialization'],
            actual_joint_decisions=completed, counts=dict(ledger.counts), validation_checkpoints=len(validations),
            nonforced_per_head=nonforced.tolist(),
            per_head_actor_weight_change=(model.actor.weight.detach()-initial_actor).reshape(3, 17, -1).norm(dim=(1, 2)).tolist(),
            critic_weight_change=float((model.critic.weight.detach()-initial_critic).norm()),
            episode_outcomes=dict(__import__('collections').Counter(r['end_reason'] for r in summaries)),
            native_exit_status_must_be_checked=True, wall_seconds=time.monotonic()-start,
            failure=error, final_sha256=sha(output/('final.pt' if error is None else 'failed.pt')),
            policy_formally_frozen=False, test_episodes=0, gazebo_formal_runs=0)
        dump(output/'summary.json', result)
        print(json.dumps(result, indent=2), flush=True)
    if error is not None:
        raise RuntimeError('Formal run failed during final stop or evidence sealing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=int, choices=(1, 2), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise SystemExit(f'Formal process received signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        train(args.run, args.output.resolve())
    except BaseException as failure:
        if not isinstance(failure, TimeoutError):
            fatal = args.output.resolve().parent/'FORMAL_FATAL.json'
            fatal.parent.mkdir(parents=True, exist_ok=True)
            save_fatal(fatal, dict(run_number=args.run, type=type(failure).__name__,
                message=str(failure), traceback=traceback.format_exc(), phase='startup_or_formal_fatal'))
        raise

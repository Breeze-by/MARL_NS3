"""Audit completed native formal runs from saved batches and actual trajectories."""
from collections import Counter
import json
import math
from pathlib import Path
import numpy as np
import torch
from maps import HERE, ROOT, PROJECT, dump, sha
from multi_robot_exploration.ppo import gae


def trajectory_audit(folder, summary, projected):
    trace = json.loads((folder/'trajectory.json').read_text())
    poses = np.asarray([[t['poses'][r] for r in ('tb1', 'tb2', 'tb3')] for t in trace])
    times = np.asarray([t['sim'] for t in trace])
    changes = np.diff(poses, axis=0)
    dt = np.diff(times)
    valid = dt > 1e-9
    distances = np.linalg.norm(changes[:, :, :2], axis=2)
    yaw_change = np.abs((changes[:, :, 2]+math.pi) % (2*math.pi)-math.pi)
    maximum_v = float(np.max(distances[valid]/dt[valid, None])) if valid.any() else 0.
    maximum_w = float(np.max(yaw_change[valid]/dt[valid, None])) if valid.any() else 0.
    paths = distances.sum(axis=0)
    path_error = float(np.max(np.abs(paths-[summary['paths_m'][r] for r in ('tb1', 'tb2', 'tb3')])))
    minimum_pair = math.inf
    for a, b in ((0, 1), (0, 2), (1, 2)):
        relative = poses[:-1, a, :2]-poses[:-1, b, :2]
        delta = changes[:, a, :2]-changes[:, b, :2]
        denominator = (delta*delta).sum(axis=1)
        proportion = np.zeros_like(denominator)
        np.divide(-(relative*delta).sum(axis=1), denominator, out=proportion, where=denominator > 0)
        proportion = np.clip(proportion, 0, 1)
        minimum_pair = min(minimum_pair, float(np.linalg.norm(relative+proportion[:, None]*delta, axis=1).min()))
    xy = poses[:, :, :2]
    columns_rows = np.floor((xy-projected['origin'])/float(projected['resolution'])).astype(int)
    columns, rows = columns_rows[:, :, 0], columns_rows[:, :, 1]
    h, w = projected['clearance'].shape
    inside = (columns >= 0) & (columns < w) & (rows >= 0) & (rows < h)
    clear = np.zeros_like(inside)
    clear[inside] = projected['clearance'][rows[inside], columns[inside]] >= .25-1e-10
    return dict(max_linear_m_s=maximum_v, max_angular_rad_s=maximum_w,
        max_path_error_m=path_error, minimum_continuous_pair_m=minimum_pair,
        zero_time_motion=bool(np.any((distances > 1e-9) & ~valid[:, None]) or np.any((yaw_change > 1e-9) & ~valid[:, None])),
        sampled_body_clearance_violations=int(np.count_nonzero(~clear)), actual_pose_records=len(trace))


def run():
    target = PROJECT/'evidence/formal-completion-audit.json'
    if target.exists():
        raise FileExistsError('Do not overwrite a completed formal audit')
    lock = json.loads((HERE/'P1_LOCK.json').read_text())
    maps = {m['name']: m for m in json.loads((ROOT/lock['maps_manifest']).read_text())}
    projections = {name: np.load(ROOT/lock['map_qualification']/name/'projection.npz') for name in maps}
    reports = []
    for number in (1, 2):
        case = PROJECT/f'runs/formal-{number:02d}'
        summary = json.loads((case/'summary.json').read_text())
        native = json.loads((case/'process-exit.json').read_text())
        ledger = Counter()
        for line in (case/'ledger.jsonl').read_text().splitlines():
            ledger.update(json.loads(line)['delta'])
        violations = []
        if native['exit_code'] != 0 or summary['status'] != 'BOUNDED TRAINING PASS':
            violations.append('registered_native_run_not_successful')
        batches = sorted(case.glob('rollout-*.npz'))
        samples, nonforced, gae_error = 0, np.zeros(3, dtype=int), 0.
        for path in batches:
            data = np.load(path)
            n = len(data['reward'])
            samples += n
            nonforced += (data['masks'].sum(axis=2) > 1).sum(axis=0)
            legal = np.take_along_axis(data['masks'], data['slots'][:, :, None], axis=2)
            if not legal.all() or not np.isfinite(data['inputs']).all():
                violations.append('stored_rollout_illegal_slot_or_nonfinite_input')
            advantage, returns = gae(data['reward'], data['value'], data['next_value'],
                data['terminated'], data['truncated'])
            gae_error = max(gae_error, float(np.max(np.abs(advantage-data['advantage']))),
                            float(np.max(np.abs(returns-data['return']))))
        if samples != 4096 or ledger['env_step'] != 4096 or ledger['optimizer_step'] != 128 or ledger['optimizer_replay_samples'] != 16384:
            violations.append('actual_formal_or_replay_budget_mismatch')
        if gae_error > 1e-6 or nonforced.tolist() != summary['nonforced_per_head']:
            violations.append('GAE_or_per_head_nonforced_accounting_mismatch')
        updates = [json.loads(s) for s in (case/'updates.jsonl').read_text().splitlines()]
        head_gradients = np.asarray([r['per_head_actor_weight_gradient'] for r in updates])
        before = torch.load(case/'initial.pt', map_location='cpu', weights_only=False)
        after = torch.load(case/'final.pt', map_location='cpu', weights_only=False)
        delta = (after['model']['actor.weight']-before['model']['actor.weight']).reshape(3, 17, -1).norm(dim=(1, 2)).tolist()
        if number == 1:
            old = torch.load(ROOT/'rl-01/runs/formal-01/case/final.pt', map_location='cpu', weights_only=False)
            if not all(torch.equal(before['model'][k], v) for k, v in old['model'].items()):
                violations.append('declared_weights_only_warm_start_not_exact')
        episodes = [json.loads(s) for s in (case/'episodes.jsonl').read_text().splitlines()]
        if sum(e['actual_joint'] for e in episodes) != 4096:
            violations.append('episode_transition_accounting_mismatch')
        aggregate = dict(max_linear_m_s=0., max_angular_rad_s=0., max_path_error_m=0.,
            minimum_continuous_pair_m=math.inf, sampled_body_clearance_violations=0, actual_pose_records=0)
        for folder in sorted((case/'episodes').iterdir()):
            item = json.loads((folder/'summary.json').read_text())
            actual = trajectory_audit(folder, item, projections[item['map']])
            for key in ('max_linear_m_s', 'max_angular_rad_s', 'max_path_error_m'):
                aggregate[key] = max(aggregate[key], actual[key])
            aggregate['minimum_continuous_pair_m'] = min(aggregate['minimum_continuous_pair_m'], actual['minimum_continuous_pair_m'])
            for key in ('sampled_body_clearance_violations', 'actual_pose_records'):
                aggregate[key] += actual[key]
            if actual['zero_time_motion']:
                violations.append('physical_state_jump_at_zero_time')
        if aggregate['max_linear_m_s'] > .26+1e-8 or aggregate['max_angular_rad_s'] > 1.+1e-8 or aggregate['minimum_continuous_pair_m'] < .7-1e-9 or aggregate['max_path_error_m'] > 1e-8 or aggregate['sampled_body_clearance_violations']:
            violations.append('stored_trajectory_physical_contract_violation')
        reports.append(dict(run=number, status='PASS' if not violations else 'FAIL', violations=violations,
            formal_counts=dict(ledger), saved_unique_samples=samples, GAE_max_abs_error=gae_error,
            nonforced_per_head=nonforced.tolist(), per_head_actor_weight_change=delta,
            per_head_nonzero_gradient_minibatches=(head_gradients > 0).sum(axis=0).tolist(),
            actual_optimizer_minibatches=len(updates), final_sha256=sha(case/'final.pt'),
            initialization=summary['initialization'], actual_episodes=len(episodes), trajectory=aggregate,
            natural_complete_episodes=sum(e['natural_complete'] for e in episodes),
            partial_global_budget_tails=sum(e['externally_cut'] for e in episodes)))
    result = dict(status='FORMAL AUDIT PASS' if all(r['status'] == 'PASS' for r in reports) else 'FORMAL AUDIT FAIL',
        runs=reports, audit_nn_forward=0, audit_env_step=0, audit_optimizer_step=0,
        physical_stop_verified=False, formally_frozen=False)
    dump(target, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()

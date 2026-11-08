"""Audit saved locked TEST physics, reset parity and accounting; no rollout."""
from collections import Counter
import json
import math
import numpy as np
from maps import PROJECT, ROOT, HERE, dump
from audit_training import trajectory_audit


def audit():
    root = PROJECT/'runs/test-01'
    whole = json.loads((root/'summary.json').read_text())
    native = json.loads((root/'process-exit.json').read_text())
    lock = json.loads((HERE/'P1_LOCK.json').read_text())
    maps = {m['name']: m for m in json.loads((ROOT/lock['maps_manifest']).read_text())}
    projections = {name: np.load(ROOT/lock['map_qualification']/name/'projection.npz') for name in maps}
    reports, violations = [], []
    totals = Counter()
    for folder in sorted(p.parent for p in root.glob('*/summary.json')):
        summary = json.loads((folder/'summary.json').read_text())
        scene = maps[summary['map']]
        pose = next(p for p in scene['positions'] if p['seed'] == summary['seed'])
        projected = projections[summary['map']]
        initial = json.loads((folder/'case.json').read_text())
        grids = np.load(folder/'observed-grids.npz')['cells']
        reference = projected['reference_free']
        before_coverage = float(np.count_nonzero((grids[0] >= 0) & reference)/reference.sum())
        coverage = float(np.count_nonzero((grids[-1] >= 0) & reference)/reference.sum())
        errors = []
        if not np.allclose(initial['positions'], pose['positions'], atol=1e-10):
            errors.append('not_registered_actual_positions')
        expected_initial = pose['attempts'][-1]['initial_coverage']
        if abs(before_coverage-expected_initial) > 1e-12:
            errors.append('initial_scan_or_seed_differs_from_locked_qualification')
        if abs(coverage-summary['coverage']) > 1e-12:
            errors.append('fixed_reference_final_coverage_mismatch')
        if summary['natural_complete'] != bool(coverage >= .95 and summary['raw_terminated'] and summary['stop_verified_kinematic']):
            errors.append('natural_completion_or_stop_certificate_mismatch')
        rows = [json.loads(s) for s in (folder/'decisions.jsonl').read_text().splitlines()]
        intents = (folder/'intents.jsonl').read_text().splitlines()
        if len(rows) != summary['actual_joint'] or len(intents) != len(rows) or len(rows) > 100:
            errors.append('attempt_transition_or_episode_budget_mismatch')
        actual = trajectory_audit(folder, summary, projected)
        if actual['max_linear_m_s'] > .26+1e-8 or actual['max_angular_rad_s'] > 1.+1e-8 or actual['minimum_continuous_pair_m'] < .7-1e-9 or actual['max_path_error_m'] > 1e-8 or actual['zero_time_motion'] or actual['sampled_body_clearance_violations']:
            errors.append('stored_proxy_physical_contract_violation')
        totals['env_step'] += len(rows)
        if summary['policy'] == 'rl':
            totals['policy_forward'] += len(rows)
        if errors:
            violations.append(dict(case=folder.name, errors=errors))
        reports.append(dict(case=folder.name, policy=summary['policy'], initial_coverage=before_coverage,
            final_coverage=coverage, actual_joint=len(rows), physical=actual, errors=errors))
    if len(reports) != 36 or native['exit_code'] != 0 or not whole['model_weights_unchanged']:
        violations.append('incomplete_test_or_changed_model')
    if totals['env_step'] != whole['counts']['env_step'] or totals['policy_forward'] != whole['counts']['policy_forward']:
        violations.append('real_call_ledger_does_not_match_cases')
    result = dict(status='TEST DATA AUDIT PASS' if not violations else 'TEST DATA AUDIT FAIL',
        violations=violations, cases=reports, actual_totals=dict(totals),
        minimum_continuous_pair_m=min(r['physical']['minimum_continuous_pair_m'] for r in reports),
        max_linear_m_s=max(r['physical']['max_linear_m_s'] for r in reports),
        max_angular_rad_s=max(r['physical']['max_angular_rad_s'] for r in reports),
        max_trajectory_path_error_m=max(r['physical']['max_path_error_m'] for r in reports),
        audit_nn_forward=0, audit_env_step=0, audit_optimizer_step=0,
        actual_nav2_or_gazebo_verified=False, physical_stop_verified=False)
    target = root/'data-audit.json'
    if target.exists():
        raise FileExistsError('Completed TEST data audit already exists')
    dump(target, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    audit()

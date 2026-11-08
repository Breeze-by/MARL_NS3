"""Read the single P2 run; no extra forward, reset, step or optimization."""
from collections import Counter
import json
import math
from pathlib import Path
import pickle
import numpy as np
from diagnose import ROOT, PROJECT, ROBOTS, dump
from multi_robot_exploration.rl_backend import swept_pair_distance


def analyse():
    source = PROJECT/'evidence/p2-diagnosis-01'
    summary = json.loads((source/'summary.json').read_text())
    maps = {r['name']: r for r in json.loads((PROJECT/'evidence/map-qualification-01/maps.json').read_text())}
    config = json.loads((source/'binding.json').read_text())['config']
    per_head = np.zeros(3, dtype=int)
    cases, all_costs, violations = [], [], []
    minimum_pair, max_linear, max_angular, max_path_error = math.inf, 0., 0., 0.
    for folder in sorted(p.parent for p in source.glob('*/summary.json')):
        item = json.loads((folder/'summary.json').read_text())
        row = maps[item['map']]
        decisions = [json.loads(s) for s in (folder/'decisions.jsonl').read_text().splitlines()]
        with (folder/'records.pkl').open('rb') as stream:
            records = pickle.load(stream)
        trace = json.loads((folder/'trajectory.json').read_text())
        corrected_idle = dict.fromkeys(ROBOTS, 0.)
        choice_counts = np.zeros(3, dtype=int)
        previous_sim = 0.
        reward = 0.
        for index, (decision, record) in enumerate(zip(decisions, records)):
            options = record['masks'].sum(axis=1)
            choice_counts += options > 1
            accepted = {e['robot'] for e in decision['actual_events'] if e['kind'] == 'accepted'}
            elapsed = decision['sim']-previous_sim
            for i, robot in enumerate(ROBOTS):
                if record['masks'][i, :15].any() and robot not in accepted:
                    corrected_idle[robot] += elapsed
                if not record['masks'][i, record['slots'][i]]:
                    violations.append([folder.name, index, 'sampled_slot_not_legal'])
            terms = decision['reward_terms']
            calculated = sum(terms[k]*v for k, v in config['reward'].items())
            if abs(calculated-record['reward']) > 1e-10:
                violations.append([folder.name, index, 'reward_does_not_reconcile'])
            reward += calculated
            previous_sim = decision['sim']
            all_costs.append(decision['step_wall_s'])
        if abs(reward-item['reward_total']) > 1e-10:
            violations.append([folder.name, 'episode_reward_sum_mismatch'])
        per_head += choice_counts
        integrated_paths = dict.fromkeys(ROBOTS, 0.)
        for before, after in zip(trace[:-1], trace[1:]):
            dt = after['sim']-before['sim']
            for robot in ROBOTS:
                a, b = np.array(before['poses'][robot]), np.array(after['poses'][robot])
                distance = float(np.linalg.norm(b[:2]-a[:2]))
                integrated_paths[robot] += distance
                yaw_change = abs((b[2]-a[2]+math.pi) % (2*math.pi)-math.pi)
                if dt > 1e-9:
                    max_linear = max(max_linear, distance/dt)
                    max_angular = max(max_angular, yaw_change/dt)
                elif distance > 1e-9 or yaw_change > 1e-9:
                    violations.append([folder.name, 'state_jump_without_time'])
            for i, a in enumerate(ROBOTS):
                for b in ROBOTS[i+1:]:
                    distance = swept_pair_distance(np.array(before['poses'][a][:2]), np.array(after['poses'][a][:2]),
                        np.array(before['poses'][b][:2]), np.array(after['poses'][b][:2]))
                    minimum_pair = min(minimum_pair, distance)
        max_path_error = max(max_path_error, *(abs(integrated_paths[r]-item['paths_m'][r]) for r in ROBOTS))
        pose = next(p for p in row['positions'] if p['seed'] == item['seed'])
        if not all(np.allclose(trace[0]['poses'][r][:2], p, atol=1e-10) for r, p in zip(ROBOTS, pose['positions'])):
            violations.append([folder.name, 'not_registered_initial_positions'])
        last = decisions[-1]['observation']
        cases.append(dict(case=folder.name, end_reason=item['end_reason'],
            actual_joint=item['actual_joint'], coverage=item['final_coverage'],
            per_head_nonforced=choice_counts.tolist(), corrected_joint_idle_opportunity_seconds=corrected_idle,
            original_raw_idle_opportunity_seconds=item['idle_opportunity_seconds'],
            last_pre_step_valid_counts=last['valid_counts'], last_pre_step_states=[r['state'] for r in last['robots']],
            last_pre_step_candidates=[{k: c[k] for k in ('robot', 'position', 'reachable', 'valid', 'traditional_eligible', 'local_map_valid')}
                                      for c in last['candidates']],
            diagnostic_actor_head_gradient=item['gradient_probe']['per_head_actor_weight_gradient'],
            actor_parameter_change=0., all_robot_participation=item['all_robot_participation']))
    if max_linear > config['backend']['max_linear_m_s']+1e-8 or max_angular > config['backend']['max_angular_rad_s']+1e-8:
        violations.append(['physical_velocity_bound'])
    if minimum_pair < config['backend']['min_pair_m']-1e-9 or max_path_error > 1e-8:
        violations.append(['physical_pair_or_path_integral'])
    mean = float(np.mean(all_costs))
    result = dict(status='P2 AUDIT PASS' if not violations else 'P2 AUDIT FAIL', violations=violations,
        actual_cases=len(cases), actual_joint=len(all_costs), counts=summary['counts'], cases=cases,
        outcomes=dict(Counter(c['end_reason'] for c in cases)),
        per_head_nonforced=per_head.tolist(), model_weights_unchanged=summary['model_weights_unchanged'],
        minimum_continuous_pair_m=minimum_pair, max_linear_m_s=max_linear, max_angular_rad_s=max_angular,
        max_trajectory_path_error_m=max_path_error, step_wall_mean_s=mean,
        step_wall_median_s=float(np.median(all_costs)), step_wall_max_s=max(all_costs),
        estimated_one_formal_run_hours_4096=4096*mean/3600,
        worst_case_registered_val_hours_12x100=1200*mean/3600,
        formal_resource_budget_revision_needed=(5296*mean > 21600),
        idle_correction='Use saved sampled conditional masks[:, :15].any(), not pre-reservation valid_counts; raw files retained',
        nn_forward_during_audit=0, env_step_during_audit=0, optimizer_during_audit=0,
        formal_joint=0, test_episodes=0, gazebo_formal_runs=0)
    dump(source/'analysis.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    analyse()

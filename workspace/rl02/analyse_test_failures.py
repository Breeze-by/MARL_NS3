"""Read-only TEST rejection and terminal-frontier analysis; no rollout."""
from collections import Counter
import json
import math
import numpy as np
from maps import PROJECT, dump
from multi_robot_exploration import frontier


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def terminal_frontiers(folder, observation):
    grid = np.load(folder/'observed-grids.npz')['cells'][-1]
    resolution = observation['map']['resolution']
    ox, oy = observation['map']['origin']
    result = []
    for robot in observation['robots']:
        start = (math.floor((robot['pose'][1]-oy)/resolution),
                 math.floor((robot['pose'][0]-ox)/resolution))
        data = frontier.costmap(grid, grid.shape[1], grid.shape[0], resolution)
        data[start] = 0
        data[data>5] = 1
        _, groups = frontier.assign_groups(frontier.frontierB(data))
        retained = frontier.fGroups(groups)
        candidates = []
        for candidate in observation['candidates']:
            if candidate['robot'] != robot['id']:
                continue
            cells = next(cells for group_id, cells in retained if group_id==candidate['group_id'])
            center = frontier.calculate_centroid([p[0] for p in cells], [p[1] for p in cells])
            distance = math.dist(start, center)
            reasons = []
            if distance>frontier.max_distance:
                reasons.append('centroid_beyond_original_150_cell_limit')
            if not candidate['local_map_valid']:
                reasons.append('not_free_in_this_received_local_map')
            target = candidate['position']
            if robot['last_success'] and math.dist(target, robot['last_success'])<.5:
                reasons.append('last_success_0.5m_veto')
            if any(h['status']=='succeeded' and math.dist(target, h['target'])<.2
                   for h in observation['history']):
                reasons.append('shared_visited_0.2m_veto')
            if any(h['robot']==robot['id'] and h['status'] in ('aborted', 'rejected', 'invalid_local_goal')
                   and math.dist(target, h['target'])<.2 for h in observation['history']):
                reasons.append('recorded_navigation_failure_0.2m_veto')
            if any(r['target'] is not None and math.dist(target, r['target'])<.2
                   for r in observation['robots']):
                reasons.append('active_target_0.2m_veto')
            candidates.append(dict(candidate=candidate, centroid_distance_cells=distance,
                                   observed_exclusions=reasons))
        result.append(dict(robot=robot['id'], state=robot['state'], candidates=candidates))
    return result


def run():
    root = PROJECT/'runs/test-01'
    cases, failures = [], []
    reason_counts = Counter()
    matched_local_invalid = 0
    rl_rejected = 0
    for folder in sorted(p.parent for p in root.glob('*/summary.json')):
        summary = json.loads((folder/'summary.json').read_text())
        intents, decisions = lines(folder/'intents.jsonl'), lines(folder/'decisions.jsonl')
        assert len(intents)==len(decisions)==summary['actual_joint']
        repeated, previous, streaks, max_streak = Counter(), {}, Counter(), {}
        for intent, decision in zip(intents, decisions):
            obs = intent['observation']
            for robot, reason in decision['rejected_actions'].items():
                reason_counts[reason] += 1
                rl_rejected += summary['policy']=='rl'
                index = ('tb1', 'tb2', 'tb3').index(robot)
                candidate = obs['candidates'][intent['action'][index]]
                signature = (robot, tuple(candidate['position']))
                repeated[signature] += 1
                streaks[robot] = streaks[robot]+1 if previous.get(robot)==signature else 1
                previous[robot] = signature
                max_streak[signature] = max(max_streak.get(signature, 0), streaks[robot])
                matched_local_invalid += (candidate['robot']==robot and candidate['traditional_eligible']
                                          and candidate['local_map_valid'] is False)
            for robot in ('tb1', 'tb2', 'tb3'):
                if robot not in decision['rejected_actions']:
                    previous.pop(robot, None)
                    streaks[robot] = 0
        cases.append(dict(case=folder.name, policy=summary['policy'],
            outcome=summary['end_reason'], rejected_robot_actions=summary['rejected_robot_actions'],
            repeated_targets=[dict(robot=key[0], position=key[1], count=count,
                longest_consecutive_rejection_decisions=max_streak[key])
                for key, count in repeated.most_common()]))
        if not summary['natural_complete']:
            last = json.loads((folder/'last-observed.json').read_text())
            failures.append(dict(case=folder.name, outcome=summary['end_reason'],
                coverage=summary['coverage'], valid_counts=last['valid_counts'],
                robot_states=[r['state'] for r in last['robots']],
                navigation_aborts=summary['abort_causes_derived'], safe_blocks=summary['safe_blocks'],
                terminal_frontiers=terminal_frontiers(folder, last)))
    result = dict(status='STATIC HISTORICAL ANALYSIS; COMPARATOR CONTRACT FAIL',
        episode_count=len(cases), noncompletion_cases=len(failures),
        rejection_reasons=dict(reason_counts), rl_rejected_robot_actions=rl_rejected,
        rejected_original_eligible_owned_locally_invalid_candidates=matched_local_invalid,
        cases=cases, failures=failures, frontier_recomputations=3*len(failures),
        nn_forward=0, env_reset=0, env_step=0, optimizer_step=0, new_policy_rollouts=0,
        caveat='JSON stores logical bool values, not original NumPy scalar identity. Type/side-effect defect is independently proven in boolean-contract-01. Repeated saved rejection does not quantify corrected counterfactual outcomes.')
    dump(PROJECT/'evidence/test-failure-analysis.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases', 'failures')}, indent=2))


if __name__=='__main__':
    run()

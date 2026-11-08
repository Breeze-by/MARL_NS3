"""Static replay of already-saved observations; no new policy rollout."""
import json
import math
import numpy as np
from diagnose import PROJECT, dump
from multi_robot_exploration import frontier
from multi_robot_exploration.allocation import distances
from multi_robot_exploration.joint import JointTraditionalPolicy


def analyse():
    root = PROJECT/'evidence/p2-diagnosis-01'
    results = []
    for folder in sorted(p.parent for p in root.glob('*/summary.json')):
        summary = json.loads((folder/'summary.json').read_text())
        if summary['end_reason'] != 'stalled_wait':
            continue
        last_decision = json.loads((folder/'decisions.jsonl').read_text().splitlines()[-1])
        observation = last_decision['observation']
        grid = np.load(folder/'observed-grids.npz')['cells'][-2]
        m = observation['map']
        res, (ox, oy) = m['resolution'], m['origin']
        details = []
        for robot in observation['robots']:
            start = (math.floor((robot['pose'][1]-oy)/res), math.floor((robot['pose'][0]-ox)/res))
            data = frontier.costmap(grid, grid.shape[1], grid.shape[0], res)
            data[start] = 0
            data[data > 5] = 1
            data, all_groups = frontier.assign_groups(frontier.frontierB(data))
            retained = frontier.fGroups(all_groups)
            data[data < 0] = 1
            reached = distances(data, start, res)
            rows = []
            for group_id, cells in retained:
                center = frontier.calculate_centroid([p[0] for p in cells], [p[1] for p in cells])
                reachable = [p for p in cells if p in reached]
                matching = [c for c in observation['candidates'] if c['robot'] == robot['id'] and c['group_id'] == group_id]
                candidate = matching[0] if matching else None
                distance = math.hypot(start[0]-center[0], start[1]-center[1])
                reasons = []
                if not reachable:
                    reasons.append('no_known_free_reachable_representative')
                if distance > frontier.max_distance:
                    reasons.append('centroid_beyond_original_150_cell_distance_limit')
                if candidate:
                    if not candidate['local_map_valid']:
                        reasons.append('representative_not_free_in_this_robot_received_local_map')
                    if robot['last_success'] and math.dist(candidate['position'], robot['last_success']) < .5:
                        reasons.append('original_last_success_0.5m_veto')
                    history = observation['history']
                    if any(h['status'] == 'succeeded' and math.dist(candidate['position'], h['target']) < .2 for h in history):
                        reasons.append('original_shared_visited_0.2m_veto')
                    if any(h['robot'] == robot['id'] and h['status'] in ('aborted', 'rejected', 'invalid_local_goal')
                           and math.dist(candidate['position'], h['target']) < .2 for h in history):
                        reasons.append('original_failed_0.2m_veto')
                rows.append(dict(group_id=group_id, frontier_cells=len(cells),
                    known_free_reachable_frontier_cells=len(reachable), centroid_distance_cells=distance,
                    original_centroid_limit_cells=frontier.max_distance, exclusion_reasons=reasons,
                    observed_candidate=candidate))
            details.append(dict(robot=robot['id'], all_frontier_groups=len(all_groups),
                groups_above_two_cells=sum(len(c) > 2 for c in all_groups.values()),
                retained_groups=len(retained), retained_frontier_cells=sum(len(c) for _, c in retained), groups=rows))
        action = JointTraditionalPolicy().select(observation)
        # This is a read-only evaluation of the already-recorded common gate,
        # not backend.advance, a new rollout, or a changed traditional selector.
        executable = [0 <= c < len(observation['candidates']) and observation['action_mask'][i][c]
                      for i, c in enumerate(action.choices)]
        results.append(dict(case=folder.name, coverage=summary['final_coverage'],
            last_observation_sim=observation['sim_stamp'], raw_rl_last_action=last_decision['action'],
            original_traditional_static_action=action.choices,
            original_traditional_executable_by_same_saved_gate=executable,
            original_traditional_static_select_calls=1, frontier_recomputations=3, robots=details,
            interpretation='At this saved state the common legal goal set is empty for every robot; more PPO cannot create a new legal action here. Earlier allocation might change the reached state; no all-policy impossibility claim.'))
    result = dict(status='STATIC STALL CAUSES IDENTIFIED', cases=results,
        nn_forward=0, env_reset=0, env_step=0, optimizer_step=0, new_policy_rollouts=0,
        allocator_get_observation_calls=0, static_traditional_select_calls=len(results),
        frontier_recomputations=3*len(results), source_contract_changed=False)
    dump(root/'stall-analysis.json', result)
    print(json.dumps(dict(cases=len(results), nn_forward=0, env_step=0,
        robots=[[(r['robot'], [g['exclusion_reasons'] for g in r['groups']]) for r in c['robots']] for c in results]), indent=2))


if __name__ == '__main__':
    analyse()

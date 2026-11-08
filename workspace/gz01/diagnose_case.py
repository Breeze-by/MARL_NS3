"""Replay received Frontier geometry and task snapshots; no model/ROS Node."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from multi_robot_exploration import frontier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--metric', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    metric = json.loads(args.metric.read_text())
    start, end = metric['start_sim'], metric['end_sim']
    events = [json.loads(line) for line in
              (args.case/'controller/allocation-events.jsonl').read_text().splitlines()]
    decisions = []
    for event in events:
        if event['kind'] not in ('rl_real_inference', 'traditional_real_decision'):
            continue
        if not start <= event['sim'] <= end:
            continue
        obs = event['observed_state_and_candidates']
        with np.load(args.case/'controller/policy-trace'/
                     f"{event['sequence']:04d}.npz", allow_pickle=False) as data:
            cells = data['received_shared_cells']
        m = obs['map']
        raw = {}
        for robot in obs['robots']:
            resolution = m['resolution']
            ox, oy = m['origin']
            height, width = cells.shape
            col = math.floor((robot['pose'][0]-ox)/resolution)
            row = math.floor((robot['pose'][1]-oy)/resolution)
            grid = frontier.costmap(cells, width, height, resolution)
            grid[row, col] = 0
            grid[grid > 5] = 1
            _, groups = frontier.assign_groups(frontier.frontierB(grid))
            raw[robot['id']] = dict(cells=sum(map(len, groups.values())),
                                    groups=len(groups),
                                    groups_at_least_three=sum(len(g)>2 for g in groups.values()))
        decisions.append(dict(sim=event['sim'], elapsed=event['sim']-start,
            choices=event['choices'], valid_counts=obs['valid_counts'],
            states={r['id']:r['state'] for r in obs['robots']},
            owners={r['id']:r['action_uuid'] for r in obs['robots']},
            raw_frontier=raw, candidate_count=len(obs['candidates']),
            policy_wall_s=event['policy_wall_s']))
    categories = dict(idle_with_candidates=0., idle_without_candidates=0.,
                      active_with_no_idle_candidates=0., all_WAIT=0.,
                      no_raw_frontier=0.)
    for i, row in enumerate(decisions):
        following = decisions[i+1]['sim'] if i+1 < len(decisions) else end
        dt = following-row['sim']
        if all(state == 'idle' for state in row['states'].values()):
            key = 'idle_with_candidates' if any(row['valid_counts']) else 'idle_without_candidates'
            categories[key] += dt
        elif not any(row['valid_counts']):
            categories['active_with_no_idle_candidates'] += dt
        if row['choices'] == [-2, -2, -2]:
            categories['all_WAIT'] += dt
        if all(raw['cells'] == 0 for raw in row['raw_frontier'].values()):
            categories['no_raw_frontier'] += dt
    result = dict(scope='Actual received policy ROI, fixed snapshot replay; no truth/model input',
        case=str(args.case), start_sim=start, end_sim=end,
        first_decision_sim=decisions[0]['sim'] if decisions else None,
        pre_first_decision_s=decisions[0]['sim']-start if decisions else end-start,
        decision_count=len(decisions), sample_held_category_seconds=categories,
        category_limit='Snapshot-held states; active-owned no translation is separately measured from physical trajectories in the metric result.',
        snapshots=decisions, calls=dict(Node=0, NN=0, environment_step=0, optimizer=0, Gazebo=0, Action=0))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    with (args.output/'decisions.csv').open('x') as stream:
        writer = csv.writer(stream)
        writer.writerow(['sim','elapsed','choices','valid_counts','states','owners','raw_cells_tb1_tb2_tb3'])
        for row in decisions:
            writer.writerow([row['sim'],row['elapsed'],row['choices'],row['valid_counts'],
                             row['states'],row['owners'],[v['cells'] for v in row['raw_frontier'].values()]])
    print(json.dumps({k:v for k,v in result.items() if k!='snapshots'}, indent=2))


if __name__ == '__main__':
    main()

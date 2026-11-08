"""Offline accounting only: consumes saved results, never calls policy/environment."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import numpy as np
import torch

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.joint import slot_mask


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def ledger_totals(path):
    result = Counter()
    for row in rows(path):
        result.update(row['delta'])
    return dict(result)


def navigation(events):
    return dict(accepted=sum(e['kind'] == 'accepted' for e in events),
                terminal_statuses=dict(Counter(e['status'] for e in events if e['kind'] == 'terminal')),
                succeeded_arrival_errors=[dict(xy_m=e['xy_error_m'], yaw_rad=e['yaw_error_rad'])
                    for e in events if e['kind'] == 'terminal' and e['status'] == 'succeeded'])


def path_revisits(trace):
    """Observed .05m robot-centre cell entries; a traversal proxy, not LiDAR area."""
    visited = {robot: set() for robot in ('tb1', 'tb2', 'tb3')}
    previous, entries, own, cross = {}, 0, 0, 0
    for sample in trace:
        for robot, pose in sample['poses'].items():
            cell = tuple(np.floor(np.array(pose[:2])/.05).astype(int))
            if previous.get(robot) == cell:
                continue
            previous[robot] = cell
            entries += 1
            own += cell in visited[robot]
            cross += any(cell in seen for name, seen in visited.items() if name != robot)
            visited[robot].add(cell)
    return dict(cell_size_m=.05, cell_entries=entries, own_revisit_entries=int(own),
                cross_robot_revisit_entries=int(cross),
                own_revisit_fraction=own/max(1, entries), cross_revisit_fraction=cross/max(1, entries),
                meaning='Robot-centre traversal proxy; no claim of repeated sensed-area measurement')


def training_summary(case, initial):
    decisions, completed = rows(case/'decisions.jsonl'), rows(case/'episodes.jsonl')
    by_episode = defaultdict(list)
    for decision in decisions:
        by_episode[decision['episode']].append(decision)
    terminal = {episode['episode']: episode for episode in completed}
    episode_rows, cancellations = [], 0
    for episode, steps in sorted(by_episode.items()):
        full = episode in terminal
        events_path = case/f'episode-{episode:04d}-navigation.json' if full else case/'last-navigation.json'
        events = json.loads(events_path.read_text())
        statuses = navigation(events)
        cancellations += statuses['terminal_statuses'].get('canceled', 0)
        episode_rows.append(dict(episode=episode, joint_decisions=len(steps), complete_record=full,
                                 task_terminated=steps[-1]['terminated'], task_truncated=steps[-1]['truncated'],
                                 reason=steps[-1]['reason'] if full else 'formal_global_budget_partial_episode',
                                 coverage=steps[-1]['coverage'], sim_seconds=steps[-1]['sim'],
                                 paths_m=steps[-1]['paths_m'], navigation=statuses,
                                 reward=sum(s['reward'] for s in steps)))
    first = torch.load(initial, map_location='cpu', weights_only=False)
    final = torch.load(case/'final.pt', map_location='cpu', weights_only=False)
    actor_weight = (final['model']['actor.weight']-first['model']['actor.weight']).reshape(3, 17, -1)
    actor_bias = (final['model']['actor.bias']-first['model']['actor.bias']).reshape(3, 17)
    gradients = rows(case/'updates.jsonl')
    return dict(summary=json.loads((case/'summary.json').read_text()),
                unique_joint_decisions=len(decisions),
                per_robot_goal_choices=dict(Counter(str(s['choices']) for s in decisions if s['choice_rows'])),
                nonforced_decisions=sum(s['choice_rows'] > 0 for s in decisions),
                per_head_nonforced_training_counts=None,
                unavailable_reason='Frozen driver recorded total choice_rows, not per-head masks; no extra env replay invented',
                actor_head_weight_changes={f'tb{i+1}':float(actor_weight[i].norm()) for i in range(3)},
                actor_head_bias_changes={f'tb{i+1}':float(actor_bias[i].norm()) for i in range(3)},
                critic_weight_change=float((final['model']['critic.weight']-first['model']['critic.weight']).norm()),
                finite_final_parameters=all(torch.isfinite(value).all().item() for value in final['model'].values()),
                optimizer_steps=len(gradients), episodes=episode_rows,
                end_cancellations=cancellations, policy_cancellations=0,
                policy_cancellation_reason='No CANCEL/preempt action exists; all canceled receipts belong to episode/global cleanup',
                actual_ledger=ledger_totals(case/'ledger.jsonl'),
                resource_log=str(case.parent/'resources.txt'),
                checkpoint_metadata=final['metadata'])


def evaluation_summary(case):
    import pickle
    results = json.loads((case/'results.json').read_text())
    replay = json.loads((case/'behavior-replay.json').read_text())
    with (case/'initial-observed-states.pkl').open('rb') as stream:
        states = pickle.load(stream)  # Own locally produced observed-state artifact only.
    per_head = {name: dict(nonforced_initial=0, nonforced_trained=0, changed_nonforced=0)
                for name in ('tb1', 'tb2', 'tb3')}
    for observation, record in zip(states, replay):
        for i, name in enumerate(per_head):
            initial = slot_mask(observation, i, record['initial'][:i]).sum() > 1
            trained = slot_mask(observation, i, record['trained'][:i]).sum() > 1
            per_head[name]['nonforced_initial'] += int(initial)
            per_head[name]['nonforced_trained'] += int(trained)
            per_head[name]['changed_nonforced'] += int((initial or trained) and record['initial'][i] != record['trained'][i])
    table = []
    for row in results:
        events = json.loads((case/(row['case']+'-navigation.json')).read_text())
        nav = navigation(events)
        decisions = rows(case/(row['case']+'-decisions.jsonl'))
        rejections = Counter(reason for decision in decisions for reason in decision['rejections'].values())
        trace = json.loads((case/(row['case']+'-trajectory.json')).read_text())
        table.append(dict(case=row['case'], map=row['map'], seed=row['seed'], policy=row['policy'],
                          decisions=row['decisions'], coverage=row['coverage'], terminated=row['reason'] == 'natural_complete',
                          reason=row['reason'], time_90=row['coverage_times'].get('0.9'),
                          time_95=row['coverage_times'].get('0.95'), paths_m=row['paths_m'],
                          total_path_m=sum(row['paths_m'].values()), participating_robots=[r for r,d in row['paths_m'].items() if d > .1],
                          conflicts=row['metrics']['target_conflicts'], duplicate_assignments=row['metrics']['duplicate_assignments'],
                          action_rejections=dict(rejections), target_switches=row['metrics']['target_switches'],
                          no_new_goal_decisions=sum(all(choice < 0 for choice in decision['choices']) for decision in decisions),
                          keep_components=sum(decision['choices'].count(-1) for decision in decisions),
                          wait_components=sum(decision['choices'].count(-2) for decision in decisions),
                          traversal_revisits=path_revisits(trace), repeated_sensor_area_m2=None,
                          repeated_sensor_area_reason='Per-step sensor-duplicate reward terms were not retained by frozen driver; not fabricated from last-step info',
                          end_cancellations=nav['terminal_statuses'].get('canceled', 0), policy_cancellations=0,
                          navigation=nav, minimum_pair_m=row['minimum_pair_m'], stop_verified=row['stop_verified'],
                          infer_mean_seconds=row['inference_mean_seconds'], reward=row['reward_total']))
    return dict(table=table, per_head_replay_opportunities=per_head,
                replay_states=len(states), changed_states=sum(r['changed'] for r in replay),
                actual_ledger=ledger_totals(case/'ledger.jsonl'),
                warning='12 fixed development episodes; no statistical significance or scientific PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('training', 'evaluation'))
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--initial', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = training_summary(args.case, args.initial) if args.mode == 'training' else evaluation_summary(args.case)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')

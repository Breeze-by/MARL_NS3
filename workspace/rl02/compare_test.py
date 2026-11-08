"""Failure-aware paired, map-clustered descriptive TEST comparison, no rollout."""
from collections import defaultdict, Counter
import json
import numpy as np
from maps import HERE, PROJECT, dump


def metrics(row):
    succeeded = row['navigation_terminals'].get('succeeded', 0)
    aborted = row['navigation_terminals'].get('aborted', 0)
    accepted = sum(row['accepted'].values())
    result = dict(complete=float(row['natural_complete']), coverage=row['coverage'],
        reached_T90=float('0.9' in row['coverage_times']), reached_T95=float('0.95' in row['coverage_times']),
        penalty_T95=row['coverage_times'].get('0.95', 500.),
        actual_T90=row['coverage_times'].get('0.9'), actual_T95=row['coverage_times'].get('0.95'),
        total_path=sum(row['paths_m'].values()), maximum_robot_path=row['maximum_robot_path_m'],
        all_robot_participation=float(row['all_robot_participation']),
        reserved_goal_count=sum(row['metrics']['assignments'].values()), accepted_goal_count=accepted,
        target_conflict_count=row['metrics']['target_conflicts'], target_switch_count=row['metrics']['target_switches'],
        evaluator_canceled_terminal_count=row['metrics']['cancellations'],
        navigation_canceled_including_cleanup=row['navigation_terminals'].get('canceled', 0),
        navigation_succeeded=succeeded, navigation_aborted=aborted,
        navigation_failure_rate_terminal=None if succeeded+aborted == 0 else aborted/(succeeded+aborted),
        navigation_aborted_per_accepted=None if accepted == 0 else aborted/accepted,
        rejected_robot_actions=row['rejected_robot_actions'],
        rejected_robot_action_rate=None if row['actual_joint'] == 0 else row['rejected_robot_actions']/(3*row['actual_joint']),
        candidate_goal_attempts=row['candidate_goal_attempts'],
        rejected_candidate_goal_attempts=row['rejected_candidate_goal_attempts'],
        rejected_candidate_proposal_rate=None if row['candidate_goal_attempts'] == 0 else row['rejected_candidate_goal_attempts']/row['candidate_goal_attempts'],
        accepted_backend_goal_gate_violation_count=row['accepted_backend_goal_gate_violation_count'],
        duplicate_assignment_count=row['metrics']['duplicate_assignments'],
        minimum_pair_m=row['minimum_pair_m'], safe_motion_blocks=row['safe_blocks'],
        duplicate_new_observed_area_proxy=row['reward_terms'].get('duplicate_new_m2', 0.),
        conditional_idle_seconds=sum(row['conditional_idle_opportunity_seconds'].values()),
        keep_count=row['keep_count'], wait_count=row['wait_count'],
        policy_decision_wall_mean_s=row['inference_wall_total_s']/row['intent_count'] if row['intent_count'] else None,
        actual_joint=row['actual_joint'])
    for robot in ('tb1', 'tb2', 'tb3'):
        result[robot+'_path_m'] = row['paths_m'][robot]
        result[robot+'_reserved_goals'] = row['metrics']['assignments'][robot]
        result[robot+'_accepted_goals'] = row['accepted'].get(robot, 0)
        result[robot+'_net_displacement_m'] = row['net_displacement_m'][robot]
        result[robot+'_idle_opportunity_seconds'] = row['conditional_idle_opportunity_seconds'][robot]
    return result


def descriptive(values):
    available = [v for v in values if v is not None]
    return dict(mean=None if not available else float(np.mean(available)),
        median=None if not available else float(np.median(available)),
        available_count=len(available), missing_count=len(values)-len(available), total_count=len(values))


def compare():
    root = PROJECT/'runs/test-01'
    summaries = []
    for path in sorted(root.glob('*/summary.json')):
        row = json.loads(path.read_text())
        intents = [json.loads(s) for s in (path.parent/'intents.jsonl').read_text().splitlines()]
        row['inference_wall_total_s'] = sum(r['inference_wall_s'] for r in intents)
        row['intent_count'] = len(intents)
        decisions = [json.loads(s) for s in (path.parent/'decisions.jsonl').read_text().splitlines()]
        row['candidate_goal_attempts'] = sum(c >= 0 for r in intents for c in r['action'])
        row['rejected_candidate_goal_attempts'] = sum(
            robot in r['rejected_actions'] and r['choices'][index] >= 0
            for r in decisions for index, robot in enumerate(('tb1', 'tb2', 'tb3')))
        row['rejection_reasons'] = dict(Counter(reason for r in decisions for reason in r['rejected_actions'].values()))
        gate_violations = 0
        for decision, intent in zip(decisions, intents):
            for event in decision['actual_events']:
                if event['kind'] != 'accepted':
                    continue
                index = ('tb1', 'tb2', 'tb3').index(event['robot'])
                choice = intent['action'][index]
                candidates = intent['observation']['candidates']
                if not (0 <= choice < len(candidates)):
                    gate_violations += 1
                    continue
                candidate = candidates[choice]
                legal = (intent['masks'][index][choice] and candidate['valid']
                    and candidate['robot'] == event['robot'] and candidate['local_map_valid']
                    and np.allclose(candidate['position'], event['target'], atol=1e-10))
                gate_violations += not legal
        row['accepted_backend_goal_gate_violation_count'] = int(gate_violations)
        row['keep_count'] = sum(r['action'].count(-1) for r in intents)
        row['wait_count'] = sum(r['action'].count(-2) for r in intents)
        summaries.append(row)
    if len(summaries) != 36:
        raise ValueError('Incomplete TEST; report missing cases rather than silently dropping failures')
    config = json.loads((HERE/'config.json').read_text())
    paired = defaultdict(dict)
    for row in summaries:
        key = (row['map'], row['seed'])
        if row['policy'] in paired[key]:
            raise ValueError('Duplicate TEST policy case')
        paired[key][row['policy']] = row
    rows = []
    both_success = []
    for (name, seed), pair in sorted(paired.items()):
        if set(pair) != {'rl', 'traditional'}:
            raise ValueError('Missing paired policy')
        rl, traditional = pair['rl'], pair['traditional']
        pair_metrics = {}
        for kind, value in pair.items():
            pair_metrics[kind] = metrics(value)
        differences = {k: None if pair_metrics['rl'][k] is None or pair_metrics['traditional'][k] is None else
                       pair_metrics['rl'][k]-pair_metrics['traditional'][k] for k in pair_metrics['rl']}
        if all(pair_metrics[k]['actual_T95'] is not None for k in pair_metrics):
            both_success.append(pair_metrics['rl']['actual_T95']-pair_metrics['traditional']['actual_T95'])
        rows.append(dict(map=name, family=rl['family'], seed=seed, policies=pair_metrics,
            rejection_reasons={k: v['rejection_reasons'] for k, v in pair.items()},
            end_reasons={k: v['end_reason'] for k, v in pair.items()},
            raw_terminated={k: v['raw_terminated'] for k, v in pair.items()},
            raw_truncated={k: v['raw_truncated'] for k, v in pair.items()}, rl_minus_traditional=differences))
    primary = ('complete', 'reached_T90', 'reached_T95', 'coverage', 'penalty_T95', 'total_path',
               'maximum_robot_path', 'all_robot_participation', 'duplicate_new_observed_area_proxy',
               'target_conflict_count', 'target_switch_count', 'navigation_canceled_including_cleanup',
               'conditional_idle_seconds')
    map_means = []
    for name in sorted({r['map'] for r in rows}):
        group = [r for r in rows if r['map'] == name]
        map_means.append(dict(map=name, family=group[0]['family'],
            **{k: float(np.mean([r['rl_minus_traditional'][k] for r in group])) for k in primary}))
    families = sorted({r['family'] for r in map_means})
    rng = np.random.default_rng(config['bootstrap_seed'])
    boot = defaultdict(list)
    for _ in range(config['bootstrap_replicates']):
        sample = []
        for family in families:
            group = [r for r in map_means if r['family'] == family]
            sample.extend(group[i] for i in rng.integers(0, len(group), len(group)))
        for key in primary:
            boot[key].append(float(np.mean([r[key] for r in sample])))
    intervals = {k: dict(mean_rl_minus_traditional=float(np.mean([r[k] for r in map_means])),
        paired_case_median=float(np.median([r['rl_minus_traditional'][k] for r in rows])),
        map_clustered_family_stratified_percentile95=np.quantile(v, [.025, .975]).tolist()) for k, v in boot.items()}
    descriptive_all_metrics = {key: dict(
        rl=descriptive([r['policies']['rl'][key] for r in rows]),
        traditional=descriptive([r['policies']['traditional'][key] for r in rows]),
        paired_difference=descriptive([r['rl_minus_traditional'][key] for r in rows]))
        for key in rows[0]['rl_minus_traditional']}
    descriptive_by_map = {}
    for name in sorted({r['map'] for r in rows}):
        group = [r for r in rows if r['map'] == name]
        descriptive_by_map[name] = {key: dict(
            rl=descriptive([r['policies']['rl'][key] for r in group]),
            traditional=descriptive([r['policies']['traditional'][key] for r in group]),
            paired_difference=descriptive([r['rl_minus_traditional'][key] for r in group]))
            for key in rows[0]['rl_minus_traditional']}
    counts = {}
    for kind in ('rl', 'traditional'):
        group = [r for r in summaries if r['policy'] == kind]
        counts[kind] = dict(episodes=len(group), natural_complete=sum(r['natural_complete'] for r in group),
            all_robot_participation=sum(r['all_robot_participation'] for r in group),
            mean_coverage=float(np.mean([r['coverage'] for r in group])),
            mean_penalty_T95=float(np.mean([r['coverage_times'].get('0.95', 500.) for r in group])),
            success_conditional_T95=[r['coverage_times']['0.95'] for r in group if '0.95' in r['coverage_times']],
            T95_not_reached=sum('0.95' not in r['coverage_times'] for r in group),
            T90_not_reached=sum('0.9' not in r['coverage_times'] for r in group),
            success_conditional_T90=[r['coverage_times']['0.9'] for r in group if '0.9' in r['coverage_times']],
            rejected_robot_actions=sum(r['rejected_robot_actions'] for r in group),
            minimum_pair_m=min(r['minimum_pair_m'] for r in group),
            mean_paths_per_robot_m={robot: float(np.mean([r['paths_m'][robot] for r in group])) for robot in ('tb1', 'tb2', 'tb3')},
            maximum_individual_robot_path_m=max(r['maximum_robot_path_m'] for r in group),
            sum_duplicate_new_observed_area_proxy_m2=sum(r['reward_terms'].get('duplicate_new_m2', 0.) for r in group),
            sum_safe_motion_blocks=sum(r['safe_blocks'] for r in group),
            navigation_succeeded=sum(r['navigation_terminals'].get('succeeded', 0) for r in group),
            navigation_aborted=sum(r['navigation_terminals'].get('aborted', 0) for r in group),
            navigation_canceled_including_cleanup=sum(r['navigation_terminals'].get('canceled', 0) for r in group),
            derived_abort_causes=[a for r in group for a in r['abort_causes_derived']],
            target_conflicts=sum(r['metrics']['target_conflicts'] for r in group),
            target_switches=sum(r['metrics']['target_switches'] for r in group),
            keep_count=sum(r['keep_count'] for r in group), wait_count=sum(r['wait_count'] for r in group),
            conditional_idle_opportunity_seconds={robot: sum(r['conditional_idle_opportunity_seconds'][robot] for r in group)
                for robot in ('tb1', 'tb2', 'tb3')},
            inference_wall_total_s=sum(r['inference_wall_total_s'] for r in group),
            actual_joint=sum(r['actual_joint'] for r in group))
    result = dict(status='DESCRIPTIVE PAIRED TEST ANALYSIS', pairs=rows, maps=map_means,
        counts=counts, intervals=intervals, descriptive_all_metrics=descriptive_all_metrics,
        policy_gate_validity=('PASS_ON_SAVED_PROXY_ACCEPTANCES' if not any(
            r['accepted_backend_goal_gate_violation_count'] for r in summaries) else 'FAIL'),
        descriptive_by_map=descriptive_by_map,
        outcome_counts={kind: {reason: sum(r['policy'] == kind and r['end_reason'] == reason for r in summaries)
                              for reason in sorted({r['end_reason'] for r in summaries})} for kind in ('rl', 'traditional')},
        both_success_T95_difference_count=len(both_success),
        both_success_T95_rl_minus_traditional=both_success,
        bootstrap_seed=config['bootstrap_seed'], bootstrap_replicates=config['bootstrap_replicates'],
        test_map_instances=6, map_cluster_units=6, generated_test_families=2,
        map_instances_within_family_are_related=True,
        metric_semantics={'rejected_candidate_proposal_rate':'Rejected by the common gate before backend dispatch; legacy traditional local-check rejection is expected and is not an unsafe goal entering Nav2.',
            'accepted_backend_goal_gate_violation_count':'Derived from actual proxy acceptance events against saved owner/candidate/conditional mask/local-valid/target; not a real Nav2 execution certificate.',
            'evaluator_canceled_terminal_count':'Evaluator counts canceled terminal events, not cancellation requests; cleanup-inclusive backend terminals are separately reported.',
            'target_switch_count':'Active-task preemption is prohibited by the fixed contract; zero is a constraint, not proof that PPO learned switching avoidance.',
            'duplicate_assignment_count':'The fixed common gate/visited rules constrain repetition; zero alone does not establish learned collaboration.'},
        caveat='Small dependent generated corpus; intervals describe these two families and do not establish external geographic generalization or strong statistical superiority.',
        penalty_T95_is_labeled_500sim_for_nonreach_not_an_actual_completion_time=True,
        nn_forward=0, env_step=0, optimizer_step=0, formally_frozen=False)
    dump(root/'comparison.json', result)
    print(json.dumps(dict(counts=counts, intervals=intervals), indent=2))


if __name__ == '__main__':
    compare()

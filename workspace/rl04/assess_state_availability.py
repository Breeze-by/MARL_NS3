"""Read actual supervisor/controller events; never start ROS or infer a policy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def assess(supervisor, controller, ledger):
    startup, = [e for e in supervisor if e['kind'] == 'exploration_command']
    calls = [e for e in controller if e['kind'] == 'rl04_allocation_wall']
    inferences = [e for e in controller if e['kind'] == 'rl_real_inference']
    counts = Counter()
    for row in ledger:
        counts.update(row['delta'])
    total_attempts = counts['ros_joint_decision_attempt']
    by_attempt = {e['allocation_attempt']: e for e in calls}
    unrecorded = sorted(set(range(1, total_attempts+1))-set(by_attempt))
    first = next((e for e in calls if e['state'] == 'applied'), None)
    steady = [] if first is None else [by_attempt.get(i) for i in range(first['allocation_attempt'], total_attempts+1)]
    valid, streak, maximum_streak = [], 0, 0
    for event in steady:
        fresh = (event is not None and event['state'] == 'applied' and not event['missing_map_at_start'] and
                 set(event['pose_ages_at_start_s']) == {'tb1', 'tb2', 'tb3'} and
                 all(age is not None and age <= 2. for age in event['pose_ages_at_start_s'].values()))
        valid.append(fresh)
        streak = 0 if fresh else streak+1
        maximum_streak = max(maximum_streak, streak)
    first_start_delay = None if not inferences else inferences[0]['inference_start_sim']-startup['sim']
    # The existing event is stamped after forward and inference-NPZ IO. Use
    # that conservative completion marker, never the earlier forward start.
    first_delay = None if not inferences else inferences[0]['sim']-startup['sim']
    fraction = sum(valid)/len(valid) if valid else None
    startup_pass = first_delay is not None and 0 <= first_delay <= 15.
    steady_pass = fraction is not None and fraction >= .9 and maximum_streak <= 1
    applied = [e for e in calls if e['state'] == 'applied']
    matched = (len(applied) == len(inferences) > 0 and
               0 <= counts['policy_forward']-len(inferences) <= len(unrecorded))
    return dict(status='P2 STATE PASS' if startup_pass and steady_pass and matched else 'P2 STATE FAIL',
        controller_start_sim=startup['sim'], first_inference_completion_delay_sim_s=first_delay,
        first_inference_start_delay_sim_s=first_start_delay,
        completion_marker='first rl_real_inference.sim, after forward and saved inference-NPZ IO',
        startup_within15sim=startup_pass, allocation_attempts=total_attempts,
        recorded_allocation_returns=len(calls), actual_forward_calls=counts['policy_forward'],
        completed_inference_records=len(inferences), unrecorded_attempt_ids=unrecorded,
        steady_attempts=len(steady), steady_fresh_attempts=sum(valid), steady_fresh_fraction=fraction,
        maximum_consecutive_steady_incomplete_or_waits=maximum_streak,
        all_recorded_applied_and_forward_counts_accounted=matched,
        applied_allocation_wall_mean_s=statistics.mean(e['allocation_wall_s'] for e in applied) if applied else None,
        NN_wall_mean_s=statistics.mean(e['inference_wall_s'] for e in inferences) if inferences else None,
        wall_latency_complete_sample_count=len(inferences),
        attempts=[{k:e[k] for k in ('allocation_attempt', 'allocation_start_sim', 'state',
            'pose_ages_at_start_s', 'missing_map_at_start', 'pose_tf_errors')} for e in calls],
        scope='closed ledger denominator; first applied inclusive; unrecorded attempts conservatively nonfresh/incomplete; fixed2s original stamps',
        policy_forward=0, env_step=0, optimizer_update=0)


def run(directory):
    read = lambda path: [json.loads(s) for s in path.read_text().splitlines()]
    result = assess(read(directory/'events.jsonl'), read(directory/'controller/allocation-events.jsonl'),
                    read(directory/'controller/ledger.jsonl'))
    with (directory/'state-availability-all-attempts.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'attempts'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)

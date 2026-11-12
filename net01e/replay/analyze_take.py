"""Once-only saved RMW timestamp analysis of new bounded collection results."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def stats(values):
    values = sorted(values)
    if not values:
        return dict(n=0)
    return dict(n=len(values), min=values[0], median=values[(len(values)-1)//2],
                p95=values[math.ceil(.95*len(values))-1], max=values[-1])


def tfkey(edges, stamp_key):
    return tuple((edge['frame_id'], edge['child_frame_id'], edge[stamp_key]) for edge in edges)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--pre-fault-summary', action='store_true',
                        help='Read saved pair analysis only; preserve original all-window result')
    args = parser.parse_args()
    if args.pre_fault_summary:
        saved = json.loads((args.case/'take-analysis.json').read_text())
        cutoff = min(int(row['monotonic']*1e9) for row in saved['first_fault'].values() if row is not None)
        groups = defaultdict(lambda: defaultdict(list)); counts = Counter(); post = Counter()
        for pair in saved['pairs']:
            if pair['take_before_monotonic_ns'] >= cutoff:
                post[pair['flow']] += 1; continue
            counts[pair['flow']] += 1
            for name, value in pair['metrics'].items():
                groups[pair['flow']][name].append(value)
        result = dict(scope='Strict take-before first actual fault monotonic cutoff; saved original pairs only',
            first_fault_monotonic_ns=cutoff, all_window_pairs=len(saved['pairs']),
            pre_fault_counts=dict(counts), at_or_after_fault_counts=dict(post),
            groups={str(flow): {name: stats(values) for name, values in group.items()} for flow, group in groups.items()},
            inherited_boundaries=saved['boundaries'])
        (args.case/'take-pre-fault-summary.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
        return
    gateway = json.loads((args.case/'gateway/network-gateway.json').read_text())
    source = json.loads((args.case/'source/result.json').read_text())['inputs']
    peer = [json.loads(line) for line in (args.case/'peer/peer-keepout.jsonl').read_text().splitlines()]
    sources = defaultdict(list)
    for row in source:
        if row['state'] == 'PUBLISHED' and row['flow'] % 20 == 3:
            sources[(row['flow'], tfkey(row['original_tf_edges'], 'source_stamp_ns'))].append(row)
    takes = [row for row in gateway['health_trace']['rows'] if row['stage'] == 'R_TF_take']
    counts = Counter(); metrics = defaultdict(lambda: defaultdict(list)); pairs = []
    for row in takes:
        metadata = row.get('metadata'); flow = row['flow']; counts['take_rows'] += 1
        if not row.get('taken') or metadata is None:
            counts['empty_or_no_metadata'] += 1; continue
        source_stamp = metadata.get('source_timestamp', 0); received = metadata.get('received_timestamp', 0)
        if source_stamp <= 0 or received <= 0:
            counts['zero_or_missing_metadata_stamp'] += 1; continue
        before_real = row['before_realtime_ns']; after_real = row['end_realtime_ns']
        if not source_stamp <= received <= after_real:
            counts['invalid_metadata_order'] += 1; continue
        values = dict(source_to_RMW_received_ms=(received-source_stamp)/1e6,
                      RMW_received_to_take_before_ms=(before_real-received)/1e6,
                      RMW_received_to_take_end_ms=(after_real-received)/1e6,
                      source_to_take_before_ms=(before_real-source_stamp)/1e6,
                      take_wall_ms=(row['end_mono_ns']-row['mono_ns'])/1e6,
                      take_thread_CPU_ms=(row['end_thread_cpu_ns']-row['thread_cpu_ns'])/1e6,
                      realtime_mono_bracket_width_ms=(row['before_realtime_mono_after_ns']-row['mono_ns'])/1e6)
        for name, value in values.items():
            metrics[flow][name].append(value)
        counts['valid_metadata'] += 1
        # This mono projection assumes the realtime/monotonic offset stayed
        # stable between source publication and take. It is not a strict source
        # realtime publication bracket: source did not independently record one.
        projected_low = source_stamp-before_real+row['mono_ns']
        projected_high = source_stamp-before_real+row['before_realtime_mono_after_ns']
        candidates = [item for item in sources[(flow, tfkey(row.get('tf_edges', []), 'stamp_ns'))]
                      if item['before_monotonic_ns'] <= projected_high
                      and item['after_monotonic_ns'] >= projected_low]
        counts['projected_unique' if len(candidates) == 1 else 'projected_ambiguous' if candidates else 'projected_unmatched'] += 1
        pairs.append(dict(flow=flow, tf_edges=row.get('tf_edges'), metadata=metadata,
            take_before_monotonic_ns=row['mono_ns'], metrics=values,
            projected_source_mono_bracket_ns=[projected_low, projected_high],
            projected_source_record_candidates=[item['source_record_id'] for item in candidates]))
    first_fault = {robot: next((event for event in guard['events'] if event['kind']=='latched_INVALID'), None)
                   for robot, guard in gateway['guards'].items()}
    result = dict(counts=dict(counts), groups={str(flow): {name: stats(values) for name, values in group.items()}
                                             for flow, group in metrics.items()},
                  first_fault=first_fault, last_peer={name: peer[-1][name] for name in
                      ('generated_sim', 'sequence', 'ready', 'odom_stamps', 'correction_stamps', 'ages')},
                  worst_metadata_received_to_take=sorted(pairs,
                      key=lambda pair: pair['metrics']['RMW_received_to_take_before_ms'], reverse=True)[:6],
                  pairs=pairs,
                  boundaries=['Source/received RMW timestamps are system-time metadata, not simulation stamps.',
                    'RMW received semantics are not independently proven earliest DDS arrival/reader-ready time.',
                    'Receive-to-take is a reported timestamp interval, not isolated Python queue CPU.',
                    'Source mono projection assumes stable clock offset; no exact source realtime bracket was recorded.',
                    'Repeated edge+stamp is not unique CDR identity; unmatched/ambiguous projection is not loss.',
                    'Private SDK same-take observer has scheduling overhead, not a pure production baseline.'])
    (args.case/'take-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    result.pop('pairs')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

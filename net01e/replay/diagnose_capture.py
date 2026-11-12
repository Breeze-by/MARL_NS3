"""Offline new-result stage diagnosis. Does not read historical corpus/body/ledger.

Header/edge matching is a semantic timing cohort, not unique body/packet identity.
Repeated keys retain publication-time brackets; no inferred permanent loss.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def summary(values):
    values = sorted(values)
    if not values:
        return dict(n=0)
    return dict(n=len(values), min=values[0], median=values[(len(values)-1)//2],
                p95=values[math.ceil(.95*len(values))-1], max=values[-1])


def key(row, source):
    if row['flow'] % 20 == 3:
        edges = row.get('original_tf_edges' if source else 'tf_edges', [])
        return tuple((edge['frame_id'], edge['child_frame_id'],
                      edge['source_stamp_ns' if source else 'stamp_ns']) for edge in edges)
    if source and row.get('original_source_stamp_available'):
        return row['original_source_stamp_ns']
    if not source and row.get('source_stamp_available'):
        return row['source_stamp_ns']
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads((args.case/'source/result.json').read_text())['inputs']
    gateway = json.loads((args.case/'gateway/network-gateway.json').read_text())
    fault_ns = min(int(event['monotonic']*1e9) for guard in gateway['guards'].values()
                   for event in guard['events'] if event['kind'] == 'latched_INVALID')
    published = [row for row in source if row['state'] == 'PUBLISHED' and row['before_monotonic_ns'] <= fault_ns]
    captures = [row for row in gateway['topics']['R']['captured'] +
                [item for item in gateway['topics']['C']['captured'] if item['flow'] == 89]
                if row['endpoint_capture_monotonic_ns'] <= fault_ns]
    groups = defaultdict(list)
    for row in published:
        groups[(row['flow'], key(row, True))].append(row)
    results = {}
    for flow in sorted({row['flow'] for row in published}):
        src = [row for row in published if row['flow'] == flow]
        cap = [row for row in captures if row['flow'] == flow]
        lag_earliest = []; lag_latest = []; ages = []; unmatched = 0; ambiguous = 0
        worst = None
        for row in cap:
            identity = key(row, False)
            if identity is None:
                unmatched += 1; continue
            candidates = [item for item in groups[(flow, identity)]
                          if item['after_monotonic_ns'] <= row['endpoint_capture_monotonic_ns']]
            if not candidates:
                unmatched += 1; continue
            ambiguous += len(candidates) > 1
            low = (row['endpoint_capture_monotonic_ns'] - max(x['after_monotonic_ns'] for x in candidates))/1e6
            high = (row['endpoint_capture_monotonic_ns'] - min(x['after_monotonic_ns'] for x in candidates))/1e6
            lag_earliest.append(high); lag_latest.append(low)
            ages.append((row['capture_node_sim_ns'] - max(x['source_publish_sim_ns'] for x in candidates))/1e6)
            if worst is None or high > worst['lag_upper_wall_ms']:
                worst = dict(key=identity, lag_upper_wall_ms=high, lag_lower_wall_ms=low,
                             capture_monotonic_ns=row['endpoint_capture_monotonic_ns'],
                             candidate_source_record_ids=[x['source_record_id'] for x in candidates])
        normal = [row for row in src if row['phase'] == 'normal']
        span = ((max(row['source_publish_sim_ns'] for row in normal) - min(row['source_publish_sim_ns'] for row in normal))/1e9
                if normal else 0)
        results[str(flow)] = dict(planned=sum(row['flow'] == flow for row in source),
            published_before_fault=len(src), captured_before_fault=len(cap),
            normal_publications_per_sim_s=len(normal)/span if span > 0 else None,
            publication_wall_ms=summary([(r['after_monotonic_ns']-r['before_monotonic_ns'])/1e6 for r in src]),
            publication_thread_cpu_ms=summary([(r['after_thread_cpu_ns']-r['before_thread_cpu_ns'])/1e6 for r in src]),
            semantic_match_missing=unmatched, semantic_match_ambiguous=ambiguous,
            source_to_capture_wall_ms_lower=summary(lag_latest), source_to_capture_wall_ms_upper=summary(lag_earliest),
            source_to_capture_sim_ms_lower=summary(ages), worst=worst)
    tf_groups = Counter((row['flow'], tuple((edge['frame_id'], edge['child_frame_id'])
                                          for edge in row.get('original_tf_edges', [])))
                        for row in source if row['flow'] % 20 == 3)
    duplicate_stamps = {}
    for flow in (23, 43, 63):
        identities = Counter(key(row, True) for row in source if row['flow'] == flow and row['phase'] == 'normal')
        duplicate_stamps[str(flow)] = dict(records=sum(identities.values()), unique_edge_stamp_keys=len(identities),
            extra_repeated_key_records=sum(count-1 for count in identities.values()),
            multiplicities=dict(Counter(identities.values())),
            semantics='Repeated TF edge+stamp, not necessarily equal transform content or same publisher')
    result = dict(first_fault_monotonic_ns=fault_ns, flows=results,
                  original_tf_edge_group_counts=[dict(flow=flow, edges=edges, count=count)
                                                 for (flow, edges), count in sorted(tf_groups.items())],
                  duplicate_tf_edge_stamps=duplicate_stamps,
                  gateway_dispatch_stats=gateway['dispatch_stats'],
                  gateway_R_cpu_aggregates=gateway['dispatch_cpu_profile']['aggregates']['R'],
                  scope='Single new failed A1 finite window. Full-life inclusive profile spans not additive. '
                        'Header/edge key timing brackets are not exact body identity or source loss. '
                        'TF edge role is observed; original publisher GID absent.')
    (args.case/'capture-diagnosis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(output=str(args.case/'capture-diagnosis.json'), first_fault_ns=fault_ns)))


if __name__ == '__main__':
    main()

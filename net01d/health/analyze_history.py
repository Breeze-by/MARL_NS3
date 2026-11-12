"""Read one saved B case; no ROS imports, replay, native ledger or source writes.

Health pairing requires unique existing CDR identity and flow. Missing/ambiguous
pairs stay unresolved; no nearest-time association or serializer re-execution.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics


def summary(values):
    values = sorted(values)
    if not values:
        return dict(n=0, status="UNRESOLVED")
    return dict(n=len(values), unit="ms", min=values[0], median=statistics.median(values),
        p95=values[math.ceil(.95*len(values))-1], p99=values[math.ceil(.99*len(values))-1],
        max=values[-1], negative_count=sum(v < 0 for v in values),
        diagnostic_fraction_above={str(t):sum(v > t for v in values)/len(values)
            for t in (10, 100, 300)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.case/'peer-keepout.jsonl').open() as stream:
        peers = {r['sequence']:r for r in map(json.loads, stream)}
    source_ids = defaultdict(set)
    with (args.case/'bound-mask-publications.jsonl').open() as stream:
        for row in map(json.loads, stream):
            source_ids[row['health_cdr_sha256']].add(row['bound_state']['sequence'])
    # One parse of the saved Gateway JSON. Never read the multi-GB native ledger.
    with (args.case/'network-gateway.json').open() as stream:
        gateway = json.load(stream)
    cohort = {seq:r for seq,r in peers.items() if 15.76 <= r['generated_sim'] <= 103.33}
    captured = defaultdict(list)
    delivered = defaultdict(list)
    destination = {}
    for row in gateway['records']:
        if row['kind'] == 'destination_complete_message':
            meta = row['meta']
            destination[(meta['flow'], meta.get('message_id', meta.get('native_id')))] = row['monotonic_ns']
    for row in gateway['topics']['C']['captured']:
        if row['flow'] in (31, 51, 71):
            captured[(row['flow'], row['cdr_sha256'])].append(row)
    for row in gateway['topics']['R']['delivered']:
        if row['flow'] in (31, 51, 71):
            delivered[(row['flow'], row['cdr_sha256'])].append(row)
    pairs = []; unresolved = defaultdict(int)
    for key, rows in captured.items():
        flow, identity = key
        seqs = source_ids.get(identity, set())
        if len(seqs) != 1:
            unresolved['C_capture_without_unique_source_hash_sequence'] += len(rows)
            continue
        seq, = seqs
        if seq not in cohort:
            continue
        if len(rows) != 1:
            unresolved['nonunique_C_capture_identity'] += len(rows)
            continue
        capture, = rows
        timing = cohort[seq]['delivery_timing']
        pair = dict(sequence=seq, flow=flow, generated_sim=cohort[seq]['generated_sim'],
            source_wrapper_before_monotonic_ns=round(timing['health_publish_before_monotonic']*1e9),
            source_wrapper_after_monotonic_ns=round(timing['health_publish_after_monotonic']*1e9),
            C_callback_capture_monotonic_ns=capture['endpoint_capture_monotonic_ns'])
        received = delivered.get(key, [])
        if len(received) == 1:
            row, = received
            mid = row.get('message_id', row.get('native_id'))
            pair['native_message_id'] = mid
            complete = destination.get((flow, mid))
            if complete is not None:
                pair['R_destination_complete_monotonic_ns'] = complete
            pair['R_public_publish_before_monotonic_ns'] = row['endpoint_publish_monotonic_ns']
            pair['R_public_publish_after_monotonic_ns'] = row['publish_after_monotonic_ns']
        else:
            unresolved['no_unique_R_public_delivery_for_C_capture'] += 1
        pairs.append(pair)
    stats = {}
    for flow in (31, 51, 71):
        rows = [r for r in pairs if r['flow'] == flow]
        spans = {}
        for name, begin, end in (
            ('wrapper_after_to_C_capture_lower_bound', 'source_wrapper_after_monotonic_ns', 'C_callback_capture_monotonic_ns'),
            ('C_capture_to_R_destination', 'C_callback_capture_monotonic_ns', 'R_destination_complete_monotonic_ns'),
            ('R_destination_to_public_publish_before_includes_guard', 'R_destination_complete_monotonic_ns', 'R_public_publish_before_monotonic_ns'),
            ('R_public_publish_call', 'R_public_publish_before_monotonic_ns', 'R_public_publish_after_monotonic_ns')):
            spans[name] = summary([(r[end]-r[begin])/1e6 for r in rows if begin in r and end in r])
        stats[str(flow)] = dict(unique_source_C_pairs=len(rows), stages=spans)
    times = sorted(r['delivery_timing']['health_publish_after_monotonic'] for r in cohort.values())
    result = dict(scope='Read-only historical B01, autonomy generated_sim [15.76,103.33]; no replay',
        source_case=str(args.case.resolve()), autonomy_source_rows=len(cohort),
        quantiles='nearest rank p95/p99; median arithmetic midpoint; negative samples retained',
        diagnostic_thresholds='10/100/300ms fractions are descriptions, not new safety criteria',
        join='Exact existing CDR hash + flow, unique source sequence and single capture/delivery only; no fresh hash/serialization',
        source_wrapper_call=summary([(r['delivery_timing']['health_publish_after_monotonic']-
            r['delivery_timing']['health_publish_before_monotonic'])*1000 for r in cohort.values()]),
        source_wrapper_return_intervals=summary([(b-a)*1000 for a,b in zip(times,times[1:])]),
        by_flow=stats, unresolved_pair_counts=dict(unresolved),
        target_sequences=[r for r in pairs if r['sequence'] in (1032,1033)],
        old_B_has_dispatch_profile='dispatch_cpu_profile' in gateway,
        UNRESOLVED=['raw DDS publish call separate from binding wrapper',
            'DDS reader-ready/receive to Python callback', 'C serialization and queue/flush subspans',
            'health native ingress/TX/RX without a dedicated ledger extraction',
            'precise guard receive/evaluation before/after and thread CPU',
            'single cause of historical 137.929925ms gap'])
    with (args.out/'historical_timeline.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

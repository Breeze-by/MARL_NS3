"""Inert offline native-admission census; no payload, ledger, PCAP or ROS reads."""
import argparse
from collections import Counter, defaultdict
import gc
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from net01d.followup04.costs.export_costs import stats

CASES = [(r, arm) for r in range(1, 4) for arm in ('b', 'c')]
OUTCOMES = ('complete_RX_before_cutoff', 'complete_RX_at_or_after_cutoff',
            'not_seen_in_sealed_RX_metadata', 'ambiguous_duplicate_ingress_key',
            'ambiguous_duplicate_RX_key', 'route_ID_matched_metadata_mismatch')


def key(row, ingress=False):
    return (row['sender'], row['receiver'], row['flow'],
            row['native_message_id' if ingress else 'message_id'])


def label(flow):
    if flow == 89:
        return 'merged_map'
    if flow == 95:
        return 'controller_records'
    if flow in (30, 50, 70):
        return 'bound_mask'
    if flow in (31, 51, 71):
        return 'health'
    if flow in (32, 52, 72):
        return 'filter_info'
    if 220 <= flow <= 269 and flow // 20 in (11, 12, 13):
        return 'Action_offset_' + str(flow % 20)
    return {1: 'map', 2: 'odom', 3: 'tf', 4: 'tf_static',
            5: 'local_costmap', 6: 'cmd_vel'}.get(flow % 20, 'unclassified')


def analyze(round_number, arm, output):
    case = f'corr6201-v2-r{round_number:02}-{arm}'
    base = REPO/'net01e/followup01'
    network = base/'gz-runs'/f'{case}.network'
    reads = {}

    def read(path):
        if str(path) in reads:
            raise RuntimeError('Duplicate metadata load: ' + str(path))
        began = time.monotonic()
        with path.open() as stream:
            value = json.load(stream)
        reads[str(path)] = dict(bytes=path.stat().st_size,
                                decode_wall_s=time.monotonic()-began, loads=1)
        return value

    proof = read(base/'gz-analysis'/case/'pre-evaluation-exit-proof.json')
    if not proof['all_known_writer_and_owned_gone']:
        raise ValueError('Original writer-exit proof is not closed')
    cost = read(base/f'health-cost-{arm}-r{round_number:02}-01'/'manifest.json')
    window = cost['window']
    lo_g = round(window['original_start_sim']*1e9)
    hi_g = round(window['original_end_sim']*1e9)
    offset = proof['host']['controlled_time']['coordinator_final']['fixed_offset_ns']
    lo, hi = lo_g-offset, hi_g-offset
    ingress = read(network/'hub-ingress.json')
    deliveries = read(network/'hub-deliveries.json')
    input_counts = Counter(key(row, True) for row in ingress)
    output_counts = Counter(key(row) for row in deliveries)
    unique_rx = {key(row): row for row in deliveries if output_counts[key(row)] == 1}
    counts = Counter(dict.fromkeys(('native_admission_mother',)+OUTCOMES, 0))
    perflow = defaultdict(lambda: Counter(dict.fromkeys(('native_admission_mother',)+OUTCOMES, 0)))
    values = defaultdict(lambda: defaultdict(list))
    anomalies = []
    terminal = cost['full_source_census']['known_terminal_monotonic_ns']
    for row in ingress:
        flow = row['flow']
        if flow in (65534, 65535):
            counts['excluded_hello_ingress'] += 1
            continue
        if not lo <= row['admission_ns'] < hi:
            counts['outside_native_admission_window'] += 1
            continue
        k = key(row, True)
        fc = perflow[flow]
        counts['native_admission_mother'] += 1
        fc['native_admission_mother'] += 1
        if terminal is not None:
            counts['mother_Hub_ingress_before_first_recorded_Guard_terminal' if
                   row['hub_ingress_monotonic_ns'] < terminal else
                   'mother_Hub_ingress_at_or_after_first_recorded_Guard_terminal'] += 1
        if lo_g <= row['source_stamp_ns'] < hi_g:
            counts['admitted_source_header_stamp_in_G_window_NOT_generation_census'] += 1
            fc['admitted_source_header_stamp_in_G_window_NOT_generation_census'] += 1
        rx = unique_rx.get(k)
        if input_counts[k] != 1:
            outcome = 'ambiguous_duplicate_ingress_key'
        elif output_counts[k] > 1:
            outcome = 'ambiguous_duplicate_RX_key'
        elif rx is None:
            outcome = 'not_seen_in_sealed_RX_metadata'
        elif any(row[field] != rx[field] for field in ('bytes', 'source_stamp_ns')):
            outcome = 'route_ID_matched_metadata_mismatch'
        else:
            outcome = 'complete_RX_before_cutoff' if rx['ns3_rx_ns'] < hi else 'complete_RX_at_or_after_cutoff'
            delay = rx['ns3_rx_ns']-row['admission_ns']
            wall = rx['hub_receive_monotonic_ns']-row['hub_ingress_monotonic_ns']
            if terminal is not None:
                counts['matched_Hub_RX_before_first_recorded_Guard_terminal' if
                       rx['hub_receive_monotonic_ns'] < terminal else
                       'matched_Hub_RX_at_or_after_first_recorded_Guard_terminal'] += 1
            for group in ('all', str(flow)):
                values[group]['native_service_ns_all_matched'].append(delay)
                values[group]['native_service_ns_'+outcome].append(delay)
                values[group]['mixed_wall_Hub_ingress_to_RX_ns_all_matched'].append(wall)
            if delay < 0 or wall < 0:
                anomalies.append(dict(key=k, reason='negative_delay_preserved',
                                      native_delay_ns=delay, mixed_wall_ns=wall,
                                      ingress=row, RX=rx))
        counts[outcome] += 1
        fc[outcome] += 1
        if outcome.startswith(('ambiguous_', 'route_ID_')):
            anomalies.append(dict(key=k, reason=outcome, ingress=row, RX=rx,
                                  ingress_key_count=input_counts[k], RX_key_count=output_counts[k]))
    result = dict(case=case, original_actual_entry_exit=proof['actual_entry_exit'],
        original_result=proof['original_result_small'], window=dict(
            G_start_inclusive_ns=lo_g, G_end_exclusive_ns=hi_g,
            fixed_offset_ns=offset, N_start_inclusive_ns=lo, N_end_exclusive_ns=hi,
            mapping='N=G-fixed_offset_ns; original time_control_state anchor; no clock fitting',
            first_recorded_Guard_terminal_monotonic_ns=terminal,
            main_mother_is_not_strict_prefault=True,
            original_window=window),
        source_generated_mother_separate=dict(
            existing_source_census=cost['full_source_census'],
            all_business_source_generated_count='UNMEASURED: Hub metadata observes admitted attempts, not original publishers',
            header_stamp_warning='Header stamp may be zero, old state or reused; not generation time. Header-window admitted counts are descriptive only.'),
        counts=dict(counts), perflow={str(f):dict(label=label(f), counts=dict(v),
            distributions={name:stats(data,unit='ns') for name,data in values[str(f)].items()})
            for f,v in sorted(perflow.items())},
        distributions={name:stats(data,unit='ns') for name,data in values['all'].items()},
        identity_audit=dict(
            scope='Whole sealed metadata, including context outside mother; pairing requires unique full route/native ID and equal bytes/source_stamp_ns',
            ingress_rows=len(ingress), RX_rows=len(deliveries),
            duplicate_ingress_keys=sum(n>1 for n in input_counts.values()),
            duplicate_ingress_rows=sum(n for n in input_counts.values() if n>1),
            duplicate_RX_keys=sum(n>1 for n in output_counts.values()),
            duplicate_RX_rows=sum(n for n in output_counts.values() if n>1),
            orphan_RX_rows=sum(n for k,n in output_counts.items() if k not in input_counts)),
        read_manifest=reads, limitations=[
            'Native service = complete native RX timestamp minus scheduled native admission; includes native stack/TCP/queues/reassembly, not pure airtime or CPU time.',
            'Matched delay distributions are conditional on unique metadata-matched complete RX; full admission mother and every unmatched outcome remain explicit.',
            'Not seen in sealed RX metadata is finite non-observation, not permanent RF loss. Cutoff is original autonomy end; later RX is distinct.',
            'Hub wall interval mixes host IPC/scheduling/native execution/barriers and is not pure ns3 wall service.',
            'Metadata identity/length/stamp agreement is not body-byte identity or ROS-consumption proof. No payload hashes or body reads.',
            'Action application retransmission attempts are distinct native messages; no logical-request deduplication.',
            'Original failures, short phases, safety outcomes and process exits are unchanged.'])
    with (output/f'{case}.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    with (output/f'{case}.anomalies.json').open('x') as stream:
        json.dump(anomalies, stream, indent=2)
    return dict(case=case, counts=dict(counts), original_actual_entry_exit=proof['actual_entry_exit'],
                metadata_bytes=sum(v['bytes'] for p,v in reads.items() if '/hub-' in p))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    began = time.monotonic()
    completed = []
    for r, arm in CASES:
        completed.append(analyze(r, arm, args.output))
        gc.collect()  # Release each case before the next two-table load.
        print(json.dumps(completed[-1]), flush=True)
        with (args.output/'progress.json').open('w') as stream:
            json.dump(dict(completed=completed, wall_s=time.monotonic()-began), stream, indent=2)


if __name__ == '__main__':
    main()

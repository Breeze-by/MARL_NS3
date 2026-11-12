"""Inert, one-pass native service-cost extraction for the normal RX cohort."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
import time

REPO = Path(__file__).resolve().parents[3]
HEADER, CHUNK = 36, 1164
EVENTS = {'ipc_ingress', 'tcp_write', 'tcp_frame_rx', 'message_deliver',
          'duplicate_fragment', 'late_or_duplicate_fragment', 'incomplete_expired'}


def stats(values):
    values = sorted(values)
    if not values:
        return dict(n=0, unit='sim_ms', status='UNMEASURED')
    return dict(n=len(values), unit='sim_ms', min=values[0],
                median=statistics.median(values), p95=values[math.ceil(.95*len(values))-1],
                p99=values[math.ceil(.99*len(values))-1], max=values[-1],
                negative_n=sum(v < 0 for v in values))


def load_targets(path):
    targets = {}; counts = Counter(); unavailable = Counter()
    with path.open() as stream:
        for line in stream:
            row = json.loads(line); counts['rows'] += 1
            meta = row.get('native_meta')
            required = ('message_id', 'sender', 'receiver', 'flow', 'bytes', 'ns3_rx_ns')
            if meta is None or any(meta.get(k) is None for k in required):
                unavailable['missing_native_meta_fields'] += 1; continue
            if row['message_id'] != meta['message_id'] or row['flow'] != meta['flow']:
                unavailable['cache_identity_mismatch'] += 1; continue
            mid = meta['message_id']
            if mid in targets:
                targets[mid]['cache_rows'] += 1
                counts['duplicate_native_id_rows'] += 1
                continue
            # Keep only identity/phase witnesses, never the full cache row.
            targets[mid] = dict(identity=(meta['sender'], meta['receiver'], meta['flow'], meta['bytes']),
                witness=dict(kind=row['kind'], robot=row['robot'], sequence=row['sequence'],
                    message_id=mid, accepted=row['accepted'], from_node=meta['sender'],
                    to_node=meta['receiver'], flow=meta['flow'], total_body_bytes=meta['bytes']),
                cache_rx_ns=meta['ns3_rx_ns'], cache_rows=1, events=Counter(), bad=Counter(),
                ingress=None, first_write=None, last_write=None, deliver=None,
                write_chunks=0, frame_prefix=0, accepted_bytes=0, offered_bytes=0,
                rx_next=0, rx_chunks=0, rx_body_bytes=0)
    counts['unique_native_ids'] = len(targets)
    counts['ambiguous_native_ids'] = sum(t['cache_rows'] > 1 for t in targets.values())
    return targets, dict(counts), dict(unavailable)


def consume(row, target, boundary, window):
    kind = row['kind']; target['events'][kind] += 1
    mono = row.get('monotonic_ns'); lo = window['lo_monotonic_ns']; hi = window['hi_monotonic_ns']
    side = ('unmeasured' if mono is None or lo is None or hi is None else
            'before_normal_R_bracket' if mono < lo else
            'after_normal_R_bracket' if mono > hi else 'inside_normal_R_bracket')
    boundary[kind][side] += 1
    identity = (row.get('from'), row.get('to'), row.get('flow'),
                row.get('body_bytes') if kind == 'ipc_ingress' else row.get('total'))
    if identity != target['identity']:
        target['bad']['event_identity_mismatch'] += 1; return
    stamp = dict(ns3_ns=row['ns3_ns'], monotonic_ns=mono)
    if kind == 'ipc_ingress':
        if target['ingress'] is None:
            target['ingress'] = dict(stamp, admission_ns=row['admission_ns'])
        return
    total = target['identity'][3]
    if kind in ('tcp_write', 'tcp_frame_rx', 'message_deliver'):
        offset = row['offset']; length = row['body_bytes']
        if offset < 0 or offset % CHUNK or offset >= total or length != min(CHUNK, total-offset):
            target['bad']['invalid_fragment_extent'] += 1
    if kind == 'tcp_write':
        offered = row['offered_bytes']; accepted = row['accepted_bytes']
        target['offered_bytes'] += offered; target['accepted_bytes'] += accepted
        expected = target['write_chunks'] * CHUNK
        if row['offset'] != expected or row['frame_offset'] != target['frame_prefix']:
            target['bad']['write_duplicate_overlap_or_gap'] += 1
        if not 0 < accepted <= offered or row['frame_offset'] + accepted > HEADER + row['body_bytes']:
            target['bad']['invalid_Send_accepted_extent'] += 1
        target['frame_prefix'] = row['frame_offset'] + accepted
        if target['frame_prefix'] == HEADER + row['body_bytes']:
            target['write_chunks'] += 1; target['frame_prefix'] = 0
        if target['first_write'] is None: target['first_write'] = stamp
        target['last_write'] = stamp
    elif kind == 'tcp_frame_rx':
        if row['offset'] < target['rx_next']: target['bad']['rx_duplicate_or_overlap'] += 1
        elif row['offset'] > target['rx_next']: target['bad']['rx_gap_or_out_of_order'] += 1
        target['rx_next'] = row['offset'] + row['body_bytes']
        target['rx_chunks'] += 1; target['rx_body_bytes'] += row['body_bytes']
    elif kind == 'message_deliver':
        if target['deliver'] is None: target['deliver'] = stamp
        if row['ns3_ns'] != target['cache_rx_ns']: target['bad']['Gateway_RX_stamp_mismatch'] += 1


def summarize(targets, cache_counts, cache_unavailable, boundary):
    coverage = Counter(); values = defaultdict(list); worst = {}; unavailable = Counter()
    byte_counts = Counter(); details = Counter()
    names = ('admission_to_first_Send_accept', 'admission_to_last_Send_accept',
             'first_Send_accept_to_complete_reassembly', 'last_Send_accept_to_complete_reassembly',
             'admission_to_complete_reassembly')
    for target in targets.values():
        events = target['events']; total = target['identity'][3]
        chunks = (total + CHUNK - 1) // CHUNK
        coverage['unique_native_id_denominator'] += 1
        for kind in ('ipc_ingress', 'tcp_write', 'tcp_frame_rx', 'message_deliver'):
            coverage[kind + '_present_ids'] += bool(events[kind])
            coverage[kind + '_missing_ids'] += not events[kind]
            details[kind + '_rows'] += events[kind]
        for kind in ('ipc_ingress', 'message_deliver'):
            coverage[kind + '_duplicate_ids'] += events[kind] > 1
        for kind in ('duplicate_fragment', 'late_or_duplicate_fragment', 'incomplete_expired'):
            details[kind + '_rows'] += events[kind]
        byte_counts.update(expected_body_bytes=total, expected_chunks=chunks,
            expected_framed_Send_bytes=total+HEADER*chunks, Send_accepted_bytes=target['accepted_bytes'],
            Send_offered_bytes=target['offered_bytes'], fully_accepted_chunks=target['write_chunks'],
            received_chunk_rows=target['rx_chunks'], received_body_bytes=target['rx_body_bytes'])
        bad = target['bad'].copy()
        if target['accepted_bytes'] != total+HEADER*chunks or target['write_chunks'] != chunks or target['frame_prefix']:
            bad['write_bytes_or_chunks_incomplete'] += 1
        if target['rx_chunks'] != chunks or target['rx_body_bytes'] != total or target['rx_next'] != total:
            bad['rx_bytes_or_chunks_incomplete'] += 1
        for reason, count in bad.items(): details[reason + '_rows_or_checks'] += count
        reason = ('ambiguous_cache_native_id' if target['cache_rows'] > 1 else
                  'ambiguous_ingress_or_deliver' if events['ipc_ingress'] > 1 or events['message_deliver'] > 1 else
                  'missing_ingress_write_or_deliver' if not all(target[k] for k in ('ingress', 'first_write', 'last_write', 'deliver')) else
                  'identity_extent_bytes_or_RX_mismatch' if bad else None)
        if reason:
            unavailable[reason] += 1; continue
        coverage['fully_matched_ids'] += 1
        admission = target['ingress']['admission_ns']; first = target['first_write']['ns3_ns']
        last = target['last_write']['ns3_ns']; deliver = target['deliver']['ns3_ns']
        witness = dict(target['witness'], admission_ns=admission, ingress=target['ingress'],
            first_Send_accept=target['first_write'], last_Send_accept=target['last_write'],
            complete_reassembly=target['deliver'], expected_chunks=chunks,
            Send_calls=events['tcp_write'], Send_accepted_bytes=target['accepted_bytes'])
        prefix = target['witness']['robot'] + '/' + target['witness']['kind'] + '/'
        for name, begin, end in zip(names, (admission, admission, first, last, admission), (first, last, deliver, deliver, deliver)):
            value = (end-begin)/1e6
            for stage in (name, prefix+name):
                values[stage].append(value)
                if stage not in worst or value > worst[stage]['value']:
                    worst[stage] = dict(value=value, unit='sim_ms', **witness)
    stages = {name: dict(**stats(values[name]), worst=worst.get(name)) for name in set(names) | values.keys()}
    for name in names:
        stages[name].update(unique_native_id_denominator=len(targets),
            matched_ids=coverage['fully_matched_ids'], unavailable_ids=sum(unavailable.values()))
    return dict(cache_counts=cache_counts, cache_unavailable=cache_unavailable,
        matching_coverage=dict(coverage), unavailable_unique_ids=dict(unavailable),
        bytes_and_chunks=dict(byte_counts), event_and_integrity_counts=dict(details),
        boundary_event_counts={k: dict(v) for k, v in boundary.items()}, stages=stages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-directory', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    admission = json.loads(Path(__file__).with_name('NATIVE_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        parser.error('SOURCE_ONLY: separate Root source/plan review and single-stream START required')
    args.directory.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='STARTED', cases=[], PCAP_reads=0, Gateway_reads=0, stderr_reads=0,
                    model_runs=0, automatic_retries=0)
    active = None
    try:
        for spec in admission['cases']:
            active = dict(arm=spec['arm'], case=spec['case'], ledger=spec['ledger'],
                ledger_opens=0, lines_read=0, bytes_read=0, status='LOADING_SMALL_CACHE')
            manifest['cases'].append(active)
            summary = json.loads((args.cache_directory/(spec['arm']+'.json')).read_text())
            if summary['case']['case'] != spec['case']:
                raise ValueError('Cache case does not match admitted original case')
            targets, counts, missing = load_targets(args.cache_directory/(spec['arm']+'-native-targets.jsonl'))
            boundary = defaultdict(Counter); active['status'] = 'STREAMING'
            began = time.monotonic(); active['ledger_opens'] += 1
            try:
                with (REPO/spec['ledger']).open('rb') as stream:
                    for line in stream:
                        active['line_start_byte'] = active['bytes_read']
                        active['lines_read'] += 1; active['bytes_read'] += len(line)
                        try: row = json.loads(line)
                        except (ValueError, UnicodeError):
                            active['first_bad_line_prefix'] = repr(line[:240]); raise
                        if row.get('kind') in EVENTS and row.get('message_id') in targets:
                            active['current_target_event'] = dict(kind=row['kind'], message_id=row['message_id'])
                            consume(row, targets[row['message_id']], boundary, summary['window'])
                active['status'] = 'STREAM_COMPLETE'
            finally:
                active['stream_wall_s'] = time.monotonic()-began
            output = summarize(targets, counts, missing, boundary)
            output.update(case=spec, normal_R_window=summary['window'],
                actual_source_identity=summary['actual_source_identity'], case_outcome=summary['case_outcome'],
                cohort='Conditional normal R-consumed health/mask native IDs, not all native ingress, not a loss denominator',
                semantics=['admission_ns is scheduled native admission, not ingress event time or source_stamp_ns',
                    'Send accept is socket-buffer acceptance including 36B headers; not PHY transmit or airtime',
                    'Native sim service includes application/TCP queueing, protocol and Wi-Fi retries; no RF-only attribution',
                    'Boundary counts compare native monotonic event timestamps with normal R consumption bracket; prior/late events retained',
                    'No stages are added together; complete matched messages only; duplicate IDs excluded explicitly',
                    'Nearest-rank p95/p99; arithmetic median; negative differences retained'],
                UNMEASURED=['Per-message CPU and native Run/STEP wall/CPU: STEP boundaries are stderr, not this ledger',
                    'PHY airtime and isolated TCP/Wi-Fi/CPU contributions'])
            with (args.directory/(spec['arm']+'.json')).open('x') as stream:
                json.dump(output, stream, indent=2); stream.write('\n')
            del targets, summary, output
        manifest['status'] = 'EXPORTED_ONLY_NO_QUALIFICATION_CHANGE'
    except BaseException as error:
        manifest.update(status='FAIL_FIRST_ERROR_PRESERVED', error=repr(error))
        if active is not None: active['status'] = 'FAIL_NO_RETRY'
        raise
    finally:
        (args.directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()

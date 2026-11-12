"""Saved opt-in health/profile observations only; no ROS, replay or ledger scan."""
import argparse
import json
from pathlib import Path

from analyze_history import summary


def analyze(case):
    with (case/'gateway/network-gateway.json').open() as stream:
        gateway = json.load(stream)
    with (case/'peer/health-trace.json').open() as stream:
        peer = json.load(stream)
    sources = {r['sequence']:r for r in peer['rows']}
    captures = [r for r in gateway['health_trace']['rows'] if r['stage']=='C_health_callback']
    receipts = [r for r in gateway['health_trace']['rows'] if r['stage']=='R_health_intake']
    destination = {(r['sequence'],r['flow']):r for r in receipts}
    spans = []
    for original in gateway['dispatch_cpu_profile']['longspans']:
        row = dict(original)
        row['wall_ms'] = (row['end_monotonic_ns']-row['begin_monotonic_ns'])/1e6
        row['thread_cpu_ms'] = (row['end_thread_cpu_ns']-row['begin_thread_cpu_ns'])/1e6
        row['wall_minus_thread_cpu_ms'] = row['wall_ms']-row['thread_cpu_ms']
        spans.append(row)
    pairs = []
    for capture in captures:
        key = capture['sequence'],capture['flow']
        source = sources.get(key[0])
        if source is None:
            continue
        row = dict(sequence=key[0],flow=key[1],
            raw_publish_begin_mono_ns=source['mono_ns'],
            raw_publish_end_mono_ns=source['raw_publish_end_mono_ns'],
            binding_end_mono_ns=source['binding_end_mono_ns'],
            C_callback_entry_mono_ns=capture['callback_entry_mono_ns'],
            raw_return_to_C_entry_ms=(capture['callback_entry_mono_ns']-source['raw_publish_end_mono_ns'])/1e6)
        receive = destination.get(key)
        if receive is not None:
            row.update(R_intake_begin_mono_ns=receive['mono_ns'],
                R_actual_guard_receipt_mono_s=receive['actual_receipt_mono_s'],
                R_guard_end_mono_ns=receive['guard_end_mono_ns'],
                armed=receive['armed'],fault_after=receive['fault_after'])
        pairs.append(row)
    by_flow = {}
    for flow in (31,51,71):
        cc = [r for r in captures if r['flow']==flow]
        rr = [r for r in receipts if r['flow']==flow]
        pp = [r for r in pairs if r['flow']==flow]
        by_flow[str(flow)] = dict(C_rows=len(cc),R_rows=len(rr),source_matched=len(pp),
            raw_return_to_C_entry=summary([r['raw_return_to_C_entry_ms'] for r in pp]),
            raw_return_to_actual_guard_receipt=summary([(r['R_actual_guard_receipt_mono_s']*1e9-r['raw_publish_end_mono_ns'])/1e6 for r in pp if 'R_actual_guard_receipt_mono_s' in r]),
            actual_guard_receipt_intervals=summary([(b['actual_receipt_mono_s']-a['actual_receipt_mono_s'])*1000 for a,b in zip(rr,rr[1:])]),
            C_serialize_wall=summary([(r['serialize_return_mono_ns']-r['serialize_begin_mono_ns'])/1e6 for r in cc]),
            C_callback_wall=summary([(r['callback_end_mono_ns']-r['callback_entry_mono_ns'])/1e6 for r in cc]),
            R_decode_wall=summary([(r['decode_end_mono_ns']-r['mono_ns'])/1e6 for r in rr]),
            R_guard_call_wall=summary([(r['guard_end_mono_ns']-r['decode_end_mono_ns'])/1e6 for r in rr]))
    worst = sorted(pairs,key=lambda r:r['raw_return_to_C_entry_ms'],reverse=True)[:6]
    for row in worst:
        begin,end = row['raw_publish_end_mono_ns'],row['C_callback_entry_mono_ns']
        row['overlapping_longspans'] = [s for s in spans if s['begin_monotonic_ns']<end and s['end_monotonic_ns']>begin]
    longest = {}
    for span in spans:
        if span['stage'] not in longest or span['wall_ms']>longest[span['stage']]['wall_ms']:
            longest[span['stage']] = span
    control = gateway.get('clock_control_trace',{}).get('events',[])
    queue_stats = {}
    for flow in (31,51,71):
        frames = [r for r in control if r.get('kind')=='health_frame' and r.get('flow')==flow]
        queue_stats[str(flow)] = dict(queued=len(frames),flushed=sum('socket_frame_flushed_monotonic_ns' in r for r in frames),
            queue_to_kernel_flush=summary([(r['socket_frame_flushed_monotonic_ns']-r['queued_monotonic_ns'])/1e6 for r in frames if 'socket_frame_flushed_monotonic_ns' in r]))
    clock_frames = [r for r in control if r.get('kind')=='clock_frame' and r.get('operation')=='clock']
    returns = {r['horizon_ns']:r['monotonic_ns'] for r in control if r.get('kind')=='clock_return_received'}
    return dict(case=str(case.resolve()),mode=gateway['mode'],gateway_failure=gateway['failure'],
        scope='Independent no-motion P1 source; no real SLAM/Nav2/Policy/Goal/89/95; guards unarmed',
        source_peer_trace_rows=len(sources),by_flow=by_flow,longest_by_stage=longest,
        largest_non_poll_parent_spans=sorted([r for r in spans if r['stage'] not in ('poll_inclusive','progress_inclusive')],key=lambda r:r['wall_ms'],reverse=True)[:12],
        worst_source_return_to_C_pairs=worst,aggregate_profile=gateway['dispatch_cpu_profile']['aggregates'],
        health_frame_queue=queue_stats,
        STEP_queue_to_actual_ACK=summary([(returns[r['horizon_ns']]-r['queued_monotonic_ns'])/1e6 for r in clock_frames if r['horizon_ns'] in returns]),
        interpretation='Only same-host mono intervals; no ns3 airtime inference. Inclusive parent/child spans must not be summed. Wall-threadCPU is not proof of I/O/OS cause. No profile/receipt extrapolation to full load.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    result = analyze(args.case)
    with args.out.open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('aggregate_profile','worst_source_return_to_C_pairs')},indent=2))


if __name__=='__main__':
    main()

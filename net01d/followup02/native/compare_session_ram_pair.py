"""One offline registered pair comparison; no imports that start a model."""
from collections import Counter
from itertools import zip_longest
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
OUT=BASE/'native/session-ram-pair-01'


def load(path):
    with path.open() as stream:return json.load(stream)


def time_v(path):
    text=path.read_text();lines=text.splitlines()
    def value(prefix):return next(r.strip().rsplit(': ',1)[1] for r in lines if r.strip().startswith(prefix))
    elapsed=value('Elapsed (wall clock) time')
    wall=0.
    for part in elapsed.split(':'):wall=wall*60+float(part)
    user=float(value('User time (seconds)'));system=float(value('System time (seconds)'))
    return dict(user_s=user,system_s=system,CPU_s=user+system,wall_s=wall,
        peak_RSS_KiB=int(value('Maximum resident set size')),exit=int(value('Exit status')),
        scope='GNU time runner+waited subtree, includes native END persistence/Hub copy/runner analysis; CPU rounded to0.01s; peak RSS is wait4 child maximum, not simultaneous aggregate subtree RSS.')


arms={}
for arm,name in (('reference','ntcp-ram-r1'),('candidate','ntcp-ram-c1')):
    run=BASE/'runs'/name;folder=OUT/arm
    wrapper=load(folder/'wrapper-result.json');result=load(run/'result.json')
    hub=result['raw_Hub_result'];status=load(run/'hub/native/ledger-status.json')
    with (run/'hub/native/control-step-trace.jsonl').open() as stream:steps=[json.loads(line) for line in stream]
    run_cpu=sum(r['end_thread_cpu_ns']-r['begin_thread_cpu_ns'] for r in steps)
    run_wall=sum(r['end_monotonic_ns']-r['begin_monotonic_ns'] for r in steps)
    arms[arm]=dict(run=run,wrapper=wrapper,result=result,hub=hub,ledger_status=status,
        time=time_v(folder/'time-v.txt'),Run=dict(step_count=len(steps),CPU_ns=run_cpu,wall_ns=run_wall,
            scope='Original per-STEP begin/end owning-thread CPU and mono spans around Run plus boundary diagnostics; excludes END/ledger.finish.'),
        native_model_CPU_at_ledger_status_ns=status['model_cpu_ns'],
        outside_Run_CPU_to_ledger_status_ns=status['model_cpu_ns']-run_cpu,
        copy_wall_s=hub['native_evidence_storage']['copy_wall_s'],
        mode_argv=hub['argv'],Hub_argv=load(run/'argv.json'))

reference=arms['reference'];candidate=arms['candidate']
body_rows=[]
ref_rx={r['rpc_id']:r for r in reference['result']['received']}
can_rx={r['rpc_id']:r for r in candidate['result']['received']}
for rpc in sorted(set(ref_rx)|set(can_rx)):
    a=(reference['run']/'received'/f'{rpc}.bin').read_bytes()
    b=(candidate['run']/'received'/f'{rpc}.bin').read_bytes()
    body_rows.append(dict(rpc_id=rpc,reference_bytes=len(a),candidate_bytes=len(b),bytes_equal=a==b))

# The only new ledger reads: each arm is streamed once, in original row order.
ledger_counts={'reference':Counter(),'candidate':Counter()};mismatches=[];n=0
with (reference['run']/'hub/native/packet-ledger.jsonl').open() as left, (candidate['run']/'hub/native/packet-ledger.jsonl').open() as right:
    for n,(a,b) in enumerate(zip_longest(left,right),1):
        ra=None if a is None else json.loads(a);rb=None if b is None else json.loads(b)
        for arm,row in (('reference',ra),('candidate',rb)):
            if row is not None:
                ledger_counts[arm][row['kind']]+=1
                row.pop('monotonic_ns')
        if ra!=rb:
            if len(mismatches)<8:mismatches.append(dict(row=n,reference=ra,candidate=rb))
            else:mismatches[-1]['further_mismatches_present']=True

pcaps=[]
for node in range(4):
    filename=f'wifi-{node}-0.pcap'
    a=(reference['run']/'hub/native'/filename).read_bytes()
    b=(candidate['run']/'hub/native'/filename).read_bytes()
    pcaps.append(dict(file=filename,reference_bytes=len(a),candidate_bytes=len(b),bytes_equal=a==b))

status=candidate['ledger_status'];wrapper=candidate['wrapper'];deadline=wrapper['whole_deadline_monotonic_ns']
finalize=candidate['hub']['poststop_finalize']
build=load(BASE/'native/session-ram-build-02/BUILD_IDENTITY.json')
candidate_identity=dict(build_driver=build['driver'],actual_mapped_executable=wrapper['observation']['exe'],
    actual_native_argv=candidate['mode_argv'],actual_Hub_argv=candidate['Hub_argv'],
    path_matches_build=wrapper['observation']['exe']==build['driver']['path'],
    actual_session_RAM_argument='--ledgerMode=session-ram-v1' in candidate['mode_argv'],
    actual_status_mode=status.get('mode'),status_mode_correct=status.get('mode')=='session-ram-v1')
checks=dict(original_wrapper_PASS_both=all(a['wrapper']['status']=='PASS_LOADED_NATIVE_BYTE_SCOPE' for a in arms.values()),
    original_runner_checks_all=all(all(a['result']['checks'].values()) for a in arms.values()),
    submitted_18_equal=len(reference['result']['submitted'])==18 and reference['result']['submitted']==candidate['result']['submitted'],
    received_18_RPC_set_equal=len(ref_rx)==18 and set(ref_rx)==set(can_rx),
    all_18_bodies_exact=len(body_rows)==18 and all(r['bytes_equal'] for r in body_rows),
    ledger_115895_rows_both=all(sum(v.values())==115895 for v in ledger_counts.values()),
    all_ledger_rows_equal_except_wall_mono=not mismatches,
    ledger_kind_counts_equal=ledger_counts['reference']==ledger_counts['candidate'],
    all_four_PCAPS_exact=all(r['bytes_equal'] for r in pcaps),
    candidate_actual_r2_path_and_mode=candidate_identity['path_matches_build'] and candidate_identity['actual_session_RAM_argument'] and candidate_identity['status_mode_correct'],
    candidate_reserved_capacity32M=status['pending_capacity_records']==status['reserved_capacity_records']==32_000_000,
    candidate_complete_RAM_accounting=status['attempted']==status['captured']==status['written']==115895 and not status['failed'],
    candidate_owned_capacity_within8GiB=status['owned_capacity_bytes']<=status['owned_capacity_limit_bytes']==8_589_934_592,
    whole60_pass_both=all(a['wrapper']['whole_deadline_met'] and a['time']['exit']==0 for a in arms.values()),
    candidate_same_absolute_deadline=(finalize['deadline_monotonic_ns']==deadline==candidate['result']['finalize_hard_deadline_ns']
        and finalize['deadline_monotonic_ns']==min(finalize['END_monotonic_ns']+90_000_000_000,deadline)),
    candidate_Hub_finalize_PASS=candidate['hub']['status']=='PASS' and 'error' not in candidate['hub'] and not finalize.get('completion_deadline_missed',False))

def delta(key):
    a,b=reference['time'][key],candidate['time'][key]
    return dict(reference=a,candidate=b,change=b-a,change_percent=100*(b-a)/a)

summary=dict(status='PASS_FIXED_NATIVE_EQUIVALENCE' if all(checks.values()) else 'FAIL',checks=checks,
    candidate_identity=candidate_identity,body_comparison=body_rows,
    ledger_comparison=dict(reads_per_arm=1,rows_per_arm={k:sum(v.values()) for k,v in ledger_counts.items()},
        only_ignored_field='monotonic_ns',event_order_ns3_values_all_compared=True,kind_counts={k:dict(v) for k,v in ledger_counts.items()},first_mismatches=mismatches),
    PCAP_comparison=pcaps,
    Run={k:a['Run'] for k,a in arms.items()},
    Run_CPU_change_percent=100*(candidate['Run']['CPU_ns']-reference['Run']['CPU_ns'])/reference['Run']['CPU_ns'],
    whole_time_v={k:a['time'] for k,a in arms.items()},whole_CPU_s=delta('CPU_s'),whole_wall_s=delta('wall_s'),peak_RSS_KiB=delta('peak_RSS_KiB'),
    native_CPU_to_ledger_status={k:dict(model_CPU_ns=a['native_model_CPU_at_ledger_status_ns'],outside_Run_CPU_ns=a['outside_Run_CPU_to_ledger_status_ns']) for k,a in arms.items()},
    outside_Run_CPU_semantics='Total native owning-thread CPU sampled after ledger.finish minus measured Run; includes startup/IPC/END work, not isolated END CPU and excludes subsequent ledger-status/native-summary writes.',
    RAM_actual_status=status,reference_ledger_status=reference['ledger_status'],
    copy_wall_s={k:a['copy_wall_s'] for k,a in arms.items()},
    finalize=dict(candidate=finalize,absolute_whole_deadline_ns=deadline,
        candidate_end_to_absolute_deadline_s=(deadline-finalize['END_monotonic_ns'])/1e9,
        candidate_END_to_whole_subtree_exit_wall_s=(wrapper['subtree_exit_monotonic_ns']-finalize['END_monotonic_ns'])/1e9,
        candidate_END_to_observer_acceptance_wall_s=(wrapper['acceptance_monotonic_ns']-finalize['END_monotonic_ns'])/1e9,
        semantics='END90 clipped by the same new whole60, not a fresh90/60. Subtree/acceptance includes persistence/copy/runner analysis; no isolated ledger-finish wall marker. Synchronous-I/O completion acceptance, not hard real-time syscall guarantee.'),
    proof_paths={k:str(OUT/k/'wrapper-result.json') for k in arms},
    caveats=['Single fixed pair, not a CPU benchmark distribution or a ROS/Gazebo/300ms qualification.',
        'Wall monotonic capture point for primitive rows is earlier in RAM mode; actual wall stamps excluded, all model values/order retained.',
        'Actual RAM peak records and conservative reserved/owned byte accounting are different from RSS; GNU time maximum is not aggregate concurrent RSS.',
        'Run savings alone cannot erase END costs; whole subtree totals include final persistence/copy/analysis.'],
    new_model_starts_during_analysis=0)
with (OUT/'comparison.json').open('x') as stream:json.dump(summary,stream,indent=2);stream.write('\n')
print(json.dumps({k:summary[k] for k in ('status','checks','Run','Run_CPU_change_percent','whole_CPU_s','whole_wall_s','peak_RSS_KiB','copy_wall_s','finalize')},indent=2))

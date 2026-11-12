"""One registered fixed-pair offline comparison; no model imports or starts."""
from collections import Counter
from itertools import zip_longest
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
OUT=BASE/'native/copy-pair-01'
def load(p):return json.load(p.open())
def time_v(p):
    lines=p.read_text().splitlines()
    def value(prefix):return next(x.strip().rsplit(': ',1)[1] for x in lines if x.strip().startswith(prefix))
    wall=0.
    for part in value('Elapsed (wall clock) time').split(':'):wall=wall*60+float(part)
    u=float(value('User time (seconds)'));s=float(value('System time (seconds)'))
    return dict(user_s=u,system_s=s,CPU_s=u+s,wall_s=wall,peak_RSS_KiB=int(value('Maximum resident set size')),exit=int(value('Exit status')))

arms={}
for arm,name in [('reference','ntcp-copy-r1'),('candidate','ntcp-copy-c1')]:
    run=BASE/'runs'/name;folder=OUT/arm;steps=[]
    with (run/'hub/native/control-step-trace.jsonl').open() as f:
        for line in f:steps.append(json.loads(line))
    status=load(run/'hub/native/ledger-status.json')
    cpu=sum(x['end_thread_cpu_ns']-x['begin_thread_cpu_ns'] for x in steps)
    wall=sum(x['end_monotonic_ns']-x['begin_monotonic_ns'] for x in steps)
    arms[arm]=dict(run=run,wrapper=load(folder/'wrapper-result.json'),result=load(run/'result.json'),
        ledger_status=status,Run=dict(steps=len(steps),CPU_ns=cpu,wall_ns=wall),
        native_total_CPU_ns=status['model_cpu_ns'],outside_Run_CPU_ns=status['model_cpu_ns']-cpu,
        time=time_v(folder/'time-v.txt'))
a,b=arms['reference'],arms['candidate'];body=[]
ra={x['rpc_id']:x for x in a['result']['received']};rb={x['rpc_id']:x for x in b['result']['received']}
for rpc in sorted(set(ra)|set(rb)):
    left=(a['run']/'received'/f'{rpc}.bin').read_bytes();right=(b['run']/'received'/f'{rpc}.bin').read_bytes()
    keys=('kind','sender','receiver','flow','message_id','source_stamp_ns','ns3_rx_ns','bytes','rpc_id','body_bytes','actual_body_sha256','exact_body_route_source_equal')
    body.append(dict(rpc_id=rpc,bytes_equal=left==right,reference_bytes=len(left),candidate_bytes=len(right),
        route_identity_source_native_stamp_equal=all(ra[rpc][k]==rb[rpc][k] for k in keys)))
counts={k:Counter() for k in arms};mismatches=[];mismatch_count=0;rows=0;ingress_bytes={k:0 for k in arms}
with (a['run']/'hub/native/packet-ledger.jsonl').open() as f,(b['run']/'hub/native/packet-ledger.jsonl').open() as h:
    for rows,(left,right) in enumerate(zip_longest(f,h),1):
        x=None if left is None else json.loads(left);y=None if right is None else json.loads(right)
        for arm,row in [('reference',x),('candidate',y)]:
            if row is not None:
                counts[arm][row['kind']]+=1
                if row['kind']=='ipc_ingress':ingress_bytes[arm]+=row['body_bytes']
                row.pop('monotonic_ns')
        if x!=y:
            mismatch_count+=1
            if len(mismatches)<8:mismatches.append(dict(row=rows,reference=x,candidate=y))
pcaps=[]
for node in range(4):
    name=f'wifi-{node}-0.pcap';left=(a['run']/'hub/native'/name).read_bytes();right=(b['run']/'hub/native'/name).read_bytes()
    pcaps.append(dict(file=name,reference_bytes=len(left),candidate_bytes=len(right),bytes_equal=left==right))
checks=dict(original_wrapper_PASS_both=all(x['wrapper']['status']=='PASS_LOADED_NATIVE_BYTE_SCOPE' for x in arms.values()),
    original_stream_checks_PASS_both=all(all(x['result']['checks'].values()) for x in arms.values()),
    exactly18_submitted_equal=len(a['result']['submitted'])==18 and a['result']['submitted']==b['result']['submitted'],
    exactly18_received_RPC_set=len(ra)==18 and set(ra)==set(rb),all18_actual_body_and_route_source_identity_equal=len(body)==18 and all(x['bytes_equal'] and x['route_identity_source_native_stamp_equal'] for x in body),
    full_ordered_ledger_equal_except_monotonic=mismatch_count==0,ledger_rows_115895_both=all(sum(x.values())==115895 for x in counts.values()),
    kind_counts_equal=counts['reference']==counts['candidate'],all4_PCAP_exact=all(x['bytes_equal'] for x in pcaps),
    serial_complete_native_END_both=all(not x['ledger_status']['async'] and not x['ledger_status']['failed'] and x['ledger_status']['attempted']==x['ledger_status']['captured']==x['ledger_status']['written']==115895 for x in arms.values()) and all(x['transport_end']==1 for x in counts.values()),
    actual_ELF_and13DSO_same_root_both=all(all(x['wrapper']['observation'][k] for k in ('exact13_names','all_in_expected_root','exact_native_executable','native_parent_is_Hub','actual_time_root_in_chain')) for x in arms.values()),
    no_force_or_owned_survivors=all(not x['wrapper']['remaining_observed_owned'] and not x['result']['resources']['forced_signals'] and not x['result']['resources']['remaining_owned_native'] for x in arms.values()),
    whole_GNUtime_exit0_both=all(x['time']['exit']==0 for x in arms.values()))
def delta(ref,can):return dict(reference=ref,candidate=can,change=can-ref,change_percent=100*(can-ref)/ref)
summary=dict(status='PASS_FIXED_NATIVE_EQUIVALENCE' if all(checks.values()) else 'FAIL',checks=checks,
    ledger_comparison=dict(reads_per_arm=1,rows_per_arm={k:sum(v.values()) for k,v in counts.items()},only_ignored_field='monotonic_ns',all_other_fields_and_order_compared=True,mismatch_count=mismatch_count,first_mismatches=mismatches,kind_counts={k:dict(v) for k,v in counts.items()}),
    body_comparison=body,PCAP_comparison=pcaps,total_ipc_ingress_body_bytes=ingress_bytes,
    native_total_CPU_ns=delta(a['native_total_CPU_ns'],b['native_total_CPU_ns']),
    Run={k:v['Run'] for k,v in arms.items()},Run_CPU_ns=delta(a['Run']['CPU_ns'],b['Run']['CPU_ns']),Run_wall_ns=delta(a['Run']['wall_ns'],b['Run']['wall_ns']),
    outside_Run_CPU_ns=delta(a['outside_Run_CPU_ns'],b['outside_Run_CPU_ns']),
    whole_GNU_time={k:v['time'] for k,v in arms.items()},whole_CPU_s=delta(a['time']['CPU_s'],b['time']['CPU_s']),whole_wall_s=delta(a['time']['wall_s'],b['time']['wall_s']),
    ledger_status={k:v['ledger_status'] for k,v in arms.items()},
    actual_identity={k:dict(native_pid=v['wrapper']['observation']['native']['pid'],exe=v['wrapper']['observation']['exe'],Hub_pid=v['result']['resources']['hub_pid'],remaining=v['wrapper']['remaining_observed_owned']) for k,v in arms.items()},
    CPU_semantics='native model_cpu_ns is owning-thread elapsed CPU sampled at ledger status after finish: includes TX outsideRun/startup/END, excludes subsequent status/summary output. Run is perSTEP sum, not total model CPU. OutsideRun difference is not isolated TX CPU. WholeGNUtime includes runner/Hub/native/copy/summary; CPU rounded0.01s and maximum RSS is child maximum, not aggregate.',
    conclusion='Single fixed pair semantic identity scope only. No demonstrated native-total CPU benefit in this observation; no performance promotion or Full/Gazebo authorization inferred.',
    caveats=['One pair is not a benchmark distribution. Small fixed TX volume may be below observable wall/CPU variance.','Allocator/cache trajectories differ while actual ordered simulation events/PacketUIDs/fourPCAPs agree for this fixture.','Opaque fixture bodies are not real ROS CDR or physical/Policy/Nav2 qualification.'],new_model_starts_during_analysis=0)
with (OUT/'comparison.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
print(json.dumps({k:summary[k] for k in ('status','checks','total_ipc_ingress_body_bytes','native_total_CPU_ns','Run_CPU_ns','Run_wall_ns','outside_Run_CPU_ns','whole_CPU_s','whole_wall_s','actual_identity','conclusion')},indent=2))

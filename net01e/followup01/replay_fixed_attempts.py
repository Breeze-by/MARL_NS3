"""One fixed-attempt transport case; no ROS, Action generation or robot publisher."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'net01'))
from hub_client import HubClient
from host_run import capture_native_load

QUANTUM = 10_000_000
WALL_PERIOD = 20_000_000
END = 15_000_000_000


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('x') as stream:json.dump(value, stream, indent=2); stream.write('\n')
    temporary.replace(path)


def percentile95(values):
    return sorted(values)[math.ceil(.95*len(values))-1] if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('A1','B','C'), required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ram', type=Path, required=True)
    args = parser.parse_args(); args.output = args.output.resolve()
    manifest = json.loads((args.corpus/'manifest.json').read_text())
    rows = [json.loads(line) for line in (args.corpus/'attempts.jsonl').open()]
    bodies = (args.corpus/'bodies.bin').read_bytes()
    if (manifest['selected_attempts']!=len(rows) or manifest['body_bytes']!=len(bodies)
            or manifest['prewarm_native_ns']!=3_000_000_000
            or manifest['main_native_duration_ns']!=10_000_000_000
            or manifest['proposed_drain_native_ns']!=2_000_000_000):
        raise ValueError('Corpus does not match the fixed admitted schedule')
    previous = -1
    for index,row in enumerate(rows):
        due = row['native_admission_ns']
        if row['replay_ordinal']!=index or not previous<=due<13_000_000_000 or due<3_000_000_000:
            raise ValueError('Attempt ordinal/due order invalid; do not sort or shift it')
        previous = due
        row.update(state='PLANNED', clock_return_confirmed=False, received=None)
    args.output.mkdir(parents=True, exist_ok=False)
    atomic_json(args.output/'input-manifest.json',manifest)
    config = json.loads((REPO/'net01d/followup04/requests/gz-simhealth-b1-02.ready.json').read_text())['network']
    native = Path(config['native_identity']['binary']['relative_phase'])
    libraries = Path(config['native_runtime']['library_directory'])
    env = dict(os.environ,LD_LIBRARY_PATH=str(libraries))
    for name in ('LD_PRELOAD','LD_AUDIT'):env.pop(name,None)
    began = time.monotonic_ns(); active_deadline = began+55_000_000_000; whole_deadline = began+60_000_000_000
    result = dict(arm=args.arm,status='FAIL',corpus=str(args.corpus),planned=len(rows),
        logical_quantum_ns=QUANTUM,planned_wall_period_ns=WALL_PERIOD,
        prewarm_native_ns=3_000_000_000,main_end_native_ns=13_000_000_000,cutoff_native_ns=END,
        active_deadline_monotonic_ns=active_deadline,whole_deadline_monotonic_ns=whole_deadline,
        scope='Fixed logical send-attempt transport only; no live Action/ROS/Gateway cost, policy, trajectory or physical safety claim',
        positions='Unmodified NETWORK_LOCK_V3 static prototype positions; no position commands',
        attempt_admission_kind='ideal-local-with-real-clock' if args.arm=='A1' else 'actual-Hub-native-SENDAT',
        AoI='NOT_MEASURED',
        AoI_scope='Only native transport admission-to-RX delay. Original CDR/header epochs unchanged; no real state freshness, ROS consumer receipt or end-to-end Action age is measured.',
        reactive_attempts_generated=0,forced=[],error=None)
    clock_returns=[]
    hub = client = None; load = None; next_row = 0; active_cpu_begin = None
    def interrupted(signum,frame):raise InterruptedError('External fixed-attempt hard bound')
    signal.signal(signal.SIGTERM,interrupted)
    def body(row):
        data=bodies[row['body_offset']:row['body_offset']+row['body_bytes']]
        if len(data)!=row['body_bytes']:raise ValueError('Sealed body extent truncated')
        return data
    def receive(meta,data,rpc):
        sink_entry=time.monotonic_ns()
        mid=meta['message_id']
        if not 1<=mid<=len(rows):raise ValueError('Unknown actual native message_id')
        row=rows[mid-1]
        if (row['received'] is not None or meta['sender']!=row['sender'] or meta['receiver']!=row['receiver']
                or meta['flow']!=row['flow'] or rpc!=row['rpc_id']
                or meta['source_stamp_ns']!=row['source_stamp_ns'] or data!=body(row)):
            raise ValueError('Actual native receive changed route/RPC/source/body or duplicated message_id')
        delay=meta['ns3_rx_ns']-row['native_admission_ns']
        if delay<0:raise ValueError('Actual native receive precedes scheduled admission')
        validation_return=time.monotonic_ns()
        row['received']=dict(meta,backend='actual-native-RX',rpc_id=rpc,
            replay_ordinal=row['replay_ordinal'],source_ordinal=row['source_ordinal'],
            complete_body_equal=True,transport_delay_ns=delay,within_cutoff=meta['ns3_rx_ns']<=END,
            sink_callback_entry_monotonic_ns=sink_entry,sink_validation_return_monotonic_ns=validation_return)
    def pump(until):
        if time.monotonic_ns()>=until:raise TimeoutError('Actual clock ACK/active deadline exceeded')
        if hub.poll() is not None:raise RuntimeError('Owned Hub exited before complete sequence')
        return client.poll()
    out=(args.output/'hub.stdout').open('xb');err=(args.output/'hub.stderr').open('xb')
    try:
        native_bytes=native.read_bytes()
        actual_native_sha=hashlib.sha256(native_bytes).hexdigest()
        expected_native_sha=config['native_identity']['binary']['sha256']
        result['native_executable_identity']=dict(path=str(native),bytes=len(native_bytes),
            expected_sha256=expected_native_sha,actual_sha256=actual_native_sha,
            matches=actual_native_sha==expected_native_sha,hashed_files=1)
        del native_bytes
        if actual_native_sha!=expected_native_sha:raise ValueError('Reviewed native executable SHA changed')
        address=args.output/'wire.sock'
        command=[sys.executable,'-B',str(REPO/'net01/tools/packet_hub.py'),'--socket',str(address),
            '--native',str(native),'--output',str(args.output/'hub'),'--profile','C' if args.arm=='C' else 'B',
            '--native-transport','tcp-mtu-v2','--wall','60','--clock-source','gazebo',
            '--control-trace','--native-evidence-ram',str(args.ram)]
        result['hub_argv']=command
        hub=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True,env=env)
        result['hub_pid']=hub.pid
        startup=min(active_deadline,time.monotonic_ns()+10_000_000_000)
        while not address.exists():
            if hub.poll() is not None or time.monotonic_ns()>=startup:raise TimeoutError('Hub startup did not complete')
            time.sleep(.001)
        # Reuse the actual ELF/13DSO identity gate before any business attempt.
        load=capture_native_load(hub,native,libraries,config['native_runtime']['expected_ns3_names'],args.output)
        result['native_load']=load
        client=HubClient(address);client.receive=receive
        while not client.ready:pump(startup)
        grid=time.monotonic_ns();result['clock_grid_origin_monotonic_ns']=grid
        active_cpu_begin=time.thread_time_ns()
        result['active_thread_cpu_begin_ns']=active_cpu_begin
        for number,horizon in enumerate(range(QUANTUM,END+1,QUANTUM),1):
            planned=grid+number*WALL_PERIOD
            while time.monotonic_ns()<planned:
                remaining=min((planned-time.monotonic_ns())/1e9,.001)
                if remaining>0:time.sleep(remaining)
                pump(active_deadline)
            if time.monotonic_ns()>=active_deadline:raise TimeoutError('55wall active bound')
            client.observed_clock(horizon);begin=next_row
            while next_row<len(rows) and rows[next_row]['native_admission_ns']<=horizon:
                row=rows[next_row];row['queue_monotonic_ns']=time.monotonic_ns()
                if row['native_admission_ns']<client.horizon_ns:raise ValueError('Would inject an attempt into the past')
                row['state']='QUEUED_UNCONFIRMED'
                if args.arm=='A1':
                    # Explicit ideal reference, not a fabricated native delivery.
                    row['received']=dict(backend='ideal-local-reference',actual_native_RX=False,
                        modeled_logical_receipt_ns=row['native_admission_ns'],endpoint_receive_monotonic_ns=time.monotonic_ns(),
                        modeled_exact_input_body=True,opaque_body_bytes=len(body(row)),
                        modeled_transport_delay_ns=0,within_cutoff=True)
                else:
                    row['native_message_id']=next_row+1
                    client.send(row['sender'],row['receiver'],row['flow'],body(row),row['rpc_id'],
                        source_stamp_ns=row['source_stamp_ns'],admission_ns=row['native_admission_ns'])
                next_row+=1
            issue=time.monotonic_ns();client.clock(horizon)
            until=min(active_deadline,issue+2_000_000_000)
            while client.horizon_ns<horizon:pump(until)
            if client.horizon_ns!=horizon:raise ValueError('Unexpected native clock return')
            for row in rows[begin:next_row]:row.update(state='ADMITTED',clock_return_confirmed=True)
            clock_returns.append(dict(horizon_ns=horizon,planned_monotonic_ns=planned,
                issue_monotonic_ns=issue,return_monotonic_ns=time.monotonic_ns(),lateness_ns=max(0,issue-planned)))
        if next_row!=len(rows):raise ValueError('Full fixed sequence not admitted before cutoff')
        result['active_complete']=True
    except BaseException as error:
        result['error']=repr(error);result['exception_trace']=traceback.format_exc()
    finally:
        if active_cpu_begin is not None:
            active_end=time.monotonic_ns();active_cpu_end=time.thread_time_ns()
            result.update(active_thread_cpu_end_ns=active_cpu_end,
                active_thread_cpu_ns=active_cpu_end-active_cpu_begin,active_end_monotonic_ns=active_end,
                active_wall_ns=active_end-grid,
                active_thread_cpu_scope='Two thread CPU samples: clock-grid origin through final ACK/active exception, before END/teardown/persistence; includes pacing, IPC and validation only, no ROS cost.')
        if client is not None:
            try:
                client.finish_poststop(min(time.monotonic_ns()+3_000_000_000,whole_deadline))
            except (EOFError,ConnectionError,OSError) as error:
                result.setdefault('shutdown_errors',[]).append(repr(error))
                result['error']=result['error'] or repr(error)
            finally:
                result['hub_shutdown']=client.finish_state
                (args.output/'poststop-opaque.bin').write_bytes(client.finish_tail)
                client.close()
        if hub is not None:
            try:result['hub_exit']=hub.wait(timeout=max(0,(whole_deadline-time.monotonic_ns())/1e9))
            except subprocess.TimeoutExpired:
                result['error']=result['error'] or 'Whole60wall Hub exit bound exceeded'
                result['forced'].append('SIGKILL_owned_Hub_group');os.killpg(hub.pid,signal.SIGKILL)
                result['hub_exit']=hub.wait()
        out.close();err.close()
    hub_result=args.output/'hub/result.json'
    result['actual_Hub_result']=json.loads(hub_result.read_text()) if hub_result.exists() else None
    result['known_native_PID_gone']=(load is not None and not (Path('/proc')/str(load['pid'])).exists())
    result['known_Hub_PID_gone']=(hub is not None and hub.poll() is not None)
    valid_hub=result['actual_Hub_result']
    ingress_path=args.output/'hub/hub-ingress.json'; ingress_mapping=[]
    result['ingress_identity_scope']='Hub ingress has metadata only: no body hash or RPC. Full CDR/RPC equality is independently checked only for actually received attempts, not missing packets.'
    try:
        # Actual Hub has exited: exactly one read of its existing ingress ledger.
        ingress=json.loads(ingress_path.read_text())
        expected_count=0 if args.arm=='A1' else len(rows)
        for index,actual in enumerate(ingress):
            row=rows[index] if args.arm!='A1' and index<len(rows) else None
            equal=(row is not None and actual['native_message_id']==index+1
                and actual['sender']==row['sender'] and actual['receiver']==row['receiver']
                and actual['flow']==row['flow'] and actual['source_stamp_ns']==row['source_stamp_ns']
                and actual['admission_ns']==row['native_admission_ns'] and actual['bytes']==row['body_bytes']+8)
            mapping=dict(actual=actual,metadata_equal=equal,
                replay_ordinal=None if row is None else row['replay_ordinal'],
                source_ordinal=None if row is None else row['source_ordinal'],
                expected_rpc_id_not_measured_at_ingress=None if row is None else row['rpc_id'],
                expected_cdr_sha256_not_measured_at_ingress=None if row is None else row['cdr_sha256'])
            ingress_mapping.append(mapping)
            if row is not None:row['actual_Hub_ingress']=mapping
        result['actual_ingress_count']=len(ingress)
        result['expected_ingress_count']=expected_count
        result['ingress_mapping_matches_corpus_order']=(len(ingress)==expected_count
            and all(entry['metadata_equal'] for entry in ingress_mapping))
        if not result['ingress_mapping_matches_corpus_order']:
            raise ValueError('Actual Hub ingress count/metadata/order differs from fixed attempts')
    except Exception as error:
        result['ingress_mapping_matches_corpus_order']=False
        result['ingress_mapping_error']=repr(error)
        result['error']=result['error'] or repr(error)
    with (args.output/'hub-ingress-mapping.jsonl').open('x') as stream:
        for entry in ingress_mapping:stream.write(json.dumps(entry)+'\n')
    counts=Counter();latency=[]
    for row in rows:
        key=f"{row['sender']}->{row['receiver']}/flow{row['flow']}"
        counts[(key,'planned')]+=1
        if row['clock_return_confirmed']:counts[(key,'admitted')]+=1
        if row['received'] is not None:
            counts[(key,'delivered_by_cutoff')]+=int(row['received']['within_cutoff'])
            if args.arm!='A1':latency.append(row['received']['transport_delay_ns'])
        row['cutoff_outcome']=('NOT_ADMITTED' if not row['clock_return_confirmed'] else
            'DELIVERED_BY_CUTOFF' if row['received'] and row['received']['within_cutoff'] else 'NOT_DELIVERED_AT_CUTOFF')
    result['outcomes']=dict(Counter(row['cutoff_outcome'] for row in rows))
    result['per_flow_direction']={key:{kind:counts[(key,kind)] for kind in ('planned','admitted','delivered_by_cutoff')}
        for key in sorted({key for key,kind in counts})}
    result['native_transport_delay_p95_ns']=percentile95(latency)
    result['percentile_method']='Empirical nearest-rank; only actual received attempts, not missing-at-cutoff'
    result['planned_grid_lateness_max_ns']=max((r['lateness_ns'] for r in clock_returns),default=None)
    result['clock_returns_count']=len(clock_returns)
    result['all_source_attempts_admitted']=next_row==len(rows) and all(row['clock_return_confirmed'] for row in rows)
    result['wall_s']=(time.monotonic_ns()-began)/1e9
    if (result['error'] is None and result.get('active_complete') and result['all_source_attempts_admitted']
            and result.get('hub_exit')==0 and valid_hub and valid_hub['status']=='PASS'
            and valid_hub['native_exit']==0 and result['hub_shutdown']['peer_eof']
            and valid_hub['ingress_messages']==(0 if args.arm=='A1' else len(rows))
            and result['ingress_mapping_matches_corpus_order']
            and result['known_native_PID_gone'] and result['known_Hub_PID_gone'] and result['wall_s']<60):
        result['status']='PASS_COMPLETE_SEQUENCE_AND_CLEAN_EXIT_NOT_ALL_DELIVERY_OR_RF_LOSS_PASS'
    with (args.output/'attempt-outcomes.jsonl').open('x') as stream:
        for row in rows:stream.write(json.dumps(row)+'\n')
    with (args.output/'clock-returns.jsonl').open('x') as stream:
        for clock in clock_returns:stream.write(json.dumps(clock)+'\n')
    result['wall_s']=(time.monotonic_ns()-began)/1e9
    if time.monotonic_ns()>=whole_deadline:
        result['error']=result['error'] or 'Whole60wall persistence bound exceeded';result['status']='FAIL'
    atomic_json(args.output/'result.json',result)
    return 0 if result['error'] is None and result['status'].startswith('PASS_') else 1


if __name__=='__main__':raise SystemExit(main())

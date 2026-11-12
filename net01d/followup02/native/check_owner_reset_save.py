"""One no-ROS owner-reset evidence test; not a performance qualification."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(REPO),str(REPO/'net01')]
from hub_client import HubClient
from net01.tools.packet_hub import read_frame
from run_native_tcp import ROUTES,body_for,ledger_summary

BASE=REPO/'net01d/followup02'
LIBRARIES=REPO.parent/'ns3-lto-portable-followup02/build/lib'


async def main(native):
    output=BASE/'runs/owner-reset-save-01'
    ram=Path('/dev/shm/net01d-f02-owner-reset-save-01')
    if output.exists() or ram.exists():raise FileExistsError('Unique owner-reset case/RAM already exists')
    if not native.is_absolute() or not native.is_file():raise FileNotFoundError(native)
    if len(os.fsencode(output/'wire.sock'))>=108:raise ValueError('Owned Unix socket path too long')
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic_ns();deadline=started+60_000_000_000;active_deadline=started+20_000_000_000
    command=[sys.executable,'-B',str(REPO/'net01/tools/packet_hub.py'),
        '--socket',str(output/'wire.sock'),'--native',str(native),'--output',str(output/'hub'),
        '--profile','B','--native-transport','tcp-mtu-v2','--wall','25','--control-trace',
        '--native-evidence-ram',str(ram),'--native-ledger-mode','session-ram-v1',
        '--finalize-hard-deadline-ns',str(deadline)]
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(LIBRARIES)
    for key in ('LD_PRELOAD','LD_AUDIT'):env.pop(key,None)
    result=dict(status='NOT_STARTED',argv=command,started_monotonic_ns=started,
        active_wall_bound_s=20,whole_wall_bound_s=60,whole_deadline_monotonic_ns=deadline,
        scope='One ordinary owner-reset negative evidence-save test; no ROS/Policy/Nav2/Gazebo/RF fault or performance claim')
    (output/'argv.json').write_text(json.dumps(command,indent=2)+'\n')
    hub=None;client=None;writer=None;native_pid=None;reset_ns=None;issued=[];checks={};forced=[]
    stdout=(output/'hub.stdout.log').open('x');stderr=(output/'hub.stderr.log').open('x')
    def active_remaining():return max(0.,(active_deadline-time.monotonic_ns())/1e9)
    async def bounded(awaitable):return await asyncio.wait_for(awaitable,timeout=active_remaining())
    try:
        hub=subprocess.Popen(command,cwd=REPO,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        result['Hub_pid']=hub.pid
        while not (output/'wire.sock').exists():
            if hub.poll() is not None:raise RuntimeError('Hub exited before actual IPC listen')
            if active_remaining()==0:raise TimeoutError('Original20s active startup bound')
            await asyncio.sleep(.005)
        children=(Path('/proc')/str(hub.pid)/'task'/str(hub.pid)/'children').read_text().split()
        if len(children)!=1:raise RuntimeError('Expected one actual owned native child')
        native_pid=int(children[0]);result['native_pid']=native_pid
        result['actual_native_exe']=os.readlink(Path('/proc')/str(native_pid)/'exe')
        checks['actual_native_exe']=Path(result['actual_native_exe']).resolve()==native.resolve()
        client=HubClient(output/'wire.sock')
        reader,writer=await bounded(asyncio.open_unix_connection(sock=client.socket))
        ready,body=await bounded(read_frame(reader));checks['actual_IPC_READY']=ready['kind']=='ready' and not body
        expected={1000+i:body_for(1000+i,64) for i in range(len(ROUTES))};received={}
        for i,(sender,receiver) in enumerate(ROUTES):
            client.send(sender,receiver,500+i,expected[1000+i],1000+i,source_stamp_ns=0)
        async def flush():
            writer.write(bytes(client.outgoing));client.outgoing.clear();await bounded(writer.drain())
        async def clock(horizon):
            client.clock(horizon);issued.append(dict(horizon_ns=horizon,queued_monotonic_ns=time.monotonic_ns()))
            await flush()
        for horizon in range(10_000_000,4_000_000_001,10_000_000):
            await clock(horizon)
            while True:
                meta,body=await bounded(read_frame(reader))
                if meta is None:raise EOFError('Hub closed during original handshake progression')
                if meta['kind']=='clock_return':
                    if meta['horizon_ns']!=horizon:raise ValueError('Original native STEP ACK mismatch')
                    break
                if meta['kind']!='delivered':raise ValueError('Unexpected handshake response')
                rpc=struct.unpack('!Q',body[:8])[0]
                if rpc not in expected or body[8:]!=expected[rpc]:raise ValueError('Original small-body check failed')
                received[rpc]=received.get(rpc,0)+1
        checks['six_real_bidirectional_TCP_receives']=(received=={rpc:1 for rpc in expected})
        for rpc in (9001,9002):client.send(0,3,704,body_for(rpc,1024*1024),rpc,source_stamp_ns=4_000_000_000)
        horizon=4_000_000_000
        while horizon<8_000_000_000:
            horizon+=100_000_000;await clock(horizon)
            while True:
                header=await bounded(reader.readline())
                if not header:raise EOFError('No large response header before reset')
                meta=json.loads(header)
                if meta['kind']=='delivered' and meta['bytes']>=1024*1024:
                    result['large_header_before_reset']=meta
                    # Leave this large body unread. A short read-only probe may
                    # observe the second native stdout write blocked on its pipe.
                    probe_until=min(active_deadline,time.monotonic_ns()+500_000_000)
                    while time.monotonic_ns()<probe_until:
                        wchan=(Path('/proc')/str(native_pid)/'wchan').read_text().strip()
                        if 'pipe_write' in wchan:
                            result['native_pipe_write_observed']=wchan;break
                        await asyncio.sleep(.005)
                    reset_ns=time.monotonic_ns();result['owner_reset_monotonic_ns']=reset_ns
                    client.socket.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
                    writer.transport.abort();writer=None
                    break
                if meta['kind']=='clock_return' and meta['bytes']==0:break
                raise ValueError('Unexpected response before planned owner reset')
            if reset_ns is not None:break
        if reset_ns is None:raise TimeoutError('Large-header reset not reached within original active bounds')
        checks['reset_within20active']=(reset_ns<active_deadline)
    except Exception as error:
        result['first_test_error']=repr(error)
    finally:
        # Deliberately never send owner END. All later END is Hub evidence-only.
        if writer is not None:writer.transport.abort()
        elif client is not None:client.close()
        if hub is not None:
            while hub.poll() is None and time.monotonic_ns()<deadline:await asyncio.sleep(.01)
            if hub.poll() is None:
                os.killpg(hub.pid,signal.SIGKILL);forced.append('SIGKILL_OWNED_HUB_GROUP')
            result['Hub_exit']=hub.wait()
        stdout.close();stderr.close()
    result.update(issued_clocks=issued,forced=forced,wall_s=(time.monotonic_ns()-started)/1e9,
        native_remaining=native_pid is not None and Path('/proc',str(native_pid)).exists())
    hub_result=output/'hub/result.json'
    checks['Hub_result_saved']=hub_result.is_file()
    if hub_result.exists():
        raw=json.loads(hub_result.read_text());state=raw.get('error_finalize',{});event=raw.get('first_error_event',{})
        checks['Hub_still_FAIL_nonzero']=raw['status']=='FAIL' and result.get('Hub_exit') not in (None,0)
        checks['first_connection_error']=any(s in event.get('error','') for s in ('Connection','BrokenPipe'))
        checks['no_owner_END_and_one_evidence_END']=(state.get('owner_END_received') is False
            and state.get('prior_END_attempted') is False and state.get('evidence_END_attempted') is True
            and state.get('evidence_END_flushed_to_stdin') is True)
        checks['native_clean_exit_no_force']=raw.get('native_exit')==0 and not state.get('forced_native') and not forced
        tail=output/'hub/native.stdout-after-error.bin'
        checks['single_large_tail_saved_to_EOF']=(state.get('stdout_EOF') is True and not state.get('incomplete')
            and state.get('bytes_not_saved')==0 and state.get('bytes_write_returned',0)>=65536
            and tail.is_file() and tail.stat().st_size==state['bytes_write_returned'])
        checks['native_evidence_copy_complete']=raw.get('native_evidence_storage',{}).get('complete') is True
        native_dir=output/'hub/native'
        if (native_dir/'ledger-status.json').exists():
            status=json.loads((native_dir/'ledger-status.json').read_text())
            summary=ledger_summary(native_dir/'packet-ledger.jsonl')  # One reused original native-ledger pass.
            checks['native_END_and_full_captured_prefix']=(not status['failed']
                and status['attempted']==status['captured']==status['written']>0
                and summary['counts'].get('transport_end')==1)
            checks['only_pre_reset_authorized_steps_completed']=(status['final_ns3_ns']==issued[-1]['horizon_ns']
                and summary['counts'].get('horizon_return')==len(issued))
            result['native_ledger_status']=status;result['native_kind_counts']=summary['counts']
        trace=json.loads((output/'hub/hub-clock-control.json').read_text())
        ingress=json.loads((output/'hub/hub-ingress.json').read_text())
        checks['no_post_reset_business_or_STEP']=(reset_ns is not None and len(ingress)==8
            and all(x['hub_ingress_monotonic_ns']<reset_ns for x in ingress)
            and all(x['monotonic_ns']<reset_ns for x in trace if x['kind']=='hub_native_STEP_write'))
        result['Hub_error_subset']=dict(error=raw.get('error'),first_error_event=event,error_finalize=state)
    checks['no_owned_native_survivor']=not result['native_remaining']
    checks['whole60_acceptance']=time.monotonic_ns()<deadline
    result['checks']=checks
    result['status']=('PASS_OWNER_RESET_EVIDENCE_ONLY' if checks and all(checks.values())
        and 'first_test_error' not in result else 'FAIL')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],first_test_error=result.get('first_test_error'),
        Hub_exit=result.get('Hub_exit'),wall_s=result['wall_s'],checks=checks,evidence=str(output))),flush=True)
    return 0 if result['status']=='PASS_OWNER_RESET_EVIDENCE_ONLY' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--native',type=Path,required=True)
    args=parser.parse_args();raise SystemExit(asyncio.run(main(args.native)))

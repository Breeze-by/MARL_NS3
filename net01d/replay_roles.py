"""NET01D thin no-motion roles. ROS imports occur only in the selected role.

Independent source/Peer/Gateway processes; no direct health injection. The
original source is a synthetic-size/cadence approximation, not SLAM or physics.
"""
import argparse
import json
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[1]
# Required by Gateway's opt-in net01d.health.trace import inside the rootfs.
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/'net01'))
SESSION=2026110912  # Matches the reused controlled-time fixture owner.


def peer(directory,stop_file):
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from bound_peer import BoundPeer
    from net01d.health.trace import HealthTrace
    rclpy.init(domain_id=91,args=['--ros-args','-p','use_sim_time:=true'],
        signal_handler_options=SignalHandlerOptions.NO)
    scene=json.loads((REPO/'inputs/scenes/regression-corridor-common-6201-dwb-v1.json').read_text())
    node=BoundPeer(scene,directory,session_id=SESSION,health_trace=HealthTrace())
    next_check=0.
    try:
        while True:
            if time.monotonic()>=next_check:
                if stop_file.exists():break
                next_check=time.monotonic()+.05
            rclpy.spin_once(node,timeout_sec=.01)
    finally:
        try:
            node.restore_runtime_gc()
            node.persist_records()
        finally:
            node.destroy_node();rclpy.try_shutdown()


def gateway(directory,stop_file,mode,full_load=False,dds_take_trace=False):
    from gateway import Gateway
    node=Gateway(mode,directory.parent/'wire.sock',directory,SESSION,
        dispatch_profile=True,control_trace=True,
        execution_profile='controlled1000-clock100-q10ms',dds_take_trace=dds_take_trace)
    announced=False;next_check=0.;radio_off=False
    base=directory.parent
    def marker(name,data):
        path=base/name
        if not path.exists():
            with path.open('x') as stream:json.dump(data,stream)
    try:
        while True:
            if time.monotonic()>=next_check:
                if stop_file.exists():break
                next_check=time.monotonic()+.05
                if full_load:
                    status=node.last_status
                    negative=(base/'NEGATIVE_PHASE.json').exists()
                    faults={str(r):g.guard.fault for r,g in node.guards.items()}
                    if not negative and (node.failure or any(faults.values())):
                        marker('FIRST_FAILURE.json',dict(monotonic_ns=time.monotonic_ns(),
                            Gateway_failure=node.failure,guards=faults))
                    if ((base/'FIRST_FAILURE.json').exists()
                            and all(not g.owned and all(f.done() for f in g.futures)
                                for g in node.guards.values())
                            and all(any(row['kind']=='actual_local_pause_response' and row['success']
                                for row in g.records) for g in node.guards.values())):
                        marker('LOCAL_CLEANUP_DRAINED.json',dict(monotonic_ns=time.monotonic_ns(),
                            owned={str(r):sorted(g.owned) for r,g in node.guards.items()},
                            actions={str(r):g.records for r,g in node.guards.items()},
                            local_futures_pending=0,PAUSE_success=True,
                            scope='Actual local cleanup only; central wireless Futures may remain unknown'))
                    if status is not None and time.monotonic_ns()-status['gateway_monotonic_ns']<=300_000_000:
                        counts=status['actual_rpc_cleanup']
                        if ((base/'CLIENT_NORMAL_DONE.json').exists() and not negative
                                and not node.failure and not any(faults.values())
                                and all(g.guard.armed and not g.owned for g in node.guards.values())
                                and all(value==0 for value in counts.values())):
                            marker('RPC_DRAINED.json',status)
                        if (not negative and all(g.guard.armed and g.guard.fault is None
                                and len(g.accepted)==1 for g in node.guards.values())
                                and not node.failure
                                and all(value=={'C_pending':3,'R_pending':3,
                                    'C_service_inflight':3}.get(key,0) for key,value in counts.items())):
                            marker('ACTIVE_GOALS_READY.json',dict(monotonic_ns=time.monotonic_ns(),
                                accepted={str(r):sorted(g.accepted) for r,g in node.guards.items()},
                                actual_status=status))
                    if mode=='B' and (base/'RADIO_OFF').exists() and not radio_off:
                        node.record('fixture_request_actual_native_radio_off',enabled=False)
                        node.hub.radio_fault(False);radio_off=True
                    active=base/'NEGATIVE_ACTIVE_READY.json'
                    if not negative and active.exists() and status is not None:
                        uuid=json.loads(active.read_text())['uuid']
                        counts=status['actual_rpc_cleanup']
                        allowed={'C_pending':1,'R_pending':1,'C_service_inflight':1}
                        if (time.monotonic_ns()-status['gateway_monotonic_ns']<=300_000_000
                                and uuid in node.guards[3].accepted and not any(faults.values())
                                and not node.failure
                                and all(value==allowed.get(key,0) for key,value in counts.items())):
                            marker('NEGATIVE_TRANSPORT_READY.json',dict(uuid=uuid,
                                monotonic_ns=time.monotonic_ns(),actual_status=status,
                                scope='Original request ACKed; one legitimate remote GetResult pending'))
                    if negative and active.exists():
                        uuid=json.loads(active.read_text())['uuid']
                        terminal=any(row['kind']=='actual_local_GetResult' and row.get('uuid')==uuid
                            and row.get('status')==5 for row in node.guards[3].records)
                        pauses=all(any(row['kind']=='actual_local_pause_response' and row['success']
                            for row in g.records) for g in node.guards.values())
                        if (terminal and pauses and all(faults.values())
                                and all(not g.owned and all(f.done() for f in g.futures)
                                    for g in node.guards.values())):
                            marker('NEGATIVE_DONE.json',dict(monotonic_ns=time.monotonic_ns(),
                                uuid=uuid,actual_local_GetResult=5,PAUSE_success=True,
                                guards=faults,local_cleanup_pending=0,
                                central_state=node.last_status,
                                scope='Local controlled-server cancellation, not physical stopping'))
            try:node.poll()
            except Exception as error:node.fail(repr(error))
            if node.connected and not announced:
                print('GATEWAY_WIRES_READY',flush=True);announced=True
    finally:clean=node.close()
    return 0 if clean else 1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--role',choices=('peer','gateway','source'),required=True)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,required=True)
    parser.add_argument('--mode',choices=('A','B'),default='A')
    parser.add_argument('--full-load',action='store_true')
    parser.add_argument('--dds-take-trace',action='store_true')
    args=parser.parse_args()
    if args.role=='peer':return peer(args.directory,args.stop_file)
    if args.role=='gateway':return gateway(args.directory,args.stop_file,args.mode,args.full_load,args.dds_take_trace)
    from followup01.continuous_dds import source
    return source(args.directory,100,'controlled1000-clock100-q10ms','frozen-source-clock')


if __name__=='__main__':raise SystemExit(main())

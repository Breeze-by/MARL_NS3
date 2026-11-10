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


def gateway(directory,stop_file,mode):
    from gateway import Gateway
    node=Gateway(mode,directory.parent/'wire.sock',directory,SESSION,
        dispatch_profile=True,control_trace=True,
        execution_profile='controlled1000-clock100-q10ms')
    announced=False;next_check=0.
    try:
        while True:
            if time.monotonic()>=next_check:
                if stop_file.exists():break
                next_check=time.monotonic()+.05
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
    args=parser.parse_args()
    if args.role=='peer':return peer(args.directory,args.stop_file)
    if args.role=='gateway':return gateway(args.directory,args.stop_file,args.mode)
    from followup01.continuous_dds import source
    return source(args.directory,100,'controlled1000-clock100-q10ms','frozen-source-clock')


if __name__=='__main__':raise SystemExit(main())

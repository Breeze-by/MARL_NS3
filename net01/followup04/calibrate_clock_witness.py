"""One isolated FastRTPS timestamp calibration, no Gazebo/control/NS3."""
import argparse
import csv
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    result=dict(scope='Synthetic20clock real DDS source_timestamp calibration only; not GZ time or arrival-queue validation',
        domain=106,Gazebo=0,Nav2=0,Goal=0,NN=0,checks={})
    records=[];child=None;node=None;started=time.monotonic();deadline=started+12
    try:
        rclpy.init(domain_id=106);node=Node('net01_clock_calibration_source')
        publisher=node.create_publisher(Clock,'/clock',qos_profile_sensor_data)
        log=(out/'witness.stderr.txt').open('x')
        child=subprocess.Popen([str(args.binary),str(out/'clock.csv')],
            env=dict(os.environ,ROS_DOMAIN_ID='106'),stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
        readable,_,_=select.select([child.stdout],[],[],min(3,deadline-time.monotonic()))
        assert readable and child.stdout.readline().strip()=='CLOCK_WITNESS_READY'
        while publisher.get_subscription_count()==0 and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.01)
        assert publisher.get_subscription_count()==1
        for number in range(1,21):
            m=Clock();m.clock.nanosec=number*10_000_000
            row=dict(clock_ns=number*10_000_000,before_monotonic_ns=time.monotonic_ns(),before_realtime_ns=time.time_ns())
            publisher.publish(m)
            row.update(after_realtime_ns=time.time_ns(),after_monotonic_ns=time.monotonic_ns());records.append(row)
            until=time.monotonic()+.02
            while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.002)
        child.send_signal(signal.SIGINT);child.wait(timeout=min(3,deadline-time.monotonic()))
        assert child.returncode==0
        with (out/'clock.csv').open() as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==20 and {int(x['clock_ns']) for x in rows}=={x['clock_ns'] for x in records}
        by_clock={r['clock_ns']:r for r in records}
        # This1ms bracket is only timestamp-calibration resolution, never a
        # source-age/heartbeat/network/simulation tolerance.
        assert all(by_clock[int(r['clock_ns'])]['before_realtime_ns']-1_000_000<=int(r['dds_source_timestamp_ns'])
            <=by_clock[int(r['clock_ns'])]['after_realtime_ns']+1_000_000 for r in rows)
        assert len({r['publisher_gid'] for r in rows})==1 and int(rows[0]['publisher_gid'],16)!=0
        result.update(status='PASS',checks=dict(exact20original_clock_values=True,
            source_timestamp_nonzero_in_actual_system_publish_bracket=True,single_nonzero_writer_GID=True),
            received_timestamp_nonzero_count=sum(int(r['dds_received_timestamp_ns'])!=0 for r in rows),
            received_semantics='Raw metadata retained; no claim that this is earliest DDS arrival',
            max_system_mono_bracket_ns=max(int(r['callback_monotonic_after_ns'])-int(r['callback_monotonic_ns']) for r in rows),
            native_exit=child.returncode)
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));raise
    finally:
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGINT)
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if node is not None:node.destroy_node();rclpy.shutdown()
        result['wall_s']=time.monotonic()-started
        (out/'source-publications.json').write_text(json.dumps(records,indent=2)+'\n')
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

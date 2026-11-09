"""MOCK_PHYSICS: no Gazebo, poses, policy, navigation or velocity output.

Only a synthetic ten-iteration Step service and simulation clock. Clock is
sampled on 10ms thresholds, deliberately not at the physical token end phase.
"""
import argparse
import json
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock
from std_srvs.srv import Trigger


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,required=True);args=parser.parse_args()
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node=Node('net01_MOCK_PHYSICS');publisher=node.create_publisher(Clock,'/clock',qos_profile_sensor_data)
    value=5_000_000;iterations=0;records=[]
    def step(request,response):
        nonlocal value,iterations
        before=value;ib=iterations;begin=time.monotonic_ns()
        for _ in range(10):
            value+=1_000_000;iterations+=1
            if value%10_000_000==0:
                message=Clock();message.clock.sec=value//1_000_000_000;message.clock.nanosec=value%1_000_000_000
                publisher.publish(message);records.append(('synthetic_clock',time.monotonic_ns(),value))
        data=dict(before_ns=before,after_ns=value,before_iterations=ib,
            after_iterations=iterations,completed_steps=10)
        response.success=True;response.message=json.dumps(data)
        records.append(('MOCK_step',begin,time.monotonic_ns(),data));return response
    service=node.create_service(Trigger,'/net01/physics_step',step)
    print('MOCK_PHYSICS_READY',flush=True)
    try:
        while not args.stop_file.exists():rclpy.spin_once(node,timeout_sec=.001)
    finally:
        node.destroy_node();rclpy.shutdown()
        with args.output.open('x') as stream:json.dump(dict(scope='MOCK_PHYSICS only; no real ODE/Gazebo',
            sim_ns=value,iterations=iterations,records=records),stream)


if __name__=='__main__':main()

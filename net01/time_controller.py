"""Independent controlled-time owner. Only simulation/admin data, no business.

World::Step acknowledgements bound physical credit; only the unchanged Gateway
and real /clock drive native. One physical RPC, at most20ms physical lookahead.
"""
import argparse
import json
from pathlib import Path
import signal
import socket
import time

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock,ClockType
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy,qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock as ClockMessage
from std_msgs.msg import String
from std_srvs.srv import Trigger,SetBool
from time_control_state import TimeControlState


class TimeController(Node):
    def __init__(self,ack_socket,output):
        super().__init__('net01_time_controller')
        self.state=TimeControlState();self.output=Path(output);self.records=[]
        self.ack_socket=Path(ack_socket)
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
        self.socket.bind(str(self.ack_socket));self.socket.setblocking(False)
        self.future=None;self.group=ReentrantCallbackGroup()
        self.step=self.create_client(Trigger,'/net01/physics_step',callback_group=self.group)
        self.subscriptions_kept=[
            self.create_subscription(ClockMessage,'/clock',self.clock,qos_profile_sensor_data),
            self.create_subscription(String,'/net01/gateway_state',self.gateway,
                QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)),
            self.create_subscription(String,'/net01/guard_fault',self.guard_fault,10)]
        self.control_services=[
            self.create_service(SetBool,'/net01/time_control/hold',self.hold,callback_group=self.group),
            self.create_service(Trigger,'/net01/time_control/run',self.run,callback_group=self.group),
            self.create_service(SetBool,'/net01/time_control/stop_observe',self.stop_observe,callback_group=self.group)]
        self.publisher=self.create_publisher(String,'/net01/time_control_state',
            QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.timer=self.create_timer(.05,self.publish_state,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def record(self,kind,*values):
        # Primitive tuples, RAM only; no payload or model object retention.
        self.records.append((kind,time.monotonic_ns(),time.thread_time_ns(),*values))

    def snapshot(self):
        return dict(mode=self.state.mode,failure=self.state.failure,
            expected_shutdown=self.state.expected_shutdown,physics_failed=self.state.physics_failed,
            physical_ns=self.state.physical_ns,iterations=self.state.iterations,
            actual_clock_ns=self.state.clock_ns,native_ACK_ns=self.state.native_ns,
            fixed_offset_ns=self.state.anchor,physical_RPC_inflight=self.state.inflight)

    def publish_state(self):self.publisher.publish(String(data=json.dumps(self.snapshot())))

    def clock(self,message):
        value=message.clock.sec*1_000_000_000+message.clock.nanosec
        self.state.clock(value);self.record('actual_clock',value)

    def gateway(self,message):
        data=json.loads(message.data)
        if data['anchor'] is not None:self.state.set_anchor(data['anchor']['offset_ns'])
        if data['failure']:self.observed_failure('gateway:'+data['failure'])

    def guard_fault(self,message):self.observed_failure('guard:'+message.data)

    def observed_failure(self,reason):
        self.record('post_expected_shutdown_condition' if self.state.expected_shutdown else 'failure',reason)
        if not self.state.expected_shutdown:self.state.fail(reason)

    async def hold(self,request,response):
        self.state.hold();self.record('HOLD_requested',request.data)
        pending=self.future
        if pending is not None:
            await pending
            self.finish_step()
        response.success=not self.state.physics_failed
        if response.success and request.data:self.state.hold(expected_shutdown=True)
        self.record('HOLD_completed',response.success,self.state.expected_shutdown)
        response.message=json.dumps(self.snapshot());return response

    def run(self,request,response):
        response.success=self.state.run();self.record('RUN',response.success)
        response.message=json.dumps(self.snapshot());return response

    def stop_observe(self,request,response):
        # The real supervisor supplies its already-established authority exit;
        # this is simulation/safety control, never a policy input or new goal.
        response.success=self.state.stop_observe(request.data)
        self.record('STOP_OBSERVE',request.data,response.success,self.state.mode)
        response.message=json.dumps(self.snapshot());return response

    def finish_step(self):
        if self.future is None or not self.future.done():return
        future=self.future;self.future=None
        try:
            response=future.result();data=json.loads(response.message)
            self.record('post_physics_ACK',response.success,data['before_ns'],data['after_ns'],
                data['before_iterations'],data['after_iterations'],data['completed_steps'])
            if not response.success:
                self.state.inflight=False;self.state.fail('physics_RPC_rejected',physics=True)
            else:self.state.complete_step(data)
        except Exception as error:
            self.state.inflight=False;self.state.fail('physics_RPC_failed:'+repr(error),physics=True)
            self.record('physics_RPC_failed',repr(error))

    def poll(self):
        while True:
            try:body=self.socket.recv(4096)
            except BlockingIOError:break
            row=json.loads(body)
            self.state.native(row['kind'],row['horizon_ns'])
            self.record('actual_native_progress',row['kind'],row['horizon_ns'],row['monotonic_ns'])
        self.finish_step()
        if self.state.can_step() and self.step.service_is_ready():
            self.state.begin_step();self.record('physical_token',self.state.mode,
                self.state.physical_ns,self.state.native_ns,self.state.anchor)
            self.future=self.step.call_async(Trigger.Request())

    def close(self):
        self.socket.close();self.ack_socket.unlink()
        with self.output.open('x') as stream:
            json.dump(dict(scope='Simulation control only; real clock/native ACK, no business payload',
                final=self.snapshot(),records=self.records),stream)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ack-socket',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,help='Isolated fixture resource teardown only')
    parser.add_argument('--hold-file',type=Path,help='Isolated fixture expected-shutdown request only')
    args=parser.parse_args()
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node=TimeController(args.ack_socket,args.output);executor=SingleThreadedExecutor();executor.add_node(node)
    stopping=False;held=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    print('TIME_CONTROL_READY '+str(args.ack_socket),flush=True)
    try:
        while not stopping:
            try:
                executor.spin_once(timeout_sec=.001);node.poll()
                if args.hold_file is not None and args.hold_file.exists():
                    node.state.hold()
                    if not node.state.inflight and not held:
                        node.state.hold(expected_shutdown=True);held=True
                        args.hold_file.with_suffix('.ack').write_text('actual physical RPC complete; resource HOLD only')
                if args.stop_file is not None and args.stop_file.exists():stopping=True
            except Exception as error:node.observed_failure(repr(error))
    finally:
        node.close();executor.remove_node(node);executor.shutdown(timeout_sec=0)
        node.destroy_node();rclpy.shutdown()
    return 1 if node.state.failure or node.state.inflight or not node.state.expected_shutdown else 0


if __name__=='__main__':raise SystemExit(main())

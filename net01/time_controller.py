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
from rclpy.task import Future
from rclpy.qos import QoSProfile,DurabilityPolicy,qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock as ClockMessage
from std_msgs.msg import String
from std_srvs.srv import Trigger,SetBool
from execution_profile import load_profile,CONTROLLED_PROFILE_IDS
from time_control_state import TimeControlState,QUANTUM_NS


class TimeController(Node):
    def __init__(self,ack_socket,output,session_id,execution_profile=CONTROLLED_PROFILE_IDS[0]):
        super().__init__('net01_time_controller')
        self.execution_profile=load_profile(execution_profile)
        self.progress_wall_timeout_ns=(int(self.execution_profile['progress_wall_timeout_s']*1e9)
            if self.execution_profile.get('health_mask_receipt_clock')=='R-ros-sim-v1' else None)
        self.state=TimeControlState(self.execution_profile['token_wall_period_ns'],self.progress_wall_timeout_ns)
        self.hold_waiters=[]
        self.output=Path(output);self.records=[]
        self.first_physical_token_wall_ns=None;self.first_physical_before_ns=None
        self.last_physical_ACK_wall_ns=None
        self.session_id=session_id;self.gateway_prerequisite=None
        self.ack_socket=Path(ack_socket)
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
        self.socket.bind(str(self.ack_socket));self.socket.setblocking(False)
        self.future=None;self.pending_holds=0;self.group=ReentrantCallbackGroup()
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
        sim_span=None if self.first_physical_before_ns is None else self.state.physical_ns-self.first_physical_before_ns
        wall_span=None if self.last_physical_ACK_wall_ns is None else self.last_physical_ACK_wall_ns-self.first_physical_token_wall_ns
        return dict(mode=self.state.mode,failure=self.state.failure,
            expected_shutdown=self.state.expected_shutdown,physics_failed=self.state.physics_failed,
            physical_ns=self.state.physical_ns,iterations=self.state.iterations,
            actual_clock_ns=self.state.clock_ns,native_ACK_ns=self.state.native_ns,
            fixed_offset_ns=self.state.anchor,physical_RPC_inflight=self.state.inflight,
            session_id=self.session_id,gateway_clock_ready=self.state.gateway_clock_ready,
            pending_holds=self.pending_holds,authority_exited=self.state.authority_exited,
            progress_wall_timeout_ns=self.progress_wall_timeout_ns,
            progress_started_monotonic_ns=self.state.progress_started_ns,
            motion_armed_since_monotonic_ns=self.state.motion_armed_since_ns,
            global_progress_activation_basis=(None if self.progress_wall_timeout_ns is None else
                'First same-session status with any actual R Guard armed; receipt monotonic, not Goal/Policy or bootstrap token'),
            actual_clock_progress_monotonic_ns=self.state.clock_progress_ns,
            native_ACK_progress_monotonic_ns=self.state.native_progress_ns,
            physical_RPC_issued_monotonic_ns=self.state.inflight_since_ns,
            execution_profile=self.execution_profile['id'],
            token_wall_period_ns=self.state.token_wall_period_ns,
            planned_realtime_factor=QUANTUM_NS/self.state.token_wall_period_ns,
            actual_achieved_physical_rtf=None if wall_span is None else sim_span/wall_span,
            physical_progress_sim_span_ns=sim_span,physical_progress_wall_span_ns=wall_span,
            achieved_rtf_scope='First physical token issue through latest successful actual physics ACK; not a rate guarantee',
            next_earliest_wall_ns=self.state.next_wall_ns,
            max_token_lateness_ns=self.state.max_lateness_ns,late_tokens=self.state.late_tokens)

    def publish_state(self):self.publisher.publish(String(data=json.dumps(self.snapshot())))

    def clock(self,message):
        value=message.clock.sec*1_000_000_000+message.clock.nanosec
        self.state.clock(value,time.monotonic_ns() if self.progress_wall_timeout_ns is not None else None)
        self.record('actual_clock',value)

    def gateway(self,message):
        data=json.loads(message.data)
        if data['session_id']!=self.session_id:return
        if self.progress_wall_timeout_ns is not None and any(g['armed'] for g in data['guards'].values()):
            received=time.monotonic_ns()
            if self.state.observe_motion_armed(received):
                self.record('actual_R_guard_ARM_watchdog_activation',received,data['gateway_monotonic_ns'],
                    tuple(robot for robot,g in data['guards'].items() if g['armed']))
        prerequisite=(data['clock_reader_ready'],data['clock_writer_discovered'],data['clock_publishers'])
        if prerequisite!=self.gateway_prerequisite:
            self.record('actual_gateway_clock_prerequisite',self.session_id,*prerequisite,data['gateway_monotonic_ns'])
            self.gateway_prerequisite=prerequisite
        self.state.gateway_clock_ready=prerequisite[0] and prerequisite[1]
        if data['anchor'] is not None:self.state.set_anchor(data['anchor']['offset_ns'])
        if data['failure']:self.observed_failure('gateway:'+data['failure'])

    def guard_fault(self,message):self.observed_failure('guard:'+message.data)

    def observed_failure(self,reason):
        self.record('post_expected_shutdown_condition' if self.state.expected_shutdown else 'failure',reason)
        if not self.state.expected_shutdown:self.state.fail(reason)

    async def hold(self,request,response):
        self.pending_holds+=1
        try:
            self.state.hold();self.record('HOLD_requested',request.data)
            pending=self.future
            if pending is not None:
                if self.progress_wall_timeout_ns is None:await pending
                else:
                    waiter=Future();self.hold_waiters.append((waiter,pending))
                    await waiter  # poll releases this on actual ACK or the independent wall timeout.
                self.finish_step()
            response.success=(not self.state.physics_failed and self.state.mode=='HOLD'
                and not self.state.inflight)
            if response.success and request.data:self.state.hold(expected_shutdown=True)
            self.record('HOLD_completed',response.success,self.state.expected_shutdown)
            response.message=json.dumps(self.snapshot());return response
        finally:self.pending_holds-=1

    def run(self,request,response):
        response.success=not self.pending_holds and self.state.run();self.record('RUN',response.success)
        response.message=json.dumps(self.snapshot());return response

    def stop_observe(self,request,response):
        # The real supervisor supplies its already-established authority exit;
        # this is simulation/safety control, never a policy input or new goal.
        response.success=not self.pending_holds and self.state.stop_observe(request.data)
        self.record('STOP_OBSERVE',request.data,response.success,self.state.mode)
        response.message=json.dumps(self.snapshot());return response

    def finish_step(self):
        if self.future is None or not self.future.done():return
        future=self.future;self.future=None
        try:
            response=future.result();data=json.loads(response.message)
            self.record('post_physics_ACK',response.success,data['before_ns'],data['after_ns'],
                data['before_iterations'],data['after_iterations'],data['completed_steps'])
            if 'diagnostic_timing_v1' in data:
                self.record('physics_step_server_timing_v1',data['diagnostic_timing_v1'])
            if not response.success:
                self.state.inflight=False;self.state.fail('physics_RPC_rejected',physics=True)
            else:
                self.state.complete_step(data,time.monotonic_ns() if self.progress_wall_timeout_ns is not None else None)
                if not self.state.physics_failed:
                    if self.first_physical_before_ns is None:self.first_physical_before_ns=data['before_ns']
                    self.last_physical_ACK_wall_ns=time.monotonic_ns()
        except Exception as error:
            self.state.inflight=False;self.state.fail('physics_RPC_failed:'+repr(error),physics=True)
            self.record('physics_RPC_failed',repr(error))

    def poll(self):
        while True:
            try:body=self.socket.recv(4096)
            except BlockingIOError:break
            row=json.loads(body)
            self.state.native(row['kind'],row['horizon_ns'],
                time.monotonic_ns() if self.progress_wall_timeout_ns is not None else None)
            self.record('actual_native_progress',row['kind'],row['horizon_ns'],row['monotonic_ns'])
        previous_failure=self.state.failure
        self.state.check_progress(time.monotonic_ns())
        self.finish_step()
        if self.progress_wall_timeout_ns is not None:
            waiting=[]
            for waiter,pending in self.hold_waiters:
                if pending.done() or self.state.physics_failed:waiter.set_result(None)
                else:waiting.append((waiter,pending))
            self.hold_waiters=waiting
            if self.state.failure!=previous_failure:
                self.record('independent_progress_wall_failure',self.state.failure)
                self.publish_state()
        if self.state.can_step(time.monotonic_ns()) and self.step.service_is_ready():
            issued=time.monotonic_ns();self.state.begin_step(issued)
            if self.first_physical_token_wall_ns is None:self.first_physical_token_wall_ns=issued
            self.record('physical_token',self.state.mode,
                self.state.physical_ns,self.state.native_ns,self.state.anchor,
                self.state.last_planned_wall_ns,self.state.last_lateness_ns)
            self.future=self.step.call_async(Trigger.Request())

    def close(self):
        self.socket.close();self.ack_socket.unlink()
        with self.output.open('x') as stream:
            json.dump(dict(scope='Simulation control only; real clock/native ACK, no business payload',
                final=self.snapshot(),records=self.records),stream)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ack-socket',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--session-id',type=int,required=True)
    parser.add_argument('--execution-profile',choices=CONTROLLED_PROFILE_IDS,default=CONTROLLED_PROFILE_IDS[0])
    parser.add_argument('--stop-file',type=Path,help='Isolated fixture resource teardown only')
    parser.add_argument('--hold-file',type=Path,help='Isolated fixture expected-shutdown request only')
    args=parser.parse_args()
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node=TimeController(args.ack_socket,args.output,args.session_id,args.execution_profile);executor=SingleThreadedExecutor();executor.add_node(node)
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

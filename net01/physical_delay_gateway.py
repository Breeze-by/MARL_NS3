"""Dedicated ACK-simulation-delay composition over the original owned Gateway."""
import json
import os
import time

import gateway as original
import delivery_guard
from nav2_msgs.action import NavigateToPose
from rclpy.serialization import deserialize_message
from execution_profile import PHYSICS_DELAY_PROFILE_ID
from physical_delay_runtime import PhysicalDelayFIFO
from physical_delay_observation import ObservedDeliveryGuard
from ros_delay_gateway import ROSDelayGateway,DelayActionWire


class PhysicalDelayActionWire(DelayActionWire):
    """Small callback observations; original Action CDR/futures/control unchanged."""
    def __init__(self,*args,physical_observation,observation_rows,**kwargs):
        self.physical_observation=physical_observation;self.observation_rows=observation_rows
        self.result_uuids={}
        super().__init__(*args,**kwargs)
        if self.robot is not None:
            client=self.clients[2];original_call=client.call_async
            def call(request):
                future=original_call(request)
                uuid=bytes(request.goal_id.uuid).hex()
                def observed(done):
                    error=done.exception()
                    self.observe_result('R_GetResult_backend_callback',self.robot,uuid,
                        None if error is not None else done.result().status,
                        error=None if error is None else type(error).__name__)
                future.add_done_callback(observed)
                return future
            client.call_async=call

    def observe_result(self,kind,robot,uuid,status,**fields):
        self.observation_rows.append(dict(kind=kind,robot=robot,uuid=uuid,status=status,
            monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),
            local_node_sim_ns=self.node.get_clock().now().nanoseconds,
            latest_confirmed_physics_ACK=self.physical_observation(),**fields))

    def _send_rpc(self,robot,offset,body,rpc):
        if self.robot is None and offset==2:
            request=deserialize_message(body,NavigateToPose.Impl.GetResultService.Request)
            self.result_uuids[(robot,rpc)]=bytes(request.goal_id.uuid).hex()
        return super()._send_rpc(robot,offset,body,rpc)

    def receive(self,peer,flow,body,rpc_id):
        robot,offset=divmod(flow-200,20)
        if self.robot is None and offset==3 and (robot,offset,rpc_id) in self.pending:
            response=deserialize_message(body,NavigateToPose.Impl.GetResultService.Response)
            self.observe_result('C_GetResult_wire_response_received',robot,
                self.result_uuids[(robot,rpc_id)],response.status,rpc_id=rpc_id)
        return super().receive(peer,flow,body,rpc_id)


class PhysicalDelayGateway(ROSDelayGateway):
    def __init__(self,*args,**kwargs):
        self.delay_queue=PhysicalDelayFIFO(int(os.environ['NET01_PHYSICAL_DELAY_NS']),
            int(os.environ['NET01_SESSION_ID']),PHYSICS_DELAY_PROFILE_ID)
        self.delay_closing=False;self.delay_stop_reason=None;self.delay_outside_epoch={}
        self.delay_proxy_rejections=[];self.delay_close=None;self.delay_epoch_close=None
        self.physical_action_observations=[]
        # Reuse original ActionWire composition and owned close, bypassing only
        # the wall-delay-specific constructor/clock selector.
        guard_class=delivery_guard.DeliveryGuard
        delivery_guard.DeliveryGuard=ObservedDeliveryGuard
        try:original.Gateway.__init__(self,*args,**kwargs)
        finally:delivery_guard.DeliveryGuard=guard_class
        if self.mode!='A' or self.execution_profile['id']!=PHYSICS_DELAY_PROFILE_ID:
            raise ValueError('Physical FIFO requires explicit local proxy profile')
        self.record('physical_delay_proxy_entry',delay_physical_ns=self.delay_queue.delay_ns,
            activation_anchor_physical_ns=self.delay_queue.activation_ns,
            action_application_confirmation=False,clock_source='actual successful physical ACK')

    def install_wires(self):
        base=original.ActionWire
        def factory(*args,**kwargs):
            return PhysicalDelayActionWire(*args,goal_permission=self.goal_permission,
                rejection_records=self.delay_proxy_rejections,observation_rows=self.physical_action_observations,
                physical_observation=lambda:dict(physical_ns=self.delay_queue.physical_ns,
                    ACK_monotonic_ns=self.delay_queue.ACK_monotonic_ns),**kwargs)
        original.ActionWire=factory
        try:return original.Gateway.install_wires(self)
        finally:original.ActionWire=base

    def send(self,*args,**kwargs):
        previous=len(self.delay_queue.rows)
        value=super().send(*args,**kwargs)
        if len(self.delay_queue.rows)>previous:
            self.delay_queue.pending[-1][0][0]['backend']='ROS_LOCAL_PHYSICAL_ACK_DELAY_FIFO'
        return value

    def time_control_state(self,message):
        state=json.loads(message.data)
        if state['session_id']!=self.session_id or state['execution_profile']!=self.execution_profile['id']:
            self.delay_queue.clock_rejections+=1;return
        super().time_control_state(message)  # Sole original guard authority lifecycle.
        self.delay_queue.observe_ACK(state,time.monotonic_ns())
        # Legal startup STOP/HOLD has no armed guard and cannot end admission.
        # A true final revocation seals periodic ingress BEFORE physical HOLD;
        # pending original RPCs retain real due times, responses and UUIDs.
        final_stop=(state['authority_exited'] and (state['mode'] in
            ('STOP_COUPLED','FAULT_STOP_OBSERVE','HOLD') or state['expected_shutdown']))
        if not self.delay_closing and final_stop and any(s.guard.armed or s.guard.halted for s in self.guards.values()):
            self.delay_closing=True
            self.delay_epoch_close=dict(reason='original_global_STOP_after_armed_authority_exit',
                monotonic_ns=time.monotonic_ns(),physical_ACK_ns=self.delay_queue.physical_ns,
                execution_profile=self.execution_profile['id'],session_id=self.session_id)
            self.record('physical_delay_ingress_epoch_closed',**self.delay_epoch_close)

    def _progress_transport(self):
        self.direct.extend(self.delay_queue.release_due(time.monotonic_ns(),
            'closing_drain' if self.delay_closing else 'open_ingress'))
        return original.Gateway._progress_transport(self)

    def extend_status(self,data):
        data['actual_rpc_cleanup'].update(delay_rpc_queued=self.delay_queue.pending_rpc(),
            delay_admitted_frames_pending=len(self.delay_queue.pending)+len(self.direct))
        data['physical_delay']=dict(delay_physical_ns=self.delay_queue.delay_ns,
            pending=len(self.delay_queue.pending),unanchored=len(self.delay_queue.unanchored),
            actual_physical_ACK_ns=self.delay_queue.physical_ns,closing=self.delay_closing,
            execution_profile=self.execution_profile['id'])

    def persist(self):
        with (self.directory/'guard-protection-observations.json').open('x') as stream:
            json.dump(dict(schema='bounded-original-guard-predicate-v1',execution_profile=self.execution_profile['id'],
                pid=os.getpid(),case=str(self.directory.resolve()),session_id=self.session_id,
                guards={str(robot):stop.guard.bounded_observations()
                    for robot,stop in self.guards.items()},
                scope='First actual trip and last actual blocked arm/rejected candidate only. Original predicate is called once; failed-call now/inputs/limits are observed, not recomputed. A GetResult time is not source generation or physical stopping.'),stream)
        with (self.directory/'physical-delay-queue.json').open('x') as stream:
            json.dump(dict(schema='physical-step-ack-fifo-v1',delay_physical_ns=self.delay_queue.delay_ns,
                activation_anchor_physical_ns=self.delay_queue.activation_ns,frames=self.delay_queue.rows,
                outside_closed_admission_epoch=self.delay_outside_epoch,
                proxy_admission_rejections=self.delay_proxy_rejections,epoch_close=self.delay_epoch_close,
                Action_callback_observations=self.physical_action_observations,
                close=self.delay_close,clock_rejections=self.delay_queue.clock_rejections,
                semantics='First received successful ACK at/after queue capture is the common anchor; due=anchor+declared physical delay. Capture local R clock is diagnostic only. Actual capture/anchor/release wall and physical ACK brackets must be reported, not assumed exact500ms from raw capture. Release enters the original dispatch queue, not destination publish/HQ take.'),stream)
        return original.Gateway.persist(self)

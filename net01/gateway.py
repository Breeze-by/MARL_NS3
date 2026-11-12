"""NET-01 two-domain composition. Only delivery backend differs in A/B/C.

The R executor is never run by the ns-3/hub process. Native IPC is polled
without waiting; its EOF latches all local stops and does not stop R callbacks.
All records are RAM captures, persisted only after the owned loop exits.
"""
import argparse
from collections import deque
import gc
import hashlib
import json
from pathlib import Path
import resource
import signal
import time
import os
from execution_profile import load_profile

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor,TimeoutException,ShutdownException
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from rclpy.serialization import deserialize_message
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock as ClockMessage
from gazebo_msgs.msg import ModelStates
from std_msgs.msg import String
from std_srvs.srv import Trigger

from action_wire import ActionWire
from bound_mask_wire import BoundMaskWire
from delivery_guard import LocalStop
from hub_client import HubClient
from link_session import LinkSession
from topic_wire import TopicWire


def record_cpu_span(table,key,wall,cpu,longspans=None,label=None):
    end=time.monotonic_ns();cpu_end=time.thread_time_ns()
    elapsed=end-wall;used=cpu_end-cpu
    if longspans is not None and elapsed>=10_000_000:
        longspans.append(dict(stage=label or key,begin_monotonic_ns=wall,end_monotonic_ns=end,
            begin_thread_cpu_ns=cpu,end_thread_cpu_ns=cpu_end))
    row=table.setdefault(key,dict(calls=0,wall_ns=0,thread_cpu_ns=0,max_wall_ns=0))
    row['calls']+=1;row['wall_ns']+=elapsed;row['thread_cpu_ns']+=used
    row['max_wall_ns']=max(row['max_wall_ns'],elapsed)


def drain_current_ready(executor,node,ready_set,after_handler=None,callback_limit=None,
                        profile=None,entity_label=None,longspans=None,side=None):
    """Bounded productive ready sets, in original SingleThreaded order.

    Keep the executor's cached iterator across cap hits. Do not wait/rebuild an
    empty waitset for every other-domain callback or favor any topic/timer.
    Timeout0 also ends a productive set; it does not mean readers are empty.
    """
    cap=callback_limit if callback_limit is not None else sum(
        len(tuple(getattr(node,name))) for name in
        ('subscriptions','timers','clients','services','guards','waitables'))
    completed=[]
    while len(completed)<cap:
        if profile is not None:wait_wall=time.monotonic_ns();wait_cpu=time.thread_time_ns()
        wait_kind='error'
        try:
            handler,entity,_=executor.wait_for_ready_callbacks(timeout_sec=0)
            wait_kind='ready'
        except TimeoutException:
            wait_kind='productive_set_end' if ready_set['productive'] else 'empty_set'
            ready_set['productive']=False
            break
        except ShutdownException:
            wait_kind='shutdown'
            ready_set['shutdown']=True
            break
        finally:
            ready_set['last_wait_kind']=wait_kind
            if profile is not None:record_cpu_span(profile['wait'],wait_kind,wait_wall,wait_cpu,
                    longspans,f'{side}:wait:{wait_kind}')
        began=time.monotonic()
        if profile is not None:handler_wall=time.monotonic_ns();handler_cpu=time.thread_time_ns()
        try:
            handler()
            if handler.exception() is not None:raise handler.exception()
            handler.result()
        finally:
            if profile is not None:record_cpu_span(profile['handlers'],entity_label(entity),handler_wall,handler_cpu,
                    longspans,f'{side}:handler:{entity_label(entity)}')
        completed.append((entity,began))
        ready_set['productive']=True
        if after_handler is not None:after_handler()
    return completed,cap


class Gateway:
    def __init__(self, mode, socket, directory, session_id, *, dispatch_profile=False,control_trace=False,execution_profile=None,
                 dds_take_trace=False,main_thread_sample=False,guardian_factory=LocalStop,gateway_cprofile=False,
                 adapter_qos_events='sdk-default',capture_central_map=False):
        if dds_take_trace and not dispatch_profile:
            raise ValueError('DDS take diagnostic requires the existing RAM dispatch profile')
        self.mode,self.directory,self.session_id=mode,Path(directory),session_id
        self.adapter_qos_events=adapter_qos_events
        self.central_map_captures=[] if capture_central_map else None
        node_type=Node
        if adapter_qos_events=='warning-free-v1':
            from adapter_node import AdapterNode
            node_type=AdapterNode
        elif adapter_qos_events!='sdk-default':raise ValueError('Unknown adapter QoS event version')
        self.execution_profile=load_profile(execution_profile)
        self.control_clock_lane=(self.execution_profile is not None and
            self.execution_profile.get('gateway_control_clock_lane')=='separate-executor-v1')
        self.step_quantum_ns=100_000_000 if self.execution_profile is None else self.execution_profile['native_step_quantum_ns']
        self.records=[];self.direct=deque();self.direct_sequence=0
        self.python_profiler=None;self.python_profile=None
        if gateway_cprofile:
            import cProfile
            self.python_profiler=cProfile.Profile(timer=time.thread_time_ns,timeunit=1e-9,
                subcalls=True,builtins=True)
            self.python_profile=dict(status='NOT_STARTED',requested_wall_ns=2_000_000_000,
                timer='thread_time_ns; CPU, not wall',profiled_polls=0,
                profiled_poll_wall_ns=0,profiled_poll_thread_cpu_ns=0,
                scope='Only original Gateway poll; probe overhead included, not separately estimated')
        self.contexts=[];self.nodes=[];self.executors=[]
        self.control_clock_node=None;self.control_clock_executor=None
        if self.control_clock_lane:
            self.control_clock_ready_set=dict(productive=False,shutdown=False,last_wait_kind='not_probed')
            self.control_clock_empty_epoch=None;self.control_clock_work_this_poll=False
            self.control_clock_stats=dict(probes=0,callbacks=0,clock_callbacks=0,wall_ns=0,max_wall_ns=0,
                wait_kinds={},idle_rejections=0,
                scope='At most one ready handler per nonblocking probe, at poll start and after each business handler; no separate STEP owner')
        self.ready_sets={side:dict(productive=False) for side in ('C','R')}
        self.c_empty_until=0.
        self._poll_transport_active=False
        self._idle_work_epoch=0;self._tail_empty_epoch={side:None for side in ('C','R')}
        self.idle_phase_snapshots={}
        self.dispatch_stats=dict(C=dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.,empty_recheck_started=0,empty_recheck_skips=0),
            R=dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.),
            guard_timers={},max_poll_gap_wall_s=0.,idle_wait=dict(calls=0,requested_ns=0,
                wall_ns=0,thread_cpu_ns=0,readable=0,max_requested_ns=0,max_wall_ns=0,max_overrun_ns=0,
                original_idle=0,tail_quiet_idle=0,history_only_eligible=0,
                stale_empty_rejections=0,backlog_or_stopped_rejections=0,deadline_rejections=0),
            schedule='C/R cached handlers alternate in fixed quantum4; stop after a pair when either initial cap is used',
            side_span_semantics='max_wall/cpu are accumulated side service time per poll, including pump; not contiguous batches or single-callback spans')
        self.cpu_profile=(dict(C=dict(wait={},handlers={}),R=dict(wait={},handlers={}),progress={})
            if dispatch_profile else None)
        self.profile_longspans=[] if dispatch_profile else None
        self.profile_labels={}
        self.health_trace=None
        if dispatch_profile:
            from net01d.health.trace import HealthTrace
            self.health_trace=HealthTrace()
        self.last_poll=None
        self.gc_events=[];self.gc_callback=None
        self.main_thread_sampler=None
        for domain,side in ((91,"C"),(92,"R")):
            context=Context()
            rclpy.init(context=context,domain_id=domain,signal_handler_options=SignalHandlerOptions.NO)
            node=node_type("net01_gateway_"+side.lower(),context=context,
                parameter_overrides=[Parameter("use_sim_time",value=True)])
            if dds_take_trace and side=='R':
                from net01d.health.take_trace import MetadataSingleThreadedExecutor
                executor=MetadataSingleThreadedExecutor(context=context,node=node,trace=self.health_trace)
            else:executor=SingleThreadedExecutor(context=context)
            executor.add_node(node)
            self.contexts.append(context);self.nodes.append(node);self.executors.append(executor)
        self.c,self.r=self.nodes
        self.hub=HubClient(socket,control_trace=control_trace);self.hub.receive=self.receive
        self.link=LinkSession(self,session_id)
        self.sim_health=(self.execution_profile is not None and
            self.execution_profile.get('health_mask_receipt_clock')=='R-ros-sim-v1')
        guard_options={'execution_profile':self.execution_profile} if self.sim_health else {}
        self.guards={r:guardian_factory(self.r,r,session_id,**guard_options) for r in (1,2,3)}
        self.time_control_sub=(self.r.create_subscription(String,'/net01/time_control_state',
            self.time_control_state,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
            if self.sim_health else None)
        self.anchor=None;self.gz=None;self.previous_clock=None;self.step_pending=None
        self.connected=False;self.failure=None;self.wires=None
        self.last_status=None  # Actual existing timer snapshot, for fixture diagnostics only.
        self.hub_poll_closed=False
        self.health_status=self.r.create_publisher(String,"/net01/gateway_state",
            QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.clock_pub=self.c.create_publisher(ClockMessage,"/clock",qos_profile_sensor_data)
        if self.control_clock_lane:self._create_control_clock_lane(node_type)
        else:self.clock_sub=self.r.create_subscription(ClockMessage,"/clock",self.clock,qos_profile_sensor_data)
        self.models_sub=self.r.create_subscription(ModelStates,"/gazebo/model_states",self.models,qos_profile_sensor_data)
        self.arm_services=[self.r.create_service(Trigger,f"/net01/tb{r}/arm",
            lambda req,resp,r=r:self.arm(r,resp)) for r in (1,2,3)]
        self.status_timer=self.r.create_timer(.05,self.status,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.journal_position=0
        self.journal_pub=self.c.create_publisher(String,"/net01/controller_records",100)
        self.journal_timer=self.c.create_timer(.02,self.export_controller_records,
            clock=Clock(clock_type=ClockType.STEADY_TIME))
        if dispatch_profile:
            self.gc_callback=self.observe_gc
            gc.callbacks.append(self.gc_callback)
        # This process has the existing supervisor wall bound. Refcounting stays
        # active; only automatic cyclic scans are deferred until teardown.
        self.gc_original_enabled=gc.isenabled()
        self.gc_runtime=dict(original_enabled=self.gc_original_enabled,
            original_thresholds=gc.get_threshold(),
            scope='Only this supervisor-bounded Gateway; deferred cycles can increase RAM, not a long-lived-service policy')
        gc.disable()
        self.gc_runtime['disabled_monotonic_ns']=time.monotonic_ns()
        self.gc_runtime['processing_start_enabled']=gc.isenabled()
        if main_thread_sample:
            from net01d.followup01.main_thread_sampler import MainThreadSampler
            self.main_thread_sampler=MainThreadSampler()
            self.main_thread_sampler.start()

    def _create_control_clock_lane(self,node_type):
        self.control_clock_node=node_type('net01_gateway_clock_control',context=self.r.context,
            parameter_overrides=[Parameter('use_sim_time',value=False)],
            start_parameter_services=False,enable_rosout=False)
        self.control_clock_executor=SingleThreadedExecutor(context=self.r.context)
        self.control_clock_executor.add_node(self.control_clock_node)
        self.clock_sub=self.control_clock_node.create_subscription(ClockMessage,'/clock',
            self.clock,qos_profile_sensor_data)

    def _service_control_clock(self):
        began=time.monotonic_ns();completed=[]
        try:
            completed,_=drain_current_ready(self.control_clock_executor,self.control_clock_node,
                self.control_clock_ready_set,callback_limit=1)
        finally:
            elapsed=time.monotonic_ns()-began;stats=self.control_clock_stats
            stats['probes']+=1;stats['wall_ns']+=elapsed
            stats['max_wall_ns']=max(stats['max_wall_ns'],elapsed)
            kind=self.control_clock_ready_set['last_wait_kind']
            stats['wait_kinds'][kind]=stats['wait_kinds'].get(kind,0)+1
        if completed:
            self._idle_work_epoch+=len(completed);self.control_clock_work_this_poll=True
            stats['callbacks']+=len(completed)
            stats['clock_callbacks']+=sum(entity is self.clock_sub for entity,_ in completed)
        self.control_clock_empty_epoch=(self._idle_work_epoch
            if self.control_clock_ready_set['last_wait_kind']=='empty_set' else None)

    def _close_control_clock_lane(self):
        self.control_clock_executor.remove_node(self.control_clock_node)
        shutdown=self.control_clock_executor.shutdown(timeout_sec=0)
        self.control_clock_node.destroy_node()
        return shutdown

    def observe_gc(self,phase,info):
        self.gc_events.append(dict(phase=phase,generation=info['generation'],
            monotonic_ns=time.monotonic_ns(),thread_cpu_ns=time.thread_time_ns(),
            collected=info.get('collected'),uncollectable=info.get('uncollectable')))

    def record(self,kind,**fields):
        self.records.append(dict(dict(kind=kind,monotonic_ns=time.monotonic_ns(),gz_ns=self.gz),**fields))

    def time_control_state(self,message):
        data=json.loads(message.data)
        for guardian in self.guards.values():guardian.guard.control_state(data)

    def clock(self,message):
        capture_monotonic_ns=time.monotonic_ns()
        gz=message.clock.sec*1_000_000_000+message.clock.nanosec
        self.clock_pub.publish(message)  # Independent simulation control, no business fields.
        publish_return_monotonic_ns=time.monotonic_ns()
        if self.anchor is None:
            self.anchor=dict(gazebo_ns=gz,ns3_ns=0,offset_ns=gz,monotonic_ns=time.monotonic_ns())
            self.record("fixed_clock_anchor",**self.anchor)
        if self.previous_clock is not None and gz<self.previous_clock:
            self.fail("gazebo_clock_rollback")
        self.previous_clock=self.gz=gz
        if self.failure is None:self.hub.observed_clock(gz-self.anchor["offset_ns"])
        self.record("actual_R_clock_relayed_C",gazebo_ns=gz,
            R_callback_capture_monotonic_ns=capture_monotonic_ns,
            C_publish_return_monotonic_ns=publish_return_monotonic_ns)

    def models(self,message):
        if self.anchor is None or self.failure:return
        for robot in (1,2,3):
            name=f"tb{robot}"
            if name in message.name:
                p=message.pose[message.name.index(name)].position
                self.hub.network_position(robot,p.x,p.y,.15)
        # These positions only update ns-3 MobilityModel; no C policy publisher.

    def send(self,sender,receiver,flow,body,rpc_id=0,source_stamp_ns=0):
        if self.failure:return
        if self.anchor is None:raise RuntimeError("Business injection before actual clock anchor")
        if 200<=flow<300:
            self.record("action_CDR_capture",sender=sender,receiver=receiver,flow=flow,rpc_id=rpc_id,
                cdr_bytes=len(body),cdr_sha256=hashlib.sha256(body).hexdigest(),source_stamp_available=False)
            if sender==0 and flow in (220,240,260) and 'start' not in self.idle_phase_snapshots:
                self._snapshot_idle_phase('start','first_actual_C_Goal_capture')
            if (self.python_profile is not None and self.python_profile['status']=='NOT_STARTED'
                    and 'trigger_monotonic_ns' not in self.python_profile
                    and sender==0 and flow in (220,240,260)):
                self.python_profile.update(status='WAITING_NEXT_POLL',trigger_flow=flow,
                    trigger_rpc_id=rpc_id,trigger_monotonic_ns=time.monotonic_ns())
        if self.mode=="A":
            self.direct_sequence+=1
            meta=dict(sender=sender,receiver=receiver,flow=flow,native_id=self.direct_sequence,
                source_stamp_ns=source_stamp_ns,bytes=len(body)+8,backend="IDEAL-DIRECT-ADAPTER",
                endpoint_capture_monotonic_ns=time.monotonic_ns())
            self.direct.append((meta,bytes(body),rpc_id))
        else:
            self.hub.send(sender,receiver,flow,body,rpc_id,source_stamp_ns,
                admission_ns=self.gz-self.anchor["offset_ns"])

    def install_wires(self):
        self.wires={}
        for side,node in (("C",self.c),("R",self.r)):
            self.wires[side]=TopicWire(node,side,self.send,bound_masks=True,runtime=True,
                health_trace=self.health_trace,
                central_map_capture=(self.retain_central_map
                    if side=='C' and self.central_map_captures is not None else None))
        self.bound_c=BoundMaskWire(self.c,"C",self.send,self.session_id,None)
        self.bound_r=BoundMaskWire(self.r,"R",self.send,self.session_id,
            lambda robot,binding,meta:self.guards[robot].guard.receive_bound(binding,meta))
        self.action_c=ActionWire(self.c,lambda peer,flow,body,rpc:self.send(0,peer,flow,body,rpc),
            session_id=self.session_id,reliable=True,transport_error=self.fail)
        self.action_r={r:ActionWire(self.r,
            lambda peer,flow,body,rpc,r=r:self.send(r,peer,flow,body,rpc),
            robot=r,session_id=self.session_id,guardian=self.guards[r],
            reliable=True,transport_error=self.fail) for r in (1,2,3)}
        if self.cpu_profile is not None:
            for side,wire in self.wires.items():
                outgoing=[flow for flow,spec in wire.specs.items()
                    if (side=='R')==(spec['direction']=='up')]
                for subscription,flow in zip(wire.subscriptions,outgoing):
                    self.profile_labels[subscription]=f'flow{flow}:{subscription.topic_name}'
            for robot,subscription in enumerate(self.bound_c.subscriptions,1):
                self.profile_labels[subscription]=f'flow{robot*20+10}:{subscription.topic_name}'
            for robot,action in self.action_r.items():
                self.profile_labels[action.timer]=f'action_readiness_tb{robot}'
                for offset,subscription in zip((6,7),action.subscriptions):
                    self.profile_labels[subscription]=f'flow{action.flow(robot,offset)}:{subscription.topic_name}'
            self.profile_labels[self.action_c.timer]='central_readiness_expiry'
        self.record("business_subscriptions_created",actual_wifi_handshake=self.mode!="A")
        self._idle_work_epoch+=1  # New endpoints may make a prior empty proof obsolete.

    def retain_central_map(self,body,row):
        # Passive references to the exact already serialized/hashed wire sample.
        self.central_map_captures.append((body,row,self.gz))

    def persist_central_maps(self):
        directory=self.directory/'central-map-capture'
        directory.mkdir()
        samples=[]
        for index,(body,row,gz) in enumerate(self.central_map_captures):
            filename=f'{index:06d}.cdr'
            with (directory/filename).open('xb') as stream:stream.write(body)
            samples.append(dict(row,cdr_file=filename,last_observed_R_clock_ns=gz))
        index=dict(scope='C_Gateway_capture',flow=89,topic='/merge_map',samples=samples,
            semantics='Original CDR at the C Gateway callback, not merge producer or HQ decision time. '
                'source_stamp_ns is the oldest contributing local-map header stamp, not generation time. '
                'capture_node_sim_ns is the C node ROS clock; last_observed_R_clock_ns is only the '
                'latest R /clock callback already processed by this Gateway. '
                'endpoint_capture_monotonic_ns is callback entry. SHA and length reuse the wire row. '
                'No sample is published from this capture; R receipt coverage remains a separate metric.')
        with (directory/'index.json').open('x') as stream:json.dump(index,stream)

    def profile_entity(self,entity):
        if entity in self.profile_labels:return self.profile_labels[entity]
        if entity is self.clock_sub:return 'control_clock'
        if entity is self.status_timer:return 'gateway_status_timer'
        if entity is self.journal_timer:return 'journal_timer'
        for robot,guard in self.guards.items():
            if entity is guard.timer:return f'guard_timer_tb{robot}'
        if hasattr(entity,'topic_name'):return 'subscription:'+entity.topic_name
        if hasattr(entity,'srv_name'):return type(entity).__name__+':'+entity.srv_name
        return type(entity).__name__

    def receive(self,meta,body,rpc):
        self.record("destination_complete_message",meta=meta,rpc_id=rpc,cdr_bytes=len(body))
        if self.failure is not None:
            self.record("post_fault_business_discarded",meta=meta,rpc_id=rpc,
                cdr_sha256=hashlib.sha256(body).hexdigest())
            return
        if self.link.receive(meta,body,rpc):return
        if self.wires is None:raise RuntimeError("Business received before link qualification")
        flow=meta["flow"]
        if flow>=200:
            self.record("action_CDR_actual_destination",meta=meta,rpc_id=rpc,
                cdr_sha256=hashlib.sha256(body).hexdigest())
            if meta["receiver"]==0:self.action_c.receive(meta["sender"],flow,body,rpc)
            else:self.action_r[meta["receiver"]].receive(meta["sender"],flow,body,rpc)
        elif flow in (30,50,70):self.bound_r.receive(meta,body,rpc)
        else:
            side="C" if meta["receiver"]==0 else "R"
            if side=="R" and flow in (31,51,71):
                guard=self.guards[meta['receiver']].guard
                row=None
                if self.health_trace is not None:
                    row=self.health_trace.stamp('R_health_intake',flow=flow,
                        native_message_id=meta.get('message_id',meta.get('native_id')),
                        old_sequence=None if guard.health is None else guard.health['sequence'],
                        old_receipt_mono_s=guard.health_receipt,armed=guard.armed,fault_before=guard.fault,
                        R_node_sim_before_ns=self.r.get_clock().now().nanoseconds,
                        last_native_ACK_before_ns=self.hub.horizon_ns)
                state=json.loads(deserialize_message(body,String).data)
                if row is not None:row.update(sequence=state['sequence'],
                    decode_end_mono_ns=time.monotonic_ns(),decode_end_thread_cpu_ns=time.thread_time_ns())
                try:
                    accepted=guard.receive_health(state)
                    if row is not None:row['returned']=accepted
                finally:
                    if row is not None:row.update(guard_end_mono_ns=time.monotonic_ns(),
                        guard_end_thread_cpu_ns=time.thread_time_ns(),
                        actual_receipt_mono_s=guard.health_receipt,fault_after=guard.fault,
                        R_node_sim_after_ns=self.r.get_clock().now().nanoseconds,
                        last_native_ACK_after_ns=self.hub.horizon_ns)
            self.wires[side].receive(meta,body,rpc)

    def arm(self,robot,response):
        response.success=self.failure is None and self.connected and self.guards[robot].guard.arm()
        response.message=json.dumps(dict(robot=robot,fault=self.guards[robot].guard.fault,
            reason=self.guards[robot].guard.reason()))
        self.record("real_R_arm_response",robot=robot,success=response.success)
        return response

    def status(self):
        clock_publishers=self.r.count_publishers('/clock')
        rpc_cleanup=dict(C_pending=0,R_pending=0,C_service_inflight=0,
            C_retired_services=0,C_unadmitted_unknown_total=0,
            C_rpc_confirmation_pending=0,R_rpc_confirmation_pending=0,
            rpc_delivery_unconfirmed=0,
            local_cleanup_pending=sum(not future.done() for guard in self.guards.values()
                for future in guard.futures))
        if self.wires is not None:
            rpc_cleanup.update(
                C_pending=sum(not future.done() for future,typ,generation in self.action_c.pending.values()),
                R_pending=sum(response is None for action in self.action_r.values()
                    for response in action.requests.values()),
                C_service_inflight=sum(state['inflight'] for states in
                    [*self.action_c.service_states.values(),*self.action_c.retired_services.values()]
                    for state in states),
                C_retired_services=sum(len(states) for states in self.action_c.retired_services.values()),
                C_unadmitted_unknown_total=self.action_c.blocked_requests,
                C_rpc_confirmation_pending=self.action_c.reliability_status()['waiting'],
                R_rpc_confirmation_pending=sum(a.reliability_status()['waiting'] for a in self.action_r.values()),
                rpc_delivery_unconfirmed=sum(a.reliability_status()['unconfirmed']
                    for a in (self.action_c,*self.action_r.values())))
        data=dict(mode=self.mode,session_id=self.session_id,connected=self.connected,
            failure=self.failure,anchor=self.anchor,gz_ns=self.gz,ns3_ns=self.hub.horizon_ns,
            gateway_monotonic_ns=time.monotonic_ns(),
            # This existing R executor timer runs after complete construction.
            clock_reader_ready=True,clock_publishers=clock_publishers,
            clock_writer_discovered=clock_publishers>0,
            actual_rpc_cleanup=rpc_cleanup,
            guards={str(r):dict(armed=g.guard.armed,fault=g.guard.fault,reason=g.guard.reason())
                for r,g in self.guards.items()})
        self.extend_status(data)
        self.last_status=data
        self.health_status.publish(String(data=json.dumps(data)))

    def extend_status(self,data):
        # Default A1/B/C status is unchanged; A0 adds actual direct ownership.
        return

    def export_controller_records(self):
        if self.cpu_profile is None:return self._export_controller_records()
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        try:return self._export_controller_records()
        finally:record_cpu_span(self.cpu_profile['progress'],'journal_call_inclusive',wall,cpu,
            self.profile_longspans,'C:journal_call_inclusive')

    def _export_controller_records(self):
        # This is a C-side source. Only actual delivered flow95 reaches R runtime.
        path=self.directory/"controller/allocation-events.jsonl"
        if not path.exists() or self.wires is None:return
        with open(path, opener=lambda filename, flags: os.open(filename, flags | os.O_NOATIME)) as stream:
            stream.seek(self.journal_position)
            while True:
                position=stream.tell();line=stream.readline()
                if not line or not line.endswith("\n"):
                    self.journal_position=position;return
                row=json.loads(line)
                if row.get("kind") in ("rl_actual_nav2_goal_request","rl_actual_nav2_goal_response","rl_actual_nav2_goal_result","rl_halt_requested"):
                    self.journal_pub.publish(String(data=line.rstrip("\n")))

    def fail(self,reason):
        if self.failure is not None:return
        self.failure=reason;self.record("transport_latched_INVALID",reason=reason)
        for guard in self.guards.values():guard.guard.trip(reason)
        if self.wires is not None:
            for action in (self.action_c,*self.action_r.values()):action.stop_reliability(reason)
            for robot in tuple(self.action_c.endpoints):self.action_c._set_ready(robot,False)
        # Stay alive to spin real R Cancel/GetResult/PAUSE and zero publishers.

    def poll(self):
        if self.python_profiler is not None:return self._profiled_poll()
        if self.cpu_profile is None:return self._poll()
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        try:return self._poll()
        finally:record_cpu_span(self.cpu_profile['progress'],'poll_inclusive',wall,cpu,
            self.profile_longspans,'poll_inclusive')

    def _profiled_poll(self):
        state=self.python_profile
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        if state['status']=='WAITING_NEXT_POLL':
            if self.failure or any(g.guard.fault for g in self.guards.values()):
                state.update(status='NOT_STARTED',stop_reason='first_fault_before_next_poll')
            else:
                state.update(status='ACTIVE',start_monotonic_ns=wall,start_thread_cpu_ns=cpu,
                    requested_end_monotonic_ns=wall+state['requested_wall_ns'])
        elif state['status']=='ACTIVE':
            faulted=self.failure or any(g.guard.fault for g in self.guards.values())
            if faulted or wall>=state['requested_end_monotonic_ns']:
                state.update(status='FINISHED',stop_reason='first_original_fault_before_next_poll'
                    if faulted else 'requested_window_before_next_poll',stop_observed_monotonic_ns=wall)
        capture=state['status']=='ACTIVE'
        if capture:self.python_profiler.enable()
        error=None
        try:return self._poll()
        except BaseException as caught:
            error=repr(caught)
            raise
        finally:
            if capture:self.python_profiler.disable()
            end=time.monotonic_ns();end_cpu=time.thread_time_ns()
            if self.cpu_profile is not None:
                record_cpu_span(self.cpu_profile['progress'],'poll_inclusive',wall,cpu,
                    self.profile_longspans,'poll_inclusive')
            if capture:
                state['profiled_polls']+=1;state['profiled_poll_wall_ns']+=end-wall
                state['profiled_poll_thread_cpu_ns']+=end_cpu-cpu
                state.update(end_monotonic_ns=end,end_thread_cpu_ns=end_cpu,
                    window_wall_ns=end-state['start_monotonic_ns'],
                    window_thread_cpu_ns=end_cpu-state['start_thread_cpu_ns'],
                    window_overrun_ns=max(0,end-state['requested_end_monotonic_ns']))
                faults={str(r):g.guard.fault for r,g in self.guards.items() if g.guard.fault}
                reason=('poll_exception' if error else 'first_original_fault' if faults or self.failure
                    else 'requested_window_at_poll_boundary' if end>=state['requested_end_monotonic_ns'] else None)
                if reason:
                    state.update(status='FINISHED',stop_reason=reason,original_guard_faults=faults,
                        original_Gateway_failure=self.failure,poll_error=error)

    def _poll(self):
        self._poll_transport_active=False
        self._tail_empty_epoch={side:None for side in ('C','R')}
        if self.control_clock_lane:
            self.control_clock_work_this_poll=False
            self._service_control_clock()
        now=time.monotonic()
        if self.last_poll is not None:self.dispatch_stats['max_poll_gap_wall_s']=max(
            self.dispatch_stats['max_poll_gap_wall_s'],now-self.last_poll)
        self.last_poll=now
        caps={side:sum(len(tuple(getattr(node,name))) for name in
            ('subscriptions','timers','clients','services','guards','waitables'))
            for side,node in zip(('C','R'),self.nodes)}
        used={side:0 for side in ('C','R')}
        spans={side:dict(wall=0.,cpu=0.) for side in ('C','R')}
        for state in self.ready_sets.values():state['shutdown']=False
        while True:
            productive=False
            for side,executor,node in zip(('C','R'),self.executors,self.nodes):
                if self.ready_sets[side]['shutdown']:continue
                before=time.monotonic();cpu=time.thread_time()
                if side=='C' and before<self.c_empty_until:
                    self.dispatch_stats['C']['empty_recheck_skips']+=1
                    continue
                limit=min(4,caps[side]-used[side])
                completed,_=drain_current_ready(executor,node,self.ready_sets[side],
                    self._after_ros_handler,callback_limit=limit,
                    profile=None if self.cpu_profile is None else self.cpu_profile[side],
                    entity_label=self.profile_entity,longspans=self.profile_longspans,side=side)
                if limit>0 and self.ready_sets[side].get('last_wait_kind')=='empty_set':
                    self._tail_empty_epoch[side]=self._idle_work_epoch
                if side=='C':
                    if completed:self.c_empty_until=0.
                    elif self.ready_sets[side].get('last_wait_kind')=='empty_set':
                        # Only an actually empty public query starts this fixed
                        # deadline; skipped probes never extend it. No sleep.
                        self.c_empty_until=time.monotonic()+.010
                        self.dispatch_stats['C']['empty_recheck_started']+=1
                spans[side]['wall']+=time.monotonic()-before
                spans[side]['cpu']+=time.thread_time()-cpu
                used[side]+=len(completed)
                productive=productive or bool(completed)
                for entity,began in completed:
                    for robot,guard in self.guards.items():
                        if entity is guard.timer:
                            timer=self.dispatch_stats['guard_timers'].setdefault(str(robot),dict(calls=0,max_gap_wall_s=0.,last=None))
                            if timer['last'] is not None:timer['max_gap_wall_s']=max(timer['max_gap_wall_s'],began-timer['last'])
                            timer['calls']+=1;timer['last']=began
            # Once an empty retry deadline is eligible, try that side again
            # after at most four other-side handlers.
            # Once either cap is used, defer all remaining work to the next poll.
            if not productive or any(used[side]>=caps[side] for side in ('C','R')):break
        for side in ('C','R'):
            stat=self.dispatch_stats[side];stat['batches']+=1;stat['callbacks']+=used[side]
            stat['cap_hits']+=int(used[side]==caps[side])
            stat['max_wall_s']=max(stat['max_wall_s'],spans[side]['wall'])
            stat['max_cpu_s']=max(stat['max_cpu_s'],spans[side]['cpu'])
        self.progress_transport()
        if 'start' in self.idle_phase_snapshots and 'end' not in self.idle_phase_snapshots:
            if self.failure or any(g.guard.fault for g in self.guards.values()):
                self._snapshot_idle_phase('end','first_fault_observed_at_original_poll_end')
        self._wait_when_idle(used)

    def _after_ros_handler(self):
        self._idle_work_epoch+=1  # Includes ready Task/Future continuation and topology work.
        if self.control_clock_lane:self._service_control_clock()
        self.progress_transport()

    def _snapshot_idle_phase(self, name, reason):
        self.idle_phase_snapshots[name]=dict(monotonic_ns=time.monotonic_ns(),reason=reason,
            work_epoch=self._idle_work_epoch,counters=dict(self.dispatch_stats['idle_wait']),
            scope='First C capture is later than client normal_start; end is poll-boundary observation or exit')

    def _wait_when_idle(self, used):
        stat=self.dispatch_stats['idle_wait']
        if (self.direct or self.hub.outgoing or self.failure or self.hub_poll_closed or not all(
                    state.get('last_wait_kind')=='empty_set' and not state['productive']
                    and not state['shutdown'] for state in self.ready_sets.values())):
            stat['backlog_or_stopped_rejections']+=1
            return
        if self.control_clock_lane and not (
                self.control_clock_ready_set['last_wait_kind']=='empty_set'
                and not self.control_clock_ready_set['productive']
                and not self.control_clock_ready_set['shutdown']
                and self.control_clock_empty_epoch==self._idle_work_epoch):
            self.control_clock_stats['idle_rejections']+=1
            return
        historical=bool(any(used.values()) or self._poll_transport_active or
            (self.control_clock_lane and self.control_clock_work_this_poll))
        if historical:
            if not all(epoch==self._idle_work_epoch for epoch in self._tail_empty_epoch.values()):
                stat['stale_empty_rejections']+=1
                return
            stat['history_only_eligible']+=1
        # Without historical work, retain the original allowed path even when
        # C only skipped its existing10ms deadline. Freshness is extra-path only.
        deadline=min(time.monotonic()+.001,self.c_empty_until)
        for guard in self.guards.values():
            before=time.monotonic();remaining=guard.timer.time_until_next_call()
            if remaining is not None:deadline=min(deadline,before+remaining/1_000_000_000)
        timeout=deadline-time.monotonic()
        if timeout<=0:
            stat['deadline_rejections']+=1
            return
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        readable=self.hub.wait_readable(timeout)
        elapsed=time.monotonic_ns()-wall;used_cpu=time.thread_time_ns()-cpu
        requested=int(timeout*1_000_000_000)
        stat['tail_quiet_idle' if historical else 'original_idle']+=1
        stat['calls']+=1;stat['requested_ns']+=requested;stat['wall_ns']+=elapsed
        stat['thread_cpu_ns']+=used_cpu;stat['readable']+=int(readable)
        stat['max_requested_ns']=max(stat['max_requested_ns'],requested)
        stat['max_wall_ns']=max(stat['max_wall_ns'],elapsed)
        stat['max_overrun_ns']=max(stat['max_overrun_ns'],elapsed-requested)
        if self.cpu_profile is not None:
            record_cpu_span(self.cpu_profile['progress'],'idle_event_wait',wall,cpu,
                self.profile_longspans,'idle_event_wait')

    def progress_transport(self):
        if self.cpu_profile is None:return self._progress_transport()
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        try:return self._progress_transport()
        finally:record_cpu_span(self.cpu_profile['progress'],'total_inclusive',wall,cpu,
            self.profile_longspans,'progress_inclusive')

    def _progress_transport(self):
        # Called between completed ROS handlers as well as at the outer boundary.
        # Never wait for native progress or replace actual receipts with a cache.
        if not self.hub_poll_closed:
            if self.cpu_profile is not None:wall=time.monotonic_ns();cpu=time.thread_time_ns()
            try:
                active=bool(self.hub.poll())
                self._poll_transport_active=active or self._poll_transport_active
                if active:self._idle_work_epoch+=1  # Conservative: partial IO also invalidates proof.
            except (EOFError,ConnectionError,OSError) as error:
                self.hub_poll_closed=True
                self.record("owned_transport_poll_closed",error=repr(error))
                self.fail(repr(error))
            finally:
                if self.cpu_profile is not None:record_cpu_span(self.cpu_profile['progress'],'hub_poll',wall,cpu,
                    self.profile_longspans,'progress:hub_poll')
        if self.failure:return
        if self.anchor is None or not self.hub.ready:return
        latest=self.gz-self.anchor["offset_ns"]
        if latest-self.hub.horizon_ns>120_000_000:
            self.fail("mapped_ns3_clock_lag_above_0.12sim");return
        if self.step_pending is not None and self.hub.horizon_ns>=self.step_pending:self.step_pending=None
        if self.step_pending is None and latest>self.hub.horizon_ns:
            self.step_pending=min(latest,self.hub.horizon_ns+self.step_quantum_ns)
            self.hub.clock(self.step_pending)
        if self.mode=="A":
            if not self.connected:
                self.connected=True;self.install_wires()
            # Fixed current batch only; responses enqueue for a later loop turn.
            if self.cpu_profile is not None:wall=time.monotonic_ns();cpu=time.thread_time_ns()
            direct_work=bool(self.direct)
            try:
                self._poll_transport_active=direct_work or self._poll_transport_active
                for _ in range(len(self.direct)):
                    meta,body,rpc=self.direct.popleft()
                    meta["endpoint_receive_monotonic_ns"]=time.monotonic_ns()
                    self.receive(meta,body,rpc)
            finally:
                if direct_work:self._idle_work_epoch+=1
                if self.cpu_profile is not None:record_cpu_span(self.cpu_profile['progress'],'direct_batch',wall,cpu,
                    self.profile_longspans,'progress:direct_batch')
        else:
            if not self.link.sent and self.hub.horizon_ns>=600_000_000:self.link.begin()
            if self.link.ready and not self.connected:
                self.connected=True;self.install_wires()
        if self.wires is not None:
            # B/C hub.poll and A's fixed current direct batch have both run.
            # receive itself still rejects a packet processed after expiry.
            for action in (self.action_c,*self.action_r.values()):
                action.reliability_tick()
                if self.failure:return

    def poststop_phase(self,phase,**fields):
        if self.execution_profile is None or not self.execution_profile.get('gateway_poststop_evidence_total_wall_s'):
            return
        row=dict(phase=phase,pid=os.getpid(),session_id=self.session_id,
            case=str(self.directory.resolve()),monotonic_ns=time.monotonic_ns(),**fields)
        with (self.directory/'network-gateway-close-phases.jsonl').open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        if phase=='resources_closed':
            temporary=self.directory/('network-gateway-resources-closed.'+str(os.getpid())+'.tmp')
            with temporary.open('x') as stream:stream.write(json.dumps(row)+'\n')
            temporary.replace(self.directory/'network-gateway-resources-closed.json')

    def persist(self):
        persist_begin=time.monotonic()
        if 'hub_shutdown' in self.cleanup:
            with (self.directory/'hub-poststop-opaque.bin').open('xb') as stream:
                stream.write(self.hub.finish_tail)
        if self.central_map_captures is not None:self.persist_central_maps()
        if 'end' not in self.idle_phase_snapshots:self._snapshot_idle_phase('end','owned_exit')
        if self.python_profile is not None:
            state=self.python_profile
            if state['status']=='ACTIVE':state.update(status='FINISHED',stop_reason='owned_loop_ended')
            elif state['status']=='WAITING_NEXT_POLL':
                state.update(status='NOT_STARTED',stop_reason='trigger_without_next_poll')
            elif state['status']=='NOT_STARTED':state.setdefault('stop_reason','no_real_C_Goal_trigger')
            if state['profiled_polls']:
                path=self.directory/'gateway-thread-cpu.pstats'
                self.python_profiler.dump_stats(str(path));state['stats_file']=str(path.name)
        data=dict(mode=self.mode,anchor=self.anchor,failure=self.failure,
            adapter_qos_events=self.adapter_qos_events,
            execution_profile=self.execution_profile,
            transport_poll_closed=self.hub_poll_closed,
            dispatch_stats=self.dispatch_stats,gc_runtime=self.gc_runtime,
            idle_phase_snapshots=self.idle_phase_snapshots,
            cleanup=self.cleanup,
            records=self.records,link=self.link.events,
            guards={str(r):dict(events=g.guard.events,actions=g.records,
                owned_unknown_or_active=sorted(g.owned),terminals=g.terminals,
                receipt_clock_basis=g.guard.receipt_clock_basis,
                health_receipt_monotonic=g.guard.health_receipt,mask_receipt_monotonic=g.guard.mask_receipt,
                health_receipt_sim=g.guard.health_receipt_sim,mask_receipt_sim=g.guard.mask_receipt_sim,
                control_permission_revoked=g.guard.halted) for r,g in self.guards.items()},
            hub_deliveries=self.hub.deliveries)
        if self.wires is not None:
            data["topics"]={side:dict(captured=w.captured,delivered=w.delivered) for side,w in self.wires.items()}
            data["bound_masks"]=self.bound_r.received
            data['action_reliability']=dict(C=self.action_c.reliability_snapshot(),
                R={str(r):a.reliability_snapshot() for r,a in self.action_r.items()})
        if self.control_clock_lane:
            data['gateway_control_clock_lane']=dict(version='separate-executor-v1',
                statistics=self.control_clock_stats,ready_state=self.control_clock_ready_set,
                empty_epoch=self.control_clock_empty_epoch,
                semantics='Only explicit actual R /clock reader moved; original R/C TimeSource, Gateway.clock and single Hub FIFO/STEP owner remain. Callback/cap ordering and achieved wall workload may change.')
        if self.cpu_profile is not None:
            data['health_trace']=self.health_trace.snapshot()
            data['dispatch_cpu_profile']=dict(aggregates=self.cpu_profile,longspans=self.profile_longspans,gc_events=self.gc_events,
                longspan_semantics='RAM spans >=10ms; end-order append. Poll includes all work; handler includes journal_call; progress total includes hub/direct. Inclusive parents and children must not be summed. Diagnostic timing overhead, not capacity proof.',
                semantics='wait and handler totals exclude progress; progress total_inclusive contains hub_poll/direct_batch, not sibling idle_event_wait. Poll includes all work and idle; do not sum parent and children. Async handler measures executing step only, not pending Future time. RAM only, diagnostic opt-in.')
        if self.main_thread_sampler is not None:
            data['main_thread_sampling']=self.main_thread_sampler.snapshot()
        if self.python_profile is not None:data['gateway_python_cpu_profile']=dict(self.python_profile)
        if self.hub.control_trace is not None:
            data['clock_control_trace']=dict(events=self.hub.control_trace,
                semantics='Socket frame flushed means all its bytes accepted by kernel, not hub/native ACK. Offsets count the entire ordered stream, including non-clock frames.')
        with (self.directory/"network-gateway.json").open("x") as stream:stream.write(json.dumps(data))
        (self.directory/"network-gateway-saved.json").write_text(json.dumps(dict(saved=True,
            mode=self.mode,records=len(self.records),failure=self.failure,
            cleanup=self.cleanup,persist_wall_s=time.monotonic()-persist_begin,
            peak_afterpersist_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))+"\n")

    def close(self):
        self.poststop_phase("close_begin")
        try:clean=self._close()
        finally:
            if self.main_thread_sampler is not None:
                self.cleanup['main_thread_sampler']=self.main_thread_sampler.stop()
            self.gc_runtime['processing_end_monotonic_ns']=time.monotonic_ns()
            self.gc_runtime['processing_end_enabled']=gc.isenabled()
            if self.gc_original_enabled:gc.enable()
            else:gc.disable()
            if self.gc_callback is not None:gc.callbacks.remove(self.gc_callback)
            self.gc_runtime.update(restored_enabled=gc.isenabled(),
                restored_thresholds=gc.get_threshold(),restored_monotonic_ns=time.monotonic_ns(),
                peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if self.main_thread_sampler is not None:
            status=self.cleanup['main_thread_sampler']
            clean=clean and status['joined'] and status['failure'] is None
        safe_closed=(clean and self.cleanup['resources_destroyed']
            and all(self.cleanup['executor_shutdown'])
            and not self.cleanup['unresolved_C_RPC'] and not self.cleanup['unresolved_R_RPC']
            and not any(self.cleanup['unresolved_local_cleanup_futures'].values()))
        self.poststop_phase('resources_closed',safe_closed=bool(safe_closed),cleanup=self.cleanup)
        self.poststop_phase('persist_begin')
        self.persist()
        self.poststop_phase('persist_end')
        self.poststop_phase('close_return',clean=bool(clean))
        return clean

    def _close(self):
        self.cleanup=dict(phase="after_supervisor_stop_and_owned_cleanup_attempts",
            end_frame_flushed=False,executor_shutdown=[],resources_destroyed=False,
            unresolved_C_RPC=[],unresolved_R_RPC=[],unresolved_local_cleanup_futures={})
        if self.wires is not None:
            self.cleanup['action_confirmation_states']=dict(C=self.action_c.reliability_status(),
                R={str(r):a.reliability_status() for r,a in self.action_r.items()})
            for action in (self.action_c,*self.action_r.values()):action.stop_reliability('owned_shutdown')
            self.cleanup["unresolved_C_RPC"]=[dict(robot=r,flow_offset=f,rpc_id=i)
                for (r,f,i),(future,typ,generation) in self.action_c.pending.items() if not future.done()]
            self.cleanup["retired_C_services"]={str(r):[dict(flow_offset=s['offset'],inflight=s['inflight']) for s in states]
                for r,states in self.action_c.retired_services.items()}
            self.cleanup["unresolved_R_RPC"]=[dict(robot=r,flow=f,rpc_id=i)
                for r,action in self.action_r.items() for (f,i),response in action.requests.items() if response is None]
        self.cleanup["unresolved_local_cleanup_futures"]={str(r):sum(not f.done() for f in guard.futures)
            for r,guard in self.guards.items()}
        # Poststop only: the original total 3wall now covers END and peer EOF.
        # Kernel acceptance is not Hub receipt; keep the read side open while
        # Hub drains its already generated output and consumes the ordered END.
        if self.hub_poll_closed:
            self.record("owned_END_not_sent_channel_closed")
        else:
            deadline_ns=time.monotonic_ns()+3_000_000_000
            try:
                self.hub.finish_poststop(deadline_ns)
            except (EOFError,ConnectionError,OSError) as error:
                self.hub_poll_closed=True
                self.record("owned_END_failed",error=repr(error))
                self.hub.finish_state['error']=repr(error)
            finally:
                self.cleanup['hub_shutdown']=self.hub.finish_state
                self.cleanup['end_frame_flushed']=self.hub.finish_state['end_frame_flushed']
        self.hub.close()
        if self.control_clock_lane:
            self.cleanup['control_clock_executor_shutdown']=self._close_control_clock_lane()
        for executor,node,context in zip(self.executors,self.nodes,self.contexts):
            executor.remove_node(node)
            self.cleanup["executor_shutdown"].append(executor.shutdown(timeout_sec=0))
            node.destroy_node();context.shutdown()
        self.cleanup["resources_destroyed"]=True
        # Saved means successful persistence after bounded teardown, not a
        # synthetic response/terminal for any unresolved callback above.
        confirmations=self.cleanup.get('action_confirmation_states')
        drained=(confirmations is None or all(not s['waiting'] and not s['unconfirmed']
            for s in (confirmations['C'],*confirmations['R'].values())))
        return (self.cleanup["end_frame_flushed"]
            and self.cleanup.get('hub_shutdown',{}).get('peer_eof',False)
            and 'error' not in self.cleanup['hub_shutdown'] and self.failure is None and drained
            and (not self.control_clock_lane or self.cleanup['control_clock_executor_shutdown']))


def main(*,gateway_factory=Gateway):
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("A","B","C"),required=True)
    parser.add_argument("--socket",type=Path,required=True)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--session-id",type=int,required=True)
    parser.add_argument('--control-trace',action='store_true')
    parser.add_argument('--dispatch-profile',action='store_true')
    parser.add_argument('--dds-take-trace',action='store_true')
    parser.add_argument('--main-thread-sample',action='store_true')
    parser.add_argument('--gateway-cprofile',action='store_true')
    parser.add_argument('--capture-central-map',action='store_true')
    parser.add_argument('--adapter-qos-events',choices=('sdk-default','warning-free-v1'),default='sdk-default')
    parser.add_argument('--execution-profile')
    args=parser.parse_args()
    node=gateway_factory(args.mode,args.socket,args.directory,args.session_id,dispatch_profile=args.dispatch_profile,
        control_trace=args.control_trace,execution_profile=args.execution_profile,dds_take_trace=args.dds_take_trace,
        main_thread_sample=args.main_thread_sample,gateway_cprofile=args.gateway_cprofile,
        adapter_qos_events=args.adapter_qos_events,capture_central_map=args.capture_central_map)
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    try:
        while not stopping:
            try:node.poll()
            except Exception as error:node.fail(repr(error))
    finally:clean=node.close()
    node.poststop_phase("main_return",exit_code=0 if clean else 1)
    return 0 if clean else 1


if __name__=="__main__":raise SystemExit(main())

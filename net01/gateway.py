"""NET-01 two-domain composition. Only delivery backend differs in A/B/C.

The R executor is never run by the ns-3/hub process. Native IPC is polled
without waiting; its EOF latches all local stops and does not stop R callbacks.
All records are RAM captures, persisted only after the owned loop exits.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import signal
import time

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


def record_cpu_span(table,key,wall,cpu):
    elapsed=time.monotonic_ns()-wall;used=time.thread_time_ns()-cpu
    row=table.setdefault(key,dict(calls=0,wall_ns=0,thread_cpu_ns=0,max_wall_ns=0))
    row['calls']+=1;row['wall_ns']+=elapsed;row['thread_cpu_ns']+=used
    row['max_wall_ns']=max(row['max_wall_ns'],elapsed)


def drain_current_ready(executor,node,ready_set,after_handler=None,callback_limit=None,
                        profile=None,entity_label=None):
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
            if not ready_set['productive']:break
            ready_set['productive']=False
            continue
        except ShutdownException:
            wait_kind='shutdown'
            ready_set['shutdown']=True
            break
        finally:
            if profile is not None:record_cpu_span(profile['wait'],wait_kind,wait_wall,wait_cpu)
        began=time.monotonic()
        if profile is not None:handler_wall=time.monotonic_ns();handler_cpu=time.thread_time_ns()
        try:
            handler()
            if handler.exception() is not None:raise handler.exception()
            handler.result()
        finally:
            if profile is not None:record_cpu_span(profile['handlers'],entity_label(entity),handler_wall,handler_cpu)
        completed.append((entity,began))
        ready_set['productive']=True
        if after_handler is not None:after_handler()
    return completed,cap


class Gateway:
    def __init__(self, mode, socket, directory, session_id, *, dispatch_profile=False,control_trace=False):
        self.mode,self.directory,self.session_id=mode,Path(directory),session_id
        self.records=[];self.direct=deque();self.direct_sequence=0
        self.contexts=[];self.nodes=[];self.executors=[]
        self.ready_sets={side:dict(productive=False) for side in ('C','R')}
        self.c_empty_until=0.
        self.dispatch_stats=dict(C=dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.,empty_recheck_started=0,empty_recheck_skips=0),
            R=dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.),
            guard_timers={},max_poll_gap_wall_s=0.,
            schedule='C/R cached handlers alternate in fixed quantum4; stop after a pair when either initial cap is used',
            side_span_semantics='max_wall/cpu are accumulated side service time per poll, including pump; not contiguous batches or single-callback spans')
        self.cpu_profile=(dict(C=dict(wait={},handlers={}),R=dict(wait={},handlers={}),progress={})
            if dispatch_profile else None)
        self.profile_labels={}
        self.last_poll=None
        for domain,side in ((91,"C"),(92,"R")):
            context=Context()
            rclpy.init(context=context,domain_id=domain,signal_handler_options=SignalHandlerOptions.NO)
            node=Node("net01_gateway_"+side.lower(),context=context,
                parameter_overrides=[Parameter("use_sim_time",value=True)])
            executor=SingleThreadedExecutor(context=context);executor.add_node(node)
            self.contexts.append(context);self.nodes.append(node);self.executors.append(executor)
        self.c,self.r=self.nodes
        self.hub=HubClient(socket,control_trace=control_trace);self.hub.receive=self.receive
        self.link=LinkSession(self,session_id)
        self.guards={r:LocalStop(self.r,r,session_id) for r in (1,2,3)}
        self.anchor=None;self.gz=None;self.previous_clock=None;self.step_pending=None
        self.connected=False;self.failure=None;self.wires=None
        self.health_status=self.r.create_publisher(String,"/net01/gateway_state",
            QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.clock_pub=self.c.create_publisher(ClockMessage,"/clock",qos_profile_sensor_data)
        self.clock_sub=self.r.create_subscription(ClockMessage,"/clock",self.clock,qos_profile_sensor_data)
        self.models_sub=self.r.create_subscription(ModelStates,"/gazebo/model_states",self.models,qos_profile_sensor_data)
        self.arm_services=[self.r.create_service(Trigger,f"/net01/tb{r}/arm",
            lambda req,resp,r=r:self.arm(r,resp)) for r in (1,2,3)]
        self.status_timer=self.r.create_timer(.05,self.status,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.journal_position=0
        self.journal_pub=self.c.create_publisher(String,"/net01/controller_records",100)
        self.journal_timer=self.c.create_timer(.02,self.export_controller_records,
            clock=Clock(clock_type=ClockType.STEADY_TIME))

    def record(self,kind,**fields):
        self.records.append(dict(dict(kind=kind,monotonic_ns=time.monotonic_ns(),gz_ns=self.gz),**fields))

    def clock(self,message):
        gz=message.clock.sec*1_000_000_000+message.clock.nanosec
        self.clock_pub.publish(message)  # Independent simulation control, no business fields.
        if self.anchor is None:
            self.anchor=dict(gazebo_ns=gz,ns3_ns=0,offset_ns=gz,monotonic_ns=time.monotonic_ns())
            self.record("fixed_clock_anchor",**self.anchor)
        if self.previous_clock is not None and gz<self.previous_clock:
            self.fail("gazebo_clock_rollback")
        self.previous_clock=self.gz=gz
        if self.failure is None:self.hub.observed_clock(gz-self.anchor["offset_ns"])
        self.record("actual_R_clock_relayed_C",gazebo_ns=gz)

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
            self.wires[side]=TopicWire(node,side,self.send,bound_masks=True,runtime=True)
        self.bound_c=BoundMaskWire(self.c,"C",self.send,self.session_id,None)
        self.bound_r=BoundMaskWire(self.r,"R",self.send,self.session_id,
            lambda robot,binding,meta:self.guards[robot].guard.receive_bound(binding,meta))
        self.action_c=ActionWire(self.c,lambda peer,flow,body,rpc:self.send(0,peer,flow,body,rpc),
            session_id=self.session_id)
        self.action_r={r:ActionWire(self.r,
            lambda peer,flow,body,rpc,r=r:self.send(r,peer,flow,body,rpc),
            robot=r,session_id=self.session_id,guardian=self.guards[r]) for r in (1,2,3)}
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
                state=json.loads(deserialize_message(body,String).data)
                self.guards[meta["receiver"]].guard.receive_health(state)
            self.wires[side].receive(meta,body,rpc)

    def arm(self,robot,response):
        response.success=self.failure is None and self.connected and self.guards[robot].guard.arm()
        response.message=json.dumps(dict(robot=robot,fault=self.guards[robot].guard.fault,
            reason=self.guards[robot].guard.reason()))
        self.record("real_R_arm_response",robot=robot,success=response.success)
        return response

    def status(self):
        data=dict(mode=self.mode,session_id=self.session_id,connected=self.connected,
            failure=self.failure,anchor=self.anchor,gz_ns=self.gz,ns3_ns=self.hub.horizon_ns,
            gateway_monotonic_ns=time.monotonic_ns(),
            guards={str(r):dict(armed=g.guard.armed,fault=g.guard.fault,reason=g.guard.reason())
                for r,g in self.guards.items()})
        self.health_status.publish(String(data=json.dumps(data)))

    def export_controller_records(self):
        # This is a C-side source. Only actual delivered flow95 reaches R runtime.
        path=self.directory/"controller/allocation-events.jsonl"
        if not path.exists() or self.wires is None:return
        with path.open() as stream:
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
            for robot in tuple(self.action_c.endpoints):self.action_c._set_ready(robot,False)
        # Stay alive to spin real R Cancel/GetResult/PAUSE and zero publishers.

    def poll(self):
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
                completed,_=drain_current_ready(executor,node,self.ready_sets[side],
                    self.progress_transport,callback_limit=min(4,caps[side]-used[side]),
                    profile=None if self.cpu_profile is None else self.cpu_profile[side],
                    entity_label=self.profile_entity)
                if side=='C':
                    if completed:self.c_empty_until=0.
                    elif not self.ready_sets[side]['shutdown']:
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

    def progress_transport(self):
        if self.cpu_profile is None:return self._progress_transport()
        wall=time.monotonic_ns();cpu=time.thread_time_ns()
        try:return self._progress_transport()
        finally:record_cpu_span(self.cpu_profile['progress'],'total_inclusive',wall,cpu)

    def _progress_transport(self):
        # Called between completed ROS handlers as well as at the outer boundary.
        # Never wait for native progress or replace actual receipts with a cache.
        if self.failure:return
        if self.cpu_profile is not None:wall=time.monotonic_ns();cpu=time.thread_time_ns()
        try:self.hub.poll()
        finally:
            if self.cpu_profile is not None:record_cpu_span(self.cpu_profile['progress'],'hub_poll',wall,cpu)
        if self.anchor is None or not self.hub.ready:return
        latest=self.gz-self.anchor["offset_ns"]
        if latest-self.hub.horizon_ns>120_000_000:
            self.fail("mapped_ns3_clock_lag_above_0.12sim");return
        if self.step_pending is not None and self.hub.horizon_ns>=self.step_pending:self.step_pending=None
        if self.step_pending is None and latest>self.hub.horizon_ns:
            self.step_pending=min(latest,self.hub.horizon_ns+100_000_000)
            self.hub.clock(self.step_pending)
        if self.mode=="A":
            if not self.connected:
                self.connected=True;self.install_wires()
            # Fixed current batch only; responses enqueue for a later loop turn.
            if self.cpu_profile is not None:wall=time.monotonic_ns();cpu=time.thread_time_ns()
            try:
                for _ in range(len(self.direct)):
                    meta,body,rpc=self.direct.popleft()
                    meta["endpoint_receive_monotonic_ns"]=time.monotonic_ns()
                    self.receive(meta,body,rpc)
            finally:
                if self.cpu_profile is not None:record_cpu_span(self.cpu_profile['progress'],'direct_batch',wall,cpu)
        else:
            if not self.link.sent and self.hub.horizon_ns>=600_000_000:self.link.begin()
            if self.link.ready and not self.connected:
                self.connected=True;self.install_wires()

    def persist(self):
        data=dict(mode=self.mode,anchor=self.anchor,failure=self.failure,
            dispatch_stats=self.dispatch_stats,
            cleanup=self.cleanup,
            records=self.records,link=self.link.events,
            guards={str(r):dict(events=g.guard.events,actions=g.records,
                owned_unknown_or_active=sorted(g.owned),terminals=g.terminals) for r,g in self.guards.items()},
            hub_deliveries=self.hub.deliveries)
        if self.wires is not None:
            data["topics"]={side:dict(captured=w.captured,delivered=w.delivered) for side,w in self.wires.items()}
            data["bound_masks"]=self.bound_r.received
        if self.cpu_profile is not None:
            data['dispatch_cpu_profile']=dict(aggregates=self.cpu_profile,
                semantics='wait and handler totals exclude progress; progress total_inclusive contains hub_poll/direct_batch; do not sum parent and children. Async handler measures executing step only, not pending Future time. RAM only, diagnostic opt-in.')
        if self.hub.control_trace is not None:
            data['clock_control_trace']=dict(events=self.hub.control_trace,
                semantics='Socket frame flushed means all its bytes accepted by kernel, not hub/native ACK. Offsets count the entire ordered stream, including non-clock frames.')
        with (self.directory/"network-gateway.json").open("x") as stream:json.dump(data,stream)
        (self.directory/"network-gateway-saved.json").write_text(json.dumps(dict(saved=True,
            mode=self.mode,records=len(self.records),failure=self.failure,
            cleanup=self.cleanup))+"\n")

    def close(self):
        self.cleanup=dict(phase="after_supervisor_stop_and_owned_cleanup_attempts",
            end_frame_flushed=False,executor_shutdown=[],resources_destroyed=False,
            unresolved_C_RPC=[],unresolved_R_RPC=[],unresolved_local_cleanup_futures={})
        if self.wires is not None:
            self.cleanup["unresolved_C_RPC"]=[dict(robot=r,flow_offset=f,rpc_id=i)
                for (r,f,i),(future,typ,generation) in self.action_c.pending.items() if not future.done()]
            self.cleanup["unresolved_R_RPC"]=[dict(robot=r,flow=f,rpc_id=i)
                for r,action in self.action_r.items() for (f,i),response in action.requests.items() if response is None]
        self.cleanup["unresolved_local_cleanup_futures"]={str(r):sum(not f.done() for f in guard.futures)
            for r,guard in self.guards.items()}
        self.hub.end()
        # This bounded flush is after stop/owned launch cleanup, never a guard
        # delay in the active loop. A failed END remains a separate hub failure.
        until=time.monotonic()+3
        try:
            while self.hub.outgoing and time.monotonic()<until:self.hub.poll()
            self.cleanup["end_frame_flushed"]=not self.hub.outgoing
            if self.hub.outgoing:self.record("owned_END_not_fully_flushed")
        except (EOFError,ConnectionError,OSError) as error:self.record("owned_END_failed",error=repr(error))
        self.hub.close()
        for executor,node,context in zip(self.executors,self.nodes,self.contexts):
            executor.remove_node(node)
            self.cleanup["executor_shutdown"].append(executor.shutdown(timeout_sec=0))
            node.destroy_node();context.shutdown()
        self.cleanup["resources_destroyed"]=True
        # Saved means successful persistence after bounded teardown, not a
        # synthetic response/terminal for any unresolved callback above.
        self.persist()
        return self.cleanup["end_frame_flushed"] and self.failure is None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("A","B","C"),required=True)
    parser.add_argument("--socket",type=Path,required=True)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--session-id",type=int,required=True)
    args=parser.parse_args()
    node=Gateway(args.mode,args.socket,args.directory,args.session_id)
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
    return 0 if clean else 1


if __name__=="__main__":raise SystemExit(main())

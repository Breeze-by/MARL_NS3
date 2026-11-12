"""Real SDK/domain121 and real Unix IPC; zero robot/Action/native/Gazebo.

Load only actual adapter methods. The subject supplies real SDK executors and
records test-only kernel readiness; no production Gateway/guard is constructed.
"""
import argparse
import ast
from collections import deque
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
from types import MethodType, SimpleNamespace
import traceback

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor, TimeoutException, ShutdownException
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.task import Future
from std_msgs.msg import Int32
from std_srvs.srv import Empty

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'net01'))
from hub_client import HubClient
HARD=time.monotonic()+10


def until(predicate,pump):
    end=min(HARD,time.monotonic()+2)
    while not predicate():
        if time.monotonic()>=end:raise TimeoutError('SDK fixture bound')
        pump()


def methods():
    path=ROOT/'net01/gateway.py';tree=ast.parse(path.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Gateway')
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)
              and n.name in ('drain_current_ready','record_cpu_span')]
    selected += [n for n in cls.body if isinstance(n,ast.FunctionDef)
                 and n.name in ('_poll','_wait_when_idle','_progress_transport','_after_ros_handler')]
    ns=dict(time=time,TimeoutException=TimeoutException,ShutdownException=ShutdownException)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),ns)
    return ns


class CountedExecutor(SingleThreadedExecutor):
    def __init__(self,context):
        super().__init__(context=context);self.fresh_generators=0
    def _wait_for_ready_callbacks(self,*args,**kwargs):
        self.fresh_generators+=1
        yield from super()._wait_for_ready_callbacks(*args,**kwargs)


class HeldRows:
    def __init__(self,executor,rows):self.executor,self.rows=executor,deque(rows)
    def wait_for_ready_callbacks(self,**kwargs):
        return self.rows.popleft() if self.rows else self.executor.wait_for_ready_callbacks(**kwargs)


class YieldOnce:
    def __await__(self):yield None


def subject(ns,c,r,ce,re,hub):
    def side():return dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.,
        empty_recheck_started=0,empty_recheck_skips=0)
    idle=dict(calls=0,requested_ns=0,wall_ns=0,thread_cpu_ns=0,readable=0,
        max_requested_ns=0,max_wall_ns=0,max_overrun_ns=0,original_idle=0,tail_quiet_idle=0,
        history_only_eligible=0,stale_empty_rejections=0,backlog_or_stopped_rejections=0,deadline_rejections=0)
    s=SimpleNamespace(nodes=(c,r),executors=(ce,re),ready_sets={name:dict(productive=False)
        for name in ('C','R')},last_poll=None,c_empty_until=0.,cpu_profile=None,
        profile_longspans=None,profile_entity=lambda e:'unused',guards={},hub=hub,
        hub_poll_closed=False,failure=None,anchor=None,direct=deque(),_poll_transport_active=False,
        _idle_work_epoch=0,_tail_empty_epoch=dict(C=None,R=None),idle_phase_snapshots={},
        dispatch_stats=dict(C=side(),R=side(),guard_timers={},max_poll_gap_wall_s=0.,idle_wait=idle),
        record=lambda *args,**kwargs:None)
    s.fail=lambda cause:setattr(s,'failure',cause)
    for name in ('_poll','_wait_when_idle','_progress_transport','_after_ros_handler'):
        setattr(s,name,MethodType(ns[name],s))
    s.progress_transport=s._progress_transport
    return s


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    context=Context();nodes=[];executors=[];hub=peer=listener=None;result={};checks={};started=time.monotonic()
    temp=tempfile.TemporaryDirectory(prefix='net01d-idle-')
    rclpy.init(context=context,domain_id=121,signal_handler_options=SignalHandlerOptions.NO)
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    try:
        ns=methods();source=Node('idle_source',context=context)
        c=Node('idle_c',context=context);r=Node('idle_r',context=context);nodes.extend((source,c,r))
        ce,re=CountedExecutor(context),CountedExecutor(context)
        ce.add_node(c);re.add_node(r);executors.extend((ce,re))
        path=Path(temp.name)/'h.sock';listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        listener.bind(str(path));listener.listen();hub=HubClient(path);peer,_=listener.accept();peer.setblocking(False)
        s=subject(ns,c,r,ce,re,hub);requests=[];real_wait=hub.wait_readable
        def measured_wait(timeout):
            before=time.monotonic_ns();ready=real_wait(timeout)
            requests.append(dict(request_ns=int(timeout*1e9),begin_ns=before,end_ns=time.monotonic_ns(),ready=ready))
            return ready
        hub.wait_readable=measured_wait
        received=[];pubs=[];subs=[]
        for i in range(4):
            topic=f'/net01d_idle_check/value{i}'
            subs.append(c.create_subscription(Int32,topic,lambda msg:received.append(msg.data),10))
            pubs.append(source.create_publisher(Int32,topic,10))
        rsub=r.create_subscription(Int32,'/net01d_idle_check/unused',lambda msg:None,10)
        until(lambda:all(p.get_subscription_count()==1 for p in pubs),lambda:None)
        for i,p in enumerate(pubs):p.publish(Int32(data=i+1))
        rows=[]
        def collect():
            try:rows.append(ce.wait_for_ready_callbacks(timeout_sec=0))
            except TimeoutException:pass
        until(lambda:len(rows)==4,collect)
        expected=[subs.index(row[1])+1 for row in rows]
        s.executors=(HeldRows(ce,rows),re)
        result['actual_node_entities']={side:{name:len(tuple(getattr(node,name))) for name in
            ('subscriptions','timers','clients','services','guards','waitables')}
            for side,node in (('C',c),('R',r))}
        # Real Node caps also contain parameter services and QoS waitables.
        # Explicitly reach quantum4; do not pretend the Node's total cap is4.
        completed,_=ns['drain_current_ready'](s.executors[0],c,s.ready_sets['C'],
            s._after_ros_handler,callback_limit=4)
        check('four_real_handlers_once_in_SDK_order',received==expected)
        s._wait_when_idle(dict(C=0,R=0))
        check('cached_quantum_never_idles',len(completed)==4 and not requests
              and s.ready_sets['C']['productive'] and s.ready_sets['C']['last_wait_kind']=='ready')
        s._poll()
        check('productive_tail_never_idles_or_starts_C_deadline',
              not requests and s.ready_sets['C']['last_wait_kind']=='productive_set_end' and s.c_empty_until==0.)
        s._poll()
        check('actual_empty_enters_pure_wait',len(requests)==1)
        deadline=s.c_empty_until;s._poll()
        check('C_skip_does_not_extend_deadline',s.c_empty_until==deadline)
        before=len(requests);s.c_empty_until=0.;s._wait_when_idle(dict(C=0,R=0))
        check('eligible_C_deadline_never_waits',len(requests)==before)
        s.c_empty_until=time.monotonic()+.0002;s._wait_when_idle(dict(C=0,R=0))
        check('short_remaining_C_deadline_clips_request',
              all(row['request_ns']<=200_000 for row in requests[before:]))

        # A DDS publish after the fresh snapshot, immediately before select.
        # Its precise middleware enqueue instant is not exposed by this SDK.
        edge={};one=[True]
        def publish_at_wait(timeout):
            if one[0]:
                one[0]=False;edge['publish_begin_ns']=time.monotonic_ns()
                pubs[0].publish(Int32(data=5));edge['publish_return_ns']=time.monotonic_ns()
                edge['wait_begin_ns']=time.monotonic_ns()
                ready=measured_wait(timeout);edge['wait_end_ns']=time.monotonic_ns();return ready
            return measured_wait(timeout)
        hub.wait_readable=publish_at_wait
        until(lambda:not one[0],s._poll);until(lambda:5 in received,s._poll)
        edge['callback_observed_ns']=time.monotonic_ns()
        check('new_DDS_after_snapshot_received_once',received==expected+[5])
        result['DDS_snapshot_boundary']=dict(edge,scope='Publish at wait boundary; precise DDS enqueue time NOT MEASURED')
        hub.wait_readable=measured_wait

        # Same real SDK/entities, fixed80ms each; no topology or traffic change.
        def idle_window(enabled):
            s._wait_when_idle=MethodType(ns['_wait_when_idle'],s) if enabled else lambda used:None
            begin=time.monotonic_ns();cpu=time.thread_time_ns();before=(ce.fresh_generators,re.fresh_generators)
            while time.monotonic_ns()-begin<80_000_000:
                if time.monotonic()>=HARD:raise TimeoutError('SDK total bound')
                s._poll()
            return dict(wall_ns=time.monotonic_ns()-begin,cpu_ns=time.thread_time_ns()-cpu,
                C_generators=ce.fresh_generators-before[0],R_generators=re.fresh_generators-before[1])
        result['empty_poll_baseline']=idle_window(False);result['empty_poll_candidate']=idle_window(True)
        check('actual_empty_R_snapshots_reduced',result['empty_poll_candidate']['R_generators']<result['empty_poll_baseline']['R_generators'])

        before=len(requests);peer.send(b'{"kind":"ready","bytes":0}\n')
        check('pure_selector_wakes_without_receiving',real_wait(.001) and not hub.ready and not hub.incoming)
        s._poll()
        check('Hub_IO_suppresses_idle_and_original_poll_decodes',hub.ready and len(requests)==before and s._poll_transport_active)
        s.progress_transport()
        check('later_empty_pump_does_not_erase_activity',s._poll_transport_active)
        s._wait_when_idle(dict(C=0,R=0));check('same_poll_OR_activity_still_suppresses_idle',len(requests)==before)
        s._poll_transport_active=False;hub.frame(dict(kind='clock',horizon_ns=0))
        s._wait_when_idle(dict(C=0,R=0));check('pending_output_never_idles',len(requests)==before)
        s.progress_transport();check('pending_output_original_immediate_flush',not hub.outgoing and s._poll_transport_active)
        peer.recv(4096)
        s.anchor={'offset_ns':0};s.gz=0;s.step_pending=None;s.mode='A';s.connected=True;s.wires=None
        delivered=[];s.receive=lambda meta,body,rpc:delivered.append(rpc)
        s.direct.append(({},b'x',7));s._poll_transport_active=False;s.progress_transport()
        s._wait_when_idle(dict(C=0,R=0))
        check('real_direct_batch_activity_never_idles',delivered==[7] and not s.direct and s._poll_transport_active and len(requests)==before)
        s.anchor=None

        # Real C callback + real IPC, then both sides reach fresh empty in the
        # same original poll. Historical work must no longer force one retry.
        quiet_seen=[]
        def quiet_callback(msg):
            quiet_seen.append(msg.data)
            peer.send(b'{"kind":"clock_return","horizon_ns":0,"bytes":0}\n')
        quiet_sub=c.create_subscription(Int32,'/net01d_idle_check/tailquiet',quiet_callback,10)
        quiet_pub=source.create_publisher(Int32,'/net01d_idle_check/tailquiet',10)
        until(lambda:quiet_pub.get_subscription_count()==1,s._poll)
        before_tail=s.dispatch_stats['idle_wait']['tail_quiet_idle']
        quiet_pub.publish(Int32(data=6));until(lambda:bool(quiet_seen),s._poll)
        check('real_callback_and_IPC_then_fresh_tail_can_idle',quiet_seen==[6]
              and s.dispatch_stats['idle_wait']['tail_quiet_idle']>before_tail
              and all(v==s._idle_work_epoch for v in s._tail_empty_epoch.values()))

        # Keep a real R callback already ready while C is deliberately skipped
        # under its original10ms actual-empty deadline. No early C query.
        r_seen=[]
        r_ready=r.create_subscription(Int32,'/net01d_idle_check/Rready',lambda msg:r_seen.append(msg.data),10)
        r_pub=source.create_publisher(Int32,'/net01d_idle_check/Rready',10)
        until(lambda:r_pub.get_subscription_count()==1,s._poll)
        r_pub.publish(Int32(data=7));r_rows=[]
        def collect_r():
            try:r_rows.append(re.wait_for_ready_callbacks(timeout_sec=0))
            except TimeoutException:pass
        until(lambda:bool(r_rows),collect_r)
        check('real_R_handler_is_held',len(r_rows)==1 and r_rows[0][1] is r_ready)
        until(lambda:time.monotonic()>=s.c_empty_until,lambda:None)
        while True:
            if time.monotonic()>=HARD:raise TimeoutError('C fresh-empty preparation bound')
            ns['drain_current_ready'](s.executors[0],c,s.ready_sets['C'],s._after_ros_handler,callback_limit=4)
            if s.ready_sets['C'].get('last_wait_kind')=='empty_set':break
        # Match the existing rule after this genuine empty, without hiding any
        # Node entities or changing the production query deadline.
        s.c_empty_until=time.monotonic()+.010;s.executors=(s.executors[0],HeldRows(re,r_rows))
        before_wait=len(requests);before_stale=s.dispatch_stats['idle_wait']['stale_empty_rejections']
        s._poll()
        check('R_work_with_only_skipped_C_empty_cannot_use_new_path',r_seen==[7]
              and s._tail_empty_epoch['C'] is None and len(requests)==before_wait
              and s.dispatch_stats['idle_wait']['stale_empty_rejections']>before_stale)
        s.executors=(s.executors[0],re)

        # A genuine fresh proof is invalidated by later actual IPC, even if no
        # payload remains queued. This is not a private SDK task-queue guess.
        until(lambda:all(v==s._idle_work_epoch for v in s._tail_empty_epoch.values()),s._poll)
        before_wait=len(requests);before_stale=s.dispatch_stats['idle_wait']['stale_empty_rejections']
        peer.send(b'{"kind":"clock_return","horizon_ns":0,"bytes":0}\n');s.progress_transport()
        s._wait_when_idle(dict(C=1,R=0))
        check('new_actual_IO_epoch_invalidates_both_proofs',len(requests)==before_wait
              and s.dispatch_stats['idle_wait']['stale_empty_rejections']>before_stale)

        entered=[];yielded=[];resumed=[];gate=Future(executor=re)
        async def respond(request,response):
            entered.append(True);await YieldOnce();yielded.append(True)
            await gate;resumed.append(True);return response
        service=r.create_service(Empty,'/net01d_idle_check/async',respond)
        client=c.create_client(Empty,'/net01d_idle_check/async')
        until(client.service_is_ready,s._poll);future=client.call_async(Empty.Request())
        until(lambda:bool(yielded),s._poll)
        for _ in range(3):s._poll()
        check('async_yieldNone_and_pending_Future_preserved',len(entered)==len(yielded)==1 and not resumed and not future.done())
        gate.set_result(True);until(future.done,s._poll)
        check('async_actual_response_once',len(entered)==len(yielded)==len(resumed)==1 and isinstance(future.result(),Empty.Response))

        timer_calls=[]
        timer=r.create_timer(.02,lambda:timer_calls.append(time.monotonic_ns()),clock=Clock(clock_type=ClockType.STEADY_TIME))
        s.guards={1:SimpleNamespace(timer=timer)}
        until(lambda:len(timer_calls)>=3,s._poll)
        result['steady20ms_timer']=dict(calls=timer_calls,gaps_ns=[b-a for a,b in zip(timer_calls,timer_calls[1:])],scope='Actual dispatch gaps; no OS real-time guarantee')
        check('steady_timer_real_callbacks_survive',len(timer_calls)>=3)
        check('all_requested_idle_timeouts_at_most1ms',bool(requests) and all(0<row['request_ns']<=1_000_000 for row in requests))
        s.hub_poll_closed=True;before=len(requests);s._wait_when_idle(dict(C=0,R=0))
        check('closed_transport_never_waits',len(requests)==before)
        idle=s.dispatch_stats['idle_wait']
        check('old_and_tail_paths_both_observed_and_counted',idle['original_idle']>0
              and idle['tail_quiet_idle']>0 and idle['calls']==idle['original_idle']+idle['tail_quiet_idle'])
        result.update(status='PASS',idle_requests=requests,idle_stats=s.dispatch_stats['idle_wait'])
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));traceback.print_exc()
    finally:
        if hub is not None:hub.close()
        if peer is not None:peer.close()
        if listener is not None:listener.close()
        shutdown_results=[executor.shutdown(timeout_sec=0) for executor in executors]
        for node in nodes:node.destroy_node()
        rclpy.try_shutdown(context=context);temp.cleanup()
        descriptors_closed=all(obj is None or obj.fileno()==-1 for obj in (hub.socket if hub else None,peer,listener))
        resources_closed=all(shutdown_results) and not context.ok() and descriptors_closed
        if not resources_closed:result.update(status='FAIL',cleanup_error='Actual SDK/IPC cleanup incomplete')
        result.update(checks=checks,wall_s=time.monotonic()-started,domain=121,
            scope='Real SDK and kernel IPC only; no robot, Action, native, ns3, GZ, arm or velocity',
            executor_shutdown=shutdown_results,descriptors_closed=descriptors_closed,resources_closed=resources_closed)
        with (args.directory/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

"""Real installed SDK, isolated domain117. No robot endpoints or transport.

Baseline is the saved inherited817 function excerpt; candidate is actual current
Gateway source. Handler rows come from the real SDK and are replayed once only
so four already-ready messages have no DDS-delivery timing race in the oracle.
"""
import argparse
import ast
from collections import deque
import json
from pathlib import Path
import time
from types import SimpleNamespace
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor, TimeoutException, ShutdownException
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.task import Future
from std_msgs.msg import Int32
from std_srvs.srv import Empty

ROOT=Path(__file__).resolve().parents[2]
HARD=time.monotonic()+10

def until(predicate,pump):
    end=min(HARD,time.monotonic()+2)
    while not predicate():
        if time.monotonic()>=end:raise TimeoutError('fixed SDK check boundary')
        pump()


def methods(path,baseline=False):
    tree=ast.parse(path.read_text())
    ns=dict(time=time,TimeoutException=TimeoutException,ShutdownException=ShutdownException)
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    if not baseline:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Gateway')
        funcs+=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_poll']
    selected=[n for n in funcs if n.name in ('record_cpu_span','drain_current_ready','_poll')]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),ns)
    return ns


class CountedExecutor(SingleThreadedExecutor):
    def __init__(self,context):
        super().__init__(context=context);self.snapshot_generators=0
    def _wait_for_ready_callbacks(self,*args,**kwargs):
        self.snapshot_generators+=1
        yield from super()._wait_for_ready_callbacks(*args,**kwargs)


class HeldRows:
    def __init__(self,executor,rows):self.executor,self.rows=executor,deque(rows)
    def wait_for_ready_callbacks(self,**kwargs):
        return self.rows.popleft() if self.rows else self.executor.wait_for_ready_callbacks(**kwargs)


def subject(nodes,executors,stateC,pump):
    def stat():return dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.,
        empty_recheck_started=0,empty_recheck_skips=0)
    return SimpleNamespace(nodes=nodes,executors=executors,ready_sets=dict(C=stateC,R=dict(productive=False)),
        last_poll=None,c_empty_until=0.,cpu_profile=None,profile_longspans=None,profile_entity=lambda e:'unused',guards={},
        dispatch_stats=dict(C=stat(),R=stat(),guard_timers={},max_poll_gap_wall_s=0.),progress_transport=pump)


def run_variant(label,ns,context,all_nodes,all_executors):
    source=Node('source_'+label,context=context);c=Node('consumer_'+label,context=context)
    r=Node('other_'+label,context=context);all_nodes.extend((source,c,r))
    ce,re=CountedExecutor(context),CountedExecutor(context);ce.add_node(c);re.add_node(r)
    all_executors.extend((ce,re));received=[];order=[];pubs=[];subs=[]
    for i in range(4):
        topic=f'/net01d_dispatch_test/{label}/value{i}'
        subs.append(c.create_subscription(Int32,topic,lambda msg:received.append(msg.data),10))
        pubs.append(source.create_publisher(Int32,topic,10))
    until(lambda:all(pub.get_subscription_count()==1 for pub in pubs),lambda:None)
    for i,pub in enumerate(pubs):pub.publish(Int32(data=i+1))
    rows=[]
    def collect():
        try:rows.append(ce.wait_for_ready_callbacks(timeout_sec=0))
        except TimeoutException:pass
    until(lambda:len(rows)==4,collect)
    expected=[subs.index(row[1])+1 for row in rows]
    buffered=HeldRows(ce,rows);state=dict(productive=False)
    ns['drain_current_ready'](buffered,c,state,lambda:order.append('pump'),callback_limit=4)
    before=ce.snapshot_generators
    s=subject((c,r),(buffered,re),state,lambda:order.append('pump'))
    ns['_poll'](s)
    result=dict(initial_received=list(received),SDK_yield_order=expected,
        initial_callbacks_once=received==expected,
        snapshot_rebuilds_on_productive_tail=ce.snapshot_generators-before,
        C_cooldown_started_on_tail=s.c_empty_until>time.monotonic(),
        C_last_wait_kind=state.get('last_wait_kind'),pumps_through_tail=len(order))
    if label=='candidate':
        pubs[0].publish(Int32(data=5))
        until(lambda:5 in received,lambda:ns['_poll'](s))
        result['fifth_message_once_after_tail']=received==expected+[5]
        s.c_empty_until=0.;state['productive']=False;state['last_wait_kind']=None
        until(lambda:state.get('last_wait_kind')=='empty_set',lambda:ns['_poll'](s))
        result['only_actual_empty_starts_C_deadline']=s.c_empty_until>time.monotonic()
    return result


def async_service(ns,context,all_nodes,all_executors):
    server=Node('async_server',context=context);client_node=Node('async_client',context=context)
    all_nodes.extend((server,client_node));se,ce=CountedExecutor(context),CountedExecutor(context)
    se.add_node(server);ce.add_node(client_node);all_executors.extend((se,ce))
    gate=Future(executor=se);entered=[];resumed=[];states=[dict(productive=False),dict(productive=False)]
    async def respond(request,response):
        entered.append(True);await gate;resumed.append(True);return response
    service=server.create_service(Empty,'/net01d_dispatch_test/async',respond)
    client=client_node.create_client(Empty,'/net01d_dispatch_test/async')
    until(client.service_is_ready,lambda:None)
    future=client.call_async(Empty.Request())
    def pump():
        for e,n,state in zip((se,ce),(server,client_node),states):
            ns['drain_current_ready'](e,n,state,callback_limit=4)
    until(lambda:bool(entered),pump)
    for _ in range(3):pump()
    was_pending=not future.done() and not resumed
    gate.set_result(True)
    until(future.done,pump)
    return dict(pending_across_snapshot_boundaries=was_pending,
        original_callback_once=len(entered)==len(resumed)==1,
        actual_client_response_received=isinstance(future.result(),Empty.Response))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    context=Context();all_nodes=[];all_executors=[];result={};begin=time.monotonic()
    rclpy.init(context=context,domain_id=117,signal_handler_options=SignalHandlerOptions.NO)
    try:
        baseline=methods(Path(__file__).with_name('baseline_dispatch_excerpt.py'),True)
        candidate=methods(ROOT/'net01/gateway.py')
        result['baseline']=run_variant('baseline',baseline,context,all_nodes,all_executors)
        result['candidate']=run_variant('candidate',candidate,context,all_nodes,all_executors)
        result['async_service']=async_service(candidate,context,all_nodes,all_executors)
        b,c,a=result['baseline'],result['candidate'],result['async_service']
        checks=dict(real_SDK_baseline_rebuilds_empty=b['snapshot_rebuilds_on_productive_tail']==1,
            real_SDK_candidate_yields_without_rebuild=c['snapshot_rebuilds_on_productive_tail']==0,
            C_productive_tail_is_not_actual_empty=not c['C_cooldown_started_on_tail'],
            actual_C_empty_uses_original_deadline=c['only_actual_empty_starts_C_deadline'],
            real_four_order_and_once=b['initial_callbacks_once'] and c['initial_callbacks_once'],
            original_handler_and_outer_pumps=b['pumps_through_tail']==c['pumps_through_tail']==5,
            next_poll_can_take_fifth=c['fifth_message_once_after_tail'],
            async_pending_task_and_response_preserved=all(a.values()))
        result.update(checks=checks,status='PASS' if all(checks.values()) else 'FAIL')
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));raise
    finally:
        for executor in all_executors:executor.shutdown(timeout_sec=0)
        for node in all_nodes:node.destroy_node()
        rclpy.try_shutdown(context=context)
        result.update(wall_s=time.monotonic()-begin,domain=117,
            scope='Real SDK DDS/timer-free four-topic and Empty async-service diagnostic; 0robot/Action/arm/velocity/ns3/Gazebo')
        with (args.directory/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

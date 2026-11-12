"""One bounded real-DDS clock/queued-business check; zero robot/native/model.

Reuse f02's real SDK held-handler/subject helpers and actual Gateway AST.
The Unix peer is only a fixture sink/READY source, not an ns-3 ACK authority.
"""
import argparse
import ast
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
from types import MethodType,SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'net01'))
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor,TimeoutException
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rclpy.serialization import serialize_message
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock as ClockMessage
from std_msgs.msg import Int32
from adapter_node import AdapterNode
from hub_client import HubClient
from net01d.followup02.check_gateway_idle import HeldRows,subject,methods


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    begin=time.monotonic();deadline=begin+10;checks={};result={};contexts=[];nodes=[];executors=[]
    listener=peer=hub=s=None;clock_executor=None;clock_closed=False
    temporary=tempfile.TemporaryDirectory(prefix='net01d-clocklane-')
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def until(predicate,action):
        while not predicate():
            if time.monotonic()>=deadline:raise TimeoutError('Original10wall SDK fixture bound')
            action()
    try:
        ns=methods();tree=ast.parse((ROOT/'net01/gateway.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Gateway')
        names=('_create_control_clock_lane','_service_control_clock','_close_control_clock_lane','clock','record','send')
        added=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        ns.update(SingleThreadedExecutor=SingleThreadedExecutor,Parameter=Parameter,
            ClockMessage=ClockMessage,qos_profile_sensor_data=qos_profile_sensor_data)
        exec(compile(ast.Module(body=added,type_ignores=[]),'actual_Gateway_clocklane','exec'),ns)
        init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        lane_setup=next(n for n in init.body if isinstance(n,ast.If) and any(
            isinstance(a,ast.Assign) and isinstance(a.targets[0],ast.Attribute)
            and a.targets[0].attr=='control_clock_ready_set' for a in n.body))
        lane_create=next(n for n in init.body if isinstance(n,ast.If) and any(
            isinstance(a,ast.Expr) and isinstance(a.value,ast.Call) and isinstance(a.value.func,ast.Attribute)
            and a.value.func.attr=='_create_control_clock_lane' for a in n.body))
        setup=compile(ast.Module(body=[lane_setup,lane_create],type_ignores=[]),'actual_Gateway_lane_construction','exec')
        for domain in (131,132):
            context=Context();rclpy.init(context=context,domain_id=domain,signal_handler_options=SignalHandlerOptions.NO)
            contexts.append(context)
        c=AdapterNode('clocklane_C',context=contexts[0],parameter_overrides=[Parameter('use_sim_time',value=True)])
        r=AdapterNode('clocklane_R',context=contexts[1],parameter_overrides=[Parameter('use_sim_time',value=True)])
        source=AdapterNode('clocklane_source',context=contexts[1]);nodes.extend((c,r,source))
        ce=SingleThreadedExecutor(context=contexts[0]);re=SingleThreadedExecutor(context=contexts[1])
        ce.add_node(c);re.add_node(r);executors.extend((ce,re))
        path=Path(temporary.name)/'wire.sock';listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        listener.bind(str(path));listener.listen();hub=HubClient(path);peer,_=listener.accept();peer.setblocking(False)
        peer.send(b'{"kind":"ready","bytes":0}\n');until(lambda:hub.ready,hub.poll)
        s=subject(ns,c,r,ce,re,hub);s.c,s.r=c,r;s.records=[];s.previous_clock=None;s.gz=None
        s.step_pending=None;s.step_quantum_ns=10_000_000
        s.mode='B';s.connected=True;s.wires=None;s.link=SimpleNamespace(sent=True,ready=False)
        s.control_clock_node=s.control_clock_executor=None
        for name in names:setattr(s,name,MethodType(ns[name],s))
        s.clock_pub=c.create_publisher(ClockMessage,'/clock',qos_profile_sensor_data)
        s.control_clock_lane=False;exec(setup,ns,dict(self=s,node_type=AdapterNode))
        check('defaultoff_explicit_reader_stays_on_R_no_extra_executor',s.clock_sub in r.subscriptions
              and s.control_clock_node is None and s.control_clock_executor is None)
        r.destroy_subscription(s.clock_sub)
        s.control_clock_lane=True;exec(setup,ns,dict(self=s,node_type=AdapterNode));clock_executor=s.control_clock_executor
        check('new_executor_shares_R_context_without_C_R_list_change',s.control_clock_node.context is r.context
              and tuple(s.nodes)==(c,r) and tuple(s.executors)==(ce,re))
        check('control_node_false_simtime_no_parameter_services',
              s.control_clock_node.get_parameter('use_sim_time').value is False and not tuple(s.control_clock_node.services))
        check('only_explicit_control_clock_subscription_and_original_TimeSources',
              [sub.topic_name for sub in s.control_clock_node.subscriptions]==['/clock']
              and sum(sub.topic_name=='/clock' for sub in r.subscriptions)==1
              and sum(sub.topic_name=='/clock' for sub in c.subscriptions)==1)
        clock_pub=source.create_publisher(ClockMessage,'/clock',qos_profile_sensor_data)
        business=[];publishers=[];subscriptions=[]
        def work(message):
            business.append(dict(sequence=message.data,monotonic_ns=time.monotonic_ns(),Gateway_gz=s.gz))
            s.send(1,0,123,serialize_message(message),source_stamp_ns=0)
        for i in range(4):
            topic=f'/clocklane_sdk/business{i}'
            subscriptions.append(r.create_subscription(Int32,topic,work,10))
            publishers.append(source.create_publisher(Int32,topic,10))
        until(lambda:clock_pub.get_subscription_count()==2 and s.clock_pub.get_subscription_count()==1
              and all(p.get_subscription_count()==1 for p in publishers),lambda:time.sleep(.001))
        result['startup_clock_subscriptions']=dict(R=clock_pub.get_subscription_count(),C=s.clock_pub.get_subscription_count())
        for i,publisher in enumerate(publishers):publisher.publish(Int32(data=i+1))
        held=[]
        def collect_business():
            try:held.append(re.wait_for_ready_callbacks(timeout_sec=0))
            except TimeoutException:pass
        until(lambda:len(held)==4,collect_business)
        check('four_actual_DDS_business_handlers_queued_not_executed',not business and all(row[1] in subscriptions for row in held))
        s.executors=(ce,HeldRows(re,held))
        def publish_clock(value):
            message=ClockMessage();message.clock.sec,message.clock.nanosec=divmod(value,1_000_000_000)
            clock_pub.publish(message)
        publish_clock(10_000_000);clock_rows=[]
        def collect_clock():
            try:clock_rows.append(clock_executor.wait_for_ready_callbacks(timeout_sec=0))
            except TimeoutException:pass
        until(lambda:bool(clock_rows),collect_clock)
        check('actual_clock_ready_in_separate_executor',clock_rows[0][1] is s.clock_sub)
        s.control_clock_executor=HeldRows(clock_executor,clock_rows)
        s._poll();s.control_clock_executor=clock_executor;s.executors=(ce,re)
        check('pollstart_relay_precedes_queued_business_once',len(business)==4 and
              all(row['Gateway_gz']==10_000_000 for row in business) and s.control_clock_stats['clock_callbacks']==1)
        relay=[row for row in s.records if row['kind']=='actual_R_clock_relayed_C']
        check('real_relay_callback_before_first_business',len(relay)==1
              and relay[0]['C_publish_return_monotonic_ns']<=business[0]['monotonic_ns'])
        publish_clock(20_000_000);until(lambda:s.control_clock_stats['clock_callbacks']==2,s._poll)
        s.progress_transport();s.progress_transport()
        captured=bytearray()
        while True:
            try:data=peer.recv(65536)
            except BlockingIOError:break
            if not data:break
            captured.extend(data)
        frames=[]
        while captured:
            end=captured.index(b'\n');meta=json.loads(captured[:end]);size=meta['bytes']
            check('complete_actual_IPC_frame',len(captured)>=end+1+size)
            frames.append(meta);del captured[:end+1+size]
        known=[i for i,row in enumerate(frames) if row['kind']=='observed_clock']
        sent=[i for i,row in enumerate(frames) if row['kind']=='send'];steps=[i for i,row in enumerate(frames) if row['kind']=='clock']
        check('actual_single_Hub_FIFO_KNOWN_before_business_and_STEP',len(sent)==4 and known[0]<min(sent)
              and bool(steps) and any(i<steps[0] and frames[i]['horizon_ns']>=frames[steps[0]]['horizon_ns'] for i in known))
        waits=[];real_wait=hub.wait_readable
        def measured_wait(timeout):waits.append(timeout);return real_wait(timeout)
        hub.wait_readable=measured_wait
        until(lambda:bool(waits) and s.control_clock_ready_set['last_wait_kind']=='empty_set',s._poll)
        check('actual_empty_lane_allows_original_kernel_idle',bool(waits))
        publish_clock(30_000_000);clock_rows=[];until(lambda:bool(clock_rows),collect_clock)
        s.control_clock_executor=HeldRows(clock_executor,clock_rows);s._service_control_clock()
        s.control_clock_executor=clock_executor;s.progress_transport()
        before=len(waits);rejected=s.control_clock_stats['idle_rejections']
        s._wait_when_idle(dict(C=0,R=0))
        check('actual_productive_control_cursor_cannot_idle',len(waits)==before
              and s.control_clock_stats['idle_rejections']==rejected+1)
        until(lambda:s.control_clock_ready_set['last_wait_kind']=='empty_set',s._service_control_clock)
        peer.send(b'{"kind":"clock_return","horizon_ns":0,"bytes":0}\n')
        epoch=s._idle_work_epoch;until(lambda:s._idle_work_epoch>epoch,s.progress_transport)
        before=len(waits);rejected=s.control_clock_stats['idle_rejections'];s._wait_when_idle(dict(C=0,R=0))
        check('actual_IO_invalidates_control_empty_epoch',len(waits)==before
              and s.control_clock_stats['idle_rejections']==rejected+1)
        publish_clock(25_000_000);until(lambda:s.failure is not None,s._poll)
        check('original_actual_clock_rollback_failure_preserved',s.failure=='gazebo_clock_rollback')
        check('separate_executor_shutdown_before_shared_context',s._close_control_clock_lane() is True and r.context.ok())
        clock_closed=True
        result.update(status='PASS',frames=frames,business=business,clock_lane=s.control_clock_stats,
            clock_records=s.records,original_failure=s.failure)
    except BaseException as error:result.update(status='FAIL',error=repr(error))
    finally:
        if s is not None and clock_executor is not None and not clock_closed:
            s.control_clock_executor=clock_executor;s._close_control_clock_lane()
        shutdown=[executor.shutdown(timeout_sec=0) for executor in executors]
        for node in reversed(nodes):node.destroy_node()
        for context in reversed(contexts):rclpy.try_shutdown(context=context)
        if hub is not None:hub.close()
        if peer is not None:peer.close()
        if listener is not None:listener.close()
        temporary.cleanup()
        closed=all(shutdown) and all(not c.ok() for c in contexts)
        if not closed:result.update(status='FAIL',cleanup_error='Actual SDK resources not closed')
        result.update(checks=checks,wall_s=time.monotonic()-begin,executor_shutdown=shutdown,resources_closed=closed,
            domains=dict(C=131,R=132),scope='Actual DDS/SDK and Unix FIFO only. READY/horizon peer is a fixture, not native ACK/physics. '
                'Real original methods, bounded clock handling; no robot, Guard, Action, cmd_vel, ns3, Gazebo or policy. No300ms/throughput certificate.')
        with (args.directory/'result.json').open('x') as out:json.dump(result,out,indent=2);out.write('\n')
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

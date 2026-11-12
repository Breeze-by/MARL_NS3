"""One real SDK/domain122 check; no robot/Guard/Action/velocity/native/Gazebo."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

os.environ['RCUTILS_LOGGING_USE_STDOUT']='0'
os.environ['RCUTILS_LOGGING_BUFFERED_STREAM']='0'
os.environ['RCUTILS_COLORIZED_OUTPUT']='0'
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.qos_event import PublisherEventCallbacks, SubscriptionEventCallbacks
from rclpy.serialization import serialize_message
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Int32
from std_srvs.srv import Empty

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'net01'))
from adapter_node import AdapterNode


def qos_value(q):
    return dict(history=int(q.history),depth=q.depth,reliability=int(q.reliability),
        durability=int(q.durability),deadline_ns=q.deadline.nanoseconds,
        lifespan_ns=q.lifespan.nanoseconds,liveliness=int(q.liveliness),
        lease_ns=q.liveliness_lease_duration.nanoseconds,
        avoid_ros_namespace_conventions=q.avoid_ros_namespace_conventions)


def entities(node):
    return {name:len(tuple(getattr(node,name))) for name in
        ('subscriptions','timers','clients','services','guards','waitables')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+10;context=Context();executor=None;nodes=[]
    result={};checks={};variants={};logpath=args.directory/'rclpy.stderr.log'
    previous=os.dup(2);log=logpath.open('xb');os.dup2(log.fileno(),2)
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def pump():
        if time.monotonic()>=hard:raise TimeoutError('10wall SDK check boundary')
        executor.spin_once(timeout_sec=0)
    def until(predicate):
        end=min(hard,time.monotonic()+2)
        while not predicate():
            if time.monotonic()>=end:raise TimeoutError('SDK predicate boundary')
            pump()
    def spin_for(seconds):
        end=min(hard,time.monotonic()+seconds)
        while time.monotonic()<end:pump()
    try:
        rclpy.init(context=context,domain_id=122,signal_handler_options=SignalHandlerOptions.NO)
        executor=SingleThreadedExecutor(context=context)
        for label,cls in [('default',Node),('candidate',AdapterNode)]:
            node=cls('qos_event_'+label,context=context);nodes.append(node);executor.add_node(node)
            item=dict(node=node,initial_entities=entities(node),compatible=[],auto_incompatible=[],
                      explicit_incompatible=[],events=dict(pub=[],sub=[]))
            topic='/net01d_qos_event_check/'+label
            before=entities(node)['waitables']
            item['pub']=node.create_publisher(Int32,topic+'/compatible',QoSProfile(depth=10))
            item['sub']=node.create_subscription(Int32,topic+'/compatible',
                lambda msg,item=item:item['compatible'].append(serialize_message(msg)),QoSProfile(depth=10))
            item['compatible_waitable_delta']=entities(node)['waitables']-before
            before=entities(node)['waitables']
            item['auto_pub']=node.create_publisher(Int32,topic+'/auto_incompatible',
                QoSProfile(depth=10,reliability=ReliabilityPolicy.BEST_EFFORT))
            item['auto_sub']=node.create_subscription(Int32,topic+'/auto_incompatible',
                lambda msg,item=item:item['auto_incompatible'].append(msg.data),
                QoSProfile(depth=10,reliability=ReliabilityPolicy.RELIABLE))
            item['auto_waitable_delta']=entities(node)['waitables']-before
            def callback(info,item=item,kind='pub'):
                item['events'][kind].append(dict(total_count=info.total_count,
                    total_count_change=info.total_count_change,last_policy_kind=int(info.last_policy_kind)))
            pub_cb=callback
            sub_cb=lambda info,item=item:callback(info,item,'sub')
            pe=PublisherEventCallbacks(incompatible_qos=pub_cb)
            se=SubscriptionEventCallbacks(incompatible_qos=sub_cb)
            before=entities(node)['waitables']
            item['explicit_pub']=node.create_publisher(Int32,topic+'/explicit_incompatible',
                QoSProfile(depth=10,reliability=ReliabilityPolicy.BEST_EFFORT),event_callbacks=pe)
            item['explicit_sub']=node.create_subscription(Int32,topic+'/explicit_incompatible',
                lambda msg,item=item:item['explicit_incompatible'].append(msg.data),
                QoSProfile(depth=10,reliability=ReliabilityPolicy.RELIABLE),event_callbacks=se)
            item['explicit_waitable_delta']=entities(node)['waitables']-before
            item['explicit_containers_unmodified']=(pe.incompatible_qos is pub_cb and se.incompatible_qos is sub_cb
                and pe.use_default_callbacks and se.use_default_callbacks)
            item['service']=node.create_service(Empty,topic+'/empty',lambda request,response:response)
            item['client']=node.create_client(Empty,topic+'/empty')
            item['final_entities']=entities(node);variants[label]=item
        until(lambda:all(v['pub'].get_subscription_count()==1 and v['client'].service_is_ready()
                         for v in variants.values()))
        original=Int32(data=24681357);original_cdr=serialize_message(original)
        for v in variants.values():
            v['pub'].publish(original);v['auto_pub'].publish(original);v['explicit_pub'].publish(original)
            v['future']=v['client'].call_async(Empty.Request())
        until(lambda:all(v['compatible'] and v['future'].done()
            and v['events']['pub'] and v['events']['sub'] for v in variants.values()))
        spin_for(.15)
        for label,v in variants.items():
            check(label+'_compatible_actual_body',v['compatible']==[original_cdr])
            check(label+'_service_ready_and_actual_response',v['client'].service_is_ready()
                  and isinstance(v['future'].result(),Empty.Response))
            check(label+'_explicit_incompatible_callbacks_trigger',
                  bool(v['events']['pub']) and bool(v['events']['sub']) and v['explicit_containers_unmodified'])
            check(label+'_incompatible_is_not_delivery',not v['auto_incompatible'] and not v['explicit_incompatible'])
            v['live_qos']={name:qos_value(v[name].qos_profile) for name in
                ('pub','sub','auto_pub','auto_sub','explicit_pub','explicit_sub')}
            v['graph_qos']={kind:[qos_value(info.qos_profile) for info in getattr(v['node'],method)(
                '/net01d_qos_event_check/'+label+'/compatible')]
                for kind,method in [('pub','get_publishers_info_by_topic'),('sub','get_subscriptions_info_by_topic')]}
        b,c=variants['default'],variants['candidate']
        check('requested_live_QoS_unchanged',b['live_qos']==c['live_qos'])
        check('actual_graph_QoS_unchanged',b['graph_qos']==c['graph_qos'] and all(b['graph_qos'].values()))
        check('normal_warning_entities_only_removed',b['compatible_waitable_delta']==b['auto_waitable_delta']==2
              and c['compatible_waitable_delta']==c['auto_waitable_delta']==0)
        check('explicit_warning_entities_retained',b['explicit_waitable_delta']==c['explicit_waitable_delta']==2)
        check('parameter_services_retained',b['initial_entities']['services']==c['initial_entities']['services']==6)
        result['variants']={label:{key:v[key] for key in ('initial_entities','final_entities',
            'compatible_waitable_delta','auto_waitable_delta','explicit_waitable_delta','events',
            'explicit_containers_unmodified','live_qos','graph_qos')} for label,v in variants.items()}
        result.update(status='PASS',compatible_body_hex=original_cdr.hex(),incompatible_received={
            label:dict(auto=v['auto_incompatible'],explicit=v['explicit_incompatible']) for label,v in variants.items()})
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));traceback.print_exc()
    finally:
        shutdown=executor.shutdown(timeout_sec=0) if executor is not None else None
        for node in nodes:node.destroy_node()
        rclpy.try_shutdown(context=context)
        os.dup2(previous,2);os.close(previous);log.close()
        lines=logpath.read_text().splitlines()
        warning_lines=[line for line in lines if 'incompatible QoS' in line]
        default_lines=[line for line in warning_lines if '[qos_event_default]' in line]
        candidate_lines=[line for line in warning_lines if '[qos_event_candidate]' in line]
        checks['baseline_actual_automatic_warning_observed']=bool(default_lines)
        checks['candidate_no_automatic_incompatible_warning']=not candidate_lines
        closed=shutdown is True and not context.ok() and log.closed
        if not closed or not all(checks.values()):result['status']='FAIL'
        result.update(checks=checks,automatic_warning_lines=dict(default=default_lines,candidate=candidate_lines),
            executor_shutdown=shutdown,context_closed=not context.ok(),resources_closed=closed,
            wall_s=time.monotonic()-start,domain=122,
            scope='Real QoS diagnostic-entity/typed body/service check, not performance or safety/fullAction qualification; source ActionWire/LocalStop unchanged')
        with (args.directory/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

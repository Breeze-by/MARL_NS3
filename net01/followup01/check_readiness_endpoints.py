"""Real isolated five endpoints vs native ActionClient oracle; zero requests."""
import json
import argparse
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_action_status_default,qos_check_compatible
from rclpy.signals import SignalHandlerOptions
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatusArray
from action_wire import ActionWire,SERVICES


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path(__file__).with_name('readiness-endpoints-01.json'))
    args=parser.parse_args()
    rclpy.init(domain_id=96,signal_handler_options=SignalHandlerOptions.NO)
    server=Node('net01_controlled_five_endpoints')
    bridge=Node('net01_readiness_business_endpoints')
    reference=Node('net01_native_readiness_oracle')
    executor=SingleThreadedExecutor()
    for node in (server,bridge,reference):executor.add_node(node)
    wire=ActionWire(bridge,lambda *args:None,robot=1,session_id=51)
    oracle=ActionClient(reference,NavigateToPose,wire.name(1))
    endpoints={};samples=[];checks={};requests=[]
    until=time.monotonic()+15
    def callback(request,response):requests.append(type(request).__name__);return response
    def create(key):
        if key in (0,2,4):
            _,typ,suffix=next(x for x in SERVICES if x[0]==key)
            endpoints[key]=server.create_service(typ,wire.name(1)+'/_action/'+suffix,callback)
        elif key==6:endpoints[key]=server.create_publisher(NavigateToPose.Impl.FeedbackMessage,wire.name(1)+'/_action/feedback',10)
        else:endpoints[key]=server.create_publisher(GoalStatusArray,wire.name(1)+'/_action/status',qos_profile_action_status_default)
    def remove(key):
        obj=endpoints.pop(key)
        if key in (0,2,4):server.destroy_service(obj)
        else:server.destroy_publisher(obj)
    def match(label,expected):
        limit=min(until,time.monotonic()+1.2)
        while time.monotonic()<limit:
            executor.spin_once(timeout_sec=.001)
            observed=wire.backend_is_ready();old=oracle.server_is_ready()
            samples.append(dict(stage=label,monotonic=time.monotonic(),replacement=observed,native_oracle=old))
            if observed==old==expected:
                checks[label]=True;return
        checks[label]=False
        raise RuntimeError('Actual readiness mismatch: '+label)
    failure=None;details={}
    try:
        match('absent_five_endpoints_false',False)
        for key in (0,2,4,6,7):create(key)
        match('all_actual_typed_endpoints_true',True)
        for key in (0,2,4,6,7):
            remove(key);match(f'missing_endpoint_{key}_false',False)
            create(key);match(f'restored_endpoint_{key}_true',True)
        checks['no_business_service_requests_or_goals']=not requests
        checks['production_wire_has_no_probe_action_client']=not hasattr(wire,'probes')
    except Exception as error:
        failure=repr(error)
        details['clients']={str(k):c.service_is_ready() for k,c in wire.clients.items()}
        details['topics']=[]
        for sub in wire.subscriptions:
            infos=[]
            for info in bridge.get_publishers_info_by_topic(sub.topic_name):
                compatibility,reason=qos_check_compatible(info.qos_profile,sub.qos_profile)
                infos.append(dict(type=info.topic_type,node_name=info.node_name,
                    publisher_qos=str(info.qos_profile),requested_qos=str(sub.qos_profile),
                    compatibility=str(compatibility),compatibility_value=int(compatibility),reason=reason))
            details['topics'].append(dict(topic=sub.topic_name,publishers=infos))
    finally:
        wire.close();oracle.destroy()
        for key in tuple(endpoints):remove(key)
        executor.shutdown(timeout_sec=0)
        for node in (server,bridge,reference):node.destroy_node()
        rclpy.shutdown()
        result=dict(status='PASS' if failure is None and all(checks.values()) else 'FAIL',error=failure,
            checks=checks,samples=samples,details=details,service_requests=requests,domain=96,
            scope='Real generated typed endpoints and native ActionClient discovery oracle only; no goal/ActionServer/Nav2/GZ/NN/WiFi, no wait after runtime source stale',
            match_window_wall_s=15)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

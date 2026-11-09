"""One real DDS data-path check; controlled facade, no Action goal/robot/GZ."""
from collections import deque
import json,time
from pathlib import Path
import rclpy
from rclpy.context import Context
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_action_status_default
from rclpy.serialization import deserialize_message
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatusArray,GoalStatus
from std_msgs.msg import Bool
from action_wire import ActionWire
out=Path('/mnt/net01/followup02/action-raw-cdr-01');out.mkdir(exist_ok=False)
contexts=[];nodes=[];executors=[];checks={};error=None
packets=deque();source_raw={};destination_raw={};typed={};readiness=[];session=2026110919
try:
    for domain,name in [(96,'net01_raw_robot'),(97,'net01_raw_central')]:
        context=Context();rclpy.init(context=context,domain_id=domain,signal_handler_options=SignalHandlerOptions.NO)
        node=Node(name,context=context);executor=SingleThreadedExecutor(context=context);executor.add_node(node)
        contexts.append(context);nodes.append(node);executors.append(executor)
    r,c=nodes
    def send(peer,flow,body,rpc):
        if flow in (226,227):
            source_raw[flow]=body;packets.append((flow,body,rpc))
        elif flow==228:readiness.append(deserialize_message(body,Bool).data)
        else:raise RuntimeError('No-goal data fixture received an unexpected Action RPC')
    robot=ActionWire(r,send,robot=1,session_id=session)
    central=ActionWire(c,lambda *args:None,robots=(1,),session_id=session)
    central.timer.cancel();central._set_ready(1,True)
    # Explicit controlled facade only: no backend server/readiness claim.
    feedback=NavigateToPose.Impl.FeedbackMessage();feedback.goal_id.uuid=list(range(16))
    f=feedback.feedback;f.current_pose.header.frame_id='map';f.current_pose.header.stamp.sec=123;f.current_pose.header.stamp.nanosec=456
    f.current_pose.pose.position.x=1.25;f.current_pose.pose.position.y=-2.5;f.current_pose.pose.orientation.w=1.
    f.navigation_time.sec=3;f.navigation_time.nanosec=789;f.estimated_time_remaining.sec=7;f.estimated_time_remaining.nanosec=123
    f.number_of_recoveries=2;f.distance_remaining=2.75
    status=GoalStatusArray()
    for offset,code in [(0,4),(16,2)]:
        item=GoalStatus();item.goal_info.goal_id.uuid=list(range(offset,offset+16));item.goal_info.stamp.sec=120;item.goal_info.stamp.nanosec=offset+42;item.status=code;status.status_list.append(item)
    prefix='/tb1/navigate_to_pose/_action/'
    fp=r.create_publisher(NavigateToPose.Impl.FeedbackMessage,prefix+'feedback',10)
    sp=r.create_publisher(GoalStatusArray,prefix+'status',qos_profile_action_status_default)
    consumers=[]
    for flow,cls,suffix,qos in [(226,NavigateToPose.Impl.FeedbackMessage,'feedback',10),(227,GoalStatusArray,'status',qos_profile_action_status_default)]:
        consumers.append(c.create_subscription(cls,prefix+suffix,lambda msg,flow=flow:typed.__setitem__(flow,msg),qos))
        consumers.append(c.create_subscription(cls,prefix+suffix,lambda body,flow=flow:destination_raw.__setitem__(flow,body),qos,raw=True))
    deadline=time.monotonic()+12;published=False
    while time.monotonic()<deadline:
        for executor in executors:executor.spin_once(timeout_sec=0)
        while packets:
            flow,body,rpc=packets.popleft();central.receive(1,flow,body,rpc)
        if not published and fp.get_subscription_count() and sp.get_subscription_count() and all(p.get_subscription_count()>=2 for p in central.endpoints[1][1:]):
            fp.publish(feedback);sp.publish(status);published=True
        if set(typed)=={226,227} and set(destination_raw)=={226,227} and readiness:break
    checks['real_R_subscriptions_are_raw_original_types']=all(s.raw for s in robot.subscriptions) and robot.subscriptions[0].msg_type is NavigateToPose.Impl.FeedbackMessage and robot.subscriptions[1].msg_type is GoalStatusArray
    checks['matched_real_DDS_source_published']=published
    checks['R_native_raw_capture_is_bytes']=set(source_raw)=={226,227} and all(isinstance(b,bytes) for b in source_raw.values())
    checks['feedback_capture_to_C_DDS_raw_bytes_exact']=source_raw.get(226)==destination_raw.get(226) and 226 in source_raw
    checks['status_capture_to_C_DDS_raw_bytes_exact']=source_raw.get(227)==destination_raw.get(227) and 227 in source_raw
    checks['all_feedback_typed_fields_and_original_UUID_exact']=typed.get(226)==feedback
    checks['all_statuses_UUIDs_and_stamps_exact']=typed.get(227)==status
    checks['readiness_Bool_timer_remains_typed_false']=bool(readiness) and all(v is False for v in readiness)
    checks['no_goal_or_other_business_RPC']=robot.forwarded_requests==0 and not central.pending
    for flow,body in source_raw.items():(out/f'{flow}.cdr').write_bytes(body)
except BaseException as exc:error=repr(exc)
finally:
    for executor,node,context in zip(executors,nodes,contexts):
        executor.remove_node(node);executor.shutdown(timeout_sec=0);node.destroy_node();context.shutdown()
    result=dict(status='PASS' if error is None and all(checks.values()) and checks else 'FAIL',checks=checks,error=error,domains=dict(R=96,C=97),wire='Complete original Action CDR plus original flow/rpc in local queue, not WiFi',source_raw_bytes={k:len(v) for k,v in source_raw.items()},scope='Real DDS publisher→R raw ActionWire→complete local wire→C original typed publisher publish(bytes)→actual typed+raw DDS consumers; explicit controlled facade and canceled C expiry timer only for this data check, no native Nav2 readiness claim',calls=dict(Gazebo=0,NN=0,Goal=0,Nav2=0,Node=len(nodes)))
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if result['status']=='PASS' else 1)

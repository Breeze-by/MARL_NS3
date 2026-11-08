"""Real DDS reader-history fixture. No Gazebo, robot topics or motor commands.

Run with ROS_DOMAIN_ID=63, ROS_LOCALHOST_ONLY=1. Two static publishers model
robot_state_publisher and the independent map-alignment publisher. No spin
between reliable publications models a busy startup executor.
"""
import json
import ast
import os
from pathlib import Path
import time
import rclpy
from rclpy.duration import Duration
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSProfile,DurabilityPolicy,HistoryPolicy,ReliabilityPolicy
from rclpy.time import Time
from rclpy.utilities import get_rmw_implementation_identifier
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from tf2_ros import Buffer


def transform(parent, child, stamp=0):
    t=TransformStamped();t.header.frame_id=parent;t.child_frame_id=child
    t.header.stamp.sec=stamp;t.transform.rotation.w=1.
    return t


def configured_qos(source):
    """Evaluate the actual production profile and verify tf_static uses it."""
    tree=ast.parse(source.read_text())
    assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='static_qos' for t in n.targets))
    subscriptions=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and n.func.attr=='create_subscription' and len(n.args)>1 and any(isinstance(s,ast.Constant)
            and isinstance(s.value,str) and '/tf_static' in s.value for s in ast.walk(n.args[1]))]
    if len(subscriptions)!=1 or not isinstance(subscriptions[0].args[-1],ast.Name) or subscriptions[0].args[-1].id!='static_qos':
        raise AssertionError('Production tf_static subscription does not use its dedicated profile')
    return eval(compile(ast.Expression(assignment.value),str(source),'eval'),globals())


def case(depth, service_between, profile=None):
    suffix=f'{depth}_{int(service_between)}'
    topic='/base02_tf_history_fixture/case_'+suffix
    writers=[rclpy.create_node('tf_fixture_writer_'+suffix+'_'+str(i)) for i in (0,1)]
    reader=rclpy.create_node('tf_fixture_reader_'+suffix)
    qos=lambda size:QoSProfile(depth=size,history=HistoryPolicy.KEEP_LAST,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
    pubs=[n.create_publisher(TFMessage,topic,qos(100)) for n in writers]
    buffer=Buffer();received=[]
    buffer.set_transform(transform('diag/map','diag/odom',1),'fixture_dynamic')
    buffer.set_transform(transform('diag/odom','diag/foot',1),'fixture_dynamic')
    def callback(message):
        received.append([(t.header.frame_id,t.child_frame_id) for t in message.transforms])
        for t in message.transforms:buffer.set_transform_static(t,'fixture_static')
    subscription=reader.create_subscription(TFMessage,topic,callback,qos(depth) if profile is None else profile)
    executor=SingleThreadedExecutor();executor.add_node(reader)
    deadline=time.monotonic()+5
    while any(p.get_subscription_count()!=1 for p in pubs) and time.monotonic()<deadline:time.sleep(.02)
    if any(p.get_subscription_count()!=1 for p in pubs):raise RuntimeError('Fixture DDS discovery did not finish')
    messages=[TFMessage(transforms=[transform('diag/foot','diag/base_link'),transform('diag/base_link','diag/base_scan')]),
              TFMessage(transforms=[transform('diag/merge_map','diag/map')])]
    acks=[]
    for publisher,message in zip(pubs,messages):
        publisher.publish(message)
        acks.append(publisher.wait_for_all_acked(Duration(seconds=2)))
        if service_between:
            until=time.monotonic()+.3
            while time.monotonic()<until:executor.spin_once(timeout_sec=.02)
    # Let DDS enqueue both acknowledged samples; do not service the reader yet.
    time.sleep(.1)
    until=time.monotonic()+.5
    while time.monotonic()<until:executor.spin_once(timeout_sec=.02)
    result=dict(depth=depth,service_between_publications=service_between,reliable_acks=acks,
        received=received,ready=bool(buffer.can_transform('diag/map','diag/base_scan',Time())),
        debug=buffer.can_transform('diag/map','diag/base_scan',Time(),return_debug_tuple=True),
        frames=buffer.all_frames_as_yaml())
    executor.remove_node(reader);executor.shutdown()
    reader.destroy_subscription(subscription);reader.destroy_node()
    for n in writers:n.destroy_node()
    return result


if __name__=='__main__':
    if os.environ.get('ROS_DOMAIN_ID')!='63':raise RuntimeError('Use isolated diagnostic ROS_DOMAIN_ID=63')
    rclpy.init()
    try:
        root=Path('/project')
        profiles={name:configured_qos(path) for name,path in {
            'observer':root/'tools/run_baseline.py',
            'controller':root/'workspace/src/multi_robot_exploration/multi_robot_exploration/control.py'}.items()}
        results=[case(1,False),case(1,True)]
        for name,profile in profiles.items():
            result=case(profile.depth,False,profile);result['production_profile']=name;results.append(result)
        print(json.dumps(dict(rmw=get_rmw_implementation_identifier(),results=results),indent=2),flush=True)
        if not all(all(x['reliable_acks']) for x in results):raise AssertionError('DDS acknowledgements missing')
        if results[0]['ready'] or not all(r['ready'] for r in results[1:]):
            raise AssertionError('Reader-history hypothesis was not reproduced')
    finally:rclpy.shutdown()

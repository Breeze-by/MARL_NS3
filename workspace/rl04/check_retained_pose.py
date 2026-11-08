"""Actual callback/gate directed fixture: no ROS Node initialization, policy, action or env."""
import ast
import copy
from contextlib import nullcontext
import json
import math
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from tf2_ros import Buffer
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.allocation import Allocator


class FreshGateReached(Exception):pass


def run():
    ws=Path('/mnt/workspace');output=Path('/mnt/evidence/retained-pose-check-02');output.mkdir(exist_ok=False)
    source=ast.parse((ws/'rl01/ros_policy.py').read_text())
    original=next(c for c in source.body if isinstance(c,ast.ClassDef) and c.name=='CheckpointHeadquarters')
    methods=[m for m in original.body if isinstance(m,ast.FunctionDef) and m.name in ('robot_odom_callback','allocate_once')]
    assert len(methods)==2
    fixture=ast.Module(body=[ast.ClassDef(name='Harness',bases=[ast.Name(id='HeadquartersControl',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    context=dict(HeadquartersControl=HeadquartersControl,math=math)
    exec(compile(ast.fix_missing_locations(fixture),'<actual-rl01-callback-and-gate>','exec'),context)
    Harness=context['Harness']
    node=Harness.__new__(Harness)  # No inherited Node/__init__, clock, context or transport.
    import threading
    node.lock=threading.RLock();clock=[10.];events=[]
    node.now=lambda:clock[0];node.record=lambda event:events.append(copy.deepcopy(event));node.pose_tf_errors={}
    node.allocator=Allocator();node.allocator.update_map(np.zeros((80,80),dtype=np.int16),.05,(0.,0.),10.)
    for name in node.allocator.robots:node.allocator.update_robot(name,(1.,2.,0.),10.,(0.,0.,0.))
    node.tf={'tb1':Buffer()};node.goal_handles={};node.config=dict(episode_decisions=100);node.decisions=0
    node.ledger=SimpleNamespace(call=lambda *args,**kwargs:nullcontext(),add=lambda *args,**kwargs:None)
    def forbidden_policy(observation):raise FreshGateReached()
    node.policy=SimpleNamespace(select=forbidden_policy)
    def transform(stamp):
        t=TransformStamped();t.header.frame_id='merge_map';t.child_frame_id='odom';t.header.stamp.sec=int(stamp)
        t.header.stamp.nanosec=int(round((stamp-int(stamp))*1e9));t.transform.rotation.w=1.
        node.tf['tb1'].set_transform(t,'fixture_exact_tf')
    def odom(stamp,vx=.26,vy=0.):
        m=Odometry();m.header.frame_id='odom';m.child_frame_id='base_footprint'
        m.header.stamp.sec=int(stamp);m.header.stamp.nanosec=int(round((stamp-int(stamp))*1e9))
        m.pose.pose.position.x=1.;m.pose.pose.position.y=2.
        m.pose.pose.orientation.z=m.pose.pose.orientation.w=math.sqrt(.5)
        m.twist.twist.linear.x=vx;m.twist.twist.linear.y=vy;m.twist.twist.angular.z=.1
        return m
    transform(10.);node.robot_odom_callback(odom(10.),'tb1')
    state=node.allocator.robots['tb1'];first=(state.pose,state.stamp,state.velocity)
    assert np.allclose(state.velocity,(0.,.26,.1),atol=1e-10)
    clock[0]=10.1;node.robot_odom_callback(odom(10.1),'tb1')  # Authentic future extrapolation.
    assert (state.pose,state.stamp,state.velocity)==first
    assert node.pose_tf_errors['tb1']['count']==1 and node.pose_tf_errors['tb1']['error']=='ExtrapolationException'
    try:node.allocate_once()
    except FreshGateReached:pass
    else:raise AssertionError('Fresh retained state did not pass the existing gate')
    clock[0]=12.01
    for name in ('tb2','tb3'):node.allocator.update_robot(name,(1.,2.,0.),12.01,(0.,0.,0.))
    stale=node.allocate_once();assert stale['state']=='awaiting_fresh_state'
    stale_event=next(e for e in reversed(events) if e['kind']=='rl_wait_fresh_state')
    assert stale_event['pose_ages_s']['tb1']>2. and stale_event['pose_ages_s']['tb2']==stale_event['pose_ages_s']['tb3']==0.
    clock[0]=12.1;transform(12.1);node.robot_odom_callback(odom(12.1,.1,.2),'tb1')
    assert state.stamp==12.1 and np.allclose(state.velocity,(-.2,.1,.1),atol=1e-10)
    for name in ('tb2','tb3'):node.allocator.update_robot(name,(1.,2.,0.),12.1,(0.,0.,0.))
    try:node.allocate_once()
    except FreshGateReached:pass
    else:raise AssertionError('New exact success did not restore freshness')
    # A missing initial state remains unavailable; no last-valid value is invented.
    node.allocator.robots['tb1'].pose=None;node.allocator.robots['tb1'].stamp=None
    node.tf['tb1']=Buffer();node.robot_odom_callback(odom(12.1),'tb1')
    missing=node.allocate_once();assert missing['state']=='awaiting_observation'
    assert node.allocator.robots['tb1'].pose is None
    assert stale_event['pose_tf_errors']['tb1']['count']==1 and stale_event['pose_tf_errors']['tb1']['sim']==10.1
    result=dict(status='PASS',actual_parent_callback=True,actual_RL_callback_and_gate_AST=True,
        exact_success_then_future_failure_retains_pose_stamp_velocity=True,retained_velocity_not_rotated_twice=True,
        original_2s_stale_gate_rejects=True,new_exact_success_recovers=True,initial_missing_not_invented=True,
        errors_logged_only_at_waits=True,last_tf_error=node.pose_tf_errors,events=events,
        supersedes='check01 retained mutable event aliases; production immediate JSON unaffected. This fixture deepcopies snapshots and isolates stale rejection to tb1 only.',
        ros_Node_init=0,rclpy_init=0,model_load=0,nn_forward=0,policy_sampling=0,goal_dispatch=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('events','last_tf_error')},indent=2))


if __name__=='__main__':run()

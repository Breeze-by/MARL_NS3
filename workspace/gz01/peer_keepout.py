"""ROS-observable peer keepout masks; no goal or velocity publisher."""
import argparse
from array import array
from collections import deque
import json
import math
from pathlib import Path
import time

import numpy as np
from multi_robot_exploration.observations import project_local_navigation
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.time import Time
from nav_msgs.msg import OccupancyGrid, Odometry
from nav2_msgs.msg import CostmapFilterInfo
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage
from tf2_ros import Buffer, TransformException

ROBOTS=('tb1','tb2','tb3')
# .25m own Nav2 radius + .237m peer body envelope + .063m margin.
# The user's .30m centre alarm is separate from physical configuration space.
RADIUS=.55
RESOLUTION=.05
# Per-owner fixed odom extent is the original common origin translated by
# its declared initial calibration and snapped to the native .05m lattice.
# It is never used as an exploration denominator or policy observation.
SIZE=400
ORIGIN=(-9.,-9.)
ODOM_MAX_AGE=.4
ODOM_RECEIPT_MAX_AGE=.2
CLOCK_QUANTUM=.1  # Existing Gazebo /clock publisher is 10Hz.
CORRECTION_MAX_AGE=.55
CORRECTION_FUTURE=.2+CLOCK_QUANTUM  # Existing SLAM transform future tolerance.
CORRECTION_POSITION_JUMP_M=1.0  # Gross localization INVALID, not a safe-motion bound.


def peer_mask(robot, poses, origin):
    y,x=np.indices((SIZE,SIZE))
    x=origin[0]+(x+.5)*RESOLUTION;y=origin[1]+(y+.5)*RESOLUTION
    blocked=np.zeros((SIZE,SIZE),dtype=bool)
    # Include any mask cell intersecting the continuous exclusion disk.
    r=RADIUS+RESOLUTION/math.sqrt(2)
    for name,p in poses.items():
        if name!=robot:blocked |= (x-p[0])**2+(y-p[1])**2<=r*r
    # Outside peers is NO_INFORMATION, not free: Keepout otherwise overwrites
    # primary unknown(255) with background0. Primary-layer copy clears old disks.
    return np.where(blocked,100,-1).astype(np.int8)


def mask_xy(point, transform):
    tx,ty,yaw=transform;c,s=math.cos(yaw),math.sin(yaw)
    return (tx+c*point[0]-s*point[1],ty+s*point[0]+c*point[1])


def mask_poses(robot, state):
    return {name:mask_xy(p,state['mask_from_common'][robot]) for name,p in state['poses'].items()}


def state_fresh(state, now):
    if state is None or not state['ready']:return False
    # One end-to-end budget from original source stamps. Do not add a second
    # delivery allowance or impose a separate generation-age ceiling.
    if now-state['generated_sim'] < -CLOCK_QUANTUM-1e-6:return False
    return all(state['generated_sim']-state['odom_stamps'][r]>=-CLOCK_QUANTUM-1e-6
               and now-state['odom_stamps'][r]<=ODOM_MAX_AGE+1e-6
               and state['generated_sim']-state['correction_stamps'][r]>=-CORRECTION_FUTURE-1e-6
               and now-state['correction_stamps'][r]<=CORRECTION_MAX_AGE+1e-6
               for r in ROBOTS)


def target_allowed(robot, target, state, now):
    if not state_fresh(state,now):return False
    target=mask_xy(target,state['mask_from_common'][robot])
    origin=state['origins'][robot]
    col=math.floor((target[0]-origin[0])/RESOLUTION);row=math.floor((target[1]-origin[1])/RESOLUTION)
    if not (0<=row<SIZE and 0<=col<SIZE):return False
    cell=(origin[0]+(col+.5)*RESOLUTION,origin[1]+(row+.5)*RESOLUTION)
    return all(math.dist(cell,p[:2])>RADIUS+RESOLUTION/math.sqrt(2)
               for name,p in mask_poses(robot,state).items() if name!=robot)


def route_blocked(robot, shared, state, now):
    """Same peer raster, projected once for both route graphs; never clears seed."""
    if not state_fresh(state,now):return np.ones(shared['cells'].shape,dtype=bool)
    origin=state['origins'][robot]
    mask=peer_mask(robot,mask_poses(robot,state),origin)
    return project_local_navigation(mask,RESOLUTION,(*origin,0.),state['mask_from_common'][robot],shared)==100


def timed_peer_call(node, stage, callback, robot, *args, **kwargs):
    """RAM-only public-call span; preserve the callback return and exception."""
    begin=time.monotonic();cpu=time.thread_time()
    sim=node.get_clock().now().nanoseconds*1e-9;sequence=node.sequence
    if stage=='publish_masks' and node.timing_health_return is not None:
        health=node.timing_health_return
        if begin-health['monotonic']>.3:
            summary=dict(health_return=health.copy(),timer_entry_monotonic=begin,
                gap_wall_s=begin-health['monotonic'],gap_thread_cpu_s=cpu-health['thread_cpu'],
                sequence_before=sequence,sim_at_entry=sim)
            node.timing_gaps.append(summary)
            if node.timing_first_gap is None:
                node.timing_first_gap=dict(summary,context=list(node.timing_rows),closed=False)
    try:
        return callback(*args,**kwargs)
    finally:
        end_cpu=time.thread_time();end=time.monotonic()
        row=dict(stage=stage,robot=robot,begin_monotonic=begin,end_monotonic=end,
            wall_s=end-begin,begin_thread_cpu=cpu,end_thread_cpu=end_cpu,
            thread_cpu_s=end_cpu-cpu,sim_before=sim,
            sim_after=node.get_clock().now().nanoseconds*1e-9,
            sequence_before=sequence,sequence_after=node.sequence)
        node.timing_rows.append(row)
        key=stage+'|'+str(robot)
        stats=node.timing_stats.setdefault(key,dict(calls=0,max_wall=row))
        stats['calls']+=1
        if row['wall_s']>stats['max_wall']['wall_s']:stats['max_wall']=row
        if row['wall_s']>=.02:node.timing_long_spans.append(row)
        gap=node.timing_first_gap
        if gap is not None and not gap['closed']:
            gap['context'].append(row)
            if stage=='spin_once':gap['closed']=True


def install_peer_timing(node):
    # Bound public methods: subscription lambdas still invoke the same methods.
    for stage,index in (('receive_tf',1),('receive_odom',1),('project_latest',0),('publish_masks',None)):
        callback=getattr(node,stage)
        setattr(node,stage,lambda *args,callback=callback,stage=stage,index=index,**kwargs: timed_peer_call(
            node,stage,callback,None if index is None else (args[index] if len(args)>index else kwargs['robot']),
            *args,**kwargs))
    # Includes the real TimeSource /clock callback, without a second subscription.
    for subscription in node.subscriptions:
        if subscription.topic_name=='/clock':
            callback=subscription.callback
            subscription.callback=lambda *args,callback=callback,**kwargs: timed_peer_call(
                node,'clock',callback,None,*args,**kwargs)


class PeerKeepout(Node):
    def __init__(self, scene, directory, timing=False):
        super().__init__('peer_keepout')
        self.poses={r['name']:(r['x'],r['y']) for r in scene['robots']}
        self.origins={r['name']:[math.floor((ORIGIN[i]-r[k])/RESOLUTION)*RESOLUTION
            for i,k in enumerate(('x','y'))] for r in scene['robots']}
        self.mask_from_common={};self.mask_frames={}
        self.odom={};self.received={};self.tf={r:Buffer(cache_time=Duration(seconds=10),node=self) for r in ROBOTS}
        self.valid_stamps={};self.valid_receipts={}
        self.correction_stamps={};self.correction_receipts={}
        self.correction_values={};self.localization_invalid={}
        self.pending_tf={}
        self.directory=directory;self.event_lines=[]
        self.subs=[];self.maps={};self.info={}
        latched=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        static=QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        for robot in ROBOTS:
            self.subs += [self.create_subscription(Odometry,f'/{robot}/odom',lambda m,r=robot:self.receive_odom(m,r),10),
                self.create_subscription(TFMessage,f'/{robot}/tf',lambda m,r=robot:self.receive_tf(m,r,False),100),
                self.create_subscription(TFMessage,f'/{robot}/tf_static',lambda m,r=robot:self.receive_tf(m,r,True),static)]
            self.maps[robot]=self.create_publisher(OccupancyGrid,f'/{robot}/peer_keepout_mask',latched)
            self.info[robot]=self.create_publisher(CostmapFilterInfo,f'/{robot}/peer_keepout_filter_info',latched)
            msg=CostmapFilterInfo();msg.type=0;msg.base=0.;msg.multiplier=1.;msg.filter_mask_topic=f'/{robot}/peer_keepout_mask'
            self.info[robot].publish(msg)
        self.health=self.create_publisher(String,'/peer_keepout_state',1)
        self.sequence=0
        self.timing_rows=deque(maxlen=4096) if timing else None
        self.timing_stats={};self.timing_long_spans=[];self.timing_gaps=[]
        self.timing_health_return=None;self.timing_first_gap=None
        if timing:install_peer_timing(self)
        self.timer=self.create_timer(.1,self.publish_masks)

    def receive_odom(self,msg,robot):
        self.odom[robot]=msg;self.received[robot]=time.monotonic()
        self.project_latest(robot)

    def receive_tf(self,msg,robot,static):
        for transform in msg.transforms:
            if static:self.tf[robot].set_transform_static(transform,robot)
            else:self.tf[robot].set_transform(transform,robot)
            if transform.header.frame_id=='map' and transform.child_frame_id=='odom':
                self.correction_receipts[robot]=time.monotonic()
        self.project_latest(robot)

    def project_latest(self,robot):
        if robot not in self.odom:return
        odom=self.odom[robot]
        try:
            correction=self.tf[robot].lookup_transform('merge_map',odom.header.frame_id,Time())
            t=correction.transform
        except TransformException as error:
            self.pending_tf[robot]=str(error);return
        q=t.rotation;yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));p=odom.pose.pose.position
        current=(t.translation.x,t.translation.y,yaw)
        position=mask_xy((p.x,p.y),current)
        previous=self.correction_values.get(robot)
        if previous is not None and robot not in self.localization_invalid:
            old_position=mask_xy((p.x,p.y),previous)
            difference=math.dist(old_position,position)
            if difference>CORRECTION_POSITION_JUMP_M:
                self.localization_invalid[robot]=dict(reason='localization_discontinuity',
                    position_change_m=difference,old_correction=previous,new_correction=current,
                    old_position=old_position,new_position=position,encoder_position=(p.x,p.y),
                    old_correction_stamp=self.correction_stamps[robot],
                    new_correction_stamp=correction.header.stamp.sec+correction.header.stamp.nanosec*1e-9,
                    odom_stamp=odom.header.stamp.sec+odom.header.stamp.nanosec*1e-9)
        self.correction_values[robot]=current
        # Keep the actual new pose, even after INVALID; never freeze the old TF.
        self.poses[robot]=position
        self.mask_from_common[robot]=(-math.cos(yaw)*t.translation.x-math.sin(yaw)*t.translation.y,
            math.sin(yaw)*t.translation.x-math.cos(yaw)*t.translation.y,-yaw)
        self.mask_frames[robot]=odom.header.frame_id
        self.valid_stamps[robot]=odom.header.stamp.sec+odom.header.stamp.nanosec*1e-9
        self.valid_receipts[robot]=self.received[robot]
        self.correction_stamps[robot]=correction.header.stamp.sec+correction.header.stamp.nanosec*1e-9
        self.pending_tf.pop(robot,None)

    def publish_masks(self):
        timing=dict(entry_monotonic=time.monotonic(),masks={})
        now=self.get_clock().now().nanoseconds*1e-9
        ages={};failures={}
        for robot in ROBOTS:
            if robot not in self.odom:
                failures[robot]='missing_odom';continue
            # Current encoder pose composed with the latest RECEIVED SLAM
            # correction. The correction timestamp is not the robot-pose age.
            if robot not in self.valid_stamps:
                failures[robot]='no_source_time_TF_pose';continue
            ages[robot]=dict(source=now-self.valid_stamps[robot],receipt=time.monotonic()-self.valid_receipts[robot],
                correction=now-self.correction_stamps[robot],
                correction_receipt=time.monotonic()-self.correction_receipts[robot])
            if not (-CLOCK_QUANTUM-1e-6<=ages[robot]['source']<=ODOM_MAX_AGE+1e-6 and ages[robot]['receipt']<=ODOM_RECEIPT_MAX_AGE):failures[robot]='stale_odom'
            if not -CORRECTION_FUTURE-1e-6<=ages[robot]['correction']<=CORRECTION_MAX_AGE+1e-6:
                failures[robot]='stale_localization_correction'
        for robot in self.localization_invalid:failures[robot]='localization_discontinuity'
        ready=not failures
        origins=self.origins
        self.sequence+=1
        state=dict(time_contract='peer-e2e-time-v1',generated_sim=now,ready=ready,sequence=self.sequence,poses=self.poses.copy(),origins=origins,
                   mask_contract='owner-odom-lattice-v1',mask_from_common=self.mask_from_common.copy(),mask_frames=self.mask_frames.copy(),
                   radius_m=RADIUS,resolution=RESOLUTION,ages=ages,failures=failures,pending_tf=self.pending_tf.copy(),
                   odom_stamps=self.valid_stamps.copy(),correction_stamps=self.correction_stamps.copy(),
                   localization_contract='loop-confidence-v2-latched-correction-guard',
                   localization_invalid=self.localization_invalid.copy(),
                   source='CURRENT encoder odom x latest RECEIVED SLAM correction; separate stamps/ages; no prediction or Gazebo truth')
        timing['snapshot_monotonic']=time.monotonic()
        for robot in ROBOTS:
            begin=time.monotonic()
            grid=OccupancyGrid();grid.header.stamp=self.get_clock().now().to_msg();grid.header.frame_id='odom'
            grid.info.resolution=RESOLUTION;grid.info.width=grid.info.height=SIZE
            grid.info.origin.position.x,grid.info.origin.position.y=origins[robot];grid.info.origin.orientation.w=1.
            if ready:grid.header.frame_id=self.mask_frames[robot]
            data=peer_mask(robot,mask_poses(robot,state),origins[robot]) if ready else np.full((SIZE,SIZE),100,dtype=np.int8)
            built=time.monotonic()
            grid.data=array('b',data.tobytes());before=time.monotonic()
            self.maps[robot].publish(grid)
            timing['masks'][robot]=dict(begin=begin,built=built,before_publish=before,after_publish=time.monotonic())
        msg=String();msg.data=json.dumps(state)
        timing['health_publish_before_monotonic']=time.monotonic()
        self.health.publish(msg)
        timing['health_publish_after_monotonic']=time.monotonic()
        if self.timing_rows is not None:
            self.timing_health_return=dict(monotonic=timing['health_publish_after_monotonic'],
                sequence=self.sequence,sim=now,thread_cpu=time.thread_time())
        # These local timings are producer evidence, not delivery/reader ACK.
        self.event_lines.append(json.dumps(dict(state,delivery_timing=timing))+'\n')


    def persist_records(self):
        with (self.directory/'peer-keepout.jsonl').open('x') as stream:
            stream.writelines(self.event_lines)
        # Created only after the raw records have closed successfully; checked by the supervisor.
        (self.directory/'peer-recording-saved.json').write_text(json.dumps(dict(
            saved=True,rows=len(self.event_lines),last_sequence=self.sequence,
            phase='after_peer_spin_exit'),indent=2))


    def persist_timing(self):
        if self.timing_rows is not None:
            (self.directory/'peer_timing.json').write_text(json.dumps(dict(
                scope='Diagnostic only; public callbacks and original global executor spin_once; RAM until spin exit',
                rows=list(self.timing_rows),stage_summary=self.timing_stats,
                first_health_timer_gap=self.timing_first_gap,gap_summaries=self.timing_gaps,
                long_spans=self.timing_long_spans),indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--timing',action='store_true')
    args,ros_args=p.parse_known_args();rclpy.init(args=ros_args)
    node=PeerKeepout(json.loads(args.scene.read_text()),args.directory,timing=args.timing)
    if args.timing:
        executor=rclpy.get_global_executor()
        original_spin_once=executor.spin_once
        executor.spin_once=lambda *a,**kw: timed_peer_call(node,'spin_once',original_spin_once,None,*a,**kw)
    try:rclpy.spin(node)
    finally:
        if args.timing:executor.spin_once=original_spin_once
        try:
            node.persist_records()
            node.persist_timing()
        finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

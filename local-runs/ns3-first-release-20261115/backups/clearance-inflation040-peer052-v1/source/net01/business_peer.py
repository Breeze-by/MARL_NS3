"""Versioned Peer receipt-time adapter; frozen Peer source remains unchanged.

The explicit sim-business profile changes only the .2-second odom receipt
clock. Original source-age gates, poses, masks and diagnostic wall timings are
retained. publish_masks mirrors the frozen implementation because it exposes
no receipt-clock hook; legacy profiles delegate to that implementation.
"""
from array import array
import json
import time
import numpy as np
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import String
import peer_keepout as frozen
from peer_keepout import (ROBOTS, CLOCK_QUANTUM, ODOM_MAX_AGE,
    ODOM_RECEIPT_MAX_AGE, CORRECTION_FUTURE, CORRECTION_MAX_AGE,
    RADIUS, RESOLUTION, SIZE, mask_poses)


class BusinessPeer(frozen.PeerKeepout):
    def receive_odom(self,message,robot):
        if self.sim_business_receipt:
            self.odom_receipt_sim_ns[robot]=self.get_clock().now().nanoseconds
        return super().receive_odom(message,robot)

    def project_latest(self,robot):
        value=super().project_latest(robot)
        if self.sim_business_receipt and robot in self.valid_stamps and robot not in self.pending_tf:
            # Match frozen valid_receipts: only a successfully projected pose
            # inherits the original odom receipt, never the later TF callback.
            self.valid_receipt_sim_ns[robot]=self.odom_receipt_sim_ns[robot]
        return value

    def publish_masks(self):
        if not self.sim_business_receipt:return super().publish_masks()
        timing=dict(entry_monotonic=time.monotonic(),masks={})
        now_ns=self.get_clock().now().nanoseconds
        now=now_ns*1e-9
        ages={};failures={}
        for robot in ROBOTS:
            if robot not in self.odom:
                failures[robot]='missing_odom';continue
            # Current encoder pose composed with the latest RECEIVED SLAM
            # correction. The correction timestamp is not the robot-pose age.
            if robot not in self.valid_stamps:
                failures[robot]='no_source_time_TF_pose';continue
            ages[robot]=dict(source=now-self.valid_stamps[robot],receipt=(now_ns-self.valid_receipt_sim_ns[robot])/1e9,
                receipt_wall=time.monotonic()-self.valid_receipts[robot],
                correction=now-self.correction_stamps[robot],
                correction_receipt=time.monotonic()-self.correction_receipts[robot])
            if not (-CLOCK_QUANTUM-1e-6<=ages[robot]['source']<=ODOM_MAX_AGE+1e-6 and ages[robot]['receipt']<=ODOM_RECEIPT_MAX_AGE):failures[robot]='stale_odom'
            if not -CORRECTION_FUTURE-1e-6<=ages[robot]['correction']<=CORRECTION_MAX_AGE+1e-6:
                failures[robot]='stale_localization_correction'
        for robot in self.localization_invalid:failures[robot]='localization_discontinuity'
        ready=not failures
        origins=self.origins
        self.sequence+=1
        state=dict(time_contract='peer-e2e-time-sim-business-v1',odom_receipt_clock_basis='ros-sim-v1',generated_sim=now,ready=ready,sequence=self.sequence,poses=self.poses.copy(),origins=origins,
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
            data=frozen.peer_mask(robot,mask_poses(robot,state),origins[robot]) if ready else np.full((SIZE,SIZE),100,dtype=np.int8)
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


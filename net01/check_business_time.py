"""No-motion ROS Node/clock/CDR checks of the explicit business-time profile.

Actual ROS entities and clocks; delivery and sim event order are controlled.
No Gazebo, Nav2 execution, network simulation or policy inference is started.
"""
import argparse
import json
from pathlib import Path
import time
from unittest.mock import patch

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.time import Time
from rclpy.serialization import serialize_message,deserialize_message
from std_msgs.msg import Bool
from nav_msgs.msg import Odometry,OccupancyGrid
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from action_wire import ActionWire
from bound_peer import BoundPeer
import peer_keepout as frozen
from execution_profile import SIM_BUSINESS_PROFILE_ID,load_profile
from delivery_guard import DeliveryGuard
from time_control_state import TimeControlState


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output;output.mkdir(parents=True,exist_ok=False)
    result=dict(status='FAIL',checks={},scope='Actual no-motion ROS Nodes/clocks/timers/CDR; controlled delivery; no live Nav2/Gazebo/ns3')
    nodes=[];wires=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        result['checks'][name]=True
    def stamp(node,seconds):node.get_clock().set_ros_time_override(Time(nanoseconds=round(seconds*1e9)))
    def action_run(pause):
        node=Node('business_action_'+str(len(nodes)),parameter_overrides=[Parameter('use_sim_time',value=True)])
        nodes.append(node);stamp(node,100.)
        sent=[];faults=[]
        action=ActionWire(node,lambda peer,flow,body,rpc:sent.append((peer,flow,bytes(body),rpc)),
            robots=(1,),session_id=91,reliable=True,transport_error=faults.append,
            business_now_ns=lambda:node.get_clock().now().nanoseconds)
        wires.append(action)
        check('readiness_timer_uses_ROS_clock',action.timer.clock is node.get_clock())
        action.receive(1,228,serialize_message(Bool(data=True)),(91<<32)|1)
        request=NavigateToPose.Impl.GetResultService.Request();request.goal_id.uuid=[9]*16
        rpc=action.next_id();action._send_rpc(1,2,serialize_message(request),rpc)
        observations=[]
        for elapsed in (.1,.2,.22,.5,.51,.84,1.):
            time.sleep(pause);stamp(node,100.+elapsed)
            action.reliability_tick()
            if elapsed==.22:
                action.receive(1,229,bytes((1,2)),rpc)
                action.receive(1,229,bytes((1,2)),rpc)
            action.poll_readiness()
            if elapsed==.2:check('nonzero_epoch_exact_point2_retry',action.transfers[(1,2,rpc)]['attempts']==2)
            if elapsed==.5:check('nonzero_epoch_exact_point5_readiness_still_valid',action.ready[1])
            observations.append((elapsed,action.ready[1],action.transfers[(1,2,rpc)]['attempts'],
                action.transfers[(1,2,rpc)]['state']))
        check('confirmed_RPC_duplicate_ACK_no_fault',not faults and action.transfers[(1,2,rpc)]['state']=='ACKED')
        stamp(node,102.);rpc=action.next_id();action._send_rpc(1,2,serialize_message(request),rpc)
        for elapsed in (.2,.4,.6,.8):
            time.sleep(pause);stamp(node,102.+elapsed);action.reliability_tick()
        before=action.transfers[(1,2,rpc)]['attempts']
        # Simulated time pauses while real wall time passes; business cannot expire.
        time.sleep(.25);action.reliability_tick()
        check('paused_sim_does_not_advance_RPC_business_deadline',action.transfers[(1,2,rpc)]['attempts']==before and not faults)
        stamp(node,103.);action.receive(1,229,bytes((1,2)),rpc)
        check('ACK_at_sim_deadline_stays_UNCONFIRMED',len(faults)==1 and action.transfers[(1,2,rpc)]['state']=='UNCONFIRMED')
        return dict(observations=observations,lost_attempts=before,final=action.transfers[(1,2,rpc)]['state'])
    def peer_run(profile,pause):
        scene=dict(robots=[dict(name='tb'+str(i),x=float(i),y=0.) for i in (1,2,3)])
        peer=BoundPeer(scene,output,session_id=91,execution_profile=profile);nodes.append(peer)
        stamp(peer,200.)
        for robot in frozen.ROBOTS:
            odom=Odometry();odom.header.stamp.sec=200;odom.header.frame_id='odom'
            peer.receive_odom(odom,robot)
            peer.valid_stamps[robot]=200.;peer.valid_receipts[robot]=peer.received[robot]
            peer.valid_receipt_sim_ns[robot]=200_000_000_000
            peer.correction_stamps[robot]=200.;peer.correction_receipts[robot]=time.monotonic()
            peer.mask_from_common[robot]=(0.,0.,0.);peer.mask_frames[robot]='odom'
        peer.publish_masks();first=json.loads(peer.event_lines[-1])
        time.sleep(pause);peer.publish_masks();paused=json.loads(peer.event_lines[-1])
        stamp(peer,200.2);peer.publish_masks();edge=json.loads(peer.event_lines[-1])
        if profile==SIM_BUSINESS_PROFILE_ID:check('Peer_exact_nonzero_epoch_point2_boundary_remains_ready',edge['ready'])
        stamp(peer,200.21);peer.publish_masks();stale=json.loads(peer.event_lines[-1])
        return peer,first,paused,stale
    try:
        rclpy.init(args=['--ros-args','-p','use_sim_time:=true'],domain_id=97)
        fast=action_run(.001);slow=action_run(.012)
        check('same_sim_events_two_wall_paces_same_Action_outputs',fast==slow)
        profile=load_profile(SIM_BUSINESS_PROFILE_ID)
        peer,first,paused,stale=peer_run(SIM_BUSINESS_PROFILE_ID,.25)
        check('new_profile_real_Peer_publish_fresh_and_paused',first['ready'] and paused['ready'])
        check('new_profile_point2_sim_receipt_gate_preserved',not stale['ready'] and
            all(v=='stale_odom' for v in stale['failures'].values()))
        check('wall_receipt_diagnostics_retained',all(a['receipt_wall']>.2 and abs(a['receipt'])<1e-9 for a in paused['ages'].values()))
        fast_peer,fast_first,fast_paused,fast_stale=peer_run(SIM_BUSINESS_PROFILE_ID,.001)
        check('same_sim_events_two_wall_paces_same_Peer_ready',
            [first['ready'],paused['ready'],stale['ready']]==[fast_first['ready'],fast_paused['ready'],fast_stale['ready']])
        stamp(peer,200.22)
        odom=Odometry();odom.header.stamp.sec=200;odom.header.stamp.nanosec=220_000_000;odom.header.frame_id='odom'
        peer.receive_odom(odom,'tb1')
        check('failed_TF_projection_does_not_refresh_valid_receipt',
            peer.odom_receipt_sim_ns['tb1']==200_220_000_000 and peer.valid_receipt_sim_ns['tb1']==200_000_000_000 and 'tb1' in peer.pending_tf)
        peer.publish_masks()
        check('failed_projection_old_pose_receipt_stays_expired',json.loads(peer.event_lines[-1])['failures']['tb1']=='stale_odom')
        stamp(peer,200.25)
        transform=TransformStamped();transform.header.frame_id='merge_map';transform.child_frame_id='odom'
        transform.header.stamp.sec=200;transform.header.stamp.nanosec=220_000_000;transform.transform.rotation.w=1.
        peer.receive_tf(TFMessage(transforms=[transform]),'tb1',False)
        check('delayed_TF_success_binds_original_odom_receipt_not_TF_time',
            peer.valid_receipt_sim_ns['tb1']==200_220_000_000 and 'tb1' not in peer.pending_tf)
        stamp(peer,200.42);peer.publish_masks()
        check('delayed_projection_exact_receipt_boundary_preserved','tb1' not in json.loads(peer.event_lines[-1])['failures'])
        stamp(peer,200.43);peer.publish_masks()
        check('delayed_projection_receipt_expires_from_odom_time',json.loads(peer.event_lines[-1])['failures']['tb1']=='stale_odom')
        legacy,old_first,old_paused,old_stale=peer_run(profile['predecessor'],.25)
        check('old_profile_keeps_point2_wall_receipt_gate',old_first['ready'] and not old_paused['ready'])
        # Prove the adapted fresh publication retains the frozen mask bytes.
        bodies={}
        for robot,publisher in peer.maps.items():
            original=publisher.publisher
            class Capture:
                def publish(self,message,robot=robot):bodies[robot]=bytes(serialize_message(message))
            publisher.publisher=Capture()
        stamp(peer,201.)
        for robot in frozen.ROBOTS:
            peer.valid_stamps[robot]=201.;peer.correction_stamps[robot]=201.
            peer.odom_receipt_sim_ns[robot]=201_000_000_000;peer.valid_receipt_sim_ns[robot]=201_000_000_000;peer.valid_receipts[robot]=time.monotonic()
        peer.publish_masks();adapted=bodies.copy()
        frozen.PeerKeepout.publish_masks(peer)
        result['mask_compare']={r:dict(bytes_equal=bodies[r]==adapted[r],message_equal=deserialize_message(bodies[r],OccupancyGrid)==deserialize_message(adapted[r],OccupancyGrid),first_different=[i for i,(a,b) in enumerate(zip(bodies[r],adapted[r])) if a!=b][:20]) for r in bodies}
        check('fresh_masks_all_fields_match_frozen_publication',all(row['message_equal'] for row in result['mask_compare'].values()))
        now=[10.];wall=[0.];stops=[]
        guard=DeliveryGuard(1,91,lambda:now[0],stops.append,wall_now=lambda:wall[0],execution_profile=profile)
        control=dict(session_id=91,failure=None,mode='RUN',authority_exited=False,expected_shutdown=False)
        guard.control_state(control)
        state=dict(ready=True,sequence=1,generated_sim=10.,odom_stamps={r:10. for r in frozen.ROBOTS},correction_stamps={r:10. for r in frozen.ROBOTS})
        guard.receive_health(state);guard.receive_bound(dict(robot='tb1',session_id=91,bound_state=state))
        check('new_profile_guard_arms_with_fresh_sim_inputs',guard.arm())
        wall[0]=2.01;guard.tick()
        check('paused_sim_independent_wall_protection_retained',guard.fault=='time_control_state_wall_timeout' and len(stops)==1)
        coordinator=TimeControlState(progress_wall_timeout_ns=2_000_000_000)
        coordinator.observe_motion_armed(0);coordinator.check_progress(2_000_000_001)
        check('coordinator_actual_clock_wall_watchdog_retained',coordinator.failure=='actual_clock_progress_wall_timeout')
        result.update(status='PASS',action_fast=fast,action_slow=slow,
            profile=profile['id'],peer_receipt_clock=paused['odom_receipt_clock_basis'],
            remaining_blocker='Installed Nav2 BT/control loops retain wall-clock execution; this component check does not establish closed-loop pacing invariance')
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        for wire in wires:wire.close()
        for node in nodes:node.destroy_node()
        rclpy.try_shutdown()
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

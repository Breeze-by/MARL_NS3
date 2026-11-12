"""Bounded generated-Action/DDS -> actual ns3 WiFi -> DDS fixture.

Controlled Action servers have no motion publishers. The clock is synthetic
transport metadata, not Gazebo /clock. This is NOT real Nav2/Gazebo acceptance.
The hub must already be owned/running with the fixed channel-blackout fixture flag.
"""
import argparse
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_action_status_default
from rclpy.serialization import serialize_message, deserialize_message
from unique_identifier_msgs.msg import UUID
from action_msgs.msg import GoalStatusArray
from nav2_msgs.action import NavigateToPose

from action_wire import ActionWire
from check_action_wire import ControlledServer
from hub_client import HubClient
from link_session import LinkSession


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--socket',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result=dict(status='RUNNING',checks={},domains={'C':93,'R':94},session_id=41,
        scope='real FastRTPS/generated Action over actual ns3 WiFi; controlled no-motion servers and synthetic transport ticks',
        Nav2=False,Gazebo=False,NN=False,training=False,velocity_publishers=0,
        RMW_IMPLEMENTATION=os.environ.get('RMW_IMPLEMENTATION'),
        fault_scope='CHANNEL_FAULT_V1: post-LogDistance Range gate; channel_blackout, not PHY power-off')
    hub=HubClient(args.socket);link=LinkSession(hub,session_id=41)
    contexts=[];nodes=[];executors=[];bridges={};servers={};clients={}
    feedback={r:[] for r in (1,2,3)};statuses={r:[] for r in (1,2,3)}
    emitted=[];received=[];sent_bodies={};captures=[]
    start=time.monotonic();deadline=start+75.
    clock_target=None;next_clock=start

    def check(name,condition):
        assert condition,name
        result['checks'][name]=True;print('PASS',name,flush=True)

    def send(sender,dest,flow,body,rpc_id):
        body=bytes(body)
        emitted.append(dict(sender=sender,receiver=dest,flow=flow,rpc_id=rpc_id,
            body_hex=body.hex(),capture_controlled_horizon_ns=hub.horizon_ns,
            source_stamp_ns=0,source_stamp_available=False,monotonic_ns=time.monotonic_ns()))
        sent_bodies[(sender,dest,flow,rpc_id)]=body.hex()
        if sender==0 and flow%20==0:captures.append((dest,flow,body,rpc_id))
        hub.send(sender,dest,flow,body,rpc_id,source_stamp_ns=0)

    def delivered(meta,cdr,rpc_id):
        if link.receive(meta,cdr,rpc_id):return
        received.append(dict(meta,rpc_id=rpc_id,body_hex=bytes(cdr).hex()))
        # No source cache participates in delivery or ROS publication.
        bridges[meta['receiver']].receive(meta['sender'],meta['flow'],cdr,rpc_id)
    hub.receive=delivered

    def pump():
        nonlocal clock_target,next_clock
        if time.monotonic()>deadline:raise TimeoutError('75wall Action/WiFi fixture bound')
        hub.poll()
        for executor in executors:executor.spin_once(timeout_sec=.001)
        if clock_target is not None and hub.horizon_ns==clock_target:
            clock_target=None;next_clock=time.monotonic()+.1
        if hub.ready and clock_target is None and time.monotonic()>=next_clock:
            clock_target=hub.horizon_ns+100_000_000
            hub.clock(clock_target)
        hub.poll()

    def until(predicate,limit=10.):
        end=min(deadline,time.monotonic()+limit)
        while not predicate() and time.monotonic()<end:pump()
        if not predicate():raise TimeoutError('Action/WiFi condition deadline')

    def duration(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:pump()

    def goal(robot,number):
        request=NavigateToPose.Goal();request.pose.header.frame_id='map'
        request.pose.header.stamp.sec=123;request.pose.header.stamp.nanosec=456789
        request.pose.pose.position.x=number+.125;request.pose.pose.position.y=-2.75
        request.pose.pose.orientation.z=.6;request.pose.pose.orientation.w=.8
        request.behavior_tree='fixture-original-tree-field'
        uuid=UUID(uuid=list(bytes([robot,number])+bytes(range(2,16))))
        return request,uuid

    try:
        until(lambda:hub.ready)
        until(lambda:hub.horizon_ns>=600_000_000)
        link.begin();until(lambda:link.ready)
        check('one_actual_HELLO_ACK_all_three_STA_before_business',link.ready and not emitted)
        for domain,name in ((93,'net01_action_wifi_c'),(94,'net01_action_wifi_r')):
            context=Context();rclpy.init(context=context,domain_id=domain)
            contexts.append(context);node=Node(name,context=context);nodes.append(node)
            executor=SingleThreadedExecutor(context=context);executor.add_node(node);executors.append(executor)
        cnode,rnode=nodes
        central=ActionWire(cnode,lambda dest,flow,body,rpc:send(0,dest,flow,body,rpc),session_id=41)
        bridges[0]=central
        for robot in (1,2,3):
            bridges[robot]=ActionWire(rnode,lambda dest,flow,body,rpc,robot=robot:send(robot,dest,flow,body,rpc),robot=robot,session_id=41)
            clients[robot]=ActionClient(cnode,NavigateToPose,ActionWire.name(robot),callback_group=ReentrantCallbackGroup())
        status_subs=[cnode.create_subscription(GoalStatusArray,ActionWire.name(robot)+'/_action/status',
            lambda msg,robot=robot:statuses[robot].extend((bytes(s.goal_info.goal_id.uuid).hex(),s.status) for s in msg.status_list),
            qos_profile_action_status_default) for robot in (1,2,3)]
        duration(.7)
        check('absent_real_server_no_WiFi_fabricated_C_endpoints',not central.endpoints and not any(c.server_is_ready() for c in clients.values()))
        for robot in (1,2,3):servers[robot]=ControlledServer(rnode,robot)
        until(lambda:all(c.server_is_ready() for c in clients.values()))
        check('actual_remote_five_endpoints_and_WiFi_readiness',all(bridges[r].backend_is_ready() and central.ready[r] for r in (1,2,3)))

        def send_goal(robot,number):
            request,uuid=goal(robot,number)
            future=clients[robot].send_goal_async(request,goal_uuid=uuid,
                feedback_callback=lambda msg:feedback[robot].append(msg))
            until(future.done);handle=future.result();uuid_hex=bytes(uuid.uuid).hex()
            until(lambda:uuid_hex in servers[robot].executing)
            check(f'tb{robot}_actual_accept_original_UUID_goal_frame_stamp',handle.accepted and handle.goal_id==uuid and deserialize_message(bytes.fromhex(servers[robot].accepted[-1]),NavigateToPose.Goal)==request)
            return uuid_hex,handle

        uuid1,handle1=send_goal(1,1);outcome1=handle1.get_result_async()
        until(lambda:bool(feedback[1]) and (uuid1,2) in statuses[1])
        check('WiFi_GetResult_waits_for_actual_terminal',not outcome1.done())
        feedback_message=feedback[1][-1]
        check('WiFi_feedback_all_typed_fields_original_UUID',feedback_message.goal_id==handle1.goal_id and any(p['flow']==226 and deserialize_message(bytes.fromhex(p['body_hex']),NavigateToPose.Impl.FeedbackMessage)==feedback_message for p in received))
        servers[1].release.add(uuid1);until(outcome1.done);until(lambda:(uuid1,4) in statuses[1])
        check('WiFi_real_SUCCEEDED_result_and_dynamic_status',outcome1.result().status==4)

        uuid2,handle2=send_goal(2,2);outcome2=handle2.get_result_async()
        until(lambda:bool(feedback[2]));cancel=handle2.cancel_goal_async();until(cancel.done)
        check('WiFi_cancel_real_response_UUID_list',cancel.result().return_code==0 and [g.goal_id for g in cancel.result().goals_canceling]==[handle2.goal_id])
        until(outcome2.done);until(lambda:(uuid2,5) in statuses[2])
        check('WiFi_real_CANCELED_result_status_same_UUID',outcome2.result().status==5 and uuid2 in servers[2].cancelled)

        uuid3,handle3=send_goal(3,3);outcome3=handle3.get_result_async()
        servers[3].release.add(uuid3);until(outcome3.done);until(lambda:(uuid3,4) in statuses[3])
        check('third_STA_actual_SUCCEEDED',outcome3.result().status==4)

        original=captures[0]
        accepted_before={r:len(s.accepted) for r,s in servers.items()}
        forwards_before={r:bridges[r].forwarded_requests for r in (1,2,3)}
        blackout_wall=time.monotonic();blackout_sim=hub.horizon_ns
        hub.radio_fault(False)
        lost_request,lost_uuid=goal(1,4)
        lost_future=clients[1].send_goal_async(lost_request,goal_uuid=lost_uuid)
        until(lambda:len(captures)>3,limit=.4)
        lost_packet=captures[-1]
        until(lambda:hub.horizon_ns-blackout_sim>=1_200_000_000 and time.monotonic()-blackout_wall>=.8)
        until(lambda:not central.endpoints and not any(c.server_is_ready() for c in clients.values()))
        check('actual_channel_blackout_withdraws_C_endpoints',not central.endpoints)
        check('channel_blackout_request_not_accepted_no_fake_response_or_closure',not lost_future.done() and {r:len(s.accepted) for r,s in servers.items()}==accepted_before and not any(p['receiver']==1 and p['flow']==lost_packet[1] and p['rpc_id']==lost_packet[3] for p in received))
        count=len(captures);duration(.15)
        check('no_new_Action_dispatch_after_readiness_expiry',len(captures)==count)

        hub.radio_fault(True)
        until(lambda:all(c.server_is_ready() for c in clients.values()))
        # Reinject the exact already-completed Action RPC through actual WiFi;
        # a new native message ID must not become another Nav2 submission.
        cached_responses=sum(p['sender']==1 and p['flow']==original[1]+1 and p['rpc_id']==original[3] for p in received)
        send(0,original[0],original[1],original[2],original[3])
        until(lambda:bridges[1].duplicate_requests==1)
        until(lambda:sum(p['sender']==1 and p['flow']==original[1]+1 and p['rpc_id']==original[3] for p in received)>cached_responses)
        duration(.2)
        check('recovery_same_RPC_over_WiFi_never_resubmits_goal',not lost_future.done() and {r:len(s.accepted) for r,s in servers.items()}==accepted_before and {r:bridges[r].forwarded_requests for r in (1,2,3)}==forwards_before)

        rxkeys={(p['sender'],p['receiver'],p['flow'],p['rpc_id']) for p in received}
        check('request_response_same_RPC_both_directions',all(
            any((robot,0,200+robot*20+offset+1,p['rpc_id']) in rxkeys
                for p in received if p['sender']==0 and p['receiver']==robot and p['flow']==200+robot*20+offset)
            for robot in (1,2,3) for offset in ((0,2,4) if robot==2 else (0,2))))
        first_ready={r:next(p['rpc_id'] for p in received if p['sender']==r and p['flow']==200+r*20+8) for r in (1,2,3)}
        check('three_R_same_RPC_value_routes_without_collision',len(set(first_ready.values()))==1)
        check('received_business_CDR_matches_actual_sent_full_payload',all(p['body_hex']==sent_bodies[(p['sender'],p['receiver'],p['flow'],p['rpc_id'])] for p in received))
        native_ids=[p['message_id'] for p in hub.deliveries]
        check('native_message_ids_unique_independent_of_Action_RPC',len(native_ids)==len(set(native_ids)))
        check('all_nine_generated_Action_flow_kinds_really_received',all(any(p['flow']%20==offset for p in received) for offset in range(9)))
        result.update(status='PASS',accepted_per_robot=accepted_before,first_readiness_rpc=first_ready,
            lost_goal_uuid=bytes(lost_uuid.uuid).hex(),lost_goal_future_pending=not lost_future.done(),
            pending_on_withdrawal='unknown; no cross-reconnect fake accept/rejection/terminal',
            controlled_horizon_ns=hub.horizon_ns,elapsed_wall_s=time.monotonic()-start,
            source_clock_scope='no Action generation stamp available: native source_stamp_ns=0; capture controlled horizon separate; generated Action stamps unchanged',
            emitted_messages=len(emitted),received_messages=len(received))
    except BaseException as error:
        result.update(status='FAIL',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (args.output/'emitted-CDR.json').write_text(json.dumps(emitted,indent=2)+'\n')
        (args.output/'received-CDR.json').write_text(json.dumps(received,indent=2)+'\n')
        (args.output/'link-events.json').write_text(json.dumps(link.events,indent=2)+'\n')
        (args.output/'native-deliveries.json').write_text(json.dumps(hub.deliveries,indent=2)+'\n')
        for server in servers.values():server.close()
        for client in clients.values():client.destroy()
        for bridge in bridges.values():bridge.close()
        for executor in executors:executor.shutdown(timeout_sec=0.)
        for node in nodes:node.destroy_node()
        for context in contexts:context.shutdown()
        hub.end()
        end=time.monotonic()+2.
        while hub.outgoing and time.monotonic()<end:hub.poll()
        hub.close()


if __name__=='__main__':main()

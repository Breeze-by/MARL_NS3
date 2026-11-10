"""One staged real Gateway/DDS/ns3-WiFi Action fixture, no physical robots.

LocalStop health/bound inputs are explicitly synthetic fixture state, as in the
existing local-guard test. Only Action traffic is under test; no safety/SLAM
qualification is inferred. ACK-specific drops below happen AFTER real WiFi RX
and are labelled application fault injection, not PHY loss.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import qos_profile_sensor_data,qos_profile_action_status_default
from rclpy.serialization import deserialize_message,serialize_message
from rosgraph_msgs.msg import Clock
from unique_identifier_msgs.msg import UUID

from action_wire import ActionWire
from check_action_wire import ControlledServer
from gateway import Gateway


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--socket',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    directory=args.output/'gateway';directory.mkdir()
    start=time.monotonic();deadline=start+45.
    result=dict(status='RUNNING',checks={},domains=[91,92],session_id=5002,
        scope='Actual Gateway/real DDS controlled Action servers/actual ns3 WiFi; no Nav2/Gazebo/Policy',
        health_bound_source='synthetic fresh fixture intake only; not radio health/mask qualification',
        nonzero_velocity_publishers=0,physical_stop_certified=False)
    gateway=None;servers={};clients={};feedback={r:[] for r in (1,2,3)}
    statuses={r:[] for r in (1,2,3)};zeros={r:[] for r in (1,2,3)};pauses=[]
    injections=[];actual_packets=[];next_clock=start;clock_ns=0;sequence=0
    drop_getresult_ack=True;drop_sendgoal_response_ack=True
    expected_goals={}

    def check(name,value):
        assert value,name
        result['checks'][name]=True;print('PASS',name,flush=True)

    def fresh():
        nonlocal sequence
        if gateway.failure is not None:return
        now=gateway.r.get_clock().now().nanoseconds/1e9;sequence+=1
        state=dict(ready=True,sequence=sequence,generated_sim=now,
            odom_stamps={f'tb{r}':now for r in (1,2,3)},
            correction_stamps={f'tb{r}':now for r in (1,2,3)})
        for robot,stop in gateway.guards.items():
            stop.guard.receive_health(state)
            stop.guard.receive_bound(dict(robot=f'tb{robot}',session_id=5002,bound_state=state))

    def pump():
        nonlocal next_clock,clock_ns
        now=time.monotonic()
        if now>=deadline:raise TimeoutError('45wall ROS active-loop bound; outer60wall includes teardown')
        if gateway.failure is None and now>=next_clock:
            clock_ns+=10_000_000;message=Clock()
            message.clock.sec,message.clock.nanosec=divmod(clock_ns,1_000_000_000)
            clock.publish(message);next_clock=now+.01
        fresh();gateway.poll()

    def until(predicate,limit=6.):
        end=min(deadline,time.monotonic()+limit)
        while not predicate() and time.monotonic()<end:pump()
        if not predicate():raise TimeoutError('reliable Action fixture condition')

    def duration(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:pump()

    def request(robot,number):
        goal=NavigateToPose.Goal();goal.pose.header.frame_id='map'
        goal.pose.header.stamp.sec=123;goal.pose.header.stamp.nanosec=456789
        goal.pose.pose.position.x=number+.125;goal.pose.pose.position.y=-2.75
        goal.pose.pose.orientation.z=.6;goal.pose.pose.orientation.w=.8
        goal.behavior_tree='unchanged-generated-fixture-goal'
        return goal,UUID(uuid=list(bytes([robot,number])+bytes(range(2,16))))

    def send_goal(robot,number):
        goal,uuid=request(robot,number)
        expected_goals[bytes(uuid.uuid).hex()]=deserialize_message(serialize_message(goal),NavigateToPose.Goal)
        future=clients[robot].send_goal_async(goal,goal_uuid=uuid,
            feedback_callback=lambda msg:feedback[robot].append(msg))
        return uuid,future

    def confirm_goal(robot,uuid,future):
        until(future.done);handle=future.result();key=bytes(uuid.uuid).hex()
        until(lambda:key in servers[robot].executing)
        original=deserialize_message(bytes.fromhex(servers[robot].accepted[-1]),NavigateToPose.Goal)
        check(f'tb{robot}_real_client_accept_original_UUID_and_all_Goal_fields',handle.accepted and
            handle.goal_id==uuid and original==expected_goals[key])
        return key,handle

    try:
        gateway=Gateway('B',args.socket,directory,5002,control_trace=True,
            execution_profile='original1000-clock100-q10ms')
        original_receive=gateway.receive
        def delivered(meta,body,rpc):
            nonlocal drop_getresult_ack,drop_sendgoal_response_ack
            actual_packets.append(dict(meta,rpc_id=rpc,body_hex=bytes(body).hex()))
            drop=(drop_getresult_ack and meta['sender']==2 and meta['receiver']==0 and meta['flow']==249 and body==bytes((1,2)))
            drop_response=(drop_sendgoal_response_ack and meta['sender']==0 and meta['receiver']==3 and meta['flow']==269 and body==bytes((1,1)))
            if drop or drop_response:
                if drop:drop_getresult_ack=False
                if drop_response:drop_sendgoal_response_ack=False
                injections.append(dict(kind='application_drop_after_actual_native_RX',meta=meta,rpc_id=rpc,
                    body_hex=bytes(body).hex(),monotonic=time.monotonic()))
                return
            original_receive(meta,body,rpc)
        gateway.hub.receive=delivered
        clock=gateway.r.create_publisher(Clock,'/clock',qos_profile_sensor_data)
        until(lambda:gateway.connected)
        duration(.6)  # bounded discovery observation, not a fake connectivity ACK
        services=[name for name,types in gateway.r.get_service_names_and_types()
            if any(name.startswith(f'/tb{r}/navigate_to_pose/_action/') or
                name==f'/tb{r}/lifecycle_manager_navigation/manage_nodes' for r in (1,2,3))]
        foreign_drive_readers={r:[info.node_name for info in gateway.r.get_subscriptions_info_by_topic(f'/tb{r}/cmd_vel')
            if info.node_name!=gateway.r.get_name()] for r in (1,2,3)}
        ready_clients={f'tb{r}:offset{offset}':client.service_is_ready()
            for r,action in gateway.action_r.items() for offset,client in action.clients.items()}
        ready_pause={r:stop.pause.service_is_ready() for r,stop in gateway.guards.items()}
        # The graph's unqualified service-topic list includes local clients;
        # only the existing typed clients test real server availability.
        result['preflight']=dict(discovered_service_topics=services,foreign_cmd_vel_readers=foreign_drive_readers,
            Action_server_ready=ready_clients,PAUSE_server_ready=ready_pause)
        check('isolated_domain_no_real_Action_lifecycle_or_robot_driver_before_fixture',
            not any(ready_clients.values()) and not any(ready_pause.values()) and
            not any(foreign_drive_readers.values()) and not gateway.action_c.endpoints)
        for robot in (1,2,3):
            servers[robot]=ControlledServer(gateway.r,robot)
            clients[robot]=ActionClient(gateway.c,NavigateToPose,ActionWire.name(robot),callback_group=ReentrantCallbackGroup())
            gateway.c.create_subscription(GoalStatusArray,ActionWire.name(robot)+'/_action/status',
                lambda msg,robot=robot:statuses[robot].extend((bytes(s.goal_info.goal_id.uuid).hex(),s.status) for s in msg.status_list),
                qos_profile_action_status_default)
            gateway.r.create_subscription(Twist,f'/tb{robot}/cmd_vel',lambda msg,robot=robot:zeros[robot].append(msg),10)
            def pause(req,resp,robot=robot):
                pauses.append(dict(robot=robot,command=req.command));resp.success=True;return resp
            gateway.r.create_service(ManageLifecycleNodes,f'/tb{robot}/lifecycle_manager_navigation/manage_nodes',pause)
        fresh()
        check('synthetic_fixture_guard_inputs_explicitly_arm',all(stop.guard.arm() for stop in gateway.guards.values()))
        until(lambda:all(c.server_is_ready() for c in clients.values()))
        check('real_five_endpoints_after_actual_three_STA_handshake',gateway.link.ready and
            all(a.backend_is_ready() for a in gateway.action_r.values()))

        # The first request and its first automatic retry meet a real channel
        # blackout. The window is below existing C readiness expiry, unchanged.
        gateway.hub.radio_fault(False);uuid1,future1=send_goal(1,1)
        until(lambda:any(r['kind']=='action_CDR_capture' and r['sender']==0 and r['flow']==220 for r in gateway.records))
        first_request=next(r for r in gateway.records if r['kind']=='action_CDR_capture' and r['sender']==0 and r['flow']==220)
        duration(.25)
        check('physical_blackout_request_not_whole_received_before_restore',not future1.done() and
            not any(r['receiver']==1 and r['flow']==220 and r['rpc_id']==first_request['rpc_id'] for r in actual_packets))
        gateway.hub.radio_fault(True)
        key1,handle1=confirm_goal(1,uuid1,future1)
        attempts=[r for r in gateway.action_c.reliability_events if r['kind']=='original_CDR_attempt' and r['rpc_id']==first_request['rpc_id']]
        check('lost_request_recovered_same_RPC_one_real_goal',len(attempts)>=2 and len(servers[1].accepted)==1)
        result1=handle1.get_result_async();servers[1].release.add(key1);until(result1.done)
        until(lambda:(key1,4) in statuses[1])
        check('recovered_goal_real_SUCCESS_feedback_status',result1.result().status==4 and bool(feedback[1]))

        uuid2,future2=send_goal(2,2);key2,handle2=confirm_goal(2,uuid2,future2)
        result2=handle2.get_result_async()
        until(lambda:any(key[0]==2 and key[1]==2 and t['state']=='ACKED'
            for key,t in gateway.action_c.transfers.items()))
        wait_begin=time.monotonic();duration(1.2)
        check('GetResult_real_wait_beyond_confirmation_budget_no_false_fault',not result2.done() and
            gateway.failure is None and time.monotonic()-wait_begin>=1.2 and not drop_getresult_ack)
        get_keys=[key for key in gateway.action_c.pending if key[0]==2 and key[1]==3]
        get_rpc=get_keys[0][2]
        check('lost_request_ACK_deduplicated_without_second_GetResult_call',gateway.action_r[2].duplicate_requests>=1 and
            gateway.action_r[2].forwarded_requests==2 and (242,get_rpc) in gateway.action_r[2].requests)
        gateway.hub.radio_fault(False);servers[2].release.add(key2)
        until(lambda:gateway.action_r[2].requests[(242,get_rpc)] is not None)
        duration(.25)
        check('physical_blackout_response_not_whole_received_before_restore',not result2.done() and
            not any(r['receiver']==0 and r['flow']==243 and r['rpc_id']==get_rpc for r in actual_packets))
        gateway.hub.radio_fault(True);until(result2.done)
        check('lost_real_response_retried_same_CDR_to_original_client',result2.result().status==4 and
            gateway.action_r[2].transfers[(2,3,get_rpc)]['attempts']>=2)

        uuid3,future3=send_goal(3,3);completion=[];future3.add_done_callback(lambda f:completion.append(f.result()))
        key3,handle3=confirm_goal(3,uuid3,future3)
        until(lambda:not drop_sendgoal_response_ack and gateway.action_r[3].reliability_status()['waiting']==0)
        check('lost_response_ACK_recovered_no_second_DDS_accept',len(completion)==1 and len(servers[3].accepted)==1)
        result3=handle3.get_result_async();cancel=handle3.cancel_goal_async();until(cancel.done);until(result3.done)
        until(lambda:(key3,5) in statuses[3])
        check('real_Cancel_UUID_list_and_CANCELED_terminal',cancel.result().return_code==0 and
            [g.goal_id for g in cancel.result().goals_canceling]==[uuid3] and result3.result().status==5)
        until(lambda:all(a.reliability_status()['waiting']==0 for a in (gateway.action_c,*gateway.action_r.values())))
        check('healthy_rpc_and_confirmation_counts_drained',not gateway.action_c.pending and
            all(value is not None for a in gateway.action_r.values() for value in a.requests.values()))
        result['positive_phase']=dict(accepted={r:len(s.accepted) for r,s in servers.items()},
            outcomes={1:result1.result().status,2:result2.result().status,3:result3.result().status},
            ACK_injections=injections)
        captured={(r['sender'],r['receiver'],r['flow'],r['rpc_id'],r['cdr_sha256'])
            for r in gateway.records if r['kind']=='action_CDR_capture'}
        check('all_actual_Action_CDR_bytes_equal_captured_full_payload',all(
            (r['sender'],r['receiver'],r['flow'],r['rpc_id'],hashlib.sha256(bytes.fromhex(r['body_hex'])).hexdigest()) in captured
            for r in actual_packets if r['flow']>=200))

        # Permanent partition: readiness withdrawal can fail closed BEFORE the
        # one-second transport ceiling. Neither original limit is relaxed.
        gateway.hub.radio_fault(False);lost_uuid,lost=send_goal(1,4)
        until(lambda:gateway.failure is not None,limit=3.)
        check('permanent_partition_latches_actual_Gateway_INVALID_unknown',not lost.done() and
            gateway.action_c.pending and gateway.action_c.reliability_status()['unconfirmed']>=1 and
            len(servers[1].accepted)==1)
        failure=gateway.failure;counts=[len(a.reliability_events) for a in (gateway.action_c,*gateway.action_r.values())]
        emitted=sum(r['kind']=='action_CDR_capture' for r in gateway.records)
        # Explicit method-level replay of a previously actual native packet:
        # not a fresh radio delivery, and not an ideal cleanup business path.
        saved=next(r for r in actual_packets if r['flow']==221)
        replay={k:v for k,v in saved.items() if k not in ('body_hex','rpc_id')}
        gateway.record('fixture_postfailure_replay_of_saved_actual_RX')
        gateway.receive(replay,bytes.fromhex(saved['body_hex']),saved['rpc_id'])
        duration(.15)
        check('failure_stops_reliable_sends_and_discards_late_business',gateway.failure==failure and not lost.done() and
            sum(r['kind']=='action_CDR_capture' for r in gateway.records)==emitted and
            any(r['kind']=='post_fault_business_discarded' for r in gateway.records))
        until(lambda:all(zeros[r] for r in (1,2,3)) and len(pauses)>=3 and
            all(future.done() for stop in gateway.guards.values() for future in stop.futures) and
            all(any(row['kind']=='actual_local_pause_response' and row['success'] for row in stop.records)
                for stop in gateway.guards.values()))
        check('original_local_zero_PAUSE_continue_after_fault',all(m==Twist() for rows in zeros.values() for m in rows) and
            all(p['command']==ManageLifecycleNodes.Request.PAUSE for p in pauses) and
            all(any(row['kind']=='actual_local_pause_response' and row['success'] for row in stop.records)
                for stop in gateway.guards.values()))
        result.update(status='PASS within controlled fixture; final transport INVALID is expected',
            expected_failure=failure,lost_UUID=bytes(lost_uuid.uuid).hex(),lost_future_unknown=not lost.done(),
            autonomous_goal_or_physical_stop_verified=False,elapsed_wall_s=time.monotonic()-start)
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));raise
    finally:
        if gateway is not None:
            result['confirmation_state']={'C':gateway.action_c.reliability_snapshot(),
                'R':{r:a.reliability_snapshot() for r,a in gateway.action_r.items()}} if gateway.wires is not None else None
            for server in servers.values():server.close()
            for client in clients.values():client.destroy()
            result['Gateway_clean_return']=gateway.close()
            result['cleanup']=gateway.cleanup
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (args.output/'actual-native-CDR.json').write_text(json.dumps(actual_packets,indent=2)+'\n')
        (args.output/'fixture-injections.json').write_text(json.dumps(injections,indent=2)+'\n')
    print(json.dumps(result['checks']),flush=True)


if __name__=='__main__':main()

"""30wall real-DDS local-stop fixture; no robot/Nav2/Gazebo/physical-stop claim.

Controlled Action servers and PAUSE spy services exercise exact UUID cleanup.
Health/bound inputs are explicitly synthetic fresh fixture states, not sensors.
"""
import argparse
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from geometry_msgs.msg import Twist
from rosgraph_msgs.msg import Clock
from builtin_interfaces.msg import Time
from unique_identifier_msgs.msg import UUID

from check_action_wire import ControlledServer
from delivery_guard import LocalStop


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result=dict(status='RUNNING',checks={},domain=95,RMW_IMPLEMENTATION=os.environ.get('RMW_IMPLEMENTATION'),
        scope='controlled real-DDS Action/local-stop interface fixture only',
        Nav2=False,Gazebo=False,NN=False,ns3=False,physical_stop_certified=False,
        pause_service='real DDS spy returning success, no physical effect',
        health_source='synthetic fixture health/bound state only')
    deadline=time.monotonic()+30.;context=Context();nodes=[];stops=[]
    server=None;executor=None;zeros={1:[],2:[]};pauses=[];input_sequence=0

    def check(name,condition):
        assert condition,name
        result['checks'][name]=True;print('PASS',name,flush=True)

    def fresh(stop):
        nonlocal input_sequence
        input_sequence+=1;now=stop.node.get_clock().now().nanoseconds/1e9
        state=dict(ready=True,sequence=input_sequence,generated_sim=now,
            odom_stamps={r:now for r in ('tb1','tb2','tb3')},
            correction_stamps={r:now for r in ('tb1','tb2','tb3')})
        stop.guard.receive_health(state)
        stop.guard.receive_bound(dict(robot=f'tb{stop.robot}',session_id=61,bound_state=state))

    def pump():
        if time.monotonic()>deadline:raise TimeoutError('30wall local guard fixture bound')
        # R1's healthy fixture input remains fresh until the explicit trip.
        if stops and stops[0].guard.fault is None:fresh(stops[0])
        executor.spin_once(timeout_sec=.002)

    def until(predicate,limit=6.):
        end=min(deadline,time.monotonic()+limit)
        while not predicate() and time.monotonic()<end:pump()
        if not predicate():raise TimeoutError('local guard condition deadline')

    def duration(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:pump()

    def request(number):
        req=NavigateToPose.Impl.SendGoalService.Request()
        req.goal_id=UUID(uuid=list(bytes([1,number])+bytes(range(2,16))))
        req.goal.pose.header.frame_id='map';req.goal.pose.header.stamp.sec=100
        req.goal.pose.pose.position.x=number+.125;req.goal.pose.pose.orientation.w=1.
        return req

    try:
        rclpy.init(context=context,domain_id=95)
        fixture=Node('net01_local_guard_fixture',context=context)
        node1=Node('net01_local_guard_tb1',context=context)
        node2=Node('net01_local_guard_tb2_paused_clock',context=context,
            parameter_overrides=[Parameter('use_sim_time',value=True)])
        nodes=[fixture,node1,node2]
        executor=SingleThreadedExecutor(context=context)
        for node in nodes:executor.add_node(node)
        server=ControlledServer(fixture,1)
        for robot in (1,2):
            def pause(request,response,robot=robot):
                pauses.append(dict(robot=robot,command=request.command,monotonic=time.monotonic()))
                response.success=True;return response
            fixture.create_service(ManageLifecycleNodes,f'/tb{robot}/lifecycle_manager_navigation/manage_nodes',pause)
            fixture.create_subscription(Twist,f'/tb{robot}/cmd_vel',
                lambda msg,robot=robot:zeros[robot].append((msg,time.monotonic())),10)
        stops=[LocalStop(node1,1,61),LocalStop(node2,2,61)]
        stop=stops[0]
        send=fixture.create_client(NavigateToPose.Impl.SendGoalService,'/tb1/navigate_to_pose/_action/send_goal')
        get=fixture.create_client(NavigateToPose.Impl.GetResultService,'/tb1/navigate_to_pose/_action/get_result')
        until(lambda:send.service_is_ready() and get.service_is_ready() and
            all(s.cancel.service_is_ready() if s.robot==1 else True for s in stops) and
            all(s.pause.service_is_ready() and s.zero.get_subscription_count()>0 for s in stops))

        foreign=request(9);foreign_uuid=bytes(foreign.goal_id.uuid).hex()
        foreign_response=send.call_async(foreign);until(foreign_response.done)
        until(lambda:foreign_uuid in server.executing)
        foreign_get=NavigateToPose.Impl.GetResultService.Request();foreign_get.goal_id=foreign.goal_id
        foreign_result=get.call_async(foreign_get)
        check('foreign_goal_real_accepted_and_not_registered_owned',foreign_response.result().accepted and foreign_uuid not in stop.owned)

        fresh(stop);check('fresh_fixture_inputs_explicit_arm',stop.guard.arm())
        owned=request(1);owned_uuid=bytes(owned.goal_id.uuid).hex()
        check('observe_send_goal_registers_original_pending_UUID',stop.observe_send_goal(owned) and owned_uuid in stop.owned)
        accepted=send.call_async(owned);until(accepted.done)
        until(lambda:owned_uuid in server.executing)
        check('actual_accept_response_held_before_local_hook',accepted.result().accepted and owned_uuid not in stop.accepted and owned_uuid not in stop.terminals)

        stop.guard.trip('controlled_link_loss_before_accept_hook')
        until(lambda:bool(zeros[1]) and any(p['robot']==1 for p in pauses))
        check('trip_zero_pause_does_not_fake_pending_closure',owned_uuid in stop.owned and owned_uuid not in stop.terminals and owned_uuid not in stop.stopped and not server.cancelled)
        stop.observe_goal_response(owned,accepted.result())
        stop.observe_goal_response(owned,accepted.result())  # transport duplicate
        until(lambda:owned_uuid in stop.terminals and any(r['kind']=='actual_local_GetResult' for r in stop.records))
        cancel_records=[r for r in stop.records if r['kind']=='actual_local_cancel_response']
        get_records=[r for r in stop.records if r['kind']=='actual_local_GetResult']
        check('late_actual_accept_exactly_one_same_UUID_cancel',server.cancelled==[owned_uuid] and stop.stopped=={owned_uuid} and len(cancel_records)==1 and cancel_records[0]['goals_canceling']==[owned_uuid])
        check('actual_local_CANCELED_status_and_GetResult5',stop.terminals[owned_uuid]==5 and len(get_records)==1 and get_records[0]['uuid']==owned_uuid and get_records[0]['status']==5)
        check('foreign_UUID_not_cancelled_by_owned_cleanup',foreign_uuid in server.executing and not foreign_result.done() and foreign_uuid not in server.cancelled and foreign_uuid not in stop.terminals)
        fresh(stop)
        check('latched_gate_rejects_new_SendGoal_no_automatic_rearm',not stop.guard.arm() and not stop.guard.may_send_goal() and not stop.observe_send_goal(request(2)))

        # A single actual /clock sample establishes 100sim and then pauses.
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        clock=fixture.create_publisher(Clock,'/clock',qos)
        until(lambda:clock.get_subscription_count()>0)
        clock.publish(Clock(clock=Time(sec=100)))
        until(lambda:node2.get_clock().now().nanoseconds==100_000_000_000)
        fresh(stops[1]);check('paused_sim_clock_guard_explicitly_armed',stops[1].guard.arm())
        health_receipt=stops[1].guard.health_receipt
        wall_start=time.monotonic()
        until(lambda:stops[1].guard.fault is not None and bool(zeros[2]) and any(p['robot']==2 for p in pauses))
        elapsed=time.monotonic()-wall_start
        trip=next(event for event in stops[1].guard.events if event['kind']=='latched_INVALID')
        check('steady_timer_trips_after_original_point3_wall_with_clock_paused',trip['monotonic']-health_receipt>.3 and node2.get_clock().now().nanoseconds==100_000_000_000 and stops[1].guard.fault=='health_heartbeat_stale')
        check('all_actual_cmd_vel_messages_are_exact_zero',all(message==Twist() for rows in zeros.values() for message,_ in rows))
        check('all_actual_pause_RPC_are_original_PAUSE',bool(pauses) and all(p['command']==ManageLifecycleNodes.Request.PAUSE for p in pauses))

        server.release.add(foreign_uuid);until(foreign_result.done)
        check('foreign_fixture_cleanup_succeeds_without_cancel',foreign_result.result().status==4 and foreign_uuid not in server.cancelled)
        result.update(status='PASS',owned_uuid=owned_uuid,foreign_uuid=foreign_uuid,
            server_cancelled=server.cancelled,paused_clock_wall_to_trip_s=elapsed,
            paused_clock_sim_ns=node2.get_clock().now().nanoseconds,
            zero_samples={r:len(rows) for r,rows in zeros.items()},pauses=pauses,
            local_records={s.robot:s.records for s in stops},guard_events={s.robot:s.guard.events for s in stops})
    except BaseException as error:
        result.update(status='FAIL',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if server is not None:server.close()
        if executor is not None:executor.shutdown(timeout_sec=0.)
        for node in nodes:node.destroy_node()
        context.shutdown()


if __name__=='__main__':main()

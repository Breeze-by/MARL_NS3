"""P5 independent C-domain merge or real ActionClient/journal role; no policy.

Merge uses only actual C-domain received maps. The client never injects guardian
state, arms a local guard, sends clock or changes the network. Host owns the
single negative phase and final STOP; this process remains alive to observe it.
"""
import argparse
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO),str(REPO/'net01'),str(REPO/'workspace/src/merge_map')]


def publish_marker(path, row):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('x') as stream:
        json.dump(row,stream);stream.write('\n')
    temporary.rename(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--role',choices=('merge','client'),required=True)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,required=True)
    parser.add_argument('--session-id',type=int,required=True)
    parser.add_argument('--active-wall',type=float,default=32.)
    parser.add_argument('--journal',type=Path)
    parser.add_argument('--normal-done-file',type=Path)
    parser.add_argument('--allow-negative-file',type=Path)
    parser.add_argument('--negative-active-ready-file',type=Path)
    args=parser.parse_args()
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import qos_profile_action_status_default,QoSProfile,DurabilityPolicy
    from rclpy.serialization import serialize_message
    from rclpy.signals import SignalHandlerOptions
    from nav2_msgs.action import NavigateToPose
    from action_msgs.msg import GoalStatusArray
    from nav_msgs.msg import OccupancyGrid
    from unique_identifier_msgs.msg import UUID
    from action_wire import ActionWire

    args.directory.mkdir(parents=True,exist_ok=True)
    scene=json.loads((REPO/'inputs/scenes/regression-corridor-common-6201-dwb-v1.json').read_text())
    poses=[float(robot[key]) for robot in scene['robots'] for key in ('x','y','yaw')]
    ros_args=['--ros-args','-p','use_sim_time:=true','-p','robot_count:=3',
        '-p','frame_id:=merge_map','-p','output_grid_resolution:=0.05','-p','map_poses:='+str(poses)]
    rclpy.init(domain_id=91,args=ros_args,signal_handler_options=SignalHandlerOptions.NO)
    if args.role=='merge':
        from merge_map.merge_map import MergeMapNode
        node=MergeMapNode()
    else:
        if any(value is None for value in (args.journal,args.normal_done_file,
                args.allow_negative_file,args.negative_active_ready_file)):
            raise ValueError('client role requires journal, normal-done and negative-phase paths')
        node=Node('net01d_full_load_client',parameter_overrides=[Parameter('use_sim_time',value=True)])
    events=[];feedback={r:0 for r in (1,2,3)};statuses={r:[] for r in (1,2,3)}
    readiness={};merge_samples=[];journal=None;clients={};accepted={};results={};cancel=None
    request_futures={};result_futures={};goals={};start_normal=None;normal_done=False;error=None
    next_readiness=0.
    negative=None;negative_request=None;negative_handle=None;negative_result=None
    def record(kind,**fields):
        row=dict(kind=kind,fixture_origin='NET01D real controlled ActionClient; not RL decision',
            Policy_forward=False,sim=node.get_clock().now().nanoseconds/1e9,
            wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),**fields)
        events.append(row)
        if journal is not None:
            journal.write(json.dumps(row)+'\n')
    if args.role=='client':
        args.journal.parent.mkdir(parents=True,exist_ok=True)
        journal=args.journal.open('x',buffering=1)
        for robot in (1,2,3):
            clients[robot]=ActionClient(node,NavigateToPose,ActionWire.name(robot))
            def status(message,robot=robot):
                statuses[robot].extend(dict(uuid=bytes(s.goal_info.goal_id.uuid).hex(),status=s.status) for s in message.status_list)
            node.create_subscription(GoalStatusArray,ActionWire.name(robot)+'/_action/status',status,qos_profile_action_status_default)
        def merged(message):
            merge_samples.append(dict(monotonic_ns=time.monotonic_ns(),width=message.info.width,
                height=message.info.height,frame=message.header.frame_id))
        node.create_subscription(OccupancyGrid,'/merge_map',merged,
            QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    started=time.monotonic()
    try:
        print('FULL_LOAD_C_READY '+args.role,flush=True)
        while not args.stop_file.exists():
            if time.monotonic()-started>60:
                raise TimeoutError('P5 C role60wall hard bound')
            rclpy.spin_once(node,timeout_sec=.001)
            if args.role=='merge':
                continue
            if time.monotonic()>=next_readiness:
                next_readiness=time.monotonic()+.05
                for robot,client in clients.items():
                    ready=client.server_is_ready()
                    if readiness.get(robot)!=ready:
                        readiness[robot]=ready
                        record('fixture_actual_Action_endpoint_readiness',robot=f'tb{robot}',ready=ready)
            if start_normal is None:
                if not (merge_samples and all(client.server_is_ready() for client in clients.values())):
                    continue
                start_normal=time.monotonic()
                record('fixture_normal_phase_start',normal_wall_s=args.active_wall)
                for robot,client in clients.items():
                    goal=NavigateToPose.Goal();goal.pose.header.frame_id='map'
                    goal.pose.header.stamp=node.get_clock().now().to_msg()
                    goal.pose.pose.position.x=robot+.125;goal.pose.pose.position.y=-2.75
                    goal.pose.pose.orientation.z=.6;goal.pose.pose.orientation.w=.8
                    goal.behavior_tree='NET01D controlled fixture; no Nav2 tree execution'
                    uuid=UUID(uuid=list(args.session_id.to_bytes(8,'big')+bytes([robot])+bytes(7)))
                    goals[robot]=dict(uuid=bytes(uuid.uuid).hex(),Goal_CDR=serialize_message(goal).hex())
                    record('rl_actual_nav2_goal_request',robot=f'tb{robot}',**goals[robot])
                    def feedback_callback(message,robot=robot):
                        if bytes(message.goal_id.uuid).hex()!=goals[robot]['uuid']:
                            raise AssertionError('Foreign feedback UUID')
                        feedback[robot]+=1
                    request_futures[robot]=client.send_goal_async(goal,goal_uuid=uuid,feedback_callback=feedback_callback)
            for robot,future in request_futures.items():
                if future.done() and robot not in accepted:
                    handle=future.result();accepted[robot]=handle
                    record('rl_actual_nav2_goal_response',robot=f'tb{robot}',accepted=handle.accepted,
                        uuid=bytes(handle.goal_id.uuid).hex())
                    if not handle.accepted or bytes(handle.goal_id.uuid).hex()!=goals[robot]['uuid']:
                        raise AssertionError('Goal refused or UUID changed')
                    result_futures[robot]=handle.get_result_async()
                    record('fixture_actual_GetResult_requested',robot=f'tb{robot}',uuid=goals[robot]['uuid'])
            if cancel is None and 3 in accepted and time.monotonic()-start_normal>=args.active_wall-7:
                cancel=accepted[3].cancel_goal_async()
                record('fixture_actual_Cancel_requested',robot='tb3',uuid=goals[3]['uuid'])
            for robot,future in result_futures.items():
                if future.done() and robot not in results:
                    response=future.result();results[robot]=response.status
                    record('rl_actual_nav2_goal_result',robot=f'tb{robot}',uuid=goals[robot]['uuid'],status=response.status,
                        result_CDR=serialize_message(response.result).hex())
            if not normal_done and time.monotonic()-start_normal>=args.active_wall:
                if set(results)!={1,2,3} or results[1]!=4 or results[2]!=4 or results[3]!=5:
                    raise AssertionError('Normal phase actual three terminal results incomplete')
                if cancel is None or not cancel.done():
                    raise AssertionError('Real Cancel response incomplete')
                response=cancel.result()
                if response.return_code!=0 or [bytes(g.goal_id.uuid).hex() for g in response.goals_canceling]!=[goals[3]['uuid']]:
                    raise AssertionError('Cancel original UUID list differs')
                if not all(feedback.values()):
                    raise AssertionError('Missing real feedback')
                if not all(any(s['uuid']==goals[r]['uuid'] and s['status']==results[r] for s in statuses[r]) for r in (1,2,3)):
                    raise AssertionError('Missing original UUID terminal status')
                normal_done=True
                record('fixture_normal_phase_done',outcomes=results,feedback=feedback.copy())
                publish_marker(args.normal_done_file,events[-1])
                print('CLIENT_NORMAL_DONE',flush=True)
            if normal_done and negative is None and args.allow_negative_file.exists():
                goal=NavigateToPose.Goal();goal.pose.header.frame_id='map'
                goal.pose.header.stamp=node.get_clock().now().to_msg()
                goal.pose.pose.position.x=3.25;goal.pose.pose.position.y=-2.75
                goal.pose.pose.orientation.z=.6;goal.pose.pose.orientation.w=.8
                goal.behavior_tree='NET01D controlled negative active goal; no Nav2 tree execution'
                uuid=UUID(uuid=list(args.session_id.to_bytes(8,'big')+bytes([3,1])+bytes(6)))
                negative=dict(uuid=bytes(uuid.uuid).hex(),Goal_CDR=serialize_message(goal).hex())
                record('rl_actual_nav2_goal_request',phase='negative',robot='tb3',**negative)
                negative_request=clients[3].send_goal_async(goal,goal_uuid=uuid)
            if negative_request is not None and negative_request.done() and negative_handle is None:
                negative_handle=negative_request.result()
                negative['accepted']=negative_handle.accepted
                record('rl_actual_nav2_goal_response',phase='negative',robot='tb3',
                    accepted=negative_handle.accepted,uuid=bytes(negative_handle.goal_id.uuid).hex())
                if not negative_handle.accepted or bytes(negative_handle.goal_id.uuid).hex()!=negative['uuid']:
                    raise AssertionError('Negative phase real Goal not accepted with original UUID')
                negative_result=negative_handle.get_result_async()
                if negative_result.done():
                    raise AssertionError('Negative phase Goal is already terminal')
                negative['pending_at_ready']=True
                record('fixture_negative_active_goal_ready',robot='tb3',**negative)
                publish_marker(args.negative_active_ready_file,events[-1])
                print('NEGATIVE_ACTIVE_READY',flush=True)
            # Only the one explicitly permitted negative Goal follows the three
            # normal Goals. Continue spinning through host fault/recovery.
    except BaseException as exc:
        error=repr(exc);raise
    finally:
        result=dict(role=args.role,session_id=args.session_id,error=error,
            scope='Real controlled DDS Action + original merge/journal load; not RL/Nav2/SLAM',
            normal_done=normal_done,events=events,goals=goals,results=results,feedback=feedback,
            statuses=statuses,readiness=readiness,merge_samples=merge_samples,
            request_pending=[r for r,f in request_futures.items() if not f.done()],
            GetResult_pending=[r for r,f in result_futures.items() if not f.done()])
        result['negative_phase']=dict(goal=negative,
            request_pending=negative_request is not None and not negative_request.done(),
            result_pending=negative_result is not None and not negative_result.done(),
            actual_result_status=None if negative_result is None or not negative_result.done() else negative_result.result().status)
        with (args.directory/'full-client.json').open('x') as stream:
            json.dump(result,stream);stream.write('\n')
        if journal is not None:journal.close()
        for client in clients.values():client.destroy()
        node.destroy_node();rclpy.try_shutdown()
    return 0


if __name__=='__main__':
    raise SystemExit(main())

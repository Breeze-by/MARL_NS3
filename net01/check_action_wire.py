"""Bounded real-DDS Action wire fixture, NOT Nav2/Gazebo/ns-3 acceptance.

Two real FastRTPS domains; controlled NavigateToPose servers have no motion
publishers. An explicit in-memory delivery queue tests only ActionWire's API.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.action import ActionClient, ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.serialization import serialize_message, deserialize_message
from rclpy.task import Future
from unique_identifier_msgs.msg import UUID
from action_msgs.msg import GoalStatusArray
from rclpy.qos import qos_profile_action_status_default
from nav2_msgs.action import NavigateToPose

from action_wire import ActionWire, SERVICES


class ControlledServer:
    def __init__(self,node,robot):
        self.node=node;self.robot=robot
        self.accepted=[];self.executing={};self.release=set();self.cancelled=[]
        self.server=ActionServer(node,NavigateToPose,ActionWire.name(robot),
            execute_callback=self.execute,goal_callback=self.goal,
            cancel_callback=self.cancel,callback_group=ReentrantCallbackGroup())
        self.timer=node.create_timer(.02,self.tick)

    def goal(self,request):
        self.accepted.append(serialize_message(request).hex())
        return GoalResponse.ACCEPT

    def cancel(self,handle):
        self.cancelled.append(bytes(handle.goal_id.uuid).hex())
        return CancelResponse.ACCEPT

    async def execute(self,handle):
        uuid=bytes(handle.goal_id.uuid).hex();future=Future()
        self.executing[uuid]=(handle,future)
        return await future

    def tick(self):
        for uuid,(handle,future) in tuple(self.executing.items()):
            feedback=NavigateToPose.Feedback()
            feedback.current_pose=handle.request.pose
            feedback.distance_remaining=3.25
            feedback.navigation_time.sec=7
            feedback.estimated_time_remaining.sec=11
            feedback.number_of_recoveries=2
            handle.publish_feedback(feedback)
            if handle.is_cancel_requested:
                handle.canceled();future.set_result(NavigateToPose.Result())
                self.executing.pop(uuid)
            elif uuid in self.release:
                handle.succeed();future.set_result(NavigateToPose.Result())
                self.executing.pop(uuid)

    def close(self):
        self.node.destroy_timer(self.timer);self.server.destroy()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result=dict(scope='real FastRTPS/generated ROS Action interface fixture; no Nav2, Gazebo, robot, NN or ns3',
        real_action_servers='controlled fixture only',RMW_IMPLEMENTATION=os.environ.get('RMW_IMPLEMENTATION'),
        domains=[93,94],checks={},status='RUNNING')
    queue=deque();packets=[];link=True;bridges={};contexts=[];nodes=[];executors=[]
    servers={};clients={};feedback={};statuses={};captures=[]
    overall=time.monotonic()+55.
    def check(name,condition):
        assert condition,name
        result['checks'][name]=True;print('PASS',name,flush=True)
    def emit(sender,dest,flow,body,rpc):
        packet=(sender,dest,flow,bytes(body),rpc)
        packets.append(dict(sender=sender,destination=dest,flow=flow,rpc_id=rpc,
            bytes=len(body),body_hex=bytes(body).hex(),delivered=link))
        if link:queue.append(packet)
        if sender==0 and flow%20==0:captures.append(packet)
    def pump():
        if time.monotonic()>overall:raise TimeoutError('55wall fixture overall deadline')
        for executor in executors:executor.spin_once(timeout_sec=.002)
        for _ in range(len(queue)):
            sender,dest,flow,body,rpc=queue.popleft()
            bridges[dest].receive(sender,flow,body,rpc)
    def until(predicate,timeout=8.):
        end=min(overall,time.monotonic()+timeout)
        while not predicate() and time.monotonic()<end:pump()
        if not predicate():raise TimeoutError('fixture condition deadline')
    def duration(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:pump()
    try:
        for domain,name in ((93,'action_wire_c'),(94,'action_wire_r')):
            context=Context();rclpy.init(context=context,domain_id=domain)
            contexts.append(context);node=Node(name,context=context);nodes.append(node)
            executor=SingleThreadedExecutor(context=context);executor.add_node(node);executors.append(executor)
        cnode,rnode=nodes
        central=ActionWire(cnode,lambda dest,flow,body,rpc:emit(0,dest,flow,body,rpc))
        bridges[0]=central
        for robot in (1,2,3):
            bridges[robot]=ActionWire(rnode,lambda dest,flow,body,rpc,robot=robot:emit(robot,dest,flow,body,rpc),robot=robot)
            clients[robot]=ActionClient(cnode,NavigateToPose,ActionWire.name(robot),callback_group=ReentrantCallbackGroup())
            feedback[robot]=[];statuses[robot]=[]
        status_subs=[cnode.create_subscription(GoalStatusArray,ActionWire.name(robot)+'/_action/status',
            lambda msg,robot=robot:statuses[robot].extend((bytes(s.goal_info.goal_id.uuid).hex(),s.status) for s in msg.status_list),
            qos_profile_action_status_default) for robot in (1,2,3)]
        duration(.6)
        check('no_remote_server_means_no_C_Action_endpoints',not central.endpoints and not any(c.server_is_ready() for c in clients.values()))
        for robot in (1,2,3):servers[robot]=ControlledServer(rnode,robot)
        until(lambda:all(c.server_is_ready() for c in clients.values()))
        check('real_five_endpoint_discovery_then_delivered_readiness',all(bridges[r].probes[r].server_is_ready() and central.ready[r] for r in (1,2,3)))

        def send_goal(robot,number):
            goal=NavigateToPose.Goal();goal.pose.header.frame_id='map'
            goal.pose.header.stamp.sec=123;goal.pose.header.stamp.nanosec=456789
            goal.pose.pose.position.x=number+.125;goal.pose.pose.position.y=-2.75
            goal.pose.pose.orientation.z=.6;goal.pose.pose.orientation.w=.8
            goal.behavior_tree='fixture-original-tree-field'
            uuid=UUID(uuid=list(bytes([robot,number])+bytes(range(2,16))))
            future=clients[robot].send_goal_async(goal,goal_uuid=uuid,
                feedback_callback=lambda msg:feedback[robot].append(msg))
            until(future.done);handle=future.result()
            uuid_hex=bytes(uuid.uuid).hex()
            until(lambda:uuid_hex in servers[robot].executing)
            check(f'robot{robot}_original_uuid_goal_frame_stamp_preserved',handle.accepted and handle.goal_id==uuid and servers[robot].accepted[-1]==serialize_message(goal).hex())
            return bytes(uuid.uuid).hex(),handle

        uuid1,handle1=send_goal(1,1)
        outcome1=handle1.get_result_async()
        until(lambda:bool(feedback[1]) and (uuid1,2) in statuses[1])
        feedback_body=serialize_message(feedback[1][-1]).hex()
        check('feedback_entire_generated_message_preserved',feedback[1][-1].goal_id==handle1.goal_id and any(p['flow']==226 and p['body_hex']==feedback_body for p in packets))
        check('GetResult_waits_for_real_terminal',not outcome1.done())
        servers[1].release.add(uuid1);until(outcome1.done)
        until(lambda:(uuid1,4) in statuses[1])
        check('real_success_GetResult_and_dynamic_status_same_uuid',outcome1.result().status==4 and (uuid1,2) in statuses[1])

        uuid2,handle2=send_goal(2,2)
        outcome2=handle2.get_result_async();until(lambda:bool(feedback[2]))
        cancel=handle2.cancel_goal_async();until(cancel.done)
        check('real_cancel_response_original_goal_list',cancel.result().return_code==0 and [g.goal_id for g in cancel.result().goals_canceling]==[handle2.goal_id])
        until(outcome2.done);until(lambda:(uuid2,5) in statuses[2])
        check('real_CANCELED_GetResult_and_status_UUID',outcome2.result().status==5 and uuid2 in servers[2].cancelled)

        uuid3,handle3=send_goal(3,3)
        outcome3=handle3.get_result_async();servers[3].release.add(uuid3);until(outcome3.done)
        duration(.1)
        old_feedback=len(feedback[1]);old_status=len(statuses[1])
        central.receive(1,226,serialize_message(feedback[1][-1]),123)
        old_status_body=bytes.fromhex(next(p['body_hex'] for p in reversed(packets) if p['flow']==227))
        central.receive(1,227,old_status_body,124)
        duration(.1)
        check('old_session_feedback_and_status_never_published',len(feedback[1])==old_feedback and len(statuses[1])==old_status)
        original=captures[0]
        before=bridges[1].forwarded_requests;accepted=len(servers[1].accepted)
        bridges[1].receive(0,original[2],original[3],original[4]);duration(.1)
        check('completed_duplicate_RPC_replays_response_without_SendGoal',bridges[1].forwarded_requests==before and len(servers[1].accepted)==accepted and bridges[1].duplicate_requests==1)

        link=False;queue.clear();duration(.8)
        until(lambda:not any(c.server_is_ready() for c in clients.values()))
        check('blackout_expires_readiness_withdraws_all_C_endpoints',not central.endpoints)
        count=sum(b.forwarded_requests for peer,b in bridges.items() if peer)
        duration(.15)
        check('no_new_robot_service_request_after_blackout',count==sum(b.forwarded_requests for peer,b in bridges.items() if peer))
        link=True;until(lambda:all(c.server_is_ready() for c in clients.values()))
        bridges[1].receive(0,original[2],original[3],original[4]);duration(.1)
        check('recovery_duplicate_never_resubmits_goal',len(servers[1].accepted)==accepted and bridges[1].forwarded_requests==before and bridges[1].duplicate_requests==2)

        # Remove real Nav2-shaped endpoints and observe actual discovery loss,
        # not just a test-side readiness flag.
        result['accepted_per_robot']={r:len(s.accepted) for r,s in servers.items()}
        for server in servers.values():server.close()
        servers.clear()
        until(lambda:not any(b.probes[peer].server_is_ready() for peer,b in bridges.items() if peer))
        until(lambda:not central.endpoints and not any(c.server_is_ready() for c in clients.values()))
        check('actual_server_destruction_withdraws_facade',True)
        check('all_nine_wire_flow_kinds_have_full_generated_CDR',all(any(p['flow']%20==offset and p['bytes']>=5 for p in packets) for offset in range(9)))
        result['status']='PASS'
        result['unknown_response_count']=central.unknown_responses
        result['packet_count']=len(packets)
    except BaseException as error:
        result['status']='FAIL';result['error']=f'{type(error).__name__}: {error}'
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (args.output/'wire-packets.json').write_text(json.dumps(packets,indent=2)+'\n')
        for server in servers.values():server.close()
        for client in clients.values():client.destroy()
        for bridge in bridges.values():bridge.close()
        for executor in executors:executor.shutdown(timeout_sec=0.)
        for node in nodes:node.destroy_node()
        for context in contexts:context.shutdown()


if __name__=='__main__':main()

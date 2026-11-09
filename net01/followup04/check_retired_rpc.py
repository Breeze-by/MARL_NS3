"""One real-DDS pending-RPC retirement fixture; controlled server, no motion.

Only the wire leg uses an explicit full-CDR in-memory queue. This is not ns3,
Nav2 readiness or robot safety validation. C/R use isolated domains104/105.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.serialization import deserialize_message, serialize_message
from std_msgs.msg import Bool
from unique_identifier_msgs.msg import UUID
from nav2_msgs.action import NavigateToPose
from action_wire import ActionWire
from check_action_wire import ControlledServer


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output', type=Path, required=True)
    out=parser.parse_args().output;out.mkdir(parents=True, exist_ok=False)
    result=dict(scope='Actual DDS typed clients and controlled ActionServer; full-CDR memory wire only',
        domains=[104,105], Gazebo=0,Nav2=0,NN=0,motion_publishers=0,checks={})
    queue=deque();held=[];packets=[];bridges={};contexts=[];nodes=[];executors=[];clients=[]
    hold_accept=True;deliver_readiness=True;server=None;deadline=time.monotonic()+20
    def check(name,value):
        assert value,name
        result['checks'][name]=True
    def emit(sender,destination,flow,body,rpc):
        packet=(sender,destination,flow,bytes(body),rpc);packets.append(packet)
        if sender==1 and flow==228 and not deliver_readiness:return
        if sender==1 and flow==221 and hold_accept:held.append(packet)
        else:queue.append(packet)
    def pump():
        if time.monotonic()>deadline:raise TimeoutError('20wall fixture bound')
        for executor in executors:executor.spin_once(timeout_sec=.001)
        for _ in range(len(queue)):
            sender,destination,flow,body,rpc=queue.popleft()
            bridges[destination].receive(sender,flow,body,rpc)
    def until(predicate):
        while not predicate():pump()
    try:
        for domain,name in ((104,'net01_retired_rpc_c'),(105,'net01_retired_rpc_r')):
            context=Context();rclpy.init(context=context,domain_id=domain);contexts.append(context)
            node=Node(name,context=context);nodes.append(node)
            executor=SingleThreadedExecutor(context=context);executor.add_node(node);executors.append(executor)
        cnode,rnode=nodes
        c=ActionWire(cnode,lambda peer,flow,body,rpc:emit(0,peer,flow,body,rpc),robots=(1,),session_id=2401)
        r=ActionWire(rnode,lambda peer,flow,body,rpc:emit(1,peer,flow,body,rpc),robot=1,session_id=2401)
        bridges.update({0:c,1:r});server=ControlledServer(rnode,1)
        send=cnode.create_client(NavigateToPose.Impl.SendGoalService,ActionWire.name(1)+'/_action/send_goal')
        get=cnode.create_client(NavigateToPose.Impl.GetResultService,ActionWire.name(1)+'/_action/get_result')
        clients.extend((send,get));until(lambda:c.ready[1] and send.service_is_ready() and get.service_is_ready())
        request=NavigateToPose.Impl.SendGoalService.Request();request.goal_id=UUID(uuid=[31]*16)
        request.goal.pose.header.frame_id='map';request.goal.pose.pose.orientation.w=1.
        accepted=send.call_async(request);uuid=bytes(request.goal_id.uuid).hex()
        until(lambda:bool(held) and uuid in server.executing)
        query=NavigateToPose.Impl.GetResultService.Request(goal_id=request.goal_id)
        outcome=get.call_async(query)
        until(lambda:any(k[0]==222 for k in r.requests))
        key=next(k for k in c.pending if k[1]==3)
        synthetic=NavigateToPose.Impl.GetResultService.Response(status=4)
        c.receive(1,223,serialize_message(synthetic),((2400<<32)|(key[2]&0xffffffff)))
        c.receive(1,223,serialize_message(synthetic),(2401<<32)|0x7fffffff)
        check('old_session_and_unknown_rpc_do_not_complete_original_client',not outcome.done() and key in c.pending)
        deliver_readiness=False
        r._publish_wire(1,8,Bool(data=False));until(lambda:not c.ready[1])
        check('withdrawn_ready_retains_only_admitted_original_handles',sorted(x['inflight'] for x in c.retired_services[1])==[1,1])
        before=r.forwarded_requests;blocked=c.blocked_requests
        late=NavigateToPose.Impl.SendGoalService.Request();late.goal_id=UUID(uuid=[32]*16)
        unknown=send.call_async(late);until(lambda:c.blocked_requests>blocked)
        check('unready_new_goal_unknown_not_forwarded_or_counted',not unknown.done() and r.forwarded_requests==before and
            sorted(x['inflight'] for x in c.retired_services[1])==[1,1])
        hold_accept=False
        for packet in held:queue.append(packet)
        held.clear();until(accepted.done)
        original_accept=deserialize_message(next(p[3] for p in packets if p[0]==1 and p[2]==221),NavigateToPose.Impl.SendGoalService.Response)
        check('original_C_client_receives_real_late_accept',accepted.result()==original_accept and accepted.result().accepted)
        server.release.add(uuid);until(outcome.done)
        check('original_C_client_receives_real_terminal_same_UUID_RPC',outcome.result().status==4 and uuid in server.release and
            not c.pending and len(server.accepted)==1)
        until(lambda:not c.retired_services[1])
        check('retired_cleared_only_after_actual_DDS_response',not unknown.done())
        deliver_readiness=True;until(lambda:c.ready[1])
        names=[service.srv_name for service in cnode.services if '/navigate_to_pose/_action/' in service.srv_name]
        check('readiness_recovers_without_duplicate_service_handles',len(names)==3 and len(set(names))==3 and r.forwarded_requests==2)
        result.update(status='PASS',real_accepted_uuid=uuid,blocked_unadmitted_future_still_unknown=not unknown.done(),
            pending_admitted_C_RPC=len(c.pending),retired_inflight=[])
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));raise
    finally:
        if server is not None:server.close()
        for client in clients:client.destroy()
        for bridge in bridges.values():bridge.close()
        result['executor_shutdown']=[executor.shutdown(timeout_sec=0) for executor in executors]
        result['cleanup_scope']='Deliberately unadmitted unknown C callback may keep work_tracker pending; not fake cleanup PASS'
        for node in nodes:node.destroy_node()
        for context in contexts:context.shutdown()
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'wire-packets.json').write_text(json.dumps([dict(sender=a,destination=b,flow=f,rpc_id=i,body_hex=body.hex())
            for a,b,f,body,i in packets],indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

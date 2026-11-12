"""One 0-Node unit fixture of actual ActionWire methods, not DDS.

Node/client/send are controlled stand-ins; generated CDR and rclpy.Future are
real. Backend readiness is explicitly stubbed. Actual service lifecycle and
Wi-Fi delivery and actual Gateway.fail/receive belong to the separately admitted
integration fixture; this check does not duplicate that boundary.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from action_wire import ActionWire
from nav2_msgs.action import NavigateToPose
from rclpy.serialization import serialize_message
from rclpy.task import Future


class Client:
    def __init__(self):self.calls=[]
    def call_async(self,request):
        future=Future();self.calls.append((request,future));return future


class Node:
    def __init__(self):self.clients=[]
    def create_timer(self,*args,**kwargs):return object()
    def create_client(self,*args,**kwargs):
        client=Client();self.clients.append(client);return client
    def create_subscription(self,*args,**kwargs):return object()
    def create_service(self,*args,**kwargs):return SimpleNamespace(send_response=lambda *a:None)
    def create_publisher(self,*args,**kwargs):return SimpleNamespace(publish=lambda *a:None)
    def destroy_service(self,*args):pass
    def destroy_publisher(self,*args):pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    now=[0.];checks={};failures=[];wire=[]
    def check(name,value):
        assert value,name
        checks[name]=True
    def pair():
        c=ActionWire(Node(),lambda peer,flow,body,rpc:wire.append((0,peer,flow,bytes(body),rpc)),
            robots=(1,),session_id=5001,reliable=True,transport_error=failures.append)
        r=ActionWire(Node(),lambda peer,flow,body,rpc:wire.append((1,peer,flow,bytes(body),rpc)),
            robot=1,session_id=5001,reliable=True,transport_error=failures.append)
        r.ready[1]=True;r.backend_is_ready=lambda:True
        return c,r
    def begin(c,offset,request,typ):
        rpc=c.next_id();future=Future()
        c.pending[(1,offset+1,rpc)]=(future,typ.Response,0)
        body=serialize_message(request);c._send_rpc(1,offset,body,rpc)
        return rpc,future,body
    result=dict(scope='Actual ActionWire methods/generated CDR/controlled Futures; 0 Node/DDS/ns3/Gazebo',checks=checks)
    try:
        with (patch('rclpy.init',side_effect=AssertionError('ROS init forbidden')),
                patch('rclpy.node.Node.__init__',side_effect=AssertionError('ROS Node forbidden')),
                patch('action_wire.time.monotonic',lambda:now[0])):
            c,r=pair();typ=NavigateToPose.Impl.SendGoalService
            request=typ.Request();request.goal_id.uuid=[17]*16
            rpc,future,body=begin(c,0,request,typ)
            r.receive(0,220,body,rpc);r.receive(0,220,body,rpc)
            check('duplicate_request_calls_real_client_adapter_once',r.forwarded_requests==1 and len(r.clients[0].calls)==1)
            try:r.receive(0,220,body+b'x',rpc)
            except ValueError:checks['same_identity_different_body_rejected']=True
            else:raise AssertionError('changed request body accepted')
            response=typ.Response(accepted=True);r.clients[0].calls[0][1].set_result(response)
            payload=r.requests[(220,rpc)];calls=[];future.add_done_callback(lambda f:calls.append(f.result()))
            # The real response can overtake its request confirmation.
            c.receive(1,221,payload,rpc)
            check('response_before_request_ACK_completes_only_original_future',future.done() and future.result()==response and
                c.transfers[(1,0,rpc)]['state']=='ACKED')
            r.receive(0,229,bytes((1,1)),rpc)
            c.receive(1,221,payload,rpc)
            check('completed_duplicate_response_reACK_without_second_completion',len(calls)==1 and
                len([x for x in wire if x[0]==0 and x[2]==229 and x[3]==bytes((1,1))])==2)
            check('request_and_response_confirmation_states_drained',c.reliability_status()['waiting']==0 and r.reliability_status()['waiting']==0)

            typ=NavigateToPose.Impl.GetResultService
            rpc,future,body=begin(c,2,typ.Request(goal_id=request.goal_id),typ)
            r.receive(0,222,body,rpc)  # first ACK deliberately not delivered
            now[0]=.21;c.reliability_tick();r.receive(0,222,body,rpc)
            c.receive(1,229,bytes((1,2)),rpc)
            attempts=c.transfers[(1,2,rpc)]['attempts']
            now[0]=2.;c.reliability_tick();r.reliability_tick()
            check('confirmed_GetResult_wait_beyond_transport_deadline_is_legitimate',not future.done() and
                failures==[] and len(r.clients[2].calls)==1 and r.requests[(222,rpc)] is None)
            check('request_ACK_stops_retries_without_GetResult_completion',
                not future.done() and c.transfers[(1,2,rpc)]['attempts']==attempts)
            response=typ.Response(status=4);r.clients[2].calls[0][1].set_result(response)
            payload=r.requests[(222,rpc)]  # first real response deliberately lost
            now[0]=2.21;r.reliability_tick()
            check('lost_response_retries_original_CDR_same_RPC',r.transfers[(1,3,rpc)]['attempts']==2 and
                wire[-1]==(1,0,223,payload,rpc))
            c.receive(1,223,payload,rpc)  # response ACK deliberately lost
            now[0]=2.42;r.reliability_tick();c.receive(1,223,payload,rpc)
            r.receive(0,229,bytes((1,3)),rpc)
            check('lost_response_ACK_recovered_by_duplicate_response_reACK',future.result()==response and
                r.transfers[(1,3,rpc)]['state']=='ACKED' and r.forwarded_requests==2)

            now[0]=10.;c,r=pair();typ=NavigateToPose.Impl.SendGoalService
            case_wire_start=len(wire)
            rpc,future,body=begin(c,0,request,typ)
            deadline=c.transfers[(1,0,rpc)]['deadline']
            now[0]=10.19;c._send_rpc(1,0,body,rpc)
            check('duplicate_send_preserves_original_deadline_and_attempt',
                c.transfers[(1,0,rpc)]['deadline']==deadline and c.transfers[(1,0,rpc)]['attempts']==1)
            try:c._send_rpc(1,0,body+b'x',rpc)
            except ValueError:checks['changed_C_transfer_body_rejected']=True
            else:raise AssertionError('changed C transfer body accepted')
            c.receive(1,229,bytes((1,0)),rpc-(1<<32))
            c.receive(1,229,bytes((1,2)),rpc)
            check('old_session_and_wrong_offset_ACK_do_not_confirm_request',c.transfers[(1,0,rpc)]['state']=='WAIT_CONFIRMATION')
            for value in (10.21,10.42,10.63,10.84):now[0]=value;c.reliability_tick()
            now[0]=10.9;c._send_rpc(1,0,body,rpc)
            attempts=[x for x in wire[case_wire_start:] if x[0]==0 and x[2]==220]
            check('maximum_five_attempts_same_original_CDR',c.transfers[(1,0,rpc)]['attempts']==5 and
                len(attempts)==5 and all(x[3]==body and x[4]==rpc for x in attempts))
            check('late_duplicate_does_not_extend_original_deadline',c.transfers[(1,0,rpc)]['deadline']==deadline)
            now[0]=11.;c.receive(1,229,bytes((1,0)),rpc)
            check('ACK_at_deadline_cannot_erase_expiry',c.transfers[(1,0,rpc)]['state']=='UNCONFIRMED' and len(failures)==1)
            original_fault=c.transport_failed
            c.receive(1,221,serialize_message(typ.Response(accepted=True)),rpc)
            sent=len(wire);now[0]=20.;c.reliability_tick()
            check('permanent_failure_keeps_original_unknown_and_stops_retries',not future.done() and
                (1,1,rpc) in c.pending and len(wire)==sent and len(failures)==1 and
                c.transport_failed==original_fault and original_fault is not None)

        result['status']='PASS'
    except BaseException as error:
        result.update(status='FAIL',error=repr(error));raise
    finally:
        result['failures']=failures
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

"""NavigateToPose wire adapter. No policy, motion command or ROS initialization.

One instance belongs to one transport session. Recreate both sides when that
session changes. send(peer, flow, full_cdr, rpc_id) only enqueues transport;
receive is called by the owner executor after complete actual delivery.
Readiness is generated Bool CDR; every other body is the original generated
Action service request/response or feedback/status CDR, without an envelope,
except optional offset9's two-byte application-level delivery confirmation.
"""
from functools import partial
import time

from action_msgs.msg import GoalStatusArray
from action_msgs.srv import CancelGoal
from nav2_msgs.action import NavigateToPose
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, qos_profile_action_status_default, qos_check_compatible, QoSCompatibility
from rclpy.serialization import serialize_message, deserialize_message
from rclpy.task import Future
from std_msgs.msg import Bool

SERVICES=((0, NavigateToPose.Impl.SendGoalService, 'send_goal'),
          (2, NavigateToPose.Impl.GetResultService, 'get_result'),
          (4, CancelGoal, 'cancel_goal'))


class ActionWire:
    def __init__(self, node, send, *, robot=None, robots=(1, 2, 3),
                 session_id=1, readiness_period_s=.1, readiness_timeout_s=.5, guardian=None,
                 reliable=False, transport_error=None):
        self.node, self.send, self.robot = node, send, robot
        self.guardian=guardian
        self.robots=tuple(robots) if robot is None else (robot,)
        if not self.robots or any(r not in (1,2,3) for r in self.robots):
            raise ValueError('ActionWire supports robot peers 1..3')
        self.session_id=session_id;self.counter=0
        self.group=ReentrantCallbackGroup()
        self.timeout=readiness_timeout_s
        self.ready={r:False for r in self.robots}
        self.ready_received={};self.ready_sequence={}
        self.endpoints={};self.generation={r:0 for r in self.robots}
        self.service_states={};self.retired_services={r:[] for r in self.robots}
        self.pending={};self.requests={}
        self.clients={};self.subscriptions=[]
        self.forwarded_requests=0;self.duplicate_requests=0;self.blocked_requests=0
        self.unknown_responses=0
        # Application-level confirmation over the SAME transport, not TCP.
        # Each transfer preserves the original Action CDR/flow/RPC identity.
        self.reliable=reliable;self.transport_error=transport_error
        self.transfers={};self.completed_responses={};self.request_bodies={}
        self.reliability_events=[];self.transport_failed=None
        if robot is not None:
            name=self.name(robot)
            for offset,typ,suffix in SERVICES:
                self.clients[offset]=node.create_client(typ,name+'/_action/'+suffix,callback_group=self.group)
            self.subscriptions=[
                node.create_subscription(NavigateToPose.Impl.FeedbackMessage,name+'/_action/feedback',
                    partial(self._publish_raw_wire,robot,6),QoSProfile(depth=10),callback_group=self.group,raw=True),
                node.create_subscription(GoalStatusArray,name+'/_action/status',
                    partial(self._publish_raw_wire,robot,7),qos_profile_action_status_default,callback_group=self.group,raw=True)]
        self.timer=node.create_timer(readiness_period_s,self.poll_readiness,callback_group=self.group)

    @staticmethod
    def name(robot):return f'/tb{robot}/navigate_to_pose'

    @staticmethod
    def flow(robot,offset):return 200+robot*20+offset

    def next_id(self):
        self.counter+=1
        return (self.session_id<<32)|self.counter

    def _transport_event(self,kind,**fields):
        self.reliability_events.append(dict(kind=kind,monotonic=time.monotonic(),**fields))

    def stop_reliability(self,reason):
        if self.transport_failed is None:
            self.transport_failed=reason
            self._transport_event('reliable_transport_stopped',reason=reason)

    def _transport_fail(self,reason):
        self.stop_reliability(reason)
        if self.transport_error is not None:self.transport_error(reason)

    def _expire_transfers(self,now):
        if not self.reliable or self.transport_failed is not None:return
        for key,item in self.transfers.items():
            if item['state']=='WAIT_CONFIRMATION' and now>=item['deadline']:
                item['state']='UNCONFIRMED'
                self._transport_event('delivery_confirmation_expired',robot=key[0],offset=key[1],
                    rpc_id=key[2],attempts=item['attempts'],deadline=item['deadline'])
                self._transport_fail(f'action_delivery_unconfirmed_tb{key[0]}_offset{key[1]}_rpc{key[2]}')
                return

    def _attempt_transfer(self,key,item,now):
        robot,offset,rpc=key
        item['attempts']+=1;item['next_attempt']=now+.2
        self._transport_event('original_CDR_attempt',robot=robot,offset=offset,rpc_id=rpc,
            attempt=item['attempts'],body_bytes=len(item['body']))
        self.send(robot if self.robot is None else 0,self.flow(robot,offset),item['body'],rpc)

    def _send_rpc(self,robot,offset,body,rpc):
        body=bytes(body)
        if not self.reliable:
            self.send(robot if self.robot is None else 0,self.flow(robot,offset),body,rpc);return
        if self.transport_failed is not None:return
        key=(robot,offset,rpc);now=time.monotonic()
        # An ACKed response needs no new automatic transfer. A request duplicate
        # can still elicit the original response while confirmation is pending.
        if key in self.transfers:
            if self.transfers[key]['body']!=body:raise ValueError('Action transfer identity reused with different CDR')
            return
        item=dict(body=body,attempts=0,deadline=now+1.,next_attempt=now,state='WAIT_CONFIRMATION')
        self.transfers[key]=item
        self._attempt_transfer(key,item,now)

    def _ack(self,robot,offset,rpc):
        if self.reliable and self.transport_failed is None:
            self.send(robot if self.robot is None else 0,self.flow(robot,9),bytes((1,offset)),rpc)
            self._transport_event('confirmation_enqueued',robot=robot,offset=offset,rpc_id=rpc)

    def reliability_tick(self):
        now=time.monotonic();self._expire_transfers(now)
        if not self.reliable or self.transport_failed is not None:return
        for key,item in self.transfers.items():
            if item['state']=='WAIT_CONFIRMATION' and item['attempts']<5 and now>=item['next_attempt']:
                self._attempt_transfer(key,item,now)

    def reliability_status(self):
        return dict(enabled=self.reliable,failure=self.transport_failed,
            waiting=sum(t['state']=='WAIT_CONFIRMATION' for t in self.transfers.values()),
            unconfirmed=sum(t['state']=='UNCONFIRMED' for t in self.transfers.values()))

    def reliability_snapshot(self):
        return dict(status=self.reliability_status(),events=self.reliability_events,
            transfers=[dict(robot=r,offset=o,rpc_id=i,body_bytes=len(t['body']),
                **{k:v for k,v in t.items() if k!='body'}) for (r,o,i),t in self.transfers.items()])

    def _publish_wire(self,robot,offset,message):
        self.send(0,self.flow(robot,offset),serialize_message(message),self.next_id())

    def _publish_raw_wire(self,robot,offset,body):
        self.send(0,self.flow(robot,offset),body,self.next_id())

    def backend_is_ready(self):
        # Reuse the actual typed business endpoints. A second ActionClient just
        # for discovery also consumes feedback/status and duplicates hot work.
        if not all(client.service_is_ready() for client in self.clients.values()):return False
        for subscription,expected_type in zip(self.subscriptions,
                ('nav2_msgs/action/NavigateToPose_FeedbackMessage','action_msgs/msg/GoalStatusArray')):
            publishers=self.node.get_publishers_info_by_topic(subscription.topic_name)
            # Graph SYSTEM_DEFAULT warnings are not proven incompatibility;
            # the installed native ActionClient oracle accepts these defaults.
            if not any(info.topic_type==expected_type and qos_check_compatible(
                    info.qos_profile,subscription.qos_profile)[0]!=QoSCompatibility.ERROR
                    for info in publishers):return False
        return True

    def poll_readiness(self):
        if self.robot is not None:
            ready=self.backend_is_ready()
            if self.guardian is not None:ready=ready and self.guardian.guard.may_send_goal()
            self.ready[self.robot]=ready
            self._publish_wire(self.robot,8,Bool(data=ready))
        else:
            now=time.monotonic()
            for robot in self.robots:
                if self.ready[robot] and now-self.ready_received[robot]>self.timeout:
                    self._set_ready(robot,False)

    def _set_ready(self,robot,ready):
        # Do not advertise duplicate servers while an old accepted callback is
        # still waiting for its real response on the original service handle.
        if ready and self.retired_services[robot]:return
        if self.ready[robot]==ready:return
        self.ready[robot]=ready
        self.generation[robot]+=1
        if ready:
            name=self.name(robot);services=[];states=[]
            generation=self.generation[robot]
            for offset,typ,suffix in SERVICES:
                state=dict(inflight=0,retired=False,offset=offset)
                async def forward(request,response,offset=offset,typ=typ,robot=robot,generation=generation,state=state):
                    future=Future()
                    if not self.ready[robot] or self.generation[robot]!=generation:
                        self.blocked_requests+=1
                        return await future  # unknown, no synthetic rejection
                    state['inflight']+=1
                    rpc_id=self.next_id()
                    self.pending[(robot,offset+1,rpc_id)]=(future,typ.Response,generation)
                    self._send_rpc(robot,offset,serialize_message(request),rpc_id)
                    return await future
                service=self.node.create_service(typ,name+'/_action/'+suffix,forward,callback_group=self.group)
                state['service']=service;send_response=service.send_response
                def sent(response,header,state=state,send_response=send_response,robot=robot):
                    # The executor calls this after await forward; returning a
                    # real result from the coroutine alone is not a ROS reply.
                    send_response(response,header)
                    state['inflight']-=1
                    if state['retired'] and state['inflight']==0:
                        self.node.destroy_service(state['service'])
                        self.retired_services[robot].remove(state)
                service.send_response=sent
                services.append(service);states.append(state)
            self.service_states[robot]=states
            self.endpoints[robot]=(services,
                self.node.create_publisher(NavigateToPose.Impl.FeedbackMessage,name+'/_action/feedback',10),
                self.node.create_publisher(GoalStatusArray,name+'/_action/status',qos_profile_action_status_default))
        else:
            # Revoking goal authority must not leave an unconfirmed SendGoal
            # eligible to create a new remote goal after later readiness recovery.
            if self.reliable and self.transport_failed is None:
                for (r,offset,rpc),item in self.transfers.items():
                    if r==robot and offset==0 and item['state']=='WAIT_CONFIRMATION':
                        item['state']='UNCONFIRMED'
                        self._transport_fail(f'action_goal_authority_withdrawn_unconfirmed_tb{r}_rpc{rpc}')
                        break
            services,feedback,status=self.endpoints.pop(robot)
            for state in self.service_states.pop(robot):
                state['retired']=True
                if state['inflight']:self.retired_services[robot].append(state)
                else:self.node.destroy_service(state['service'])
            self.node.destroy_publisher(feedback);self.node.destroy_publisher(status)
            # Already admitted RPCs keep their original service until the real
            # response has actually been sent. No goal is resubmitted.

    def receive(self,peer,flow,body,rpc_id):
        robot,offset=divmod(flow-200,20)
        if robot not in self.robots or peer!=(robot if self.robot is None else 0):
            raise ValueError('Action peer/flow does not match this endpoint')
        if rpc_id>>32!=self.session_id:return
        body=bytes(body)
        # A newly processed late ACK/response cannot erase a real wall expiry.
        self._expire_transfers(time.monotonic())
        if self.reliable and self.transport_failed is not None:
            self._transport_event('late_packet_after_failure',robot=robot,offset=offset,rpc_id=rpc_id)
            return
        if offset==9:
            allowed=(0,2,4) if self.robot is None else (1,3,5)
            if not self.reliable or len(body)!=2 or body[0]!=1 or body[1] not in allowed:
                raise ValueError('Invalid Action delivery confirmation')
            item=self.transfers.get((robot,body[1],rpc_id))
            if item is None:
                self._transport_event('unknown_confirmation',robot=robot,offset=body[1],rpc_id=rpc_id)
            else:
                item['state']='ACKED'
                self._transport_event('confirmation_received',robot=robot,offset=body[1],rpc_id=rpc_id)
            return
        if self.robot is None:
            if offset==8:
                if rpc_id<=self.ready_sequence.get(robot,-1):return
                self.ready_sequence[robot]=rpc_id;self.ready_received[robot]=time.monotonic()
                self._set_ready(robot,deserialize_message(body,Bool).data)
            elif offset in (1,3,5):
                key=(robot,offset,rpc_id)
                if self.reliable and key in self.completed_responses:
                    if self.completed_responses[key]!=body:raise ValueError('Completed Action response identity changed')
                    self._ack(robot,offset,rpc_id);return
                item=self.pending.get(key)
                if item is None:
                    self.unknown_responses+=1;return
                future,typ,generation=item
                response=deserialize_message(body,typ)
                self.pending.pop((robot,offset,rpc_id))
                if self.reliable:
                    request_transfer=self.transfers[(robot,offset-1,rpc_id)]
                    request_transfer['state']='ACKED'  # A real response also proves request delivery.
                    self.completed_responses[key]=body
                    self._ack(robot,offset,rpc_id)
                future.set_result(response)
            elif offset in (6,7):
                endpoints=self.endpoints.get(robot)
                if endpoints is not None:
                    endpoints[1 if offset==6 else 2].publish(body)
            else:raise ValueError('Unexpected robot-to-central Action flow')
        else:
            typ=next((typ for index,typ,_ in SERVICES if index==offset),None)
            if typ is None:raise ValueError('Unexpected central-to-robot Action flow')
            key=(flow,rpc_id)
            if key in self.requests:
                if self.request_bodies[key]!=body:raise ValueError('Action request identity reused with different CDR')
                self.duplicate_requests+=1
                self._ack(robot,offset,rpc_id)
                completed=self.requests[key]
                if completed is not None:self._send_rpc(robot,offset+1,completed,rpc_id)
                return
            # A latched goal gate must still permit real GetResult/CancelGoal cleanup.
            admission=self.ready[robot] if self.guardian is None or offset==0 else True
            if not admission or not self.backend_is_ready():
                self.blocked_requests+=1;return
            request=deserialize_message(body,typ.Request)
            if self.guardian is not None and offset==0 and not self.guardian.observe_send_goal(request):
                self.blocked_requests+=1;return
            self.requests[key]=None
            self.request_bodies[key]=body
            self.forwarded_requests+=1
            future=self.clients[offset].call_async(request)
            self._ack(robot,offset,rpc_id)
            def completed(done):
                response=done.result()
                if self.guardian is not None and offset==0:self.guardian.observe_goal_response(request,response)
                payload=serialize_message(response)
                self.requests[key]=payload
                self._send_rpc(robot,offset+1,payload,rpc_id)
            future.add_done_callback(completed)

    def close(self):
        self.node.destroy_timer(self.timer)
        if self.robot is None:
            for robot in tuple(self.endpoints):self._set_ready(robot,False)
            for states in self.retired_services.values():
                for state in states:self.node.destroy_service(state['service'])
        else:
            for subscription in self.subscriptions:self.node.destroy_subscription(subscription)
            for client in self.clients.values():self.node.destroy_client(client)

"""NavigateToPose wire adapter. No policy, motion command or ROS initialization.

One instance belongs to one transport session. Recreate both sides when that
session changes. send(peer, flow, full_cdr, rpc_id) only enqueues transport;
receive is called by the owner executor after complete actual delivery.
Readiness is generated Bool CDR; every other body is the original generated
Action service request/response or feedback/status CDR, without an envelope.
"""
from functools import partial
import time

from action_msgs.msg import GoalStatusArray
from action_msgs.srv import CancelGoal
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, qos_profile_action_status_default
from rclpy.serialization import serialize_message, deserialize_message
from rclpy.task import Future
from std_msgs.msg import Bool

SERVICES=((0, NavigateToPose.Impl.SendGoalService, 'send_goal'),
          (2, NavigateToPose.Impl.GetResultService, 'get_result'),
          (4, CancelGoal, 'cancel_goal'))


class ActionWire:
    def __init__(self, node, send, *, robot=None, robots=(1, 2, 3),
                 session_id=1, readiness_period_s=.1, readiness_timeout_s=.5, guardian=None):
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
        self.pending={};self.requests={}
        self.clients={};self.probes={};self.subscriptions=[]
        self.forwarded_requests=0;self.duplicate_requests=0;self.blocked_requests=0
        self.unknown_responses=0
        if robot is not None:
            name=self.name(robot)
            self.probes[robot]=ActionClient(node,NavigateToPose,name,callback_group=self.group)
            for offset,typ,suffix in SERVICES:
                self.clients[offset]=node.create_client(typ,name+'/_action/'+suffix,callback_group=self.group)
            self.subscriptions=[
                node.create_subscription(NavigateToPose.Impl.FeedbackMessage,name+'/_action/feedback',
                    partial(self._publish_wire,robot,6),QoSProfile(depth=10),callback_group=self.group),
                node.create_subscription(GoalStatusArray,name+'/_action/status',
                    partial(self._publish_wire,robot,7),qos_profile_action_status_default,callback_group=self.group)]
        self.timer=node.create_timer(readiness_period_s,self.poll_readiness,callback_group=self.group)

    @staticmethod
    def name(robot):return f'/tb{robot}/navigate_to_pose'

    @staticmethod
    def flow(robot,offset):return 200+robot*20+offset

    def next_id(self):
        self.counter+=1
        return (self.session_id<<32)|self.counter

    def _publish_wire(self,robot,offset,message):
        self.send(0,self.flow(robot,offset),serialize_message(message),self.next_id())

    def poll_readiness(self):
        if self.robot is not None:
            ready=self.probes[self.robot].server_is_ready()
            if self.guardian is not None:ready=ready and self.guardian.guard.may_send_goal()
            self.ready[self.robot]=ready
            self._publish_wire(self.robot,8,Bool(data=ready))
        else:
            now=time.monotonic()
            for robot in self.robots:
                if self.ready[robot] and now-self.ready_received[robot]>self.timeout:
                    self._set_ready(robot,False)

    def _set_ready(self,robot,ready):
        if self.ready[robot]==ready:return
        self.ready[robot]=ready
        self.generation[robot]+=1
        if ready:
            name=self.name(robot);services=[]
            generation=self.generation[robot]
            for offset,typ,suffix in SERVICES:
                async def forward(request,response,offset=offset,typ=typ,robot=robot,generation=generation):
                    future=Future()
                    if not self.ready[robot] or self.generation[robot]!=generation:
                        self.blocked_requests+=1
                        return await future  # unknown, no synthetic rejection
                    rpc_id=self.next_id()
                    self.pending[(robot,offset+1,rpc_id)]=(future,typ.Response,generation)
                    self.send(robot,self.flow(robot,offset),serialize_message(request),rpc_id)
                    return await future
                services.append(self.node.create_service(typ,name+'/_action/'+suffix,forward,callback_group=self.group))
            self.endpoints[robot]=(services,
                self.node.create_publisher(NavigateToPose.Impl.FeedbackMessage,name+'/_action/feedback',10),
                self.node.create_publisher(GoalStatusArray,name+'/_action/status',qos_profile_action_status_default))
        else:
            services,feedback,status=self.endpoints.pop(robot)
            for service in services:self.node.destroy_service(service)
            self.node.destroy_publisher(feedback);self.node.destroy_publisher(status)
            # Outstanding callbacks stay unknown, without fake responses from
            # retired services. Reconnection does not silently resubmit goals.

    def receive(self,peer,flow,body,rpc_id):
        robot,offset=divmod(flow-200,20)
        if robot not in self.robots or peer!=(robot if self.robot is None else 0):
            raise ValueError('Action peer/flow does not match this endpoint')
        if rpc_id>>32!=self.session_id:return
        if self.robot is None:
            if offset==8:
                if rpc_id<=self.ready_sequence.get(robot,-1):return
                self.ready_sequence[robot]=rpc_id;self.ready_received[robot]=time.monotonic()
                self._set_ready(robot,deserialize_message(body,Bool).data)
            elif offset in (1,3,5):
                item=self.pending.get((robot,offset,rpc_id))
                if item is None:
                    self.unknown_responses+=1;return
                future,typ,generation=item
                if self.ready[robot] and self.generation[robot]==generation:
                    self.pending.pop((robot,offset,rpc_id))
                    future.set_result(deserialize_message(body,typ))
            elif offset in (6,7):
                endpoints=self.endpoints.get(robot)
                if endpoints is not None:
                    typ=NavigateToPose.Impl.FeedbackMessage if offset==6 else GoalStatusArray
                    endpoints[1 if offset==6 else 2].publish(deserialize_message(body,typ))
            else:raise ValueError('Unexpected robot-to-central Action flow')
        else:
            typ=next((typ for index,typ,_ in SERVICES if index==offset),None)
            if typ is None:raise ValueError('Unexpected central-to-robot Action flow')
            key=(flow,rpc_id)
            if key in self.requests:
                self.duplicate_requests+=1
                completed=self.requests[key]
                if completed is not None:self.send(0,self.flow(robot,offset+1),completed,rpc_id)
                return
            # A latched goal gate must still permit real GetResult/CancelGoal cleanup.
            admission=self.ready[robot] if self.guardian is None or offset==0 else True
            if not admission or not self.probes[robot].server_is_ready():
                self.blocked_requests+=1;return
            request=deserialize_message(body,typ.Request)
            if self.guardian is not None and offset==0 and not self.guardian.observe_send_goal(request):
                self.blocked_requests+=1;return
            self.requests[key]=None
            self.forwarded_requests+=1
            future=self.clients[offset].call_async(request)
            def completed(done):
                response=done.result()
                if self.guardian is not None and offset==0:self.guardian.observe_goal_response(request,response)
                payload=serialize_message(response)
                self.requests[key]=payload
                self.send(0,self.flow(robot,offset+1),payload,rpc_id)
            future.add_done_callback(completed)

    def close(self):
        self.node.destroy_timer(self.timer)
        if self.robot is None:
            for robot in tuple(self.endpoints):self._set_ready(robot,False)
        else:
            for subscription in self.subscriptions:self.node.destroy_subscription(subscription)
            for client in self.clients.values():self.node.destroy_client(client)
            for probe in self.probes.values():probe.destroy()

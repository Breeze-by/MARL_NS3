"""Network-local, per-robot fail-closed permission; no policy/pose rewriting."""
import time
from bound_peer import frozen


class DeliveryGuard:
    def __init__(self,robot,session_id,sim_now,stop,wall_now=time.monotonic):
        self.robot=f"tb{robot}"
        self.session_id=session_id
        self.sim_now,self.wall_now,self.stop=sim_now,wall_now,stop
        self.health=self.mask=None
        self.health_receipt=self.mask_receipt=None
        self.armed=False
        self.fault=None
        self.events=[]

    def reason(self):
        if self.health is None or self.mask is None:return "missing_health_or_bound_mask"
        now,wall=self.sim_now(),self.wall_now()
        if wall-self.health_receipt>.3:return "health_heartbeat_stale"
        if wall-self.mask_receipt>.3:return "bound_mask_receipt_stale"
        if not frozen.state_fresh(self.health,now):return "health_original_sources_stale"
        if not frozen.state_fresh(self.mask["bound_state"],now):return "bound_mask_original_sources_stale"
        return None

    def trip(self,reason):
        if self.fault is None:
            self.fault=reason
            self.events.append(dict(kind="latched_INVALID",reason=reason,robot=self.robot,
                session_id=self.session_id,sim=self.sim_now(),monotonic=self.wall_now()))
            self.stop(reason)

    def tick(self):
        if self.armed and self.fault is None:
            reason=self.reason()
            if reason:self.trip(reason)

    def receive_health(self,state):
        # Check the previous interval first. A newly delivered packet cannot
        # conceal a real outage that already exceeded the wall/source limits.
        self.tick()
        if self.health is not None and state["sequence"]<=self.health["sequence"]:
            return False
        self.health=state
        self.health_receipt=self.wall_now()
        self.tick()
        return self.fault is None

    def receive_bound(self,binding,native=None):
        self.tick()
        if binding["robot"]!=self.robot or binding["session_id"]!=self.session_id:
            self.trip("mask_binding_robot_or_epoch_mismatch")
            return False
        state=binding["bound_state"]
        if self.mask is not None and state["sequence"]<=self.mask["bound_state"]["sequence"]:
            return False
        if not frozen.state_fresh(state,self.sim_now()):
            if self.armed:self.trip("bound_mask_original_sources_stale")
            return False
        self.mask=binding
        self.mask_receipt=self.wall_now()
        self.tick()
        return self.fault is None

    def arm(self):
        if self.fault is not None or self.reason() is not None:return False
        self.armed=True
        self.events.append(dict(kind="armed",robot=self.robot,session_id=self.session_id,
            sim=self.sim_now(),monotonic=self.wall_now()))
        return True

    def may_send_goal(self):
        self.tick()
        return self.armed and self.fault is None


class LocalStop:
    """Original UUID cancel/zero/pause primitives on local ROS, never new goals.

    Use a steady clock even when the containing node follows /clock. The
    external supervisor still performs the frozen physical-stop certification.
    """
    def __init__(self,node,robot,session_id):
        import rclpy
        from rclpy.clock import Clock,ClockType
        from geometry_msgs.msg import Twist
        from action_msgs.srv import CancelGoal
        from nav2_msgs.srv import ManageLifecycleNodes
        from nav2_msgs.action import NavigateToPose
        from std_msgs.msg import String
        from action_msgs.msg import GoalStatusArray
        from rclpy.qos import qos_profile_action_status_default
        self.node,self.robot=node,robot
        self.records=[];self.owned=set();self.accepted=set();self.terminals={};self.stopped=set();self.futures=[]
        self.Twist,self.CancelGoal,self.Manage=Twist,CancelGoal,ManageLifecycleNodes
        prefix=f"/tb{robot}"
        self.zero=node.create_publisher(Twist,prefix+"/cmd_vel",10)
        self.cancel=node.create_client(CancelGoal,prefix+"/navigate_to_pose/_action/cancel_goal")
        self.result=node.create_client(NavigateToPose.Impl.GetResultService,prefix+"/navigate_to_pose/_action/get_result")
        self.pause=node.create_client(ManageLifecycleNodes,prefix+"/lifecycle_manager_navigation/manage_nodes")
        self.fault_pub=node.create_publisher(String,"/net01/guard_fault",10)
        self.status_subscription=node.create_subscription(GoalStatusArray,
            prefix+"/navigate_to_pose/_action/status",self.observe_status,qos_profile_action_status_default)
        self.guard=DeliveryGuard(robot,session_id,lambda:node.get_clock().now().nanoseconds/1e9,self.stop)
        self.timer=node.create_timer(.02,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def tick(self):
        self.guard.tick()
        if self.guard.fault:self.zero.publish(self.Twist())

    def cancel_owned(self,uuid):
        if uuid in self.stopped:return
        self.stopped.add(uuid)
        request=self.CancelGoal.Request();request.goal_info.goal_id.uuid=list(bytes.fromhex(uuid))
        future=self.cancel.call_async(request);self.futures.append(future)
        def cancelled(done):
            response=done.result()
            self.records.append(dict(kind="actual_local_cancel_response",uuid=uuid,return_code=response.return_code,
                goals_canceling=[bytes(g.goal_id.uuid).hex() for g in response.goals_canceling]))
            request=self.result.srv_type.Request();request.goal_id.uuid=list(bytes.fromhex(uuid))
            result=self.result.call_async(request);self.futures.append(result)
            result.add_done_callback(lambda f:self.records.append(dict(kind="actual_local_GetResult",uuid=uuid,status=f.result().status)))
        future.add_done_callback(cancelled)

    def stop(self,reason):
        import json
        from std_msgs.msg import String
        self.zero.publish(self.Twist())
        self.fault_pub.publish(String(data=json.dumps(dict(robot=self.robot,session_id=self.guard.session_id,reason=reason))))
        # Pending requests remain unknown. Zero/pause happen immediately;
        # a later real accepted response below triggers its exact UUID cancel.
        for uuid in tuple(self.accepted):self.cancel_owned(uuid)
        request=self.Manage.Request();request.command=self.Manage.Request.PAUSE
        future=self.pause.call_async(request);self.futures.append(future)
        future.add_done_callback(lambda f:self.records.append(dict(kind="actual_local_pause_response",success=f.result().success)))

    def observe_send_goal(self,request):
        if not self.guard.may_send_goal():return False
        self.owned.add(bytes(request.goal_id.uuid).hex())
        return True

    def observe_goal_response(self,request,response):
        uuid=bytes(request.goal_id.uuid).hex()
        self.records.append(dict(kind="actual_local_goal_response",uuid=uuid,accepted=response.accepted))
        if not response.accepted:self.owned.discard(uuid)
        elif uuid not in self.terminals:
            self.accepted.add(uuid)
            if self.guard.fault:self.cancel_owned(uuid)

    def observe_status(self,message):
        for status in message.status_list:
            uuid=bytes(status.goal_info.goal_id.uuid).hex()
            if uuid in self.owned and status.status in (4,5,6):
                self.terminals[uuid]=status.status
                self.accepted.discard(uuid)
                self.owned.discard(uuid)
                self.records.append(dict(kind="actual_local_status_terminal",uuid=uuid,status=status.status))

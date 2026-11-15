"""ROS local proxy: original full-CDR Action/topic routing with wall delay."""
import json
import os
import time

from rclpy.serialization import deserialize_message, serialize_message
from nav2_msgs.action import NavigateToPose

import gateway as original
from action_wire import ActionWire
from execution_profile import ROS_DELAY_PROFILE_ID
from ros_delay_runtime import WallDelayFIFO


class DelayActionWire(ActionWire):
    def __init__(self, *args, goal_permission, rejection_records, **kwargs):
        kwargs['reliable'] = False  # No injected loss: omit optional Wi-Fi ACK/retry protocol in every D arm.
        super().__init__(*args, **kwargs)
        self.goal_permission = goal_permission
        self.proxy_rejections = rejection_records

    def receive(self, peer, flow, body, rpc_id):
        if (self.robot is not None and peer == 0 and flow == self.flow(self.robot, 0)
                and rpc_id >> 32 == self.session_id and (flow, rpc_id) not in self.requests):
            reason = self.goal_permission(self.robot)
            if reason is None:
                if not self.guardian.guard.may_send_goal():
                    reason = 'local_goal_permission:' + str(self.guardian.guard.reason())
                elif not self.ready[self.robot] or not self.backend_is_ready():
                    reason = 'proxy_backend_not_ready'
            if reason is not None:
                request = deserialize_message(body, NavigateToPose.Impl.SendGoalService.Request)
                response = NavigateToPose.Impl.SendGoalService.Response()
                response.accepted = False
                response.stamp = self.node.get_clock().now().to_msg()
                payload = serialize_message(response)
                key = (flow, rpc_id)
                self.request_bodies[key] = bytes(body)
                self.requests[key] = payload
                self.proxy_rejections.append(dict(kind='proxy_admission_rejection', robot=self.robot,
                    uuid=bytes(request.goal_id.uuid).hex(), rpc_id=rpc_id, flow=flow, reason=reason,
                    monotonic_ns=time.monotonic_ns(), sim_ns=self.node.get_clock().now().nanoseconds,
                    forwarded_to_Nav2=False, response_accepted=False,
                    semantics='Proxy admission refusal, not a Nav2 response or a terminal state'))
                self._send_rpc(self.robot, 1, payload, rpc_id)
                return
        return super().receive(peer, flow, body, rpc_id)


class ROSDelayGateway(original.Gateway):
    def __init__(self, *args, **kwargs):
        self.delay_queue = WallDelayFIFO(int(os.environ['NET01_ROS_DELAY_WALL_MS']))
        self.delay_closing = False
        self.delay_stop_reason = None
        self.delay_outside_epoch = {}
        self.delay_proxy_rejections = []
        self.delay_close = None
        super().__init__(*args, **kwargs)
        if self.mode != 'A' or self.execution_profile['id'] != ROS_DELAY_PROFILE_ID:
            raise ValueError('ROS delay proxy requires its explicit local mode-A profile')
        self.record('ros_delay_proxy_entry', delay_ns=self.delay_queue.delay_ns,
            action_application_confirmation=False, business_backend='ROS_LOCAL_WALL_DELAY_FIFO',
            clock_stop_admin='Original independent control, not delayed')

    def install_wires(self):
        base = original.ActionWire
        def factory(*args, **kwargs):
            return DelayActionWire(*args, goal_permission=self.goal_permission,
                rejection_records=self.delay_proxy_rejections, **kwargs)
        original.ActionWire = factory
        try:
            return super().install_wires()
        finally:
            original.ActionWire = base

    def goal_permission(self, robot):
        if self.delay_stop_reason is not None:
            return self.delay_stop_reason
        if self.r.get_clock().now().nanoseconds >= self.execution_profile['startup_contract']['decision_permission_end_ns']:
            return 'fixed_goal_budget_closed'
        return None

    def send(self, sender, receiver, flow, body, rpc_id=0, source_stamp_ns=0):
        # Once owned close begins, periodic telemetry is outside this finite
        # admission epoch. Already admitted data and Action RPCs still drain.
        if self.delay_closing and not (200 <= flow < 300 and (flow-200)%20 <= 5):
            self.delay_outside_epoch[str(flow)] = self.delay_outside_epoch.get(str(flow), 0)+1
            return
        if self.failure:
            return super().send(sender, receiver, flow, body, rpc_id, source_stamp_ns)
        super().send(sender, receiver, flow, body, rpc_id, source_stamp_ns)
        frame = self.direct.pop()
        frame[0]['backend'] = 'ROS_LOCAL_WALL_DELAY_FIFO'
        self.delay_queue.admit(frame, time.monotonic_ns(), self.r.get_clock().now().nanoseconds)

    def _progress_transport(self):
        # A future-only queue is separate from original direct, so the original
        # <=1ms idle wait remains available; no timer, busy wait or sleep handler.
        now_ns = time.monotonic_ns()
        if self.delay_queue.pending and self.delay_queue.pending[0][1]['due_monotonic_ns'] <= now_ns:
            self.direct.extend(self.delay_queue.release_due(now_ns, self.r.get_clock().now().nanoseconds,
                'closing_drain' if self.delay_closing else 'open_ingress'))
        return super()._progress_transport()

    def extend_status(self, data):
        data['actual_rpc_cleanup']['delay_rpc_queued'] = self.delay_queue.pending_rpc()
        data['ros_delay'] = dict(delay_ns=self.delay_queue.delay_ns,
            pending_frames=len(self.delay_queue.pending), closing=self.delay_closing)

    def _close(self):
        self.delay_closing = True
        self.delay_stop_reason = 'owned_gateway_close'
        begin = time.monotonic_ns()
        # The original supervisor's SIGINT/TERM/hard cleanup deadlines still
        # bound this work; no extra timeout or altered release deadline exists.
        while self.failure is None:
            rpc_pending = (self.wires is not None and (
                any(not f.done() for f, _, _ in self.action_c.pending.values())
                or any(value is None for action in self.action_r.values() for value in action.requests.values())
                or any(state['inflight'] for states in
                    [*self.action_c.service_states.values(), *self.action_c.retired_services.values()]
                    for state in states)))
            if not self.delay_queue.pending and not self.direct and not rpc_pending:
                break
            self.poll()
        self.delay_close = dict(begin_monotonic_ns=begin, end_monotonic_ns=time.monotonic_ns(),
            admitted_frames_pending=len(self.delay_queue.pending)+len(self.direct),
            unforwarded_goal_policy='Due-time proxy admission rejection; original UUID/RPC and delayed refusal response',
            parent_bounds_unchanged=True)
        clean = super()._close()
        self.cleanup['ros_delay'] = self.delay_close
        return clean and self.delay_close['admitted_frames_pending'] == 0

    def persist(self):
        with (self.directory/'ros-delay-queue.json').open('x') as stream:
            json.dump(dict(schema='ros-local-wall-delay-fifo-v1', delay_ns=self.delay_queue.delay_ns,
                clock='time.monotonic_ns', frames=self.delay_queue.rows,
                outside_closed_admission_epoch=self.delay_outside_epoch,
                proxy_admission_rejections=self.delay_proxy_rejections, close=self.delay_close,
                semantics='Original full body/header unchanged; release is leaving hold FIFO into original ready direct batch, not per-frame receive/publish/HQ take. release_sim_ns is the actual R clock at that same batch boundary. Injected hold is not source-to-HQ latency. Periodic captures after owned ingress closes are not admitted frames.'), stream)
        return super().persist()

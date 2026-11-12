"""Pending admission: real domain95 LocalStop/admin/paused-clock fixture.

Reuse ControlledServer and original LocalStop/Gateway admin callback. Synthetic
health/bound inputs, controlled Action/PAUSE servers; no robot/native/Gazebo.
"""
import argparse
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "net01"))
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.task import Future
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from geometry_msgs.msg import Twist
from rosgraph_msgs.msg import Clock
from builtin_interfaces.msg import Time
from unique_identifier_msgs.msg import UUID
from std_msgs.msg import String
from std_srvs.srv import Trigger, SetBool
from check_action_wire import ControlledServer
from delivery_guard import LocalStop
from execution_profile import load_profile
from gateway import Gateway
from time_controller import TimeController

PROFILE = "controlled1000-clock100-q10ms-pace10-raster-simhealth"


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ack-socket", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    result = dict(status="RUNNING", checks={}, profile=PROFILE, domain=95,
        scope="Real DDS controlled Action/local stop + actual admin callback; synthetic health/bound and paused ROS clock; no native/robot/Nav2/Gazebo/NN/physical-stop claim",
        central_network_future="NOT_EXERCISED; controlled local client pending/terminal recorded, never substituted for C result")
    deadline = time.monotonic() + 30.
    context = rclpy.get_default_context(); nodes = []; stops = []; servers = []; executor = None
    coordinator = None
    zeros = {1: [], 2: []}; pauses = []; controls = dict(count=0, first=None, last=None); seq = 0
    current = dict(session_id=61, mode="STOP_COUPLED", failure=None,
                   authority_exited=True, expected_shutdown=False)
    next_admin = 0.

    def check(name, condition):
        assert condition, name
        result["checks"][name] = True
        print("PASS", name, flush=True)

    def fresh(stop):
        nonlocal seq
        seq += 1; now = stop.node.get_clock().now().nanoseconds / 1e9
        state = dict(ready=True, sequence=seq, generated_sim=now,
            odom_stamps={r: now for r in ("tb1", "tb2", "tb3")},
            correction_stamps={r: now for r in ("tb1", "tb2", "tb3")})
        stop.guard.receive_health(state)
        stop.guard.receive_bound(dict(robot=f"tb{stop.robot}", session_id=61, bound_state=state))

    def pump():
        nonlocal next_admin
        now = time.monotonic()
        if now > deadline: raise TimeoutError("Original30wall controlled ROS fixture bound")
        if now >= next_admin:
            admin.publish(String(data=json.dumps(current))); next_admin = now + .02
        for stop in stops:
            if stop.guard.armed and stop.guard.fault is None: fresh(stop)
        executor.spin_once(timeout_sec=.002)
        if coordinator is not None: coordinator.poll()

    def until(predicate, seconds=6.):
        end = min(deadline, time.monotonic() + seconds)
        while not predicate() and time.monotonic() < end: pump()
        if not predicate(): raise TimeoutError("controlled ROS condition deadline")

    def duration(seconds):
        end = min(deadline, time.monotonic() + seconds)
        while time.monotonic() < end: pump()

    def request(robot):
        req = NavigateToPose.Impl.SendGoalService.Request()
        req.goal_id = UUID(uuid=list(bytes([4, robot]) + bytes(range(2, 16))))
        req.goal.pose.header.frame_id = "map"; req.goal.pose.header.stamp.sec = 100
        req.goal.pose.pose.position.x = robot + .125; req.goal.pose.pose.orientation.w = 1.
        return req

    try:
        rclpy.init(context=context, domain_id=95)
        fixture = Node("net01_f04_controlled_fixture", context=context)
        nodes = [fixture] + [Node(f"net01_f04_tb{r}", context=context,
            parameter_overrides=[Parameter("use_sim_time", value=True)]) for r in (1, 2)]
        executor = SingleThreadedExecutor(context=context)
        for node in nodes: executor.add_node(node)
        servers = [ControlledServer(fixture, r) for r in (1, 2)]
        for robot in (1, 2):
            def pause(request, response, robot=robot):
                pauses.append(dict(robot=robot, command=request.command, monotonic=time.monotonic()))
                response.success = True; return response
            fixture.create_service(ManageLifecycleNodes,
                f"/tb{robot}/lifecycle_manager_navigation/manage_nodes", pause)
            fixture.create_subscription(Twist, f"/tb{robot}/cmd_vel",
                lambda message, robot=robot: zeros[robot].append((message, time.monotonic())), 10)
        profile = load_profile(PROFILE)
        stops = [LocalStop(node, r, 61, execution_profile=profile) for r, node in enumerate(nodes[1:], 1)]
        owner = SimpleNamespace(guards={s.robot: s for s in stops})
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        admin = fixture.create_publisher(String, "/net01/time_control_state", qos)
        def control_receive(message):
            row = dict(data=json.loads(message.data), received_monotonic=time.monotonic())
            controls["count"] += 1
            if controls["first"] is None: controls["first"] = row
            controls["last"] = row
            Gateway.time_control_state(owner, message)  # Actual production fanout.
        nodes[1].create_subscription(String, "/net01/time_control_state", control_receive, qos)
        clock = fixture.create_publisher(Clock, "/clock", qos)
        until(lambda: clock.get_subscription_count() >= 2 and admin.get_subscription_count() > 0)
        clock.publish(Clock(clock=Time(sec=100)))
        until(lambda: all(s.node.get_clock().now().nanoseconds == 100_000_000_000 and s.guard.control is not None for s in stops))
        check("unarmed_preflight_STOP_observed_without_permanent_revoke", all(not s.guard.halted for s in stops))
        current.update(mode="RUN", authority_exited=False)
        until(lambda: all(s.guard.control["mode"] == "RUN" for s in stops))
        send = {r: fixture.create_client(NavigateToPose.Impl.SendGoalService,
            f"/tb{r}/navigate_to_pose/_action/send_goal") for r in (1, 2)}
        get = {r: fixture.create_client(NavigateToPose.Impl.GetResultService,
            f"/tb{r}/navigate_to_pose/_action/get_result") for r in (1, 2)}
        until(lambda: all(send[r].service_is_ready() and get[r].service_is_ready()
            and stops[r-1].cancel.service_is_ready() and stops[r-1].pause.service_is_ready()
            and stops[r-1].zero.get_subscription_count() > 0 for r in (1, 2)))
        # Normal authority-exited HOLD may be first admin terminal snapshot.
        stop = stops[1]; fresh(stop); check("tb2_fresh_original_arm", stop.guard.arm())
        req = request(2); uuid2 = bytes(req.goal_id.uuid).hex()
        check("tb2_original_pending_UUID_registered", stop.observe_send_goal(req))
        response = send[2].call_async(req); until(response.done)
        until(lambda: uuid2 in servers[1].executing)
        result_req = NavigateToPose.Impl.GetResultService.Request(); result_req.goal_id = req.goal_id
        pending_result = get[2].call_async(result_req)
        check("actual_accept_held_and_result_pending_before_local_hook",
            response.result().accepted and uuid2 not in stop.accepted and not pending_result.done())
        current.update(mode="HOLD", authority_exited=True)
        until(lambda: stop.guard.halted and bool(zeros[2]) and any(p["robot"] == 2 for p in pauses))
        check("normal_first_HOLD_revoke_real_zero_pause_no_guard_fault_or_fake_terminal",
            stop.guard.fault is None and not stop.terminals and not servers[1].cancelled and not pending_result.done())
        stop.observe_goal_response(req, response.result())
        until(lambda: stop.terminals.get(uuid2) == 5 and any(r["kind"] == "actual_local_GetResult" and r["uuid"] == uuid2 and r["status"] == 5 for r in stop.records))
        until(pending_result.done)
        check("late_accepted_after_normal_revoke_real_same_UUID_cancel_and_result5",
            servers[1].cancelled == [uuid2] and pending_result.result().status == 5
            and any(r["kind"] == "actual_local_cancel_response" and r["goals_canceling"] == [uuid2] for r in stop.records))
        current.update(mode="RUN", authority_exited=False)
        until(lambda: stop.guard.control["mode"] == "RUN")
        check("normal_revoke_not_automatically_rearmed", not stop.guard.arm() and not stop.guard.may_send_goal())
        # A second LocalStop epoch tests real steady-wall watchdog while ROS
        # clock is paused, with admin snapshots and healthy fixture states alive.
        stop = stops[0]; fresh(stop); check("tb1_actual_paused_R_clock_arm", stop.guard.arm())
        req = request(1); uuid1 = bytes(req.goal_id.uuid).hex()
        check("tb1_original_pending_UUID_registered", stop.observe_send_goal(req))
        response = send[1].call_async(req); until(response.done)
        stop.observe_goal_response(req, response.result())
        until(lambda: uuid1 in servers[0].executing)
        duration(.35)
        check("simhealth_does_not_trip_at_old_wall300", stop.guard.fault is None)
        until(lambda: stop.guard.fault is not None and stop.terminals.get(uuid1) == 5
            and any(r["kind"] == "actual_local_GetResult" and r["uuid"] == uuid1 and r["status"] == 5 for r in stop.records))
        trip = next(r for r in stop.guard.events if r["kind"] == "latched_INVALID")
        old = trip["progress_context"]
        actual_age = trip["monotonic"] - old["last_sim_progress_wall"]
        check("real_2wall_progress_fault_not_manual_trip_or_only_HOLD",
            stop.guard.fault == "R_sim_clock_progress_wall_timeout" and actual_age > 2. and trip["monotonic"] - old["control_receipt_monotonic"] <= 2.
            and bool(zeros[1]) and any(p["robot"] == 1 for p in pauses) and servers[0].cancelled == [uuid1])
        check("paused_actual_ROS_clock_and_actual_zero_PAUSE_commands",
            all(s.node.get_clock().now().nanoseconds == 100_000_000_000 for s in stops)
            and all(m == Twist() for rows in zeros.values() for m, _ in rows)
            and all(p["command"] == ManageLifecycleNodes.Request.PAUSE for p in pauses))
        until(lambda: all(any(r["kind"] == "actual_local_pause_response" and r["success"] for r in s.records) for s in stops))
        check("both_actual_local_PAUSE_responses_success", True)
        # Separate no-Goal component session in the same isolated context:
        # real TimeController + real rclpy Futures + actual HOLD service.
        # Native READY/readiness below are explicitly controlled fixture input,
        # not an ns3 ACK. No successful physical response is manufactured.
        physics_calls = []
        physics_release = Future()
        async def hung_physics(request, response):
            physics_calls.append(time.monotonic_ns())
            await physics_release
            response.success = False
            response.message = json.dumps(dict(before_ns=0, after_ns=0,
                before_iterations=0, after_iterations=0, completed_steps=0))
            return response
        fixture.create_service(Trigger, "/net01/physics_step", hung_physics,
                               callback_group=ReentrantCallbackGroup())
        class ObservedTimeController(TimeController):
            def gateway(self, message):
                before = (self.state.clock_progress_ns, self.state.native_progress_ns)
                super().gateway(message)  # Actual production callback exactly once.
                self.gateway_observations.append(dict(received_monotonic_ns=time.monotonic_ns(),
                    guard_armed={r:g['armed'] for r,g in json.loads(message.data)['guards'].items()},
                    motion_armed_since_ns=self.state.motion_armed_since_ns,
                    actual_stamps_before=before,
                    actual_stamps_after=(self.state.clock_progress_ns, self.state.native_progress_ns)))
        coordinator = ObservedTimeController(args.ack_socket, args.output / "time-controller.json", 62, PROFILE)
        coordinator.gateway_observations = []
        nodes.append(coordinator); executor.add_node(coordinator)
        hold_client = fixture.create_client(SetBool, "/net01/time_control/hold")
        gateway_state = fixture.create_publisher(String, "/net01/gateway_state", qos)
        until(lambda: coordinator.step.service_is_ready() and hold_client.service_is_ready()
              and gateway_state.get_subscription_count() > 0 and clock.get_subscription_count() >= 3)
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as native_fixture:
            native_fixture.sendto(json.dumps(dict(kind="ready", horizon_ns=0,
                monotonic_ns=time.monotonic_ns())).encode(), str(args.ack_socket))
        gateway_body = dict(session_id=62, clock_reader_ready=True,
            clock_writer_discovered=True, clock_publishers=1, gateway_monotonic_ns=time.monotonic_ns(),
            anchor=None, failure=None, guards={str(r): dict(armed=False) for r in (1, 2, 3)})
        gateway_state.publish(String(data=json.dumps(gateway_body)))
        clock.publish(Clock(clock=Time(sec=100)))
        until(lambda: len(physics_calls) == 1 and coordinator.future is not None)
        physical_future = coordinator.future
        issued = coordinator.state.inflight_since_ns
        check("actual_DDS_false_guards_do_not_activate_global_watchdog",
            coordinator.state.motion_armed_since_ns is None and len(coordinator.gateway_observations) >= 1)
        until(lambda: coordinator.state.clock_ns == 100_000_000_000)
        actual_stamps = (coordinator.state.clock_progress_ns, coordinator.state.native_progress_ns)
        gateway_body['guards']['1']['armed'] = True
        gateway_body['gateway_monotonic_ns'] = time.monotonic_ns()
        gateway_state.publish(String(data=json.dumps(gateway_body)))
        until(lambda: coordinator.state.motion_armed_since_ns is not None)
        baseline = coordinator.state.motion_armed_since_ns
        check("actual_DDS_ANY_one_guard_ARM_activates_without_forged_progress",
            baseline >= issued and (coordinator.state.clock_progress_ns, coordinator.state.native_progress_ns) == actual_stamps)
        received = len(coordinator.gateway_observations)
        gateway_body['gateway_monotonic_ns'] = time.monotonic_ns()
        gateway_state.publish(String(data=json.dumps(gateway_body)))
        until(lambda: len(coordinator.gateway_observations) > received)
        check("actual_DDS_repeated_ARM_does_not_renew_baseline_or_actual_stamps",
            coordinator.state.motion_armed_since_ns == baseline
            and (coordinator.state.clock_progress_ns, coordinator.state.native_progress_ns) == actual_stamps
            and sum(r[0] == 'actual_R_guard_ARM_watchdog_activation' for r in coordinator.records) == 1)
        hold_future = hold_client.call_async(SetBool.Request(data=True))
        until(lambda: coordinator.pending_holds == 1)
        check("real_rclpy_HOLD_waiter_is_pending_before_watchdog",
            not hold_future.done() and not physical_future.done() and len(coordinator.hold_waiters) == 1)
        until(hold_future.done)
        actual_hold = hold_future.result()
        hold_snapshot = json.loads(actual_hold.message)
        observed = time.monotonic_ns()
        check("actual_HOLD_response_false_inflight_preserved_no_fake_ACK_or_second_token",
            not actual_hold.success and hold_snapshot["physics_failed"]
            and hold_snapshot["failure"] == "physics_RPC_wall_timeout"
            and hold_snapshot["physical_RPC_inflight"] and hold_snapshot["native_ACK_ns"] == 0
            and hold_snapshot["physical_ns"] is None and not physical_future.done()
            and len(physics_calls) == 1 and observed - issued > 2_000_000_000)
        result["actual_controller_HOLD"] = dict(snapshot=hold_snapshot,
            physical_issued_monotonic_ns=issued, response_observed_monotonic_ns=observed,
            controlled_service_calls=len(physics_calls), physical_future_done_at_HOLD=physical_future.done(),
            actual_gateway_receipts=coordinator.gateway_observations)
        # Cleanup only: a real negative response closes the controlled service;
        # first timeout is retained and never converted to an ACK/success.
        physics_release.set_result(None)
        until(lambda: coordinator.future is None)
        check("controlled_physics_cleanup_reject_preserves_first_timeout",
            coordinator.state.failure == "physics_RPC_wall_timeout" and coordinator.state.native_ns == 0
            and coordinator.state.physical_ns is None and len(physics_calls) == 1)
        result.update(status="PASS_CONTROLLED_ROS_ONLY", actual_watchdog_wall_s=actual_age, actual_fault_progress_context=old,
            original_UUIDs={1: uuid1, 2: uuid2}, controls=controls, pauses=pauses,
            zero_counts={r: len(rows) for r, rows in zeros.items()},
            guard_events={s.robot: s.guard.events for s in stops}, local_records={s.robot: s.records for s in stops})
    except BaseException as error:
        result.update(status="FAIL", error=repr(error)); raise
    finally:
        if coordinator is not None: coordinator.close()
        if servers:
            for server in servers: server.close()
        if executor is not None: result["executor_shutdown"] = executor.shutdown(timeout_sec=0.)
        for node in nodes: node.destroy_node()
        context.shutdown()
        result["wall_used_s"] = time.monotonic() - (deadline - 30.)
        result["wall_remaining_s"] = deadline - time.monotonic()
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__": main()

"""Deterministic actual Guard/State methods; 0ROS/native/GZ.

Source-only preparation. Run only after root fixes/reviews the new source.
AST extraction follows check_time_hold.py; no production method is rewritten.
LocalStop I/O spies certify requests only, never DDS responses/physical stopping.
"""
import argparse
import ast
import asyncio
from concurrent.futures import Future
import json
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "net01"))
from execution_profile import load_profile
from time_control_state import TimeControlState, QUANTUM_NS

PROFILE = "controlled1000-clock100-q10ms-pace10-raster-simhealth"
ROBOTS = ("tb1", "tb2", "tb3")


def actual_guards():
    frozen_tree = ast.parse((REPO / "workspace/gz01/peer_keepout.py").read_text())
    constants = {"ROBOTS", "CLOCK_QUANTUM", "ODOM_MAX_AGE", "ODOM_RECEIPT_MAX_AGE", "CORRECTION_MAX_AGE", "CORRECTION_FUTURE"}
    selected = [n for n in frozen_tree.body if
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)
        or isinstance(n, ast.FunctionDef) and n.name == "state_fresh"]
    original = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "actual-frozen-state_fresh", "exec"), original)
    source = REPO / "net01/delivery_guard.py"
    methods = [n for n in ast.parse(source.read_text()).body if
        isinstance(n, ast.FunctionDef) or isinstance(n, ast.ClassDef) and n.name in ("DeliveryGuard", "LocalStop")]
    namespace = {"frozen": SimpleNamespace(state_fresh=original["state_fresh"]),
                 "time": __import__("time")}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["DeliveryGuard"], namespace["LocalStop"], original


class Clock:
    def __init__(self):
        self.sim, self.wall = 10., 100.


def control(**changes):
    return dict(dict(session_id=61, mode="RUN", failure=None, expected_shutdown=False, authority_exited=False), **changes)


def fresh(clock, sequence):
    return dict(ready=True, sequence=sequence, generated_sim=clock.sim,
                odom_stamps={r: clock.sim for r in ROBOTS},
                correction_stamps={r: clock.sim for r in ROBOTS})


def guard_checks(Guard, profile, check):
    def armed(selected):
        c = Clock(); stops = []
        g = Guard(1, 61, lambda: c.sim, stops.append,
                  wall_now=lambda: c.wall, execution_profile=selected)
        g.control_state(control())
        state = fresh(c, 1)
        g.receive_health(state)
        g.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
        assert g.arm(), "synthetic fresh fixture failed to arm"
        return c, g, stops

    c, g, _ = armed(None)
    c.wall += .301; c.sim += .1; g.tick()
    check("legacy_wall300_unchanged", g.fault == "health_heartbeat_stale")
    c, g, _ = armed(profile)
    c.wall += .6; c.sim += .2; g.tick()
    check("new_wall_above300_sim_below300_not_stale", g.fault is None)
    c, g, _ = armed(profile)
    for delta in (.5, 1., 1.5):
        c.wall = 100. + delta; g.control_state(control())
    c.wall = 102.001; g.control_state(control())
    check("repeated_control_cannot_hide_stopped_R_sim_clock", g.fault == "R_sim_clock_progress_wall_timeout")
    c = Clock(); stopped = []
    g = Guard(1, 61, lambda: c.sim, stopped.append, wall_now=lambda: c.wall,
              execution_profile=profile, control_stop=stopped.append)
    g.control_state(control(mode="STOP_COUPLED", authority_exited=True))
    state = fresh(c, 1); g.receive_health(state)
    g.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
    g.control_state(control())
    check("unarmed_preflight_stop_observe_does_not_permanently_revoke", not g.halted and not stopped and g.arm())
    c, g, stops = armed(profile)
    revoked = []; g.control_stop = revoked.append
    g.control_state(control(mode="FAULT_STOP_OBSERVE", failure="native_ACK_progress_wall_timeout", authority_exited=True))
    check("coordinator_failure_plus_authority_exit_is_fault_not_normal_revocation",
        g.fault == "time_control_failure:native_ACK_progress_wall_timeout" and stops == [g.fault] and not revoked)
    c, g, stops = armed(profile)
    g.control_state(control(mode="HOLD", authority_exited=False))
    check("HOLD_without_authority_exit_remains_fault", g.fault == "time_control_HOLD_while_armed" and stops == [g.fault])
    for missing, expected in (("health", "health_heartbeat_stale"), ("mask", "bound_mask_receipt_stale")):
        c, g, stops = armed(profile)
        c.sim += .15; c.wall += .15
        state = fresh(c, 2)
        if missing == "health":
            g.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
        else:
            g.receive_health(state)
        c.sim += .151; c.wall += .151; g.tick()
        check(missing + "_sim301_independently_latches", g.fault == expected and stops == [expected])
        state = fresh(c, 3)
        if missing == "health":
            g.receive_health(state)
        else:
            g.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
        check(missing + "_new_arrival_cannot_clear_old_fault", g.fault == expected and not g.arm() and not g.may_send_goal())
    for arrival in ("health", "mask"):
        c, g, _ = armed(profile)
        c.sim += .301; c.wall += .301
        state = fresh(c, 2)
        if arrival == "health":
            g.receive_health(state)
        else:
            g.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
        check(arrival + "_receive_ticks_previous_interval_first", g.fault is not None)


def state_checks(check):
    t0 = 100_000_000_000
    def started():
        s = TimeControlState(progress_wall_timeout_ns=2_000_000_000)
        s.native("ready", 0, now_ns=t0); s.gateway_clock_ready = True
        s.begin_step(t0)
        return s
    def finish(s):
        s.complete_step(dict(before_ns=0, after_ns=QUANTUM_NS,
            before_iterations=0, after_iterations=10, completed_steps=10), now_ns=t0 + 10_000_000)
    bootstrap = started()
    check("first_token_does_not_forge_clock_or_native_progress",
        bootstrap.clock_progress_ns is None and bootstrap.native_progress_ns is None)
    finish(bootstrap); bootstrap.clock(QUANTUM_NS, now_ns=t0 + 10_000_000)
    bootstrap.begin_step(t0 + 1_900_000_000)
    bootstrap.check_progress(t0 + 2_100_000_000)
    check("no_ARM_bootstrap_clock_native_gap_above2wall_RPC_below2_not_fault",
        bootstrap.failure is None and bootstrap.motion_armed_since_ns is None and bootstrap.inflight)
    for stalled in ("clock", "native"):
        s = started(); finish(s)
        s.clock(QUANTUM_NS, now_ns=t0 + 10_000_000)
        s.observe_motion_armed(t0 + 10_000_000)
        if stalled == "clock": s.native("step", QUANTUM_NS, now_ns=t0 + 1_900_000_000)
        else: s.clock(2 * QUANTUM_NS, now_ns=t0 + 1_900_000_000)
        s.check_progress(t0 + 1_999_000_000)
        check(stalled + "_before2wall_no_fault", s.failure is None)
        s.check_progress(t0 + 2_011_000_000)
        check(stalled + "_stalled_after2wall_fault", s.failure is not None)
    for mode in ("RUN", "HOLD", "STOP_COUPLED"):
        s = started()
        if mode == "HOLD": s.hold()
        elif mode == "STOP_COUPLED": s.stop_observe(True)
        s.check_progress(t0 + 2_001_000_000)
        check(mode + "_inflight_future_has2wall_bound", s.physics_failed and s.failure is not None and s.inflight)
        check(mode + "_failure_cannot_issue_second_token", not s.can_step(t0 + 3_000_000_000))
    late = started()
    late.complete_step(dict(before_ns=0, after_ns=QUANTUM_NS,
        before_iterations=0, after_iterations=10, completed_steps=10), now_ns=t0 + 2_001_000_000)
    check("late_actual_physics_ACK_keeps_preceding2wall_fault",
        late.failure == "physics_RPC_wall_timeout" and late.physics_failed and late.physical_ns == QUANTUM_NS)


def controller_activation_check(check):
    path = REPO / "net01/time_controller.py"
    cls = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "TimeController")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "gateway")
    clock = [100_000_000_000]
    namespace = dict(json=json, time=SimpleNamespace(monotonic_ns=lambda: clock[0]))
    actual = ast.ClassDef(name="ActualGatewayCallback", bases=[], keywords=[], body=[method], decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[actual], type_ignores=[])), str(path), "exec"), namespace)
    node = namespace["ActualGatewayCallback"](); node.session_id = 62
    node.progress_wall_timeout_ns = 2_000_000_000
    node.state = TimeControlState(progress_wall_timeout_ns=2_000_000_000)
    node.gateway_prerequisite = None; rows = []; node.record = lambda *row: rows.append(row)
    node.state.clock(10_000_000, now_ns=clock[0]); node.state.native("step", 10_000_000, now_ns=clock[0])
    data = dict(session_id=62, guards={str(r): dict(armed=False) for r in (1, 2, 3)},
        clock_reader_ready=True, clock_writer_discovered=True, clock_publishers=1,
        gateway_monotonic_ns=clock[0], anchor=None, failure=None)
    def receive(): node.gateway(SimpleNamespace(data=json.dumps(data)))
    clock[0] += 3_000_000_000; receive()
    check("actual_gateway_callback_no_guard_ARM_no_global_activation",
        node.state.motion_armed_since_ns is None and node.state.failure is None)
    data["session_id"] = 999; data["guards"]["2"]["armed"] = True; receive()
    check("other_session_ARM_does_not_activate", node.state.motion_armed_since_ns is None)
    data["session_id"] = 62; receive(); baseline = clock[0]
    check("actual_gateway_ANY_one_guard_ARM_activates_once",
        node.state.motion_armed_since_ns == baseline and sum(r[0] == "actual_R_guard_ARM_watchdog_activation" for r in rows) == 1)
    check("activation_preserves_actual_clock_native_stamps",
        node.state.clock_progress_ns == 100_000_000_000 and node.state.native_progress_ns == 100_000_000_000)
    node.state.check_progress(baseline + 1_999_000_000)
    check("max_ARM_and_actual_progress_grants_exact_new_activation_interval", node.state.failure is None)
    node.state.hold(); assert node.state.run()
    clock[0] = baseline + 1_999_000_000; receive()
    check("repeated_ARM_and_HOLD_RUN_do_not_extend_baseline", node.state.motion_armed_since_ns == baseline)
    clock[0] = baseline + 2_001_000_000; receive()
    first = node.state.failure
    check("late_repeated_ARM_checks_previous_interval_first", first == "actual_clock_progress_wall_timeout")
    node.state.clock(20_000_000, now_ns=clock[0] + 1)
    node.state.native("step", 20_000_000, now_ns=clock[0] + 2)
    check("late_clock_native_ACK_cannot_clear_latched_global_fault",
        node.state.failure == first and not node.state.run() and node.state.motion_armed_since_ns == baseline)


def local_route_check(Guard, LocalStop, profile, check):
    # Actual LocalStop.stop/cancel_owned; only ROS constructors and I/O are spies.
    # Futures deliberately remain pending: never manufacture response/status5.
    zero, pause, cancel, fault = [], [], [], []
    uuid = "0000000078c3ffc00100000000000000"
    def client(rows):
        return SimpleNamespace(call_async=lambda request: (rows.append(request), Future())[1])
    local = LocalStop.__new__(LocalStop)
    local.robot = 1; local.records = []; local.futures = []
    local.owned = {uuid}; local.accepted = {uuid}; local.terminals = {}; local.stopped = set()
    local.Twist = lambda: SimpleNamespace(linear=0., angular=0.)
    local.CancelGoal = SimpleNamespace(Request=lambda: SimpleNamespace(
        goal_info=SimpleNamespace(goal_id=SimpleNamespace(uuid=[]))))
    class PauseRequest:
        PAUSE = 1
    local.Manage = SimpleNamespace(Request=PauseRequest)
    local.zero = SimpleNamespace(publish=zero.append); local.fault_pub = SimpleNamespace(publish=fault.append)
    local.pause = client(pause); local.cancel = client(cancel)
    c = Clock()
    local.guard = Guard(1, 61, lambda: c.sim, local.stop, wall_now=lambda: c.wall, execution_profile=profile)
    local.guard.control_state(control())
    state = fresh(c, 1); local.guard.receive_health(state)
    local.guard.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
    assert local.guard.arm()
    msg = ModuleType("std_msgs.msg"); msg.String = lambda **kwargs: SimpleNamespace(**kwargs)
    package = ModuleType("std_msgs"); package.msg = msg
    with patch.dict(sys.modules, {"std_msgs": package, "std_msgs.msg": msg}):
        c.sim += .301; c.wall += .301; local.guard.tick()
    check("actual_fault_routes_to_cancel_zero_pause_not_only_HOLD",
          bool(zero) and len(pause) == 1 and len(cancel) == 1 and bool(fault)
          and bytes(cancel[0].goal_info.goal_id.uuid).hex() == uuid)
    check("spy_requests_do_not_fake_terminal_or_central_known", not local.terminals and len(local.futures) == 2)
    # Start a fresh epoch, keep a Goal response pending at normal revocation.
    zero.clear(); pause.clear(); cancel.clear(); fault.clear()
    local.records = []; local.futures = []; local.accepted = set(); local.stopped = set()
    c = Clock()
    local.guard = Guard(1, 61, lambda: c.sim, local.stop, wall_now=lambda: c.wall,
        execution_profile=profile, control_stop=lambda reason: local.stop(reason, publish_fault=False))
    local.guard.control_state(control())
    state = fresh(c, 1); local.guard.receive_health(state)
    local.guard.receive_bound(dict(robot="tb1", session_id=61, bound_state=state))
    assert local.guard.arm()
    with patch.dict(sys.modules, {"std_msgs": package, "std_msgs.msg": msg}):
        local.guard.control_state(control(mode="HOLD", authority_exited=True))
    check("armed_first_HOLD_authority_exit_normal_revoke_zero_pause_without_guard_fault",
        local.guard.halted and local.guard.fault is None and bool(zero) and len(pause) == 1 and not fault and not cancel)
    request = SimpleNamespace(goal_id=SimpleNamespace(uuid=list(bytes.fromhex(uuid))))
    local.observe_goal_response(request, SimpleNamespace(accepted=True))
    check("late_accepted_after_fault_free_revoke_exact_UUID_cancel",
        len(cancel) == 1 and bytes(cancel[0].goal_info.goal_id.uuid).hex() == uuid)
    local.guard.control_state(control())
    check("normal_revoke_is_permanent_and_pending_remains_UNKNOWN",
        not local.guard.arm() and not local.guard.may_send_goal() and not local.terminals)
    source = REPO / "net01/a0_runtime.py"
    cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "A0LocalStop")
    namespace = dict(LocalStop=LocalStop, time=__import__("time"))
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), "exec"), namespace)
    for route in ("response_evidence", "active_status"):
        direct = namespace["A0LocalStop"].__new__(namespace["A0LocalStop"])
        direct.__dict__.update(local.__dict__)
        direct.records = []; direct.futures = []; direct.owned = {uuid}
        direct.accepted = set(); direct.stopped = set(); cancel.clear()
        if route == "response_evidence": direct.response_evidence(uuid, True)
        else:
            status = SimpleNamespace(status=2, goal_info=SimpleNamespace(goal_id=request.goal_id))
            direct.observe_status(SimpleNamespace(status_list=[status]))
        check("A0_normal_revoke_late_" + route + "_same_UUID_cancel",
            direct.guard.halted and direct.guard.fault is None and len(cancel) == 1
            and bytes(cancel[0].goal_info.goal_id.uuid).hex() == uuid and not direct.terminals)


async def hold_check(check):
    source = REPO / "net01/time_controller.py"
    controller = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "TimeController")
    methods = [n for n in controller.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ("hold", "poll", "finish_step")]
    actual = ast.ClassDef(name="ActualController", bases=[], keywords=[], body=methods, decorator_list=[])
    wall = [100_000_000_000]
    namespace = dict(json=json, Future=asyncio.Future, time=SimpleNamespace(monotonic_ns=lambda: wall[0]))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[actual], type_ignores=[])), str(source), "exec"), namespace)
    node = namespace["ActualController"]()
    node.state = TimeControlState(progress_wall_timeout_ns=2_000_000_000)
    node.state.native("ready", 0, now_ns=wall[0]); node.state.gateway_clock_ready = True
    node.state.begin_step(wall[0]); node.progress_wall_timeout_ns = 2_000_000_000
    node.pending_holds = 0; node.hold_waiters = []; node.records = []
    node.record = lambda *row: node.records.append(row)
    node.snapshot = lambda: dict(failure=node.state.failure, inflight=node.state.inflight)
    node.publish_state = lambda: None
    class EmptySocket:
        def recv(self, size): raise BlockingIOError
    node.socket = EmptySocket()
    original_future = node.future = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(node.hold(SimpleNamespace(data=True), SimpleNamespace()))
    await asyncio.sleep(0)
    check("actual_HOLD_waits_original_inflight_no_fake_success", not task.done() and node.pending_holds == 1)
    wall[0] += 1_999_000_000; node.poll()
    check("actual_HOLD_future_before2wall_still_pending", not task.done() and not original_future.done())
    wall[0] += 2_000_000; node.poll()
    response = await task
    check("actual_poll_releases_HOLD_after2wall_as_failure_not_ACK",
        not response.success and node.state.physics_failed and node.state.inflight
        and node.future is original_future and not original_future.done() and not node.state.expected_shutdown)
    original_future.cancel()


def observer_checks(frozen, check):
    c = Clock(); namespace = dict(json=json, time=SimpleNamespace(monotonic=lambda: c.wall),
        ROBOTS=ROBOTS, state_fresh=frozen["state_fresh"])
    path = REPO / "workspace/gz01/run_case.py"
    base = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "Observer")
    methods = [n for n in base.body if isinstance(n, ast.FunctionDef) and n.name in ("peer_health", "peer_error")]
    cls = ast.ClassDef(name="Observer", bases=[], keywords=[], body=methods, decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), "exec"), namespace)
    namespace["original"] = SimpleNamespace(Observer=namespace["Observer"], ROBOTS=ROBOTS, state_fresh=frozen["state_fresh"])
    path = REPO / "net01/run_network_case.py"
    candidate = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "NetworkObserver")
    selected = [n for n in candidate.body if isinstance(n, ast.FunctionDef) and n.name in ("peer_health", "sim_peer_error", "peer_error")]
    cls = ast.ClassDef(name="NetworkObserver", bases=candidate.bases, keywords=[], body=selected, decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), "exec"), namespace)
    def node(sim_health):
        c.sim = 10.; c.wall = 100.
        n = namespace["NetworkObserver"](); n.sim_health = sim_health; n.peer_received_sim = None
        n.peer_guard = True; n.sim = c.sim; n.event = lambda *args, **kwargs: None
        n.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=round(c.sim * 1e9)))
        n.network_fault = None; n.direct_reference = False; n.network_received = c.wall
        n.network_state = dict(failure=None, connected=True, guards={})
        data = dict(fresh(c, 1), ages={}, failures={})
        n.peer_health(SimpleNamespace(data=json.dumps(data)))
        return n
    n = node(False); c.wall += .6; c.sim += .2; n.sim = c.sim; n.network_received = c.wall
    check("actual_Observer_legacy_peer_receipt_wall300", n.peer_error() == "peer state heartbeat stale")
    n = node(True); c.wall += .6; c.sim += .2; n.sim = c.sim; n.network_received = c.wall
    check("actual_Observer_new_peer_receipt_not_wall300", n.peer_error() is None and n.peer_received == 100.)
    c.sim += .101; n.sim = c.sim
    check("actual_Observer_new_peer_receipt_sim301", n.peer_error() == "peer state heartbeat stale")
    n = node(True); c.sim += .1; n.sim = c.sim
    n.peer_state["odom_stamps"]["tb1"] = c.sim - .401
    check("actual_Observer_retains_original_source_freshness", n.peer_error().startswith("peer odom/source-time TF not fresh:"))
    n = node(True); c.wall += .301
    check("actual_Observer_process_status_retains_wall300", n.peer_error() == "Network gateway receipt stale")
    tree = ast.parse((REPO / "workspace/gz01/peer_keepout.py").read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "publish_masks")
    test = next(n.test for n in ast.walk(method) if isinstance(n, ast.If) and
        any(isinstance(x, ast.Name) and x.id == "ODOM_RECEIPT_MAX_AGE" for x in ast.walk(n.test)))
    expr = compile(ast.Expression(body=test), "actual-Peer-snapshot-odom-predicate", "eval")
    def rejected(age):
        return eval(expr, frozen, dict(robot="tb1", ages={"tb1": dict(source=.1, receipt=age)}))
    check("actual_frozen_Peer_odom_receipt_wall200_retained", not rejected(.199) and rejected(.201))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    result = dict(status="RUNNING", scope="Actual AST Guard/LocalStop and pure State; synthetic clocks/I/O spies; 0ROS/native/GZ", checks={})
    def check(name, condition):
        assert condition, name
        result["checks"][name] = True
    try:
        profile = load_profile(PROFILE)
        Guard, LocalStop, frozen = actual_guards()
        guard_checks(Guard, profile, check); state_checks(check)
        controller_activation_check(check)
        local_route_check(Guard, LocalStop, profile, check)
        asyncio.run(hold_check(check))
        observer_checks(frozen, check)
        result["status"] = "PASS_DETERMINISTIC_ONLY_NOT_ROS_QUALIFICATION"
    except BaseException as error:
        result.update(status="FAIL", error=repr(error)); raise
    finally:
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__": main()

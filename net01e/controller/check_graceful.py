"""Fixed no-motion qualifications for the external executor exit adapter."""
import argparse
from array import array
import io
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from continuous_dds import save, observe_exception
from graceful_spin import make_graceful_spin

DOMAIN = 97
TOPIC = '/net01e/controller/fixed_grid'


def ros_types():
    import rclpy
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    return rclpy, Node, SignalHandlerOptions


def child(directory, mode):
    rclpy, Node, SignalHandlerOptions = ros_types()
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from nav_msgs.msg import OccupancyGrid
    rclpy.init(domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
    record = dict(pid=os.getpid(), mode=mode, callbacks=[], original_submit_calls=[], events=[])

    class FixtureNode(Node):
        def send_goal(self, robot, target, token):
            record['original_submit_calls'].append(dict(robot=robot, token=token,
                monotonic_ns=time.monotonic_ns()))

        def now(self):
            return time.monotonic()

        def record(self, event):
            record['events'].append(dict(event, observed_monotonic_ns=time.monotonic_ns()))

    node = FixtureNode('net01e_graceful_' + mode)
    primary = None
    try:
        if mode != 'idle':
            grid = OccupancyGrid()
            grid.header.frame_id = 'odom'
            grid.info.width = grid.info.height = 400
            grid.info.resolution = struct.unpack('<f', struct.pack('<f', .05))[0]
            grid.info.origin.orientation.w = 1.
            grid.data = array('b', [-1, 0, 100]) * 53333 + array('b', [-1])
            qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)

            def received(message):
                record['callbacks'].append(time.monotonic_ns())
                if mode == 'failure':
                    raise RuntimeError('NET01E_NON_SIGNAL_CALLBACK_FAILURE')
                if mode == 'fixed':
                    node.send_goal('tb1', (1., 2.), 1)
                elif len(record['callbacks']) == 3:
                    signal.raise_signal(signal.SIGINT)

            sub = node.create_subscription(OccupancyGrid, TOPIC, received, qos, raw=False)
            publisher = node.create_publisher(OccupancyGrid, TOPIC, qos)
            limit = time.monotonic() + 3.
            while publisher.get_subscription_count() != 1:
                if time.monotonic() >= limit:
                    raise TimeoutError('Self-DDS discovery bound')
                rclpy.spin_once(node, timeout_sec=.002)
            node.create_timer(.05, lambda: publisher.publish(grid))
            if mode == 'fixed':
                constructor = OccupancyGrid.__init__.__code__

                def profile(frame, event, arg):
                    if event != 'call' or frame.f_code is not constructor:
                        return
                    cursor = frame.f_back
                    while cursor is not None:
                        if cursor.f_code.co_name == '_take_subscription' and cursor.f_locals.get('sub') is sub:
                            record['hook'] = dict(monotonic_ns=time.monotonic_ns(),
                                constructor_file=frame.f_code.co_filename,
                                exact_constructor_code=True, take_file=cursor.f_code.co_filename,
                                take_line=cursor.f_lineno, topic=sub.topic_name, raw=sub.raw)
                            sys.setprofile(None)
                            record['hook']['signal_request_monotonic_ns'] = time.monotonic_ns()
                            signal.raise_signal(signal.SIGINT)
                            record['hook']['signal_return_monotonic_ns'] = time.monotonic_ns()
                            return
                        cursor = cursor.f_back
                sys.setprofile(profile)
        save(directory / 'ready.json', dict(pid=os.getpid(), mode=mode, monotonic_ns=time.monotonic_ns()))
        try:
            make_graceful_spin(directory)(node)
        except BaseException as error:
            primary = error
            observe_exception(directory, 'exception.json', error)
            raise
        record['context_ok_after_spin'] = rclpy.ok()
        if mode == 'fixed' and (len(record['callbacks']) != 1 or record['original_submit_calls'] or 'hook' not in record):
            raise RuntimeError('Fixed constructor/gate evidence mismatch')
        if mode == 'normal' and len(record['callbacks']) != 3:
            raise RuntimeError('Normal DDS callback evidence mismatch')
    finally:
        sys.setprofile(None)
        record['destroy_begin_monotonic_ns'] = time.monotonic_ns()
        try:
            node.destroy_node()
            record['destroy_end_monotonic_ns'] = time.monotonic_ns()
            rclpy.shutdown()
            record['context_ok_after_shutdown'] = rclpy.ok()
        except BaseException as error:
            observe_exception(directory, 'cleanup-error.json', error)
            if primary is None:
                raise
        finally:
            save(directory / 'lifecycle.json', record)


def action_child(directory):
    rclpy, Node, SignalHandlerOptions = ros_types()
    from rclpy.action import ActionClient
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_action_status_default
    from action_msgs.msg import GoalStatusArray
    from nav2_msgs.action import NavigateToPose
    from nav2_msgs.action._navigate_to_pose import NavigateToPose_GetResult
    from unique_identifier_msgs.msg import UUID
    from check_action_wire import ControlledServer
    from ros_policy import CheckpointHeadquarters
    from ros_headquarters import close_controller

    rclpy.init(domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
    server_context = Context()
    rclpy.init(context=server_context, domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
    server_node = Node('net01e_cancel_server', context=server_context)
    server = ControlledServer(server_node, 1)
    server_executor = SingleThreadedExecutor(context=server_context)
    server_executor.add_node(server_node)
    record = dict(pid=os.getpid(), events=[], status=[], original_submit_calls=[],
        scope='Real DDS controlled Action; original halt/close, fixture allocator/ledger; no Policy/Nav2/motion')

    class ControllerNode(Node):
        halt = CheckpointHeadquarters.halt

        def now(self):
            return time.monotonic()

        def record(self, event):
            record['events'].append(dict(event, observed_monotonic_ns=time.monotonic_ns()))

        def send_goal(self, robot, target, token):
            record['original_submit_calls'].append(dict(robot=robot, token=token))
            raise RuntimeError('Stop gate permitted a new submission')

    node = ControllerNode('net01e_cancel_controller')
    node.lock = threading.RLock()
    node.events = io.StringIO()
    node.goal_handles = {}
    node.allocator = SimpleNamespace(
        tick=lambda stamp: record['events'].append(dict(kind='fixture_allocator_tick', monotonic_ns=time.monotonic_ns())),
        stop=lambda reason: record['events'].append(dict(kind='fixture_allocator_stop', reason=reason, monotonic_ns=time.monotonic_ns())))
    ledger = SimpleNamespace(flush=lambda reason: record['events'].append(dict(kind='fixture_ledger_flush', reason=reason, monotonic_ns=time.monotonic_ns())))
    controller_executor = rclpy.get_global_executor()
    controller_executor.add_node(node)
    client = ActionClient(node, NavigateToPose, '/tb1/navigate_to_pose')
    status_sub = server_node.create_subscription(GoalStatusArray, '/tb1/navigate_to_pose/_action/status',
        lambda message: record['status'].extend(dict(uuid=bytes(s.goal_info.goal_id.uuid).hex(),
            status=s.status, monotonic_ns=time.monotonic_ns()) for s in message.status_list),
        qos_profile_action_status_default)
    witness = server_node.create_client(NavigateToPose_GetResult, '/tb1/navigate_to_pose/_action/get_result')
    closed = False
    deadline = time.monotonic() + 7.

    def until(predicate, controller_alive=True):
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError('7wall accepted-action cancellation bound')
            if controller_alive:
                controller_executor.spin_once(timeout_sec=.002)
            server_executor.spin_once(timeout_sec=.002)

    try:
        until(client.server_is_ready)
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.orientation.w = 1.
        goal_uuid = UUID(uuid=list(bytes.fromhex('0102030405060708090a0b0c0d0e0f10')))
        accepted = client.send_goal_async(goal, goal_uuid=goal_uuid)
        until(accepted.done)
        handle = accepted.result()
        if not handle.accepted:
            raise RuntimeError('Controlled goal was not accepted')
        uuid_hex = bytes(handle.goal_id.uuid).hex()
        until(lambda: uuid_hex in server.executing)
        node.goal_handles['tb1'] = handle
        record.update(accepted_uuid=uuid_hex, accepted_observed_monotonic_ns=time.monotonic_ns())
        request = NavigateToPose_GetResult.Request()
        request.goal_id = goal_uuid
        result_future = witness.call_async(request)

        def callback_stop():
            node.destroy_timer(stop_timer)
            record['callback_enter_monotonic_ns'] = time.monotonic_ns()
            signal.raise_signal(signal.SIGINT)
            node.send_goal('tb1', (1., 2.), 2)
            record['callback_return_monotonic_ns'] = time.monotonic_ns()

        stop_timer = node.create_timer(.01, callback_stop)
        make_graceful_spin(directory)(node)
        record['context_ok_before_original_close'] = rclpy.ok()
        record['original_close_begin_monotonic_ns'] = time.monotonic_ns()
        close_controller(node, ledger)
        closed = True
        record['original_close_end_monotonic_ns'] = time.monotonic_ns()
        record['controller_context_ok_after_close'] = rclpy.ok()
        until(lambda: result_future.done() and any(s['uuid'] == uuid_hex and s['status'] == 5 for s in record['status']), False)
        record.update(server_cancelled=server.cancelled, witness_GetResult_status=result_future.result().status)
        if record['original_submit_calls'] or server.cancelled != [uuid_hex] or result_future.result().status != 5:
            raise RuntimeError('Actual accepted-goal cancellation/gate evidence mismatch')
    except BaseException as error:
        observe_exception(directory, 'exception.json', error)
        raise
    finally:
        if not closed:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        server.close()
        server_executor.shutdown(timeout_sec=0)
        server_node.destroy_node()
        server_context.shutdown()
        record['server_context_ok_after_shutdown'] = server_context.ok()
        save(directory / 'lifecycle.json', record)


def driver(directory, admission):
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / 'ADMISSION-at-run.json', admission)
    (directory / 'source-at-run.py').write_text(Path(__file__).read_text())
    (directory / 'adapter-at-run.py').write_text(Path(__file__).with_name('graceful_spin.py').read_text())
    cases = []
    process = None
    begin = time.monotonic()
    try:
        for mode in ('fixed', 'normal', 'idle', 'failure', 'action'):
            case_dir = directory / mode
            case_dir.mkdir()
            case = dict(mode=mode, expected_exit=1 if mode == 'failure' else 0, signals=[])
            cases.append(case)
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                '--child-directory', str(case_dir), '--mode', mode]
            with (case_dir / 'stdout.txt').open('x') as stdout, (case_dir / 'stderr.txt').open('x') as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
            case.update(pid=process.pid, argv=command)
            if mode == 'idle':
                ready_deadline = time.monotonic() + 5.
                while not (case_dir / 'ready.json').exists():
                    if process.poll() is not None or time.monotonic() >= ready_deadline:
                        raise RuntimeError('Idle child not ready')
                    time.sleep(.005)
                time.sleep(.2)
                event = dict(signal='SIGINT', before_monotonic_ns=time.monotonic_ns())
                os.kill(process.pid, signal.SIGINT)
                event['after_monotonic_ns'] = time.monotonic_ns()
                case['signals'].append(event)
            process.wait(timeout=min(12., max(.01, 55. - (time.monotonic() - begin))))
            case.update(raw_exit=process.returncode, exit_observed_monotonic_ns=time.monotonic_ns())
            if process.returncode != case['expected_exit']:
                raise RuntimeError(mode + ' unexpected actual child exit')
        return 1  # Preserve the actually observed non-SIGINT RuntimeError child1.
    finally:
        if process is not None and process.poll() is None:
            cases[-1]['signals'].append(dict(signal='SIGTERM_FAILURE_CLEANUP', monotonic_ns=time.monotonic_ns()))
            process.terminate()
            try:
                process.wait(timeout=1.)
            except subprocess.TimeoutExpired:
                cases[-1]['signals'].append(dict(signal='SIGKILL_FAILURE_CLEANUP', monotonic_ns=time.monotonic_ns()))
                process.kill()
                process.wait(timeout=1.)
            cases[-1]['final_raw_exit'] = process.returncode
        save(directory / 'result.json', dict(cases=cases, duration_wall_s=time.monotonic() - begin,
            all_expected_raw_exits=len(cases) == 5 and all(c.get('raw_exit') == c['expected_exit'] for c in cases),
            parent_exit_policy='Actual expected non-SIGINT child error1 remains parent1; inspect per-case evidence',
            last_child_gone=process is None or process.poll() is not None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--child-directory', type=Path)
    parser.add_argument('--mode', choices=('fixed', 'normal', 'idle', 'failure', 'action'))
    args = parser.parse_args()
    admission = json.loads(Path(__file__).with_name('GRACEFUL_TEST_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        parser.error('Inert regression: Root source review and unique START required')
    os.environ['ROS_DOMAIN_ID'] = str(DOMAIN)
    if args.child_directory is not None:
        if args.mode == 'action':
            return action_child(args.child_directory)
        return child(args.child_directory, args.mode)
    return driver(args.output, admission)


if __name__ == '__main__':
    raise SystemExit(main())

"""Controlled conversion intervention, never a historical-trigger reproduction."""
import argparse
from array import array
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

from continuous_dds import save, observe_exception

DOMAIN = 97
TOPIC = '/net01e/controller/mechanism_grid'


def receiver(directory, mode):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from nav_msgs.msg import OccupancyGrid

    if signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        raise RuntimeError('Probe requires unchanged Python default SIGINT handler')
    rclpy.init(domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_mechanism_' + mode)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    record = dict(pid=os.getpid(), ppid=os.getppid(), mode=mode,
        original_default_SIGINT=True, signal_handler_options='NO',
        count=0, callbacks=[], hook=None)

    def received(message):
        record['count'] += 1
        record['callbacks'].append(time.monotonic_ns())
        if message.info.width != 400 or message.info.height != 400 or len(message.data) != 160000:
            raise ValueError('Unexpected fixture grid dimensions')

    sub = node.create_subscription(OccupancyGrid, TOPIC, received,
        QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL), raw=False)
    record.update(subscription_created_monotonic_ns=time.monotonic_ns(),
        subscription_identity=id(sub), topic=sub.topic_name,
        msg_type=sub.msg_type.__module__ + '.' + sub.msg_type.__qualname__, raw=sub.raw)
    constructor = OccupancyGrid.__init__.__code__

    def profile(frame, event, arg):
        if event != 'call' or frame.f_code is not constructor:
            return
        cursor = frame.f_back
        frames = []
        take = None
        while cursor is not None:
            frames.append(dict(file=cursor.f_code.co_filename,
                function=cursor.f_code.co_name, line=cursor.f_lineno))
            if cursor.f_code.co_name == '_take_subscription':
                take = cursor.f_locals.get('sub')
            cursor = cursor.f_back
        if take is not sub:
            return  # Do not intervene in setup or another construction.
        record['hook'] = dict(entry_monotonic_ns=time.monotonic_ns(),
            constructor_file=frame.f_code.co_filename, constructor_line=frame.f_code.co_firstlineno,
            constructor_code_identity_match=True, active_take_subscription_identity=id(take),
            topic=take.topic_name, raw=take.raw, frames=frames,
            intervention=mode == 'interrupt', signal_raise_returned=False)
        sys.setprofile(None)  # Exactly one matched entry; identical in control.
        if mode == 'interrupt':
            record['hook']['signal_request_monotonic_ns'] = time.monotonic_ns()
            signal.raise_signal(signal.SIGINT)  # Original default handler, no wrapper.
            record['hook']['signal_raise_returned'] = True

    primary = None
    try:
        sys.setprofile(profile)
        save(directory / 'ready.json', dict(record))
        try:
            while record['count'] < 3:
                executor.spin_once(timeout_sec=.1)
        except BaseException as error:
            primary = error
            observe_exception(directory, 'exception.json', error)
            raise
        if record['hook'] is None:
            raise RuntimeError('No real typed DDS constructor hook observed')
        if mode == 'interrupt':
            raise RuntimeError('Controlled SIGINT failed to interrupt typed receive')
    finally:
        sys.setprofile(None)
        record['destroy_begin_monotonic_ns'] = time.monotonic_ns()
        try:
            executor.shutdown(timeout_sec=0)
            node.destroy_node()
            record['destroy_end_monotonic_ns'] = time.monotonic_ns()
            rclpy.shutdown()
            record['context_ok_after_shutdown'] = rclpy.ok()
        except BaseException as cleanup_error:
            observe_exception(directory, 'cleanup-error.json', cleanup_error)
            if primary is None:
                raise
        finally:
            record['finally_end_monotonic_ns'] = time.monotonic_ns()
            try:
                save(directory / 'lifecycle.json', record)
            except BaseException as record_error:
                print('lifecycle observation failed: ' + repr(record_error), file=sys.stderr)
                if primary is None:
                    raise


def driver(directory, admission):
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rclpy.serialization import serialize_message, deserialize_message
    from rclpy.signals import SignalHandlerOptions
    from nav_msgs.msg import OccupancyGrid

    directory.mkdir(parents=True, exist_ok=False)
    save(directory / 'ADMISSION-at-run.json', admission)
    (directory / 'source-at-run.py').write_text(Path(__file__).read_text())
    (directory / 'observer-dependency-at-run.py').write_text(Path(__file__).with_name('continuous_dds.py').read_text())
    record = dict(pid=os.getpid(), start_monotonic_ns=time.monotonic_ns(),
        scope='Artificial constructor-entry SIGINT; mechanism susceptibility only', cases=[])
    context = Context()
    process = node = executor = None
    primary = None
    start = time.monotonic()

    def outer_stop(number, frame):
        raise InterruptedError('Outer signal ' + str(number))

    signal.signal(signal.SIGTERM, outer_stop)
    try:
        grid = OccupancyGrid()
        grid.header.frame_id = 'odom'
        grid.info.resolution = struct.unpack('<f', struct.pack('<f', .05))[0]
        grid.info.width = grid.info.height = 400
        grid.info.origin.orientation.w = 1.
        grid.data = array('b', [-1, 0, 100]) * 53333 + array('b', [-1])
        encoded = serialize_message(grid)
        if deserialize_message(encoded, OccupancyGrid) != grid:
            raise ValueError('Strict typed CDR roundtrip mismatch')
        record['CDR_bytes'] = len(encoded)
        record['roundtrip_equal'] = True
        rclpy.init(context=context, domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
        node = Node('net01e_mechanism_source', context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        for mode in ('control', 'interrupt'):
            # A fresh writer has no previous control sample in durable history.
            publisher = node.create_publisher(OccupancyGrid, TOPIC,
                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
            case_dir = directory / mode
            case_dir.mkdir()
            case = dict(mode=mode, published=0, signals=[], first_publish_monotonic_ns=None,
                last_publish_monotonic_ns=None, start_monotonic_ns=time.monotonic_ns())
            record['cases'].append(case)
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                '--receiver-directory', str(case_dir), '--mode', mode]
            with (case_dir / 'stdout.txt').open('x') as stdout, (case_dir / 'stderr.txt').open('x') as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
            case.update(pid=process.pid, argv=command)
            save(case_dir / 'launch.json', case)
            case_start = time.monotonic()
            while not (case_dir / 'ready.json').exists() or publisher.get_subscription_count() != 1:
                if process.poll() is not None:
                    raise RuntimeError(mode + ' exited before ready')
                if time.monotonic() - case_start >= 5.:
                    raise TimeoutError(mode + ' 5wall startup bound')
                executor.spin_once(timeout_sec=.002)
            supply_start = time.monotonic()
            next_publish = supply_start
            while process.poll() is None:
                now = time.monotonic()
                if now - start >= 20. or now - supply_start >= 3.:
                    raise TimeoutError(mode + ' real-DDS bounded receive timeout')
                if now >= next_publish and case['published'] < 60:
                    grid.header.stamp = node.get_clock().now().to_msg()
                    publisher.publish(grid)
                    stamp = time.monotonic_ns()
                    case['published'] += 1
                    case['last_publish_monotonic_ns'] = stamp
                    if case['first_publish_monotonic_ns'] is None:
                        case['first_publish_monotonic_ns'] = stamp
                    next_publish = now + .05
                executor.spin_once(timeout_sec=.002)
            case.update(raw_exit=process.returncode, exit_observed_monotonic_ns=time.monotonic_ns())
            error_path = case_dir / 'exception.json'
            case['exception'] = json.loads(error_path.read_text()) if error_path.exists() else None
            case['lifecycle'] = json.loads((case_dir / 'lifecycle.json').read_text())
            if mode == 'control':
                if process.returncode != 0 or case['lifecycle']['count'] != 3 or case['lifecycle']['hook'] is None:
                    raise RuntimeError('Control did not exit0 with three real callbacks and matching hook')
                node.destroy_publisher(publisher)
            else:
                error = case['exception']
                hook = case['lifecycle']['hook']
                matching = (error is not None and error['type'] == 'builtins.RuntimeError'
                    and 'Unable to convert call argument to Python object' in error['repr']
                    and hook is not None and hook['intervention']
                    and 'signal_request_monotonic_ns' in hook
                    and any(sub['topic'] == TOPIC and sub['raw'] is False
                        and sub['msg_type'] == 'nav_msgs.msg._occupancy_grid.OccupancyGrid'
                        for sub in error['subscriptions']))
                record['status'] = 'CONTROLLED_CONVERSION_MECHANISM_OBSERVED' if matching else 'CONTROLLED_MECHANISM_NOT_REPRODUCED'
                if process.returncode == 0:
                    raise RuntimeError('Unexpected clean intervention return')
                return process.returncode if process.returncode >= 0 else 128 - process.returncode
    except BaseException as error:
        primary = error
        record['status'] = 'DIAGNOSTIC_FAILURE'
        observe_exception(directory, 'driver-exception.json', error)
        raise
    finally:
        try:
            if process is not None and process.poll() is None:
                case = record['cases'][-1]
                case['signals'].append(dict(signal='SIGTERM_FAILURE_CLEANUP', monotonic_ns=time.monotonic_ns()))
                process.terminate()
                try:
                    process.wait(timeout=1.)
                except subprocess.TimeoutExpired:
                    case['signals'].append(dict(signal='SIGKILL_FAILURE_CLEANUP', monotonic_ns=time.monotonic_ns()))
                    process.kill()
                    process.wait(timeout=1.)
                case['final_raw_exit'] = process.returncode
            if executor is not None:
                executor.shutdown(timeout_sec=0)
            if node is not None:
                node.destroy_node()
            if context.ok():
                context.shutdown()
        except BaseException as cleanup_error:
            observe_exception(directory, 'driver-cleanup-error.json', cleanup_error)
            if primary is None:
                raise
        finally:
            record.update(end_monotonic_ns=time.monotonic_ns(),
                last_child_gone=process is None or process.poll() is not None,
                parent_context_ok=context.ok())
            try:
                save(directory / 'result.json', record)
            except BaseException as record_error:
                print('result observation failed: ' + repr(record_error), file=sys.stderr)
                if primary is None:
                    raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--receiver-directory', type=Path)
    parser.add_argument('--mode', choices=('control', 'interrupt'))
    args = parser.parse_args()
    admission = json.loads(Path(__file__).with_name('MECHANISM_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        parser.error('Inert controlled intervention: Root review, pin and unique START required')
    os.environ['ROS_DOMAIN_ID'] = str(DOMAIN)
    if args.receiver_directory is not None:
        if args.mode is None:
            parser.error('--mode required for receiver')
        return receiver(args.receiver_directory, args.mode)
    if args.output is None:
        parser.error('--output required for driver')
    return driver(args.output, admission)


if __name__ == '__main__':
    raise SystemExit(main())

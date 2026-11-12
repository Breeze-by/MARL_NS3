"""Inert until Root admits: one real DDS stream, one observed default SIGINT.

No HQ/Policy/robot imports. No private take or generated-type modification.
"""
import argparse
from array import array
import faulthandler
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

DOMAIN = 97
TOPIC = '/net01e/controller/grid'
PERIOD = .05
SIGNAL_AFTER = 12.
EXIT_WAIT = 5.
MAX_PUBLISHES = 340


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    temporary.rename(path)


def error_record(error):
    record = dict(observed_monotonic_ns=time.monotonic_ns(),
        type=type(error).__module__ + '.' + type(error).__qualname__,
        repr=repr(error), cause=repr(error.__cause__), context=repr(error.__context__),
        traceback=''.join(traceback.format_exception(type(error), error, error.__traceback__)),
        subscriptions=[])
    tb = error.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_name == '_take_subscription':
            sub = tb.tb_frame.f_locals.get('sub')
            record['subscriptions'].append(dict(topic=sub.topic_name,
                msg_type=sub.msg_type.__module__ + '.' + sub.msg_type.__qualname__,
                raw=sub.raw, python_identity=id(sub)))
        tb = tb.tb_next
    return record


def observe_exception(directory, name, error):
    # A failed observation must never replace the original exception.
    try:
        save(directory / name, error_record(error))
    except BaseException as observation_error:
        print('exception observation failed: ' + repr(observation_error), file=sys.stderr)


def receiver(directory):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from nav_msgs.msg import OccupancyGrid

    original_handler = signal.getsignal(signal.SIGINT)
    if original_handler is not signal.default_int_handler:
        raise RuntimeError('Receiver requires the original default Python SIGINT handler')
    signal_observations = []

    def observed_sigint(number, frame):
        observation = dict(handler_entry_monotonic_ns=time.monotonic_ns(), frames=[])
        cursor = frame
        while cursor is not None and len(observation['frames']) < 16:
            observation['frames'].append(dict(file=cursor.f_code.co_filename,
                function=cursor.f_code.co_name, line=cursor.f_lineno))
            cursor = cursor.f_back
        signal_observations.append(observation)
        return original_handler(number, frame)

    rclpy.init(domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_continuous_receiver')
    lifecycle = dict(pid=os.getpid(), ppid=os.getppid(), domain=DOMAIN,
        signal_handler='observer immediately delegates to original Python default_int_handler',
        signal_handler_options='NO', raw=False, signal_observations=signal_observations,
        count=0, first_callback_monotonic_ns=None, last_callback_monotonic_ns=None,
        recent_callback_monotonic_ns=[], post_handler_callback_count=0, invalid_message_count=0)

    def received(message):
        stamp = time.monotonic_ns()
        lifecycle['count'] += 1
        lifecycle['last_callback_monotonic_ns'] = stamp
        lifecycle['recent_callback_monotonic_ns'].append(stamp)
        del lifecycle['recent_callback_monotonic_ns'][:-16]
        if signal_observations:
            lifecycle['post_handler_callback_count'] += 1
        if message.info.width != 400 or message.info.height != 400 or len(message.data) != 160000:
            lifecycle['invalid_message_count'] += 1
            raise ValueError('Fixture received unexpected grid dimensions')
        if lifecycle['count'] == 1:
            lifecycle['first_callback_monotonic_ns'] = stamp
            save(directory / 'first-callback.json', dict(monotonic_ns=stamp, pid=os.getpid()))

    sub = node.create_subscription(OccupancyGrid, TOPIC, received,
        QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL), raw=False)
    lifecycle.update(subscription_created_monotonic_ns=time.monotonic_ns(),
        subscription_python_identity=id(sub), topic=sub.topic_name,
        msg_type=sub.msg_type.__module__ + '.' + sub.msg_type.__qualname__)
    signal.signal(signal.SIGINT, observed_sigint)
    faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)
    save(directory / 'receiver-ready.json', dict(lifecycle))
    primary = None
    try:
        try:
            rclpy.spin(node)
        except BaseException as error:
            primary = error
            observe_exception(directory, 'receiver-exception.json', error)
            raise
    finally:
        lifecycle['destroy_begin_monotonic_ns'] = time.monotonic_ns()
        try:
            node.destroy_node()
            lifecycle['destroy_end_monotonic_ns'] = time.monotonic_ns()
            rclpy.shutdown()
            lifecycle['context_ok_after_shutdown'] = rclpy.ok()
        except BaseException as cleanup_error:
            observe_exception(directory, 'receiver-cleanup-error.json', cleanup_error)
            if primary is None:
                raise
        finally:
            lifecycle['finally_end_monotonic_ns'] = time.monotonic_ns()
            try:
                save(directory / 'receiver-lifecycle.json', lifecycle)
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
    begin = time.monotonic()
    record = dict(parent_pid=os.getpid(), parent_ppid=os.getppid(), domain=DOMAIN,
        start_monotonic_ns=time.monotonic_ns(), status='STARTED', published=0,
        pre_signal_published=0, post_signal_published=0, signals=[],
        first_publish_monotonic_ns=None, last_publish_monotonic_ns=None,
        scope='Synthetic real DDS only; no historical payload or root-cause claim')
    context = Context()
    process = node = executor = None
    primary = None

    def outer_stop(number, frame):
        raise InterruptedError('Outer signal ' + str(number))

    signal.signal(signal.SIGTERM, outer_stop)

    def send_owned(number, label):
        event = dict(pid=process.pid, signal=label, before_monotonic_ns=time.monotonic_ns())
        os.kill(process.pid, number)
        event['after_monotonic_ns'] = time.monotonic_ns()
        record['signals'].append(event)
        save(directory / ('signal-' + str(len(record['signals'])) + '.json'), event)

    try:
        grid = OccupancyGrid()
        grid.header.frame_id = 'odom'
        grid.info.resolution = .05
        grid.info.width = grid.info.height = 400
        grid.info.origin.orientation.w = 1.
        grid.data = array('b', [-1, 0, 100]) * 53333 + array('b', [-1])
        encoded = serialize_message(grid)
        if deserialize_message(encoded, OccupancyGrid) != grid:
            raise ValueError('Public typed CDR roundtrip mismatch')
        record['payload'] = dict(width=400, height=400, CDR_bytes=len(encoded),
            exact_data_values=[-1, 0, 100], finite_metadata=True, roundtrip_equal=True,
            period_wall_s=PERIOD, signal_after_wall_s=SIGNAL_AFTER, max_publishes=MAX_PUBLISHES)
        command = [sys.executable, '-B', str(Path(__file__).resolve()),
            '--receiver-directory', str(directory)]
        with (directory / 'receiver.stdout.txt').open('x') as stdout, (directory / 'receiver.stderr.txt').open('x') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        record.update(receiver_pid=process.pid, receiver_argv=command)
        save(directory / 'launch.json', record)
        rclpy.init(context=context, domain_id=DOMAIN, signal_handler_options=SignalHandlerOptions.NO)
        node = Node('net01e_continuous_source', context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        publisher = node.create_publisher(OccupancyGrid, TOPIC,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        while not (directory / 'receiver-ready.json').exists() or publisher.get_subscription_count() != 1:
            if process.poll() is not None:
                raise RuntimeError('Receiver exited before matched DDS startup')
            if time.monotonic() - begin >= 8.:
                raise TimeoutError('8wall startup bound')
            executor.spin_once(timeout_sec=.002)
        record['receiver_ready'] = json.loads((directory / 'receiver-ready.json').read_text())
        source_start = time.monotonic()
        next_publish = source_start
        signal_time = None
        while process.poll() is None:
            now = time.monotonic()
            if now - begin >= 27.:
                raise TimeoutError('27wall inner bound')
            if signal_time is None and now - source_start >= SIGNAL_AFTER:
                if not (directory / 'first-callback.json').exists():
                    raise RuntimeError('No actual callback before scheduled SIGINT; no signal sent')
                send_owned(signal.SIGINT, 'SIGINT')
                signal_time = time.monotonic()
            if signal_time is not None and now - signal_time >= EXIT_WAIT:
                record['status'] = 'TIMEOUT_INCONCLUSIVE'
                send_owned(signal.SIGUSR1, 'SIGUSR1_STACK_DIAGNOSTIC')
                # One bounded stack-observation interval, no new SIGINT.
                try:
                    process.wait(timeout=.05)
                except subprocess.TimeoutExpired:
                    pass
                raise TimeoutError('5wall after SIGINT; DDS supplied continuously')
            if now >= next_publish and record['published'] < MAX_PUBLISHES:
                grid.header.stamp = node.get_clock().now().to_msg()
                publisher.publish(grid)
                stamp = time.monotonic_ns()
                record['published'] += 1
                record['pre_signal_published' if signal_time is None else 'post_signal_published'] += 1
                if record['first_publish_monotonic_ns'] is None:
                    record['first_publish_monotonic_ns'] = stamp
                record['last_publish_monotonic_ns'] = stamp
                next_publish = now + PERIOD  # Never catch-up burst.
            executor.spin_once(timeout_sec=.002)
        record['receiver_exit_observed_monotonic_ns'] = time.monotonic_ns()
        record['receiver_raw_exit'] = process.returncode
        error_path = directory / 'receiver-exception.json'
        error = json.loads(error_path.read_text()) if error_path.exists() else None
        record['exception'] = error
        if signal_time is None:
            record['status'] = 'PRE_SIGNAL_EXIT_DIAGNOSTIC_FAILURE'
            if process.returncode == 0:
                raise RuntimeError('Unexpected clean exit before scheduled SIGINT')
        elif error and error['type'] == 'builtins.RuntimeError' and 'Unable to convert call argument to Python object' in error['repr']:
            record['status'] = 'MATCHING_RUNTIMEERROR_OBSERVED'
        elif error and error['type'] == 'builtins.KeyboardInterrupt':
            record['status'] = 'NOT_REPRODUCED_ONE_OBSERVED_SIGINT'
        else:
            record['status'] = 'OTHER_EXIT_DIAGNOSTIC_FAILURE'
            if process.returncode == 0:
                raise RuntimeError('Unexpected clean receiver exit')
        return process.returncode if process.returncode >= 0 else 128 - process.returncode
    except BaseException as error:
        primary = error
        observe_exception(directory, 'driver-exception.json', error)
        if record['status'] != 'TIMEOUT_INCONCLUSIVE':
            record['status'] = 'DIAGNOSTIC_FAILURE'
        raise
    finally:
        try:
            if process is not None and process.poll() is None:
                send_owned(signal.SIGTERM, 'SIGTERM_OWNED_FAILURE_CLEANUP')
                try:
                    process.wait(timeout=1.)
                except subprocess.TimeoutExpired:
                    send_owned(signal.SIGKILL, 'SIGKILL_OWNED_FAILURE_CLEANUP')
                    process.wait(timeout=1.)
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
                receiver_final_raw_exit=None if process is None else process.poll(),
                receiver_gone=process is None or process.poll() is not None,
                parent_context_ok=context.ok())
            try:
                save(directory / 'result.json', record)
            except BaseException as record_error:
                print('driver final observation failed: ' + repr(record_error), file=sys.stderr)
                if primary is None:
                    raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--receiver-directory', type=Path)
    args = parser.parse_args()
    admission = json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        parser.error('Inert: reviewed source, Root pin and unique START required')
    os.environ['ROS_DOMAIN_ID'] = str(DOMAIN)
    if args.receiver_directory is not None:
        return receiver(args.receiver_directory)
    if args.output is None:
        parser.error('--output is required for driver')
    return driver(args.output, admission)


if __name__ == '__main__':
    raise SystemExit(main())

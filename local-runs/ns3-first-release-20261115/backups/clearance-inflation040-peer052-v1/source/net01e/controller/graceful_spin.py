"""External ROS executor exit adapter; no ROS work or signal change on import."""
import json
import os
from pathlib import Path
import signal
import sys
import time


def make_graceful_spin(directory):
    def spin(node, executor=None):
        import rclpy

        executor = rclpy.get_global_executor() if executor is None else executor
        original_submit = node.send_goal
        original_handler = signal.getsignal(signal.SIGINT)
        state = dict(pid=os.getpid(), spin_begin_monotonic_ns=time.monotonic_ns(),
            idle_wait_limit_wall_s=.05, stop_requested=False, signal_requests=[], submissions=[],
            semantics='Gate admission is entry to original send_goal, not DDS send or Nav2 acceptance')

        def request_stop(number, frame):
            state['stop_requested'] = True
            state['signal_requests'].append(dict(signal=number, handler_monotonic_ns=time.monotonic_ns(),
                interrupted_file=frame.f_code.co_filename, interrupted_function=frame.f_code.co_name,
                interrupted_line=frame.f_lineno))

        def submit(robot, target, token):
            # One gate only. A call already through this read is in-flight;
            # no claim that its actual DDS send/acceptance has happened yet.
            stopped_at_gate = state['stop_requested']
            event = dict(robot=robot, token=token, target=list(target),
                entry_observed_monotonic_ns=time.monotonic_ns(), admitted=not stopped_at_gate)
            state['submissions'].append(event)
            if stopped_at_gate:
                event['outcome'] = 'NOT_SUBMITTED_STOP_REQUESTED'
                node.record(dict(kind='controller_stop_goal_not_submitted', robot=robot,
                    token=token, target=target, sim=node.now(),
                    reason='SIGINT received before external submission gate',
                    actual_DDS_goal_sent=False, synthetic_Action_response=False))
                return
            try:
                return original_submit(robot, target, token)
            finally:
                event['original_send_goal_return_or_unwind_monotonic_ns'] = time.monotonic_ns()

        primary = None
        node.send_goal = submit
        executor.add_node(node)
        signal.signal(signal.SIGINT, request_stop)
        try:
            while executor.context.ok() and not state['stop_requested']:
                executor.spin_once(timeout_sec=.05)
            state['spin_boundary_exit_monotonic_ns'] = time.monotonic_ns()
            state['context_ok_at_boundary'] = executor.context.ok()
        except BaseException as error:
            primary = error
            state['exception_type'] = type(error).__module__ + '.' + type(error).__qualname__
            state['exception_observed_monotonic_ns'] = time.monotonic_ns()
            raise  # Real conversion/callback errors retain their actual failure.
        finally:
            signal.signal(signal.SIGINT, original_handler)
            node.send_goal = original_submit
            executor.remove_node(node)
            state['spin_adapter_finished_monotonic_ns'] = time.monotonic_ns()
            try:
                with (Path(directory) / 'graceful-spin.json').open('x') as stream:
                    json.dump(state, stream, indent=2)
                    stream.write('\n')
            except BaseException as observation_error:
                print('graceful spin observation failed: ' + repr(observation_error), file=sys.stderr)
                if primary is None:
                    raise
    return spin

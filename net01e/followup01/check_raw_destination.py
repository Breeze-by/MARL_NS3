"""One bounded real-DDS semantic qualification, with explicit negative children."""
import argparse
from array import array
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / 'net01'), str(REPO / 'net01e/controller')]
from continuous_dds import save, observe_exception


def source_equivalence():
    def method(path, class_name):
        tree = ast.parse(path.read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'receive')
    original = method(REPO / 'net01/topic_wire.py', 'TopicWire')
    candidate = method(HERE / 'raw_destination_wire.py', 'RawDestinationTopicWire')
    calls = [node for node in ast.walk(original) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'publish']
    if len(calls) != 1 or ast.dump(calls[0].args[0]) != "Name(id='message', ctx=Load())":
        raise AssertionError('Original receive publish boundary changed')
    calls[0].args[0] = ast.Name(id='cdr', ctx=ast.Load())
    if ast.dump(original, include_attributes=False) != ast.dump(candidate, include_attributes=False):
        raise AssertionError('Candidate differs beyond destination publish argument')


def payloads():
    import struct
    from geometry_msgs.msg import TransformStamped, Twist
    from nav_msgs.msg import OccupancyGrid, Odometry
    from nav2_msgs.msg import CostmapFilterInfo
    from std_msgs.msg import String
    from tf2_msgs.msg import TFMessage
    grid = OccupancyGrid()
    grid.header.frame_id = 'map'; grid.header.stamp.sec = 42; grid.header.stamp.nanosec = 123456789
    grid.info.width = grid.info.height = 400
    grid.info.resolution = struct.unpack('<f', struct.pack('<f', .05))[0]
    grid.info.origin.position.x = -.125; grid.info.origin.orientation.w = 1.
    grid.data = array('b', [-1, 0, 100]) * 53333 + array('b', [-1])
    odom = Odometry(); odom.header = grid.header; odom.child_frame_id = 'base_footprint'
    odom.pose.pose.position.x = .125; odom.pose.pose.position.y = -.25
    odom.pose.pose.orientation.w = 1.; odom.twist.twist.linear.x = .5
    odom.pose.covariance = [.25] * 36; odom.twist.covariance = [.5] * 36
    transform = TransformStamped(); transform.header = grid.header; transform.child_frame_id = 'odom'
    transform.transform.translation.x = .125; transform.transform.rotation.w = 1.
    tf = TFMessage(transforms=[transform])
    twist = Twist(); twist.linear.x = .125; twist.angular.z = -.5
    text = String(data='{"sequence":7,"ready":true,"note":"真实CDR"}')
    info = CostmapFilterInfo(); info.type = 0; info.base = 0.; info.multiplier = 1.
    info.filter_mask_topic = '/tb1/peer_keepout_mask'
    return {21: grid, 22: odom, 23: tf, 26: twist, 31: text, 32: info}


def positive(directory):
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    from rclpy.serialization import serialize_message, deserialize_message
    from topic_wire import TopicWire, flows, qos, tf_headers
    from raw_destination_wire import RawDestinationTopicWire
    source_equivalence()
    cases = []
    for name, implementation in (('original', TopicWire), ('raw_destination', RawDestinationTopicWire)):
        context = Context(); rclpy.init(context=context, domain_id=97, signal_handler_options=SignalHandlerOptions.NO)
        nodes = [Node('net01e_raw_' + name + '_' + label, context=context) for label in ('C', 'R', 'sink')]
        executor = SingleThreadedExecutor(context=context)
        for node in nodes: executor.add_node(node)
        wire_c, wire_r, sink = nodes
        wires = {side: implementation(node, side, lambda *args: None, bound_masks=True, runtime=True)
                 for side, node in (('C', wire_c), ('R', wire_r))}
        typed = {}; raw = {}; specifications = flows(runtime=True)
        messages = payloads(); case = dict(implementation=name, messages=[], rejected=[])
        cases.append(case)
        try:
            for flow, message in messages.items():
                spec = specifications[flow]; topic = spec.get('received_topic', spec['topic'])
                typed[flow] = []; raw[flow] = []
                sink.create_subscription(spec['cls'], topic,
                    lambda msg, f=flow: typed[f].append(msg), qos(spec))
                sink.create_subscription(spec['cls'], topic,
                    lambda msg, f=flow: raw[f].append(msg), qos(spec), raw=True)
            deadline = time.monotonic() + 7.
            def until(predicate):
                while not predicate():
                    if time.monotonic() >= deadline: raise TimeoutError('7wall real DDS sink bound')
                    executor.spin_once(timeout_sec=.002)
            # The opposite TopicWire has one source reader (three on the
            # common health topic), in addition to both actual test sinks.
            until(lambda: all(wires['C' if flow < 30 else 'R'].publishers[flow].get_subscription_count() >= (5 if flow == 31 else 3)
                              for flow in messages))
            for flow, message in messages.items():
                body = serialize_message(message)
                if deserialize_message(body, type(message)) != message:
                    raise AssertionError('Fixture strict typed roundtrip failed')
                side = 'C' if flow < 30 else 'R'
                sender, receiver = (1, 0) if side == 'C' else (0, 1)
                wires[side].receive(dict(flow=flow, sender=sender, receiver=receiver), body, 0)
                until(lambda: bool(typed[flow]) and bool(raw[flow]))
                typed_equal = typed[flow][0] == message
                wire_equal = raw[flow][0] == body
                if not typed_equal or deserialize_message(raw[flow][0], type(message)) != message:
                    raise AssertionError('Actual typed/raw sink semantic mismatch')
                if name == 'raw_destination' and not wire_equal:
                    raise AssertionError('Raw destination changed original CDR bytes')
                row = wires[side].delivered[-1]
                if row['cdr_sha256'] != hashlib.sha256(body).hexdigest() or not row['publisher_returned']:
                    raise AssertionError('Original delivered identity metadata mismatch')
                if flow == 23 and row['tf_edges'] != tf_headers(message):
                    raise AssertionError('Original TF metadata mismatch')
                case['messages'].append(dict(flow=flow, type=type(message).__module__ + '.' + type(message).__name__,
                    bytes=len(body), typed_semantics_equal=typed_equal, received_raw_CDR_exact=wire_equal,
                    raw_CDR_hash=hashlib.sha256(raw[flow][0]).hexdigest()))
            body = serialize_message(messages[21]); wire = wires['C']
            for label, meta, rpc, expected in (
                ('wrong_route', dict(flow=21, sender=2, receiver=0), 0, ValueError),
                ('nonzero_rpc', dict(flow=21, sender=1, receiver=0), 1, ValueError),
                ('unknown_flow', dict(flow=999, sender=1, receiver=0), 0, KeyError)):
                before = len(wire.delivered)
                try: wire.receive(meta, body, rpc)
                except expected as error:
                    case['rejected'].append(dict(case=label, type=type(error).__name__, repr=repr(error)))
                else: raise AssertionError(label + ' was not rejected')
                if len(wire.delivered) != before: raise AssertionError('Invalid route appended delivery')
        finally:
            executor.shutdown(timeout_sec=0)
            for node in nodes: node.destroy_node()
            context.shutdown()
            case['context_ok_after_shutdown'] = context.ok()
            save(directory / (name + '.json'), case)
    save(directory / 'positive.json', dict(source_one_argument_equivalence=True, cases=cases))


def negative(directory, raw):
    import rclpy
    from rclpy.context import Context
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    from topic_wire import TopicWire
    from raw_destination_wire import RawDestinationTopicWire
    context = Context(); rclpy.init(context=context, domain_id=97, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_invalid_cdr_' + ('raw' if raw else 'typed'), context=context)
    implementation = RawDestinationTopicWire if raw else TopicWire
    wire = implementation(node, 'C', lambda *args: None, bound_masks=True, runtime=True)
    try:
        try: wire.receive(dict(flow=21, sender=1, receiver=0), b'\x00', 0)
        except BaseException as error:
            observe_exception(directory, 'exception.json', error)
            raise
        raise AssertionError('Malformed CDR was accepted')
    finally:
        count = len(wire.delivered)
        node.destroy_node(); context.shutdown()
        save(directory / 'negative.json', dict(actual_delivered=count, context_ok=context.ok(),
            scope='Real malformed CDR conversion error must escape before publication'))


def driver(directory, admission):
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / 'ADMISSION-at-run.json', admission)
    (directory / 'source-at-run.py').write_text(Path(__file__).read_text())
    (directory / 'candidate-at-run.py').write_text((HERE / 'raw_destination_wire.py').read_text())
    cases = []; process = None; begin = time.monotonic(); passed = False
    try:
        for mode in ('positive', 'original_bad_cdr', 'raw_bad_cdr'):
            child_dir = directory / mode; child_dir.mkdir()
            case = dict(mode=mode, expected_exit=0 if mode == 'positive' else 1, cleanup_signals=[])
            cases.append(case)
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--child-directory', str(child_dir), '--mode', mode]
            with (child_dir / 'stdout.txt').open('x') as out, (child_dir / 'stderr.txt').open('x') as err:
                process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
            case.update(pid=process.pid, argv=command)
            process.wait(timeout=min(18., max(.01, 30. - (time.monotonic() - begin))))
            case['raw_exit'] = process.returncode
            if process.returncode != case['expected_exit']: raise AssertionError(mode + ' unexpected actual exit')
            if mode != 'positive':
                case['exception'] = json.loads((child_dir / 'exception.json').read_text())
                case['negative'] = json.loads((child_dir / 'negative.json').read_text())
                if case['negative']['actual_delivered'] != 0: raise AssertionError('Malformed CDR published')
        if cases[1]['exception']['type'] != cases[2]['exception']['type']:
            raise AssertionError('Candidate changed original malformed-CDR exception type')
        passed = True
        return 0  # Unit qualification: expected actual negative exits stay recorded.
    finally:
        if process is not None and process.poll() is None:
            cases[-1]['cleanup_signals'].append('SIGTERM'); process.terminate()
            try: process.wait(timeout=1.)
            except subprocess.TimeoutExpired:
                cases[-1]['cleanup_signals'].append('SIGKILL'); process.kill(); process.wait(timeout=1.)
            cases[-1]['final_raw_exit'] = process.returncode
        save(directory / 'result.json', dict(passed=passed, cases=cases, duration_wall_s=time.monotonic() - begin,
            last_child_gone=process is None or process.poll() is not None,
            scope='Original/candidate real DDS semantics and bytes plus explicit negative tests, not capacity or production acceptance'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--child-directory', type=Path)
    parser.add_argument('--mode', choices=('positive', 'original_bad_cdr', 'raw_bad_cdr'))
    args = parser.parse_args()
    admission = json.loads((HERE / 'RAW_DESTINATION_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        parser.error('Inert qualification: Root source review, pin and unique START required')
    os.environ['ROS_DOMAIN_ID'] = '97'
    if args.child_directory is not None:
        if args.mode == 'positive': return positive(args.child_directory)
        return negative(args.child_directory, args.mode == 'raw_bad_cdr')
    return driver(args.output, admission)


if __name__ == '__main__':
    raise SystemExit(main())

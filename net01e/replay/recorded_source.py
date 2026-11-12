"""Publish only frozen original R observation CDR and original C89, no motion backend.

Historical feedback/status/health/filter records remain inventory-only here:
active Action/BoundPeer components own those sources in the new collection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.signals import SignalHandlerOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    from std_msgs.msg import String
    from topic_wire import flows, qos

    manifest = json.loads((args.corpus / 'manifest.json').read_text())
    if manifest['status'] != 'EXTRACTED_NEEDS_TYPED_CORPUS_ADMISSION':
        raise ValueError('Source corpus is not the admitted finite extracted corpus')
    rows = [json.loads(line) for line in (args.corpus / 'records.jsonl').read_text().splitlines()]
    selected = [dict(row, state='PLANNED') for row in rows
                if row.get('flow') == 89 or (row.get('flow') is not None
                                            and row['flow'] < 80 and 1 <= row['flow'] % 20 <= 6)]
    prelude = [row for row in selected if row['phase'] == 'prelude']
    normal = sorted((row for row in selected if row['phase'] == 'normal'),
                    key=lambda row: (row['original_record_ns'],
                                     1 if row['flow'] == 89 else 0, row['source_record_id']))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'planned-inputs.json').write_text(json.dumps(selected, indent=2) + '\n')
    bodies = (args.corpus / 'bodies.bin').read_bytes()
    contexts = []; nodes = []; executors = []
    for domain, side in ((92, 'R'), (91, 'C')):
        context = Context()
        rclpy.init(context=context, domain_id=domain, signal_handler_options=SignalHandlerOptions.NO)
        node = Node('net01e_original_source_' + side.lower(), context=context,
                    parameter_overrides=[Parameter('use_sim_time', value=True)])
        executor = SingleThreadedExecutor(context=context); executor.add_node(node)
        contexts.append(context); nodes.append(node); executors.append(executor)
    robot_node, central_node = nodes
    specifications = flows(runtime=True)
    publishers = {}
    for flow in sorted({row['flow'] for row in selected}):
        spec = specifications[flow]
        node = central_node if flow == 89 else robot_node
        publishers[flow] = node.create_publisher(get_message(next(row['type'] for row in selected
                                                                 if row['flow'] == flow)),
                                                spec['topic'], qos(spec))
    status = None
    def state(message):
        nonlocal status
        status = json.loads(message.data)
    robot_node.create_subscription(String, '/net01/gateway_state', state, 1)
    begin = time.monotonic(); index = 0; prelude_done = False; error = None
    def emit(row):
        body = bodies[row['body_offset']:row['body_offset'] + row['body_bytes']]
        row.update(before_monotonic_ns=time.monotonic_ns(),
                   cdr_sha256=hashlib.sha256(body).hexdigest(),
                   before_thread_cpu_ns=time.thread_time_ns(),
                   source_publish_sim_ns=robot_node.get_clock().now().nanoseconds)
        publishers[row['flow']].publish(body)
        row.update(state='PUBLISHED', after_monotonic_ns=time.monotonic_ns(),
                   after_thread_cpu_ns=time.thread_time_ns())
    try:
        decoded = 0
        for row in selected:
            message = deserialize_message(bodies[row['body_offset']:row['body_offset'] + row['body_bytes']],
                                          specifications[row['flow']]['cls'])
            header = getattr(message, 'header', None)
            if header is not None:
                row['original_source_stamp_ns'] = header.stamp.sec * 1_000_000_000 + header.stamp.nanosec
                row['original_source_stamp_available'] = True
            else:
                row['original_source_stamp_available'] = False
            if hasattr(message, 'transforms'):
                row['original_tf_edges'] = [dict(frame_id=t.header.frame_id, child_frame_id=t.child_frame_id,
                    source_stamp_ns=t.header.stamp.sec * 1_000_000_000 + t.header.stamp.nanosec)
                    for t in message.transforms]
            row['typed_decode_returned'] = True; decoded += 1
        (args.output / 'typed-corpus.json').write_text(json.dumps(dict(decoded=decoded,
            bytes_preserved=True, header_rewritten=False, stage='startup before READY/clock/source publication')) + '\n')
        print('RECORDED_SOURCE_READY', flush=True)
        while not args.stop_file.exists():
            if time.monotonic() - begin > 60:
                raise TimeoutError('recorded source 60wall hard bound')
            for executor in executors:
                executor.spin_once(timeout_sec=0)
            if status and status['connected'] and status['anchor'] is not None:
                if not prelude_done:
                    for row in prelude:
                        emit(row)
                    prelude_done = True
                now = robot_node.get_clock().now().nanoseconds
                while index < len(normal) and normal[index]['original_record_ns'] <= now:
                    emit(normal[index]); index += 1
                if index == len(normal) and not (args.output / 'NORMAL_INPUTS_PUBLISHED.json').exists():
                    (args.output / 'NORMAL_INPUTS_PUBLISHED.json').write_text(json.dumps(
                        dict(sim_ns=now, monotonic_ns=time.monotonic_ns(), normal_records=len(normal))))
            time.sleep(.0005)
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        (args.output / 'result.json').write_text(json.dumps(dict(error=error, inputs=selected,
            scope='Original body bytes unchanged; source publish is newly executed ROS business. '
                  'PLANNED includes every selected input even when no publication occurred.',
            historical_feedback_status_injected=False, physical_motion_backend=False), indent=2) + '\n')
        for executor, node, context in zip(executors, nodes, contexts):
            executor.shutdown(); node.destroy_node(); rclpy.shutdown(context=context)


if __name__ == '__main__':
    main()

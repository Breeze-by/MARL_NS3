"""Narrow passive-trace qualification: no HQ checkpoint, Gazebo or Nav2."""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace as NS

from consumer_trace import ConsumerTrace, metadata_executor


def cache_checks(directory):
    node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=25_000_000_000)),
        local_maps={}, navigation_costmaps={}, tf={}, request_uuids={})
    trace = ConsumerTrace(node, directory)
    node._consumer_trace = trace
    robot = NS(pose=None, stamp=None, velocity=None)
    observation = dict(decision_id=1, map=dict(version=3))
    counts = dict(update_robot=0, update_map=0, observation=0, select=0, callback=0, lookup=0)
    def update_robot(name, pose, stamp, velocity):
        counts['update_robot'] += 1
        robot.pose, robot.stamp, robot.velocity = pose, stamp, velocity
    def update_map():
        counts['update_map'] += 1
    def get_observation():
        counts['observation'] += 1
        return observation
    node.allocator = NS(update_robot=update_robot, update_map=update_map,
        get_observation=get_observation, accepted=lambda *a: True, finish=lambda *a: False,
        robots={'tb1': robot})
    value = NS(header=NS(frame_id='merge_map', stamp=NS(sec=24, nanosec=7)),
        child_frame_id='odom', transform=NS(translation=NS(x=1., y=2., z=0.),
                                          rotation=NS(x=0., y=0., z=0., w=1.)))
    def lookup(*args):
        counts['lookup'] += 1
        return value
    node.tf['tb1'] = NS(lookup_transform=lookup)
    inference = dict(kind='rl_real_inference', decision_id=1, input_npz='ORIGINAL/0001.npz',
        observed_state_and_candidates={'candidates': ['ORIGINAL_CANDIDATE']}, choices=[1, 2, 3])
    def select(obs):
        counts['select'] += 1
        assert obs is copied_observation
        trace.observe_record(inference)
        return 'ORIGINAL_ACTION'
    node.policy = NS(select=select)
    trace.install_state_observers()
    original_message = NS(header=NS(stamp=NS(sec=24, nanosec=7), frame_id='odom'))
    good = True
    def callback(message):
        counts['callback'] += 1
        assert message is original_message
        if good:
            node.allocator.update_robot('tb1', (1., 2., 0.), 24., (.1, 0., 0.))
        # Deliberately same None return as the real HQ, including TF failure.
    receive = trace.callback('/tb1/odom', callback)
    receive(original_message)
    valid = trace.sources['pose:tb1']
    good = False
    receive(original_message)
    assert trace.sources['pose:tb1'] == valid
    assert [row['valid_pose_applied'] for row in trace.rows if row['kind'] == 'hq_input_callback'] == [True, False]
    assert node.tf['tb1'].lookup_transform('merge_map', 'odom', NS(nanoseconds=24_000_000_007)) is value
    assert node.allocator.get_observation() is observation
    copied_observation = dict(observation, joint_assignment_rule='maximum-participation-v1')
    assert node.policy.select(copied_observation) == 'ORIGINAL_ACTION'
    assert trace.first_inference is inference and trace.first_inference['input_npz'] == 'ORIGINAL/0001.npz'
    build = next(row for row in trace.rows if row['kind'] == 'hq_observation_build')
    use = next(row for row in trace.rows if row['kind'] == 'hq_policy_use')
    assert use['observation_event_id'] == build['event_id']
    assert counts == dict(update_robot=1, update_map=0, observation=1, select=1, callback=2, lookup=1)
    assert not list(directory.iterdir()), 'Trace wrote during execution'
    trace.flush()
    return dict(passed=True, original_message_identity=True, callback_once_per_delivery=True,
        failed_odom_did_not_refresh_pose_source=True, lookup_original_object=True,
        observation_and_joint_copy_unchanged=True, original_select_once=True,
        original_npz_only=True, ram_until_flush=True, counts=counts)


def dds_checks(directory):
    import rclpy
    from rclpy.context import Context
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.serialization import serialize_message
    from rclpy.signals import SignalHandlerOptions
    from rosgraph_msgs.msg import Clock
    from builtin_interfaces.msg import Time
    from std_msgs.msg import String
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'net01e/followup01'))
    from consumer_topic_wire import ConsumerTraceTopicWire

    context = Context()
    rclpy.init(context=context, domain_id=97, signal_handler_options=SignalHandlerOptions.NO)
    source = Node('consumer_trace_source', context=context,
        parameter_overrides=[Parameter('use_sim_time', value=True)])
    sink = Node('consumer_trace_sink', context=context,
        parameter_overrides=[Parameter('use_sim_time', value=True)])
    clock_publisher = source.create_publisher(Clock, '/clock', 10)
    sink._consumer_trace = ConsumerTrace(sink, directory)
    trace = sink._consumer_trace
    wire = ConsumerTraceTopicWire(source, 'R', lambda *args: None, bound_masks=True, runtime=True)
    executor = metadata_executor(sink)
    original_take = executor._take_subscription
    take_calls = []
    def counted_take(sub):
        result = original_take(sub)
        if result is not None and sub.topic_name == '/peer_keepout_state':
            take_calls.append((sub.raw, id(result)))
        return result
    executor._take_subscription = counted_take
    received = []
    def callback(message):
        received.append((id(message), message.data))
    subscription = sink.create_subscription(String, '/peer_keepout_state',
        trace.callback('/peer_keepout_state', callback), 10)
    # This component uses String health-shaped input but has no real HQ parser.
    sink.peer_keepout_state = dict(sequence=7, generated_sim=24.5)
    raw = []
    raw_subscription = sink.create_subscription(String, '/peer_keepout_state', raw.append, 10, raw=True)
    executor.add_node(sink)
    executor.add_node(source)
    body = serialize_message(String(data='{"sequence":7,"generated_sim":24.5}'))
    deadline = time.monotonic() + 5
    try:
        while wire.publishers[31].get_subscription_count() < 2 or clock_publisher.get_subscription_count() < 2:
            if time.monotonic() > deadline:
                raise TimeoutError('Component DDS discovery')
            executor.spin_once(timeout_sec=.01)
        clock_publisher.publish(Clock(clock=Time(sec=25)))
        while sink.get_clock().now().nanoseconds != 25_000_000_000 or source.get_clock().now().nanoseconds != 25_000_000_000:
            if time.monotonic() > deadline:
                raise TimeoutError('Component simulated clock receipt')
            executor.spin_once(timeout_sec=.01)
        for number in (1, 2):
            # Identical complete CDR bodies are distinct publications by real
            # measured metadata/seq, not by pretending their digest is unique.
            wire.receive(dict(flow=31, sender=0, receiver=1, message_id=number), body, 0)
            while len(received) < number or len(raw) < number:
                if time.monotonic() > deadline:
                    raise TimeoutError('Component DDS receipt')
                executor.spin_once(timeout_sec=.01)
        typed_takes = [row for row in trace.rows if row['kind'] == 'hq_native_take' and not row['raw']]
        callbacks = [row for row in trace.rows if row['kind'] == 'hq_input_callback']
        assert len(typed_takes) == len(callbacks) == len(received) == 2
        assert all(row['metadata']['source_timestamp'] > 0 and row['metadata']['received_timestamp'] > 0
                   for row in typed_takes)
        assert all(row['before']['sim_ns'] == row['after']['sim_ns'] == 25_000_000_000 for row in typed_takes)
        assert all(row['begin']['sim_ns'] == row['end']['sim_ns'] == 25_000_000_000 for row in callbacks)
        assert [identity for identity, data in received] == [identity for raw_take, identity in take_calls if not raw_take]
        assert raw == [body, body], 'Full original raw CDR changed'
        assert [row['gateway_publication_seq'] for row in wire.delivered] == [1, 2]
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from analyze_consumer_trace import publication_candidates
        matches = [publication_candidates(row, wire.delivered) for row in typed_takes]
        assert [match['status'] for match in matches] == ['UNIQUE_OBSERVED_PUBLICATION_CANDIDATE'] * 2
        ambiguous = publication_candidates(typed_takes[0], [wire.delivered[0], dict(wire.delivered[0])])
        assert ambiguous['status'] == 'AMBIGUOUS_MULTIPLE_PUBLICATION_CANDIDATES'
        unknown = publication_candidates(typed_takes[0], [])
        assert unknown['status'] == 'UNKNOWN_NO_PUBLICATION_CANDIDATE'
        assert not list(directory.iterdir()), 'Trace persisted while spinning'
        trace.flush()
        return dict(passed=True, native_take_rows=len(typed_takes), callbacks=len(callbacks),
            exact_message_object_from_take=True, exact_original_raw_cdr=True,
            actual_metadata=[row['metadata'] for row in typed_takes],
            actual_local_ros_sim_ns=25_000_000_000,
            publication_brackets=wire.delivered,
            repeated_equal_cdr_not_unique_identity=True,
            unique_observed_candidates=True, ambiguous_and_unknown_retained=True,
            no_model_no_gazebo_no_nav2=True, ram_until_flush=True)
    finally:
        executor.remove_node(sink)
        executor.remove_node(source)
        executor.shutdown(timeout_sec=0)
        sink.destroy_node()
        source.destroy_node()
        context.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cache, dds = args.output / 'cache', args.output / 'dds'
    cache.mkdir(); dds.mkdir()
    result = dict(cache=cache_checks(cache), dds=dds_checks(dds),
        scope='Passive component only; not production qualification or a robot experiment')
    with (args.output / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cache=result['cache']['passed'], dds=result['dds']['passed'])))


if __name__ == '__main__':
    main()

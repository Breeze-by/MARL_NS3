"""Passive HQ input -> state -> original observation/policy provenance.

No subscriptions, business messages, encoding or inference are created here.
The installed Humble executor exposes metadata only at its one native take.
All new rows stay in RAM until the existing controller stops and destroys HQ.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time

SOURCE_REF_SCOPE = ('Latest successfully applied state/cache provenance; cached inputs may be '
                    'rejected or unused. Original read records show the executed observation branches.')


def input_topic(topic):
    return (topic in ('/merge_map', '/peer_keepout_state') or
            any(topic == f'/tb{r}/{suffix}' for r in (1, 2, 3)
                for suffix in ('odom', 'map', 'tf', 'tf_static', 'local_costmap/costmap',
                               'shared_navigation/map')))


def stamp_ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def transform_value(value):
    t, q = value.transform.translation, value.transform.rotation
    return dict(target=value.header.frame_id, source=value.child_frame_id,
                stamp_ns=stamp_ns(value.header.stamp),
                translation=[t.x, t.y, t.z], rotation=[q.x, q.y, q.z, q.w])


def json_value(value):
    if isinstance(value, Path):
        return str(value)
    return value.tolist() if hasattr(value, 'tolist') else value.item()


class ConsumerTrace:
    def __init__(self, node, directory):
        self.node, self.directory = node, Path(directory)
        self.rows, self.pending, self.sources = [], {}, {}
        self.local = threading.local()
        self.overhead_wall_ns = self.overhead_cpu_ns = 0
        self.receipts = {}
        self.observations = {}
        self.first_decision_id = None
        self.first_inference = None
        self.first_goals = []
        self.flushed = False

    @contextmanager
    def diagnostic(self):
        wall, cpu = time.monotonic_ns(), time.thread_time_ns()
        try:
            yield
        finally:
            self.overhead_cpu_ns += time.thread_time_ns() - cpu
            self.overhead_wall_ns += time.monotonic_ns() - wall

    def clock(self):
        return dict(monotonic_ns=time.monotonic_ns(), realtime_ns=time.time_ns(),
                    sim_ns=self.node.get_clock().now().nanoseconds)

    def row(self, kind, **fields):
        row = dict(event_id=len(self.rows) + 1, kind=kind, **fields)
        self.rows.append(row)
        return row

    def received(self, sub, result, before, after):
        """Retain the real tuple[1]; never substitute a header or guessed GID."""
        if result is None:
            return
        message, metadata = result
        row = self.row('hq_native_take', topic=sub.topic_name, raw=sub.raw,
                       before=before, after=after, metadata=metadata,
                       publisher_gid=None, publisher_gid_status='UNEXPOSED_BY_INSTALLED_SDK')
        self.pending[(sub.topic_name, id(message))] = row

    def callback(self, topic, original):
        def receive(message):
            with self.diagnostic():
                sequence = self.receipts.get(topic, 0) + 1
                self.receipts[topic] = sequence
                take = self.pending.pop((topic, id(message)), None)
                header = getattr(message, 'header', None)
                row = self.row('hq_input_callback', topic=topic, receipt_seq=sequence,
                    take_event_id=None if take is None else take['event_id'],
                    begin=self.clock(), end=None, original_returned=False,
                    header_stamp_ns=None if header is None else stamp_ns(header.stamp),
                    header_frame=None if header is None else header.frame_id,
                    header_stamp_semantics=('oldest_contributing_input_stamp_not_generation'
                        if topic == '/merge_map' or topic.endswith('/shared_navigation/map')
                        else 'original_source_header_stamp'),
                    generated_sim_ns=None, generated_time_status='UNMEASURED',
                    shared_map_applied=False, valid_pose_applied=False)
                if hasattr(message, 'transforms'):
                    row['tf_edges'] = [dict(target=t.header.frame_id,
                        source=t.child_frame_id, stamp_ns=stamp_ns(t.header.stamp))
                        for t in message.transforms]
                previous = getattr(self.local, 'callback', None)
                self.local.callback = row
            try:
                result = original(message)
                row['original_returned'] = True
                return result
            finally:
                with self.diagnostic():
                    if row['original_returned']:
                        robot = topic.split('/')[1]
                        if topic.endswith('/shared_navigation/map'):
                            if self.node.shared_navigation_maps.get(robot) is message:
                                self.sources['shared_navigation_map:' + robot] = row['event_id']
                        elif topic.endswith('/map') and topic != '/merge_map':
                            if self.node.local_maps.get(robot) is message:
                                self.sources['local_map:' + robot] = row['event_id']
                        elif topic.endswith('/local_costmap/costmap'):
                            entry = self.node.navigation_costmaps.get(robot)
                            if entry is not None and entry[0] is message:
                                self.sources['costmap:' + robot] = row['event_id']
                        elif topic == '/peer_keepout_state':
                            self.sources['peer_state'] = row['event_id']
                            state = self.node.peer_keepout_state
                            row['peer_sequence'] = state['sequence']
                            row['generated_sim'] = state['generated_sim']
                            row['generated_time_status'] = 'ORIGINAL_PAYLOAD_GENERATED_SIM'
                        if row['valid_pose_applied']:
                            state = self.node.allocator.robots[robot]
                            row['pose_after_original_callback'] = dict(pose=state.pose,
                                stamp=state.stamp, velocity=state.velocity)
                    row['end'] = self.clock()
                    self.local.callback = previous
        return receive

    def install_state_observers(self):
        allocator = self.node.allocator
        original_update = allocator.update_robot
        def update_robot(robot, *args, **kwargs):
            result = original_update(robot, *args, **kwargs)
            with self.diagnostic():
                callback = getattr(self.local, 'callback', None)
                if callback is not None and callback['topic'] == f'/{robot}/odom':
                    callback['valid_pose_applied'] = True
                    self.sources['pose:' + robot] = callback['event_id']
                    self.row('hq_valid_pose_applied', robot=robot,
                        callback_event_id=callback['event_id'], at=self.clock())
            return result
        allocator.update_robot = update_robot

        original_map = allocator.update_map
        def update_map(*args, **kwargs):
            result = original_map(*args, **kwargs)
            with self.diagnostic():
                callback = getattr(self.local, 'callback', None)
                if callback is not None and callback['topic'] == '/merge_map':
                    callback['shared_map_applied'] = True
                    self.sources['shared_map'] = callback['event_id']
            return result
        allocator.update_map = update_map

        for method in ('accepted', 'finish'):
            original_change = getattr(allocator, method)
            def change(robot, *args, method=method, original=original_change, **kwargs):
                result = original(robot, *args, **kwargs)
                with self.diagnostic():
                    callback = getattr(self.local, 'action', None)
                    if result and callback is not None:
                        self.sources['action:' + robot] = callback['event_id']
                        self.row('hq_action_state_applied', robot=robot, method=method,
                            callback_event_id=callback['event_id'], at=self.clock())
                return result
            setattr(allocator, method, change)

        for robot, buffer in self.node.tf.items():
            self.install_lookup(robot, buffer)
        original_observation = allocator.get_observation
        def observation(*args, **kwargs):
            with self.diagnostic():
                previous = getattr(self.local, 'observation', None)
                row = self.row('hq_observation_build', begin=self.clock(), end=None,
                    source_callback_refs=dict(self.sources), lookup_event_ids=[],
                    source_ref_scope=SOURCE_REF_SCOPE, original_read_event_ids=[],
                    decision_id=None, map_version=None, original_returned=False)
                self.local.observation = row
            try:
                value = original_observation(*args, **kwargs)
                with self.diagnostic():
                    row.update(decision_id=value['decision_id'],
                        map_version=value['map']['version'], original_returned=True)
                    self.observations[(value['decision_id'], value['map']['version'])] = row
                return value
            finally:
                with self.diagnostic():
                    row['end'] = self.clock()
                    self.local.observation = previous
        allocator.get_observation = observation

        original_select = self.node.policy.select
        def select(value):
            with self.diagnostic():
                row = self.row('hq_policy_use', begin=self.clock(), end=None,
                    decision_id=value['decision_id'], map_version=value['map']['version'],
                    observation_event_id=self.observations[(value['decision_id'], value['map']['version'])]['event_id'],
                    source_ref_scope=SOURCE_REF_SCOPE,
                    source_callback_refs=dict(self.sources), original_returned=False)
                self.local.policy_use = row
            try:
                action = original_select(value)
                row['original_returned'] = True
                return action
            finally:
                with self.diagnostic():
                    row['end'] = self.clock()
                    self.local.policy_use = None
        self.node.policy.select = select

    def install_lookup(self, robot, buffer):
        original = buffer.lookup_transform
        def lookup(*args, **kwargs):
            with self.diagnostic():
                requested = args[2] if len(args) >= 3 else kwargs['time']
                callback = getattr(self.local, 'callback', None)
                observation = getattr(self.local, 'observation', None)
                row = self.row('hq_tf_lookup', robot=robot, begin=self.clock(), end=None,
                    requested_target=args[0] if args else kwargs['target_frame'],
                    requested_source=args[1] if len(args) >= 2 else kwargs['source_frame'],
                    requested_time_ns=requested.nanoseconds,
                    callback_event_id=None if callback is None else callback['event_id'],
                    observation_event_id=None if observation is None else observation['event_id'],
                    source_tf_callback_refs=None,
                    source_tf_match_status='UNMEASURED_CHAIN_OR_INTERPOLATION',
                    original_returned=False)
                if observation is not None:
                    observation['lookup_event_ids'].append(row['event_id'])
            try:
                value = original(*args, **kwargs)
                with self.diagnostic():
                    row.update(returned_transform=transform_value(value), original_returned=True)
                return value
            finally:
                with self.diagnostic():
                    row['end'] = self.clock()
        buffer.lookup_transform = lookup

    def observe_record(self, event):
        kind = event['kind']
        if kind not in ('rl_real_inference', 'traditional_real_decision',
                        'rl_actual_nav2_goal_request', 'rl_actual_nav2_goal_response',
                        'rl_actual_nav2_goal_result', 'local_navigation_grid', 'shared_navigation_grid',
                        'gz01_seed_connection', 'gz01_peer_routing_mask'):
            return
        with self.diagnostic():
            use = getattr(self.local, 'policy_use', None)
            observation = getattr(self.local, 'observation', None)
            retained = event
            if kind == 'gz01_seed_connection':
                retained = {key: value for key, value in event.items()
                    if key not in ('self_body_excluded_cells', 'connection_cells')}
            read_refs = {}
            if kind in ('local_navigation_grid', 'shared_navigation_grid',
                        'gz01_seed_connection', 'gz01_peer_routing_mask'):
                role = {'local_navigation_grid': 'local_map:' + event['robot'],
                        'shared_navigation_grid': 'shared_navigation_map:' + event['robot'],
                        'gz01_seed_connection': 'costmap:' + event['robot'],
                        'gz01_peer_routing_mask': 'peer_state'}[kind]
                read_refs[role] = self.sources.get(role)
            row = self.row('hq_original_record', at=self.clock(), event=retained,
                branch_cache_callback_refs=read_refs,
                policy_use_event_id=None if use is None else use['event_id'],
                observation_event_id=None if observation is None else observation['event_id'])
            if observation is not None and read_refs:
                observation['original_read_event_ids'].append(row['event_id'])
            if kind in ('rl_real_inference', 'traditional_real_decision'):
                if self.first_inference is None:
                    self.first_inference = event
                    self.first_decision_id = event['decision_id']
            if kind == 'rl_actual_nav2_goal_request' and event['decision_id'] == self.first_decision_id:
                self.first_goals.append(event)

    def action_callback(self, kind, robot, token, original, value):
        with self.diagnostic():
            row = self.row(kind, begin=self.clock(), end=None, robot=robot, token=token,
                request_uuid=self.node.request_uuids.get((robot, token)),
                wire_message_id=None, wire_match_status='UNMEASURED_AT_ACTION_CALLBACK',
                original_returned=False)
            previous = getattr(self.local, 'action', None)
            self.local.action = row
        try:
            result = original(robot, token, value)
            row['original_returned'] = True
            return result
        finally:
            with self.diagnostic():
                row['end'] = self.clock()
                self.local.action = previous

    def flush(self):
        if self.flushed:
            return
        # Called only after the original executor's spin has left the node.
        with (self.directory / 'consumer-trace.jsonl').open('x') as stream:
            for row in self.rows:
                stream.write(json.dumps(row, default=json_value, allow_nan=False) + '\n')
        with (self.directory / 'consumer-trace-summary.json').open('x') as stream:
            json.dump(dict(schema='hq-consumer-trace-v1', rows=len(self.rows),
                diagnostic_wall_ns=self.overhead_wall_ns,
                diagnostic_thread_cpu_ns=self.overhead_cpu_ns,
                pending_take_without_callback=len(self.pending),
                first_inference=self.first_inference, first_actual_goals=self.first_goals,
                input_701='Existing first_inference.input_npz encoded_inputs; no extra encoding/inference',
                scope='Passive diagnostics; same common profile and pacing gates required',
                wire_identity='Join actual RMW source_timestamp against same-topic measured Gateway publish brackets; 0/multiple candidates stay unknown/ambiguous',
                unavailable='Publisher GID, TF publication chain/interpolation and unreported generation timestamps remain unmeasured'),
                stream, default=json_value, allow_nan=False, indent=2)
            stream.write('\n')
        self.flushed = True


def metadata_executor(node):
    """One HQ-owned executor, preserving installed Humble scheduling and take."""
    from rclpy.executors import SingleThreadedExecutor
    class ConsumerMetadataExecutor(SingleThreadedExecutor):
        def _take_subscription(self, sub):
            trace = node._consumer_trace
            if not input_topic(sub.topic_name):
                return super()._take_subscription(sub)
            with trace.diagnostic():
                before = trace.clock()
            # Identical installed Humble boundary: one native take, tuple[0].
            with sub.handle:
                result = sub.handle.take_message(sub.msg_type, sub.raw)
            with trace.diagnostic():
                after = trace.clock()
                trace.received(sub, result, before, after)
            return None if result is None else result[0]
    return ConsumerMetadataExecutor(context=node.context)


def traced_headquarters(original, startup=None):
    class TracedHeadquarters(original):
        def __init__(self, checkpoint, expected_sha256, directory, *args, **kwargs):
            self._consumer_trace = ConsumerTrace(self, directory)
            super().__init__(checkpoint, expected_sha256, directory, *args, **kwargs)
            self._consumer_trace.install_state_observers()
            if startup is not None:
                startup(self)

        def create_subscription(self, msg_type, topic, callback, qos_profile, **kwargs):
            if input_topic(topic):
                callback = self._consumer_trace.callback(topic, callback)
            return super().create_subscription(msg_type, topic, callback, qos_profile, **kwargs)

        def record(self, event):
            result = super().record(event)
            self._consumer_trace.observe_record(event)
            return result

        def goal_response_callback(self, robot, token, future):
            return self._consumer_trace.action_callback('hq_action_response_callback',
                robot, token, super().goal_response_callback, future)

        def goal_result_callback(self, robot, token, result):
            return self._consumer_trace.action_callback('hq_action_result_callback',
                robot, token, super().goal_result_callback, result)

        def destroy_node(self):
            try:
                if startup is not None:
                    self._fixed_startup_gate.finish()
                self._consumer_trace.flush()
            finally:
                result = super().destroy_node()
            return result
    return TracedHeadquarters

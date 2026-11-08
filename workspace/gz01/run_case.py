#!/usr/bin/env python3
"""One reviewed GZ-01 case with inherited safety/stop and independent outcomes.

Run inside tools/in-rootfs.sh after sourcing the two ROS setup files.
No model pose is set and no nonzero velocity is published by this tool.
"""
import argparse
from collections import deque
from debug_process import bind_owned_inferior, saved_owned_inferior
import sys
import csv
import itertools
import json
import math
import os
from pathlib import Path
import signal
import re
import hashlib
import subprocess
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'rl02'))
import numpy as np
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.time import Time
from rclpy.signals import SignalHandlerOptions
from action_msgs.msg import GoalStatusArray
from action_msgs.srv import CancelGoal
from gazebo_msgs.msg import ModelStates, ContactsState
from geometry_msgs.msg import Twist
from lifecycle_msgs.srv import GetState
from rcl_interfaces.srv import GetParameters
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from nav_msgs.msg import OccupancyGrid, Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan, JointState
from std_srvs.srv import Empty
from std_msgs.msg import Float64MultiArray, String
from tf2_msgs.msg import TFMessage
from tf2_ros import Buffer
from execution_evidence import read_controller_records, request_closure, engineering_closed_loop
from peer_keepout import state_fresh


ROBOTS = ('tb1', 'tb2', 'tb3')
NAV_NODES = ('controller_server', 'smoother_server', 'planner_server', 'behavior_server',
             'bt_navigator', 'waypoint_follower', 'velocity_smoother')


def timed_observer_call(node, stage, callback, *args, **kwargs):
    """Diagnostic only: no IO/wait, same callback return and exception."""
    if node.diagnostic_timing is None:return callback(*args,**kwargs)
    begin=time.monotonic();cpu=time.thread_time();sim=node.sim
    sequence=None if node.peer_state is None else node.peer_state['sequence']
    try:
        return callback(*args,**kwargs)
    finally:
        end_cpu=time.thread_time();end=time.monotonic()
        row=dict(stage=stage,phase=node.phase,begin_monotonic=begin,end_monotonic=end,
            wall_s=end-begin,thread_cpu_s=end_cpu-cpu,
            sim_before=sim,sim_after=node.sim,peer_sequence_before=sequence,
            peer_sequence_after=None if node.peer_state is None else node.peer_state['sequence'])
        node.diagnostic_timing.append(row)
        key=node.phase+'|'+stage
        stats=node.diagnostic_timing_stats.setdefault(key,dict(calls=0,max_wall=row))
        stats['calls']+=1
        if row['wall_s']>stats['max_wall']['wall_s']:stats['max_wall']=row


class Observer(Node):
    def __init__(self, directory, peer_guard=False, diagnostic_timing=False):
        super().__init__('base01_observer', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.directory = directory
        self.diagnostic_timing=deque(maxlen=4096) if diagnostic_timing else None
        self.diagnostic_timing_stats={}
        self.event_lines = []
        self.trajectory_rows = []
        self.trajectory_header = ['wall_unix', 'sim_s', 'robot', 'x', 'y', 'z', 'speed_xy', 'angular_z']
        self.map_snapshots = {}
        self.tf_snapshot_json = {}
        self.phase = 'preflight'
        self.paused_robots = set()
        self.drive = {}
        self.drive_rows = []
        self.drive_header = ['wall_unix','observer_sim','robot','phase','driver_sim','consumed_seq','rx_sim',
            'target_x','target_rot','measured_left_mps','measured_right_mps','desired_left_mps','desired_right_mps',
            'instruction_left_mps','instruction_right_mps','motor_left_mps','motor_right_mps','state_sync']
        self.sim = None
        self.latest = {}
        self.counts = {}
        self.maps = {}
        self.map_changes = {}
        self.positions = {}
        self.current_models = set()
        self.all_models_seen = False
        self.initial_positions = {}
        self.distances = dict.fromkeys(ROBOTS, 0.0)
        self.max_displacement = dict.fromkeys(ROBOTS, 0.0)
        self.max_speed = dict.fromkeys(ROBOTS, 0.0)
        self.minimum_pair_distance = float('inf')
        self.hazard = None
        self.tf = {r: Buffer(cache_time=Duration(seconds=15), node=self) for r in ROBOTS}
        self.tf_edges = {r: set() for r in ROBOTS}
        self.statuses = {r: set() for r in ROBOTS}
        self.active_goals = {r: set() for r in ROBOTS}
        self.feedback_goals = {}
        self.cancelled_goals = {}
        self.subscriptions_kept = []
        self.peer_guard = peer_guard
        self.peer_state = None
        self.peer_received = 0.
        if peer_guard:
            self.subscriptions_kept.append(self.create_subscription(String,
                '/peer_keepout_state',self.peer_health,1))
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        static_qos = QoSProfile(depth=100, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                reliability=ReliabilityPolicy.RELIABLE)
        self.subscriptions_kept.append(self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data))
        self.subscriptions_kept.append(self.create_subscription(ModelStates, '/gazebo/model_states', self.models, qos_profile_sensor_data))
        for r in ROBOTS:
            self.subscriptions_kept += [
                self.create_subscription(Float64MultiArray, f'/{r}/drive_diagnostics', lambda m, r=r: self.drive_state(m, r), 100),
                self.create_subscription(LaserScan, f'/{r}/scan', lambda m, r=r: self.scan(m, r), qos_profile_sensor_data),
                self.create_subscription(JointState, f'/{r}/joint_states', lambda m, r=r: self.wheels(m, r), qos_profile_sensor_data),
                self.create_subscription(Odometry, f'/{r}/odom', lambda m, r=r: self.odom(m, r), qos_profile_sensor_data),
                self.create_subscription(OccupancyGrid, f'/{r}/map', lambda m, r=r: self.map(m, r), latched),
                self.create_subscription(TFMessage, f'/{r}/tf', lambda m, r=r: self.transforms(m, r, False), 100),
                self.create_subscription(TFMessage, f'/{r}/tf_static', lambda m, r=r: self.transforms(m, r, True), static_qos),
                self.create_subscription(ContactsState, f'/{r}/contacts', lambda m, r=r: self.contacts(m, r), qos_profile_sensor_data),
                self.create_subscription(GoalStatusArray, f'/{r}/navigate_to_pose/_action/status', lambda m, r=r: self.status(m, r), latched),
                self.create_subscription(NavigateToPose.Impl.FeedbackMessage, f'/{r}/navigate_to_pose/_action/feedback', lambda m, r=r: self.feedback(m, r), qos_profile_sensor_data),
                self.create_subscription(Twist, f'/{r}/cmd_vel', lambda m, r=r: self.command(m, r), 10),
            ]
        self.subscriptions_kept.append(self.create_subscription(OccupancyGrid, '/merge_map', lambda m: self.map(m, 'merge_map'), latched))
        self.zero_publishers = {r: self.create_publisher(Twist, f'/{r}/cmd_vel', 10) for r in ROBOTS}
        self.next_stop_zero = 0.
        self.authority_stopped = True
        self.controller_directory = None
        self.diagnostic_deadline_sim = None
        self.diagnostic_budget_exhausted = False
        # Keep request/response endpoints alive through discovery and shutdown.
        self.service_clients = {}
        for robot in ROBOTS:
            for service_type, name in (
                    (ManageLifecycleNodes, f'/{robot}/lifecycle_manager_navigation/manage_nodes'),
                    (CancelGoal, f'/{robot}/navigate_to_pose/_action/cancel_goal'),
                    *((GetState, f'/{robot}/{node}/get_state') for node in NAV_NODES)):
                self.service_clients[name] = self.create_client(service_type, name)

        if self.diagnostic_timing is not None:
            # Public Subscription.callback; normal rclpy dispatch is unchanged.
            for index,subscription in enumerate(self.subscriptions):
                callback=subscription.callback
                stage=f'callback:{index}:{subscription.topic_name}'
                subscription.callback=lambda message,callback=callback,stage=stage: timed_observer_call(
                    self,stage,callback,message)

    def event(self, kind, **values):
        self.event_lines.append(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), wall=time.time(), sim=self.sim, kind=kind, **values)) + '\n')

    def seen(self, key):
        self.latest[key] = time.monotonic()
        self.counts[key] = self.counts.get(key, 0) + 1

    def drive_state(self, message, robot):
        self.seen(robot + '/drive')
        self.drive[robot] = list(message.data)
        self.drive_rows.append([time.time(), self.sim, robot, self.phase, *message.data])

    def peer_health(self,message):
        self.peer_state=json.loads(message.data)
        self.peer_received=time.monotonic()
        self.event('peer_state_received',sequence=self.peer_state['sequence'],
            generated_sim=self.peer_state['generated_sim'],observer_sim=self.sim,
            received_monotonic=self.peer_received,odom_stamps=self.peer_state['odom_stamps'],
            correction_stamps=self.peer_state['correction_stamps'])

    def peer_error(self):
        if not self.peer_guard:return None
        if self.peer_state is None or self.sim is None:return 'peer state/clock missing'
        heartbeat_wall_age=time.monotonic()-self.peer_received
        if heartbeat_wall_age>.3:
            self.event('peer_heartbeat_stale_context',
                sequence=self.peer_state['sequence'],generated_sim=self.peer_state['generated_sim'],
                observer_sim=self.sim,heartbeat_wall_age=heartbeat_wall_age,
                consumer_ages={r:dict(source=self.sim-self.peer_state['odom_stamps'][r],
                    correction=self.sim-self.peer_state['correction_stamps'][r]) for r in ROBOTS
                    if r in self.peer_state['odom_stamps'] and r in self.peer_state['correction_stamps']},
                end_to_end_fresh=state_fresh(self.peer_state,self.sim),
                peer_ready=self.peer_state['ready'],failures=self.peer_state['failures'])
            return 'peer state heartbeat stale'
        if not state_fresh(self.peer_state,self.sim):
            return 'peer odom/source-time TF not fresh: '+str(dict(
                sequence=self.peer_state['sequence'],generated_sim=self.peer_state['generated_sim'],
                observer_sim=self.sim,heartbeat_wall_age=heartbeat_wall_age,
                consumer_ages={r:dict(source=self.sim-self.peer_state['odom_stamps'][r],
                    correction=self.sim-self.peer_state['correction_stamps'][r]) for r in ROBOTS
                    if r in self.peer_state['odom_stamps'] and r in self.peer_state['correction_stamps']},
                ages=self.peer_state['ages'],failures=self.peer_state['failures']))
        return None

    def clock(self, message):
        self.sim = message.clock.sec + message.clock.nanosec * 1e-9
        if self.diagnostic_deadline_sim is not None and self.sim >= self.diagnostic_deadline_sim:
            self.diagnostic_deadline_sim = None
            self.diagnostic_budget_exhausted = True
            raise RuntimeError('Controlled stop diagnostic simulation budget exhausted')

    def scan(self, message, robot):
        self.seen(robot + '/scan')
        if self.counts[robot + '/scan'] == 1:
            finite = [x for x in message.ranges if math.isfinite(x)]
            self.event('scan_first', robot=robot, frame=message.header.frame_id, samples=len(message.ranges),
                       min_angle=message.angle_min, max_angle=message.angle_max,
                       range_min=message.range_min, range_max=message.range_max,
                       minimum_finite=min(finite) if finite else None)

    def odom(self, message, robot):
        self.seen(robot + '/odom')
        if self.counts[robot + '/odom'] == 1:
            p = message.pose.pose.position
            self.event('odom_first', robot=robot, frame=message.header.frame_id,
                       child=message.child_frame_id, x=p.x, y=p.y)

    def transforms(self, message, robot, static):
        self.seen(robot + ('/tf_static' if static else '/tf'))
        for transform in message.transforms:
            self.tf_edges[robot].add((transform.header.frame_id, transform.child_frame_id, static))
            if static:
                self.tf[robot].set_transform_static(transform, robot)
            else:
                self.tf[robot].set_transform(transform, robot)

    def capture_tf_state(self, label):
        data = {robot: dict(
            debug=self.tf[robot].can_transform('map', 'base_scan', Time(), return_debug_tuple=True),
            frames=self.tf[robot].all_frames_as_yaml(), received_edges=sorted(self.tf_edges[robot]),
            static_messages=self.counts.get(robot+'/tf_static', 0),
            dynamic_messages=self.counts.get(robot+'/tf', 0)) for robot in ROBOTS}
        self.tf_snapshot_json[label] = json.dumps(data, indent=2)
        self.event('tf_snapshot', label=label, ready={r: bool(v['debug'][0]) for r,v in data.items()})

    def map(self, message, robot):
        self.seen(robot + '/map')
        data = np.asarray(message.data, dtype=np.int8)
        if robot not in self.maps or not np.array_equal(data, self.maps[robot][1]):
            self.map_changes[robot] = self.map_changes.get(robot, 0) + 1
        self.maps[robot] = (message, data.copy())
        if self.counts[robot + '/map'] == 1:
            self.save_map(robot, 'first')
        self.event('map', robot=robot, width=message.info.width, height=message.info.height,
                   resolution=message.info.resolution, frame=message.header.frame_id,
                   origin=[message.info.origin.position.x, message.info.origin.position.y],
                   known=int(np.count_nonzero(data >= 0)), occupied=int(np.count_nonzero(data > 50)))

    def save_map(self, robot, suffix):
        message, data = self.maps[robot]
        self.map_snapshots[robot, suffix] = dict(data=data.copy(),
            width=message.info.width, height=message.info.height,
            resolution=message.info.resolution,
            origin=[message.info.origin.position.x, message.info.origin.position.y],
            frame=message.header.frame_id)

    def persist_observer_records(self):
        # No callback/stop loop is serviced here: all owned cleanup attempts have finished.
        with (self.directory/'events.jsonl').open('w') as stream:
            stream.writelines(self.event_lines)
        for name, header, rows in (
                ('trajectories.csv', self.trajectory_header, self.trajectory_rows),
                ('drive_diagnostics.csv', self.drive_header, self.drive_rows)):
            with (self.directory/name).open('w') as stream:
                writer = csv.writer(stream)
                writer.writerow(header)
                writer.writerows(rows)
        for label, serialized in self.tf_snapshot_json.items():
            (self.directory/('tf_'+label+'.json')).write_text(serialized)
        for (robot, suffix), snapshot in self.map_snapshots.items():
            np.savez_compressed(self.directory/f'{robot}_{suffix}.npz', **snapshot)
            data = snapshot['data']
            pixels = np.where(data < 0, 205, np.where(data > 50, 0, 254)).astype(np.uint8)
            pixels = np.flipud(pixels.reshape(snapshot['height'], snapshot['width']))
            with (self.directory/f'{robot}_{suffix}.pgm').open('wb') as stream:
                stream.write(f"P5\n{snapshot['width']} {snapshot['height']}\n255\n".encode())
                stream.write(pixels.tobytes())

    def models(self, message):
        self.seen('model_states')
        present = [n for n in message.name if n.startswith('tb')]
        if any(n not in ROBOTS for n in present):
            self.hazard = 'Unexpected robot models: ' + repr(present)
        self.current_models = set(message.name).intersection(ROBOTS)
        missing = set(ROBOTS) - self.current_models
        for robot in missing:
            self.positions.pop(robot, None)
        if self.all_models_seen and missing:
            self.hazard = 'Robot state missing: ' + repr(sorted(missing))
        self.all_models_seen = self.all_models_seen or not missing
        for robot in ROBOTS:
            if robot not in self.current_models:
                continue
            self.seen(robot + '/model_state')
            i = message.name.index(robot)
            p, v = message.pose[i].position, message.twist[i]
            speed = math.hypot(v.linear.x, v.linear.y)
            if not all(math.isfinite(x) for x in (p.x, p.y, p.z, speed, v.angular.z)):
                self.positions.pop(robot, None)
                self.hazard = robot + ' non-finite model state'
                continue
            if robot in self.positions:
                old = self.positions[robot]
                self.distances[robot] += math.hypot(p.x - old[0], p.y - old[1])
            self.positions[robot] = (p.x, p.y, p.z, speed, v.angular.z)
            self.initial_positions.setdefault(robot, (p.x, p.y))
            start = self.initial_positions[robot]
            self.max_displacement[robot] = max(self.max_displacement[robot], math.hypot(p.x - start[0], p.y - start[1]))
            self.max_speed[robot] = max(self.max_speed[robot], speed)
            self.trajectory_rows.append([time.time(), self.sim, robot, p.x, p.y, p.z, speed, v.angular.z])
            if abs(p.z) > 0.3:
                self.hazard = f'{robot} abnormal height {p.z}'
        if len(self.positions) == 3:
            distance = min(math.dist(self.positions[a][:2], self.positions[b][:2]) for a, b in itertools.combinations(ROBOTS, 2))
            self.minimum_pair_distance = min(self.minimum_pair_distance, distance)
            if distance < 0.30:
                self.hazard = f'Robot separation below 0.30 m: {distance:.3f}'

    def contacts(self, message, robot):
        self.seen(robot + '/contacts')
        for state in message.states:
            self.event('contact', robot=robot, collision1=state.collision1_name, collision2=state.collision2_name)
            self.hazard = f'{robot} chassis contact: {state.collision1_name}, {state.collision2_name}'

    def status(self, message, robot):
        self.active_goals[robot] = {bytes(s.goal_info.goal_id.uuid).hex()
                                   for s in message.status_list if s.status in (1, 2, 3)}
        self.seen(robot + '/action_status')
        for status in message.status_list:
            item = (bytes(status.goal_info.goal_id.uuid).hex(), status.status)
            if item not in self.statuses[robot]:
                self.statuses[robot].add(item)
                self.event('action_status', robot=robot, goal=item[0], status=item[1])

    def feedback(self, message, robot):
        self.seen(robot + '/feedback')
        self.feedback_goals[robot] = bytes(message.goal_id.uuid).hex()
        if self.counts[robot + '/feedback'] % 10 == 1:
            p = message.feedback.current_pose.pose.position
            self.event('action_feedback', robot=robot, goal=self.feedback_goals[robot], x=p.x, y=p.y,
                       remaining=message.feedback.distance_remaining)

    def wheels(self, message, robot):
        self.seen(robot + '/joint_states')
        if self.counts[robot + '/joint_states'] % 15 == 1:
            self.event('joint_state_observed', robot=robot, names=list(message.name),
                       positions=list(message.position), velocities=list(message.velocity),
                       stamp=[message.header.stamp.sec, message.header.stamp.nanosec])

    def command(self, message, robot):
        self.seen(robot + '/cmd_vel')
        if abs(message.linear.x) > 1e-4 or abs(message.angular.z) > 1e-4:
            self.event('cmd_vel', robot=robot, x=message.linear.x, angular_z=message.angular.z)
        else:
            self.seen(robot + '/zero_command_topic')
            if self.counts[robot + '/zero_command_topic'] % 20 == 1:
                # This is topic observation, NOT acknowledgement by the driver.
                self.event('zero_command_topic_observed', robot=robot)

    def stop_zeros(self):
        if self.phase == 'stop' and time.monotonic() >= self.next_stop_zero:
            for robot, publisher in self.zero_publishers.items():
                publisher.publish(Twist())
                self.event('zero_command_sent', robot=robot)
            self.next_stop_zero = time.monotonic()+.05

    def call(self, service_type, name, request, timeout=6):
        if name not in self.service_clients:
            self.service_clients[name] = self.create_client(service_type, name)
        client = self.service_clients[name]
        until = time.monotonic() + timeout
        while not client.service_is_ready() and time.monotonic() < until:
            self.stop_zeros()
            rclpy.spin_once(self, timeout_sec=0.02)
        if not client.service_is_ready():
            raise RuntimeError('Service unavailable: ' + name)
        future = client.call_async(request)
        while not future.done() and time.monotonic() < until:
            self.stop_zeros()
            rclpy.spin_once(self, timeout_sec=0.02)
        if not future.done():
            future.cancel()
            raise RuntimeError('Service timed out: ' + name)
        return future.result()

    def ready(self):
        now = time.monotonic()
        required = ['model_states'] + [r + '/' + t for r in ROBOTS for t in ('model_state', 'drive', 'scan', 'odom', 'map', 'contacts')]
        required += ['merge_map/map']
        missing = [key for key in required if key not in self.latest or now - self.latest[key] > (15 if key.endswith('/map') else 3)]
        missing += [r + '/TF map->base_scan' for r in ROBOTS if not self.tf[r].can_transform('map', 'base_scan', Time())]
        if self.peer_error():missing.append(self.peer_error())
        return missing

    def lifecycle(self):
        states = {}
        for robot in ROBOTS:
            for node in NAV_NODES:
                response = self.call(GetState, f'/{robot}/{node}/get_state', GetState.Request(), timeout=3)
                states[f'{robot}/{node}'] = response.current_state.label
        self.event('lifecycle', states=states)
        return all(state == 'active' for state in states.values())

    def startup_navigation(self, deadline):
        # Entities, sensor TF and SLAM must exist before native Nav2 configure/activate.
        for robot in ROBOTS:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Startup wall budget exhausted before Nav2 startup')
            request = ManageLifecycleNodes.Request()
            request.command = ManageLifecycleNodes.Request.STARTUP
            self.event('navigation_startup_requested', robot=robot)
            response = self.call(ManageLifecycleNodes,
                f'/{robot}/lifecycle_manager_navigation/manage_nodes', request,
                timeout=min(45., remaining))
            self.event('navigation_startup', robot=robot, success=response.success)
            if not response.success:
                raise RuntimeError('Native navigation startup failed: '+robot)

    def stop_motion(self):
        if self.diagnostic_budget_exhausted:
            # The caller's existing exception path issues emergency physics
            # pause; do not extend the diagnostic to obtain a PASS window.
            raise RuntimeError('Controlled diagnostic budget forbids further stop observation')
        self.phase = 'stop'
        self.next_stop_zero = 0.
        self.stop_zeros()
        errors = []
        controller_records, controller_errors = read_controller_records(self.controller_directory)
        # Keep the same ownership evidence without rescanning pose/feedback
        # history after every ROS callback in the freshness-sensitive stop loop.
        ownership_records = [row for row in controller_records if row['kind'] in (
            'rl_actual_nav2_goal_request', 'rl_actual_nav2_goal_response',
            'rl_actual_nav2_goal_result')]
        owned = {r:{goal for goal, _ in self.statuses[r]} for r in ROBOTS}
        for robot in ROBOTS:
            try:
                response = self.call(CancelGoal, f'/{robot}/navigate_to_pose/_action/cancel_goal', CancelGoal.Request())
                self.cancelled_goals[robot] = [bytes(g.goal_id.uuid).hex() for g in response.goals_canceling]
                owned[robot].update(self.cancelled_goals[robot])
                self.event('cancel_all', robot=robot, return_code=response.return_code,
                           goals=len(response.goals_canceling), goal_ids=self.cancelled_goals[robot])
                if response.return_code != 0:
                    raise RuntimeError('Cancel-all rejected: '+robot)
            except Exception as exc:
                errors.append(str(exc))
                self.event('stop_rpc_error', robot=robot, stage='cancel', detail=str(exc))
        for robot in ROBOTS:
            if robot in self.paused_robots:
                self.event('navigation_already_paused', robot=robot)
                continue
            try:
                request = ManageLifecycleNodes.Request()
                request.command = ManageLifecycleNodes.Request.PAUSE
                response = self.call(ManageLifecycleNodes, f'/{robot}/lifecycle_manager_navigation/manage_nodes', request, timeout=15)
                self.event('navigation_pause', robot=robot, success=response.success)
                if not response.success:
                    raise RuntimeError('Navigation pause failed: ' + robot)
                self.paused_robots.add(robot)
            except Exception as exc:
                errors.append(str(exc))
                self.event('stop_rpc_error', robot=robot, stage='pause', detail=str(exc))
        self.phase = 'stop'
        start_receipts = {r: self.drive[r][1] if r in self.drive else -1 for r in ROBOTS}
        start_count = self.counts.get('model_states', 0)
        stable_since = stable_sim = None
        last_sample = self.counts.get('model_states', 0)
        until = time.monotonic() + 12
        while time.monotonic() < until:
            self.stop_zeros()
            rclpy.spin_once(self, timeout_sec=0.02)
            # A whole message being fresh cannot certify an absent robot.
            complete = self.current_models == set(ROBOTS) and set(self.positions) == set(ROBOTS)
            fresh = all(time.monotonic() - self.latest.get(r + '/model_state', 0) < 1 for r in ROBOTS)
            stationary = complete and all(p[3] < 0.01 and abs(p[4]) < 0.03 for p in self.positions.values())
            received_zero = all(
                r in self.drive and self.drive[r][1] > start_receipts[r]
                and self.drive[r][3] == 0.0 and self.drive[r][4] == 0.0
                and time.monotonic()-self.latest.get(r+'/drive', 0) < 1 for r in ROBOTS)
            for robot in ROBOTS:
                owned[robot].update(goal for goal, _ in self.statuses[robot])
            closure = request_closure(ownership_records, self.statuses, self.active_goals,
                self.authority_stopped, extra_owned=owned, log_errors=controller_errors)
            ownership_closed = closure['closed']
            if (not self.authority_stopped or not ownership_closed or not stationary
                    or not fresh or not received_zero or self.hazard):
                stable_since = stable_sim = None
            elif self.counts['model_states'] != last_sample:
                if stable_since is None:
                    stable_since, stable_sim = time.monotonic(), self.sim
                if (time.monotonic() - stable_since > 1.5 and self.sim > stable_sim + 0.5
                        and self.counts['model_states'] > start_count + 5):
                    self.event('observed_stop', positions=self.positions.copy(),
                               per_robot_wall={r: self.latest[r + '/model_state'] for r in ROBOTS},
                               sim_advanced=self.sim - stable_sim,
                               drive_received={r:self.drive[r] for r in ROBOTS}, rpc_errors=errors,
                               authority_stopped=self.authority_stopped, ownership_closed=ownership_closed,
                               owned_goals={r:sorted(goals) for r,goals in owned.items()},
                               request_ownership=closure,
                               lifecycle_pause_healthy=set(ROBOTS)==self.paused_robots)
                    return True
            last_sample = self.counts.get('model_states', 0)
        self.event('stop_unresolved_ownership', request_ownership=closure)
        return False

    def diagnose_motion(self, sim_budget):
        self.phase = 'stop_diagnostic_motion'
        start_sim, start_wall = self.sim, time.monotonic()
        # The 120sim bound starts with the first controlled test command;
        # it remains armed through final stopping. Startup has its own wall cap.
        self.diagnostic_deadline_sim = start_sim + sim_budget
        next_command = 0.0
        self.event('stop_diagnostic_motion_start', angular_z=0.6, linear_x=0.0,
                   diagnostic_deadline_sim=self.diagnostic_deadline_sim, actor_calls=0)
        while self.sim-start_sim < 4.0 and time.monotonic()-start_wall < 60.0:
            if time.monotonic() >= next_command:
                command = Twist()
                command.angular.z = 0.6
                for publisher in self.zero_publishers.values():
                    publisher.publish(command)
                next_command = time.monotonic()+0.05
            rclpy.spin_once(self, timeout_sec=0.02)
            if self.hazard or self.ready():
                raise RuntimeError('Diagnostic safety/observation failure: '+str(self.hazard or self.ready()))
        if self.sim-start_sim < 4.0:
            raise RuntimeError('Diagnostic wall-clock budget exhausted')
        self.event('stop_diagnostic_motion_end', sim_elapsed=self.sim-start_sim, wall_elapsed=time.monotonic()-start_wall)

    def verify_slam_loop_gate(self):
        for robot in ROBOTS:
            request=GetParameters.Request();request.names=['loop_match_minimum_response_fine']
            response=self.call(GetParameters,f'/{robot}/slam_toolbox/get_parameters',request)
            value=response.values[0]
            self.event('slam_loop_gate_loaded',robot=robot,parameter=request.names[0],
                parameter_type=value.type,value=value.double_value,expected=.75)
            if value.type!=3 or value.double_value!=.75:
                raise RuntimeError(f'{robot} SLAM loop fine gate is not the locked .75')

    def record_loaded_driver(self, launch_log, expected):
        match = re.search(r'\[gzserver-\d+\]: process started with pid \[(\d+)\]', launch_log.read_text())
        if not match:
            raise RuntimeError('Cannot bind gzserver PID')
        pid = int(match.group(1))
        if os.environ.get('GZ01_BATCH_GDB') == '1':
            pid = bind_owned_inferior(self.directory, pid, 'gzserver')['pid']
        maps = Path(f'/proc/{pid}/maps').read_text()
        (self.directory/'gzserver.maps').write_text(maps)
        library = Path('/project/workspace/install/base01_diff_drive/lib')/expected
        rows = [line for line in maps.splitlines() if expected in line]
        if not rows or not any(int(line.split()[4]) == library.stat().st_ino for line in rows):
            raise RuntimeError('Expected driver binary is not the loaded inode')
        identity = dict(pid=pid, library=str(library), sha256=hashlib.sha256(library.read_bytes()).hexdigest(), maps=rows)
        (self.directory/'loaded-driver.json').write_text(json.dumps(identity,indent=2))
        self.event('loaded_driver', **identity)

    def resume(self):
        for robot in ROBOTS:
            request = ManageLifecycleNodes.Request()
            request.command = ManageLifecycleNodes.Request.RESUME
            response = self.call(ManageLifecycleNodes, f'/{robot}/lifecycle_manager_navigation/manage_nodes', request, timeout=15)
            if not response.success:
                raise RuntimeError('Navigation resume failed: ' + robot)
            self.paused_robots.discard(robot)
        if not self.lifecycle():
            raise RuntimeError('Navigation inactive after resume')


def end_process(process, observer, name):
    if process is None or process.poll() is not None:
        return
    for sig, timeout in ((signal.SIGINT, 20), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        observer.event('process_signal', process=name, pid=process.pid, signal=sig.name)
        os.killpg(process.pid, sig)
        until = time.monotonic()+timeout
        while process.poll() is None and time.monotonic() < until:
            observer.stop_zeros()
            rclpy.spin_once(observer, timeout_sec=0.02)
        if process.poll() is not None:
            observer.event('process_exit', process=name, code=process.returncode)
            return



def record_process(directory, role, pid):
    with (directory/'owned_processes.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(role=role,pid=pid))+"\n")


def controller_end(directory, position):
    path = directory/'allocation-events.jsonl'
    if not path.exists():
        return None, position
    with path.open() as stream:
        stream.seek(position)
        while True:
            position = stream.tell()
            line = stream.readline()
            # Retry only the incomplete trailing record on the next poll.
            if not line or not line.endswith('\n'):
                return None, position
            row = json.loads(line)
            if row.get('kind') == 'rl_halt_requested':
                return row['reason'], stream.tell()


def active_cancel_complete(result):
    """Actual owned CANCELED UUIDs may precede the supervisor cancel RPC."""
    trigger = result.get('cancel_trigger')
    if not trigger:
        return False
    ownership = result['final_request_ownership']
    return bool(result['error'] is None and result['observed_stop']
        and result['hazard'] is None and ownership['authority_stopped']
        and ownership['closed'] and all(
            result['cancel_trigger_positions'][r][3] > .03
            and trigger[r]
            and set(trigger[r]).issubset(ownership['owned_goals'][r])
            and all((goal,5) in {(uuid,status) for uuid,status in result['action_statuses'][r]}
                    for goal in trigger[r]) for r in ROBOTS))


def drain_ready_callbacks(node):
    # One round based on this real node's declared entities, no delivery wait.
    count=sum(sum(1 for _ in getattr(node,name)) for name in
        ('subscriptions','timers','clients','services','guards','waitables'))
    for _ in range(count):
        rclpy.spin_once(node,timeout_sec=0)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready', type=Path, required=True)
    ready_arg = parser.parse_args()
    from boot import validate_ready
    ready = validate_ready(ready_arg.ready, consumed=True)
    args = argparse.Namespace(directory=Path(ready['case_path']),
        scene=Path(ready['scene_path']), arm=ready['arm'],system_variant=ready['system_variant'],
        rl_checkpoint=Path(ready['checkpoint_path']), rl_checkpoint_sha256=ready['checkpoint_sha256'],
        controller_script=str(Path(__file__).with_name('headquarters.py')),
        stationary_only=ready['mode']=='stationary_only', stop_diagnostic=ready['stop_diagnostic'],
        active_cancel_check=ready['active_cancel_check'], drive_plugin='libbase01_diff_drive.so',
        sim_seconds=ready['sim_budget'], wall_seconds=ready['autonomous_wall'],
        startup_wall=ready['startup_wall'])
    args.directory.mkdir(parents=True, exist_ok=False)
    # Retain the ROS context while handling SIGINT so cancellation and observed
    # stop can still use services before shutdown.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    observer = Observer(args.directory,peer_guard=ready['peer_guard'],
        diagnostic_timing=ready.get('observer_timing',False))
    launch = control = bag = None
    result = dict(preflight=False, smoke_started=False, observed_stop=False, error=None,
                  end_reason='not_started', sim_elapsed=0.0, wall_elapsed=0.0,
                  natural_complete=False, threshold_reached=None, arm=args.arm, scene=str(args.scene),
                  system_variant=args.system_variant,
                  launch_request_utc=None, launch_exit_utc=None, gazebo_started=False, gzserver_pid=None)
    os.environ['BASE01_RUN_DIR'] = str(args.directory.resolve())
    os.environ['ROS_LOG_DIR'] = str(args.directory.resolve() / 'ros_logs')
    if ready['phase_probe']:
        os.environ['GZ01_PHASE_PROBE_LIBRARY'] = str(
            Path(__file__).parent/'phase_probe/build/libgz01_phase_probe.so')
    if ready['peer_guard']:os.environ['GZ01_PEER_GUARD']='1'
    try:
        command = ['ros2', 'launch', str(Path(__file__).with_name('scene_launch.py')),
                   'robot_count:=3', 'scene:='+str(args.scene), 'drive_plugin:='+args.drive_plugin, 'enable_exploration:=false', 'enable_rviz:=false', 'enable_gui:=false', 'enable_drive:=false',
                   'nav2_autostart:=false', 'nav2_log_level:=info']
        observer.event('launch_command', argv=command)
        launch_log = (args.directory / 'launch.log').open('w')
        result['launch_request_utc'] = datetime.now(timezone.utc).isoformat()
        # Exclusive case/boot markers exist before this first actual launch attempt.
        launch = subprocess.Popen(command, stdout=launch_log, stderr=subprocess.STDOUT, start_new_session=True)
        record_process(args.directory, 'launch', launch.pid)
        observer.event('launch_process_started', pid=launch.pid, utc_start=result['launch_request_utc'])
        bag_topics = ['/clock', '/gazebo/model_states', '/gazebo/link_states', '/merge_map']
        if ready['peer_guard']:bag_topics.append('/peer_keepout_state')
        for robot in ROBOTS:
            bag_topics += [f'/{robot}/'+topic for topic in ('scan', 'odom', 'map', 'tf', 'tf_static', 'cmd_vel', 'drive_diagnostics', 'navigate_to_pose/_action/status', 'navigate_to_pose/_action/feedback', 'plan', 'local_plan', 'local_costmap/costmap')]
            if ready['peer_guard']:
                bag_topics += [f'/{robot}/global_costmap/costmap',f'/{robot}/peer_keepout_filter_info']
        bag_command = ['ros2', 'bag', 'record', '--use-sim-time', '--include-hidden-topics', '--storage', 'sqlite3',
            '--max-bag-size', '134217728', '--max-cache-size', '10485760',
            '--qos-profile-overrides-path', '/mnt/workspace/rl02/bag-qos.yaml',
            '--output', str(args.directory/'bag'), *bag_topics]
        observer.event('bag_command', argv=bag_command)
        bag_log = (args.directory/'bag.log').open('w')
        bag = subprocess.Popen(bag_command, stdout=bag_log, stderr=subprocess.STDOUT, start_new_session=True)
        record_process(args.directory, 'bag', bag.pid)
        until = time.monotonic() + args.startup_wall
        while time.monotonic() < until:
            rclpy.spin_once(observer, timeout_sec=0.1)
            if launch.poll() is not None or bag.poll() is not None:
                raise RuntimeError('Launch exited before readiness')
            if observer.hazard:
                raise RuntimeError(observer.hazard)
            if not observer.ready() and all(observer.counts.get(r + '/scan', 0) >= 5 for r in ROBOTS):
                break
        else:
            observer.capture_tf_state('preflight_failure')
            raise RuntimeError('Preflight missing: ' + repr(observer.ready()))
        observer.capture_tf_state('preflight_ready')
        observer.startup_navigation(until)
        while time.monotonic() < until:
            if observer.lifecycle():
                break
            rclpy.spin_once(observer, timeout_sec=.1)
        else:
            raise RuntimeError('Nav2 lifecycle not active within startup budget')
        for filename, command in [('nodes.txt', ['ros2', 'node', 'list']),
                                  ('topics.txt', ['ros2', 'topic', 'list', '-t']),
                                  ('actions.txt', ['ros2', 'action', 'list', '-t']),
                                  ('processes.txt', ['ps', '-eo', 'pid,ppid,pgid,lstart,args'])]:
            with (args.directory / filename).open('w') as stream:
                subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=20, check=True)
        (args.directory / 'tf_edges.json').write_text(json.dumps({r: sorted(edges) for r, edges in observer.tf_edges.items()}, indent=2))
        observer.record_loaded_driver(args.directory/'launch.log', args.drive_plugin)
        observer.verify_slam_loop_gate()
        if not observer.stop_motion():
            raise RuntimeError('Stationary preflight could not prove observed stop')
        result['preflight'] = True
        observer.event('preflight_pass')
        observer.event('initial_scan_ready', counts={r:observer.counts.get(r+'/scan',0) for r in ROBOTS})
        if args.stationary_only:
            result['end_reason'] = 'stationary_only'
        if args.stop_diagnostic:
            result['diagnostic_started'] = True
            observer.diagnose_motion(args.sim_seconds)
        elif not args.stationary_only:
            observer.resume()
            control_log = (args.directory / 'control.log').open('w')
            observer.controller_directory = args.directory/'controller'
            command = ['python3', '-B', args.controller_script, '--arm', args.arm,
                       '--system-variant',args.system_variant,
                '--checkpoint', str(args.rl_checkpoint), '--checkpoint-sha256', args.rl_checkpoint_sha256,
                '--run-dir', str(args.directory/'controller'), '--ros-args', '-p', 'use_sim_time:=true']
            if ready.get('joint_participation',False):command.insert(3,'--joint-participation')
            observer.event('exploration_command', argv=command)
            result['autonomy_start_sim'] = observer.sim
            result['autonomy_start_wall_unix'] = time.time()
            control = subprocess.Popen(command, stdout=control_log, stderr=subprocess.STDOUT, start_new_session=True)
            record_process(args.directory, 'controller', control.pid)
            observer.authority_stopped = False
            # Prove motion and Action outcomes in this interval, not startup.
            observer.initial_positions = {r: observer.positions[r][:2] for r in ROBOTS}
            observer.distances = dict.fromkeys(ROBOTS, 0.0)
            observer.max_displacement = dict.fromkeys(ROBOTS, 0.0)
            observer.max_speed = dict.fromkeys(ROBOTS, 0.0)
            observer.statuses = {r: set() for r in ROBOTS}
            observer.cancelled_goals = {}
            observer.map_changes = dict.fromkeys((*ROBOTS, 'merge_map'), 0)
            for robot in ROBOTS:
                observer.counts[robot + '/feedback'] = 0
            observer.event('smoke_initial_positions', positions=observer.initial_positions)
            observer.phase = 'autonomous_exploration'
            start_sim, start_wall = observer.sim, time.monotonic()
            result['smoke_started'] = True
            result['end_reason'] = 'running'
            next_health = start_wall
            controller_terminal = None
            controller_position = 0
            while observer.sim - start_sim < args.sim_seconds and time.monotonic() - start_wall < args.wall_seconds:
                timed_observer_call(observer,'spin_once',rclpy.spin_once,observer,timeout_sec=0.05)
                if timed_observer_call(observer,'process_poll',lambda: control.poll() is not None or launch.poll() is not None or bag.poll() is not None):
                    raise RuntimeError('Controller, launch or bag exited during autonomous interval')
                controller_terminal, controller_position = timed_observer_call(observer,'controller_end',controller_end,
                    observer.controller_directory, controller_position)
                if controller_terminal:
                    if controller_terminal == 'decision_budget':
                        break
                    raise RuntimeError('Controller halted unexpectedly: '+controller_terminal)
                if observer.hazard:
                    raise RuntimeError(observer.hazard)
                peer_error=timed_observer_call(observer,'peer_error',observer.peer_error)
                if peer_error:
                    before_sequence=observer.peer_state['sequence']
                    spins=timed_observer_call(observer,'drain_ready_callbacks',drain_ready_callbacks,observer)
                    if observer.hazard:raise RuntimeError(observer.hazard)
                    after_error=timed_observer_call(observer,'peer_error_after_drain',observer.peer_error)
                    observer.event('peer_ready_callback_round',spin_attempts=spins,
                        before_sequence=before_sequence,after_sequence=observer.peer_state['sequence'],
                        error_before=peer_error,error_after=after_error)
                    peer_error=after_error
                if peer_error:raise RuntimeError(peer_error)
                if time.monotonic() - observer.latest.get('model_states', 0) > 3:
                    raise RuntimeError('Gazebo truth pose stream lost')
                if time.monotonic() >= next_health:
                    missing = timed_observer_call(observer,'periodic_ready',observer.ready)
                    if missing:
                        observer.capture_tf_state('runtime_failure')
                        raise RuntimeError('Runtime observation missing/stale: ' + repr(missing))
                    nodes = {(ns.rstrip('/') + '/' + name) for name, ns in timed_observer_call(observer,'periodic_graph',observer.get_node_names_and_namespaces)}
                    expected = {f'/{r}/{node}' for r in ROBOTS for node in ('slam_toolbox', 'controller_server', 'planner_server', 'bt_navigator')}
                    if expected - nodes:
                        raise RuntimeError('Critical nodes missing: ' + repr(sorted(expected - nodes)))
                    stale_tf = []
                    for robot in ROBOTS:
                        transform = timed_observer_call(observer,'periodic_tf:'+robot,observer.tf[robot].lookup_transform,'map','base_scan',Time())
                        stamp = transform.header.stamp.sec + transform.header.stamp.nanosec * 1e-9
                        if observer.sim - stamp > 3:
                            stale_tf.append(robot)
                    if stale_tf:
                        observer.capture_tf_state('runtime_stale')
                        raise RuntimeError('Stale navigation TF: ' + repr(stale_tf))
                    next_health = time.monotonic() + 2
                if args.active_cancel_check and observer.sim-start_sim >= 30.0 and all(
                        observer.active_goals[r] and observer.positions[r][3] > 0.03
                        and time.monotonic()-observer.latest.get(r+'/model_state', 0) < 1
                        and observer.feedback_goals.get(r) in observer.active_goals[r]
                        and time.monotonic()-observer.latest.get(r+'/feedback', 0) < 1
                        for r in ROBOTS):
                    result['cancel_trigger'] = {r: sorted(observer.active_goals[r]) for r in ROBOTS}
                    result['cancel_trigger_positions'] = observer.positions.copy()
                    observer.event('active_cancel_trigger', goals=result['cancel_trigger'],
                                   positions=observer.positions.copy())
                    break
            result['sim_elapsed'] = observer.sim - start_sim
            result['wall_elapsed'] = time.monotonic() - start_wall
            result['end_reason'] = ('active_cancel_trigger' if 'cancel_trigger' in result else
                'decision_budget' if controller_terminal == 'decision_budget' else
                'simulation_budget' if result['sim_elapsed'] >= args.sim_seconds else 'wall_timeout')
            observer.event('smoke_bound', sim_elapsed=result['sim_elapsed'],
                           wall_elapsed=result['wall_elapsed'], reason=result['end_reason'])
            if args.active_cancel_check and result['end_reason'] != 'active_cancel_trigger':
                raise RuntimeError('No three-robot active moving goal interval within bounded cancel check')
            if not args.active_cancel_check and result['end_reason'] not in ('simulation_budget','decision_budget'):
                raise RuntimeError('Wall-clock budget exhausted before requested simulation duration')
    except KeyboardInterrupt:
        result['end_reason'] = 'interrupted'
        result['error'] = 'Run interrupted by operator or outer wall-clock timeout'
        observer.event('error', detail=result['error'])
    except Exception as exc:
        result['end_reason'] = 'fatal_error'
        result['error'] = str(exc)
        observer.event('error', detail=str(exc))
    finally:
        diagnostic_runtime_window=(None if observer.diagnostic_timing is None else list(observer.diagnostic_timing))
        if result['smoke_started'] and result['error'] is not None:
            result['sim_elapsed'] = observer.sim - start_sim
            result['wall_elapsed'] = time.monotonic() - start_wall
        observer.phase = 'stop'
        observer.next_stop_zero = 0.
        observer.stop_zeros()
        end_process(control, observer, 'exploration')
        observer.authority_stopped = control is None or control.poll() is not None
        try:
            result['observed_stop'] = observer.stop_motion()
            if not result['observed_stop']:
                raise RuntimeError('Observed motion stop not confirmed')
        except Exception as exc:
            observer.event('stop_error', detail=str(exc))
            result['stop_error'] = str(exc)
            try:
                observer.call(Empty, '/pause_physics', Empty.Request(), timeout=3)
                observer.event('emergency_physics_pause')
            except Exception as pause_error:
                observer.event('emergency_pause_error', detail=str(pause_error))
        for robot in observer.maps:
            observer.save_map(robot, 'last')
        end_process(bag, observer, 'bag')
        end_process(launch, observer, 'launch')
        if observer.peer_guard:
            saved_path=args.directory/'peer-recording-saved.json'
            result['peer_recording']=(json.loads(saved_path.read_text()) if saved_path.exists()
                else dict(saved=False,reason='Peer records save marker missing after owned shutdown'))
        else:
            result['peer_recording']=None
        if result['launch_request_utc'] is not None:
            result['launch_exit_utc'] = datetime.now(timezone.utc).isoformat()
            match = re.search(r'\[gzserver-\d+\]: process started with pid \[(\d+)\]',
                              (args.directory/'launch.log').read_text())
            if os.environ.get('GZ01_BATCH_GDB') == '1':
                result['gzserver_debugger_pid'] = int(match.group(1)) if match else None
                inferior = saved_owned_inferior(args.directory, result['gzserver_debugger_pid'], 'gzserver')
                result['gazebo_started'] = inferior is not None
                result['gzserver_pid'] = inferior['pid'] if inferior else None
            else:
                result['gazebo_started'] = match is not None
                result['gzserver_pid'] = int(match.group(1)) if match else None
        import shutil
        gazebo_logs = Path('/root/.gazebo')/('server-'+os.environ['GAZEBO_MASTER_URI'].rsplit(':',1)[-1])
        if gazebo_logs.exists():
            shutil.copytree(gazebo_logs,args.directory/'gazebo_logs')
        with (args.directory / 'processes_after.txt').open('w') as stream:
            subprocess.run(['ps', '-eo', 'pid,ppid,pgid,lstart,args'], stdout=stream, stderr=subprocess.STDOUT, timeout=10)
        result.update(counts=observer.counts, map_changes=observer.map_changes,
                      distances=observer.distances, max_displacement=observer.max_displacement,
                      max_speed=observer.max_speed,
                      minimum_pair_distance=observer.minimum_pair_distance if math.isfinite(observer.minimum_pair_distance) else None,
                      action_statuses={r: sorted(x) for r, x in observer.statuses.items()},
                      hazard=observer.hazard)
        result['diagnostic_stop_pass'] = bool(result.get('diagnostic_started') and result['error'] is None and result['observed_stop'] and observer.hazard is None)
        result['baseline_smoke_pass'] = (result['smoke_started'] and result['error'] is None
            and result['observed_stop'] and observer.hazard is None
            and all(observer.max_displacement[r] > 0.10 for r in ROBOTS)
            and result['end_reason'] == 'simulation_budget'
            and all(any(status == 4 for _, status in observer.statuses[r]) for r in ROBOTS)
            and all(observer.counts.get(r + '/feedback', 0) > 0 for r in ROBOTS)
            and all(observer.map_changes.get(r, 0) > 1 for r in (*ROBOTS, 'merge_map')))
        controller_records, controller_errors = read_controller_records(observer.controller_directory)
        result['engineering_evidence'] = engineering_closed_loop(controller_records, result)
        result['final_request_ownership'] = request_closure(controller_records, observer.statuses,
            observer.active_goals, observer.authority_stopped, log_errors=controller_errors)
        result['active_cancel_pass'] = bool(args.active_cancel_check and active_cancel_complete(result))
        result['engineering_closed_loop_pass'] = (result['engineering_evidence']['engineering_closed_loop_pass']
            and result['final_request_ownership']['closed'])
        result['lifecycle_pause_healthy'] = set(ROBOTS)==observer.paused_robots
        result['participation'] = {r:dict(path_m=observer.distances[r],
            actual_goals=sum(row.get('kind')=='rl_actual_nav2_goal_request' and row.get('robot')==r
                             for row in controller_records)) for r in ROBOTS}
        for robot, row in result['participation'].items():
            row['effective_motion'] = row['path_m'] >= 1. and row['actual_goals'] >= 1
        # Coverage/quality/thresholds are populated only by the offline evaluator.
        # Low coverage, no motion or no successes remain valid performance outcomes.
        result['run_integrity'] = bool(result['preflight'] and result['error'] is None
            and result['observed_stop'] and observer.hazard is None
            and not result.get('stop_error') and result['lifecycle_pause_healthy']
            and result['final_request_ownership']['closed']
            and (not observer.peer_guard or result['peer_recording']['saved'])
            and (not args.active_cancel_check or result['active_cancel_pass']))
        observer.event('finished', **result)
        observer.persist_observer_records()
        result['observer_records_saved'] = dict(events=len(observer.event_lines),
            trajectory_rows=len(observer.trajectory_rows), drive_rows=len(observer.drive_rows),
            map_snapshots=len(observer.map_snapshots), tf_snapshots=len(observer.tf_snapshot_json))
        (args.directory / 'result.json').write_text(json.dumps(result, indent=2))
        if observer.diagnostic_timing is not None:
            (args.directory/'observer_timing.json').write_text(json.dumps(dict(
                scope='Diagnostic timing only, no guard/clock/source/stop changes',
                max_recent_rows=4096,last_runtime_window=diagnostic_runtime_window,
                phase_stage_summary=observer.diagnostic_timing_stats,
                output_phase='after_existing_stop_and_cleanup_attempts'),indent=2))
        print(json.dumps(result, indent=2), flush=True)
        observer.destroy_node()
        rclpy.shutdown()
    return 0 if result['run_integrity'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

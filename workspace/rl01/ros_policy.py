"""Fixed-checkpoint ROS adapter. Import does not initialize ROS or start robots.

This separate P7 file leaves the frozen training implementation and accepted
traditional entry untouched. Real execution requires the external BASE01/02
supervisor; halt requests do not claim physical stopping.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import numpy as np
import torch
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid, Odometry
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer
from tf2_msgs.msg import TFMessage

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.evaluation import Evaluator
from multi_robot_exploration.ppo import ActorCritic, PPOPolicy, load_checkpoint
from multi_robot_exploration.rl_ledger import Ledger
from completion import validate_development_checkpoint


def fixed_policy(checkpoint, expected_sha256, ledger):
    actual_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError('Fixed checkpoint SHA256 mismatch')
    torch.set_num_threads(1)
    model = ActorCritic(ledger)
    metadata = load_checkpoint(checkpoint, model)
    completion = validate_development_checkpoint(torch.load(checkpoint, map_location='cpu', weights_only=False), metadata['config'])
    if metadata.get('failure') is not None or metadata.get('joint_decisions') != 1024:
        raise ValueError('P7 requires the successful fixed 1024-step final checkpoint')
    config = metadata['config']
    if tuple(metadata['task_roi']) != model.task_roi or config['task_roi'] != list(model.task_roi):
        raise ValueError('Checkpoint ROI/config disagreement')
    if metadata.get('encoding') != 'received-grid-to-fixed-metric-roi-0.05m-v1':
        raise ValueError('Checkpoint encoding contract mismatch')
    model.eval()
    ledger.flush('fixed_policy_bound', checkpoint=str(checkpoint), sha256=actual_sha256,
                 source_sha256=metadata['source_sha256'], roi=config['task_roi'], completion=completion)
    return PPOPolicy(model, deterministic=True), config


class CheckpointHeadquarters(HeadquartersControl):
    """One ROS-time central decision callback; original Nav2 methods inherited.

    Do not call the parent constructor: it starts three traditional workers.
    Map/TF/goal-send/feedback methods are reused unchanged. Odom wraps the
    velocity-frame conversion; response/result wrap timeout-cancel cause only.
    """
    def __init__(self, checkpoint, expected_sha256, directory, ledger, timed=False,
                 policy_loader=fixed_policy, action_client_factory=ActionClient):
        self.events = (directory/'allocation-events.jsonl').open('x', buffering=1)
        Node.__init__(self, 'headquarters_control_rl')
        self.ledger = ledger
        # Load and validate the policy before any callback can allocate a goal.
        self.policy, self.config = policy_loader(checkpoint, expected_sha256, ledger)
        self.lock = threading.RLock()
        self.worker_error = None
        self.goal_handles, self.local_maps = {}, {}
        self.pose_tf_errors = {}
        self.timeout_cancel_tokens = set()
        self.tf = {r: Buffer(cache_time=Duration(seconds=15), node=self) for r in ('tb1', 'tb2', 'tb3')}
        self.robot_nav_clients = {r: action_client_factory(self, NavigateToPose, f'/{r}/navigate_to_pose') for r in self.tf}
        self.evaluator = Evaluator(tuple(self.tf))
        self.allocator = Allocator(tuple(self.tf), self.goal_valid, self.record,
            task_timeout_s=self.config['backend']['navigation_timeout_sim_s'], task_roi=self.config['task_roi'],
            candidate_mode=self.config.get('candidate_mode','legacy'),
            local_navigation_grid=self.local_navigation_grid,
            navigation_path_budget_m=self.config.get('navigation_path_budget_m'),
            navigation_goal_tolerance_m=self.config['backend']['xy_goal_tolerance_m'])
        self.decisions = 0
        self.record(dict(kind='rl_checkpoint_bound', sim=self.now(), checkpoint=str(checkpoint),
                         checkpoint_sha256=expected_sha256, task_roi=self.config['task_roi'],
                         decision_period_sim_s=self.config['step_sim_seconds'], physical_stop_verified=False))
        self.subscriptions_kept = []
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        static_qos = QoSProfile(depth=100, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.subscriptions_kept.append(self.create_subscription(OccupancyGrid, '/merge_map', self.map_callback, 10))
        for robot in self.tf:
            self.subscriptions_kept += [
                self.create_subscription(Odometry, f'/{robot}/odom', lambda m, r=robot: self.robot_odom_callback(m, r), 10),
                self.create_subscription(Twist, f'/{robot}/cmd_vel', lambda m, r=robot: self.robot_status_control(m, r), 4),
                self.create_subscription(OccupancyGrid, f'/{robot}/map', lambda m, r=robot: self.local_map_callback(m, r), latched),
                self.create_subscription(TFMessage, f'/{robot}/tf', lambda m, r=robot: self.tf_callback(m, r, False), 100),
                self.create_subscription(TFMessage, f'/{robot}/tf_static', lambda m, r=robot: self.tf_callback(m, r, True), static_qos)]
        self.timer = self.create_timer(self.config['step_sim_seconds'], self.decision_callback) if timed else None

    def robot_odom_callback(self, message, robot):
        # ROS Odometry twist is expressed in child/base frame; the training proxy
        # supplies merge_map linear velocity. This is an explicit message-frame
        # conversion, not a change of learned observation features or Nav2 control.
        with self.lock:
            if not super().robot_odom_callback(message, robot):
                return  # Retained velocity is already in merge_map; do not rotate it twice.
            state = self.allocator.robots[robot]
            if state.pose is not None:
                vx, vy, omega = state.velocity
                yaw = state.pose[2]
                state.velocity = (math.cos(yaw)*vx-math.sin(yaw)*vy,
                                  math.sin(yaw)*vx+math.cos(yaw)*vy, omega)

    def allocate_once(self):
        """Same immutable snapshot → PPO → common gate → inherited Nav2 pipeline."""
        with self.ledger.call('ros_joint_decision_attempt'):
            with self.lock:
                self.allocator.tick(self.now())
                if self.allocator.halted:
                    return dict(state='halted', proposals={}, rejected={})
                if self.decisions >= self.config['episode_decisions']:
                    self.halt('decision_budget')
                    return dict(state='decision_budget', proposals={}, rejected={})
                missing=[r.name for r in self.allocator.robots.values() if r.pose is None]
                if self.allocator.map is None or missing:
                    self.record(dict(kind='rl_wait_observation',sim=self.now(),missing_map=self.allocator.map is None,
                        missing_robots=missing,pose_tf_errors=self.pose_tf_errors))
                    self.dispatch_requested_cancels()
                    return dict(state='awaiting_observation', proposals={}, rejected={})
                # Explicit engineering guard for missing/frozen ROS delivery; no
                # replacement goal or modified checkpoint is used on stale state.
                if any(self.now()-r.stamp > 2. for r in self.allocator.robots.values()):
                    self.record(dict(kind='rl_wait_fresh_state', sim=self.now(),
                        pose_ages_s={r.name:self.now()-r.stamp for r in self.allocator.robots.values()},
                        pose_tf_errors=self.pose_tf_errors))
                    self.dispatch_requested_cancels()
                    return dict(state='awaiting_fresh_state', proposals={}, rejected={})
                observation = self.allocator.get_observation()
                self.ledger.add('ros_allocator_observation_build')
                action = self.policy.select(observation)
                proposals, rejected = self.allocator.apply(observation, action)
                self.decisions += 1
                self.record(dict(kind='rl_joint_action', sim=self.now(), decision=self.decisions,
                                 decision_id=action.decision_id, map_version=action.map_version,
                                 choices=action.choices, rejected=rejected))
                if rejected:
                    raise ValueError('PPO joint action rejected: '+str(rejected))
                self.dispatch_requested_cancels()
            for robot, (target, token) in proposals.items():
                self.send_goal(robot, target, token)
            return dict(state='applied', proposals=proposals, rejected=rejected, action=action)

    def dispatch_requested_cancels(self):
        for robot, state in self.allocator.robots.items():
            if state.cancel_requested and robot in self.goal_handles:
                if state.condition == 'task_timeout_cancel_required':
                    self.mark_timeout_cancel(robot, state.token)
                self.goal_handles.pop(robot).cancel_goal_async()

    def mark_timeout_cancel(self, robot, token):
        self.timeout_cancel_tokens.add((robot, token))
        self.record(dict(kind='timeout_cancel_dispatched', sim=self.now(), robot=robot,
                         token=token, reason='navigation_timeout'))

    def goal_response_callback(self, robot, token, future):
        with self.lock:
            state = self.allocator.robots[robot]
            # A pending request may be accepted after its deadline. Parent will
            # cancel that late handle; retain the cause before its callback runs.
            if (future.result().accepted and state.token == token and state.state == 'pending'
                    and state.cancel_requested and state.condition == 'task_timeout_cancel_required'
                    and not self.allocator.halted):
                self.mark_timeout_cancel(robot, token)
            HeadquartersControl.goal_response_callback(self, robot, token, future)

    def goal_result_callback(self, robot, token, result):
        with self.lock:
            key = (robot, token)
            state = self.allocator.robots[robot]
            owned = state.token == token and state.state != 'idle'
            own_timeout = key in self.timeout_cancel_tokens
            self.timeout_cancel_tokens.discard(key)
            if owned and own_timeout and result.status == 5:
                self.allocator.tick(self.now())
                # Preserve the real Nav2 CANCELED receipt, while matching the
                # training backend's high-level timeout failure and exclusion.
                self.record(dict(kind='nav2_terminal_classified', sim=self.now(), robot=robot,
                                 token=token, raw_nav2_status=5, high_level_status='aborted',
                                 reason='navigation_timeout'))
                if self.allocator.finish(robot, token, 'aborted'):
                    self.goal_handles.pop(robot, None)
                self.get_logger().info(f'{robot} raw Nav2 status=5; task timeout classified aborted')
            else:
                # External cancellation (even a late receipt), success, and old
                # tokens keep the original handling and ownership semantics.
                HeadquartersControl.goal_result_callback(self, robot, token, result)

    def decision_callback(self):
        try:
            self.allocate_once()
        except Exception as error:
            self.worker_error = f'{type(error).__name__}: {error}'
            self.halt('policy_error')
            self.get_logger().fatal(self.worker_error)
            self.context.try_shutdown()

    def halt(self, reason):
        with self.lock:
            self.allocator.tick(self.now())
            self.allocator.stop(reason)
            for handle in tuple(self.goal_handles.values()):
                handle.cancel_goal_async()
            self.record(dict(kind='rl_halt_requested', sim=self.now(), reason=reason,
                             physical_stop_verified=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    args, ros_args = parser.parse_known_args()
    args.run_dir.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(args.run_dir/'ledger.jsonl', 'ros_inference')
    rclpy.init(args=ros_args)
    node = CheckpointHeadquarters(args.checkpoint, args.checkpoint_sha256, args.run_dir, ledger, timed=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.halt('controller_shutdown')
        node.events.close()
        node.destroy_node()
        ledger.flush('ros_inference_end')
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

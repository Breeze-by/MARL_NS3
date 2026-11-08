"""Typed ROS2/Nav2 Mock integration, never a Gazebo or physical experiment."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import rclpy
from rclpy.task import Future
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid, Odometry

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend
from multi_robot_exploration.ppo import MAP_SIDE
from ros_headquarters import RL04Headquarters as CheckpointHeadquarters


class MockHandle:
    accepted = True

    def __init__(self, robot, number, ledger):
        self.ledger = ledger
        self.goal_id = SimpleNamespace(uuid=bytearray((int(robot[-1])*1000000+number).to_bytes(16, 'little')))
        self.result = Future()

    def get_result_async(self):
        return self.result

    def complete(self, status):
        self.ledger.add('mock_nav2_terminal_receipts')
        self.result.set_result(SimpleNamespace(status=status))

    def cancel_goal_async(self):
        self.ledger.add('mock_nav2_cancel_requests')
        if not self.result.done():
            self.complete(5)
        future = Future()
        future.set_result(SimpleNamespace(goals_canceling=[self.goal_id]))
        return future


class MockClient:
    def __init__(self, robot, ledger):
        self.robot, self.ledger = robot, ledger
        self.sent, self.handles, self.feedback = [], [], []

    def wait_for_server(self, timeout_sec):
        self.ledger.add('mock_nav2_wait_for_server')
        return True

    def send_goal_async(self, goal, feedback_callback):
        self.ledger.add('mock_nav2_goal_sends')
        self.sent.append(goal)
        self.feedback.append(feedback_callback)
        handle = MockHandle(self.robot, len(self.sent), self.ledger)
        self.handles.append(handle)
        future = Future()
        future.set_result(handle)
        return future


def grid(cells, resolution, origin, frame, stamp):
    message = OccupancyGrid()
    message.header.frame_id = frame
    message.header.stamp = stamp
    message.info.height, message.info.width = cells.shape
    message.info.resolution = float(resolution)
    message.info.origin.position.x, message.info.origin.position.y = map(float, origin)
    message.info.origin.orientation.w = 1.
    message.data = cells.astype(np.int8).ravel().tolist()
    return message


def fresh_odom(node, positions):
    for robot in positions:
        message = Odometry()
        message.header.frame_id = 'odom'
        message.child_frame_id = 'base_footprint'
        message.header.stamp = node.get_clock().now().to_msg()
        message.pose.pose.orientation.w = 1.
        node.robot_odom_callback(message, robot)


def run(case, checkpoint):
    case.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(case/'ledger.jsonl', 'rl04_selected_typed_ros_mock')
    result = dict(status='RUNNING', gazebo=False, actual_nav2_action_server=False,
                  physical_stop_verified=False, environment_steps=0, optimizer_updates=0)
    node = None
    rclpy.init(args=[])
    try:
        node = CheckpointHeadquarters(checkpoint, hashlib.sha256(checkpoint.read_bytes()).hexdigest(), case, ledger, timed=False)
        # The goal transformation, local validity, send, feedback and response/result
        # code is the actual BASE02 implementation, not a rewritten approximation.
        inherited = ('map_callback', 'local_map_callback', 'local_point',
                     'goal_valid', 'local_navigation_grid', 'nav_goal_in_local_map', 'send_goal', 'feedback_callback')
        assert all(getattr(CheckpointHeadquarters, name) is getattr(HeadquartersControl, name) for name in inherited)
        for path in (WORKSPACE/'rl01/ros_policy.py', WORKSPACE/'rl04/ros_headquarters.py', WORKSPACE/'src/multi_robot_exploration/multi_robot_exploration/control.py'):
            tree = ast.parse(path.read_text())
            assert not any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                           and call.func.attr == 'create_publisher' for call in ast.walk(tree))
        with ledger.call('world_projection_build', scope='sensor-only mock setup, not development evaluation'):
            world = ProjectedWorld(WORKSPACE/'src/multi_robot/worlds/my_world.world', '/project/assets/gazebo_models', 'A')
        backend = KinematicBackend(world, node.config['backend'], ledger, 11)
        receipt = backend.reset()  # No advance/step/motion: obtain legally observed sensor fixture.
        node.map_callback(grid(receipt['snapshot']['map']['cells'], .05, world.origin,
                               'merge_map', node.get_clock().now().to_msg()))
        positions = dict(zip(('tb1', 'tb2', 'tb3'), node.config['backend']['initial_positions']))
        for robot, position in positions.items():
            node.robot_nav_clients[robot].destroy()
            node.robot_nav_clients[robot] = MockClient(robot, ledger)
            transform = TransformStamped()
            transform.header.frame_id, transform.child_frame_id = 'merge_map', 'map'
            transform.transform.translation.x, transform.transform.translation.y = map(float, position)
            transform.transform.rotation.w = 1.
            node.tf[robot].set_transform_static(transform, 'declared_initial_calibration_fixture')
            transform = TransformStamped()
            transform.header.frame_id, transform.child_frame_id = 'map', 'odom'
            transform.transform.rotation.w = 1.
            node.tf[robot].set_transform_static(transform, 'identity_slam_alignment_fixture')
            node.local_map_callback(grid(backend.local[robot], .05,
                (world.origin[0]-position[0], world.origin[1]-position[1]), 'map', node.get_clock().now().to_msg()), robot)
        fresh_odom(node, positions)
        # A real typed Odometry fixture checks the explicit body→merge velocity adapter.
        from math import sqrt
        message = Odometry()
        message.header.frame_id = 'odom'
        message.child_frame_id = 'base_footprint'
        message.header.stamp = node.get_clock().now().to_msg()
        message.pose.pose.orientation.z = message.pose.pose.orientation.w = sqrt(.5)
        message.twist.twist.linear.x = .26
        node.robot_odom_callback(message, 'tb1')
        assert np.allclose(node.allocator.robots['tb1'].velocity, (0., .26, 0.), atol=1e-10)
        ledger.add('ros_velocity_fixture_observation_build')
        velocity_features = node.policy.model.encode(node.allocator.get_observation())
        robot_features_start = 2*MAP_SIDE*MAP_SIDE
        assert np.allclose(velocity_features[robot_features_start+4:robot_features_start+7], (0., 1., 0.), atol=1e-7)
        fresh_odom(node, positions)
        first = node.allocate_once()
        assert first['proposals'] and not first['rejected'], 'Fixed fixture did not exercise any actual policy goal dispatch'
        assert all(node.allocator.robots[r].state == 'active' and node.allocator.robots[r].uuid for r in first['proposals'])
        for robot, (target, token) in first['proposals'].items():
            goal = node.robot_nav_clients[robot].sent[0]
            assert goal.pose.header.frame_id == 'map'
            assert np.allclose([goal.pose.pose.position.x, goal.pose.pose.position.y],
                               np.array(target)-positions[robot], atol=1e-9)
            assert goal.pose.pose.orientation.w == 1.
            assert node.allocator.robots[robot].token == token
        before = sum(len(client.sent) for client in node.robot_nav_clients.values())
        tokens = {name: robot.token for name, robot in node.allocator.robots.items()}
        fresh_odom(node, positions)
        second = node.allocate_once()
        assert not second['rejected']
        # -1 is KEEP for an owned active task; -2 is WAIT for an idle robot.
        # This unchanged-map fixture has not invalidated or timed out these tasks;
        # the policy cannot cancel a valid active task by choosing WAIT.
        keep_checks = 0
        for i, robot in enumerate(('tb1','tb2','tb3')):
            if robot in first['proposals']:
                assert robot not in second['proposals']
                assert node.allocator.robots[robot].token == tokens[robot]
                assert second['action'].choices[i] == -1
                keep_checks += 1
                assert node.allocator.robots[robot].state == 'active'
        assert sum(len(client.sent) for client in node.robot_nav_clients.values()) == before+len(second['proposals'])
        active_robots = [r for r in ('tb1','tb2','tb3') if node.allocator.robots[r].state == 'active']
        assert len(active_robots) >= 2, 'Fixed fixture did not supply two owned goals for terminal callback coverage'
        for robot in active_robots:
            node.robot_nav_clients[robot].feedback[-1](SimpleNamespace(feedback=SimpleNamespace(distance_remaining=1.)))
        for robot, status in zip(active_robots[:2], (4,6)):
            node.robot_nav_clients[robot].handles[-1].complete(status)
            assert node.allocator.robots[robot].state == 'idle'
        retained = {r:node.allocator.robots[r].token for r in active_robots[2:]}
        fresh_odom(node, positions)
        third = node.allocate_once()
        assert not third['rejected']
        for robot, token in retained.items():
            assert node.allocator.robots[robot].token == token and robot not in third['proposals']
            assert node.allocator.robots[robot].state == 'active'
        node.halt('mock_end')
        assert not node.goal_handles
        fresh_odom(node, positions)
        halted = node.allocate_once()
        assert halted['state'] == 'halted' and not halted['proposals']
        assert backend.stop('sensor_fixture_end')
        result.update(status='TYPED ROS MOCK PASS; Gazebo NOT VERIFIED',
                      checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                      inherited_methods=list(inherited), initial_joint_choices=first['action'].choices,
                      wrapped_callbacks=['robot_odom_callback', 'goal_response_callback', 'goal_result_callback'],
                      keep_no_resend_exercised=keep_checks>0, success_and_failure_terminal=True,
                      retained_active_token_count=len(retained), active_token_preserved_when_retained=True,
                      body_to_merge_map_velocity_conversion=True,
                      encoded_velocity_frame_matches_training=True,
                      task_halt_blocks_new_goals=True, no_cmd_vel_publisher=True,
                      allocator_metrics=node.evaluator.summary())
    except Exception as error:
        import traceback
        result.update(status='FAIL', error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
        raise
    finally:
        if node is not None:
            node.halt('mock_cleanup')
            node.events.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        ledger.flush('typed_mock_end')
        result['ledger_totals'] = dict(ledger.counts)
        (case/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.checkpoint)

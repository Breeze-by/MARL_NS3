#!/usr/bin/env python3
"""Focused configuration and action-result checks; does not start ROS nodes."""
import ast
from concurrent.futures import Future
import importlib.util
import itertools
import json
import math
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import yaml

project = Path('/project')
source = project / 'workspace/src'
launch_path = source / 'multi_robot/launch/gazebo_multirobot_mapping_with_nav2.launch.py'
tree = ast.parse(launch_path.read_text())
robot_assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'robots' for t in node.targets)
                        and isinstance(node.value, ast.List))
robots = ast.literal_eval(robot_assignment.value)
assert [r['name'] for r in robots[:3]] == ['tb1', 'tb2', 'tb3']
assert len({r['name'] for r in robots}) == len(robots)
minimum_spawn = min(math.dist([float(a['x_pose']), float(a['y_pose'])],
                             [float(b['x_pose']), float(b['y_pose'])])
                    for a, b in itertools.combinations(robots[:3], 2))
assert minimum_spawn > 0.70
for i in range(1, 5):
    parameters = yaml.safe_load((source / f'multi_robot/params/nav2_params_tb{i}_0.yaml').read_text())
    assert parameters['controller_server']['ros__parameters']['goal_checker_plugins'] == ['goal_checker']
    assert parameters['local_costmap']['local_costmap']['ros__parameters']['robot_radius'] == 0.25
    assert parameters['global_costmap']['global_costmap']['ros__parameters']['robot_radius'] == 0.25
    assert parameters['controller_server']['ros__parameters']['FollowPath']['plugin'] == 'dwb_core::DWBLocalPlanner'
model = ET.parse(source / 'multi_robot/models/turtlebot3_waffle/model.sdf')
base_collision = model.find(".//link[@name='base_link']/collision[@name='base_collision']")
cx, cy = map(float, base_collision.findtext('pose').split()[:2])
sx, sy = map(float, base_collision.findtext('geometry/box/size').split()[:2])
radius = max(math.hypot(cx + x * sx / 2, cy + y * sy / 2) for x, y in itertools.product((-1, 1), repeat=2))
assert radius < 0.25
assert model.find(".//sensor[@name='baseline_contacts']") is not None
assert not any('/home/' in u.text for u in model.findall('.//uri'))
world = ET.parse(source / 'multi_robot/worlds/my_world.world')
assert world.find(".//plugin[@name='baseline_state']") is not None

spec = importlib.util.spec_from_file_location('econ_control', source / 'multi_robot_exploration/multi_robot_exploration/control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
logs = []
logger = SimpleNamespace(info=logs.append, warning=logs.append)
owner = SimpleNamespace(robot_states={'tb1': 'active'}, get_logger=lambda: logger,
                        last_successful_targets={})
owner.release_target = lambda robot, succeeded=False, failed=False: control.HeadquartersControl.release_target(owner, robot, succeeded, failed)
owner.goal_result_callback = lambda robot, result: control.HeadquartersControl.goal_result_callback(owner, robot, result)
for status in (4, 6, 5):
    owner.robot_states['tb1'] = 'active'
    terminal = Future()
    accepted = Future()
    accepted.set_result(SimpleNamespace(accepted=True, get_result_async=lambda: terminal, goal_id=SimpleNamespace(uuid=[0]*16)))
    control.HeadquartersControl.goal_response_callback(owner, 'tb1', accepted)
    assert owner.robot_states['tb1'] == 'active', 'Goal acceptance must not imply navigation completion'
    terminal.set_result(SimpleNamespace(status=status))
    assert owner.robot_states['tb1'] == 'idle'
owner.robot_states['tb1'] = 'active'
rejected = Future()
rejected.set_result(SimpleNamespace(accepted=False))
control.HeadquartersControl.goal_response_callback(owner, 'tb1', rejected)
assert owner.robot_states['tb1'] == 'idle'

for path in (launch_path, source / 'merge_map/launch/merge_map_launch.py', project / 'tools/run_baseline.py'):
    ast.parse(path.read_text())
print(json.dumps(dict(status='PASS', configured_robots=robots, minimum_spawn_distance_m=minimum_spawn,
                      chassis_xy_radius_m=radius, nav2_radius_m=0.25,
                      action_result_checks=['accepted_not_complete', 'success', 'abort', 'cancel', 'reject'],
                      action_logs=logs), indent=2))

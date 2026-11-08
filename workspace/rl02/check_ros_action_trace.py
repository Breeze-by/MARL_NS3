"""Typed goal/signature/token-UUID logging fixture; no ROS node or server."""
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import numpy as np
from nav2_msgs.action import NavigateToPose
from unique_identifier_msgs.msg import UUID
from rclpy.action import ActionClient
from ros_headquarters import RL02Headquarters, LoggedActionClient, PROJECT
from multi_robot_exploration.allocation import Allocator
from maps import dump


def run():
    output = PROJECT/'evidence/ros-action-trace-01'
    output.mkdir(parents=True, exist_ok=False)
    events, deferred_results = [], []
    node = object.__new__(RL02Headquarters)
    node.lock = threading.RLock()
    node.goal_handles = {}
    node.request_uuids = {}
    node.timeout_cancel_tokens = set()
    node.now = lambda: 12.
    node.record = lambda event: events.append(event)
    node.get_logger = lambda: SimpleNamespace(info=lambda message: None)
    node.allocator = Allocator(emit=node.record)
    node.allocator.tick(12.)
    node.allocator.decision_id = 11
    state = node.allocator.robots['tb1']
    state.token, state.target, state.state, state.started = 7, (2., 3.), 'pending', 12.
    client = object.__new__(LoggedActionClient)
    client.trace_node, client.trace_robot = node, 'tb1'
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp.sec = 12
    goal.pose.pose.position.x, goal.pose.pose.position.y = 2., 3.
    goal.pose.pose.orientation.w = 1.
    uuid = UUID(uuid=list(range(16)))
    handle = SimpleNamespace(accepted=True, goal_id=uuid,
        get_result_async=lambda: SimpleNamespace(add_done_callback=deferred_results.append))
    future = SimpleNamespace(result=lambda: handle, add_done_callback=lambda callback: callback(future))
    feedback = lambda message: None
    with patch.object(ActionClient, 'send_goal_async', autospec=True, return_value=future) as parent:
        actual = client.send_goal_async(goal, feedback_callback=feedback, goal_uuid=uuid)
        parent.assert_called_once_with(client, goal, feedback_callback=feedback, goal_uuid=uuid)
        if actual is not future:
            raise AssertionError('Wrapped Action future was replaced')
    node.goal_response_callback('tb1', 7, future)
    sent = next(e for e in events if e['kind'] == 'rl_actual_nav2_goal_request')
    accepted = next(e for e in events if e['kind'] == 'goal_accepted')
    if sent['token'] != accepted['token'] or accepted['uuid'] != bytes(range(16)).hex():
        raise AssertionError('Goal request token lost its accepted UUID')
    if state.state != 'active' or node.goal_handles['tb1'] is not handle or len(deferred_results) != 1:
        raise AssertionError('Original Action ownership/result wiring changed')
    dump(output/'events.json', events)
    result = dict(status='PASS', original_parent_signature_preserved=True, real_NavigateToPose_message=True,
        goal_request_frame=sent['actual_goal_frame'], raw_goal_position=sent['actual_goal_position'],
        token=7, accepted_uuid=accepted['uuid'], deferred_result_callbacks=len(deferred_results),
        true_ros_node_init=0, actual_action_client_init=0, real_action_server=0, actual_goal_dispatch=0,
        nn_forward=0, env_step=0, optimizer_step=0, physical_stop_verified=False)
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()

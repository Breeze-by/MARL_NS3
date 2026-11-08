"""Directed cleanup ordering fixture; no initialized ROS context or model."""
import json
from types import SimpleNamespace
from unittest.mock import patch
import ros_headquarters as adapter
from maps import PROJECT, dump
from multi_robot_exploration.rl_ledger import Ledger


def run():
    output = PROJECT/'evidence/ros-shutdown-01'
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for alive in (True, False):
        calls, events = [], []
        node = SimpleNamespace(worker_error=None if alive else 'ValueError: original policy failure',
            halt=lambda reason: calls.append('halt'), record=events.append, now=lambda: 12.,
            events=SimpleNamespace(close=lambda: calls.append('events_close')),
            destroy_node=lambda: calls.append('destroy'))
        original_error = node.worker_error
        ledger = Ledger(output/f'{"alive" if alive else "closed"}-ledger.jsonl', 'cleanup_fixture_no_ros')
        with patch.object(adapter.rclpy, 'ok', return_value=alive), patch.object(adapter.rclpy, 'shutdown',
                side_effect=lambda: calls.append('context_shutdown')):
            adapter.close_controller(node, ledger)
        expected = ['halt', 'events_close', 'destroy', 'context_shutdown'] if alive else ['events_close', 'destroy']
        if calls != expected or node.worker_error != original_error:
            raise AssertionError('Cleanup order or first policy error changed')
        if not alive and (events[0]['first_worker_error'] != original_error or events[0]['physical_stop_verified']):
            raise AssertionError('Closed-context path lost its original cause or claimed stopping')
        results.append(dict(context_alive_fixture=alive, calls=calls, events=events,
                            original_worker_error_preserved=True, counts=dict(ledger.counts)))
    result = dict(status='PASS', cases=results, actual_rclpy_init=0, actual_node_init=0,
        actual_action_rpc=0, nn_forward=0, optimizer_step=0, env_step=0,
        gazebo_start=0, physical_stop_verified=False)
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()

"""Offline first-attempt evidence, reading SQLite CDR without a ROS node."""
from collections import Counter
import csv
import json
import sqlite3
from pathlib import Path
import numpy as np
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from maps import PROJECT, dump


def run():
    case = PROJECT/'evidence/gazebo-rl-01'
    output = PROJECT/'evidence/gazebo-failure-analysis-01'
    output.mkdir(exist_ok=False)
    events = [json.loads(line) for line in (case/'events.jsonl').read_text().splitlines()]
    counts, types, samples = Counter(), {}, {}
    duration = []
    for path in sorted((case/'bag').glob('*.db3')):
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as connection:
            for topic_id, name, kind in connection.execute('SELECT id, name, type FROM topics'):
                number = connection.execute('SELECT COUNT(*) FROM messages WHERE topic_id=?', (topic_id,)).fetchone()[0]
                counts[name] += number
                types[name] = kind
                if number and name not in samples:
                    sample = connection.execute('SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp LIMIT 1', (topic_id,)).fetchone()[0]
                    samples[name] = deserialize_message(sample, get_message(kind))
            duration.append(connection.execute('SELECT MIN(timestamp), MAX(timestamp) FROM messages').fetchone())
    robots = ('tb1', 'tb2', 'tb3')
    sensors = {}
    for robot in robots:
        scan, odom = samples[f'/{robot}/scan'], samples[f'/{robot}/odom']
        sensors[robot] = dict(scan_messages=counts[f'/{robot}/scan'], rays=len(scan.ranges),
            scan_frame=scan.header.frame_id, odom_messages=counts[f'/{robot}/odom'],
            odom_frame=odom.header.frame_id, child_frame=odom.child_frame_id,
            map_messages=counts[f'/{robot}/map'], tf_messages=counts[f'/{robot}/tf'],
            tf_static_messages=counts[f'/{robot}/tf_static'])
    map_samples = {}
    for name in (*robots, 'merge_map'):
        before, after = [np.load(case/f'{name}_{suffix}.npz') for suffix in ('first', 'last')]
        map_samples[name] = dict(width=int(after['width']), height=int(after['height']),
            frame=str(after['frame']), known_cells=int(np.count_nonzero(after['data']>=0)),
            first_last_occupancy_equal=bool(np.array_equal(before['data'], after['data'])))
    commands = {}
    for robot in robots:
        name = f'/{robot}/cmd_vel'
        message = samples[name]
        commands[robot] = dict(count=counts[name], first_command_linear=[message.linear.x, message.linear.y, message.linear.z],
                              first_command_angular=[message.angular.x, message.angular.y, message.angular.z])
    with (case/'drive_diagnostics.csv').open() as stream:
        driver_rows = list(csv.DictReader(stream))
    last_driver = {robot:next(r for r in reversed(driver_rows) if r['robot']==robot) for robot in robots}
    lifecycle = next(e['states'] for e in events if e['kind']=='lifecycle')
    result = dict(status='GAZEBO FIRST ATTEMPT BLOCKED; STOP CERTIFICATION FAILED',
        original_result=json.loads((case/'result.json').read_text()),
        native_exit=json.loads((PROJECT/'evidence/gazebo-rl-01.process-exit.json').read_text()),
        first_utc=events[0]['utc'], last_utc=events[-1]['utc'], lifecycle=lifecycle,
        relevant_events=[e for e in events if e['kind'] in ('error', 'cancel_all', 'navigation_pause',
            'stop_error', 'emergency_physics_pause', 'process_signal', 'process_exit', 'observed_stop')],
        bag_message_count=sum(counts.values()), bag_topic_counts=dict(counts),
        bag_sim_stamp_duration_seconds=(max(x[1] for x in duration)-min(x[0] for x in duration))*1e-9,
        sensor_samples=sensors, model_names_in_first_message=list(samples['/gazebo/model_states'].name),
        maps=map_samples, command_samples=commands, last_driver_rows=last_driver,
        action_status_messages=sum(v for k,v in counts.items() if k.endswith('/_action/status')),
        action_feedback_messages=sum(v for k,v in counts.items() if k.endswith('/_action/feedback')),
        RL_controller_started=(case/'controller').exists(),
        nodes_topics_actions_process_snapshot_stage_reached=(case/'nodes.txt').exists(),
        loaded_driver_inode_capture_stage_reached=(case/'loaded-driver.json').exists(),
        actual_ros_node_init=0, nn_forward=0, env_reset=0, env_step=0, optimizer_step=0,
        new_gazebo_start=0, physical_stop_verified=False,
        caveat='Offline CDR deserialization only. Small settling displacement is not autonomous navigation; emergency physics pause and process disappearance do not establish the required physical-stop certificate. Underlying tb3 lifecycle response timeout is observed, but its transport/startup root cause is not proven.')
    dump(output/'result.json', result)
    print(json.dumps({k:result[k] for k in ('status', 'bag_message_count', 'bag_sim_stamp_duration_seconds',
        'lifecycle', 'sensor_samples', 'action_status_messages', 'action_feedback_messages',
        'RL_controller_started', 'nn_forward', 'new_gazebo_start')}, indent=2))


if __name__=='__main__':
    run()

"""Read only the actual command bag and body trajectory; no ROS node."""
import csv
import json
import math
import sqlite3
from collections import defaultdict
from rclpy.serialization import deserialize_message
from geometry_msgs.msg import Twist
from maps import PROJECT, dump


def run():
    case = PROJECT/'evidence/gazebo-rl-01'
    events = [json.loads(line) for line in (case/'events.jsonl').read_text().splitlines()]
    start = next(e['sim'] for e in events if e['kind']=='smoke_initial_positions')
    end = next(e['sim'] for e in events if e['kind']=='smoke_bound')
    command = defaultdict(lambda:dict(messages=0, max_linear_xy_m_s=0., max_abs_angular_z_rad_s=0.))
    for path in (case/'bag').glob('*.db3'):
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as connection:
            for robot in ('tb1','tb2','tb3'):
                query = 'SELECT m.data FROM messages m JOIN topics t ON m.topic_id=t.id WHERE t.name=?'
                for (data,) in connection.execute(query,(f'/{robot}/cmd_vel',)):
                    msg = deserialize_message(data,Twist)
                    row = command[robot]
                    row['messages'] += 1
                    row['max_linear_xy_m_s'] = max(row['max_linear_xy_m_s'],math.hypot(msg.linear.x,msg.linear.y))
                    row['max_abs_angular_z_rad_s'] = max(row['max_abs_angular_z_rad_s'],abs(msg.angular.z))
    body = defaultdict(lambda:dict(samples=0,max_linear_xy_m_s=0.,max_abs_angular_z_rad_s=0.))
    with (case/'trajectories.csv').open() as stream:
        for sample in csv.DictReader(stream):
            if not start<=float(sample['sim_s'])<=end:
                continue
            row = body[sample['robot']]
            row['samples'] += 1
            row['max_linear_xy_m_s'] = max(row['max_linear_xy_m_s'],float(sample['speed_xy']))
            row['max_abs_angular_z_rad_s'] = max(row['max_abs_angular_z_rad_s'],abs(float(sample['angular_z'])))
    dump(PROJECT/'evidence/command-body-audit.json',dict(command=dict(command),
        actual_autonomous_body=dict(body),autonomous_sim_interval=[start,end],
        actual_ros_node_init=0,nn_forward=0,env_reset=0,env_step=0,new_Gazebo_start=0,
        interpretation='Actual body peaks differ from nominal/proxy dynamics. No dynamics cause inferred; no hardware or hard physical-speed guarantee. Command bag includes startup and stop zeros.'))
    print(json.dumps(dict(command=dict(command),actual_autonomous_body=dict(body)),indent=2))


if __name__=='__main__':
    run()

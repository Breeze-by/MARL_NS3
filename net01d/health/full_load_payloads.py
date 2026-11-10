"""Prepare six immutable Grid content templates; no ROS import or node.

The old bag is opened read-only. These are payload templates for explicitly new
synthetic observations, never replayed historical data labelled as fresh SLAM.
"""
import argparse
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bag',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--template-after-sim',type=float,default=50.64)
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    manifest = dict(bag=str(args.bag.resolve()),after_bag_timestamp_ns=round(args.template_after_sim*1e9),
        scope='Exact old Grid CDR content templates, not current SLAM observations',templates={})
    with sqlite3.connect(args.bag.resolve().as_uri()+'?mode=ro',uri=True) as connection:
        for robot in (1,2,3):
            for kind,suffix in (('map','map'),('costmap','local_costmap/costmap')):
                topic = f'/tb{robot}/{suffix}'
                topic_id,typ = connection.execute('SELECT id,type FROM topics WHERE name=?',(topic,)).fetchone()
                if typ != 'nav_msgs/msg/OccupancyGrid':
                    raise ValueError((topic,typ))
                row = connection.execute('SELECT id,timestamp,data FROM messages WHERE topic_id=? AND timestamp>=? ORDER BY timestamp,id LIMIT 1',
                    (topic_id,manifest['after_bag_timestamp_ns'])).fetchone()
                if row is None:
                    raise ValueError('No historical content template at requested time: '+topic)
                message_id,stamp,body = row
                filename = f'tb{robot}-{kind}.cdr'
                with (args.out/filename).open('xb') as stream:
                    stream.write(body)
                manifest['templates'][f'{robot}:{kind}'] = dict(topic=topic,type=typ,bag_message_id=message_id,
                    bag_record_timestamp_ns=stamp,complete_CDR_bytes=len(body),file=filename)
    with (args.out/'manifest.json').open('x') as stream:
        json.dump(manifest,stream,indent=2);stream.write('\n')
    print(json.dumps(manifest),flush=True)


if __name__=='__main__':
    main()

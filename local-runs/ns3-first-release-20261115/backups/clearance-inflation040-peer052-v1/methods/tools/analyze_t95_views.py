"""Offline T95 at three observation boundaries; never starts ROS or simulators."""
import argparse
from contextlib import closing
import csv
import heapq
import json
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'workspace/gz01'))
sys.path.insert(0, str(ROOT / 'workspace/src/multi_robot_exploration'))
import numpy as np
from metrics import load_reference, measure, sample_received

ROBOTS = ('tb1', 'tb2', 'tb3')
MAP_TOPICS = ('/merge_map', *(f'/{robot}/map' for robot in ROBOTS))


def map_records(directory):
    """Read only the four map topics, once per sqlite shard, in receipt order."""
    import yaml
    metadata = yaml.safe_load((directory / 'metadata.yaml').read_text())['rosbag2_bagfile_information']
    if metadata['storage_identifier'] != 'sqlite3':
        raise ValueError('T95 reader requires sqlite3 bags')
    from contextlib import ExitStack
    with ExitStack() as stack:
        streams = []
        for shard, name in enumerate(metadata['relative_file_paths']):
            connection = stack.enter_context(closing(sqlite3.connect(
                'file:' + str(directory / name) + '?mode=ro', uri=True)))
            topics = {row[0]: row[1] for row in connection.execute('SELECT id,name FROM topics')
                      if row[1] in MAP_TOPICS}
            if not topics:
                continue
            query = ('SELECT timestamp,id,topic_id,data FROM messages WHERE topic_id IN ('
                     + ','.join('?' for _ in topics) + ') ORDER BY timestamp,id')
            def rows(connection=connection, topics=topics, query=query, shard=shard):
                for timestamp, identity, topic, body in connection.execute(query, tuple(topics)):
                    yield timestamp, shard, identity, topics[topic], body
            streams.append(rows())
        for timestamp, shard, identity, topic, body in heapq.merge(*streams, key=lambda row: row[:3]):
            yield timestamp / 1e9, topic, body


def sampled_map(message, reference, position=None):
    grid = np.asarray(message.data, dtype=np.int16).reshape(message.info.height, message.info.width)
    origin = message.info.origin
    q = origin.orientation
    angle = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    expected_frame = 'map' if position is not None else 'merge_map'
    if message.header.frame_id != expected_frame:
        raise ValueError('Unexpected map frame: ' + message.header.frame_id)
    x, y = origin.position.x, origin.position.y
    if position is not None:
        x += position[0]
        y += position[1]
    return sample_received(grid, message.info.resolution, (x, y, angle), reference)


def union_latest(samples):
    """Latest local snapshots: free union, occupied where no robot reports free."""
    grids = np.stack(list(samples.values()))
    return np.where(np.any(grids == 0, axis=0), 0,
                    np.where(np.any(grids == 100, axis=0), 100, -1))


class View:
    def __init__(self, name, start, end, budget):
        self.name, self.start, self.end, self.budget = name, start, end, budget
        self.baseline = None
        self.curve = []
        self.last_event_sim = None

    def observe(self, event_sim, measured, sources):
        if self.last_event_sim is not None and event_sim < self.last_event_sim:
            raise ValueError('Nonmonotonic observation time in ' + self.name)
        self.last_event_sim = event_sim
        row = dict(observation_sim=event_sim, elapsed_sim_s=event_sim - self.start,
                   coverage=measured['coverage'], map_quality_valid=measured['map_quality_valid'],
                   map_quality_warnings=measured['map_quality_warnings'], sources=sources)
        if event_sim <= self.start:
            self.baseline = row
        elif event_sim <= min(self.end, self.start + self.budget):
            self.curve.append(row)

    def rows(self):
        return ([] if self.baseline is None else [dict(self.baseline, elapsed_sim_s=0.)]) + self.curve

    def summary(self, missing_sources=()):
        rows = self.rows()
        hit = next((row for row in rows if row['map_quality_valid'] and row['coverage'] >= .95), None)
        if missing_sources or not rows:
            status = 'missing_data'
            hit = None
        elif hit:
            status = 'reached'
        elif self.end - self.start + 1e-8 < self.budget:
            status = 'not_reached_early_stop'
        else:
            status = 'not_reached_within_budget'
        return dict(status=status, T95_sim_s=None if hit is None else hit['elapsed_sim_s'],
                    threshold_observation=None if hit is None else hit,
                    task_coverage_complete=status == 'reached',
                    initial_sample_available=self.baseline is not None,
                    samples_including_baseline=len(rows), missing_sources=list(missing_sources),
                    last_observation=None if not rows else rows[-1],
                    natural_completion_verified=False)


def analyze(args):
    from nav_msgs.msg import OccupancyGrid
    from rclpy.serialization import deserialize_message
    with (args.case / 'events.jsonl').open() as stream:
        events = [json.loads(line) for line in stream]
    start_event, = (row for row in events if row['kind'] == 'exploration_command')
    start = start_event['sim']
    stop_event = next(row for row in events if row['kind'] in ('smoke_bound', 'error')
                      and row['sim'] is not None and row['sim'] >= start)
    end = stop_event['sim']
    run = json.loads((args.case / 'result.json').read_text())
    positions = tuple(tuple(map(float, value.split(','))) for value in args.positions.split(';'))
    if len(positions) != len(ROBOTS) or any(len(value) != 2 for value in positions):
        raise ValueError('Supply three declared x,y positions in tb1/tb2/tb3 order')
    reference, boundary = load_reference(args.world, args.assets, positions)
    views = {name: View(name, start, end, args.budget_s)
             for name in ('local_union', 'central_merged', 'robot_received')}
    latest, sources, bag_counts = {}, {}, {topic: 0 for topic in MAP_TOPICS}
    for time, topic, body in map_records(args.case / 'bag'):
        if time > min(end, start + args.budget_s):
            break
        bag_counts[topic] += 1
        message = deserialize_message(body, OccupancyGrid)
        stamp = message.header.stamp.sec + message.header.stamp.nanosec / 1e9
        source = dict(topic=topic, header_stamp_sim=stamp, observation_sim=time,
                      timing='R bag receipt; not source generation')
        if topic == '/merge_map':
            sample = sampled_map(message, reference)
            views['robot_received'].observe(time, measure(sample, reference), [source])
        else:
            robot = topic.split('/')[1]
            latest[robot] = sampled_map(message, reference, positions[ROBOTS.index(robot)])
            sources[robot] = source
            if len(latest) == len(ROBOTS):
                views['local_union'].observe(time, measure(union_latest(latest), reference),
                                             [sources[robot] for robot in ROBOTS])
    capture = args.central_capture or args.case / 'central-map-capture'
    central_count = 0
    central_missing = []
    if (capture / 'index.json').is_file():
        index = json.loads((capture / 'index.json').read_text())
        for row in index['samples']:
            if 'capture_node_sim_ns' not in row:
                central_missing.append('capture_node_sim_ns')
                break
            time = row['capture_node_sim_ns'] / 1e9
            if time > min(end, start + args.budget_s):
                break
            message = deserialize_message((capture / row['cdr_file']).read_bytes(), OccupancyGrid)
            central_count += 1
            source = dict(topic='/merge_map', header_stamp_sim=message.header.stamp.sec
                          + message.header.stamp.nanosec / 1e9,
                          observation_sim=time, cdr_file=row['cdr_file'],
                          timing=f"Central application callback side={index.get('capture_side','C')}, domain={index.get('central_application_domain',91)}; not merge generation or policy consumption")
            views['central_merged'].observe(time, measure(sampled_map(message, reference), reference), [source])
    else:
        central_missing.append('central-map-capture/index.json')
    missing = {'local_union': [robot for robot in ROBOTS if robot not in latest],
               'central_merged': central_missing, 'robot_received': []}
    summary = dict(metric='first observed quality-valid coverage >= 0.95',
                   case=str(args.case), start_sim=start, observed_end_sim=end,
                   maximum_budget_sim_s=args.budget_s, observed_window_sim_s=end - start,
                   end_reason=stop_event.get('reason', 'fatal_error'),
                   original_run_error=run.get('error'), original_run_integrity=run.get('run_integrity'),
                   reference_free_cells=int(reference.reference_free.sum()),
                   reference_free_area_m2=float(reference.reference_free.sum()) * reference.resolution ** 2,
                   boundary_connected_cells=boundary,
                   input_counts=dict(bag_maps=bag_counts, central_captures=central_count),
                   views={name: view.summary(missing[name]) for name, view in views.items()},
                   semantics=['Observation times are separate from map header stamps; no backdating.',
                              'Local union uses each robot latest recorded map, not an ever-seen accumulation.',
                              'Quality gates and declared common alignment reuse workspace/gz01/metrics.py.',
                              'T95 is sampled threshold attainment, not exact continuous crossing or natural termination.',
                              'Reached T95 does not erase later run failures; missing and unreached remain explicit.',
                              'Central callback is at the declared application domain; direct A0 has no modeled downlink. It is not merge producer or policy consumer.',
                              'No interpolation, tail extension, source-time inference or policy input changes.'])
    args.output.mkdir(parents=True, exist_ok=False)
    for name, view in views.items():
        with (args.output / (name + '.csv')).open('x') as stream:
            writer = csv.DictWriter(stream, fieldnames=('observation_sim', 'elapsed_sim_s', 'coverage',
                                                       'map_quality_valid', 'map_quality_warnings', 'sources'))
            writer.writeheader()
            for row in view.rows():
                writer.writerow(dict(row, sources=json.dumps(row['sources'], separators=(',', ':')),
                                     map_quality_warnings=json.dumps(row['map_quality_warnings'])))
    (args.output / 'result.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: {key: value for key, value in result.items()
                            if key in ('status', 'T95_sim_s', 'missing_sources')}
                      for name, result in summary['views'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--positions', required=True)
    parser.add_argument('--central-capture', type=Path)
    parser.add_argument('--budget-s', type=float, default=180.)
    parser.add_argument('--output', type=Path, required=True)
    analyze(parser.parse_args())

"""Bounded offline original-CDR corpus extraction; no ROS/native/model imports.

Inert unless explicitly invoked after Root admission. This corpus is a new
denominator of recorded inputs, not a reconstruction of original publisher loss.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time


REPO = Path(__file__).resolve().parents[2]
CASE = REPO / 'net01d/followup04/runs/gz-simhealth-b1-02'
START_NS = 50_000_000_000
END_NS = 60_000_000_000
MAX_BODY_BYTES = 64 * 1024 * 1024
MAX_NORMAL = 20_000


def specs():
    result = {}
    for robot in (1, 2, 3):
        for suffix, offset, typ, prelude in (
            ('map', 1, 'nav_msgs/msg/OccupancyGrid', 'latest'),
            ('odom', 2, 'nav_msgs/msg/Odometry', None),
            ('tf', 3, 'tf2_msgs/msg/TFMessage', None),
            ('tf_static', 4, 'tf2_msgs/msg/TFMessage', 'all'),
            ('local_costmap/costmap', 5, 'nav_msgs/msg/OccupancyGrid', None),
            ('cmd_vel', 6, 'geometry_msgs/msg/Twist', None),
            ('peer_keepout_filter_info', 12, 'nav2_msgs/msg/CostmapFilterInfo', 'latest'),
            ('navigate_to_pose/_action/feedback', 206,
             'nav2_msgs/action/NavigateToPose_FeedbackMessage', None),
            ('navigate_to_pose/_action/status', 207, 'action_msgs/msg/GoalStatusArray', None),
        ):
            down = offset == 12
            result[f'/tb{robot}/{suffix}'] = dict(
                flow=robot * 20 + offset, sender=0 if down else robot,
                receiver=robot if down else 0, type=typ, prelude=prelude,
                role='business', provenance='historical_R_recorder')
    result['/peer_keepout_state'] = dict(
        flow=None, type='std_msgs/msg/String', prelude=None, role='business',
        provenance='historical_R_delivered_health',
        fanout=[dict(flow=r * 20 + 11, sender=0, receiver=r) for r in (1, 2, 3)])
    result['/clock'] = dict(flow=None, type='rosgraph_msgs/msg/Clock',
                           prelude=None, role='clock_control', provenance='historical_R_recorder')
    return result


def extract(output):
    output.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic_ns()
    manifest = dict(
        status='INCOMPLETE', scope='Finite original recorded CDR input corpus, not full historical traffic',
        source=str(CASE / 'bag/bag_0.db3'), source_runtime='aae271f49a8d041285b9a903b3f58d9546985574',
        normal_interval_ns=[START_NS, END_NS], maximum_body_bytes=MAX_BODY_BYTES,
        maximum_normal_records=MAX_NORMAL, database_opens=0,
        body_bytes=0, records=0, counts={},
        missing_original_business=['bound_mask_30_50_70', 'Action_service_requests_responses_RPC_ACK',
                                   'C_health_full_source_before_original_network', 'flow95_exact_wire_capture'],
        interpretation='Original recorder time and CDR preserved. Headers not decoded or refreshed. '
                       'No original publication-rate/loss or complete-system qualification claim.')
    counts = Counter()
    normal_count = 0
    selected = specs()
    try:
        with (output / 'bodies.bin').open('xb') as bodies, (output / 'records.jsonl').open('x') as index:
            def append(body, row):
                nonlocal normal_count
                if row['phase'] == 'normal':
                    normal_count += 1
                    if normal_count > MAX_NORMAL:
                        raise ValueError('normal-record extraction cap exceeded; corpus invalid')
                if manifest['body_bytes'] + len(body) > MAX_BODY_BYTES:
                    raise ValueError('body-byte extraction cap exceeded; corpus invalid')
                row.update(ordinal=manifest['records'], body_offset=manifest['body_bytes'], body_bytes=len(body),
                           original_header_decoded=False, source_stamp_available=None)
                bodies.write(body)
                index.write(json.dumps(row, separators=(',', ':')) + '\n')
                manifest['body_bytes'] += len(body)
                manifest['records'] += 1
                counts[(row['phase'], row['topic'])] += 1

            database = CASE / 'bag/bag_0.db3'
            manifest['database_opens'] += 1
            with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
                topics = {name: (tid, typ) for tid, name, typ in
                          connection.execute('SELECT id,name,type FROM topics')}
                for name, spec in selected.items():
                    tid, typ = topics[name]
                    if typ != spec['type']:
                        raise ValueError(f'topic type mismatch: {name}: {typ}')
                    prelude = spec['prelude']
                    if prelude:
                        order = 'ASC' if prelude == 'all' else 'DESC'
                        limit = ' LIMIT 1001' if prelude == 'all' else ' LIMIT 1'
                        rows = connection.execute(
                            'SELECT id,timestamp,data FROM messages WHERE topic_id=? AND timestamp<? '
                            f'ORDER BY timestamp {order},id {order}' + limit, (tid, START_NS))
                        prelude_count = 0
                        for mid, timestamp, body in rows:
                            prelude_count += 1
                            if prelude_count > 1000:
                                raise ValueError('static TF prelude cap exceeded')
                            append(body, dict(spec, topic=name, phase='prelude', source_file='bag/bag_0.db3',
                                              source_record_id=mid, original_record_ns=timestamp))
                ids = {topics[name][0]: name for name in selected}
                placeholders = ','.join('?' for _ in ids)
                rows = connection.execute(
                    'SELECT id,topic_id,timestamp,data FROM messages WHERE timestamp>=? AND timestamp<? '
                    f'AND topic_id IN ({placeholders}) ORDER BY timestamp,id',
                    (START_NS, END_NS, *ids))
                for mid, tid, timestamp, body in rows:
                    name = ids[tid]
                    append(body, dict(selected[name], topic=name, phase='normal', source_file='bag/bag_0.db3',
                                      source_record_id=mid, original_record_ns=timestamp))

            capture = CASE / 'central-map-capture'
            source_index = json.loads((capture / 'index.json').read_text())
            for ordinal, sample in enumerate(source_index['samples']):
                timestamp = sample['capture_node_sim_ns']
                if START_NS <= timestamp < END_NS:
                    filename = sample['cdr_file']
                    if Path(filename).name != filename:
                        raise ValueError('capture index is not a direct original CDR filename')
                    body = (capture / filename).read_bytes()
                    if len(body) != sample['bytes']:
                        raise ValueError('C89 original index/body length mismatch')
                    append(body, dict(topic='/merge_map', type='nav_msgs/msg/OccupancyGrid', phase='normal',
                                      flow=89, sender=0, receiver=1, role='business',
                                      provenance='historical_C_Gateway_capture', source_file='central-map-capture/' + filename,
                                      source_record_id=ordinal, original_record_ns=timestamp,
                                      original_capture_metadata=sample))
        manifest['status'] = 'EXTRACTED_NEEDS_TYPED_CORPUS_ADMISSION'
    except BaseException as error:
        manifest.update(status='FAIL', error=repr(error))
        raise
    finally:
        manifest['counts'] = [dict(phase=phase, topic=topic, count=count)
                              for (phase, topic), count in sorted(counts.items())]
        manifest.update(normal_records=normal_count, wall_ns=time.monotonic_ns() - begin,
                        output_order='prelude by fixed topic inventory; bag normal timestamp/id; '
                                     'C89 source capture index last. Replay MUST merge normal by '
                                     '(original_record_ns,fixed provenance order,source_record_id), '
                                     'not append ordinal. Prelude excluded from normal denominator.')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    extract(arguments.output)

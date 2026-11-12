"""One fixed closing-tail extraction from sealed B02, no ROS or database writes.

This is real bridge observation/control traffic, including cmd_vel; not an
all-sensor tail. Its ledger stays separate from the original 50..60 main input.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'net01e/replay'))
from extract_bag import CASE, specs

OUT=REPO/'net01e/followup01/tail-corpus-01'
START_NS=60_000_000_000
END_NS=62_000_000_000
MAX_BYTES=16*1024*1024
MAX_RECORDS=5000


def main():
    OUT.mkdir(exist_ok=False)
    begin=time.monotonic_ns()
    selected={name:spec for name,spec in specs().items()
              if spec.get('flow') is not None and spec['flow']<80 and 1<=spec['flow']%20<=6}
    manifest=dict(status='INCOMPLETE',scope='Real original closing bridge observation/control tail, not main test samples',
        source=str(CASE/'bag/bag_0.db3'),source_runtime='aae271f49a8d041285b9a903b3f58d9546985574',
        tail_interval_ns=[START_NS,END_NS],maximum_body_bytes=MAX_BYTES,maximum_records=MAX_RECORDS,
        database_opens=0,body_bytes=0,records=0,counts={})
    try:
        with (OUT/'bodies.bin').open('xb') as bodies,(OUT/'records.jsonl').open('x') as index:
            def emit(body,row):
                if manifest['records']>=MAX_RECORDS or manifest['body_bytes']+len(body)>MAX_BYTES:
                    raise ValueError('Fixed closing-tail extraction bound exceeded; no truncation/retry')
                row.update(ordinal=manifest['records'],phase='tail',purpose='closing_tail',
                    body_offset=manifest['body_bytes'],body_bytes=len(body),original_header_decoded=False)
                bodies.write(body);index.write(json.dumps(row,separators=(',',':'))+'\n')
                manifest['records']+=1;manifest['body_bytes']+=len(body)
                manifest['counts'][row['topic']]=manifest['counts'].get(row['topic'],0)+1
            manifest['database_opens']+=1
            with closing(sqlite3.connect((CASE/'bag/bag_0.db3').resolve().as_uri()+'?mode=ro',uri=True)) as connection:
                topics={name:(tid,typ) for tid,name,typ in connection.execute('SELECT id,name,type FROM topics')}
                for name,spec in selected.items():
                    if topics[name][1]!=spec['type']:raise ValueError('Original topic type mismatch: '+name)
                ids={topics[name][0]:name for name in selected}
                placeholders=','.join('?' for _ in ids)
                query=('SELECT id,topic_id,timestamp,data FROM messages WHERE timestamp>=? AND timestamp<? '
                    f'AND topic_id IN ({placeholders}) ORDER BY timestamp,id')
                for mid,tid,stamp,body in connection.execute(query,(START_NS,END_NS,*ids)):
                    name=ids[tid]
                    emit(body,dict(selected[name],topic=name,source_file='bag/bag_0.db3',
                        source_record_id=mid,original_record_ns=stamp))
            capture=CASE/'central-map-capture'
            samples=json.loads((capture/'index.json').read_text())['samples']
            for ordinal,sample in enumerate(samples):
                stamp=sample['capture_node_sim_ns']
                if START_NS<=stamp<END_NS:
                    filename=sample['cdr_file']
                    if Path(filename).name!=filename:raise ValueError('Non-direct original C89 filename')
                    body=(capture/filename).read_bytes()
                    if len(body)!=sample['bytes']:raise ValueError('Original C89 body length mismatch')
                    emit(body,dict(flow=89,sender=0,receiver=1,topic='/merge_map',type='nav_msgs/msg/OccupancyGrid',
                        role='business',provenance='historical_C_Gateway_capture',source_file='central-map-capture/'+filename,
                        source_record_id=ordinal,original_record_ns=stamp,original_capture_metadata=sample))
        manifest['status']='EXTRACTED_TAIL_NEEDS_TYPED_STARTUP_VALIDATION'
    except BaseException as error:
        manifest.update(status='FAIL',error=repr(error));raise
    finally:
        manifest['wall_ns']=time.monotonic_ns()-begin
        manifest['order']='Bag timestamp/id then C89 index; runtime merges by original_record_ns/provenance/source_record_id.'
        (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()

"""Read sealed A02 four topics in 145..150sim only; no Node or replay."""
from collections import defaultdict,deque
import json
from pathlib import Path
import sqlite3
import statistics

from rclpy.serialization import deserialize_message
from tf2_msgs.msg import TFMessage
from rosgraph_msgs.msg import Clock


def main():
    case=Path('/mnt/runs/net01-a-corridor-6201-02')
    out=Path(__file__).with_name('TF_CHAIN_145_150.json')
    names=['/clock']+[f'/tb{r}/tf' for r in (1,2,3)]
    con=sqlite3.connect('file:'+str(case/'bag/bag_0.db3')+'?mode=ro',uri=True)
    ids={n:i for i,n in con.execute('SELECT id,name FROM topics') if n in names}
    selected=list(con.execute('SELECT topic_id,timestamp,data FROM messages WHERE timestamp BETWEEN ? AND ? AND topic_id IN (?,?,?,?) ORDER BY timestamp,id',
        (145_000_000_000,150_000_000_000,*ids.values())))
    if len(selected)>2500:raise RuntimeError('Explicit narrow decode cap2500 exceeded; do not expand automatically')
    by_id={i:n for n,i in ids.items()};clock=[];corrections=defaultdict(list)
    for topic,receipt,data in selected:
        name=by_id[topic]
        if name=='/clock':
            m=deserialize_message(data,Clock)
            clock.append(dict(bag_receipt_sim=receipt/1e9,clock=m.clock.sec+m.clock.nanosec/1e9))
        else:
            m=deserialize_message(data,TFMessage)
            for t in m.transforms:
                if t.header.frame_id=='map' and t.child_frame_id=='odom':
                    corrections[name.split('/')[1]].append(dict(bag_receipt_sim=receipt/1e9,
                        source_header=t.header.stamp.sec+t.header.stamp.nanosec/1e9,
                        translation=[t.transform.translation.x,t.transform.translation.y,t.transform.translation.z],
                        quaternion=[t.transform.rotation.x,t.transform.rotation.y,t.transform.rotation.z,t.transform.rotation.w]))
    con.close()
    peer=[json.loads(x) for x in (case/'peer-keepout.jsonl').read_text().splitlines()]
    peer=[p for p in peer if 145<=p['generated_sim']<=150]
    comparisons=[]
    for p in peer:
        if round(p['generated_sim']*10)%5 and abs(p['generated_sim']-149.3)>1e-5:continue
        for r in ('tb1','tb2','tb3'):
            available=[t for t in corrections[r] if t['bag_receipt_sim']<=p['generated_sim']+1e-6]
            latest=max(available,key=lambda t:t['source_header']) if available else None
            comparisons.append(dict(robot=r,producer_sim=p['generated_sim'],Peer_C_header=p['correction_stamps'][r],
                Peer_C_age=p['ages'][r]['correction'],Peer_C_receipt_age_wall=p['ages'][r]['correction_receipt'],
                latest_available_R_bag=latest))
    gateway=json.loads((case/'network-gateway.json').read_text())
    queues=defaultdict(deque)
    for row in gateway['topics']['R']['captured']:
        if row['flow'] in (23,43,63):queues[(row['flow'],row['cdr_sha256'])].append(row)
    lo=peer[0]['delivery_timing']['entry_monotonic']*1e9
    hi=peer[-1]['delivery_timing']['entry_monotonic']*1e9
    delays=defaultdict(list);unmatched=[]
    for row in gateway['topics']['C']['delivered']:
        if row['flow'] not in (23,43,63):continue
        q=queues[(row['flow'],row['cdr_sha256'])]
        capture=q.popleft() if q else None
        stamp=row['endpoint_publish_monotonic_ns']
        if lo<=stamp<=hi:
            if capture is None:unmatched.append(row)
            else:delays[str(row['flow'])].append((stamp-capture['endpoint_capture_monotonic_ns'])/1e6)
    result=dict(scope='One sealed A02 bag 145..150sim /clock and three /tf only; no Node/NN/replay/GZ',
        decoded_messages=len(selected),decode_cap=2500,clock=clock,raw_R_corrections=dict(corrections),
        sampled_header_comparisons=comparisons,
        actual_capture_to_C_publish_wall_ms={f:dict(n=len(v),min=min(v),median=statistics.median(v),max=max(v)) for f,v in delays.items()},
        unmatched_same_capture_CDR=len(unmatched),
        limits=['R bag receipt is not Peer private ACK; exact same-sequence publisher receipt wall unknown',
            'CDR hashes only match actual one captured payload against its delivered bytes, never separate DDS serializers',
            'No QoS/source stamp/SLAM/TTL change or automatic rerun'])
    with out.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(dict(decoded_messages=len(selected),correction_counts={k:len(v) for k,v in corrections.items()},
        captured_delivery=result['actual_capture_to_C_publish_wall_ms'],at1493=[x for x in comparisons if abs(x['producer_sim']-149.3)<1e-5])),flush=True)


if __name__=='__main__':main()

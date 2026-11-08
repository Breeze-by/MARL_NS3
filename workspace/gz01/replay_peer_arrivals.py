"""Replay sealed slot3 tb2 arrivals through actual callbacks/TF2; no ROS Node."""
import heapq
import json
from pathlib import Path
import sqlite3
import types

import yaml
from rclpy.serialization import deserialize_message
from rclpy.duration import Duration
from rosidl_runtime_py.utilities import get_message
from tf2_ros import Buffer
from peer_keepout import PeerKeepout, state_fresh

ROOT=Path('/mnt')
CASE=ROOT/'runs/peer-open-ring-traditional-01'


def main():
    peer=types.SimpleNamespace(odom={},received={},tf={'tb2':Buffer(cache_time=Duration(seconds=15))},
        poses={},valid_stamps={},valid_receipts={},pending_tf={})
    for name in ('receive_odom','receive_tf','project_latest'):
        setattr(peer,name,types.MethodType(getattr(PeerKeepout,name),peer))
    metadata=yaml.safe_load((CASE/'bag/metadata.yaml').read_text())['rosbag2_bagfile_information']
    connections=[];streams=[];receipts={};samples=[];counts={}
    topics={'/clock','/tb2/odom','/tb2/tf','/tb2/tf_static'}
    try:
        for shard,filename in enumerate(metadata['relative_file_paths']):
            db=sqlite3.connect('file:'+str(CASE/'bag'/filename)+'?mode=ro',uri=True);connections.append(db)
            table={i:(n,t) for i,n,t in db.execute('SELECT id,name,type FROM topics') if n in topics}
            query='SELECT timestamp,id,topic_id,data FROM messages WHERE topic_id IN ('+','.join('?' for i in table)+') AND timestamp<=? ORDER BY timestamp,id'
            def records(db=db,table=table,shard=shard):
                for stamp,id_,topic,data in db.execute(query,[*table,32_600_000_000]):yield stamp,shard,id_,*table[topic],data
            streams.append(records())
        for stamp,shard,id_,topic,type_,data in heapq.merge(*streams,key=lambda r:r[:3]):
            msg=deserialize_message(data,get_message(type_));counts[topic]=counts.get(topic,0)+1
            if topic=='/tb2/odom':
                peer.receive_odom(msg,'tb2')
                receipts[msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9]=peer.received['tb2']
            elif topic.endswith('/tf_static'):peer.receive_tf(msg,'tb2',True)
            elif topic.endswith('/tf'):peer.receive_tf(msg,'tb2',False)
            else:
                clock=msg.clock.sec+msg.clock.nanosec*1e-9
                if 32.2-1e-6<=clock<=32.5+1e-6:
                    samples.append(dict(clock_sim=clock,valid_pose_source=peer.valid_stamps.get('tb2'),
                        source_age=clock-peer.valid_stamps['tb2'],pending_tf=peer.pending_tf.copy()))
            if 'tb2' in peer.valid_stamps:
                assert peer.valid_receipts['tb2']==receipts[peer.valid_stamps['tb2']]
        snapshot=next(r for r in samples if abs(r['clock_sim']-32.4)<1e-6)
        state=dict(ready=True,generated_sim=32.4,ages={'tb2':dict(source=snapshot['source_age'])})
        assert state_fresh(state,32.5)
        out=dict(passed=True,source='sealedslot3 filtered clock/tb2 odom/tf/tf_static in recorder arrival order',
            callbacks='actual PeerKeepout functions + installed tf2_ros.Buffer; no Node, no NN, no Gazebo',counts=counts,
            samples=samples,new_snapshot_passes_original_02_at_observer_325=True,original_stamp_and_receipt_preserved=True,
            original_recorded_generated_324_source_age=.107,
            limitations='Recorder arrival order is not exact producer or Observer executor order. Original Observer sequence not recorded; replay shows the causal correction, not unique historical callback attribution.')
        (ROOT/'evidence/peer-arrival-replay-01.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
    finally:
        for db in connections:db.close()


if __name__=='__main__':main()

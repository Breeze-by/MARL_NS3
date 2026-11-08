"""Read-only prior bag order replay in actual tf2 Buffers; no Node/init/control/model."""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import time
from rclpy.serialization import deserialize_message
from rclpy.time import Time
from rclpy.duration import Duration
from rosidl_runtime_py.utilities import get_message
from tf2_ros import Buffer, TransformException


def run():
    start=time.monotonic()
    prior=Path('/tmp/prior/evidence/gazebo-rl-01')
    output=Path('/mnt/evidence/pose-bag-replay-02');output.mkdir(exist_ok=False)
    calls=[r for s in (prior/'controller/allocation-events.jsonl').read_text().splitlines()
           if (r:=json.loads(s))['kind']=='rl03_allocation_wall']
    buffers={r:Buffer(cache_time=Duration(seconds=15)) for r in ('tb1','tb2','tb3')}
    latest_good=dict.fromkeys(buffers)
    latest_ok=dict.fromkeys(buffers,False)
    latest_error=dict.fromkeys(buffers)
    counts=Counter();examples={};checks=[];cursor=0
    def sample(call):
        old={r:latest_ok[r] for r in buffers}
        # Match the existing guard exactly (age>2 rejects). Bag clock samples
        # can precede message header stamps slightly; do not add an age>=0 rule.
        retained={r:latest_good[r] is not None and call['sim']-latest_good[r]<=2. for r in buffers}
        checks.append(dict(sim=call['sim'],actual_state=call['state'],
            old_bag_order_available=all(old.values()),retained_fresh_available=all(retained.values()),
            latest_good_stamp=latest_good.copy(),latest_odom_tf_ok=old,last_error=latest_error.copy()))
    database=prior/'bag/bag_0.db3'
    connection=sqlite3.connect('file:'+str(database)+'?mode=ro&immutable=1',uri=True)
    topics={row[0]:(row[1],get_message(row[2])) for row in connection.execute('SELECT id,name,type FROM topics')
        if row[1] in [f'/{r}/{t}' for r in buffers for t in ('tf','tf_static','odom')]}
    ids=','.join(str(k) for k in topics)
    for stamp,topic_id,data in connection.execute(f'SELECT timestamp,topic_id,data FROM messages WHERE topic_id IN ({ids}) ORDER BY timestamp,id'):
        sim=stamp/1e9
        while cursor<len(calls) and calls[cursor]['sim']<sim:
            sample(calls[cursor]);cursor+=1
        topic,cls=topics[topic_id];robot=topic.split('/')[1];msg=deserialize_message(data,cls)
        if topic.endswith('/odom'):
            counts[robot+'_odom']+=1
            try:buffers[robot].lookup_transform('merge_map',msg.header.frame_id,Time.from_msg(msg.header.stamp))
            except TransformException as error:
                latest_ok[robot]=False;latest_error[robot]=type(error).__name__
                counts[robot+'_lookup_failed']+=1;counts[type(error).__name__]+=1
                direction='future' if 'into the future' in str(error) else 'past' if 'into the past' in str(error) else 'other'
                counts['lookup_failure_'+direction]+=1
                key=robot+'_'+type(error).__name__+'_'+direction
                if key not in examples:examples[key]=dict(bag_sim=sim,odom_stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9,error=str(error))
            else:
                latest_ok[robot]=True;latest_error[robot]=None
                latest_good[robot]=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
                counts[robot+'_lookup_success']+=1
        else:
            for transform in msg.transforms:
                if topic.endswith('/tf_static'):buffers[robot].set_transform_static(transform,robot)
                else:buffers[robot].set_transform(transform,robot)
    connection.close()
    while cursor<len(calls):sample(calls[cursor]);cursor+=1
    result=dict(status='READ-ONLY TF2 BAG ORDER REPLAY COMPLETE',counts=dict(counts),first_error_examples=examples,
        callback_samples=checks,actual_callback_states=dict(Counter(r['state'] for r in calls)),
        old_bag_order_ready=sum(r['old_bag_order_available'] for r in checks),
        retained_fresh_ready=sum(r['retained_fresh_available'] for r in checks),
        caveat='Bag recorder receive order is not the controller executor delivery order; this is a mechanism replay, not an exact reproduction of its28waits. All transforms are exact odom-stamp lookups, no latest-TF fallback.',
        unchanged_freshness_s=2.,ros_nodes_created=0,rclpy_init=0,nn_forward=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0,
        correction_from_first_replay='First replay incorrectly added age>=0 absent in production. Corrected to original age>2 rule; preserve first artifact as superseded diagnostic, not evidence of0fresh callbacks.',
        wall_seconds=time.monotonic()-start)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='callback_samples'},indent=2))


if __name__=='__main__':run()

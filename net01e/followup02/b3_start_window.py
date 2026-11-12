"""Inspect only G58..62 published grids around the first two failed goals."""
import json
import math
from pathlib import Path
import sqlite3
from rclpy.serialization import deserialize_message
from nav_msgs.msg import OccupancyGrid

root=Path('/mnt/net01e/followup01/gz-runs/corr6201-v2-r03-b')
goals=json.loads(Path('/tmp/analysis/b3-navigation-observations.json').read_text())['goals']
out=[]
db=root/'bag/bag_0.db3'
conn=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
topics={i:n for i,n in conn.execute('SELECT id,name FROM topics') if any(n==f'/{r}/{suffix}' for r in ('tb1','tb2') for suffix in ('map','global_costmap/costmap'))}
rows=0
for tid,stamp,body in conn.execute('SELECT topic_id,timestamp,data FROM messages WHERE timestamp BETWEEN ? AND ? AND topic_id IN ('+','.join('?' for _ in topics)+') ORDER BY timestamp',[58_000_000_000,62_000_000_000]+list(topics)):
    rows+=1;name=topics[tid];robot=name.split('/')[1]
    g=next(g for g in goals if g['robot']==robot and g['token']==3)
    msg=deserialize_message(body,OccupancyGrid);info=msg.info;w,h=info.width,info.height
    item=dict(topic=name,bag_sim=stamp/1e9,header_sim=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9,
              resolution=info.resolution,origin=[info.origin.position.x,info.origin.position.y],
              origin_quaternion=[getattr(info.origin.orientation,k) for k in ('x','y','z','w')],size=[w,h],points={})
    if item['origin_quaternion'] != [0.0,0.0,0.0,1.0]:
        raise ValueError('Axis-aligned diagnostic requires identity grid origin orientation')
    # These same-robot poses differ by only micrometres within this stationary
    # window; retain the reference time rather than imply exact consumption.
    item['pose_reference_sim']=g['samples'][0]['at_sim']
    for label,xy in [('robot',g['samples'][0]['pose']['xy']),('goal',g['actual_map_goal'])]:
        fx=(xy[0]-info.origin.position.x)/info.resolution;fy=(xy[1]-info.origin.position.y)/info.resolution
        p=dict(xy=xy,fractional_cell=[fx,fy])
        for mode,(cx,cy) in [('floor',(math.floor(fx),math.floor(fy))),('navfn_round',(math.floor(fx+.5),math.floor(fy+.5)))]:
            p[mode]=dict(cell=[cx,cy],value=int(msg.data[cy*w+cx]) if 0<=cx<w and 0<=cy<h else None,
                        patch7_rows_low_to_high_y=[[int(msg.data[y*w+x]) if 0<=x<w and 0<=y<h else None for x in range(cx-3,cx+4)] for y in range(cy-3,cy+4)])
        item['points'][label]=p
    out.append(item)
static=[]
from tf2_msgs.msg import TFMessage
for robot in ('tb1','tb2'):
    tid=conn.execute('SELECT id FROM topics WHERE name=?',(f'/{robot}/tf_static',)).fetchone()[0]
    row=conn.execute('SELECT timestamp,data FROM messages WHERE topic_id=? ORDER BY timestamp LIMIT 1',(tid,)).fetchone()
    msg=deserialize_message(row[1],TFMessage)
    for tr in msg.transforms:
        if 'base' in tr.header.frame_id or 'base' in tr.child_frame_id:
            static.append(dict(robot=robot,bag_sim=row[0]/1e9,parent=tr.header.frame_id,child=tr.child_frame_id,
                               translation=[getattr(tr.transform.translation,k) for k in ('x','y','z')],
                               quaternion=[getattr(tr.transform.rotation,k) for k in ('x','y','z','w')]))
conn.close()
Path('/tmp/analysis/b3-start-window-v2.json').write_text(json.dumps(dict(window_sim=[58,62],rows=rows,samples=out,base_static_edges=static,limits=['Grids are published samples, not planner internal snapshots.','Robot point reused from accepted-time recorded TF composition; robots stationary in this window.','Identity grid origin quaternion verified in these sampled messages.','v1 output retained: v2 adds actual origin quaternion check and recorded base static edges.']),indent=2)+'\n')
print(json.dumps(dict(rows=rows,no_ros_init=True)))

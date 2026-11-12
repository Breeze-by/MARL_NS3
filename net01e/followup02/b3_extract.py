"""Read sealed B3 bags without ROS init; summarize navigation observations.

Bag timestamp is recorded ROS simulation time. Published costmaps are samples,
not the planner's mutex-protected internal grid at the instant of planning.
"""
import bisect
from collections import Counter, defaultdict, deque
import json
import math
from pathlib import Path
import sqlite3
import time

from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

ROOT = Path('/mnt')
CASE = ROOT / 'net01e/followup01/gz-runs/corr6201-v2-r03-b'
OUT = Path('/tmp/analysis')
begin = time.monotonic()
chains = json.loads((ROOT / 'net01e/followup01/gz-analysis/corr6201-v2-r03-b/abort-audit-01/summary.json').read_text())['chains']
records = defaultdict(list)
read_counts = Counter()
classes = {}
for db in sorted((CASE / 'bag').glob('*.db3')):
    conn = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    topics = {i: (n, t) for i, n, t in conn.execute('SELECT id,name,type FROM topics')}
    wanted = [i for i, (n, _) in topics.items() if n == '/gazebo/model_states' or
              n == '/peer_keepout_state' or any(n == f'/{r}/{s}' for r in ('tb1','tb2')
              for s in ('map','tf','global_costmap/costmap','local_costmap/costmap','plan','navigate_to_pose/_action/feedback'))]
    query = 'SELECT topic_id,timestamp,data FROM messages WHERE timestamp BETWEEN ? AND ? AND topic_id IN (' + ','.join('?' for _ in wanted) + ') ORDER BY timestamp'
    for tid, stamp, body in conn.execute(query, [54_000_000_000, 180_000_000_000] + wanted):
        name, typ = topics[tid]
        if typ not in classes:
            classes[typ] = get_message(typ)
        msg = deserialize_message(body, classes[typ])
        t = stamp / 1e9
        read_counts[name] += 1
        if name.endswith('/tf'):
            for tr in msg.transforms:
                records[(name, tr.header.frame_id, tr.child_frame_id)].append((t,tr))
        elif name.endswith('/feedback'):
            uuid = bytes(msg.goal_id.uuid).hex()
            f = msg.feedback
            item = dict(sim=t, distance=f.distance_remaining, recoveries=f.number_of_recoveries,
                        nav_time=f.navigation_time.sec+f.navigation_time.nanosec/1e9)
            seq = records[(name,uuid)]
            if not seq or item['recoveries'] != seq[-1][1]['recoveries']:
                seq.append((t,item))
            records[(name,uuid,'last')] = [(t,item)]
        else:
            records[name].append((t,msg))
    conn.close()

def prior(key,t):
    seq=records.get(key,[])
    i=bisect.bisect_right([x[0] for x in seq],t)-1
    return seq[i] if i>=0 else None

def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))

def pose(robot,t):
    keys=[k for k in records if isinstance(k,tuple) and k[0]==f'/{robot}/tf']
    mo=next((prior(k,t) for k in keys if k[1].strip('/')=='map' and k[2].strip('/')=='odom'),None)
    ob=next((prior(k,t) for k in keys if k[1].strip('/')=='odom' and k[2].strip('/') in ('base_footprint','base_link')),None)
    if not mo or not ob:
        return dict(error='no recorded map->odom / odom->base pair',keys=[str(k) for k in keys])
    a,b=mo[1].transform,ob[1].transform
    theta=yaw(a.rotation)
    xy=[a.translation.x+math.cos(theta)*b.translation.x-math.sin(theta)*b.translation.y,
        a.translation.y+math.sin(theta)*b.translation.x+math.cos(theta)*b.translation.y]
    return dict(xy=xy,bag_sim=[mo[0],ob[0]],header_sim=[z[1].header.stamp.sec+z[1].header.stamp.nanosec/1e9 for z in (mo,ob)])

def cell(msg,xy):
    info=msg.info
    a=yaw(info.origin.orientation)
    x,y=xy[0]-info.origin.position.x,xy[1]-info.origin.position.y
    return [math.floor((math.cos(a)*x+math.sin(a)*y)/info.resolution),
            math.floor((-math.sin(a)*x+math.cos(a)*y)/info.resolution)]

def grid_summary(sample,target,start):
    if sample is None:
        return None
    t,msg=sample; w,h=msg.info.width,msg.info.height; gx,gy=cell(msg,target)
    inside=0<=gx<w and 0<=gy<h
    out=dict(bag_sim=t,header_sim=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9,
             frame=msg.header.frame_id,size=[w,h],resolution=msg.info.resolution,
             origin=[msg.info.origin.position.x,msg.info.origin.position.y],goal_cell=[gx,gy],
             goal_value=int(msg.data[gy*w+gx]) if inside else None)
    radius=math.ceil(.5/msg.info.resolution)
    tolerance={y*w+x for y in range(max(0,gy-radius),min(h,gy+radius+1))
               for x in range(max(0,gx-radius),min(w,gx+radius+1))
               if ((x-gx)**2+(y-gy)**2)*msg.info.resolution**2<=.5**2}
    out['tolerance_disk_values']=dict(Counter(int(msg.data[i]) for i in tolerance))
    if start and 'xy' in start:
        sx,sy=cell(msg,start['xy']);out['start_cell']=[sx,sy]
        if 0<=sx<w and 0<=sy<h:
            seed=sy*w+sx;out['start_value']=int(msg.data[seed]);seen={seed};queue=deque([seed])
            # This permissive topology is a diagnostic, not a NavFn reproduction:
            # allow unknown, use 8-neighbours, no diagonal-corner restriction,
            # and seed the robot cell even if that sampled cell is occupied.
            while queue:
                i=queue.popleft();x,y=i%w,i//w
                for ny in range(max(0,y-1),min(h,y+2)):
                    for nx in range(max(0,x-1),min(w,x+2)):
                        j=ny*w+nx
                        if j not in seen and int(msg.data[j])<99:
                            seen.add(j);queue.append(j)
            out['permissive_component_cells']=len(seen)
            out['goal_in_permissive_component']=inside and gy*w+gx in seen
            out['tolerance_reachable_cells']=len(tolerance & seen)
    return out

result=[]
for chain in chains:
    robot=chain['robot'];token=chain['token'];uuid=chain['uuid'][0]
    req=next(x['record'] for x in chain['lifecycle'] if x['record']['kind']=='rl_actual_nav2_goal_request')
    response=next(x['record'] for x in chain['lifecycle'] if x['record']['kind']=='rl_actual_nav2_goal_response')
    a,b=response['sim'],chain['terminal_sim'];goal=req['actual_goal_position'][:2]
    item=dict(robot=robot,token=token,uuid=uuid,request_sim=req['sim'],accepted_sim=a,terminal_sim=b,
              actual_map_goal=goal,merge_goal=req['merge_map_target'],samples=[])
    gc=records[f'/{robot}/global_costmap/costmap']
    times=[a]+[t for t,_ in gc if a<t<=a+2]+[b]
    for t in times:
        p=pose(robot,t)
        item['samples'].append(dict(at_sim=t,pose=p,
          global_costmap=grid_summary(prior(f'/{robot}/global_costmap/costmap',t),goal,p),
          source_map=grid_summary(prior(f'/{robot}/map',t),goal,None)))
    plans=[(t,m) for t,m in records[f'/{robot}/plan'] if a<=t<=b]
    item['plan_messages']=len(plans)
    item['plan_endpoints']=[dict(bag_sim=t,header_sim=m.header.stamp.sec+m.header.stamp.nanosec/1e9,
       size=len(m.poses),end=[m.poses[-1].pose.position.x,m.poses[-1].pose.position.y] if m.poses else None)
       for t,m in (plans[:2]+plans[-2:] if len(plans)>4 else plans)]
    item['recovery_feedback']= [v for _,v in records.get((f'/{robot}/navigate_to_pose/_action/feedback',uuid),[])]
    item['last_feedback']=records.get((f'/{robot}/navigate_to_pose/_action/feedback',uuid,'last'),[])
    models=[(t,m) for t,m in records['/gazebo/model_states'] if a<=t<=b]
    physical={};minimum=float('inf')
    for r in ('tb1','tb2','tb3'):
        pts=[]
        for t,m in models:
            if r in m.name:
                p=m.pose[m.name.index(r)].position;pts.append((t,p.x,p.y))
        if pts:
            physical[r]=dict(first=pts[0],last=pts[-1],path_m=sum(math.hypot(y[1]-x[1],y[2]-x[2]) for x,y in zip(pts,pts[1:])))
    for _,m in models:
        pp=[m.pose[m.name.index(r)].position for r in ('tb1','tb2','tb3') if r in m.name]
        for i,p in enumerate(pp):
            for q in pp[i+1:]:minimum=min(minimum,math.hypot(p.x-q.x,p.y-q.y))
    item['physical_during_goal']=physical
    item['minimum_any_robot_center_distance_m']=minimum if math.isfinite(minimum) else None
    peer=prior('/peer_keepout_state',a)
    if peer:item['peer_state_at_accept']=dict(bag_sim=peer[0],body=json.loads(peer[1].data))
    result.append(item)

output=dict(case=CASE.name,window_sim=[54,180],no_ros_init=True,read_only_sqlite=True,
            original_files_written=False,read_counts=dict(read_counts),wall_s=time.monotonic()-begin,
            tf_keys=[list(k) for k in records if isinstance(k,tuple) and '/tf' in k[0]],goals=result,
            limits=['Published samples are not exact internal planner snapshots.',
                    'Permissive connectivity is not a NavFn solver or causal proof.',
                    'OccupancyGrid 99/100 represent inscribed/lethal cost; unknown -1 allowed in diagnostic flood.',
                    'TF composition uses last recorded edges, not proof of Nav2 callback consumption.'])
(OUT/'b3-navigation-observations.json').write_text(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps(dict(goals=len(result),wall_s=output['wall_s'],read_counts=dict(read_counts))))

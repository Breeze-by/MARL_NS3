"""Saved public DEV observations only; stationary proxy sensors justify local-map reuse."""
from collections import Counter
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

HERE=Path(__file__).resolve().parent;WS=HERE.parent;ROOT=WS.parents[1]
sys.path.insert(0,str(WS/'src/multi_robot_exploration'))
from multi_robot_exploration import frontier
from multi_robot_exploration.allocation import distances


def run():
    output=ROOT/'rl-04/evidence/candidate-stages-02';output.mkdir(exist_ok=False)
    began=time.monotonic();cases=[];counts=Counter()
    public=ROOT/'rl-03/runs/test-01'
    for summary in sorted(public.glob('*/summary.json')):
        saved=json.loads(summary.read_text())
        if saved['policy']!='rl' or saved['all_robot_participation']:continue
        folder=summary.parent;trace=json.loads((folder/'trajectory.json').read_text())
        intents=[json.loads(s) for s in (folder/'intents.jsonl').read_text().splitlines()]
        grids=np.load(folder/'observed-grids.npz')['cells'];locals=np.load(folder/'final-local-maps.npz')
        if len(grids)!=len(intents)+1:raise ValueError('Shared snapshot alignment mismatch')
        for name in ('tb1','tb2','tb3'):
            if saved['accepted'].get(name,0) or saved['paths_m'][name]!=0:continue
            poses=np.array([r['poses'][name] for r in trace])
            if not np.all(poses==poses[0]):raise ValueError('Cannot reuse final local map: stationary premise fails')
            local=locals[name];res=intents[0]['observation']['map']['resolution'];ox,oy=intents[0]['observation']['map']['origin']
            start=(math.floor((poses[0,1]-oy)/res),math.floor((poses[0,0]-ox)/res))
            local_data=frontier.costmap(local,*reversed(local.shape),res)
            local_data[local_data!=0]=1;local_data[start]=0
            local_paths=distances(local_data,start,res);counts['local_Dijkstra']+=1
            own=frontier.costmap(local,*reversed(local.shape),res);own[start]=0;own[own>5]=1
            own,own_groups=frontier.assign_groups(frontier.frontierB(own))
            own_cells=[p for cells in own_groups.values() if len(cells)>2 for p in cells if p in local_paths]
            def point(p):return ((p[1]+.5)*res+ox,(p[0]+.5)*res+oy)
            rows=[]
            for index,intent in enumerate(intents):
                obs=intent['observation'];shared=grids[index]
                if tuple(obs['map']['origin'])!=(ox,oy) or obs['map']['resolution']!=res:raise ValueError('Grid coordinates changed')
                robot=next(r for r in obs['robots'] if r['id']==name)
                if robot['pose']!=poses[0].tolist() or robot['state']!='idle':raise ValueError('Idle pose premise mismatch')
                data=frontier.costmap(shared,*reversed(shared.shape),res);data[start]=0;data[data>5]=1
                data,groups=frontier.assign_groups(frontier.frontierB(data));data[data<0]=1
                global_paths=distances(data,start,res);counts['global_Dijkstra']+=1
                retained={g[0] for g in frontier.fGroups(groups)}
                history=obs['history']
                blocked=[e['target'] for e in history if e['status']=='succeeded' or
                    (e['robot']==name and e['status'] in ('aborted','rejected','invalid_local_goal'))]
                blocked += [r['target'] for r in obs['robots'] if r['target'] is not None]
                details=[];reconstructed=[];all_legal_groups=0
                for gid,cells in sorted(groups.items(),key=lambda x:len(x[1]),reverse=True):
                    if len(cells)<3:continue
                    center=frontier.calculate_centroid([p[0] for p in cells],[p[1] for p in cells])
                    stages=[cells]
                    stages.append([p for p in stages[-1] if p in global_paths])
                    stages.append([p for p in stages[-1] if local[p]==0])
                    stages.append([p for p in stages[-1] if p in local_paths])
                    stages.append([p for p in stages[-1] if local_paths[p]<=90*.26])
                    stages.append([p for p in stages[-1] if not any(math.dist(point(p),q)<.2 for q in blocked)])
                    stages.append([p for p in stages[-1] if robot['last_success'] is None or math.dist(point(p),robot['last_success'])>=.5])
                    legal=stages[-1];all_legal_groups+=bool(legal)
                    if legal and gid in retained:
                        chosen=min(legal,key=lambda p:((p[0]-center[0])**2+(p[1]-center[1])**2,p))
                        reconstructed.append((gid,point(chosen)))
                    details.append(dict(group=gid,retained_top5=gid in retained,
                        counts=dict(zip(['raw_frontier','shared_reachable','own_known_free','own_reachable','path_budget','memory','last_success'],map(len,stages)))))
                recorded=[c for c in obs['candidates'] if c['robot']==name]
                if sorted(reconstructed)!=sorted((c['group_id'],tuple(c['position'])) for c in recorded):
                    raise ValueError('Reconstruction does not match recorded candidate contract')
                i=('tb1','tb2','tb3').index(name)
                row=dict(decision=index+1,sim=obs['sim_stamp'],groups=details,
                    legal_groups_before_top5=all_legal_groups,raw_candidates=len(recorded),
                    conditional_goal_options=sum(intent['masks'][i][:15]),
                    own_local_frontier_cells=len(own_cells),
                    own_frontier_already_shared_known=int(sum(shared[p]>=0 for p in own_cells)),
                    own_frontier_shared_free=int(sum(shared[p]==0 for p in own_cells)),
                    own_frontier_in_shared_reachable=sum(p in global_paths for p in own_cells))
                rows.append(row)
            cases.append(dict(map=saved['map'],seed=saved['seed'],robot=name,
                stationary_premise=dict(accepted=0,path_m=0.,all_xyz_yaw_samples_constant=True,trajectory_samples=len(trace),
                    local_source='saved final-local-maps; valid throughout this static proxy because pose+fixed ray offsets never change and sensor has a stationary cache; not a claim for dynamic real sensors'),
                rows=rows))
    if len(cases)!=5:raise ValueError('Expected5stationary robot rows in4public failure cases')
    result=dict(status='SAVED STATIONARY-OBSERVATION STAGE DIAGNOSIS COMPLETE',cases=cases,counts=dict(counts),
        observed_decision_robot_rows=sum(len(c['rows']) for c in cases),
        all_recorded_candidates_reproduced=True,world_truth_reads=0,new_sensor_scans=0,
        nn_forward=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0,wall_seconds=time.monotonic()-began)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    for c in cases:
        print(json.dumps(dict(map=c['map'],seed=c['seed'],robot=c['robot'],decisions=len(c['rows']),
            first=c['rows'][0],last=c['rows'][-1],
            raw_opportunities=sum(r['raw_candidates']>0 for r in c['rows']),
            conditional_opportunities=sum(r['conditional_goal_options']>0 for r in c['rows'])),indent=2))


if __name__=='__main__':run()

"""Six admitted initial sensor fixtures; enumerate masks only, no policy/physics step."""
import itertools
import json
import math
from pathlib import Path
import sys
import numpy as np

WS=Path(__file__).resolve().parent.parent;ROOT=WS.parents[1]
sys.path.insert(0,str(WS/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator
from multi_robot_exploration.joint import slot_mask,slot_to_choice
from multi_robot_exploration.rl_backend import KinematicBackend,route
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_ledger import Ledger


def cross(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def endpoint_distance2(points,starts,edges):
    difference=points[:,None,:]-starts[None,:,:]
    t=np.clip(np.sum(difference*edges[None,:,:],axis=-1)/np.sum(edges*edges,axis=-1),0.,1.)
    delta=difference-t[...,None]*edges[None,:,:]
    return np.sum(delta*delta,axis=-1)


def flagged(a,b):
    """Spatial risk witness only. Opposite direction or one stationary body."""
    if len(a)==1 and len(b)==1:return False
    if len(a)==1 or len(b)==1:
        point,line=(a,b) if len(a)==1 else (b,a)
        return bool(np.min(endpoint_distance2(point,line[:-1],np.diff(line,axis=0)))<.7**2)
    p=a[:-1,None,:];q=b[None,:-1,:];u=np.diff(a,axis=0)[:,None,:];v=np.diff(b,axis=0)[None,:,:]
    opposite=np.sum(u*v,axis=-1)<-1e-12
    if not opposite.any():return False
    minimum=np.minimum.reduce([endpoint_distance2(a[:-1],b[:-1],np.diff(b,axis=0)),
        endpoint_distance2(a[1:],b[:-1],np.diff(b,axis=0)),
        endpoint_distance2(b[:-1],a[:-1],np.diff(a,axis=0)).T,
        endpoint_distance2(b[1:],a[:-1],np.diff(a,axis=0)).T])
    denominator=cross(u,v);nonparallel=np.abs(denominator)>1e-12
    t=np.divide(cross(q-p,v),denominator,out=np.full(denominator.shape,np.inf),where=nonparallel)
    s=np.divide(cross(q-p,u),denominator,out=np.full(denominator.shape,np.inf),where=nonparallel)
    intersects=nonparallel&(t>=0)&(t<=1)&(s>=0)&(s<=1)
    return bool(np.any(opposite&((minimum<.7**2)|intersects)))


def vectors(observation,prefix=()):
    if len(prefix)==3:return [prefix]
    return [v for slot in np.flatnonzero(slot_mask(observation,len(prefix),prefix))
        for v in vectors(observation,prefix+(slot_to_choice(int(slot)),))]


def run():
    output=ROOT/'rl-04/evidence/initial-route-choices-01';output.mkdir(exist_ok=False)
    ledger=Ledger(output/'ledger.jsonl','rl04_initial_sensor_only_route_diagnosis')
    config=json.loads((WS/'rl04/config-v2.json').read_text())
    cases=json.loads((ROOT/'rl-04/evidence/development-01/plan.json').read_text())['cases']
    maps=json.loads((ROOT/'rl-03/evidence/new-test-qualification-01/maps.json').read_text())
    maps+=json.loads((ROOT/'rl-02/evidence/map-qualification-01/maps.json').read_text())
    reports=[]
    for index,case in enumerate(cases):
        row=next(r for r in maps if r['name']==case['map']);pose=next(p for p in row['positions'] if p['seed']==case['seed'])
        # Private geometry is used only by the original sensor/reset backend.
        world=ProjectedWorld(ROOT/row['source'],ROOT/'base-01-econ/assets/gazebo_models',row['variant'],reference_positions=row['reference_positions'])
        backend=KinematicBackend(world,dict(config['backend'],initial_positions=pose['positions']),ledger,pose['seed'])
        receipt=backend.reset();snapshot=receipt['snapshot'];m=snapshot['map']
        np.savez_compressed(output/f'{index:02d}-observed.npz',shared=m['cells'],**backend.local)
        observations=[]
        for mode in ('rl04_approach_v1','rl04_approach_v2'):
            a=Allocator(local_goal_valid=backend.goal_valid,candidate_mode=mode,local_navigation_grid=backend.navigation_grid,
                navigation_path_budget_m=config['navigation_path_budget_m'])
            a.update_map(m['cells'],m['resolution'],m['origin'],m['stamp'])
            for name,r in snapshot['robots'].items():a.update_robot(name,r['pose'],r['stamp'],r['velocity'])
            observations.append(a.get_observation())
        v1,v2=observations
        if [c['position'] for c in v1['candidates']]!=[c['position'] for c in v2['candidates']]:raise ValueError('Initial raw candidate difference beyond joint spacing')
        res=m['resolution'];ox,oy=m['origin']
        def cell(point):return math.floor((point[1]-oy)/res),math.floor((point[0]-ox)/res)
        paths={}
        for c in v2['candidates']:
            name=c['robot'];current=snapshot['robots'][name]['pose']
            grid_path=route(backend.local[name],cell(current),cell(c['position']),res)
            if grid_path is None:raise ValueError('Observed candidate lacks executable proxy route')
            points=[tuple(current[:2])]+[((p[1]+.5)*res+ox,(p[0]+.5)*res+oy) for p in grid_path[1:]]
            if math.dist(current[:2],c['position'])<=config['backend']['xy_goal_tolerance_m']:points=points[:1]
            paths[c['index']]=np.array(points)
        def path(name,choice):return paths[choice] if choice>=0 else np.array([snapshot['robots'][name]['pose'][:2]])
        pairs={}
        all_vectors=vectors(v2)
        unflagged=[]
        for vector in all_vectors:
            bad=False
            for i,j in itertools.combinations(range(3),2):
                key=(i,vector[i],j,vector[j])
                if key not in pairs:pairs[key]=flagged(path(f'tb{i+1}',vector[i]),path(f'tb{j+1}',vector[j]))
                bad |= pairs[key]
            if not bad:unflagged.append(vector)
        reports.append(dict(map=row['name'],seed=pose['seed'],raw_options=list(v2['valid_counts']),
            v1_point2_joint_vectors=len(vectors(v1)),v2_point7_joint_vectors=len(all_vectors),
            v2_geometrically_unflagged_vectors=len(unflagged),
            unflagged_with3goals=sum(all(c>=0 for c in v) for v in unflagged),
            per_robot_goal_available_in_unflagged=[any(v[i]>=0 for v in unflagged) for i in range(3)],
            example=unflagged[0] if unflagged else None,
            route_diagnosis='Only opposing segment proximity<.7 or a WAIT body intersected by another route is flagged. Same-direction/perpendicular overlap is not blanket-banned.',
            not_a_rollout_or_real_Nav2_prediction=True))
        if not backend.stop('initial_sensor_fixture_end'):raise RuntimeError('Initial fixture stop failed')
        ledger.flush('initial_route_fixture',map=row['name'],seed=pose['seed'])
    result=dict(status='INITIAL OBSERVED ROUTE CHOICE DIAGNOSIS',cases=reports,counts=dict(ledger.counts),
        qualification_or_selection_of_new_maps=False,actual_sensor_backend_resets=6,original_sensor_scans=18,
        nn_forward=0,policy_sampling=0,env_step=0,optimizer_update=0,ros_nodes=0,gazebo_start=0,
        limitation='Existence of an unflagged initial joint choice is not proof of learned coordination or later-state feasibility. Routes are observed proxy plans, not actual Nav2 execution guarantees.')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':run()

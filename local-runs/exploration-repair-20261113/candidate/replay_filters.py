"""Offline original allocator replay from original received NPZ/recorded reads.

No ROS initialization, model, simulator, truth geometry or source modification.
Seed-link results use their recorded actual outputs; full source costmaps were
not included in PolicyTrace NPZ. Peer payload is the actual recorded sequence.
"""
from array import array
from collections import Counter
import argparse
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

REPO=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(REPO/'workspace/src/multi_robot_exploration'),str(REPO/'workspace/gz01')]
from multi_robot_exploration.allocation import Allocator, distances
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.observations import project_local_navigation
from multi_robot_exploration import frontier
from peer_keepout import route_blocked, target_allowed
from nav_msgs.msg import OccupancyGrid


def load_case(case, sequence):
    events=[json.loads(line) for line in (case/'controller/allocation-events.jsonl').open()]
    inference=next(e for e in events if e['kind']=='rl_real_inference' and e['sequence']==sequence)
    observation=inference['observed_state_and_candidates']
    decision=observation['decision_id']
    reads={kind:{e['robot']:e for e in events if e['kind']==kind and e.get('decision_id')==decision}
           for kind in ('gz01_seed_connection','gz01_peer_routing_mask')}
    reads['local_navigation_grid']={e['robot']:e for e in events
        if e['kind']=='local_navigation_grid' and e['shared_version']==observation['map']['version']
        and abs(e['sim']-inference['sim'])<1e-6}
    sequence=reads['gz01_peer_routing_mask']['tb1']['peer_sequence']
    peer=next(e for e in map(json.loads,(case/'peer-keepout.jsonl').open()) if e['sequence']==sequence)
    with np.load(case/'controller/policy-trace'/Path(inference['input_npz']).name) as source:
        arrays={key:source[key].copy() for key in source.files}
    return inference,observation,reads,peer,arrays


def replay(case, sequence, selected_robot, clearance_contract=None):
    inference,observation,reads,peer,z=load_case(case,sequence)
    shared=dict(observation['map'],cells=z['received_shared_cells'])
    projected={}
    grids={}
    for robot in ('tb1','tb2','tb3'):
        r=reads['local_navigation_grid'][robot]
        cells=z[robot+'_local_cells']
        projected[robot]=project_local_navigation(cells,float(z[robot+'_local_resolution']),
            (*z[robot+'_local_origin'],r['origin'][2]),r['local_from_shared'],shared)
        grid=OccupancyGrid();grid.info.width=cells.shape[1];grid.info.height=cells.shape[0]
        grid.info.resolution=float(z[robot+'_local_resolution'])
        grid.info.origin.position.x,grid.info.origin.position.y=map(float,z[robot+'_local_origin'])
        grid.info.origin.orientation.z=math.sin(r['origin'][2]/2)
        grid.info.origin.orientation.w=math.cos(r['origin'][2]/2)
        grid.data=array('b',cells.ravel())
        grids[robot]=grid
    fake=SimpleNamespace(local_maps=grids)
    def local_valid(robot,x,y):
        tx,ty,yaw=reads['local_navigation_grid'][robot]['local_from_shared']
        x,y=tx+math.cos(yaw)*x-math.sin(yaw)*y,ty+math.sin(yaw)*x+math.cos(yaw)*y
        return HeadquartersControl.nav_goal_in_local_map(fake,robot,x,y,planner_bounds=True)
    def seed(robot,shared,*args,**kwargs):
        record=reads['gz01_seed_connection'][robot]
        for cell in record['self_body_excluded_cells']:
            kwargs['routing_shared_cells'][tuple(cell)]=0
        return tuple(map(tuple,record['connection_cells'] or ()))
    allocator=Allocator(local_goal_valid=local_valid,candidate_mode='rl04_approach_v2',
        local_navigation_grid=lambda robot,shared:projected[robot],navigation_path_budget_m=23.4,
        seed_connection=seed)
    allocator.map=shared;allocator.map_version=shared['version']
    allocator.decision_id=decision=observation['decision_id']-1
    allocator.now=observation['sim_stamp']
    allocator.goal_separation_m=observation['goal_separation_m']
    allocator.idle_body_goal_clearance_m=observation['idle_body_goal_clearance_m']
    allocator.self_body_route_exclusion=True;allocator.planner_goal_admissibility=True
    allocator.initial_route_conflicts=(.26*1.7,.55)
    allocator.peer_routing_mask=lambda robot,shared:route_blocked(robot,shared,peer,allocator.now)
    allocator.peer_goal_valid=lambda robot,target:target_allowed(robot,target,peer,allocator.now)
    allocator.history=observation['history']
    allocator.visited=[e['target'] for e in allocator.history if e['status']=='succeeded']
    for e in allocator.history:
        if e['status'] in ('aborted','rejected','invalid_local_goal'):allocator.failed[e['robot']].append(e['target'])
    for record in observation['robots']:
        robot=allocator.robots[record['id']]
        for name in ('pose','velocity','state','target','last_status','last_success','condition','cancel_requested'):
            setattr(robot,name,record[name])
        robot.stamp=record['pose_stamp'];robot.token=record['task_token'];robot.uuid=record['action_uuid']
        robot.started=None if record['goal_duration_s'] is None else allocator.now-record['goal_duration_s']
    snapshot=[]
    original_cells=shared['cells'].copy()
    original_costmap=frontier.costmap
    if clearance_contract is not None:
        from candidate_clearance import install_candidate_clearance
        install_candidate_clearance(SimpleNamespace(allocator=allocator),clearance_contract)
    def trace(frame,event,arg):
        if frame.f_code is not Allocator.get_observation.__code__:
            return None
        if event=='line':
            values=frame.f_locals
            if frame.f_lineno==337 and values.get('robot').name==selected_robot:
                snapshot.append(dict(values))
        return trace
    sys.settrace(trace)
    try:actual=allocator.get_observation()
    finally:sys.settrace(None)
    pairs=lambda rows:[(c['robot'],tuple(c['position']),c['kind'],c['valid']) for c in rows]
    reproduced=pairs(actual['candidates'])==pairs(observation['candidates'])
    if clearance_contract is None:
        assert reproduced, (pairs(actual['candidates']),pairs(observation['candidates']))
        assert actual['valid_counts']==tuple(observation['valid_counts'])
    assert np.array_equal(original_cells,shared['cells'])
    assert frontier.costmap is original_costmap
    # Derive every executed group stage from original function locals. The
    # trace line is checked against the installed source before invocation.
    groups=[]
    for values in snapshot:
        cells=values['cells'];shared_free=values['shared_free'];local=values['local'];local_paths=values['local_paths']
        counts=Counter()
        for p in shared_free:
            target=values['position'](p)
            checks=(('planner_goal',local_valid(selected_robot,*target)),
                ('idle_body',all(name==selected_robot or math.dist(target,pose[:2])>=allocator.idle_body_goal_clearance_m for name,pose in observation['idle_body_positions'].items())),
                ('peer_goal',allocator.peer_goal_valid(selected_robot,target)),
                ('raw_local_free',local[p]==0),('local_reachable',p in local_paths),
                ('clearance_shared',values['shared_inflated'][p]==0),('clearance_local',values['local_inflated'][p]==0),
                ('path_budget',p in local_paths and local_paths[p]<=allocator.navigation_path_budget_m),
                ('visited_failed',not any(math.dist(target,q)<.2 for q in values['blocked'])),
                ('assigned_target',not any(math.dist(target,q)<allocator.goal_separation_m for q in values['assigned'])),
                ('last_success',values['robot'].last_success is None or math.dist(target,values['robot'].last_success)>=.5))
            for key,passed in checks:
                if not passed:counts[key]+=1
        groups.append(dict(group_id=values['group_id'],raw_frontier_cells=len(cells),
            shared_reachable=len(shared_free),admissible=len(values['free']),failed_predicate_counts=dict(counts),
            local_reachable_frontier=sum(local[p]==0 and p in local_paths for p in shared_free)))
    first=snapshot[0]
    start=(first['r'],first['column'])
    no_peer=frontier.costmap(shared['cells'],shared['cells'].shape[1],shared['cells'].shape[0],shared['resolution'])
    no_peer[start]=0;no_peer[no_peer<0]=1;no_peer[no_peer>5]=1
    no_peer_reachable=distances(no_peer,start,shared['resolution'])
    raw=(shared['cells']!=0).astype(np.int8);raw[start]=0
    raw_reachable=distances(raw,start,shared['resolution'])
    route_stats=dict(seed=start,shared_inflated_seed=float(first['shared_inflated'][start]),
        local_inflated_seed=float(first['local_inflated'][start]),
        shared_reachable_cells=len(first['reachable']),local_reachable_cells=len(first['local_paths']),
        shared_without_peer_reachable_cells=len(no_peer_reachable),
        shared_without_peer_frontier_cells=sum(p in no_peer_reachable for _,cells in first['groups'] for p in cells),
        shared_raw_knownfree_reachable_cells=len(raw_reachable),
        shared_raw_knownfree_frontier_cells=sum(p in raw_reachable for _,cells in first['groups'] for p in cells),
        peer_blocked_seed=bool(first['peer_blocked'][start]),
        local_knownfree_frontier_cells=int(sum(first['local'][p]==0 and p in first['local_paths'] for _,cells in first['groups'] for p in cells)))
    return dict(case=str(case),decision_id=observation['decision_id'],sim=inference['sim'],robot=selected_robot,
        original_candidates_reproduced_exactly=reproduced,original_valid_counts=observation['valid_counts'],
        replayed_valid_counts=actual['valid_counts'],source_shared_grid_unchanged=True,
        global_costmap_restored=True,candidates=[dict(c) for c in actual['candidates'] if c['robot']==selected_robot],
        source='Original received NPZ grids, original local TF/seed output and actual peer payload sequence; no truth',
        route_stats=route_stats,groups=groups)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--sequence',type=int,required=True);parser.add_argument('--robot',required=True)
    args=parser.parse_args();print(json.dumps(replay(args.case,args.sequence,args.robot),indent=2))

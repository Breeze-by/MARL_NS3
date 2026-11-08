"""Finite saved TRAIN/VAL observation ablation; no policy/environment execution."""
from collections import Counter
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
WORKSPACE, PROJECT, ROOT = HERE.parent, HERE.parent.parent, HERE.parent.parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration import frontier
from multi_robot_exploration.allocation import distances


def save(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def inputs():
    seen, selected = set(), []
    for line in (ROOT/'rl-02/runs/formal-01/episodes.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row['map'] in seen:
            continue
        seen.add(row['map'])
        selected.append(dict(phase='TRAIN_first_saved_episode_per_map', map=row['map'],
            folder=f'rl-02/runs/formal-01/episodes/{row["episode"]:05d}'))
    for run, checkpoint in ((1,'01024'),(2,'02048')):
        base=ROOT/f'rl-02/runs/formal-{run:02d}/validation/{checkpoint}'
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            selected.append(dict(phase=f'VAL_run{run}_checkpoint{checkpoint}',
                folder=str(folder.relative_to(ROOT))))
    if len(selected)!=14:
        raise ValueError('Expected eight first-per-map TRAIN and six fixed VAL snapshots')
    return selected


def analyse(folder, budget, counts):
    summary=json.loads((folder/'summary.json').read_text())
    if summary['split'] not in ('TRAIN','VAL'):
        raise ValueError('This ablation cannot use TEST observations')
    obs=json.loads((folder/'last-observed.json').read_text())
    shared=np.load(folder/'observed-grids.npz')['cells'][-1]
    locals=np.load(folder/'final-local-maps.npz')
    res=obs['map']['resolution'];ox,oy=obs['map']['origin']
    out=[]
    for robot in obs['robots']:
        name=robot['id'];local=locals[name]
        if shared.shape!=local.shape:
            raise ValueError('Saved local/shared projection grids disagree')
        start=(math.floor((robot['pose'][1]-oy)/res),math.floor((robot['pose'][0]-ox)/res))
        data=frontier.costmap(shared,shared.shape[1],shared.shape[0],res)
        data[start]=0;data[data>5]=1
        data,groups=frontier.assign_groups(frontier.frontierB(data))
        counts['frontier_robot_recomputations']+=1
        original_groups=frontier.fGroups(groups)
        all_groups=[g for g in sorted(groups.items(),key=lambda g:len(g[1]),reverse=True) if len(g[1])>2]
        data[data<0]=1
        global_paths=distances(data,start,res);counts['observed_global_Dijkstra']+=1
        local_data=frontier.costmap(local,*reversed(local.shape),res)
        local_data[local_data!=0]=1;local_data[start]=0
        local_paths=distances(local_data,start,res);counts['observed_local_Dijkstra']+=1
        visited=[r['target'] for r in obs['history'] if r['status']=='succeeded']
        failed=[r['target'] for r in obs['history'] if r['robot']==name and r['status'] in ('aborted','rejected','invalid_local_goal')]
        blocked=visited+failed+[r['target'] for r in obs['robots'] if r['target'] is not None]
        def position(cell):
            return ((cell[1]+.5)*res+ox,(cell[0]+.5)*res+oy)
        def memory_valid(cell):
            point=position(cell)
            return (not any(math.dist(point,p)<.2 for p in blocked)
                and (robot['last_success'] is None or math.dist(point,robot['last_success'])>=.5))
        detail=[]
        for group_id,cells in all_groups:
            center=frontier.calculate_centroid([p[0] for p in cells],[p[1] for p in cells])
            free=[p for p in cells if p in global_paths]
            if not free:
                continue
            old=min(free,key=lambda p:((p[0]-center[0])**2+(p[1]-center[1])**2,p))
            distance=math.dist(start,center)
            old_local=bool(local[old]==0)
            old_eligible=distance<=frontier.max_distance and not any(math.dist(position(old),p)<.2 for p in blocked)
            old_last=(robot['last_success'] is None or math.dist(position(old),robot['last_success'])>=.5)
            old_valid=bool(old_eligible and old_local and old_last)
            saved=next((c for c in obs['candidates'] if c['robot']==name and c['group_id']==group_id),None)
            retained=any(group_id==key for key,_ in original_groups)
            if retained and (saved is None or tuple(saved['position'])!=position(old)
                    or bool(saved['valid'])!=old_valid):
                raise ValueError('Legacy saved observation alignment failed')
            feasible=[p for p in free if local[p]==0 and p in local_paths
                and local_paths[p]<=budget and memory_valid(p)]
            representative=min(feasible,key=lambda p:((p[0]-center[0])**2+(p[1]-center[1])**2,p)) if feasible else None
            A=bool(old_local and old in local_paths and local_paths[old]<=budget and memory_valid(old))
            detail.append(dict(group_id=group_id,frontier_cells=len(cells),in_original_top5=retained,
                old_position=position(old),centroid_distance_cells=distance,
                old_valid=old_valid,old_local_point_valid=old_local,
                old_local_path_cost_m=local_paths.get(old),A_same_point_local_path_budget=A,
                B_has_local_executable_representative=representative is not None,
                local_reachable_unblocked_frontier_cells=len(feasible),
                B_position=None if representative is None else position(representative),
                B_path_cost_m=None if representative is None else local_paths[representative]))
        old_count=sum(r['old_valid'] for r in detail if r['in_original_top5'])
        A_count=sum(r['A_same_point_local_path_budget'] for r in detail if r['in_original_top5'])
        B_count=sum(r['B_has_local_executable_representative'] for r in detail if r['in_original_top5'])
        C_count=min(5,sum(r['B_has_local_executable_representative'] for r in detail))
        idle=robot['state']=='idle'
        out.append(dict(robot=name,state=robot['state'],saved_idle_valid_count=obs['valid_counts'][('tb1','tb2','tb3').index(name)],
            group_counts=dict(all=len(groups),larger_than_two=len(all_groups),original_retained=len(original_groups)),
            geometric_counts=dict(legacy=old_count,A_same_rep= A_count,B_local_rep_original_top5=B_count,C_legal_then_top5=C_count),
            idle_opportunity_counts={k:(v if idle else 0) for k,v in dict(legacy=old_count,A=A_count,B=B_count,C=C_count).items()},
            groups=detail))
    return dict(map=summary['map'],split=summary['split'],outcome=summary['end_reason'],robots=out)


def main():
    output=PROJECT/'evidence/candidate-static-01'
    output.mkdir(parents=True,exist_ok=False)
    selected=inputs()
    config=json.loads((WORKSPACE/'rl02/config.json').read_text())
    budget=config['backend']['navigation_timeout_sim_s']*config['backend']['max_linear_m_s']
    save(output/'plan.json',dict(snapshots=selected,local_path_budget_m=budget,
        reason='90s times nominal .26m/s is an optimistic length ceiling, not guaranteed completion time',
        max_snapshots=14,nn_forward=0,env_reset=0,env_step=0,gazebo_start=0))
    counts=Counter();results=[];started=time.monotonic()
    for row in selected:
        results.append(analyse(ROOT/row['folder'],budget,counts));counts['saved_snapshots']+=1
    totals=Counter()
    for case in results:
        for robot in case['robots']:
            values=robot['idle_opportunity_counts']
            for k,v in values.items():totals[k+'_idle_goals']+=v
            totals['A_improved_idle_rows']+=values['A']>values['legacy']
            totals['B_improved_over_A_idle_rows']+=values['B']>values['A']
            totals['C_improved_over_B_idle_rows']+=values['C']>values['B']
    result=dict(status='SAVED OBSERVATION ABLATION COMPLETE',cases=results,totals=dict(totals),counts=dict(counts),
        wall_seconds=time.monotonic()-started,nn_forward=0,env_reset=0,env_step=0,optimizer_step=0,gazebo_start=0,
        interpretation='Static candidate opportunities only, before sequential joint reservations; no rollout benefit or guaranteed Nav2 feasibility inferred.')
    save(output/'result.json',result)
    print(json.dumps(dict(totals=dict(totals),counts=dict(counts),wall_seconds=result['wall_seconds']),indent=2))


if __name__=='__main__':
    main()

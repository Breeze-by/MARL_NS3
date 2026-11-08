"""Saved DEV goals and poses only: distinguish endpoint competition and route meetings."""
from collections import Counter,defaultdict
import itertools
import json
import math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'rl-04/evidence/development-01'


def run():
    plan=json.loads((BASE/'plan.json').read_text());reports=[]
    for summary_path in sorted(BASE.glob('*/summary.json')):
        folder=summary_path.parent;s=json.loads(summary_path.read_text())
        intents=[json.loads(x) for x in (folder/'intents.jsonl').read_text().splitlines()]
        events=json.loads((folder/'navigation.json').read_text())
        trace=json.loads((folder/'trajectory.json').read_text())
        metadata={}
        for intent in intents:
            obs=intent['observation']
            for i,choice in enumerate(intent['action']):
                if choice>=0:metadata[(obs['robots'][i]['id'],obs['robots'][i]['task_token']+1)]=obs['candidates'][choice]
        goals={}
        for event in events:
            if event['kind']=='accepted':
                c=metadata[(event['robot'],event['token'])]
                if not np.allclose(c['position'],event['target'],atol=1e-12):raise ValueError('Goal link mismatch')
                goals[event['uuid']]=dict(robot=event['robot'],token=event['token'],uuid=event['uuid'],
                    start=event['sim'],end=trace[-1]['sim'],target=event['target'],kind=c['kind'],status='unresolved',
                    associated_frontier=c['shared_frontier_position'])
            elif event['kind']=='terminal':
                g=goals[event['uuid']];g.update(end=event['sim'],status=event['status'],terminal_pose=event['actual_pose'],
                    xy_error=event['xy_error_m'])
        overlaps=[]
        for a,b in itertools.combinations(goals.values(),2):
            start=max(a['start'],b['start']);end=min(a['end'],b['end'])
            if a['robot']==b['robot'] or end<=start:continue
            d=math.dist(a['target'],b['target'])
            overlaps.append(dict(a=a['uuid'],b=b['uuid'],kinds=[a['kind'],b['kind']],
                start=start,end=end,target_distance_m=d,below_minpair=d<.7,
                goal_disks_geometrically_incompatible=d+2*.25<.7-1e-9,
                robust_separation_for_all_tolerance_poses=d>=.7+2*.25))
        # Replay only recorded goal ownership; no simulator/goal/route execution.
        ordered=sorted(events,key=lambda r:r['sim']);cursor=0;active={};blocked=defaultdict(lambda:dict(seconds=0.,samples=0,first=None,last=None,example=None))
        for previous,current in zip(trace,trace[1:]):
            t=previous['sim'];dt=current['sim']-t
            while cursor<len(ordered) and ordered[cursor]['sim']<=t+1e-9:
                e=ordered[cursor]
                if e['kind']=='accepted':active[e['robot']]=goals[e['uuid']]
                elif e['kind']=='terminal':active.pop(e['robot'],None)
                cursor+=1
            for a,b in itertools.combinations(('tb1','tb2','tb3'),2):
                pa=np.array(previous['poses'][a][:2]);pb=np.array(previous['poses'][b][:2]);distance=float(np.linalg.norm(pa-pb))
                stationary=all(np.linalg.norm(np.array(current['poses'][r][:2])-previous['poses'][r][:2])<1e-9 for r in (a,b))
                if not stationary or distance>.7+.052+1e-6:continue
                ga,gb=active.get(a),active.get(b)
                if ga is None and gb is None:continue
                target_distance=math.dist(ga['target'],gb['target']) if ga and gb else None
                infeasible=[]
                for robot,other,goal in ((a,b,ga),(b,a,gb)):
                    if goal is not None and other not in active:
                        d=math.dist(goal['target'],previous['poses'][other][:2])
                        if d+.25<.7-1e-9:infeasible.append(dict(active_robot=robot,idle_other=other,d_goal_to_idle_pose=d))
                key=(a,b,ga['uuid'] if ga else 'idle',gb['uuid'] if gb else 'idle')
                out=blocked[key];out['seconds']+=dt;out['samples']+=1;out['last']=current['sim']
                if out['first'] is None:
                    out['first']=t
                    out['example']=dict(sim=t,poses={a:previous['poses'][a],b:previous['poses'][b]},pair_distance_m=distance,
                        active_goals={r:dict(uuid=g['uuid'],kind=g['kind'],target=g['target'],status_at_sample='active',
                            final_status=g['status'],age=t-g['start'],distance_to_goal=math.dist(previous['poses'][r][:2],g['target']))
                            for r,g in ((a,ga),(b,gb)) if g is not None},
                        target_distance_m=target_distance,goal_unreachable_with_other_idle_pose=infeasible,
                        mechanism='far endpoints / meeting routes' if target_distance is not None and target_distance>=1.2 else
                            'near endpoints / tolerance interaction' if target_distance is not None and target_distance<.7 else 'mixed/idle obstacle')
        old_path=ROOT/next(r['baseline'] for r in plan['cases'] if r['map']==s['map'] and r['seed']==s['seed'])
        old=json.loads(old_path.read_text())
        reports.append(dict(map=s['map'],seed=s['seed'],new=dict(actual_joint=s['actual_joint'],reason=s['end_reason'],
            externally_cut=s['externally_cut'],coverage=s['coverage'],T95=s['coverage_times'].get('0.95'),
            total_path=sum(s['paths_m'].values()),participation=s['all_robot_participation'],paths=s['paths_m'],
            safe_blocks=s['safe_blocks'],nonforced=s['nonforced_per_head']),
            old=dict(actual_joint=old['actual_joint'],T95=old['coverage_times'].get('0.95'),total_path=sum(old['paths_m'].values()),participation=old['all_robot_participation']),
            goals=list(goals.values()),concurrent_goal_pairs=overlaps,
            near_stationary_pair_intervals=sorted(blocked.values(),key=lambda r:r['seconds'],reverse=True),
            minimum_concurrent_target_distance=min((r['target_distance_m'] for r in overlaps),default=None),
            target_pairs_below_minpair=sum(r['below_minpair'] for r in overlaps),
            goal_disk_incompatible_pairs=sum(r['goal_disks_geometrically_incompatible'] for r in overlaps),
            observed_limitations='Stationary near-pair intervals are descriptive, not exact per-physics safe_block attribution; no saved per-rejection reason or original route list.'))
    result=dict(status='OFFLINE SAVED DEVELOPMENT FORENSICS',cases=reports,
        interpretation='Distance<.7 of target centres alone does not prove impossible: .25goal tolerance permits two outer stop points. Fixed idle pose with goal_distance+.25<.7 is a stronger impossibility witness.',
        nn_forward=0,policy_sampling=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0)
    output=ROOT/'rl-04/evidence/development-forensics.json';output.write_text(json.dumps(result,indent=2)+'\n')
    for r in reports:
        print(r['map'],r['seed'],'min_target',r['minimum_concurrent_target_distance'],'nearTargetPairs',r['target_pairs_below_minpair'],'impossibleDisks',r['goal_disk_incompatible_pairs'])
        for meeting in r['near_stationary_pair_intervals'][:3]:print('meeting',json.dumps(meeting))


if __name__=='__main__':run()

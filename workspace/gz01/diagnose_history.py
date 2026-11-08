"""Observed controller/CSV timeline only; no policy forward or environment step."""
import csv
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'gz-01/workspace/src/multi_robot_exploration'))
from multi_robot_exploration import frontier


def main():
    case=ROOT/'rl-04/runs/gazebo-rl-smoke-01'
    output=ROOT/'gz-01/evidence/historical-180-diagnosis-01'
    output.mkdir(parents=True,exist_ok=False)
    metric=json.loads((ROOT/'gz-01/evidence/historical-180-01/result.json').read_text())
    start,end=metric['start_sim'],metric['end_sim']
    control=[json.loads(row) for row in (case/'controller/allocation-events.jsonl').open()]
    inferences=[row for row in control if row['kind']=='rl_real_inference']
    decisions=[]
    for event in inferences:
        obs=event['observed_state_and_candidates'];m=obs['map']
        with np.load(case/f'controller/inference/{event["inference_sequence"]:04d}.npz',allow_pickle=False) as source:
            cells=source['received_shared_cells']
        raw={}
        for robot in obs['robots']:
            resolution=m['resolution'];ox,oy=m['origin'];h,w=cells.shape
            col=math.floor((robot['pose'][0]-ox)/resolution);row=math.floor((robot['pose'][1]-oy)/resolution)
            data=frontier.costmap(cells,w,h,resolution);data[row,col]=0;data[data>5]=1
            _,groups=frontier.assign_groups(frontier.frontierB(data))
            raw[robot['id']]=dict(raw_groups=len(groups),raw_frontier_cells=sum(map(len,groups.values())),
                minimum_three_cell_groups=sum(len(group)>2 for group in groups.values()))
        decisions.append(dict(sim=event['sim'],elapsed=event['sim']-start,
            sequence=event['inference_sequence'],choices=event['raw_choices'],
            candidate_count=len(obs['candidates']),valid_counts=obs['valid_counts'],
            states={row['id']:row['state'] for row in obs['robots']},raw_frontier=raw,
            interpretation='Within policy received/cropped ROI only; not outdoor/full-world frontier'))
    true_rows={}
    for row in csv.DictReader((case/'trajectories.csv').open()):
        time=float(row['sim_s'])
        if start<=time<=end:
            true_rows.setdefault(round(time,6),{})[row['robot']]=float(row['speed_xy'])
    complete=sorted((t,row) for t,row in true_rows.items() if len(row)==3)
    t95=start+metric['quality_valid_thresholds']['0.95']['elapsed_sim_s']
    t98=start+metric['quality_valid_thresholds']['0.98']['elapsed_sim_s']
    first=inferences[0]['sim'];last_goal=max(row['sim'] for row in control if row['kind']=='rl_actual_nav2_goal_result')
    stationary=dict(total=0.,before_first_decision=0.,before_T95=0.,after_T95=0.,after_T98=0.,after_last_goal_terminal=0.)
    legal_work_stationary=0.
    for (time,speeds),(following,_) in zip(complete,complete[1:]):
        if following-time>.5 or not all(v<.01 for v in speeds.values()):continue
        dt=following-time;stationary['total']+=dt
        for key,bound,after in [('before_first_decision',first,False),('before_T95',t95,False),
            ('after_T95',t95,True),('after_T98',t98,True),('after_last_goal_terminal',last_goal,True)]:
            stationary[key]+=max(0.,following-max(time,bound)) if after else max(0.,min(following,bound)-time)
        active_snapshot=next((row for row in reversed(decisions) if row['sim']<=time),None)
        if active_snapshot and any(active_snapshot['valid_counts']):legal_work_stationary+=dt
    exhausted=[row for row in decisions if all(v['raw_frontier_cells']==0 for v in row['raw_frontier'].values())]
    all_wait=[row for row in decisions if row['choices']==[-2,-2,-2]]
    result=dict(scope='Historical actual Gazebo controller/trajectory diagnosis; indoor ROI only',
        first_decision_sim=first,T95_sim=t95,T98_sim=t98,last_goal_terminal_sim=last_goal,
        earliest_all_WAIT_sim=None if not all_wait else all_wait[0]['sim'],
        earliest_no_raw_ROI_frontier_sim=None if not exhausted else exhausted[0]['sim'],
        all_wait_decisions=len(all_wait),no_raw_ROI_frontier_decisions=len(exhausted),
        all_robot_stationary_seconds=stationary,
        all_stationary_with_available_candidate_seconds_sample_held=legal_work_stationary,
        snapshots=decisions,
        diagnosis=[
            'Raw frontier extraction is replayed from actual received policy ROI, without a network/model call or truth input.',
            'Long stationary tail after coverage/last real terminal is not automatically cooperation failure.',
            'If ROI frontier is exhausted, missing natural shutdown is an observable lifecycle/budget issue; full-world outdoors remains outside this policy contract.',
            'Candidate availability is held between recorded joint snapshots; this is not continuous-time proof of every intermediate mask.'],
        calls=dict(Node=0,NN=0,environment_step=0,optimizer=0,Gazebo=0,actual_Action=0))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    with (output/'decisions.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['sim','elapsed','choices','candidate_count','valid_counts','raw_frontier_cells_tb1_tb2_tb3'])
        for row in decisions:writer.writerow([row['sim'],row['elapsed'],row['choices'],row['candidate_count'],row['valid_counts'],[r['raw_frontier_cells'] for r in row['raw_frontier'].values()]])
    print(json.dumps({k:v for k,v in result.items() if k not in ('snapshots','diagnosis')},indent=2))


if __name__=='__main__':main()

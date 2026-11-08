"""Read existing ROS bags offline; no Node, policy, Nav2 or simulator calls."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from metrics import load_reference, sample_received, measure, thresholds
from bag_records import records

ROBOTS=('tb1','tb2','tb3')


def read_json(path):
    return json.loads(path.read_text())


def stamp(header):
    return header.stamp.sec+header.stamp.nanosec*1e-9


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


def interval_duration(intervals):
    total=0.;right=float('-inf')
    for begin,end in sorted(intervals):
        total+=max(0.,end-max(begin,right))
        right=max(end,right)
    return total


def task_timeline(control,robot,start,end):
    rows=[r for r in control if r.get('robot')==robot and start<=r.get('sim',-1)<=end]
    requests=[r for r in rows if r['kind']=='rl_actual_nav2_goal_request']
    responses=[r for r in rows if r['kind']=='rl_actual_nav2_goal_response']
    terminals=[r for r in rows if r['kind']=='rl_actual_nav2_goal_result']
    owned=[];pending=[];active=[]
    for request in requests:
        uuid=request['request_uuid'];begin=request['sim']
        response=next((r for r in responses if r['request_uuid']==uuid),None)
        terminal=next((r for r in terminals if r['request_uuid']==uuid),None)
        finish=terminal['sim'] if terminal else end
        if response is not None and not response['accepted']:finish=response['sim']
        owned.append((begin,finish))
        pending.append((begin,response['sim'] if response else finish))
        if response is not None and response['accepted']:active.append((response['sim'],finish))
    logical=[r for r in rows if r['kind']=='goal_terminal']
    statuses={status:sum(r['status']==status for r in logical)
              for status in ('succeeded','aborted','rejected','invalid_local_goal','canceled')}
    return dict(dispatched_ownership_intervals=owned,accepted_active_intervals=active,
        waiting_no_dispatched_task_s=end-start-interval_duration(owned),
        pending_response_s=interval_duration(pending),accepted_active_s=interval_duration(active),
        rejected_actual_responses=sum(not r['accepted'] for r in responses),
        high_level_terminal_counts=statuses,
        high_level_failure_count=sum(statuses[s] for s in ('aborted','rejected','invalid_local_goal')),
        timeout_cancel_dispatched=sum(r['kind']=='timeout_cancel_dispatched' for r in rows),
        timeout_terminal_failures=sum(r['kind']=='nav2_terminal_classified'
            and r.get('reason')=='navigation_timeout' and r.get('high_level_status')=='aborted' for r in rows),
        logical_terminal_events=logical,
        time_semantics='Actual request/response/result ROS event times define dispatched/pending/active intervals. Allocator logical timestamps can be cached and are retained only for cause/count; they are not treated as exact acceptance receipts.')


def main(args):
    args.output.mkdir(parents=True,exist_ok=False)
    events=[json.loads(line) for line in (args.case/'events.jsonl').open()]
    control=[json.loads(line) for line in (args.case/'controller/allocation-events.jsonl').open()]
    start_event,=[e for e in events if e['kind']=='exploration_command']
    bound_event=next(e for e in events if e['kind'] in ('smoke_bound','error')
                     and e['sim'] is not None and e['sim']>=start_event['sim'])
    phase_result=read_json(args.case/'result.json')
    start,end=start_event['sim'],bound_event['sim']
    positions=tuple(tuple(map(float,p.split(','))) for p in args.positions.split(';'))
    reference,boundary=load_reference(args.world,args.assets,positions,require_closed=not args.indoor_roi_only)
    origin_yaws={r:(*p,0.) for r,p in zip(ROBOTS,positions)}
    latest={};initial={};ever_local={r:np.zeros(reference.shape,dtype=bool) for r in ROBOTS}
    initial_local={};curve=[];bodies=[];initial_source=None;first_scans={}
    shape=reference.shape
    def sampled_map(message,name):
        grid=np.asarray(message.data,dtype=np.int16).reshape(message.info.height,message.info.width)
        origin=message.info.origin;ox,oy,rotation=origin.position.x,origin.position.y,yaw(origin.orientation)
        if name=='/merge_map':
            if message.header.frame_id!='merge_map':raise ValueError('Unexpected shared map frame')
        else:
            if message.header.frame_id!='map':raise ValueError('Unexpected local map frame')
            x,y,angle=origin_yaws[name.split('/')[1]]
            ox,oy=x+math.cos(angle)*ox-math.sin(angle)*oy,y+math.sin(angle)*ox+math.cos(angle)*oy
            rotation+=angle
        return sample_received(grid,message.info.resolution,(ox,oy,rotation),reference)
    types={}
    for name,type_,timestamp,data in records(args.case/'bag'):
        time=timestamp/1e9
        if name.endswith('/scan') and name.split('/')[1] in ROBOTS:
            first_scans.setdefault(name,time)
        if name not in ('/merge_map','/gazebo/model_states',*(f'/{r}/map' for r in ROBOTS)):
            continue
        if time>end:continue
        if type_ not in types:types[type_]=get_message(type_)
        message=deserialize_message(data,types[type_])
        if name=='/gazebo/model_states':
            if start<=time and all(r in message.name for r in ROBOTS):
                bodies.append((time,{r:dict(x=message.pose[message.name.index(r)].position.x,
                    y=message.pose[message.name.index(r)].position.y,
                    speed=math.hypot(message.twist[message.name.index(r)].linear.x,
                        message.twist[message.name.index(r)].linear.y),
                    angular=abs(message.twist[message.name.index(r)].angular.z)) for r in ROBOTS}))
            continue
        sample=sampled_map(message,name)
        latest[name]=sample
        if time<=start:
            initial[name]=sample.copy()
            if name=='/merge_map':initial_source=dict(receipt_sim=time,source_stamp=stamp(message.header))
            continue
        if name=='/merge_map':
            curve.append(dict(receipt_sim=time,source_stamp=stamp(message.header),
                elapsed_sim_s=time-start,**measure(sample,reference)))
        else:
            robot=name.split('/')[1]
            ever_local[robot]|=(sample==0)&reference.reference_free
    if '/merge_map' not in initial:raise ValueError('No received initial map at/before autonomy start')
    baseline=dict(receipt_sim=start,source_stamp=initial_source['source_stamp'],elapsed_sim_s=0.,
        initial_map_receipt_sim=initial_source['receipt_sim'],**measure(initial['/merge_map'],reference))
    curve.insert(0,baseline)
    for robot in ROBOTS:
        key=f'/{robot}/map'
        initial_local[robot]=(initial[key]==0)&reference.reference_free if key in initial else np.zeros(shape,dtype=bool)
        ever_local[robot]|=initial_local[robot]
    requests=[r for r in control if r['kind']=='rl_actual_nav2_goal_request' and start<=r['sim']<=end]
    results=[r for r in control if r['kind']=='rl_actual_nav2_goal_result' and start<=r['sim']<=end]
    inferences=[r for r in control if r['kind'] in ('rl_real_inference','traditional_real_decision') and start<=r['sim']<=end]
    robot_metrics={}
    for robot in ROBOTS:
        points=[(t,row[robot]) for t,row in bodies]
        path=sum(math.hypot(b['x']-a['x'],b['y']-a['y']) for (_,a),(_,b) in zip(points,points[1:]))
        goals=[r for r in requests if r['robot']==robot]
        terminals=[r for r in results if r['robot']==robot]
        timeline=task_timeline(control,robot,start,end)
        overlap_requests=0;switches=0;repeat_coordinates=0
        for index,goal in enumerate(goals):
            previous=goals[:index]
            live=[old for old in previous if not any(
                r.get('request_uuid')==old['request_uuid'] and r['sim']<=goal['sim']
                and (r['kind']=='rl_actual_nav2_goal_result' or
                     r['kind']=='rl_actual_nav2_goal_response' and not r['accepted'])
                for r in control)]
            overlap_requests+=int(bool(live))
            switches+=int(any(math.dist(old['merge_map_target'],goal['merge_map_target'])>1e-6 for old in live))
            repeat_coordinates+=int(any(math.dist(old['merge_map_target'],goal['merge_map_target'])<.2 for old in previous))
        own=[r for r in inferences if any(v['id']==robot for v in r['observed_state_and_candidates']['robots'])]
        waiting=0.
        for row,next_row in zip(own,own[1:]+[dict(sim=end)]):
            state=next(v for v in row['observed_state_and_candidates']['robots'] if v['id']==robot)
            if state['state']=='idle':waiting+=max(0.,next_row['sim']-row['sim'])
        added=ever_local[robot]&~initial_local[robot]
        others=np.logical_or.reduce([ever_local[r] for r in ROBOTS if r!=robot])
        exclusive=ever_local[robot]&~others
        intervals=timeline['accepted_active_intervals']
        owned_low_translation=0.;owned_stationary=0.
        for (time,point),(next_time,_) in zip(points,points[1:]):
            if next_time-time>.5 or not any(begin<=time<finish for begin,finish in intervals):continue
            if point['speed']<.01:
                owned_low_translation+=next_time-time
                if point['angular']<.03:owned_stationary+=next_time-time
        robot_metrics[robot]=dict(path_m=path,goals=len(goals),succeeded=sum(r['raw_status']==4 for r in terminals),
            aborted=sum(r['raw_status']==6 for r in terminals),canceled=sum(r['raw_status']==5 for r in terminals),
            motion_participation=bool(goals and path>=1.),predecision_idle_sample_held_proxy_s=waiting,
            task_timeline=timeline,
            local_ever_correct_area_m2=float(ever_local[robot].sum())*reference.resolution**2,
            local_added_correct_area_m2=float(added.sum())*reference.resolution**2,
            exclusive_correct_area_m2=float(exclusive.sum())*reference.resolution**2,
            exclusive_new_correct_area_m2=float(np.count_nonzero(exclusive & ~np.logical_or.reduce(list(initial_local.values()))))*reference.resolution**2,
            active_owned_low_translation_s=owned_low_translation,active_owned_stationary_s=owned_stationary,
            repeated_request_coordinates_0_2m=repeat_coordinates,overlapping_request_ownership=overlap_requests,
            target_switch_while_previous_request_unterminated=switches,
            task_ownership_intervals=intervals,
            attribution_limit='Local map observation/overlap facts, not causal first-arrival sensor credit')
    stationary=0.
    for (t,row),(next_t,_) in zip(bodies,bodies[1:]):
        if next_t-t<=.5 and all(row[r]['speed']<.01 and row[r]['angular']<.03 for r in ROBOTS):stationary+=next_t-t
    final=curve[-1]
    np.savez_compressed(args.output/'reference-and-final.npz',reference_free=reference.reference_free,
        physical_obstacles=reference.obstacles,laser_obstacles=reference.lidar_obstacles,
        final_received_sample=latest['/merge_map'],origin=reference.origin,resolution=reference.resolution)
    with (args.output/'coverage.csv').open('x') as stream:
        fields=['receipt_sim','source_stamp','elapsed_sim_s','coverage','correct_free_area_m2',
            'unknown_reachable_area_m2','false_occupied_reachable_area_m2','false_free_physical_area_m2',
            'free_precision_physical','known_obstacle_recall_within_0_10m','map_quality_valid']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(curve)
    summary=dict(scope='HISTORICAL INDOOR-ROI ONLY; NOT WHOLE GAZEBO WORLD' if args.indoor_roi_only else 'ENCLOSED TASK COMPONENT',
        analysis_version='gz01-recorded-v2',
        source_case=str(args.case),world=str(args.world),start_sim=start,end_sim=end,autonomy_sim_s=end-start,
        reference_bounds=reference.bounds,reference_shape=list(shape),boundary_connected_cells=boundary,
        reference_free_area_m2=baseline['reference_free_area_m2'],initial_source=initial_source,
        initial_coverage=baseline['coverage'],final_coverage=final['coverage'],
        added_coverage=final['coverage']-baseline['coverage'],final_metrics=final,
        raw_thresholds=thresholds(curve,start),quality_valid_thresholds=thresholds(curve,start,require_quality=True),
        coverage_curve=curve,first_scan_receipt_sim=first_scans,
        initial_scan_ready_sim=next((e['sim'] for e in events if e['kind']=='preflight_pass'),None),
        initial_scan_ready_semantics='Common supervisor readiness and observed-stop complete; first scan receipts separately recorded, not called initial-scan completion.',
        first_policy_decision_sim=None if not inferences else inferences[0]['sim'],
        first_goal_submission_sim=None if not requests else requests[0]['sim'],
        first_motion_sim=next((t for t,row in bodies if any(v['speed']>=.01 or v['angular']>=.03 for v in row.values())),None),
        first_translation_sim=next((t for t,row in bodies if any(v['speed']>=.01 for v in row.values())),None),
        all_robot_stationary_s=stationary,robot_metrics=robot_metrics,
        stationary_definition='linear speed<.01m/s AND abs angular speed<.03rad/s; intervals with sample gap≤.5sim only',
        autonomous_wall_s=bound_event['wall']-start_event['wall'],
        observed_stop_sim=next((e['sim'] for e in reversed(events)
            if e['kind']=='observed_stop' and e['sim']>=end),None)
            if phase_result['observed_stop'] else None,
        post_task_observed_stop=phase_result['observed_stop'],
        stop_error=phase_result.get('stop_error'),
        emergency_physics_pause_sim=next((e['sim'] for e in events
            if e['kind']=='emergency_physics_pause' and e['sim']>=end),None),
        original_result_sim_elapsed=phase_result.get('sim_elapsed'),
        target_counter_semantics='succeeded/aborted/canceled are raw Nav2 callbacks within task phase; high-level failures (including timeout raw5) and actual rejection responses are separate in task_timeline. Stop-phase outcomes are not task successes. Sample-held predecision idle is only a proxy; waiting_no_dispatched_task_s uses actual UUID events and includes startup.',
        end_reason=bound_event.get('reason','fatal_error'),
        raw_run_end_reason=phase_result['end_reason'],raw_run_error=phase_result['error'],
        first_error=bound_event.get('detail'),natural_completion_verified=False,
        quality_valid_samples=sum(r['map_quality_valid'] for r in curve),samples=len(curve),
        calls=dict(Node=0,NN=0,environment_step=0,optimizer=0,Gazebo=0,actual_Action=0),
        caveats=['Map receipt/bag ROS time used, never min-source header backdating.',
            'Strict metric uses fixed declared world/common alignment, no fitted map transform.',
            'Existing original budget outcome retained; retrospective threshold is not a natural policy terminal.',
            'Reference region is not expanded to arbitrary ground-plane padding.'])
    (args.output/'result.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:summary[k] for k in ('scope','initial_coverage','final_coverage','raw_thresholds','quality_valid_thresholds','quality_valid_samples','samples','robot_metrics')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--positions',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--indoor-roi-only',action='store_true')
    main(parser.parse_args())

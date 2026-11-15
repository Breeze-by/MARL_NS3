"""Closed-case pacing and feedback only; never reads native ledgers or maps.

Requires actual host cleanup proof, then reads small JSON/JSONL and one
six-topic feedback/status SELECT per bag shard. Source publisher callback
counts are not invented from bag receipts or the Observer's 1-in-10 samples.
"""
import argparse
from contextlib import ExitStack,closing
import heapq
import json
from pathlib import Path
import sqlite3
import statistics

ROBOTS=('tb1','tb2','tb3')
SUFFIX='/navigate_to_pose/_action/'
TOPICS={f'/{robot}'+SUFFIX+kind:(robot,kind) for robot in ROBOTS for kind in ('feedback','status')}


def json_lines(path):
    with path.open() as stream:
        for line in stream:yield json.loads(line)


def stats(values):
    if not values:return dict(n=0,min=None,median=None,p95=None,max=None)
    ordered=sorted(values);k=(len(ordered)-1)*.95;i=int(k)
    return dict(n=len(values),min=ordered[0],median=statistics.median(ordered),
        p95=ordered[i]+(ordered[min(i+1,len(ordered)-1)]-ordered[i])*(k-i),max=ordered[-1])


def gaps(values):return [b-a for a,b in zip(values,values[1:])]


def bag_rows(directory):
    import yaml
    metadata=yaml.safe_load((directory/'metadata.yaml').read_text())['rosbag2_bagfile_information']
    if metadata['storage_identifier']!='sqlite3':raise ValueError('Expected sqlite3 recording')
    with ExitStack() as stack:
        streams=[]
        for shard,name in enumerate(metadata['relative_file_paths']):
            db=stack.enter_context(closing(sqlite3.connect('file:'+str(directory/name)+'?mode=ro',uri=True)))
            topics={i:TOPICS[name] for i,name in db.execute('SELECT id,name FROM topics') if name in TOPICS}
            if not topics:continue
            query='SELECT timestamp,id,topic_id,data FROM messages WHERE topic_id IN ('+','.join('?' for _ in topics)+') ORDER BY timestamp,id'
            def rows(db=db,topics=topics,query=query,shard=shard):
                for timestamp,identity,topic,body in db.execute(query,tuple(topics)):
                    yield timestamp,shard,identity,topics[topic],body
            streams.append(rows())
        yield from heapq.merge(*streams,key=lambda row:row[:3])


def analyze(case,plan,output,comparison=None):
    host_path=case.with_name(case.name+'.host-exit.json')
    host=json.loads(host_path.read_text());cleanup=host['cli_daemon_cleanup']
    if not (host['runner_exit']==0 and host['hub_exit']==0 and cleanup['all_recorded_pids_gone']
            and cleanup['cleanup_pass'] and cleanup['target_process_exited']
            and not host['controlled_time']['remaining_owned_groups']):
        raise ValueError('Successful host/owned-writer exit proof required before offline read')
    run=json.loads((case/'result.json').read_text())
    events=list(json_lines(case/'events.jsonl'))
    start,= (r for r in events if r['kind']=='exploration_command')
    stop=next(r for r in events if r['kind'] in ('smoke_bound','error') and r['sim'] is not None and r['sim']>=start['sim'])
    lo,hi=start['sim'],stop['sim'];wall=stop['wall']-start['wall'];rtf=(hi-lo)/wall
    coordinator=json.loads((case.with_name(case.name+'.time-control')/'coordinator.json').read_text())
    ns0,ns1=round(lo*1e9),round(hi*1e9)
    tokens=[r for r in coordinator['records'] if r[0]=='physical_token' and r[4] is not None and ns0<=r[4]<ns1]
    late=[r[8]/1e6 for r in tokens];above=sum(value>40 for value in late)
    policy=plan['predeclared_qualification'];limits=policy['autonomy_rtf_each_arm']
    gates=dict(rtf_within_predeclared_band=limits['lower']<=rtf<=limits['upper'],
        lateness_p95_le_20wall_ms=bool(late) and stats(late)['p95']<=policy['token_lateness_p95_wall_ms_max'],
        lateness_above_40wall_ms_fraction_le_point01=bool(late) and above/len(late)<=policy['token_lateness_above_40wall_ms_fraction_max'])
    pacing=dict(start_G=lo,end_G=hi,sim_span_s=hi-lo,wall_span_s=wall,rtf=rtf,
        physical_tokens=len(tokens),lateness_wall_ms=stats(late),above_40wall_ms_count=above,
        above_40wall_ms_fraction=None if not late else above/len(late),gates=gates,
        pass_=all(gates.values()),token_selection='physical_token before-G in [autonomy start,end); tuple index8 is original lateness ns',
        global_first_step_lateness_excluded=True)
    control=list(json_lines(case/'controller/allocation-events.jsonl'))
    requests={r['request_uuid']:r for r in control if r['kind']=='rl_actual_nav2_goal_request' and lo<=r['sim']<=hi}
    tokens_to_uuid={(r['robot'],r['token']):uuid for uuid,r in requests.items()}
    goals={uuid:dict(robot=r['robot'],token=r['token'],request_G=r['sim'],R_bag_feedback_G=[],
        R_observer_sampled_feedback=[],C_feedback_G=[],C_accepted_G=None,C_terminal_G=None,
        R_accepted_stamp_G=None,R_terminal_receipt_G=None) for uuid,r in requests.items()}
    for r in control:
        if not lo<=r.get('sim',-1)<=hi:continue
        if r['kind']=='rl_actual_nav2_goal_response' and r['accepted'] and r['request_uuid'] in goals:
            goals[r['request_uuid']]['C_accepted_G']=r['sim']
        elif r['kind']=='rl_actual_nav2_goal_result' and r['request_uuid'] in goals:
            goals[r['request_uuid']]['C_terminal_G']=r['sim']
        elif r['kind']=='feedback':
            uuid=tokens_to_uuid.get((r['robot'],r['token']))
            if uuid in goals:goals[uuid]['C_feedback_G'].append(r['sim'])
    for r in events:
        if r['kind']=='action_feedback' and lo<=r['sim']<=hi and r['goal'] in goals:
            goals[r['goal']]['R_observer_sampled_feedback'].append((r['sim'],r['wall']))
    from action_msgs.msg import GoalStatusArray
    from nav2_msgs.action import NavigateToPose
    from rclpy.serialization import deserialize_message
    counts={name:0 for name in TOPICS};unowned=0
    for timestamp,shard,identity,(robot,kind),body in bag_rows(case/'bag'):
        time=timestamp/1e9
        if time>hi:break
        if time<lo:continue
        counts[f'/{robot}'+SUFFIX+kind]+=1
        if kind=='feedback':
            message=deserialize_message(body,NavigateToPose.Impl.FeedbackMessage)
            uuid=bytes(message.goal_id.uuid).hex()
            if uuid in goals:goals[uuid]['R_bag_feedback_G'].append(time)
            else:unowned+=1
        else:
            message=deserialize_message(body,GoalStatusArray)
            for status in message.status_list:
                uuid=bytes(status.goal_info.goal_id.uuid).hex()
                if uuid not in goals:continue
                goal=goals[uuid];accept=status.goal_info.stamp.sec+status.goal_info.stamp.nanosec/1e9
                if accept>0:goal['R_accepted_stamp_G']=accept
                if status.status in (4,5,6) and goal['R_terminal_receipt_G'] is None:
                    goal['R_terminal_receipt_G']=time
    by_goal={}
    for uuid,goal in goals.items():
        accepted=goal['R_accepted_stamp_G'];terminal=goal['R_terminal_receipt_G']
        span=None if accepted is None else max(0.,min(hi,terminal if terminal is not None else hi)-max(lo,accepted))
        receipt=[t for t in goal['R_bag_feedback_G'] if accepted is not None and max(lo,accepted)<=t<=min(hi,terminal if terminal is not None else hi)]
        callbacks=goal['R_observer_sampled_feedback'];c=goal['C_feedback_G']
        cspan=None if goal['C_accepted_G'] is None else max(0.,min(hi,goal['C_terminal_G'] if goal['C_terminal_G'] is not None else hi)-max(lo,goal['C_accepted_G']))
        by_goal[uuid]=dict(robot=goal['robot'],token=goal['token'],request_G=goal['request_G'],
            R_observed_active_sim_s=span,R_acceptance_source_stamp_G=accepted,R_terminal_receipt_G=terminal,
            R_active_end_right_censored=terminal is None,R_bag_feedback_in_autonomy=len(goal['R_bag_feedback_G']),
            R_bag_feedback_in_observed_active=len(receipt),R_bag_receipt_per_observed_active_sim_s=None if not span else len(receipt)/span,
            R_bag_receipt_intervals_sim_s=stats(gaps(receipt)),R_sampled_Observer_callbacks=len(callbacks),
            R_sampled_Observer_callback_intervals_sim_s=stats(gaps([p[0] for p in callbacks])),
            R_sampled_Observer_callback_intervals_wall_s=stats(gaps([p[1] for p in callbacks])),
            C_delivered_feedback_callbacks=len(c),C_observed_active_sim_s=cspan,
            C_callback_per_C_observed_active_sim_s=None if not cspan else len(c)/cspan,
            C_delivered_callback_intervals_sim_s=stats(gaps(c)))
    feedback=dict(by_owned_uuid=by_goal,bag_topic_counts=counts,unowned_feedback_records=unowned,
        exact_R_source_callback_per_UUID='UNMEASURED: source publisher callbacks are not bag receipt callbacks. Gateway has unsampled captures but no decoded UUID; its large JSON/native ledgers were intentionally not read.',
        R_observer_sampling='Actual Observer callbacks recorded every tenth callback; never multiply samples into exact source count. UUID and callback sim/wall retained.',
        R_active_denominator='Source GoalInfo acceptance ROS stamp through first R bag terminal receipt, clipped to autonomy. Terminal publication/receipt gap is not measured; missing terminal is right-censored.',
        C_scope='Actual central controller feedback callbacks, mapped by robot/token to owned request UUID; separate from R bag receipts and Observer samples; no count subtraction as loss.',
        configured_feedback_tolerance='No numeric feedback pass/fail tolerance was preregistered in PLAN; report descriptive cadence and expose missing exact source callback attribution.')
    result=dict(case=str(case),host_exit_proof=str(host_path),scope='Closed case only; six bag topics; no map/T95 recalculation or native-ledger/Gateway-large-JSON scan',
        run_error=run.get('error'),run_integrity=run.get('run_integrity'),observed_stop=run.get('observed_stop'),pacing=pacing,feedback=feedback,
        between_arm_rtf='PENDING_OTHER_ARM',causal_qualification='FAIL' if not pacing['pass_'] else 'PACING_SINGLE_ARM_PASS_FEEDBACK_SOURCE_UNMEASURED')
    if comparison:
        other=json.loads(comparison.read_text());baseline=other['pacing']['rtf']
        difference=abs(rtf-baseline)/baseline
        result['between_arm_rtf']=dict(reference_case=other['case'],formula=policy['rtf_between_formula'],relative_difference=difference,
            limit=policy['autonomy_rtf_between_arms_relative_difference_max'],pass_=difference<=policy['autonomy_rtf_between_arms_relative_difference_max'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(case=str(case),pacing=pacing,causal_qualification=result['causal_qualification'],between_arm_rtf=result['between_arm_rtf']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compare',type=Path)
    args=parser.parse_args();analyze(args.case,json.loads(args.plan.read_text()),args.output,args.compare)

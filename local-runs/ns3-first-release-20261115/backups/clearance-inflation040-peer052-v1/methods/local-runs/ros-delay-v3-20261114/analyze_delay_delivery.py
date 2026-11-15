"""Observed-source conditional delivery; publication time is not generation AoI."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))

from analyze_consumer_trace import PublicationIndex, publication_candidates
from analyze_delay_hold import analyze_hold_data, analyze_hold_queue

SOURCE_TOPICS={f'/tb{r}/{name}' for r in (1,2,3) for name in ('map','odom','tf','tf_static')}


def source_key(row):
    metadata=row.get('metadata')
    stamp=None if metadata is None else metadata.get('source_timestamp')
    return None if stamp is None or stamp<=0 else (row['topic'],stamp)


def descriptive(values):
    if not values:return dict(n=0,mean=None,sd=None,p50=None,p95=None,max=None)
    values=sorted(values)
    return dict(n=len(values),mean=statistics.mean(values),
        sd=statistics.stdev(values) if len(values)>1 else None,
        p50=statistics.median(values),p95=values[math.ceil(.95*len(values))-1],max=values[-1])


def rate(statuses):
    n=sum(statuses.values());known=statuses.get('DELIVERED_OBSERVED',0)
    unresolved=sum(v for k,v in statuses.items() if k.startswith(('UNKNOWN','AMBIGUOUS')))
    return dict(denominator=n,status_counts=dict(statuses),
        exact_success_rate=None if not n or unresolved else known/n,
        success_rate_lower=None if not n else known/n,
        success_rate_upper=None if not n else (known+unresolved)/n)


def completed_trace(path,summary_path,sequence_field,keep):
    """The existing summary is written only after the trace stream closes."""
    reasons=[];expected=None;count=0;last=None;retained=[]
    try:
        summary=json.loads(summary_path.read_text());expected=summary['rows']
    except (FileNotFoundError,json.JSONDecodeError,KeyError):
        reasons.append('completion_summary_missing_or_invalid')
    try:
        with path.open() as stream:
            for line in stream:
                row=json.loads(line);count+=1;last=row.get(sequence_field)
                if last!=count and 'noncontiguous_record_ids' not in reasons:reasons.append('noncontiguous_record_ids')
                if keep(row):retained.append(row)
    except (FileNotFoundError,json.JSONDecodeError):
        reasons.append('trace_missing_or_invalid_json')
    if expected!=count:reasons.append('declared_actual_row_count_mismatch')
    return retained,dict(complete=not reasons,declared_rows=expected,actual_rows=count,
        last_record_id=last,reasons=reasons,completion_boundary='summary created after trace close')


def postclose_capture_dispositions(all_captured,destinations,queue,end_ns,window_source_keys):
    """Separate proven rejected callbacks; never choose admitted CDR by digest."""
    groups=defaultdict(list);admissions=defaultdict(list);excluded={};errors=[]
    for side,row in all_captured:
        if row.get('direct_native_id') is not None:
            groups[(row['flow'],row['direct_native_id'])].append((side,row))
    if queue is not None:
        for row in queue['frames']:admissions[(row['flow'],row['sequence'])].append(row)
    close=None if queue is None else queue.get('close')
    for (flow,identity),rows in groups.items():
        if len(rows)<2:continue
        ds=destinations.get((flow,identity),[])
        # Trigger only an existing unique-destination digest conflict. No
        # destination or no conflict retains the original analysis unchanged.
        if len(ds)!=1 or not any(c['cdr_sha256']!=ds[0]['cdr_sha256'] for _,c in rows):continue
        reason=None;actual=None
        qs=admissions.get((flow,identity),[])
        if (queue is None or queue.get('schema')!='ros-local-wall-delay-fifo-v1'
                or queue.get('clock')!='time.monotonic_ns' or close is None
                or close['begin_monotonic_ns']>close['end_monotonic_ns']
                or close['admitted_frames_pending']!=0 or close['parent_bounds_unchanged'] is not True):
            reason='missing_or_invalid_closed_admission_epoch'
        elif len(qs)!=1 or len(ds)!=1:
            reason='nonunique_actual_admission_or_destination'
        else:
            q,d=qs[0],ds[0];sent=d.get('endpoint_capture_monotonic_ns')
            admitted=q['capture_monotonic_ns'];released=q.get('release_monotonic_ns')
            candidates=[(side,c) for side,c in rows if type(sent) is int and
                c['endpoint_capture_monotonic_ns']<=sent<=admitted]
            if len(candidates)!=1:
                reason='nonunique_actual_capture_send_admission_interval'
            else:
                actual_side,actual=candidates[0]
                route_ok=all(q[k]==d.get(k) for k in ('sender','receiver','flow'))
                if (not route_ok or q['rpc_id']!=0 or d.get('backend')!='ROS_LOCAL_WALL_DELAY_FIFO' or
                        q['bytes']!=actual['bytes'] or q['bytes']!=d.get('cdr_bytes') or
                        d.get('bytes')!=q['bytes']+8 or not admitted<close['begin_monotonic_ns'] or
                        q['due_monotonic_ns']!=admitted+queue['delay_ns'] or type(released) is not int or
                        released<q['due_monotonic_ns'] or released>close['end_monotonic_ns'] or
                        d.get('endpoint_receive_monotonic_ns',-1)<released or
                        d.get('endpoint_publish_monotonic_ns',-1)<d.get('endpoint_receive_monotonic_ns',-1)):
                    reason='actual_admission_route_bytes_or_timing_unproven'
                else:
                    rejected=[(side,c) for side,c in rows if c is not actual]
                    for side,c in rejected:
                        take=c.get('source_take');key=None if take is None else source_key(take)
                        if (200<=flow<300 or side!=actual_side or
                                c['capture_node_sim_ns']<end_ns or
                                c['endpoint_capture_monotonic_ns']<=close['begin_monotonic_ns'] or
                                c['endpoint_capture_monotonic_ns']<=admitted or
                                key in window_source_keys):
                            reason='reused_capture_not_proven_outside_close_and_source_cohort';break
                    if not reason and queue.get('outside_closed_admission_epoch',{}).get(str(flow),0)<len(rejected):
                        reason='outside_closed_epoch_counter_insufficient'
                    if not reason:
                        for side,c in rejected:
                            excluded[id(c)]=dict(disposition='NOT_ADMITTED_POST_CLOSE',side=side,
                                flow=flow,original_direct_native_id=identity,capture_seq=c.get('capture_seq'),
                                capture_sim_ns=c['capture_node_sim_ns'],capture_monotonic_ns=c['endpoint_capture_monotonic_ns'],
                                close_begin_monotonic_ns=close['begin_monotonic_ns'],
                                actual_admitted_capture_seq=actual.get('capture_seq'),actual_send_monotonic_ns=sent,
                                actual_admission_monotonic_ns=admitted,window_source_key_intersection=False)
        if reason:errors.append(dict(flow=flow,identity=identity,reason=reason))
    return excluded,errors


def analyze(case,path,ingress_path,start_ns,end_ns):
    if end_ns<=start_ns:raise ValueError('No actual autonomy window: delivery metrics are N/A, do not analyze a zero-length cohort')
    source,source_completion=completed_trace(case/'source-observer-takes.jsonl',
        case/'source-observer-measurement.json','take_seq',lambda row:True)
    source=[r for r in source if r['topic'] in SOURCE_TOPICS and start_ns<=r['after']['sim_ns']<end_ns]
    sources=defaultdict(list)
    for row in source:sources[source_key(row)].append(row)
    hq,hq_completion=completed_trace(case/'controller/consumer-trace.jsonl',
        case/'controller/consumer-trace-summary.json','event_id',lambda row:
            row['kind']=='hq_native_take' and row['topic'] in SOURCE_TOPICS and row['after']['sim_ns']<end_ns)
    hq_by_source=defaultdict(list)
    for row in hq:hq_by_source[source_key(row)].append(row)
    measurement=json.loads((case/'comparison-gateway.json').read_text())
    gateway_data=json.loads((case/'network-gateway.json').read_text())
    try:wire_completion=json.loads((case/'network-gateway-saved.json').read_text()).get('saved') is True
    except (FileNotFoundError,json.JSONDecodeError):wire_completion=False
    gateway_topics=gateway_data.get('topics',{}) if path!='A0' else {}
    captured=[];all_captured=[];destinations=defaultdict(list);captures_by_source=defaultdict(list);received_hq=defaultdict(list)
    ambiguous_destination=set();unknown_hq_topics={r['topic'] for r in hq if source_key(r) is None}
    unknown_capture_topics=set()
    unmatched_publication_topics=set();duplicate_ingress=[];duplicate_destinations=[]
    wire_rates=None;native_latencies=[];local_fifo=[];identity_errors=[];postclose={};queue_data=None
    if path!='A0':
        for side,wire in gateway_topics.items():
            for row in wire['captured']:
                all_captured.append((side,row))
                if start_ns<=row['capture_node_sim_ns']<end_ns:captured.append((side,row))
                take=row.get('source_take')
                if side=='R' and take is not None:captures_by_source[source_key(take)].append(row)
                if side=='R' and (take is None or source_key(take) is None):
                    unknown_capture_topics.add(row.get('source_topic'))
            for row in wire['delivered']:
                identity=row.get('native_id') if path=='A1' else row.get('message_id')
                destinations[(row['flow'],identity)].append(row)
        ingress_groups=defaultdict(list);send_groups=defaultdict(list)
        if ingress_path is not None:
            for r in json.loads(ingress_path.read_text()):ingress_groups[r['native_message_id']].append(r)
        for r in measurement['sends']:send_groups[r['send_seq']].append(r)
        ingress={key:rows[0] for key,rows in ingress_groups.items() if len(rows)==1}
        send_index={key:rows[0] for key,rows in send_groups.items() if len(rows)==1}
        duplicate_ingress=[key for key,rows in ingress_groups.items() if len(rows)>1]
        duplicate_destinations=[key for key,rows in destinations.items() if len(rows)>1]
        publications=[r for r in gateway_topics['C']['delivered'] if 'gateway_publication_topic' in r]
        index=PublicationIndex(publications)
        for take in hq:
            match=publication_candidates(take,index.possible(take))
            if len(match['candidates'])==1:
                p=match['candidates'][0]
                identity=p.get('native_id') if path=='A1' else p.get('message_id')
                received_hq[(p['flow'],identity)].append(take)
            elif len(match['candidates'])>1:
                for p in match['candidates']:
                    identity=p.get('native_id') if path=='A1' else p.get('message_id')
                    ambiguous_destination.add((p['flow'],identity))
            else:unmatched_publication_topics.add(take['topic'])
        if path=='A1':
            queue_path=case/'ros-delay-queue.json'
            if queue_path.is_file():queue_data=json.loads(queue_path.read_text())
            postclose,admission_errors=postclose_capture_dispositions(
                all_captured,destinations,queue_data,end_ns,set(sources))
            identity_errors.extend(admission_errors)
        statuses=Counter()
        for side,capture in all_captured:
            if id(capture) in postclose:
                # Keep all source/capture indexes; this key is proven disjoint
                # from the actual-window source cohort and capture is outside it.
                capture['_measurement_identity_valid']=False
                continue
            identity=capture.get('direct_native_id') if path=='A1' else capture.get('hub_send_seq')
            valid=identity is not None
            if path!='A1' and valid:
                sent=send_index.get(identity);entered=ingress.get(identity)
                valid=sent is not None and entered is not None and all(sent[k]==entered[k] for k in
                    ('sender','receiver','flow','bytes','admission_ns','source_stamp_ns'))
                if not valid:identity_errors.append(dict(flow=capture['flow'],hub_send_seq=identity))
            matches=destinations.get((capture['flow'],identity),[]) if valid else []
            if len(matches)>1:
                valid=False;identity_errors.append(dict(flow=capture['flow'],identity=identity,reason='duplicate_destination_identity'))
            destination=matches[0] if len(matches)==1 else None
            if destination is not None and capture['cdr_sha256']!=destination['cdr_sha256']:
                valid=False;identity_errors.append(dict(flow=capture['flow'],identity=identity,reason='original_CDR_digest_mismatch'))
            capture['_measurement_identity_valid']=valid
            delivered=valid and destination is not None and destination['publisher_returned'] and destination['destination_node_sim_ns']<end_ns
            in_window=start_ns<=capture['capture_node_sim_ns']<end_ns
            if in_window:statuses['UNKNOWN_CAPTURE_IDENTITY' if not valid else 'DELIVERED_OBSERVED' if delivered else 'NOT_OBSERVED_BY_BUDGET']+=1
            if delivered and in_window:
                if path!='A1':native_latencies.append((destination['ns3_rx_ns']-ingress[identity]['admission_ns'])/1e6)
                elif capture.get('gateway_capture_clock_ns') is not None and destination.get('gateway_receive_clock_ns') is not None:
                    local_fifo.append((destination['gateway_receive_clock_ns']-capture['gateway_capture_clock_ns'])/1e6)
        wire_rates=rate(statuses)
    statuses=Counter();topics=defaultdict(Counter);latencies=[];by_topic=defaultdict(list);negative=0
    negative_topics=Counter();negative_samples=[]
    for key,rows in sources.items():
        for row in rows:
            takes=[]
            if not source_completion['complete']:status='UNKNOWN_SOURCE_TRACE_INCOMPLETE'
            elif not hq_completion['complete']:status='UNKNOWN_HQ_TRACE_INCOMPLETE'
            elif path!='A0' and not wire_completion:status='UNKNOWN_WIRE_TRACE_INCOMPLETE'
            elif key is None:status='UNKNOWN_SOURCE_METADATA'
            elif len(rows)!=1:status='AMBIGUOUS_SOURCE_PUBLICATION_TIMESTAMP'
            elif path=='A0':
                takes=hq_by_source.get(key,[])
                status=('AMBIGUOUS_HQ_PUBLICATION_TIMESTAMP' if len(takes)>1 else
                    'DELIVERED_OBSERVED' if takes else 'UNKNOWN_HQ_METADATA' if row['topic'] in unknown_hq_topics else 'NOT_OBSERVED_BY_BUDGET')
            else:
                captures=captures_by_source.get(key,[])
                if len(captures)>1:status='AMBIGUOUS_SOURCE_CAPTURE'
                elif not captures:status=('UNKNOWN_SOURCE_CAPTURE_METADATA' if row['topic'] in unknown_capture_topics else
                    'UNKNOWN_DESTINATION_PUBLICATION_MATCH' if row['topic'] in unmatched_publication_topics else 'NOT_OBSERVED_BY_BUDGET')
                else:
                    capture=captures[0]
                    identity=capture.get('direct_native_id') if path=='A1' else capture.get('hub_send_seq')
                    if not capture.get('_measurement_identity_valid',False):status='UNKNOWN_CAPTURE_IDENTITY'
                    else:
                        takes=received_hq.get((capture['flow'],identity),[])
                        status=('AMBIGUOUS_DESTINATION_PUBLICATION' if (capture['flow'],identity) in ambiguous_destination else
                            'AMBIGUOUS_HQ_TAKE' if len(takes)>1 else 'DELIVERED_OBSERVED' if takes else
                            'UNKNOWN_DESTINATION_PUBLICATION_MATCH' if row['topic'] in unmatched_publication_topics else
                            'UNKNOWN_HQ_METADATA' if row['topic'] in unknown_hq_topics else 'NOT_OBSERVED_BY_BUDGET')
            statuses[status]+=1;topics[row['topic']][status]+=1
            if status=='DELIVERED_OBSERVED':
                first=min(takes,key=lambda t:t['after']['realtime_ns'])
                delay=(first['after']['realtime_ns']-key[1])/1e6
                if delay<0:
                    negative+=1;negative_topics[row['topic']]+=1
                    negative_samples.append(dict(topic=row['topic'],source_publish_realtime_ns=key[1],
                        hq_take_return_realtime_ns=first['after']['realtime_ns'],wall_ms=delay))
                else:latencies.append(delay);by_topic[row['topic']].append(delay)
    requests={};accepted=set()
    with (case/'controller/allocation-events.jsonl').open() as stream:
        for line in stream:
            e=json.loads(line)
            if not start_ns<=round(e.get('sim',0)*1e9)<end_ns:continue
            if e['kind']=='rl_actual_nav2_goal_request':requests[e['request_uuid']]=e
            elif e['kind']=='rl_actual_nav2_goal_response' and e['accepted']:accepted.add(e['request_uuid'])
    wall_stats=descriptive(latencies)
    complete=source_completion['complete'] and hq_completion['complete'] and (path=='A0' or wire_completion)
    if negative or not complete:
        for key in ('mean','sd','p50','p95','max'):wall_stats[key]=None
    wall_by_topic={k:descriptive(v) for k,v in by_topic.items()}
    for topic in negative_topics:
        wall_by_topic[topic]=dict(descriptive([]),measurement_status='INVALID_NEGATIVE_REALTIME_INTERVAL')
    result=dict(schema='comparison-delivery-v1',analysis_revision='trace-completion-audit-v2-postclose-admission-am3',case=str(case),path=path,window_sim_ns=[start_ns,end_ns],
        original_gateway_facts=dict(failure=gateway_data.get('failure'),guards={robot:
            {key:guard[key] for key in ('events','control_permission_revoked','owned_unknown_or_active') if key in guard}
            for robot,guard in gateway_data.get('guards',{}).items()}),
        source_freshness_gateway_records=[r['source_freshness_applied'] for r in gateway_data['records']
            if r['kind']=='common_raw_destination_production_entry' and 'source_freshness_applied' in r],
        source_cohort=rate(statuses),source_cohort_by_topic={k:rate(v) for k,v in topics.items()},
        source_publish_to_hq_take_return_wall_ms=wall_stats,
        source_publish_to_hq_take_return_wall_ms_by_topic=wall_by_topic,
        wall_latency_measurement_status='INVALID_TRACE_INCOMPLETE' if not complete else 'INVALID_NEGATIVE_REALTIME_INTERVAL' if negative else 'OBSERVED_DELIVERED_MATCHES_ONLY',
        trace_completion=dict(source=source_completion,hq=hq_completion,wire_saved=wire_completion),
        source_cohort_denominator_complete=source_completion['complete'],
        negative_wall_intervals=negative,wire_capture_to_destination_publish=wire_rates if wire_completion else None,
        negative_wall_samples=negative_samples,
        measurement_valid=complete and not negative and not identity_errors and not duplicate_ingress and not duplicate_destinations,
        measurement_completeness='PARTIAL_UNKNOWN_OR_AMBIGUOUS' if any(k.startswith(('UNKNOWN','AMBIGUOUS')) for k in statuses) else 'FULLY_ATTRIBUTED_OBSERVED_COHORT',
        measurement_invalid_reasons=(["SOURCE_TRACE_INCOMPLETE"] if not source_completion['complete'] else [])+
            (["HQ_TRACE_INCOMPLETE"] if not hq_completion['complete'] else [])+
            (["WIRE_TRACE_INCOMPLETE"] if path!='A0' and not wire_completion else [])+
            (["negative_realtime_interval"] if negative else [])+
            (["capture_identity_or_integrity_error"] if identity_errors else [])+
            (["duplicate_native_ingress_identity"] if duplicate_ingress else [])+
            (["duplicate_destination_identity"] if duplicate_destinations else []),
        duplicate_native_ingress_ids=duplicate_ingress,duplicate_destination_ids=duplicate_destinations,
        unmatched_hq_publication_topics=sorted(unmatched_publication_topics),
        ingress_to_native_rx_sim_ms=descriptive(native_latencies) if path in ('B','C') and wire_completion else None,
        a1_local_fifo_clock_witness_delta_sim_ms=descriptive(local_fifo) if path=='A1' and wire_completion else None,
        ingress_identity_errors=identity_errors,
        not_admitted_postclose_captures=list(postclose.values()),
        goal_acceptance_within_budget=dict(requested=len(requests),accepted=len(set(requests)&accepted),
            rate=None if not requests else len(set(requests)&accepted)/len(requests)),
        semantics='Cohort is existing R Observer takes, not all publisher generations. DDS source_timestamp is publication time, not generation AoI. HQ last republisher timestamps are traced back to original source. Unique observed candidates lack writer GID. Wire delivery is capture to successful destination publish, not proof HQ consumed every message. Wall-ms and native sim-ms are separate; neither is converted by RTF. A1 is the actual Gateway local FIFO, not an ns3/Hub radio path.')
    if queue_data is None:hold=analyze_hold_queue(case,path,start_ns,end_ns,all_captured)
    else:
        hold=analyze_hold_data(queue_data,start_ns,end_ns,all_captured)
        hold['source_queue_file']=str(case/'ros-delay-queue.json')
    result['injected_hold_queue']=hold
    if not hold['measurement_valid']:
        result['measurement_valid']=False
        result['measurement_invalid_reasons']+=hold['measurement_errors']
    return result



CONDITIONS=('A0','D0','D100','D200','D300','D400','D500')


def aggregate(rows):
    if len(rows)!=70 or len({r['map'] for r in rows})!=2 or {r['experiment_condition'] for r in rows}!=set(CONDITIONS):
        raise ValueError('Final delay comparison requires all70 declared slots: two maps, seven conditions, five slots')
    groups=defaultdict(list)
    for row in rows:groups[(row['map'],row['experiment_condition'])].append(row)
    result=[]
    for (map_name,condition),runs in sorted(groups.items()):
        if len(runs)!=5:raise ValueError('Each declared map/condition requires all five slots')
        physical_path='A0' if condition=='A0' else 'A1'
        if any(r['path']!=physical_path for r in runs):raise ValueError('Condition and physical transport do not match')
        if any(r.get('native_service_p95_sim_ms') is not None for r in runs):raise ValueError('No ns3 business native service exists in this cohort')
        statuses=Counter(r['task_metric_status'] for r in runs)
        if set(statuses)-{'CONFIRMED_REACHED','EXPLICITLY_UNREACHED_IN_OBSERVED_WINDOW','UNKNOWN'}:
            raise ValueError('Task measurement status must distinguish reached/unreached/unknown')
        reached=statuses['CONFIRMED_REACHED'];unreached=statuses['EXPLICITLY_UNREACHED_IN_OBSERVED_WINDOW'];unknown=statuses['UNKNOWN']
        valid=[r['t95_sim_s'] for r in runs if r['task_metric_status']=='CONFIRMED_REACHED']
        if any(v is None for v in valid):raise ValueError('Confirmed T95 requires an actual measured value')
        metrics={}
        for name in ('source_delivery_rate','source_delivery_rate_lower','source_delivery_rate_upper',
                     'wire_delivery_rate','source_to_hq_mean_wall_ms','source_to_hq_p95_wall_ms',
                     'last_coverage','injected_hold_mean_wall_ms','injected_hold_p95_wall_ms','native_service_p95_sim_ms'):
            values=[None if name=='last_coverage' and r['task_metric_status']=='UNKNOWN'
                    else r.get(name) for r in runs]
            available=[v for v in values if v is not None]
            metrics[name]=dict(available_runs=len(available),mean=None if len(available)!=5 else statistics.mean(available),
                sd=None if len(available)!=5 else statistics.stdev(available))
        result.append(dict(map=map_name,path=condition,experiment_condition=condition,physical_path=physical_path,
            runs=runs,task_successes=reached,task_denominator=5,
            confirmed_reached_n=reached,observed_unreached_n=unreached,unknown_n=unknown,
            task_status_counts=dict(confirmed_reached=reached,explicitly_unreached_in_observed_window=unreached,unknown=unknown),
            task_window_measurement_qualified_runs=sum(r.get('task_window_measurement_qualified') is True for r in runs),
            full_engineering_qualified_runs=sum(r.get('full_engineering_qualified') is True for r in runs),
            clean_exit_runs=sum(r.get('clean_exit') is True for r in runs),
            failure_classes=dict(Counter(r['batch_classification'] for r in runs)),
            task_success_rate=None if unknown else reached/5,
            task_success_sample_sd=None if unknown else statistics.stdev([int(r['task_metric_status']=='CONFIRMED_REACHED') for r in runs]),
            confirmed_success_lower_bound=reached/5,
            possible_success_upper_bound=(reached+unknown)/5,
            t95_all_five_mean=None if len(valid)!=5 else statistics.mean(valid),
            t95_all_five_sd=None if len(valid)!=5 else statistics.stdev(valid),
            reached_only_t95=dict(n=len(valid),mean=None if not valid else statistics.mean(valid),
                sd=None if len(valid)<2 else statistics.stdev(valid)),metrics=metrics,
            valid_partial_observations=[dict(slot=r['slot'],actual_window=r.get('autonomous_window'),
                delivery=r.get('descriptive_partial_delivery')) for r in runs
                if r.get('partial_delivery_valid') is True
                and r['batch_classification']=='TASK_INFORMATION_FRESHNESS_PROTECTION']))
    blocks=defaultdict(list)
    for row in rows:
        if row.get('block') is not None:blocks[(row['map'],row['block'])].append(row)
    block_rtfs=[]
    for (map_name,block),runs in sorted(blocks.items()):
        by_condition={r['experiment_condition']:r for r in runs}
        complete=len(runs)==7 and set(by_condition)==set(CONDITIONS)
        values={c:by_condition.get(c,{}).get('actual_physical_rtf') for c in CONDITIONS}
        missing=[c for c,value in values.items() if value is None];span=None
        if complete and not missing:
            lo,hi=min(values.values()),max(values.values());span=(hi-lo)/((hi+lo)/2)
        full=complete and all(r.get('task_window_measurement_qualified') is True
            and r.get('autonomous_window') is not None and r['autonomous_window']['duration']>=120 for r in runs)
        block_rtfs.append(dict(map=map_name,block=block,actual_physical_rtfs=values,
            actual_windows={c:by_condition.get(c,{}).get('autonomous_window') for c in CONDITIONS},
            missing_RTF_conditions=missing,all_seven_conditions_present_once=complete,
            symmetric_relative_span=span,predeclared_limit=.01,
            span_within_limit=None if span is None else span<=.01,
            all_seven_full_120_qualified=full,
            full_block_qualification_pass=None if not full or span is None else span<=.01,
            scope='Partial windows retained descriptively, not equal120 qualification. No missing RTF imputation.'))
    return dict(schema='ros-delay70-map-five-run-summary-v1',groups=result,block_rtf_comparison=block_rtfs,
        pure_delay_conditions=list(CONDITIONS[1:]),literal_A0_role='Fresh transport calibration only; A0->D0 is proxy overhead, not pure added delay',
        rows_missing_block_metadata=sum(r.get('block') is None for r in rows),
        block_rtf_formula='(maxRTF-minRTF)/((maxRTF+minRTF)/2)<=0.01 across seven conditions.',
        semantics='Five-run equal weights within map/condition; samples are runs, not pooled messages. Confirmed reached n, explicitly unreached in the actual observed window m, and unknown k sum to five. Unknown is not counted as observed failure; success mean/SD are N/A if k>0, with explicitly named lower/upper bounds. Null T95 is never replaced with120. All failures remain in five-slot denominators. Partial valid metrics are separately listed. Wall-ms and sim-ms are never converted using nominal RTF.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    run=sub.add_parser('run');run.add_argument('--case',type=Path,required=True);run.add_argument('--path',choices=('A0','A1'),required=True)
    run.add_argument('--hub-ingress',type=Path);run.add_argument('--start-s',type=float,default=20);run.add_argument('--budget-s',type=float,default=120)
    summary=sub.add_parser('summary');summary.add_argument('--rows',type=Path,required=True)
    for command in (run,summary):command.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=(analyze(args.case,args.path,args.hub_ingress,round(args.start_s*1e9),round((args.start_s+args.budget_s)*1e9))
        if args.operation=='run' else aggregate(json.loads(args.rows.read_text())))
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')


if __name__=='__main__':main()

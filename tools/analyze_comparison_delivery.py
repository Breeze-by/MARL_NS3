"""Observed-source conditional delivery; publication time is not generation AoI."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics

from analyze_consumer_trace import PublicationIndex, publication_candidates

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
    wire_rates=None;native_latencies=[];local_fifo=[];identity_errors=[]
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
        statuses=Counter()
        for side,capture in all_captured:
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
    return dict(schema='comparison-delivery-v1',analysis_revision='trace-completion-audit-v2',case=str(case),path=path,window_sim_ns=[start_ns,end_ns],
        original_gateway_facts=dict(failure=gateway_data.get('failure'),guards={robot:
            {key:guard[key] for key in ('events','control_permission_revoked','owned_unknown_or_active') if key in guard}
            for robot,guard in gateway_data.get('guards',{}).items()}),
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
        goal_acceptance_within_budget=dict(requested=len(requests),accepted=len(set(requests)&accepted),
            rate=None if not requests else len(set(requests)&accepted)/len(requests)),
        semantics='Cohort is existing R Observer takes, not all publisher generations. DDS source_timestamp is publication time, not generation AoI. HQ last republisher timestamps are traced back to original source. Unique observed candidates lack writer GID. Wire delivery is capture to successful destination publish, not proof HQ consumed every message. Wall-ms and native sim-ms are separate; neither is converted by RTF. A1 is the actual Gateway local FIFO, not an ns3/Hub radio path.')


def aggregate(rows):
    if len(rows)!=40 or len({r['map'] for r in rows})!=2 or {r['path'] for r in rows}!={'A0','A1','B','C'}:
        raise ValueError('Final comparison requires all 40 preregistered rows: two maps, four paths, five slots')
    groups=defaultdict(list)
    for row in rows:groups[(row['map'],row['path'])].append(row)
    result=[]
    for (map_name,path),runs in sorted(groups.items()):
        if len(runs)!=5:raise ValueError('Each preregistered map/path requires all five slots')
        valid=[r['t95_sim_s'] for r in runs if r['t95_sim_s'] is not None]
        metrics={}
        for name in ('source_delivery_rate','source_delivery_rate_lower','source_delivery_rate_upper',
                     'wire_delivery_rate','source_to_hq_mean_wall_ms','source_to_hq_p95_wall_ms',
                     'native_service_p95_sim_ms','a1_local_fifo_clock_witness_p95_sim_ms','last_coverage'):
            values=[r.get(name) for r in runs];available=[v for v in values if v is not None]
            metrics[name]=dict(available_runs=len(available),mean=None if len(available)!=5 else statistics.mean(available),
                sd=None if len(available)!=5 else statistics.stdev(available))
        result.append(dict(map=map_name,path=path,runs=runs,task_successes=len(valid),task_denominator=5,
            task_window_measurement_qualified_runs=sum(r.get('task_window_measurement_qualified') is True for r in runs),
            full_engineering_qualified_runs=sum(r.get('full_engineering_qualified') is True for r in runs),
            clean_exit_runs=sum(r.get('clean_exit') is True for r in runs),
            failure_classes=dict(Counter(r['batch_classification'] for r in runs)),
            task_success_rate=len(valid)/5,
            task_success_sample_sd=statistics.stdev([int(r['t95_sim_s'] is not None) for r in runs]),
            t95_all_five_mean=None if len(valid)!=5 else statistics.mean(valid),
            t95_all_five_sd=None if len(valid)!=5 else statistics.stdev(valid),
            reached_only_t95=dict(n=len(valid),mean=None if not valid else statistics.mean(valid),
                sd=None if len(valid)<2 else statistics.stdev(valid)),metrics=metrics))
    blocks=defaultdict(list)
    for row in rows:
        if row.get('block') is not None:blocks[(row['map'],row['block'])].append(row)
    block_rtfs=[]
    for (map_name,block),runs in sorted(blocks.items()):
        by_path={r['path']:r for r in runs}
        four=len(runs)==4 and set(by_path)=={'A0','A1','B','C'}
        values={path:by_path.get(path,{}).get('actual_physical_rtf') for path in ('A0','A1','B','C')}
        missing=[path for path,value in values.items() if value is None]
        span=None
        if four and not missing:
            lo,hi=min(values.values()),max(values.values())
            span=(hi-lo)/((hi+lo)/2)
        full=four and all(r.get('task_window_measurement_qualified') is True
            and r.get('autonomous_window') is not None and r['autonomous_window']['duration']>=120 for r in runs)
        block_rtfs.append(dict(map=map_name,block=block,actual_physical_rtfs=values,
            actual_windows={path:by_path.get(path,{}).get('autonomous_window') for path in values},
            missing_RTF_paths=missing,all_four_paths_present_once=four,
            symmetric_relative_span=span,predeclared_limit=.01,
            span_within_limit=None if span is None else span<=.01,
            all_four_full_120_qualified=full,
            equal_window_qualification_basis='task_window_measurement_qualified; original full_engineering_qualified and clean_exit retained separately',
            full_block_qualification_pass=None if not full or span is None else span<=.01,
            scope='Partial actual windows retained descriptively; not equal120window qualification.'))
    return dict(schema='comparison-map-five-run-summary-v1',groups=result,block_rtf_comparison=block_rtfs,
        rows_missing_block_metadata=sum(r.get('block') is None for r in rows),
        block_rtf_formula='(maxRTF-minRTF)/((maxRTF+minRTF)/2)<=0.01; maximum pairwise symmetric relative difference. No imputation for missing actualRTF.',
        semantics='Five-run equal weights within each map/path; no pooled message weighting. T95 nulls never replaced with budget; reached-only mean is explicitly conditional, not the five-run T95 mean. All preregistered failures/missing slots remain rows; metrics with missing runs retain N/A rather than silent complete-case means.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    run=sub.add_parser('run');run.add_argument('--case',type=Path,required=True);run.add_argument('--path',choices=('A0','A1','B','C'),required=True)
    run.add_argument('--hub-ingress',type=Path);run.add_argument('--start-s',type=float,default=20);run.add_argument('--budget-s',type=float,default=120)
    summary=sub.add_parser('summary');summary.add_argument('--rows',type=Path,required=True)
    for command in (run,summary):command.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=(analyze(args.case,args.path,args.hub_ingress,round(args.start_s*1e9),round((args.start_s+args.budget_s)*1e9))
        if args.operation=='run' else aggregate(json.loads(args.rows.read_text())))
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')


if __name__=='__main__':main()

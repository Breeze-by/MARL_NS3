"""Inert offline exporter; each original Gateway JSON decoded once, no raw cache."""
import argparse
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import statistics
import time

REPO=Path(__file__).resolve().parents[3]


def stats(values,unit='wall_ms'):
    values=sorted(values)
    if not values:return dict(n=0,unit=unit,status='UNMEASURED')
    return dict(n=len(values),unit=unit,min=values[0],median=statistics.median(values),
        p95=values[math.ceil(.95*len(values))-1],p99=values[math.ceil(.99*len(values))-1],
        max=values[-1],negative_n=sum(v<0 for v in values))


def unique(rows,key):
    counts=Counter(key(r) for r in rows)
    return {key(r):r for r in rows if counts[key(r)]==1},counts


def ident(meta):return meta.get('message_id',meta.get('native_id'))


def export_loaded(gateway,direct,result,timing,bound,peer,rawhealth,publications):
    """Accept the one loaded object; never reopen Gateway or import old exporter."""
    clocks=[r for r in gateway['records'] if r['kind']=='actual_R_clock_relayed_C']
    start=result.get('autonomy_start_sim');elapsed=result.get('sim_elapsed')
    end=bound['sim'] if bound is not None else (None if start is None or elapsed is None else start+elapsed)
    observed=[r['end_monotonic'] for r in timing.get('last_runtime_window',[]) if r['phase']=='autonomous_exploration']
    first=next((r for r in clocks if start is not None and r['gazebo_ns']>=round(start*1e9)),None)
    limit=None if not observed else round(max(observed)*1e9)
    lasts=[r for r in clocks if end is not None and r['gazebo_ns']<=round(end*1e9)
        and limit is not None and r['R_callback_capture_monotonic_ns']<=limit]
    last=max(lasts,key=lambda r:r['R_callback_capture_monotonic_ns']) if lasts else None
    lo=None if first is None else first['R_callback_capture_monotonic_ns']
    hi=None if last is None else last['R_callback_capture_monotonic_ns']
    valid=lo is not None and hi is not None and lo<=hi
    inside=lambda ns:valid and ns is not None and lo<=ns<=hi
    window=dict(status='MEASURED_CLOCK_BRACKET' if valid else 'UNMEASURED',
        original_start_sim=start,original_end_sim=end,end_basis='smoke_bound' if bound else 'original_result_actual_partial_sim_elapsed',
        original_autonomy_wall_s=result.get('wall_elapsed'),original_sim_elapsed_s=elapsed,
        actual_autonomy_RTF=None if not result.get('wall_elapsed') or elapsed is None else elapsed/result['wall_elapsed'],
        lo_monotonic_ns=lo,hi_monotonic_ns=hi,first_clock=first,last_clock=last,
        last_autonomous_observer_end_monotonic_ns=limit,
        scope='Discrete R-clock bracket inside original autonomous start/end and Observer last runtime mono cap; not exact Observer start/end. Partial failed phases remain partial; whole actual errors/faults retained independently.')
    source,source_dups=unique(peer,lambda r:r['sequence'])
    pub,pub_dups=unique(publications,lambda r:(r['robot'],r['bound_state']['sequence']))
    raw,raw_dups=unique(rawhealth.get('rows',[]),lambda r:r['sequence'])
    trace=gateway.get('health_trace',{}).get('rows',[])
    callbacks,cb_dups=unique([r for r in trace if r['stage']=='C_health_callback'],lambda r:(r['flow'],r['sequence']))
    captures,capture_counts=unique([r for side in gateway.get('topics',{}).values() for r in side['captured']],
        lambda r:(r['flow'],r['endpoint_capture_monotonic_ns']))
    deliveries,delivery_counts=unique([r for side in gateway.get('topics',{}).values() for r in side['delivered']],lambda r:(r['flow'],ident(r)))
    endpoints,endpoint_counts=unique(gateway.get('hub_deliveries',[]),lambda r:(r['flow'],ident(r)))
    complete,complete_counts=unique([r for r in gateway['records'] if r['kind']=='destination_complete_message'],lambda r:(r['meta']['flow'],ident(r['meta'])))
    frames=defaultdict(list)
    for row in gateway.get('clock_control_trace',{}).get('events',[]):
        if row['kind']=='health_frame':frames[row['flow']].append(row)
    for flow in frames:frames[flow].sort(key=lambda r:r['queued_monotonic_ns'])
    frame_times={flow:[r['queued_monotonic_ns'] for r in rows] for flow,rows in frames.items()}
    values=defaultdict(list);worst={};attempts=Counter();unavailable=defaultdict(Counter);stage_units={}
    identities=defaultdict(Counter);coverage=defaultdict(Counter);cohorts={};native_targets=[]
    def match(table,counts,key,label,dependency='matched'):
        row=None;status=dependency
        if dependency=='matched':
            n=counts.get(key,0);status='matched' if n==1 else ('missing' if n==0 else 'ambiguous')
            row=table.get(key)
        base='not_applicable' if status=='not_applicable' else ('ambiguous' if status=='ambiguous' else ('matched' if status=='matched' else 'missing'))
        coverage[label]['total']+=1;coverage[label][base]+=1
        if status not in ('matched','missing','ambiguous','not_applicable'):coverage[label][status]+=1
        return row,status
    def field(row,name):return None if row is None else row.get(name)
    def reason(*statuses):
        if 'not_applicable' in statuses:return 'not_applicable'
        if 'ambiguous' in statuses:return 'ambiguous'
        return 'missing' if any(x!='matched' for x in statuses) else None
    def add(name,value,witness,unit='wall_ms',failure=None):
        attempts[name]+=1;stage_units[name]=unit
        if value is None:unavailable[name][failure or 'missing_fields']+=1;return
        values[name].append(value)
        if name not in worst or value>worst[name]['value']:
            worst[name]=dict(value=value,unit=unit,**witness)
    def span(name,begin,end,witness,unit='wall_ms',failure=None):
        add(name,None if begin is None or end is None else (end-begin)/1e6,witness,unit,failure)
    def identity(name,equal,status='matched'):
        identities[name]['total']+=1
        if equal is None:identities[name][reason(status) or 'missing_fields']+=1
        else:identities[name]['measured']+=1;identities[name]['equal' if equal else 'mismatch']+=1
    def source_stages(state):
        t=state.get('delivery_timing',{});seq=state['sequence'];w=dict(sequence=seq)
        if not inside(round(t.get('health_publish_after_monotonic',0)*1e9)):return
        def ns(k):return None if k not in t else round(t[k]*1e9)
        span('Peer/batch_entry_to_snapshot',ns('entry_monotonic'),ns('snapshot_monotonic'),w)
        span('Peer/batch_entry_to_health_return',ns('entry_monotonic'),ns('health_publish_after_monotonic'),w)
        for robot,m in t.get('masks',{}).items():
            for stage,a,b in [('mask_build','begin','built'),('grid_data_materialize','built','before_publish'),('original_mask_publish','before_publish','after_publish')]:
                span(f'Peer/{robot}/{stage}',round(m[a]*1e9),round(m[b]*1e9),w)
    for state in peer:source_stages(state)
    for robot in (1,2,3):
        name=f'tb{robot}';flow=20*robot+11;prefix=name+'/health/'
        if direct is not None:
            health=[r for r in direct['health'] if r['robot']==robot]
            hkey=lambda r:r['before_monotonic_ns']
        else:
            health=[r for r in trace if r['stage']=='R_health_intake' and r['flow']==flow]
            hkey=lambda r:r['mono_ns']
        selected=[r for r in health if inside(hkey(r))]
        cohorts[name]=dict(health_intakes=len(selected),health_accepted=sum(bool(r.get('accepted',r.get('returned'))) for r in selected))
        previous=None
        for r in health:
            accepted=r.get('accepted',r.get('returned'));seq=r['sequence'];receipt=r.get('actual_receipt_monotonic_s',r.get('actual_receipt_mono_s'))
            if inside(hkey(r)):
                w=dict(robot=name,flow=flow,sequence=seq,native_message_id=r.get('native_message_id'),intake_mono_ns=hkey(r))
                state,source_status=match(source,source_dups,seq,prefix+'source')
                origin,raw_status=match(raw,raw_dups,seq,prefix+'raw_publication')
                rawbegin=None if origin is None else origin.get('mono_ns')
                rawend=None if origin is None else origin.get('raw_publish_end_mono_ns')
                span(prefix+'raw_publish_begin_to_intake',rawbegin,hkey(r),w,failure=reason(raw_status))
                if accepted:span(prefix+'raw_publish_end_to_actual_receipt_signed',rawend,None if receipt is None else round(receipt*1e9),w,failure=reason(raw_status))
                if direct is not None:
                    span(prefix+'A0_guard_call',r['before_monotonic_ns'],r['after_monotonic_ns'],w)
                    if accepted:
                        span(prefix+'accepted_receipt_gap_actual_mono',None if previous is None else round(previous['actual_receipt_monotonic_s']*1e9),round(receipt*1e9),dict(w,previous_sequence=None if previous is None else previous['sequence'],predecessor_inside=False if previous is None else inside(hkey(previous))))
                    now=r.get('R_sim_ns')
                else:
                    now=r.get('R_node_sim_before_ns')
                    if accepted:
                        span(prefix+'accepted_receipt_gap_actual_mono',None if r.get('old_receipt_mono_s') is None else round(r['old_receipt_mono_s']*1e9),None if receipt is None else round(receipt*1e9),dict(w,old_sequence=r.get('old_sequence')))
                    span(prefix+'decode_wall',r['mono_ns'],r.get('decode_end_mono_ns'),w)
                    span(prefix+'decode_threadCPU',r.get('thread_cpu_ns'),r.get('decode_end_thread_cpu_ns'),w,'thread_cpu_ms')
                    span(prefix+'guard_wall',r.get('decode_end_mono_ns'),r.get('guard_end_mono_ns'),w)
                    span(prefix+'guard_threadCPU',r.get('decode_end_thread_cpu_ns'),r.get('guard_end_thread_cpu_ns'),w,'thread_cpu_ms')
                    cb,cb_status=match(callbacks,cb_dups,(flow,seq),prefix+'C_callback')
                    capture,capture_status=match(captures,capture_counts,(flow,field(cb,'callback_entry_mono_ns')),
                        prefix+'C_capture',cb_status if cb_status=='ambiguous' else ('missing_callback' if cb is None else 'matched'))
                    key=(flow,r['native_message_id'])
                    endpoint,endpoint_status=match(endpoints,endpoint_counts,key,prefix+'endpoint',
                        'not_applicable' if gateway['mode']=='A' else 'matched')
                    dest,dest_status=match(deliveries,delivery_counts,key,prefix+'R_publication')
                    binding,binding_status=match(pub,pub_dups,(name,seq),prefix+'producer_binding')
                    span(prefix+'C_callback_to_intake',field(cb,'callback_entry_mono_ns'),r['mono_ns'],w,failure=reason(cb_status))
                    span(prefix+'raw_publish_begin_to_C_callback',rawbegin,field(cb,'callback_entry_mono_ns'),w,failure=reason(raw_status,cb_status))
                    span(prefix+'C_serialize_wall',field(cb,'serialize_begin_mono_ns'),field(cb,'serialize_return_mono_ns'),w,failure=reason(cb_status))
                    span(prefix+'C_serialize_threadCPU',field(cb,'serialize_begin_thread_cpu_ns'),field(cb,'serialize_return_thread_cpu_ns'),w,'thread_cpu_ms',reason(cb_status))
                    frame=None;frame_status='not_applicable' if gateway['mode']=='A' else cb_status
                    if gateway['mode']!='A' and cb is not None:
                        qs=frame_times.get(flow,[]);left=bisect_left(qs,cb['callback_entry_mono_ns']);right=bisect_right(qs,cb.get('callback_end_mono_ns',cb['callback_entry_mono_ns']))
                        frame_status='matched' if right-left==1 else ('missing' if right==left else 'ambiguous')
                        frame=frames[flow][left] if right-left==1 else None
                    elif frame_status=='matched':frame_status='missing_callback'
                    coverage[prefix+'socket_frame']['total']+=1;coverage[prefix+'socket_frame'][frame_status]+=1
                    span(prefix+'C_callback_to_socket_queue',field(cb,'callback_entry_mono_ns'),field(frame,'queued_monotonic_ns'),w,failure=reason(cb_status,frame_status))
                    span(prefix+'socket_queue_to_frame_flushed',field(frame,'queued_monotonic_ns'),field(frame,'socket_frame_flushed_monotonic_ns'),w,failure=reason(frame_status))
                    span(prefix+'frame_flushed_to_Hub_receive_signed',field(frame,'socket_frame_flushed_monotonic_ns'),field(endpoint,'hub_receive_monotonic_ns'),w,failure=reason(frame_status,endpoint_status))
                    span(prefix+'Hub_receive_to_endpoint_receive',field(endpoint,'hub_receive_monotonic_ns'),field(endpoint,'endpoint_receive_monotonic_ns'),w,failure=reason(endpoint_status))
                    span(prefix+'endpoint_receive_to_intake',field(endpoint,'endpoint_receive_monotonic_ns'),r['mono_ns'],w,failure=reason(endpoint_status))
                    mapped_rx=None if endpoint is None or gateway.get('anchor') is None or now is None or endpoint.get('ns3_rx_ns') is None else (now-endpoint['ns3_rx_ns']-gateway['anchor']['offset_ns'])/1e6
                    add(prefix+'R_clock_minus_mapped_native_RX',mapped_rx,w,'sim_ms',reason(endpoint_status))
                    span(prefix+'guardEnd_to_topicPublishBegin',r.get('guard_end_mono_ns'),field(dest,'endpoint_publish_monotonic_ns'),w,failure=reason(dest_status))
                    span(prefix+'R_topic_publish_wall',field(dest,'endpoint_publish_monotonic_ns'),field(dest,'publish_after_monotonic_ns'),w,failure=reason(dest_status))
                    span(prefix+'R_topic_publish_threadCPU',field(dest,'publish_before_thread_cpu_ns'),field(dest,'publish_after_thread_cpu_ns'),w,'thread_cpu_ms',reason(dest_status))
                    if gateway['mode'] in ('B','C'):
                        native_targets.append(dict(kind='health',flow=flow,message_id=r['native_message_id'],sequence=seq,robot=name,
                            R_intake_mono_ns=r['mono_ns'],accepted=bool(accepted),C_callback_mono_ns=field(cb,'callback_entry_mono_ns'),
                            source_publish_begin_mono_ns=rawbegin,source_publish_end_mono_ns=rawend,
                            queued_mono_ns=field(frame,'queued_monotonic_ns'),socket_flushed_mono_ns=field(frame,'socket_frame_flushed_monotonic_ns'),
                            native_meta=endpoint,match_status=dict(callback=cb_status,frame=frame_status,endpoint=endpoint_status)))
                    identity('health_C_R_existing_CDR',None if capture is None or dest is None else capture['cdr_sha256']==dest['cdr_sha256'] and capture['bytes']==dest['cdr_bytes'],reason(capture_status,dest_status) or 'matched')
                    identity('health_producer_C_existing_CDR',None if capture is None or binding is None else binding['health_cdr_sha256']==capture['cdr_sha256'],reason(capture_status,binding_status) or 'matched')
                add(prefix+'source_generated_age_at_observed_R_clock',None if state is None or now is None else (now/1e9-state['generated_sim'])*1000,w,'sim_ms',reason(source_status))
                for owner in ('tb1','tb2','tb3'):
                    for kind in ('odom','correction'):
                        add(prefix+f'{owner}_{kind}_age_at_observed_R_clock',None if state is None or now is None else (now/1e9-state[kind+'_stamps'][owner])*1000,w,'sim_ms',reason(source_status))
            if accepted:previous=r
        masks=([r for r in direct['masks'] if r['robot']==robot] if direct is not None else
            [r for r in gateway.get('bound_masks',[]) if r['native']['flow']==20*robot+10])
        previous=None;accepted_count=0;rejected_count=0
        for r in masks:
            before=r['validation_after_monotonic_ns'] if direct is not None else r['accept_bound_before_monotonic_ns']
            after=r['accept_after_monotonic_ns'] if direct is not None else r['accept_bound_after_monotonic_ns']
            if inside(before):
                accepted_count+=bool(r['accepted']);rejected_count+=not r['accepted'];binding=r['binding'];seq=binding['bound_state']['sequence']
                w=dict(robot=name,flow=20*robot+10,sequence=seq,native=None if direct is not None else r['native'],accept_before_mono_ns=before,accept_after_mono_ns=after)
                span(name+'/mask/wrapper_capture_to_accept_before',binding['captured_monotonic_ns'],before,w)
                span(name+'/mask/guard_call_bracket',before,after,w)
                if direct is not None:span(name+'/mask/A0_validation_wall',r['validation_before_monotonic_ns'],r['validation_after_monotonic_ns'],w)
                else:
                    key=(20*robot+10,ident(r['native']))
                    entry,entry_status=match(complete,complete_counts,key,name+'/mask/Gateway_complete')
                    endpoint,endpoint_status=match(endpoints,endpoint_counts,key,name+'/mask/endpoint','not_applicable' if gateway['mode']=='A' else 'matched')
                    if gateway['mode'] in ('B','C'):
                        native_targets.append(dict(kind='mask',flow=key[0],message_id=key[1],sequence=seq,robot=name,
                            R_accept_before_mono_ns=before,R_accept_after_mono_ns=after,accepted=bool(r['accepted']),
                            binding_capture_mono_ns=binding['captured_monotonic_ns'],native_meta=endpoint))
                    span(name+'/mask/Gateway_complete_to_accept_before',None if entry is None else entry['monotonic_ns'],before,w,failure=reason(entry_status))
                    span(name+'/mask/Hub_receive_to_endpoint_receive',None if endpoint is None else endpoint.get('hub_receive_monotonic_ns'),None if endpoint is None else endpoint.get('endpoint_receive_monotonic_ns'),w,failure=reason(endpoint_status))
                    span(name+'/mask/endpoint_receive_to_accept_before',None if endpoint is None else endpoint.get('endpoint_receive_monotonic_ns'),before,w,failure=reason(endpoint_status))
                origin,pub_status=match(pub,pub_dups,(name,seq),name+'/mask/producer_publication')
                identity('mask_binding_original_publication',None if origin is None else origin==binding,pub_status)
                state,state_status=match(source,source_dups,seq,name+'/mask/source')
                m=None if state is None else state.get('delivery_timing',{}).get('masks',{}).get(name)
                span(name+'/mask/original_publish_end_to_accept_before_signed',None if m is None else round(m['after_publish']*1e9),before,w,failure=reason(state_status))
                if r['accepted']:
                    pb=None if previous is None else (previous['validation_after_monotonic_ns'] if direct is not None else previous['accept_bound_before_monotonic_ns'])
                    pa=None if previous is None else (previous['accept_after_monotonic_ns'] if direct is not None else previous['accept_bound_after_monotonic_ns'])
                    span(name+'/mask/accepted_mono_gap_lower',pa,before,w)
                    span(name+'/mask/accepted_mono_gap_upper',pb,after,w)
            if r['accepted']:previous=r
        cohorts[name].update(mask_accepted=accepted_count,mask_rejected=rejected_count)
    longspans=gateway.get('dispatch_cpu_profile',{}).get('longspans',[])
    for r in longspans:
        if inside(r['end_monotonic_ns']):
            w=dict(stage=r['stage'],begin_monotonic_ns=r['begin_monotonic_ns'],end_monotonic_ns=r['end_monotonic_ns'])
            span('dispatch_longspan_ge10ms/'+r['stage']+'/wall',r['begin_monotonic_ns'],r['end_monotonic_ns'],w)
            span('dispatch_longspan_ge10ms/'+r['stage']+'/threadCPU',r['begin_thread_cpu_ns'],r['end_thread_cpu_ns'],w,'thread_cpu_ms')
    flows={};capture_hashes=defaultdict(Counter);delivery_hashes=defaultdict(Counter)
    for side,tables in gateway.get('topics',{}).items():
        for kind,rows in tables.items():
            counts=Counter();normal=Counter();sizes=Counter()
            for r in rows:
                flow=r['flow'];counts[flow]+=1;sizes[flow]+=r['bytes'] if kind=='captured' else r['cdr_bytes']
                ns=r.get('endpoint_capture_monotonic_ns') if kind=='captured' else r.get('endpoint_publish_monotonic_ns')
                if inside(ns):normal[flow]+=1
                (capture_hashes if kind=='captured' else delivery_hashes)[flow][r['cdr_sha256']]+=1
            flows[side+'/'+kind]=dict(whole_counts=dict(counts),normal_event_counts=dict(normal),whole_CDR_bytes=dict(sizes))
    for kind in ('action_CDR_capture','action_CDR_actual_destination'):
        rows=[r for r in gateway['records'] if r['kind']==kind];counts=Counter();normal=Counter()
        for r in rows:
            flow=r['flow'] if kind=='action_CDR_capture' else r['meta']['flow']
            counts[flow]+=1
            if inside(r['monotonic_ns']):normal[flow]+=1
            (capture_hashes if kind=='action_CDR_capture' else delivery_hashes)[flow][r['cdr_sha256']]+=1
        flows[kind]=dict(whole_counts=dict(counts),normal_event_counts=dict(normal),scope='Actual ActionWire CDR observations, retries may create repeated samples; not unique Goals')
    flows['HubClient_complete_deliveries']=dict(whole_counts=dict(Counter(r['flow'] for r in gateway.get('hub_deliveries',[]))),
        normal_event_counts=dict(Counter(r['flow'] for r in gateway.get('hub_deliveries',[]) if inside(r['endpoint_receive_monotonic_ns']))),
        scope='Native whole application-body completions with RPC prefix, includes link qualification flows; NOT TCP application-fragment/frame count or ROS-only count')
    cdr={str(flow):dict(captured=sum(capture_hashes[flow].values()),delivered=sum(delivery_hashes[flow].values()),
        existing_hash_multiset_overlap=sum((capture_hashes[flow]&delivery_hashes[flow]).values()),
        whole_existing_hash_multisets_equal=capture_hashes[flow]==delivery_hashes[flow]) for flow in capture_hashes.keys()|delivery_hashes.keys()}
    if direct is not None:flows['A0_direct_observations_NOT_native_flow_counts']=dict(health=dict(Counter(r['robot'] for r in direct['health'])),masks=dict(Counter(r['robot'] for r in direct['masks'])))
    faults={robot:dict(whole=[r for r in g['events'] if r['kind']=='latched_INVALID'],
        inside_clock_bracket=[r for r in g['events'] if r['kind']=='latched_INVALID' and inside(round(r['monotonic']*1e9))]) for robot,g in gateway['guards'].items()}
    stages={}
    for name,total in attempts.items():
        unavailable_counts=unavailable[name];n=len(values[name])
        stages[name]=dict(**stats(values[name],stage_units[name]),
            total=total,matched=n,missing=sum(v for k,v in unavailable_counts.items() if k not in ('ambiguous','not_applicable')),
            ambiguous=unavailable_counts['ambiguous'],not_applicable=unavailable_counts['not_applicable'],
            unavailable_detail=dict(unavailable_counts),worst=worst.get(name))
        if n==0 and unavailable_counts['not_applicable']==total:stages[name]['status']='NOT_APPLICABLE'
    identity_summary={}
    for name in ('health_C_R_existing_CDR','health_producer_C_existing_CDR','mask_binding_original_publication'):
        counts=identities[name]
        identity_summary[name]=dict(status='NOT_MEASURED' if not counts['measured'] else 'MEASURED_SAMPLES_NOT_GLOBAL_PASS',
            total=counts['total'],measured=counts['measured'],equal=counts['equal'],mismatch=counts['mismatch'],
            missing=counts['missing']+counts['missing_fields'],ambiguous=counts['ambiguous'])
    index_ambiguity={name:dict(ambiguous_keys=sum(n>1 for n in counts.values()),excluded_rows=sum(n for n in counts.values() if n>1))
        for name,counts in [('peer',source_dups),('publication',pub_dups),('raw_health',raw_dups),('C_callback',cb_dups),
            ('C_capture',capture_counts),('R_publication',delivery_counts),('endpoint',endpoint_counts),('Gateway_complete',complete_counts)]}
    return dict(window=window,cohorts=cohorts,stages=stages,native_targets=native_targets,flow_counts=flows,whole_CDR_existing_hash_counts=dict(status='MEASURED_COUNTS_NOT_DELIVERY_PASS' if cdr else 'NOT_MEASURED',flows=cdr),
        matched_CDR_binding_checks=identity_summary,matching_coverage={k:dict(total=v['total'],matched=v['matched'],missing=v['missing'],ambiguous=v['ambiguous'],not_applicable=v['not_applicable'],detail={a:b for a,b in v.items() if a not in ('total','matched','missing','ambiguous','not_applicable')}) for k,v in coverage.items()},ambiguous_index_rows=index_ambiguity,
        actual_faults=faults,original_result=dict(error=result.get('error'),hazard=result.get('hazard'),run_integrity=result.get('run_integrity'),scope='RAW_ORIGINAL_FIELDS_ONLY_NOT_PROCESS_ACCEPTANCE'),
        Gateway=dict(mode=gateway['mode'],failure=gateway['failure'],cleanup=gateway['cleanup'],
            last_receipts_not_a_distribution={robot:{k:v for k,v in g.items() if 'receipt' in k or k=='control_permission_revoked'} for robot,g in gateway['guards'].items()},
            whole_dispatch_statistics=gateway.get('dispatch_stats'),whole_dispatch_aggregates=gateway.get('dispatch_cpu_profile',{}).get('aggregates')),
        native_meta_scope='Gateway has native RX sim stamp only; source_stamp is original ROS header, never native TX. No model TX/admission/PHY airtime inferred, no native ledger or PCAP reads.',
        UNMEASURED=['Per-message exact health/mask receipt_sim (not persisted in these packet rows; final Guard fields are last-only)',
            'Mask C callback entry/socket queue/flush (not traced)', 'Native model TX/admission and exact transport-only model latency',
            'All-call normal dispatch percentiles/CPU totals (only >=10ms longspans are phase-selectable; whole aggregates remain whole)'],
        NOT_APPLICABLE=['A0 C-business adapter/queue/native-business stages'] if direct is not None else (['A1 native WiFi business/health Hub socket-frame stages'] if gateway['mode']=='A' else []),
        semantics=['mono_ns/time.monotonic same-host wall; ROS/ns3 clocks named sim and never subtracted from monotonic',
            'Signed publish-end spans may overlap callbacks; negative samples retained and counted. Do not sum overlapping spans or inclusive dispatch parents/children.',
            'Health source age uses actual observed R node clock: A0 after-call vs adapter before-call, not exact receipt_sim or continuous safety supremum.',
            'Mask mono receipt lies inside before/after bracket; accepted predecessor may precede normal bracket. No >300wall pass/fail test under new contract.',
            'Whole capture/delivery hash cohorts and normal capture/delivery event cohorts differ at boundaries; count differences are not loss estimates.',
            'Stage percentiles nearest-rank ceil(p*n), median arithmetic; worst is one actual matching witness, no full-cache copy.',
            'Diagnostic measurement cost and different trajectories/loads/sourceavailability remain; cross-arm differences do not alone isolate CPU or RF causes.'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    admission=json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:parser.error('Inert exporter: Root one-load START required after all models/writers exit')
    args.directory.mkdir(parents=True,exist_ok=False);manifest=dict(status='STARTED',cases=[],source='No runtime modules imported',ledger_reads=0,PCAP_reads=0,bag_reads=0)
    try:
        for spec in admission['cases']:
            case=REPO/spec['case'];reads=Counter();parse={}
            def read(name):
                key=str(name);path=case/name;reads[key]+=1;t=time.monotonic()
                with path.open() as stream:value=json.load(stream)
                parse[key]=dict(bytes=path.stat().st_size,read_decode_wall_s=time.monotonic()-t);return value
            def lines(name):
                reads[name]+=1
                with (case/name).open() as stream:
                    for line in stream:yield json.loads(line)
            # Resolve source from this case's actual launched admission, not
            # a planned source label (C may add reviewed observation only).
            used_path=case.with_name(case.name+'.admission-used.json')
            source_identity=dict(status='NOT_MEASURED',actual_admission=str(used_path))
            if used_path.exists():
                used=read(used_path);ready_path=Path(used['ready_path'])
                if ready_path.is_relative_to('/mnt'):ready_path=REPO/ready_path.relative_to('/mnt')
                launched=read(ready_path)
                source_identity=dict(status='ACTUAL_LAUNCHED_ADMISSION_FIELDS',admission_used=str(used_path),ready_path=str(ready_path),
                    recorded_ready_sha256=used.get('ready_sha256'),runtime_base_source_commit=launched.get('runtime_base_source_commit'),
                    candidate_source_commit=launched.get('candidate_source_commit'),adapter_source_commit=launched['network'].get('adapter_source_commit'),
                    frozen_source_commit=launched.get('source_commit'),current_ready_bytes_rehashed=False,
                    execution_profile=launched['network'].get('execution_profile'),
                    adapter_binding=launched['network'].get('adapter_binding_relative_repo'),
                    declared_adapter_sha256=launched['network'].get('adapter_sha256'),
                    controller_observation_options={k:v for k,v in launched['network'].items()
                        if any(label in k for label in ('bootstrap','controller','exception','observation'))},
                    scope='Recorded actual launch-ready path/hash plus its explicit source fields; no planned-AAE substitution, hash recomputation or source equivalence inference')
            reviewed_summary=REPO/spec['observed_small_summary']
            observed=read(reviewed_summary) if reviewed_summary.exists() else {}
            preserved_outcome=dict(explicit_reviewed_case_verdict=spec['reviewed_case_verdict'],
                authoritative_review=spec['independent_review'],observed_summary=str(reviewed_summary),
                observed_summary_status='LOADED' if observed else 'NOT_MEASURED',
                observed_process_and_raw_fields={k:v for k,v in observed.items() if 'controller' in k or 'exit' in k or k in ('status','run_integrity','network_run_integrity','error','hazard')},
                scope='Preserve original raw success fields independently from process verdict; metrics/empty ownership do not override controller nonzero')
            gateway=read('network-gateway.json')
            direct=read('a0-direct-safety.json') if spec['arm']=='A0' else None
            result=read('result.json');timing=read('observer_timing.json')
            bound=None
            for r in lines('events.jsonl'):
                if r['kind']=='smoke_bound':bound=r
            peer=list(lines('peer-keepout.jsonl'));raw=read('health-trace.json');publications=list(lines('bound-mask-publications.jsonl'))
            summary=export_loaded(gateway,direct,result,timing,bound,peer,raw,publications)
            summary.update(case=spec,actual_source_identity=source_identity,case_outcome=preserved_outcome,read_counts=dict(reads),JSON_parse_metadata=parse,
                source_protocol='Per-case actual launched admission fields retained, including later C source/observation changes; no common-source substitution or inferred process PASS')
            targets=summary.pop('native_targets')
            with (args.directory/(spec['arm']+'-native-targets.jsonl')).open('x') as stream:
                for target in targets:stream.write(json.dumps(target)+'\n')
            summary['native_target_cache']=dict(path=spec['arm']+'-native-targets.jsonl',rows=len(targets),
                scope='Only matched normal R-consumed health/mask IDs; not full Gateway cache, native ingress cohort, loss denominator or permission to scan ledger')
            with (args.directory/(spec['arm']+'.json')).open('x') as stream:json.dump(summary,stream,indent=2);stream.write('\n')
            manifest['cases'].append(dict(arm=spec['arm'],case=spec['case'],read_counts=dict(reads),window=summary['window'],summary=spec['arm']+'.json'))
            del gateway,direct,summary,peer,raw,publications
        manifest['status']='EXPORTED_ONLY_NO_QUALIFICATION_CHANGE'
    except BaseException as error:manifest.update(status='FAIL_FIRST_ERROR_PRESERVED',error=repr(error));raise
    finally:(args.directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

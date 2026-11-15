"""Post-exit hold-queue evidence only; release means ready for dispatch, not delivery."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics


def stats_ns(values):
    values=sorted(v/1e6 for v in values)
    if not values:return dict(n=0,mean=None,sd=None,p95=None,max=None)
    return dict(n=len(values),mean=statistics.mean(values),sd=statistics.stdev(values) if len(values)>1 else None,
        p95=values[max(0,math.ceil(.95*len(values))-1)],max=values[-1])


def queue_stats(rows):
    return dict(frames=len(rows),hold_wall_ms=stats_ns([r['release_monotonic_ns']-r['capture_monotonic_ns'] for r in rows]),
        release_lateness_wall_ms=stats_ns([r['release_monotonic_ns']-r['due_monotonic_ns'] for r in rows]))


def analyze_hold_data(data,start_ns,end_ns,topic_captures):
    errors=[];rows=data['frames'];close=data['close'];delay=data['delay_ns']
    if data['schema']!='ros-local-wall-delay-fifo-v1' or data['clock']!='time.monotonic_ns':errors.append('queue_schema_or_clock_mismatch')
    if close is None:
        errors.append('queue_close_marker_missing');close_begin=None
    else:
        close_begin=close['begin_monotonic_ns']
        if close_begin>close['end_monotonic_ns'] or close['parent_bounds_unchanged'] is not True:errors.append('queue_close_order_or_bounds_invalid')
        if close['admitted_frames_pending']!=0:errors.append('queue_not_closed')
    identities=[r['sequence'] for r in rows]
    if len(set(identities))!=len(identities):errors.append('duplicate_queue_sequence')
    captures=defaultdict(list);topic_capture_denominator=0;unmatched_capture_refs=[]
    queue_ids={(r['flow'],r['sequence']) for r in rows}
    for side,capture in topic_captures:
        if not start_ns<=capture['capture_node_sim_ns']<end_ns:continue
        topic_capture_denominator+=1
        identity=capture.get('direct_native_id')
        if identity is None or (capture['flow'],identity) not in queue_ids:
            unmatched_capture_refs.append(dict(side=side,flow=capture['flow'],direct_native_id=identity,capture_seq=capture.get('capture_seq'),capture_sim_ns=capture['capture_node_sim_ns']))
        if identity is not None:captures[(capture['flow'],identity)].append((side,capture))
    stage_counts=Counter();capture_counts=Counter();window_rows=[];released_in_window=[];released_capture_cohort=[]
    topic_window=[];topic_released=[];topic_references=[];match_counts=Counter()
    all_business_by_flow=defaultdict(Counter)
    for row in rows:
        capture=row['capture_monotonic_ns'];release=row['release_monotonic_ns'];sim=row['capture_sim_ns'];due=row['due_monotonic_ns']
        if due!=capture+delay:errors.append('queue_due_not_capture_plus_declared_delay')
        capture_stage='before_window' if sim<start_ns else 'capture_in_window' if sim<end_ns else 'at_or_after_window'
        capture_counts[capture_stage]+=1
        if release is None:
            stage='not_released'
        else:
            if release<due or row.get('injected_hold_ns')!=release-capture or row.get('release_overshoot_ns')!=release-due:
                errors.append('queue_release_time_or_duration_invalid')
            release_sim=row.get('release_sim_ns')
            if type(release_sim) is not int:
                stage='release_sim_unmeasured';errors.append('queue_release_sim_unmeasured')
            elif close_begin is not None and release>=close_begin:
                stage='closing_drain'
            elif row.get('release_phase')=='closing_drain':
                stage='closing_drain'
            elif release_sim<start_ns:stage='release_before_window'
            elif release_sim<end_ns:stage='release_in_window'
            else:stage='release_at_or_after_window_before_close'
        stage_counts[stage]+=1;all_business_by_flow[str(row['flow'])][stage]+=1
        captured=start_ns<=sim<end_ns
        if captured:window_rows.append((row,stage))
        if stage=='release_in_window':released_in_window.append(row)
        if captured and stage=='release_in_window':released_capture_cohort.append(row)
        matches=captures.get((row['flow'],row['sequence']),[])
        if not matches:continue
        if len(matches)!=1:
            match_counts['AMBIGUOUS_CAPTURE_ID']+=1;continue
        side,source=matches[0]
        topic_in_window=start_ns<=source['capture_node_sim_ns']<end_ns
        if not topic_in_window:continue
        match_counts['UNIQUE_OBSERVED_TOPICWIRE_CAPTURE']+=1;topic_window.append((row,stage))
        if stage=='release_in_window':topic_released.append(row)
        topic_references.append(dict(sequence=row['sequence'],sender=row['sender'],receiver=row['receiver'],flow=row['flow'],
            rpc_id=row['rpc_id'],bytes=row['bytes'],queue_capture_sim_ns=sim,release_sim_ns=row.get('release_sim_ns'),
            release_stage=stage,topic_capture_side=side,topic_capture_seq=source.get('capture_seq'),
            topic_capture_sim_ns=source['capture_node_sim_ns'],source_topic=source.get('source_topic'),
            original_CDR_sha256=source.get('cdr_sha256')))
    if any(r['release_monotonic_ns'] is None for r in rows):errors.append('admitted_queue_frames_not_released_at_persist')
    def cohort(values,released):
        count=Counter(stage for _,stage in values)
        return dict(capture_denominator=len(values),release_within_actual_window=len(released),
            not_released_by_window_end=len(values)-len(released),release_stage_counts=dict(count),
            released_within_window=queue_stats(released))
    return dict(schema='ros-delay-hold-postexit-v1',applicable=True,measurement_valid=not errors,
        measurement_errors=sorted(set(errors)),observed_nominal_delay_wall_ms=delay/1e6,
        actual_window_sim_ns=[start_ns,end_ns],interval='Half-open [start,end), excluding closing_drain regardless of frozen clock',
        all_business=dict(total_admitted_frames=len(rows),capture_stage_counts=dict(capture_counts),release_stage_counts=dict(stage_counts),
            by_flow={k:dict(v) for k,v in all_business_by_flow.items()},
            window_capture_cohort=cohort(window_rows,released_capture_cohort),
            window_release_cohort=queue_stats(released_in_window)),
        matched_topicwire_window_capture_cohort=dict(**cohort(topic_window,topic_released),
            observed_identity_match_counts=dict(match_counts),frame_references=topic_references,
            total_topicwire_window_captures=topic_capture_denominator,
            unmatched_capture_references=unmatched_capture_refs,
            matched_subset_is_all_window_captures=(len(topic_references)==topic_capture_denominator),
            scope='Unique observed TopicWire captures by original direct_native_id/flow, not all business or all source publications'),
        close=close,proxy_admission_rejections=data['proxy_admission_rejections'],
        outside_closed_admission_epoch=data['outside_closed_admission_epoch'],
        semantics='All business includes Action/BoundMask/control data admitted to this FIFO; matched TopicWire subset is separate. Hold release is departure to original dispatch-ready batch, not destination publish/HQ take. Window capture cohort and release cohort are different denominators. No nominal-delay or RTF imputation; eventual/closing-drain releases never enter task-window mean.')


def analyze_hold_queue(case,path,start_ns,end_ns,topic_captures):
    if path=='A0':return dict(applicable=False,status='N/A_LITERAL_ROS_DIRECT',measurement_valid=True,measurement_errors=[])
    source=Path(case)/'ros-delay-queue.json'
    if not source.is_file():return dict(applicable=True,measurement_valid=False,measurement_errors=['queue_trace_missing'])
    result=analyze_hold_data(json.loads(source.read_text()),start_ns,end_ns,topic_captures)
    result['source_queue_file']=str(source);return result

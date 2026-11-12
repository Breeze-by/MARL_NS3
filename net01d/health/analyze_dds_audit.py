"""Exact source-system-time bracket joins for saved DDS takes; no ROS or replay."""
import argparse
import bisect
from collections import Counter,defaultdict
import json
from pathlib import Path

from analyze_history import summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    with (args.case/'gateway/network-gateway.json').open() as stream:
        gateway=json.load(stream)
    source_groups=defaultdict(list);matched_changes={};source_counts={}
    for robot in (1,2,3):
        with (args.case/f'source-tb{robot}/full-source.json').open() as stream:
            source=json.load(stream)
        matched_changes[str(robot)]=[r for r in source['records'] if r['kind']=='tf_matched_readers_changed']
        for row in source['records']:
            if 'dds_source_trace' in row:
                source_groups[(robot*20+3,row['kind'])].append(row)
    starts={}
    for key,rows in source_groups.items():
        rows.sort(key=lambda r:r['dds_source_trace']['before_realtime_ns'])
        starts[key]=[r['dds_source_trace']['before_realtime_ns'] for r in rows]
        source_counts[str(key)]=len(rows)
    taken=[r for r in gateway['health_trace']['rows'] if r['stage']=='R_TF_take']
    joined=defaultdict(list);unmatched=[];metadata_keys=Counter();none_takes=Counter()
    used=Counter()
    for row in taken:
        metadata=row.get('metadata')
        if metadata is None:
            none_takes[row['flow']]+=1;continue
        metadata_keys[tuple(sorted(metadata))]+=1
        edges=row.get('tf_edges',[])
        first=edges[0] if edges else {}
        kind=('both_wheel_TF' if first.get('frame_id')=='base_link' else
            first.get('frame_id','?')+'->'+first.get('child_frame_id','?'))
        key=row['flow'],kind;stamp=metadata.get('source_timestamp',0)
        candidates=source_groups.get(key,[])
        index=bisect.bisect_right(starts.get(key,[]),stamp)-1
        if index<0 or stamp>candidates[index]['dds_source_trace']['after_realtime_ns']:
            unmatched.append(dict(flow=row['flow'],kind=kind,metadata=metadata,take_mono_ns=row['mono_ns'],tf_edges=edges));continue
        source=candidates[index];pub=source['dds_source_trace']
        used[(key,pub['publication_ordinal'])]+=1
        pair=dict(flow=row['flow'],kind=kind,publication_ordinal=pub['publication_ordinal'],
            source_stamp_ns=source['source_stamp_ns'],source_matched_readers=pub['matched_readers'],
            source_publish_before_mono_ns=source['before_monotonic_ns'],
            source_publish_return_mono_ns=source['after_monotonic_ns'],
            source_before_realtime_ns=pub['before_realtime_ns'],source_after_realtime_ns=pub['after_realtime_ns'],
            metadata=metadata,take_before_mono_ns=row['mono_ns'],take_end_mono_ns=row['end_mono_ns'],
            take_before_realtime_ns=row['before_realtime_ns'],take_end_realtime_ns=row['end_realtime_ns'],
            R_sim_before_ns=row['ros_sim_before_ns'],
            source_return_to_take_begin_ms=(row['mono_ns']-source['after_monotonic_ns'])/1e6,
            source_timestamp_to_take_realtime_ms=(row['before_realtime_ns']-stamp)/1e6,
            take_wall_ms=(row['end_mono_ns']-row['mono_ns'])/1e6,
            take_thread_CPU_ms=(row['end_thread_cpu_ns']-row['thread_cpu_ns'])/1e6,
            source_before_to_pre_publish_realtime_sample_ms=(pub['before_realtime_mono_after_ns']-source['before_monotonic_ns'])/1e6)
        received=metadata.get('received_timestamp',0)
        if received:
            pair['source_to_RMW_received_realtime_ms']=(received-stamp)/1e6
            pair['RMW_received_to_take_begin_realtime_ms']=(row['before_realtime_ns']-received)/1e6
        joined[key].append(pair)
    groups={}
    for key,sources in source_groups.items():
        rows=joined.get(key,[])
        metrics={}
        for name in ('source_return_to_take_begin_ms','source_timestamp_to_take_realtime_ms',
                'source_to_RMW_received_realtime_ms','RMW_received_to_take_begin_realtime_ms',
                'take_wall_ms','take_thread_CPU_ms','source_before_to_pre_publish_realtime_sample_ms'):
            metrics[name]=summary([r[name] for r in rows if name in r])
        groups[str(key)]=dict(source_publications=len(sources),strict_system_bracket_joins=len(rows),
            source_ordinals_not_observed=[r['dds_source_trace']['publication_ordinal'] for r in sources
                if not used[(key,r['dds_source_trace']['publication_ordinal'])]],
            matched_reader_counts=sorted(set(r['dds_source_trace']['matched_readers'] for r in sources)),
            first_source_publication=sources[0],first_joined_take=rows[0] if rows else None,
            worst_source_to_take=sorted(rows,key=lambda r:r['source_return_to_take_begin_ms'],reverse=True)[:3],
            statistics=metrics)
    components=dict(scope='Raw small component subset copied while original Gateway was loaded; no component judgement',
        guards=gateway['guards'],cleanup=gateway['cleanup'],
        topics={side:{family:[r for r in gateway['topics'][side][family] if r['flow'] in (89,95)]
            for family in ('captured','delivered')} for side in ('C','R')})
    with (args.out/'component-subset.json').open('x') as stream:
        json.dump(components,stream,indent=2);stream.write('\n')
    with (args.out/'health-control-subset.json').open('x') as stream:
        json.dump(dict(health_trace=[r for r in gateway['health_trace']['rows']
            if r['stage']!='R_TF_take'],bound_masks=gateway.get('bound_masks',[]),
            clock_control_trace=gateway.get('clock_control_trace'),
            dispatch_cpu_profile=gateway.get('dispatch_cpu_profile'),
            dispatch_stats=gateway.get('dispatch_stats')),stream,indent=2)
        stream.write('\n')
    result=dict(case=str(args.case.resolve()),scope='Saved no-motion DDS audit; source/received are system-time metadata, take wall is mono',
        take_rows=len(taken),empty_take_counts=dict(none_takes),
        metadata_key_sets=[dict(keys=list(k),n=n) for k,n in metadata_keys.items()],
        strict_bracket_joined=sum(map(len,joined.values())),unmatched_take_count=len(unmatched),unmatched_takes=unmatched,
        duplicate_join_identities=[str(key) for key,n in used.items() if n>1],
        matched_reader_changes=matched_changes,groups=groups,
        boundaries=['source get_subscription_count is endpoint matching, not delivery ACK',
            'source before-to-realtime sample includes matched-count query and bookkeeping, not isolated getter cost',
            'RMW received_timestamp is not independently established as earliest DDS arrival or reader-ready time',
            'No GID or sequence number is exposed by this installed Python metadata; repeated TF header is not unique',
            'Strict source realtime bracket + flow + writer kind defines the join, no nearest-time or tolerance substitution',
            'Diagnostic overhead may change scheduling; nonrecurrence is not a behavior repair'])
    with (args.out/'summary.json').open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(take_rows=len(taken),joined=result['strict_bracket_joined'],unmatched=len(unmatched),
        metadata_keys=result['metadata_key_sets'],groups={k:{'source':v['source_publications'],
            'joined':v['strict_system_bracket_joins'],'matched_counts':v['matched_reader_counts'],
            'first_ordinal':None if v['first_joined_take'] is None else v['first_joined_take']['publication_ordinal'],
            'first_delay_ms':None if v['first_joined_take'] is None else v['first_joined_take']['source_return_to_take_begin_ms'],
            'stats':v['statistics']} for k,v in groups.items()}),indent=2))


if __name__=='__main__':
    main()

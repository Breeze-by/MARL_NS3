"""Saved full-window result summary; no experiment or historical reads."""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path


def stats(values):
    values=sorted(values)
    if not values:return dict(n=0)
    return dict(n=len(values),median=values[(len(values)-1)//2],p95=values[math.ceil(.95*len(values))-1],
                p99=values[math.ceil(.99*len(values))-1],max=values[-1],min=values[0])


def edgekey(edges,stamp):
    return tuple((e['frame_id'],e['child_frame_id'],e[stamp]) for e in edges)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=Path,required=True)
    args=parser.parse_args();b=args.case
    host=json.loads((b/'result.json').read_text());g=json.loads((b/'gateway/network-gateway.json').read_text())
    source=json.loads((b/'source/result.json').read_text())['inputs']
    tail=json.loads((b/'source/tail-result.json').read_text())
    peer=[json.loads(x) for x in (b/'peer/peer-keepout.jsonl').read_text().splitlines()]
    phase=json.loads((b/'gateway/active-phase-profile.json').read_text());inc=phase['increment'];cpu=inc['cpu_profile']
    published=defaultdict(list)
    for row in source+tail['inputs']:
        if row['state']=='PUBLISHED' and row['flow'] in (23,43,63):
            published[(row['flow'],edgekey(row['original_tf_edges'],'source_stamp_ns'))].append(row)
    counts=Counter();groups=defaultdict(lambda:defaultdict(list));matched_ids=defaultdict(set)
    for row in g['health_trace']['rows']:
        if row['stage']!='R_TF_take' or not row.get('taken'):continue
        counts['all_taken']+=1;meta=row.get('metadata') or {}
        s=meta.get('source_timestamp',0);r=meta.get('received_timestamp',0)
        if not (s>0 and r>=s and row['end_realtime_ns']>=r):
            counts['invalid_metadata']+=1;continue
        low=s-row['before_realtime_ns']+row['mono_ns']
        high=s-row['before_realtime_ns']+row['before_realtime_mono_after_ns']
        candidates=[v for v in published[(row['flow'],edgekey(row.get('tf_edges',[]),'stamp_ns'))]
                    if v['before_monotonic_ns']<=high and v['after_monotonic_ns']>=low]
        if len(candidates)!=1:
            counts['projection_unmatched' if not candidates else 'projection_ambiguous']+=1;continue
        item=candidates[0]
        if item['phase']!='normal':
            counts['matched_closing_tail']+=1;continue
        counts['matched_main']+=1;matched_ids[row['flow']].add(item['ordinal'])
        flow=row['flow'];values=dict(source_to_RMW_received_ms=(r-s)/1e6,
            reported_received_to_take_ms=(row['before_realtime_ns']-r)/1e6,
            source_timestamp_to_take_ms=(row['before_realtime_ns']-s)/1e6,
            publication_return_to_take_ms=(row['mono_ns']-item['after_monotonic_ns'])/1e6,
            take_wall_ms=(row['end_mono_ns']-row['mono_ns'])/1e6,
            realtime_mono_bracket_width_ms=(row['before_realtime_mono_after_ns']-row['mono_ns'])/1e6)
        for name,value in values.items():groups[flow][name].append(value)
    first_arm={r:min((e['sim'] for e in guard['events'] if e['kind']=='armed'),default=None)
               for r,guard in g['guards'].items()}
    healthy_begin=max(v for v in first_arm.values() if v is not None)
    active_peer=[row for row in peer if healthy_begin<=row['generated_sim']<=60.000001]
    guard_samples={r:dict(max_source_age_sim_s=max(row['ages']['tb'+r]['source'] for row in active_peer),
        max_correction_age_sim_s=max(row['ages']['tb'+r]['correction'] for row in active_peer),
        max_odom_receipt_wall_s=max(row['ages']['tb'+r]['receipt'] for row in active_peer)) for r in first_arm}
    parts={side+'_'+category:sum(v['thread_cpu_ns'] for v in cpu[side][category].values())
           for side in ('C','R') for category in ('wait','handlers')}
    parts['progress_inclusive']=cpu['progress']['total_inclusive']['thread_cpu_ns']
    parts['idle_event_wait']=cpu['progress']['idle_event_wait']['thread_cpu_ns']
    parts['bookkeeping']=cpu['progress']['poll_inclusive']['thread_cpu_ns']-sum(parts.values())
    owned=json.loads((b/'owned.json').read_text());native=json.loads((b/'native-load-proof.json').read_text())['native']
    pids={r:v['pid'] for r,v in owned.items()};pids['native']=native['pid']
    result=dict(arm=host['arm'], host_exit_success=host['error'] is None and not host['forced'] and all(v==0 for v in host['exits'].values()),
        primary_source=dict(planned=len(source),published=sum(v['state']=='PUBLISHED' for v in source),
            TF_normal_planned={str(f):sum(v['flow']==f and v['phase']=='normal' for v in source) for f in (23,43,63)}),
        tail={k:tail[k] for k in ('planned','published','censored')},
        main_TF_take_counts=dict(counts),main_TF_unique_source_ordinals={str(f):len(ids) for f,ids in matched_ids.items()},
        main_TF_wall_metrics={str(f):{name:stats(values) for name,values in metrics.items()} for f,metrics in groups.items()},
        guards=dict(first_armed_sim=first_arm,latched_fault_counts={r:sum(e['kind']=='latched_INVALID' for e in guard['events']) for r,guard in g['guards'].items()},
            stored_Peer_active_main_snapshots=len(active_peer),stored_Peer_all_ready=all(row['ready'] for row in active_peer),
            sampled_freshness=guard_samples),
        active_profile=dict(start_gz=phase['start']['gz_ns'],end_gz=phase['end']['gz_ns'],end_reason=phase['end'].get('end_reason'),
            wall_ns=inc['wall_between_snapshot_brackets_ns'],thread_cpu_ns=inc['thread_cpu_between_snapshot_brackets_ns'],
            thread_cpu_wall_ratio=inc['thread_cpu_between_snapshot_brackets_ns']/inc['wall_between_snapshot_brackets_ns'],CPU_partition_ns=parts),
        actual_owned_pids=pids,owned_proc_exists_after_wait={r:Path('/proc',str(pid)).exists() for r,pid in pids.items()},
        boundaries=['Main TF cohort uses a unique projected source publication bracket; stable realtime/mono offset assumption, not exact CDR body identity.',
            'RMW reported received timestamp is not independently proven earliest DDS arrival.',
            'Peer freshness maxima describe stored snapshots after actual ARM, not a mathematical continuous supremum.',
            'Active profile includes actual closing/authority revocation through normal close entry, excluding persistence/resource teardown.',
            'Tail counts are separate; functional completion is not every-input wireless loss, physical stopping or Gazebo qualification.'])
    (b/'SUCCESS_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

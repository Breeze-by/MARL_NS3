"""Offline audit of this sealed fixture's actual C normal-phase interval."""
import bisect
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
CASE = OUT.parents[1] / 'runs' / 'actual-phase-local-01'


def load(path):
    with path.open() as stream:
        return json.load(stream)


def stats(values, unit):
    values = sorted(values)
    if not values:
        return dict(n=0, unit=unit)
    def percentile(p):
        import math
        return values[max(0, math.ceil(len(values)*p)-1)]
    return dict(n=len(values), unit=unit, min=values[0], median=statistics.median(values),
                p95=percentile(.95), p99=percentile(.99), max=values[-1])


client = load(CASE / 'client/full-client.json')
start = next(r for r in client['events'] if r['kind']=='fixture_normal_phase_start')
done = next(r for r in client['events'] if r['kind']=='fixture_normal_phase_done')
lo, hi = start['monotonic_ns'], done['monotonic_ns']
inside = lambda n: lo <= n <= hi
saved = load(OUT / 'health-control-subset.json')
peer = [json.loads(line) for line in (CASE/'peer/peer-keepout.jsonl').open()]
peer_seq = {r['sequence']:r for r in peer}
normal_health = {}
for flow in (31,51,71):
    rows = [r for r in saved['health_trace'] if r['stage']=='R_health_intake'
            and r['flow']==flow and inside(r['mono_ns'])]
    metrics = defaultdict(list)
    for r in rows:
        metrics['receipt_interval_from_actual_previous'].append(
            (r['actual_receipt_mono_s']-r['old_receipt_mono_s'])*1000)
        metrics['held_receipt_age_at_callback_entry'].append(
            r['mono_ns']/1e6-r['old_receipt_mono_s']*1000)
        now = r['R_node_sim_before_ns']/1e9
        for phase, sequence in (('held',r['old_sequence']),('incoming',r['sequence'])):
            state = peer_seq[sequence]
            for robot in ('tb1','tb2','tb3'):
                for kind, key in (('odom','odom_stamps'),('correction','correction_stamps')):
                    metrics[f'{phase}_{robot}_{kind}_age'].append((now-state[key][robot])*1000)
    normal_health[str(flow)] = dict(n=len(rows), sequences=[r['sequence'] for r in rows],
        all_armed=all(r['armed'] for r in rows),
        fault_before_count=sum(r['fault_before'] is not None for r in rows),
        fault_after_count=sum(r['fault_after'] is not None for r in rows),
        all_returned=all(r['returned'] for r in rows),
        first_interval_previous_receipt_inside_normal=inside(int(rows[0]['old_receipt_mono_s']*1e9)),
        statistics={k:stats(v,'sim_ms' if k.endswith('_age') and not k.startswith('held_receipt') else 'wall_ms')
                    for k,v in metrics.items()})

masks = {}
for flow in (30,50,70):
    all_rows = [r for r in saved['bound_masks'] if r['native']['flow']==flow and r['accepted']]
    intervals=[]; selected=[]; previous=None
    for r in all_rows:
        if inside(r['accept_bound_before_monotonic_ns']):
            selected.append(r)
            if previous is not None:
                intervals.append(dict(sequence=r['binding']['bound_state']['sequence'],
                    previous_sequence=previous['binding']['bound_state']['sequence'],
                    previous_inside_normal=inside(previous['accept_bound_before_monotonic_ns']),
                    lower_wall_ms=(r['accept_bound_before_monotonic_ns']-previous['accept_bound_after_monotonic_ns'])/1e6,
                    upper_wall_ms=(r['accept_bound_after_monotonic_ns']-previous['accept_bound_before_monotonic_ns'])/1e6))
        previous=r
    masks[str(flow)] = dict(n=len(selected),sequences=[r['binding']['bound_state']['sequence'] for r in selected],
        rejected_in_normal=sum(not r['accepted'] and inside(r['accept_bound_before_monotonic_ns'])
            for r in saved['bound_masks'] if r['native']['flow']==flow),
        interval_lower=stats([r['lower_wall_ms'] for r in intervals],'wall_ms'),
        interval_upper=stats([r['upper_wall_ms'] for r in intervals],'wall_ms'),
        accept_duration=stats([(r['accept_bound_after_monotonic_ns']-r['accept_bound_before_monotonic_ns'])/1e6
            for r in selected],'wall_ms'),first_interval=intervals[0],
        largest_upper_interval=max(intervals,key=lambda r:r['upper_wall_ms']))

source_groups=defaultdict(list);source_report={}
for robot in (1,2,3):
    source=load(CASE/f'source-tb{robot}/full-source.json')
    rows=source['records']
    for r in rows:
        if 'dds_source_trace' in r:source_groups[(20*robot+3,r['kind'])].append(r)
    emitted=Counter((r['kind'] for r in rows if 'before_monotonic_ns' in r and inside(r['before_monotonic_ns'])))
    source_report[str(robot)]=dict(normal_actual_publications_by_kind=dict(emitted),
        full_supply_actual_wall_s=source['active_supply_wall_s'],
        full_supply_begin_sim_ns=source['active_supply_begin_sim_ns'],full_supply_end_sim_ns=source['active_supply_end_sim_ns'],
        final_ticks=source['source_ticks'],final_skips=source['skipped_configured_ticks'],
        active_and_stop_baselines=[r for r in rows if r['kind'] in
            ('fixture_observations_active','observation_supply_stopped_services_continue')])
starts={k:[r['dds_source_trace']['before_realtime_ns']for r in rows]for k,rows in source_groups.items()}

# One explicitly permitted supplemental Gateway read: the first audit export
# deliberately omitted TF takes, and its whole-case statistics cannot be used
# as the normal-window distribution.
gateway=load(CASE/'gateway/network-gateway.json')
tf_groups=defaultdict(lambda:defaultdict(list));unmatched=[];identities=Counter()
for row in gateway['health_trace']['rows']:
    if row['stage']!='R_TF_take' or not inside(row['mono_ns']) or row.get('metadata') is None:continue
    first=row['tf_edges'][0]
    kind='both_wheel_TF' if first['frame_id']=='base_link' else first['frame_id']+'->'+first['child_frame_id']
    key=row['flow'],kind;md=row['metadata'];stamp=md['source_timestamp']
    i=bisect.bisect_right(starts[key],stamp)-1
    if i<0 or stamp>source_groups[key][i]['dds_source_trace']['after_realtime_ns']:
        unmatched.append(row);continue
    src=source_groups[key][i];identities[(key,src['dds_source_trace']['publication_ordinal'])]+=1
    values=tf_groups[key]
    values['sourceTS_to_receivedTS_system'].append((md['received_timestamp']-stamp)/1e6)
    values['receivedTS_to_take_system'].append((row['before_realtime_ns']-md['received_timestamp'])/1e6)
    values['sourceTS_to_take_system'].append((row['before_realtime_ns']-stamp)/1e6)
    values['source_publish_return_to_take_monotonic'].append((row['mono_ns']-src['after_monotonic_ns'])/1e6)

coordinator=load(CASE/'time-controller.json');phase=[];credit=[];latest=None
for r in coordinator['records']:
    if r[0]=='actual_clock':latest=r[3]
    if r[0]=='post_physics_ACK' and inside(r[1]):
        phase.append(dict(mono_ns=r[1],E=r[5],G=latest,success=r[3],completed_steps=r[8]))
    if r[0]=='physical_token' and inside(r[1]) and r[4]is not None and r[6]is not None:
        credit.append(dict(mono_ns=r[1],end_minus_anchor_actualACK_ns=r[4]+10_000_000-r[5]-r[6],lateness_ns=r[-1]))
result=dict(case=str(CASE),normal_start=start,normal_done=done,normal_wall_s=(hi-lo)/1e9,
    normal_client_sim_advance_s=done['sim']-start['sim'],normal_client_RTF=(done['sim']-start['sim'])/((hi-lo)/1e9),
    health=normal_health,masks=masks,source=source_report,
    TF=dict(cohort='actual R take entry inside the C normal phase; source publication may precede its boundary',
        unmatched_count=len(unmatched),duplicate_join_count=sum(v-1 for v in identities.values()),
        groups={str(k):{name:stats(values,'system_ms' if name.endswith('_system') else 'wall_ms')
            for name,values in metrics.items()}for k,metrics in tf_groups.items()}),
    phase_credit=dict(ACK_n=len(phase),all_ACK_success=all(r['success'] and r['completed_steps']==10 for r in phase),
        E_minus_latest_actual_G_ns=dict(Counter(str(r['E']-r['G'])for r in phase)),
        token_n=len(credit),end_minus_anchor_actualACK=stats([r['end_minus_anchor_actualACK_ns']/1e6 for r in credit],'sim_ms'),
        pacer_lateness=stats([r['lateness_ns']/1e6 for r in credit],'wall_ms')),
    boundaries=['Normal is the actual C marker interval, not the whole case or source prewarm interval.',
        'The first normal receipt/accept interval may start before C normal t0; this is explicitly marked.',
        'Health source ages use actual recorded R node clock at each intake entry, not native ACK or source clock.',
        'These are sampled intake ages, not a continuous supremum of every guard timer evaluation.',
        'Mask acceptance lies inside recorded before/after brackets; no exact mask receipt instant or Rsim was invented.',
        'Negative source ages are retained; the synthetic correction source uses latest scan + .2sim.',
        'Source and RMW timestamps are system time; receipt intervals use monotonic wall time.',
        'RMW received_timestamp is not independently proved earliest arrival or reader-ready time.',
        'No ROS/ns3/Gazebo run; original normal and later intentional-negative outcomes are kept separate.'])
with(OUT/'normal-window.json').open('x')as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(normal_wall_s=result['normal_wall_s'],normal_RTF=result['normal_client_RTF'],
    health={f:{'n':r['n'],'max_receipt_interval_ms':r['statistics']['receipt_interval_from_actual_previous']['max'],
        'max_held_odom_sim_ms':max(r['statistics'][f'held_{b}_odom_age']['max']for b in('tb1','tb2','tb3')),
        'max_held_correction_sim_ms':max(r['statistics'][f'held_{b}_correction_age']['max']for b in('tb1','tb2','tb3')),
        'max_new_odom_sim_ms':max(r['statistics'][f'incoming_{b}_odom_age']['max']for b in('tb1','tb2','tb3')),
        'max_new_correction_sim_ms':max(r['statistics'][f'incoming_{b}_correction_age']['max']for b in('tb1','tb2','tb3'))}
        for f,r in normal_health.items()},masks={f:{'n':r['n'],'max_lower_ms':r['interval_lower']['max'],'max_upper_ms':r['interval_upper']['max']}for f,r in masks.items()},
    TF_take_n=sum(next(iter(x.values()))['n']for x in result['TF']['groups'].values()),phase_credit=result['phase_credit']),indent=2))

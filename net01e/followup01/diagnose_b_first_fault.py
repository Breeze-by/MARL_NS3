"""Saved B first-fault chain, using actual wire/Hub IDs and trace only."""
import json
from pathlib import Path

B=Path(__file__).resolve().parent/'pace20-tail-b1-01'


def main():
    g=json.loads((B/'gateway/network-gateway.json').read_text())
    s=json.loads((B/'source/result.json').read_text())['inputs']
    peer=[json.loads(line) for line in (B/'peer/peer-keepout.jsonl').read_text().splitlines()]
    wire=[json.loads(line) for line in (B/'gateway/wire-records.jsonl').read_text().splitlines()]
    ingress=json.loads((B/'hub/hub-ingress.json').read_text())
    delivered=json.loads((B/'hub/hub-deliveries.json').read_text())
    faults={r:next((e for e in v['events'] if e['kind']=='latched_INVALID'),None) for r,v in g['guards'].items()}
    cutoff=min(int(e['monotonic']*1e9) for e in faults.values() if e)
    prefix=[];mismatches=[];binding={}
    for i,h in enumerate(ingress):
        if i>=len(wire):mismatches.append(dict(index=i,reason='No wire input'));continue
        w=wire[i]
        same=(all(w[k]==h[k] for k in ('sender','receiver','flow','source_stamp_ns')) and w['body_bytes']+8==h['bytes'])
        if same:
            prefix.append(h['native_message_id']);binding[h['native_message_id']]=w
        else:mismatches.append(dict(index=i,wire=w,hub=h))
    hi={r['native_message_id']:r for r in ingress};hd={r['message_id']:r for r in delivered}
    selected=[]
    for robot in (1,2,3):
        flow=robot*20+3
        def correction(row,key):return any(e['frame_id']=='map' and e['child_frame_id']=='odom' for e in row.get(key,[]))
        src=[r for r in s if r['flow']==flow and r['state']=='PUBLISHED' and r['before_monotonic_ns']<cutoff and correction(r,'original_tf_edges')][-1]
        cap=[r for r in g['topics']['R']['captured'] if r['flow']==flow and r['endpoint_capture_monotonic_ns']<cutoff and correction(r,'tf_edges')][-1]
        next_capture=min((r['endpoint_capture_monotonic_ns'] for r in g['topics']['R']['captured']
                          if r['flow']==flow and r['endpoint_capture_monotonic_ns']>cap['endpoint_capture_monotonic_ns']),default=2**63)
        candidates=[(mid,w) for mid,w in binding.items() if w['flow']==flow and w['cdr_sha256']==cap['cdr_sha256']
                    and cap['endpoint_capture_monotonic_ns']<=w['capture_monotonic_ns']<next_capture]
        selected.append(dict(robot=robot,latest_source_before_fault={k:src[k] for k in
            ('source_record_id','original_record_ns','source_publish_sim_ns','before_monotonic_ns','original_tf_edges')},
            latest_R_capture_before_fault=cap,
            actual_native_chain=[dict(native_id=mid,wire=w,hub_ingress=hi[mid],hub_complete_RX=hd.get(mid),
                C_topic_publish=[r for r in g['topics']['C']['delivered'] if r.get('message_id')==mid]) for mid,w in candidates]))
    target_health=[r for r in g['health_trace']['rows'] if r['stage'] in ('C_health_callback','R_health_intake') and r.get('sequence') in (23,24)]
    health_ids={r['native_message_id'] for r in target_health if 'native_message_id' in r}
    for mid,w in binding.items():
        if w['flow'] in (31,51,71) and w['capture_monotonic_ns']>=627531000000000:health_ids.add(mid)
    semantic_packets=[]
    for side in ('C','R'):
        for row in g['topics'][side]['delivered']:
            mid=row.get('message_id')
            if mid in binding:
                semantic_packets.append(dict(native_id=mid,flow=row['flow'],source_wire_hash=binding[mid]['cdr_sha256'],
                    destination_hash=row['cdr_sha256'],equal=binding[mid]['cdr_sha256']==row['cdr_sha256']))
    phase=json.loads((B/'gateway/active-phase-profile.json').read_text());inc=phase['increment']
    result=dict(first_faults=faults,wire_capture_inputs=len(wire),actual_Hub_ingress=len(ingress),
        actual_Hub_complete_RX=len(delivered),wire_Hub_FIFO_prefix=dict(matched=len(prefix),mismatches=mismatches),
        unmatched_Hub_ingress_ids=sorted(set(hi)-set(hd)),
        topic_packet_hash_matches=dict(n=len(semantic_packets),equal=sum(r['equal'] for r in semantic_packets),
            mismatches=[r for r in semantic_packets if not r['equal']]),
        latest_TF_chains=selected,health_last_two_sequences=target_health,
        actual_health_native_ids=[dict(native_id=mid,wire=binding.get(mid),hub_ingress=hi.get(mid),
            hub_complete_RX=hd.get(mid)) for mid in sorted(health_ids)],
        last_Peer={k:peer[-1][k] for k in ('sequence','generated_sim','ready','odom_stamps','correction_stamps','ages')},
        link=g['link'],active_CPU=dict(wall_ns=inc['wall_between_snapshot_brackets_ns'],
            thread_CPU_ns=inc['thread_cpu_between_snapshot_brackets_ns'],idle=inc['dispatch']['idle_wait'],
            CPU_profile=inc['cpu_profile']),
        boundaries=['FIFO match uses actual single-owner send order plus route/flow/source stamp/length, not only consumer-conditioned IDs.',
            'Hub complete RX fields derive actual native RX/reassembly output; raw native ledger not read by this script.',
            'Pending/undelivered at early stop is censored, not an inferred permanent loss ratio.',
            'Source actual first publication may be late; this case cannot be called equal offered cadence before startup is corrected.'])
    (B/'B_FIRST_FAULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('active_CPU','link','latest_TF_chains','actual_health_native_ids','health_last_two_sequences')},indent=2))


if __name__=='__main__':main()

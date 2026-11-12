"""One admitted offline case: reuse stage exporter, add full-source health/mask census."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from net01d.followup04.costs.export_costs import export_loaded, ident


def groups(rows,key):
    indexed=defaultdict(list)
    for row in rows:
        value=key(row)
        if value is not None:indexed[value].append(row)
    return indexed


def one(rows):return rows[0] if len(rows)==1 else None


def pick(row,keys):return {key:row[key] for key in keys if key in row}


def phase(ns,lo,hi,terminal=None):
    if ns is None or lo is None or hi is None:return 'UNMEASURED'
    if terminal is not None and ns>terminal:return 'POST_TERMINAL_RIGHT_CENSORED'
    if ns<lo:return 'PRE_WINDOW_CONTEXT'
    if ns>hi:return 'POST_WINDOW_RIGHT_CENSORED'
    return 'IN_AUTONOMY_WINDOW'


def census(gateway,direct,peer,raw,publications,window,output):
    lo=window.get('lo_monotonic_ns');hi=window.get('hi_monotonic_ns')
    states=groups(peer,lambda r:r['sequence'])
    pubs=groups([r for r in raw.get('rows',[]) if r['stage']=='Peer_health_publish'],lambda r:r['sequence'])
    source_keys=set(states)|set(pubs)
    start=window.get('original_start_sim');end=window.get('original_end_sim')
    main_source_keys={seq for seq,rows in states.items() if start is not None and end is not None
        and any(row.get('generated_sim') is not None and start<=row['generated_sim']<end for row in rows)}
    trace=gateway.get('health_trace',{}).get('rows',[])
    callbacks=groups([r for r in trace if r['stage']=='C_health_callback'],lambda r:(r['flow'],r['sequence']) if r.get('sequence') is not None else None)
    if direct is None:
        health=groups([r for r in trace if r['stage']=='R_health_intake'],lambda r:(r['flow'],r['sequence']) if r.get('sequence') is not None else None)
        masks=groups(gateway.get('bound_masks',[]),lambda r:(r['native']['flow']+1,r['binding']['bound_state']['sequence']))
    else:
        health=groups(direct['health'],lambda r:(20*r['robot']+11,r['sequence']))
        masks=groups(direct['masks'],lambda r:(20*r['robot']+11,r['binding']['bound_state']['sequence']))
    bindings=groups(publications,lambda r:(int(r['robot'][2:])*20+11,r['bound_state']['sequence']))
    captures=groups([r for t in gateway.get('topics',{}).values() for r in t['captured']],lambda r:(r['flow'],r['endpoint_capture_monotonic_ns']))
    endpoints=groups(gateway.get('hub_deliveries',[]),lambda r:(r['flow'],ident(r)))
    destinations=groups([r for t in gateway.get('topics',{}).values() for r in t['delivered']],lambda r:(r['flow'],ident(r)))
    terminals={}
    for robot,g in gateway['guards'].items():
        rows=[r for r in g['events'] if r['kind'] in ('latched_INVALID','control_permission_revoked')]
        terminals[int(robot)]=min((round(r['monotonic']*1e9) for r in rows if r.get('monotonic') is not None),default=None)
    known_terminal=min((value for value in terminals.values() if value is not None),default=None)
    keys={(flow,seq) for seq in source_keys for flow in (31,51,71)}|set(callbacks)|set(health)|set(bindings)|set(masks)
    counts=Counter();main_counts=Counter();boundary_counts=Counter();used_ids=set();aois=Counter();mask_counts=Counter()
    mask_outcomes=Counter();main_mask_outcomes=Counter()
    with (output/'source-health-outer.jsonl').open('x') as hs,(output/'source-mask-outer.jsonl').open('x') as ms:
        for flow,seq in sorted(keys):
            robot=(flow-11)//20;name=f'tb{robot}';terminal=known_terminal
            state=one(states[seq]);rawpub=one(pubs[seq]);cb=callbacks[(flow,seq)];intakes=health[(flow,seq)]
            source_ns=None if rawpub is None else rawpub.get('mono_ns')
            source_basis='actual_Peer_health_publish_begin'
            if source_ns is None and state is not None:
                value=state.get('delivery_timing',{}).get('health_publish_before_monotonic')
                source_ns=None if value is None else round(value*1e9);source_basis='producer_record_publish_bracket'
            source_phase=phase(source_ns,lo,hi,terminal)
            in_main=seq in main_source_keys
            generated_candidates=[r.get('generated_sim') for r in states[seq]]
            generation_scope=('MAIN_GENERATION_WINDOW' if in_main else 'UNMEASURED_GENERATION_SIM'
                if not generated_candidates or any(g is None for g in generated_candidates) or start is None or end is None
                else 'BEFORE_MAIN_CONTEXT' if max(generated_candidates)<start else 'AFTER_MAIN_CONTEXT')
            boundary_overlap=in_main and source_phase in ('PRE_WINDOW_CONTEXT','POST_WINDOW_RIGHT_CENSORED')
            cutoff=None if hi is None else min(hi,terminal) if terminal is not None else hi
            seen=[];identities=[];cc=[]
            for callback in cb:
                cc.extend(captures[(flow,callback['callback_entry_mono_ns'])])
            for row in intakes:
                entry=row.get('before_monotonic_ns') if direct is not None else row.get('mono_ns')
                now=row.get('R_sim_ns') if direct is not None else row.get('R_node_sim_before_ns')
                actual_state=row.get('state') if direct is not None else state
                generated=None if actual_state is None else actual_state.get('generated_sim')
                aoi=None if now is None or generated is None else now/1e6-generated*1000
                sample=dict(observation=pick(row,('before_monotonic_ns','after_monotonic_ns','mono_ns','guard_end_mono_ns','R_sim_ns','R_node_sim_before_ns','R_node_sim_after_ns','accepted','returned','fault','fault_before','fault_after','actual_receipt_mono_s','actual_receipt_monotonic_s')),
                    sampled_health_AoI_sim_ms=aoi,AoI_status='UNMEASURED' if aoi is None else 'SAMPLED_OBSERVED_R_CLOCK_MINUS_GENERATED_SIM',
                    clock_basis='A0_after_guard' if direct is not None else 'adapter_before_guard',exact_receipt_sim='UNMEASURED',
                    intake_phase=phase(entry,lo,hi,terminal),source_header_age_sim_ms={})
                if actual_state is not None and now is not None:
                    for kind in ('odom','correction'):
                        sample['source_header_age_sim_ms'][kind]={owner:('UNMEASURED' if actual_state.get(kind+'_stamps',{}).get(owner) is None else now/1e6-actual_state[kind+'_stamps'][owner]*1000) for owner in ('tb1','tb2','tb3')}
                else:sample['source_header_age_status']='UNMEASURED'
                if direct is None:
                    mid=row.get('native_message_id');key=(flow,mid)
                    sample['message_identity']=mid
                    sample['identity_backend']='actual_native_message_id' if gateway['mode'] in ('B','C') else 'A1_local_adapter_sequence_NOT_native'
                    if mid is not None:
                        used_ids.add(key)
                        identities.append(dict(message_id=mid,endpoint_candidates=endpoints[key],R_publication_candidates=destinations[key]))
                seen.append(sample)
                if sample['intake_phase']=='IN_AUTONOMY_WINDOW':aois[(name,sample['AoI_status'])]+=1
            in_cutoff=[r for r in seen if cutoff is not None and (r['observation'].get('before_monotonic_ns') if direct is not None else r['observation'].get('mono_ns')) is not None and (r['observation'].get('before_monotonic_ns') if direct is not None else r['observation'].get('mono_ns'))<=cutoff]
            ambiguous=any(len(value)>1 for value in (states[seq],pubs[seq],cb,intakes,cc))
            outcome=('POST_TERMINAL_RIGHT_CENSORED' if source_phase=='POST_TERMINAL_RIGHT_CENSORED' else
                'NON_MAIN_GENERATION_CONTEXT' if not in_main else
                'MAIN_GENERATION_CLOCK_BRACKET_BOUNDARY_OVERLAP' if boundary_overlap else
                'AMBIGUOUS_JOIN' if ambiguous else 'UNMEASURED_SOURCE_TIME_OR_WINDOW' if source_phase=='UNMEASURED' else
                'R_INTAKE_BY_CUTOFF' if in_cutoff else 'R_INTAKE_ONLY_AFTER_CUTOFF' if seen else
                'NOT_SEEN_AT_R_BY_CUTOFF_NOT_A_LOSS_CLAIM')
            record=dict(sequence=seq,robot=name,health_flow=flow,source_key=seq in source_keys,
                source_in_original_main_generation_window=in_main,source_generation_sim_candidates=generated_candidates,
                source_generation_scope=generation_scope,clock_bracket_boundary_overlap=boundary_overlap,
                source_phase=source_phase,source_publish_basis=source_basis,cutoff_monotonic_ns=cutoff,terminal_monotonic_ns=terminal,
                producer_state_candidates=[pick(r,('sequence','generated_sim','ready','odom_stamps','correction_stamps')) for r in states[seq]],
                source_publish_candidates=pubs[seq],C_callback_candidates=cb,C_capture_candidates=cc,
                C_adapter_status='NOT_APPLICABLE' if direct is not None else 'AMBIGUOUS' if len(cb)>1 or len(cc)>1 else 'OBSERVED' if cb else 'NOT_SEEN',
                R_intake_candidates=seen,message_identity_candidates=identities,
                native_ID_status='NOT_APPLICABLE' if direct is not None or gateway['mode']=='A' else 'OBSERVED_R_LINK' if identities else 'UNMEASURED_NO_SOURCE_TO_NATIVE_ID_RECORD',
                ambiguous=ambiguous,outcome=outcome)
            hs.write(json.dumps(record)+'\n');counts[(name,outcome)]+=1
            if in_main:main_counts[(name,outcome)]+=1
            if boundary_overlap:boundary_counts[name]+=1
            source_masks=bindings[(flow,seq)];received_masks=masks[(flow,seq)]
            mask_source=one(source_masks)
            mask_source_ns=None if mask_source is None else mask_source.get('captured_monotonic_ns')
            mask_phase=phase(mask_source_ns,lo,hi,terminal)
            mr=[]
            for m in received_masks:
                mid=None if direct is not None else ident(m['native'])
                if mid is not None:used_ids.add((flow-1,mid))
                mr.append(dict(record=m,native_endpoint_candidates=[] if mid is None else endpoints[(flow-1,mid)],
                    intake_phase=phase(m.get('validation_after_monotonic_ns') if direct is not None else m.get('accept_bound_before_monotonic_ns'),lo,hi,terminal),
                    sampled_mask_receipt_AoI='UNMEASURED_NAV2_CONSUMER_TIME; adapter R clock absent, A0 R_sim is validator-only',
                    scope='Mask validator observation, not Nav2 receipt; mono accept bracket retained'))
            mask_times=[m.get('validation_after_monotonic_ns') if direct is not None else m.get('accept_bound_before_monotonic_ns') for m in received_masks]
            mask_seen=any(value is not None and cutoff is not None and value<=cutoff for value in mask_times)
            mask_outcome=('POST_TERMINAL_RIGHT_CENSORED' if mask_phase=='POST_TERMINAL_RIGHT_CENSORED' else
                'NON_MAIN_GENERATION_CONTEXT' if not in_main else
                'MAIN_GENERATION_CLOCK_BRACKET_BOUNDARY_OVERLAP' if mask_phase in ('PRE_WINDOW_CONTEXT','POST_WINDOW_RIGHT_CENSORED') else
                'AMBIGUOUS_JOIN' if len(source_masks)>1 or len(received_masks)>1 else
                'R_MASK_VALIDATOR_BY_CUTOFF' if mask_seen else 'R_MASK_ONLY_AFTER_CUTOFF' if received_masks else
                'NOT_SEEN_AT_R_BY_CUTOFF_NOT_A_LOSS_CLAIM')
            mask_outcomes[(name,mask_outcome)]+=1
            if in_main:main_mask_outcomes[(name,mask_outcome)]+=1
            ms.write(json.dumps(dict(sequence=seq,robot=name,mask_flow=flow-1,source_health_key=seq in source_keys,
                source_in_original_main_generation_window=in_main,source_generation_scope=generation_scope,
                source_phase=mask_phase,source_binding_candidates=source_masks,R_accept_candidates=mr,
                source_time_basis='Bound envelope capture before original publish_bound; not original mask publish return',
                terminal_monotonic_ns=terminal,cutoff_monotonic_ns=cutoff,
                postterminal_source_right_censored=mask_phase=='POST_TERMINAL_RIGHT_CENSORED',
                main_generation_clock_bracket_overlap=in_main and mask_phase in ('PRE_WINDOW_CONTEXT','POST_WINDOW_RIGHT_CENSORED'),
                C_callback_queue_status='UNMEASURED_NOT_TRACED',
                source_binding_count=len(source_masks),R_accept_count=len(received_masks),outcome=mask_outcome,
                ambiguous=len(source_masks)>1 or len(received_masks)>1,
                not_seen_at_R_by_cutoff_is_not_loss=True))+'\n')
            mask_counts[(name,'source_bindings')]+=len(source_masks);mask_counts[(name,'R_accept_records')]+=len(received_masks)
    orphan=0
    with (output/'unassigned-native-control.jsonl').open('x') as stream:
        for row in gateway.get('hub_deliveries',[]):
            if row['flow'] in (30,31,50,51,70,71) and (row['flow'],ident(row)) not in used_ids:
                stream.write(json.dumps(dict(native=row,source_sequence='UNMEASURED',scope='Outer-join residual, not dropped or matched by time proximity'))+'\n');orphan+=1
    return dict(original_main_generation_sim_interval=dict(start_inclusive=start,end_exclusive=end),
        source_sequence_keys_whole_recording=len(source_keys),
        main_generated_source_sequence_keys=len(main_source_keys),main_source_sequence_x3flow_denominator=len(main_source_keys)*3,
        mother_scope='Original source generated_sim in main[start,end), independent of successful consumers or R clock bracket. Unknown/ambiguous generation and clock-bracket overlap retained separately.',
        actual_source_publish_attempt_rows=sum(len(v) for v in pubs.values()),
        main_source_publication_attempts=sum(len(pubs[seq]) for seq in main_source_keys),
        main_source_binding_records=sum(len(rows) for (flow,seq),rows in bindings.items() if seq in main_source_keys),
        unkeyed_health_trace_records=sum(r.get('sequence') is None for r in trace if r['stage'] in ('C_health_callback','R_health_intake')),
        known_terminal_monotonic_ns=known_terminal,terminal_basis='First recorded Guard INVALID/revocation across robots; exact earlier process-death mono UNMEASURED unless in original records.',
        source_publication_attempt_x3=sum(len(v) for v in pubs.values())*3,
        all_outer_keys=len(keys),orphan_later_keys=len(keys)-len(source_keys)*3,
        main_source_health_outcomes={robot:{outcome:value for (r,outcome),value in main_counts.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        main_source_clock_bracket_boundary_overlap=dict(boundary_counts),
        health_outcomes={robot:{outcome:value for (r,outcome),value in counts.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        sampled_AoI_record_status={robot:{kind:value for (r,kind),value in aois.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        mask_counts={robot:{kind:value for (r,kind),value in mask_counts.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        main_source_mask_outcomes={robot:{outcome:value for (r,outcome),value in main_mask_outcomes.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        mask_outcomes={robot:{outcome:value for (r,outcome),value in mask_outcomes.items() if r==robot} for robot in ('tb1','tb2','tb3')},
        unassigned_native_control_records=orphan,
        limitations=['All source keys retained, duplicate candidate lists not deduplicated; not a delivery/loss probability.',
            'Missing R evidence is cutoff non-observation, not proven radio loss. Unreceived source nativeID and mask Ccallback/queue may be UNMEASURED.',
            'Sampled health AoI uses observed R clock minus generated_sim; source-header ages remain separate. Not exact receipt_sim or continuous supremum.',
            'Mother is source generated_sim in main[start,end), never consumer/clock-bracket-filtered. Boundary overlap and all post-terminal source rows are explicit, not network loss.',
            'Post-terminal and post-window rows are right-censored/context; original FAIL/partial window/actual exits unchanged.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True);parser.add_argument('--arm',choices=('A0','A1','B','C'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--exit-proof',type=Path,required=True)
    args=parser.parse_args();case=args.case.resolve();args.output.mkdir(parents=True,exist_ok=False)
    reads=Counter();metadata={};manifest=dict(status='STARTED',case=str(case),arm=args.arm,ledger_reads=0,PCAP_reads=0,bag_reads=0)
    def read(path,lines=False,optional=False):
        path=Path(path);path=path if path.is_absolute() else case/path;key=str(path.resolve())
        if optional and not path.exists():metadata[key]=dict(status='MISSING_UNMEASURED');return [] if lines else None
        if reads[key]:raise RuntimeError('Single-load contract: duplicate open '+key)
        reads[key]+=1;t=time.monotonic()
        with path.open() as stream:value=[json.loads(line) for line in stream] if lines else json.load(stream)
        metadata[key]=dict(bytes=path.stat().st_size,read_decode_wall_s=time.monotonic()-t);return value
    try:
        proof=read(args.exit_proof.resolve())
        gateway=read('network-gateway.json');direct=read('a0-direct-safety.json') if args.arm=='A0' else None
        result=read('result.json');timing=read('observer_timing.json');events=read('events.jsonl',lines=True)
        peer=read('peer-keepout.jsonl',lines=True);raw=read('health-trace.json')
        publications=read('bound-mask-publications.jsonl',lines=True)
        bound=next((row for row in reversed(events) if row['kind']=='smoke_bound'),None)
        stage=export_loaded(gateway,direct,result,timing,bound,peer,raw,publications)
        actual_exits={name:read(case/name,optional=True) for name in ('network-controller-exit.json','network-gateway-exit.json')}
        actual_exits['host']=read(case.with_name(case.name+'.host-exit.json'),optional=True)
        actual_exits['network_integrity']=read(case.with_name(case.name+'.network-integrity.json'),optional=True)
        full=census(gateway,direct,peer,raw,publications,stage['window'],args.output)
        targets=stage.pop('native_targets')
        with (args.output/'consumed-stage-native-targets.jsonl').open('x') as stream:
            for row in targets:stream.write(json.dumps(row)+'\n')
        stage.update(actual_exits=actual_exits,original_exit_proof=proof,
            sampled_health_AoI={f'tb{r}':dict(reused_stage=stage['stages'].get(f'tb{r}/health/source_generated_age_at_observed_R_clock'),
                scope='Sampled observed R clock minus generated_sim only; not source-header age, exact receipt_sim or continuous freshness') for r in (1,2,3)})
        with (args.output/'stage-summary.json').open('x') as stream:json.dump(stage,stream,indent=2);stream.write('\n')
        manifest.update(status='EXPORTED_ONLY_NO_CASE_VERDICT_CHANGE',window=stage['window'],full_source_census=full,
            read_counts=dict(reads),parse_metadata=metadata,
            scope='One case only, existing export_loaded and full-source outer ledger; consumed native targets are not the source/loss denominator. No hash/runtime modules or native ledger/PCAP/bag read.')
    except BaseException as error:manifest.update(status='FAIL_FIRST_ERROR_PRESERVED',error=repr(error));raise
    finally:(args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

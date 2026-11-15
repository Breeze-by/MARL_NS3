#!/usr/bin/env python3
"""Small post-exit gates and one declared analysis pass for navigation-clearance six-run task."""
import argparse
import ast
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import run_batch

REPO = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def lines(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def select(plan_path, slot_id, repo=REPO):
    plan = read(plan_path)
    slot, = [row for row in plan['slots'] if row['id'] == slot_id]
    ready = read(repo / slot['ready_relative_repo'])
    return plan, slot, ready


def preflight(plan, slot, ready, repo=REPO):
    case = repo / slot['case_relative_repo']
    if not (repo/slot['socket_relative_repo']).parent.is_dir():
        raise RuntimeError('Required task-owned native socket parent is missing')
    paths = [case, case.with_name(case.name+'.host-exit.json'),
             repo/slot['network_relative_repo'], repo/slot['socket_relative_repo'],
             case.with_name(case.name+'.time-control'), Path(slot['native_evidence_ram'])]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise RuntimeError('Single-use case/socket/RAM output already exists')
    for path in [repo/slot['socket_relative_repo'], case.with_name(case.name+'.time-control')/'ack.sock']:
        if len(str(path).encode()) > 107:
            raise RuntimeError('AF_UNIX path exceeds original107-byte bound')
    if ready['case_relative_phase'] != slot['case_relative_repo'] or ready['network']['session_id'] != slot['session_id']:
        raise RuntimeError('Manifest/READY case or session mismatch')
    ram = ready['ram_storage_contract']
    v = os.statvfs('/dev/shm')
    memory = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines()
                      if row.startswith('MemAvailable:'))) * 1024
    if v.f_bavail*v.f_frsize < ram['required_free_tmpfs_bytes'] or memory < ram['required_MemAvailable_bytes']:
        raise RuntimeError('Original tmpfs/MemAvailable admission gate blocked')
    active = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc/'cmdline').read_bytes().decode(errors='replace').split('\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        if any(Path(word).name in ('gzserver', 'gzclient', 'net01-payload-tcp', 'packet_hub.py',
                                  'production_host.py', 'boot_network.py') for word in argv if word):
            active.append(int(proc.name))
    if active:
        raise RuntimeError('Existing simulation/native owner blocks exclusive start: '+str(active))
    return dict(unused=True, exclusive=True, tmpfs_free_bytes=v.f_bavail*v.f_frsize,
                MemAvailable_bytes=memory,
                note='Original production host still performs actual source/native identity and entry gates')


def window(events):
    starts = [row for row in events if row['kind']=='exploration_command']
    if not starts:
        return None
    start, = starts
    stop = next(row for row in events if row['kind'] in ('smoke_bound','error')
                and row.get('sim') is not None and row['sim']>=start['sim'])
    return dict(start=start['sim'], end=stop['sim'], duration=stop['sim']-start['sim'])


def pacing_prefix(case, policy, repo=REPO):
    """Exact original event/token calculations, without feedback/bag code.

    The old function's zero-runner-exit admission is replaced by verify()'s
    actual safety/owner/copy proof, permitting a retained original protection FAIL.
    Numeric policy, event selection, stats and token selection are unchanged.
    """
    source = repo/'local-runs/causal-fix-20261113/integration/analyze_pacing_feedback.py'
    tree = ast.parse(source.read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('json_lines','stats')]
    original = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name=='analyze')
    first = next(i for i,node in enumerate(original.body) if isinstance(node, ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='run' for t in node.targets))
    last = next(i for i,node in enumerate(original.body) if isinstance(node, ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='pacing' for t in node.targets))
    original.body = original.body[first:last+1]+[ast.Return(ast.Tuple(elts=[
        ast.Name(id='pacing',ctx=ast.Load()),ast.Name(id='coordinator',ctx=ast.Load())],ctx=ast.Load()))]
    selected.append(original)
    namespace = dict(json=json)
    import statistics
    namespace['statistics'] = statistics
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(source),'exec'),namespace)
    return namespace['analyze'](case,dict(predeclared_qualification=policy),None)


def startup_proof(events, stdout, coordinator, ready):
    """Actual spawn exits/factory reply precede the first original RUN token."""
    errors=[];session=ready['network']['session_id'];profile=ready['network']['execution_profile']
    exits=[r for r in events if r['kind']=='original_spawn_entity_exit']
    starts=[r for r in events if r['kind']=='factory_fence_process_started']
    ends=[r for r in events if r['kind']=='factory_fence_process_exited']
    sent=[r for r in events if r['kind']=='startup_spawn_ready_sent']
    records=coordinator['records'];accepted=[(i,r) for i,r in enumerate(records) if r[0]=='actual_startup_spawn_ready']
    if (len(exits)!=3 or {r['robot'] for r in exits}!={'tb1','tb2','tb3'}
            or len({r['pid'] for r in exits})!=3
            or any(type(r['pid']) is not int or r['pid']<=0 or r['returncode']!=0
                   or r['duplicate'] or r['session_id']!=session or r['execution_profile']!=profile for r in exits)):
        errors.append('not_three_unique_same_session_profile_actual_exit0')
    if len(starts)!=1 or len(ends)!=1 or len(sent)!=1 or len(accepted)!=1:
        errors.append('missing_or_duplicate_factory_fence_or_ready')
    names=re.findall(r'^name: "([^"\n]+)"$',stdout,re.MULTILINE)
    if names!=['tb3']:errors.append('CLI_stdout_not_unique_top_level_Model_tb3')
    if errors:return dict(status='FAIL',pass_=False,errors=errors)
    start=starts[0];end=ends[0];sent=sent[0];payload=sent['payload']
    fence={k:v for k,v in end.items() if k not in ('kind','passed')}
    world=fence['world_name'];command=['gz','model','-w',world,'-m','tb3','-i']
    if (not end['passed'] or not world or type(fence['pid']) is not int or fence['pid']<=0
            or fence['pid'] in {r['pid'] for r in exits} or fence['returncode']!=0
            or fence['response_model_name']!='tb3' or fence['request']!='entity_info'
            or fence['model_name']!='tb3' or fence['command']!=command
            or start['pid']!=fence['pid'] or start['command']!=command
            or start['world_name']!=world or start['model_name']!='tb3'):
        errors.append('factory_exit_PID_world_command_or_response_mismatch')
    if not (max(r['monotonic_ns'] for r in exits)<=fence['requested_monotonic_ns']
            <=fence['started_monotonic_ns']<=fence['exited_monotonic_ns']
            <=payload['monotonic_ns']<=sent['monotonic_ns']):
        errors.append('spawn_factory_ready_order_invalid')
    spawns=[dict(robot=r['robot'],pid=r['pid'],returncode=r['returncode'],
                 exit_monotonic_ns=r['monotonic_ns'],exit_realtime_ns=r['realtime_ns'])
            for r in sorted(exits,key=lambda r:r['robot'])]
    if (payload['kind']!='startup_spawn_ready' or payload['session_id']!=session
            or payload['execution_profile']!=profile or payload['factory_fence']!=fence
            or payload['spawns']!=spawns or sent['business_payload'] is not False
            or sent['control_socket']!='/mnt/'+ready['case_relative_phase']+'.time-control/ack.sock'):
        errors.append('launch_ready_payload_session_profile_or_facts_mismatch')
    index,row=accepted[0];before,after=row[7],row[8]
    if row[3]!=payload or row[5] is not True or row[6]!='all_spawn_exit0_and_factory_cycle_fence_admitted':
        errors.append('coordinator_ready_not_unique_matching_acceptance')
    fields=('physical_ns','iterations','clock_ns','native_ns','next_wall_ns','inflight')
    if not all(k in before and k in after and before[k]==after[k] for k in fields):
        errors.append('startup_admin_changed_physical_clock_native_or_deadline')
    if (any(before[k] is not None for k in ('physical_ns','iterations','next_wall_ns'))
            or before['native_ns']!=0 or before['clock_ns'] not in (None,0) or before['inflight'] is not False):
        errors.append('startup_ready_after_progress_or_inflight')
    if row[4]<payload['monotonic_ns']:errors.append('coordinator_received_before_ready_creation')
    tokens=[(i,r) for i,r in enumerate(records) if r[0]=='physical_token']
    acknowledgments=[(i,r) for i,r in enumerate(records) if r[0]=='post_physics_ACK']
    if not tokens or not acknowledgments:
        errors.append('first_actual_RUN_or_physics_ACK_missing')
    else:
        token_index,token=tokens[0];ack_index,ack=acknowledgments[0]
        if not (index<token_index<ack_index and token[3]=='RUN' and token[4] is None
                and token[5]==0 and token[7]>=row[1]):
            errors.append('physical_token_before_ready_or_first_deadline_invalid')
        if not (ack[3] is True and ack[4:9]==[0,10_000_000,0,10,10]):
            errors.append('first_actual_physics_ACK_not_0_to_10ms_10iterations')
    return dict(status='PASS' if not errors else 'FAIL',pass_=not errors,errors=errors,
        actor_exits=spawns,factory_fence=fence,stdout_top_level_model_names=names,
        administrative_before=before,administrative_after=after,
        first_physical_token=None if not tokens else tokens[0][1],
        first_physical_ACK=None if not acknowledgments else acknowledgments[0][1],
        scope='Initialization ordering/factory-cycle evidence only; not all async sensor completion or SIGSEGV cause/repair. CLI process times are brackets, not exact native request/response times.')


def barrier_proof(gate, coordinator, ready, actual_window, full):
    """Match existing gate/administrative tuples; no business or native ledger."""
    profile=ready['network']['execution_profile'];session=ready['network']['session_id']
    contract=ready['startup_contract'];first=contract['first_decision_ns']
    period=contract['decision_period_ns'];end=contract['decision_permission_end_ns']
    records=coordinator['records'];errors=[];matched=[]
    incoming=[(i,r) for i,r in enumerate(records) if r[0]=='actual_HQ_attempt_enter_ACK']
    pending=[(i,r) for i,r in enumerate(records) if r[0]=='pending_HQ_attempt_enter_after_actual_physics_ACK']
    attempts=[] if gate is None else [r for r in gate['events'] if r['kind']=='decision_attempt']
    final=coordinator['final']['attempt_entry_barrier']
    if (final['session_id'],final['execution_profile'],final['period_ns'],final['end_ns'])!=(
            session,profile,period,end):errors.append('final_barrier_identity_mismatch')
    if gate is not None and (gate['profile']!=profile or gate['contract']!=contract):
        errors.append('gate_profile_or_contract_mismatch')
    if actual_window is None:
        if attempts or incoming or pending or final['next_slot_ns']!=first:
            errors.append('attempt_ACK_without_autonomy')
        return dict(status='N/A_NO_AUTONOMY',pass_=not errors,errors=errors,matched=[])
    stop_ns=round(actual_window['end']*1e9)
    expected=list(range(first,end,period)) if full else list(range(first,min(stop_ns,end),period))
    slots=[r['planned_sim_ns'] for r in attempts]
    if len(slots)!=len(set(slots)) or slots!=sorted(slots):errors.append('duplicate_or_unordered_gate_slot')
    if (full and slots!=expected) or (not full and not set(expected)<=set(slots)):
        errors.append('missing_observed_window_attempt')
    if any(s<first or s>=end or s>stop_ns or (s-first)%period for s in slots):
        errors.append('gate_slot_outside_actual_window')
    if any(r[3].get('planned_sim_ns') not in slots for _,r in incoming+pending):
        errors.append('unexpected_future_or_unmatched_ACK')
    frozen=('physical_ns','clock_ns','native_ns','next_wall_ns','inflight')
    def preserved(before,after):
        return all(k in before and k in after and before[k]==after[k] for k in frozen)
    for attempt in attempts:
        slot=attempt['planned_sim_ns'];ack=attempt.get('attempt_enter_ACK')
        if (attempt.get('actual_sim_ns')!=slot or attempt.get('attempted') is not True
                or not isinstance(ack,dict) or 'attempt_enter_ACK_sent_monotonic_ns' not in attempt):
            errors.append(f'{slot}:missing_or_inexact_gate_ACK');continue
        if (ack.get('kind'),ack.get('session_id'),ack.get('execution_profile'),ack.get('planned_sim_ns'),ack.get('actual_sim_ns'))!=(
                'hq_attempt_enter',session,profile,slot,slot):
            errors.append(f'{slot}:gate_ACK_identity_mismatch');continue
        if attempt['attempt_enter_ACK_sent_monotonic_ns']<ack['monotonic_ns']:
            errors.append(f'{slot}:ACK_sent_time_precedes_ACK_creation')
        arrived=[(i,r) for i,r in incoming if r[3].get('planned_sim_ns')==slot]
        redeemed=[(i,r) for i,r in pending if r[3].get('planned_sim_ns')==slot]
        if len(arrived)!=1 or arrived[0][1][3]!=ack:
            errors.append(f'{slot}:missing_duplicate_or_mismatched_coordinator_ACK');continue
        index,row=arrived[0];before,after=row[7],row[8]
        if row[4]<ack['monotonic_ns'] or not preserved(before,after):
            errors.append(f'{slot}:administrative_ACK_mutated_progress_or_deadline')
        physical=[(i,r) for i,r in enumerate(records) if r[0]=='post_physics_ACK' and r[5]==slot]
        if len(physical)!=1:
            errors.append(f'{slot}:missing_or_duplicate_actual_physics_ACK');continue
        physical_index,physical_row=physical[0]
        if not (physical_row[3] is True and physical_row[4]==slot-10_000_000
                and physical_row[7]-physical_row[6]==10 and physical_row[8]==10):
            errors.append(f'{slot}:invalid_actual_physics_ACK')
        release_index=index;release_time=row[1]
        if row[5] is True and row[6]=='current_boundary_released':
            if redeemed or physical_index>=index or before['physical_ns']!=slot or before['inflight'] is not False:
                errors.append(f'{slot}:invalid_direct_release')
            if (before['next_slot_ns'],after['next_slot_ns'])!=(slot,slot+period):
                errors.append(f'{slot}:direct_release_crossed_slot')
        elif row[5] is False and row[6]=='pending_actual_physics_ACK':
            if (before['physical_ns']!=slot-10_000_000 or before['inflight'] is not True
                    or before['next_slot_ns']!=slot or after['next_slot_ns']!=slot or len(redeemed)!=1):
                errors.append(f'{slot}:invalid_pending_admission');continue
            release_index,release=redeemed[0];b,a=release[6],release[7];release_time=release[1]
            if (release[3]!=ack or release[4] is not True or release[5]!='current_boundary_released'
                    or not index<physical_index<release_index or not preserved(b,a)
                    or b['physical_ns']!=slot or b['inflight'] is not False
                    or (b['next_slot_ns'],a['next_slot_ns'])!=(slot,slot+period)):
                errors.append(f'{slot}:pending_not_redeemed_by_real_physics_ACK')
        else:
            errors.append(f'{slot}:coordinator_ACK_not_released');continue
        if any(i<release_index for i,r in enumerate(records)
               if r[0]=='physical_token' and r[3]=='RUN' and r[4]==slot):
            errors.append(f'{slot}:physical_crossed_boundary_before_release')
        matched.append(dict(planned_sim_ns=slot,actual_sim_ns=attempt['actual_sim_ns'],
            ACK_sent_monotonic_ns=attempt['attempt_enter_ACK_sent_monotonic_ns'],
            coordinator_received_monotonic_ns=row[4],released_monotonic_ns=release_time,
            pending=row[5] is False,physical_ACK_record_index=physical_index))
    if (final['session_id'],final['execution_profile'],final['period_ns'],final['end_ns'],final['next_slot_ns'])!=(
            session,profile,period,end,first+len(attempts)*period):errors.append('final_barrier_identity_or_slot_mismatch')
    return dict(status='PASS' if not errors else 'FAIL',pass_=not errors,errors=errors,
                required_attempts=len(expected),observed_attempts=len(attempts),matched=matched,
                scope='Actual entry ACK release only; original clock/pacing/2s/stop gates remain independent. No future ACK required after actual partial stop.')


def freshness_application_proof(ready, slot, applications, known_pids, role_pids, controller_not_started):
    """Actual four process records; configuration alone never proves application."""
    expected={'Gateway':('Gateway_A0_R92' if slot['physical_path']=='A0' else 'Gateway_C91_R92'),
              'BoundPeer':'BoundPeer','Observer':'NetworkObserver_R92','HQ':'HQ'}
    errors=[];actual={};policy=ready['source_freshness'];pids=[]
    receipt_policy=ready['receipt_freshness']
    if (receipt_policy['id']!='ros-delay-finite-sim-receipt-v1'
            or any(receipt_policy.get(name)!=value for name,value in {
                'health_max_age_sim_s':.6,'bound_mask_max_age_sim_s':.6,
                'observer_heartbeat_max_age_sim_s':.6,'projected_odom_max_age_sim_s':.5}.items())):
        errors.append('receipt_policy_does_not_match_root_locked_v3_contract')
    for role,name in expected.items():
        records=applications.get(role,[])
        if role=='HQ' and controller_not_started:
            actual[role]=dict(status='N/A_HQ_NOT_STARTED',records=records)
            errors.append('HQ_not_started_no_autonomous_qualification')
            continue
        if len(records)!=1:
            errors.append(role+':missing_or_duplicate_actual_application');continue
        applied=records[0];actual[role]=applied;pid=applied['pid'];pids.append(pid)
        if (applied['owner']!=name or type(pid) is not int or pid<=0 or pid not in known_pids
                or applied['execution_profile']!=ready['network']['execution_profile']
                or applied['policy']!=policy or applied['state_fresh_uses_peer_module_globals'] is not True
                or any(applied['applied'].get(module)!={'ODOM_MAX_AGE':.7,'CORRECTION_MAX_AGE':.85}
                       for module in ('peer_keepout','business_peer'))):
            errors.append(role+':actual_PID_profile_policy_globals_or_alias_mismatch')
        if role in role_pids and pid not in role_pids[role]:errors.append(role+':PID_does_not_match_original_owned_role')
        receipt=applied.get('receipt_freshness_applied',{})
        if (receipt.get('policy')!=receipt_policy
                or receipt.get('module_projected_odom_receipt_s')!={'peer_keepout':.5,'business_peer':.5}
                or receipt.get('producer_function_copied_binding')!=.5):
            errors.append(role+':actual_receipt_policy_module_or_copied_function_binding_mismatch')
        limits=receipt.get('applicable_instance_limits')
        expected_limits=({str(robot):dict(health_receipt_limit_sim_s=.6,mask_receipt_limit_sim_s=.6,
                health_receipt_limit_ns=600_000_000,mask_receipt_limit_ns=600_000_000,
                integer_ros_receipt=True) for robot in (1,2,3)} if role=='Gateway' else
            dict(observer_heartbeat_limit_sim_s=.6,observer_heartbeat_limit_ns=600_000_000,
                integer_ros_receipt=True) if role=='Observer' else {})
        if limits!=expected_limits:
            errors.append(role+':actual_instance_receipt_limits_or_integer_clock_mismatch')
    if len(pids)!=len(set(pids)):errors.append('source_freshness_owners_not_distinct_processes')
    return dict(pass_=not errors,errors=errors,actual=actual,
        qualification='All four unique actual owners, actual three Gateway guards/Observer integer-ns limits, both module globals and producer copied binding required; no config-only or preautonomy auto-continue',
        actual_record_scope='Gateway original records; BoundPeer original saved marker; Observer original events; HQ original allocation journal')


def navigation_application_proof(ready, applications, case):
    """Validate four actual owner bindings and the generated three-robot YAMLs."""
    import copy
    import yaml
    contract=ready['network']['navigation_clearance'];errors=[];actual={}
    expected=dict(revision='inflation040-peer052-v1',inflation_radius_m=.4,peer_radius_m=.52)
    if contract!=expected:errors.append('navigation_contract_mismatch')
    for role in ('Gateway','BoundPeer','Observer','HQ'):
        rows=applications.get(role,[])
        if len(rows)!=1:
            errors.append(role+':missing_unique_application');continue
        outer=rows[0];nav=outer.get('navigation_clearance_applied',{});actual[role]=nav
        if (nav.get('revision')!=contract['revision'] or nav.get('contract')!=contract
                or nav.get('owner')!=outer['owner'] or nav.get('pid')!=outer['pid']
                or nav.get('actual_module_radius_m')!={'peer_keepout':.52,'business_peer':.52}
                or nav.get('producer_state_radius_binding_m')!=.52
                or nav.get('target_allowed_uses_peer_globals') is not True
                or nav.get('route_blocked_uses_peer_globals') is not True
                or nav.get('resolution_m')!=.05):
            errors.append(role+':actual_radius_binding_or_owner_mismatch')
    launch=read(case/'navigation-clearance-revision.json')
    if (launch['revision']!=contract['revision'] or launch['contract']!=contract
            or launch['applied_before_actions'] is not True
            or launch['common_execution_revision_unchanged']!='nav2-simclock-common-v1'
            or [r['robot'] for r in launch['changes']]!=['tb1','tb2','tb3']):
        errors.append('launch_revision_or_three_robot_scope_mismatch')
    for entry in launch['changes']:
        robot=entry['robot'];path=case/f'peer_nav2_{robot}.yaml'
        before=case/f'peer_nav2_{robot}.before-clearance-tuning.yaml'
        if Path(entry['effective_params']).name!=path.name or Path(entry['before_params']).name!=before.name:
            errors.append(robot+':effective_or_before_path_mismatch')
        original=yaml.safe_load(before.read_text());modified=yaml.safe_load(path.read_text());expected_yaml=copy.deepcopy(original)
        expected_changes=[]
        for layer in ('global_costmap','local_costmap'):
            params=expected_yaml[layer][layer]['ros__parameters']
            if params['robot_radius']!=.25 or params['inflation_layer']['cost_scaling_factor']!=3.0 or params['inflation_layer']['inflation_radius']!=.55:
                errors.append(robot+':predecessor_radius_or_scaling_mismatch')
            params['inflation_layer']['inflation_radius']=.4
            expected_changes.append(dict(parameter=f'{layer}.{layer}.ros__parameters.inflation_layer.inflation_radius',previous=.55,value=.4,robot_radius_m=.25,cost_scaling_factor=3.0))
        if modified!=expected_yaml or entry['changes']!=expected_changes:
            errors.append(robot+':generated_YAML_not_exact_two_inflation_changes')
    return dict(pass_=not errors,errors=errors,actual=actual,launch=launch,
        scope='Actual four unique freshness-owned process records plus original generated YAML before/after; config alone does not qualify')


def verify(plan, slot, ready, output, repo=REPO):
    case = repo/slot['case_relative_repo']; netdir=repo/slot['network_relative_repo']
    run=read(case/'result.json'); host=read(case.with_name(case.name+'.host-exit.json'))
    hub=read(netdir/'result.json'); integrity=read(case.with_name(case.name+'.network-integrity.json'))
    events=lines(case/'events.jsonl'); actual_window=window(events)
    cleanup=host['cli_daemon_cleanup']; controlled=host['controlled_time']
    copied=hub['native_evidence_storage']; ownership=run['final_request_ownership']
    saved=read(case/'network-gateway-saved.json')
    owned_rows=lines(case/'owned_processes.jsonl')
    controller_pids=[row['pid'] for row in owned_rows if row['role']=='controller']
    controller_exit=host['controller_exit']
    controller_not_started=(controller_exit['started'] is False and not controller_pids
        and actual_window is None and not any(r['kind']=='fixed_controller_spawn' for r in events))
    controller_ended=(controller_exit['started'] is True and controller_exit['returncode'] is not None
        and controller_exit['pid'] in controller_pids)
    recorded={row['pid'] for row in owned_rows}
    recorded.update([host['native_load']['pid'],host['native_load']['hub_pid']])
    recorded.update(controlled['actual_bwrap_child_pids'].values())
    owners=(cleanup['all_recorded_pids_gone'] is True and cleanup['cleanup_pass'] is True
        and cleanup['target_process_exited'] is True and controlled['remaining_owned_groups']==[]
        and recorded<=set(cleanup['original_recorded_pids'])
        and (controller_not_started or controller_ended) and host['hub_exit'] is not None
        and host['runner_exit'] is not None and hub['native_exit'] is not None)
    stop=(run['observed_stop'] is True and run['lifecycle_pause_healthy'] is True
          and ownership['authority_stopped'] is True)
    closed=(ownership['closed'] is True and ownership['unresolved_requests']==[]
            and all(not values for values in ownership['unterminated_UUIDs'].values())
            and ownership['record_errors']==[])
    copy_ok=(copied['complete'] is True and copied['source']==slot['native_evidence_ram']
        and Path(copied['destination'])==(netdir/'native').resolve()
        and copied['source_bytes']==copied['copied_bytes']
        and copied['source_files']==copied['copied_files']
        and hub['native_exit']==0 and copied['native_exit']==0
        and copied['source_bytes']<=ready['ram_storage_contract']['evidence_budget_bytes'])
    hq_freshness=[]
    if not controller_not_started:
        with (case/'controller/allocation-events.jsonl').open() as stream:
            for line in stream:
                record=json.loads(line)
                if record['kind']=='ros_delay_source_freshness':hq_freshness.append(record['applied'])
    fresh_non_gateway=dict(
        BoundPeer=[integrity['record_saves']['bound-mask-recording-saved.json']['source_freshness_applied']],
        Observer=[r['applied'] for r in events if r['kind']=='ros_delay_source_freshness'],HQ=hq_freshness)
    final=controlled['coordinator_final']
    clock=(controlled['integrity'] is True and not final['failure'] and not final['physics_failed']
           and final['session_id']==slot['session_id'] and final['execution_profile']==ready['network']['execution_profile'])
    load=host['native_load']; expected_native=Path(ready['network']['native_identity']['binary']['relative_phase'])
    if not expected_native.is_absolute():expected_native=repo.parent/expected_native
    effective=read(netdir/'native/effective-network.json')
    native_profile=ready['network']['native_profile']
    radio=dict(B=('VhtMcs9',16,2),C=('VhtMcs3',2,3))[native_profile]
    identity=(all(load[key] is True for key in ('exact_names','all_in_expected_root','actual_exe_matches','actual_parent_is_Hub'))
        and Path(load['exe']).resolve()==expected_native.resolve()
        and effective['profile']==native_profile and effective.get('rng_seed')==slot['native_rng_seed']
        and effective.get('rng_run')==slot['native_rng_run']
        and (effective['data_mode'],effective['tx_power_dbm'],effective['pathloss_exponent'])==radio
        and ready['network']['session_id']==slot['session_id']
        and ready['case_relative_phase']==slot['case_relative_repo'])
    declared_delay=ready['network']['ros_delay']
    identity=identity and declared_delay['condition']==slot['experiment_condition'] and declared_delay['one_way_wall_ms']==slot['nominal_added_one_way_delay_wall_ms']
    identity=identity and ready['network']['comparison_condition']==slot['physical_path']
    gate_path=case/'controller/startup_gate.json'
    gate=None if controller_not_started and not gate_path.exists() else read(gate_path)
    attempts=[] if gate is None else [r for r in gate['events'] if r['kind']=='decision_attempt']
    submissions=[] if gate is None else gate['goal_submissions']
    timing=(controller_not_started if gate is None else
        gate['profile']==ready['network']['execution_profile'] and gate['failure'] is None
        and all(abs(r['actual_sim_ns']-r['planned_sim_ns'])<=10_000_000 for r in attempts)
        and len({r['planned_sim_ns'] for r in attempts})==len(attempts)
        and all(25_000_000_000<=r['actual_sim_ns']<140_000_000_000 for r in submissions))
    full=(run['end_reason']=='simulation_budget' and run['sim_elapsed']>=ready['sim_budget']
          and actual_window is not None and actual_window['duration']>=ready['sim_budget']
          and run['run_integrity'] is True
          and integrity['network_run_integrity'] is True and host['runner_exit']==0 and host['hub_exit']==0)
    if full:
        timing=timing and [r['planned_sim_ns'] for r in attempts]==list(range(25_000_000_000,140_000_000_000,5_000_000_000))
    policy=dict(autonomy_rtf_each_arm=dict(lower=.245,upper=.255),token_lateness_p95_wall_ms_max=20,
                token_lateness_above_40wall_ms_fraction_max=.01)
    # Safety/copy gates precede all token/event analysis. No bag or Gateway topics are opened here.
    if not (owners and stop and closed and copy_ok):
        raise RuntimeError('Actual owner/safe-stop/closure/copy evidence failed; do not analyze or release RAM')
    if actual_window and actual_window['duration']>0:
        pacing,coordinator=pacing_prefix(case,policy,repo)
    else:
        pacing=None
        coordinator=read(case.with_name(case.name+'.time-control')/'coordinator.json')
    barrier=barrier_proof(gate,coordinator,ready,actual_window,full)
    startup=startup_proof(lines(case/'startup-spawn-events.jsonl'),
        (case/'startup-factory-fence.stdout').read_text(),coordinator,ready)
    timing=timing and barrier['pass_'] and startup['pass_']
    identity=identity and ready['gzserver_batch_gdb'] is False
    process_ok=(host.get('error') is None and not host.get('host_timeout') and not host.get('hub_timeout_after_runner')
        and not controlled['forced_owned_groups'] and saved['saved'] is True
        and all(value==0 for value in controlled['exits'].values())
        and (controller_not_started or controller_exit['returncode']==0))
    evidence=(all(row['saved'] is True for row in integrity['record_saves'].values())
        and (case/'source-observer-measurement.json').is_file()
        and (case/'source-observer-takes.jsonl').is_file()
        and (controller_not_started or ((case/'controller/consumer-trace-summary.json').is_file()
            and (case/'controller/consumer-trace.jsonl').is_file())))
    if slot['hold_applicable']:
        evidence=evidence and (case/'ros-delay-queue.json').is_file()
    checks=dict(identity_config_source=identity,clock=clock,
        pacing=None if pacing is None else pacing['pass_'],actual_attempt_timing=timing,
        adapter_process=process_ok,independent_wall_progress=clock,evidence_complete=evidence)
    proof=dict(schema='clearance-tuning6-post-exit-proof-v1',case_relative_repo=slot['case_relative_repo'],
        native_evidence_ram=slot['native_evidence_ram'],proof_relative_repo=str(output.relative_to(repo)),
        all_owners_writers_gone=owners,copy_complete=copy_ok,disk_raw_retained=True,
        original_safe_stop=stop,owned_requests_closed=closed,engineering_checks=checks,
        original_run_stop_network_qualification=full,original_run_integrity=run['run_integrity'],
        original_run_error=run.get('error'),original_end_reason=run['end_reason'],original_hazard=run.get('hazard'),
        original_gateway_failure=saved['failure'],actual_window=actual_window,pacing=pacing,
        observed_budget_overshoot_sim_s=None if actual_window is None else max(0.,actual_window['duration']-ready['sim_budget']),
        budget_stop_semantics='Original >=budget detection and original bounded host/clock/pacing/23slot/goal permission gates; actual overshoot retained, common metric window capped at120.',
        observer_error_events=[r for r in events if r['kind']=='error'],
        autonomous_pacing_status='N/A_NO_AUTONOMY' if pacing is None else 'PASS' if pacing['pass_'] else 'FAIL',
        actual_attempt_count=len(attempts),original_controller_exit=host['controller_exit'],
        controller_not_started_proven=controller_not_started,
        startup_gate_status='N/A_HQ_NOT_STARTED' if gate is None else 'ACTUAL_SIDECAR_PRESENT',
        decision_boundary_barrier=barrier,
        startup_initialization=startup,
        original_native_effective=effective,
        source_freshness_actual_non_gateway=fresh_non_gateway,
        source_freshness_known_owned_pids=cleanup['original_recorded_pids'],
        source_freshness_owned_roles=dict(Gateway=[r['pid'] for r in owned_rows if r['role']=='network_gateway'],HQ=controller_pids))
    save(output,proof)
    return proof


def poststop_exit_proof(case, slot, host, integrity, events):
    """Original footer and supervisor records; no invented SIGTERM timestamp."""
    errors=[]
    phases=lines(case/'network-gateway-close-phases.jsonl') if (case/'network-gateway-close-phases.jsonl').exists() else []
    names=('resources_closed','persist_end','close_return','main_return')
    selected={name:[r for r in phases if r.get('phase')==name] for name in names}
    supervision=[r for r in events if r.get('kind')=='gateway_poststop_supervision']
    grace=[r for r in events if r.get('kind')=='gateway_evidence_grace']
    signals=[r for r in events if r.get('kind')=='process_signal' and r.get('process')=='network_gateway']
    exits=[r for r in events if r.get('kind')=='process_exit' and r.get('process')=='network_gateway']
    if (any(len(v)!=1 for v in selected.values()) or len(supervision)!=1 or len(grace)!=1
            or [r.get('signal') for r in signals]!=['SIGINT','SIGTERM'] or len(exits)!=1):
        return dict(pass_=False,errors=['missing_or_duplicate_footer_or_supervisor_records'])
    footer=[selected[n][0] for n in names];s=supervision[0];g=grace[0];term=signals[1]
    pids=[r['pid'] for r in lines(case/'owned_processes.jsonl') if r.get('role')=='network_gateway']
    expected_case='/mnt/'+slot['case_relative_repo'];pid=s['pid']
    if pids!=[pid] or not all(r.get('pid')==pid and r.get('session_id')==slot['session_id']
            and r.get('case')==expected_case for r in footer):errors.append('footer_owner_identity')
    if not all(r.get('pid')==pid for r in [g,*signals]):errors.append('supervisor_owner_identity')
    resource_path=case/'network-gateway-resources-closed.json'
    resource=read(resource_path) if resource_path.exists() else None
    cleanup=footer[0].get('cleanup',{})
    states=cleanup.get('action_confirmation_states',{})
    if (resource!=footer[0] or g.get('resources_closed')!=resource or footer[0].get('safe_closed') is not True
            or cleanup.get('resources_destroyed') is not True or cleanup.get('end_frame_flushed') is not True
            or cleanup.get('executor_shutdown')!=[True,True] or cleanup.get('unresolved_C_RPC')!=[]
            or cleanup.get('unresolved_R_RPC')!=[] or any(cleanup.get('unresolved_local_cleanup_futures',{'missing':1}).values())
            or set(states)!= {'C','R'} or any(x.get('waiting')!=0 or x.get('unconfirmed')!=0
                or x.get('failure') is not None for x in ([states['C'],*states['R'].values()] if set(states)=={'C','R'} else []))):
        errors.append('resources_not_proven_closed')
    stamps=[r.get('monotonic_ns') for r in footer]
    lower=g.get('grace_deadline_ns')
    if (not all(isinstance(n,int) for n in stamps) or stamps!=sorted(set(stamps))
            or not isinstance(lower,int) or not s['begin_monotonic_ns']<=stamps[0]<=s['initial_deadline_ns']
            or not stamps[-1]<lower):errors.append('footer_not_before_original_SIGTERM_lower_bound')
    if (s.get('extension_eligible') is not True or g.get('total_deadline_ns')!=s['total_deadline_ns']
            or lower!=s['total_deadline_ns']-10_000_000_000
            or term.get('deadline_monotonic_ns')!=s['total_deadline_ns']-5_000_000_000
            or term['wall']-s['wall']<(lower-s['begin_monotonic_ns'])/1e9
            or s.get('sim',0)<140 or term.get('sim',0)<140):errors.append('original_supervisor_deadline_or_order')
    if (footer[2].get('clean') is not True or footer[3].get('exit_code')!=0
            or exits[0].get('code')!=-15 or integrity['gateway_exit']['native_exit']!=-15
            or host['runner_exit']!=0 or host['hub_exit']!=0):errors.append('exit_not_exact_poststop_SIGTERM_case')
    return dict(pass_=not errors,errors=errors,pid=pid,session_id=slot['session_id'],case=expected_case,
        footer_monotonic_ns=dict(zip(names,stamps)),SIGTERM_send_monotonic_ns=None,
        SIGTERM_send_lower_bound_monotonic_ns=lower,
        main_return_before_SIGTERM_lower_bound_s=None if not isinstance(lower,int) else (lower-stamps[-1])/1e9,
        actual_SIGTERM_event=term,
        timing_basis='Original supervisor code waits until recorded grace deadline before its SIGTERM; original process_signal wall interval corroborates. Exact signal-send monotonic timestamp was not recorded. main_return exit_code0 is intent, not actual clean exit.')


def window_qualification(proof, delivery, run, poststop):
    """Full common measurement window, independently of OS clean exit."""
    actual=proof['actual_window'];trace={} if delivery is None else delivery.get('trace_completion',{})
    full=bool(actual and actual['start']==20 and actual['duration']>=120
        and run['end_reason']=='simulation_budget' and run['sim_elapsed']>=120 and run['run_integrity'] is True
        and proof['original_hazard'] is None and proof['original_run_error'] is None
        and proof['original_gateway_failure'] is None and proof['observer_error_events']==[]
        and proof['actual_attempt_count']==23
        and [r['planned_sim_ns'] for r in proof['decision_boundary_barrier']['matched']]
            ==list(range(25_000_000_000,140_000_000_000,5_000_000_000))
        and all(proof.get(k) is True for k in ('all_owners_writers_gone','copy_complete','disk_raw_retained',
              'original_safe_stop','owned_requests_closed'))
        and all(proof['engineering_checks'].get(k) is True for k in run_batch.ENGINEERING_GATES)
        and delivery is not None and delivery['measurement_valid'] is True
        and trace.get('source',{}).get('complete') is True and trace.get('hq',{}).get('complete') is True
        and trace.get('wire_saved') is True and delivery.get('measurement_invalid_reasons')==[]
        and all(delivery.get(k)==[] for k in ('duplicate_native_ingress_ids','duplicate_destination_ids','ingress_identity_errors'))
        and (proof['original_run_stop_network_qualification'] is True or poststop['pass_'] is True))
    return full


def apply_window_amendment(result, row, proof, slot, case):
    """Same saved-JSON rule for prior and future slots; never re-run metrics."""
    run=read(case/'result.json');host=read(case.with_name(case.name+'.host-exit.json'))
    integrity=read(case.with_name(case.name+'.network-integrity.json'))
    full=result['batch_classification'] in ('QUALIFIED_REACHED_CONTINUE','QUALIFIED_UNREACHED_CONTINUE')
    clean=(integrity['gateway_exit']['native_exit']==0 and integrity['network_run_integrity'] is True
        and host['runner_exit']==0 and host['hub_exit']==0 and host['controller_exit']['returncode']==0)
    poststop=(dict(pass_=False,errors=[],status='N/A_ORIGINAL_QUALIFIED') if full else
        poststop_exit_proof(case,slot,host,integrity,lines(case/'events.jsonl')))
    window_ok=(window_qualification(proof,result['delivery'],run,poststop)
        and result['earlier_engineering_faults']==[] and result['unclassified_faults']==[]
        and result['receipt_protection_events']==[])
    result.update(task_window_measurement_qualified=window_ok,full_engineering_qualified=full,
        clean_exit=clean,poststop_exit_proof=poststop,
        offline_method_amendment='New prospective task window/full-engineering distinction inherited from reviewed strict prior method; no old run is upgraded')
    result['batch_classification']=run_batch.classification(result)
    row.update(task_window_measurement_qualified=window_ok,full_engineering_qualified=full,
        clean_exit=clean,batch_classification=result['batch_classification'],
        offline_method_amendment=result['offline_method_amendment'])
    if window_ok:
        d=result['delivery'];cohort=d['source_cohort'];wall=d['source_publish_to_hq_take_return_wall_ms']
        wire=d['wire_capture_to_destination_publish'];native=d['ingress_to_native_rx_sim_ms'];fifo=d['a1_local_fifo_clock_witness_delta_sim_ms']
        row.update(source_delivery_rate=cohort['exact_success_rate'],source_delivery_rate_lower=cohort['success_rate_lower'],
            source_delivery_rate_upper=cohort['success_rate_upper'],
            wire_delivery_rate=None if wire is None else wire['exact_success_rate'],
            source_to_hq_mean_wall_ms=wall['mean'],source_to_hq_p95_wall_ms=wall['p95'],
            native_service_p95_sim_ms=None if native is None else native['p95'],
            a1_local_fifo_clock_witness_p95_sim_ms=None if fifo is None else fifo['p95'],
            descriptive_partial_delivery=None,partial_delivery_valid=False)
        hold=d['injected_hold_queue']
        if hold['applicable'] and hold['measurement_valid']:
            measured=hold['matched_topicwire_window_capture_cohort']['released_within_window']['hold_wall_ms']
            row.update(injected_hold_mean_wall_ms=measured['mean'],injected_hold_p95_wall_ms=measured['p95'],injected_hold_sample_n=measured['n'])
    return result,row


def run_command(argv, log):
    with log.open('x') as stream:
        subprocess.run(argv,check=True,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT)


def explained_error(error, receipt):
    if error is None:
        return True
    # Only used to reject unrelated errors, never as positive protection proof.
    value=error
    try:
        node=ast.parse(error,mode='eval').body
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='RuntimeError' and len(node.args)==1:
            value=ast.literal_eval(node.args[0])
    except (SyntaxError,ValueError):
        pass
    eligible=[]
    for event in receipt:
        if event.get('robot') not in ('tb1','tb2','tb3') or type(event.get('session_id')) is not int:
            continue
        # Match an error representation only to positive original guard evidence.
        probe=dict(engineering_checks={k:True for k in run_batch.ENGINEERING_GATES},
                   earlier_engineering_faults=[],unclassified_faults=[],original_outcome_retained=True,
                   receipt_protection_events=[event])
        if run_batch.receipt_protection_eligible(probe):eligible.append(event)
    expected={f"STA{event['robot'].removeprefix('tb')} INVALID: {event['reason']}" for event in eligible}
    if value in expected:return True
    if isinstance(value,str) and value.startswith('Network guardian INVALID: '):
        value=value.removeprefix('Network guardian INVALID: ')
    try:
        message=json.loads(value)
    except (json.JSONDecodeError,TypeError):
        return False
    return any(message==dict(robot=int(event['robot'].removeprefix('tb')),
                session_id=event['session_id'],reason=event['reason']) for event in eligible)


def analyze(plan, slot, ready, output, repo=REPO, runner=run_command):
    proof=read(output/'proof.json');run_batch.verify_post_exit(proof,slot)
    case=repo/slot['case_relative_repo'];actual=proof['actual_window']; delivery=None;t95=None
    if actual and actual['duration']>0:
        measurement=output/'delivery.json'
        argv=[sys.executable,'-B',str(REPO/'local-runs/ros-delay-v3-20261114/analyze_delay_delivery.py'),'run',
              '--case',str(case),'--path',slot['physical_path'],'--start-s',str(actual['start']),
              '--budget-s',str(min(actual['duration'],ready['sim_budget'])),'--output',str(measurement)]
        if slot['physical_path'] in ('B','C'):
            argv+=['--hub-ingress',str(repo/slot['network_relative_repo']/'hub-ingress.json')]
        runner(argv,output/'delivery.log');delivery=read(measurement)
        hold=delivery['injected_hold_queue']
        if (hold['applicable'] != slot['hold_applicable'] or (hold['applicable']
                and hold.get('observed_nominal_delay_wall_ms')!=slot['nominal_added_one_way_delay_wall_ms'])):
            delivery['measurement_valid']=False
            delivery['measurement_invalid_reasons'].append('queue_nominal_delay_or_applicability_identity_mismatch')

        scene=read(repo/slot['scene_relative_repo'])
        argv=['bash',str(repo/'net01/ros-python.sh'),'/mnt/tools/analyze_t95_views.py',
              '--case','/mnt/'+slot['case_relative_repo'],'--world','/mnt/'+scene['world_relative_phase'],
              '--assets','/mnt/assets/gazebo_models',
              '--positions='+';'.join(','.join(str(v) for v in row[:2]) for row in ready['common_start_xy_yaw']),
              '--budget-s','120','--output','/mnt/'+str((output/'T95').relative_to(repo))]
        runner(argv,output/'T95.log');t95=read(output/'T95/result.json')
        if t95['reference_free_cells']!=ready['reference']['cells']:
            raise RuntimeError('Per-map T95 reference denominator changed')
    fresh_gateway=[] if delivery is None else delivery['source_freshness_gateway_records']
    facts=None if delivery is None else delivery['original_gateway_facts']
    receipt=[];unknown=[];earlier=[]
    if facts:
        for guard in facts['guards'].values():
            for event in guard['events']:
                if event['kind']=='latched_INVALID':
                    if event['reason'] in run_batch.RECEIPT_FIELDS:receipt.append(event)
                    else:unknown.append(event)
        if facts.get('failure'):
            unknown.append(dict(kind='gateway_failure',detail=facts['failure']))
    if delivery is None and not actual:
        # No task-period cohort/latency calculation without autonomy. This is the
        # only Gateway read in this branch, solely extracting original guard facts.
        gateway=read(case/'network-gateway.json')
        facts=dict(failure=gateway.get('failure'),guards=gateway['guards'])
        fresh_gateway=[r['source_freshness_applied'] for r in gateway['records'] if r['kind']=='common_raw_destination_production_entry' and 'source_freshness_applied' in r]
        for guard in facts['guards'].values():
            for event in guard['events']:
                if event['kind']=='latched_INVALID':
                    (receipt if event['reason'] in run_batch.RECEIPT_FIELDS else unknown).append(event)
        if facts['failure']:
            unknown.append(dict(kind='gateway_failure',detail=facts['failure']))
    fresh_actual=dict(proof['source_freshness_actual_non_gateway'],Gateway=fresh_gateway)
    fresh_proof=freshness_application_proof(ready,slot,fresh_actual,
        set(proof['source_freshness_known_owned_pids']),proof['source_freshness_owned_roles'],proof['controller_not_started_proven'])
    proof['engineering_checks']['identity_config_source']=proof['engineering_checks']['identity_config_source'] and fresh_proof['pass_']
    if not fresh_proof['pass_']:earlier.append(dict(kind='actual_source_freshness_application_invalid',errors=fresh_proof['errors']))
    navigation_proof=navigation_application_proof(ready,fresh_actual,case)
    proof['engineering_checks']['identity_config_source']=proof['engineering_checks']['identity_config_source'] and navigation_proof['pass_']
    if not navigation_proof['pass_']:earlier.append(dict(kind='actual_navigation_application_invalid',errors=navigation_proof['errors']))
    for event in receipt:
        if event.get('robot') not in ('tb1','tb2','tb3') or event.get('session_id')!=slot['session_id']:
            unknown.append(dict(kind='guard_identity_mismatch',event=event))
    if not explained_error(proof['original_run_error'],receipt):
        unknown.append(dict(kind='original_run_error',detail=proof['original_run_error']))
    for event in proof['observer_error_events']:
        if not explained_error(event.get('detail'),receipt):
            earlier.append(event)
    if proof['original_hazard']:
        unknown.append(dict(kind='original_hazard',detail=proof['original_hazard']))
    measurement_errors=[] if delivery is None or delivery['measurement_valid'] else delivery['measurement_invalid_reasons']
    if measurement_errors:earlier.append(dict(kind='measurement_invalid',reasons=measurement_errors))
    result=dict(classification_contract='clearance-tuning6-root-reviewed-v1',
        logical_slot=slot.get('logical_slot',slot['id']),physical_slot=slot['id'],
        setup_predecessor=slot.get('setup_predecessor'),amendment=slot.get('amendment_relative_repo'),
        engineering_checks=proof['engineering_checks'],earlier_engineering_faults=earlier,
        unclassified_faults=unknown,original_outcome_retained=True,
        original_run_stop_network_qualification=proof['original_run_stop_network_qualification'],
        autonomous_window_started=actual is not None,
        autonomous_pacing_status=proof['autonomous_pacing_status'],
        receipt_protection_events=receipt,T95_sim_s=None if t95 is None else t95['views']['central_merged']['T95_sim_s'],
        original_run_error=proof['original_run_error'],original_run_integrity=proof['original_run_integrity'],
        measurement_errors=measurement_errors,delivery=delivery,T95=t95,source_freshness_application_proof=fresh_proof,navigation_clearance_application_proof=navigation_proof)
    result['batch_classification']=run_batch.classification(result)
    central=None if t95 is None else t95['views']['central_merged']
    quality={}
    if t95:
        for name in t95['views']:
            with (output/'T95'/f'{name}.csv').open() as stream:rows=list(csv.DictReader(stream))
            valid=sum(row['map_quality_valid']=='True' for row in rows)
            quality[name]=dict(total=len(rows),valid=valid,invalid=len(rows)-valid)
    qualified=(result['batch_classification'] in ('QUALIFIED_REACHED_CONTINUE','QUALIFIED_UNREACHED_CONTINUE'))
    cohort=None if delivery is None else delivery['source_cohort']
    wire=None if delivery is None else delivery['wire_capture_to_destination_publish']
    wall=None if delivery is None else delivery['source_publish_to_hq_take_return_wall_ms']
    native=None if delivery is None else delivery['ingress_to_native_rx_sim_ms']
    fifo=None if delivery is None else delivery['a1_local_fifo_clock_witness_delta_sim_ms']
    hold=None if delivery is None else delivery['injected_hold_queue']
    hold_stats=(None if hold is None or not hold['applicable'] or not hold['measurement_valid'] else
        hold['matched_topicwire_window_capture_cohort']['released_within_window']['hold_wall_ms'])

    row=dict(slot=slot.get('logical_slot',slot['id']),physical_slot=slot['id'],
        block=slot['block'],
        actual_physical_rtf=None if proof['pacing'] is None else proof['pacing']['rtf'],
        setup_predecessor=slot.get('setup_predecessor'),amendment=slot.get('amendment_relative_repo'),
        map=slot['map'],path=slot['physical_path'],experiment_condition=slot['experiment_condition'],
        nominal_added_one_way_delay_wall_ms=slot['nominal_added_one_way_delay_wall_ms'],
        hold_applicable=slot['hold_applicable'],t95_sim_s=result['T95_sim_s'],
        last_coverage=None if central is None or central['last_observation'] is None else central['last_observation']['coverage'],
        source_delivery_rate=None if not qualified or cohort is None else cohort['exact_success_rate'],
        source_delivery_rate_lower=None if not qualified or cohort is None else cohort['success_rate_lower'],
        source_delivery_rate_upper=None if not qualified or cohort is None else cohort['success_rate_upper'],
        wire_delivery_rate=None if not qualified or wire is None else wire['exact_success_rate'],
        source_to_hq_mean_wall_ms=None if not qualified or wall is None else wall['mean'],
        source_to_hq_p95_wall_ms=None if not qualified or wall is None else wall['p95'],
        native_service_p95_sim_ms=None if not qualified or native is None else native['p95'],
        a1_local_fifo_clock_witness_p95_sim_ms=None if not qualified or fifo is None else fifo['p95'],
        injected_hold_queue=hold,
        injected_hold_mean_wall_ms=None if not qualified or hold_stats is None else hold_stats['mean'],
        injected_hold_p95_wall_ms=None if not qualified or hold_stats is None else hold_stats['p95'],
        injected_hold_sample_n=None if hold_stats is None else hold_stats['n'],
        injected_hold_scope='Matched TopicWire capture cohort, queue release within actual half-open task window, excluding close drain; full all-business and release cohorts separate in injected_hold_queue',

        batch_classification=result['batch_classification'],full_engineering_qualified=qualified,
        autonomous_window=actual,autonomous_pacing_status=proof['autonomous_pacing_status'],quality_counts=quality,source_freshness_application_proof=fresh_proof,navigation_clearance_application_proof=navigation_proof,
        communication_observation_budget_sim_s=None if actual is None else min(actual['duration'],ready['sim_budget']),
        observed_budget_overshoot_sim_s=proof.get('observed_budget_overshoot_sim_s'),
        measurement_valid=None if delivery is None else delivery['measurement_valid'],
        source_cohort=cohort,wire_capture_to_destination_publish=wire,
        source_cohort_by_topic=None if delivery is None else delivery['source_cohort_by_topic'],
        source_to_hq_latency_by_topic=None if delivery is None else delivery['source_publish_to_hq_take_return_wall_ms_by_topic'],
        source_to_hq_latency_samples=None if wall is None else wall['n'],
        native_service_samples=None if native is None else native['n'],
        a1_local_fifo_clock_witness_samples=None if fifo is None else fifo['n'],
        source_to_hq_latency_measurement_status=None if delivery is None else delivery['wall_latency_measurement_status'],
        central_last_map_quality_valid=None if central is None or central['last_observation'] is None
            else central['last_observation']['map_quality_valid'],
        measurement_errors=measurement_errors,descriptive_partial_delivery=None if qualified else delivery,
        partial_delivery_valid=(not qualified and delivery is not None and delivery['measurement_valid']
            and proof['engineering_checks']['pacing'] is True
            and not earlier and not unknown),
        partial_delivery_qualification_rule='partial_delivery_valid marks a measurement candidate only; qualified partial requires final TASK_INFORMATION_FRESHNESS_PROTECTION classification as well. Engineering BLOCK data remain unqualified diagnostics.',
        original_run_integrity=proof['original_run_integrity'],original_run_error=proof['original_run_error'])
    apply_window_amendment(result,row,proof,slot,case)
    task_metric_valid=(t95 is not None and quality['central_merged']['valid']>0
        and (row['task_window_measurement_qualified'] or
            (result['batch_classification']=='TASK_INFORMATION_FRESHNESS_PROTECTION'
             and row['partial_delivery_valid'])))
    task_metric_status=('UNKNOWN' if not task_metric_valid else
        'CONFIRMED_REACHED' if row['t95_sim_s'] is not None else
        'EXPLICITLY_UNREACHED_IN_OBSERVED_WINDOW')
    task_metric_unknown_reason=(None if task_metric_valid else
        'No qualified actual-window quality-valid T95 measurement; null is not observed non-completion')
    for record in (row,result):
        record.update(task_metric_status=task_metric_status,
            task_metric_unknown_reason=task_metric_unknown_reason,
            task_metric_actual_window=actual)
    save(output/'row.json',row);save(output/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('preflight','verify','analyze','summary'))
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--slot')
    args=parser.parse_args()
    if args.operation=='summary':
        plan=read(args.plan)
        rows=[read(REPO/s.get('summary_row_result_relative_repo',s['batch_hooks']['row_result'])) for s in plan['slots']]
        import statistics
        groups=[]
        def stats(values):
            available=[v for v in values if v is not None]
            return dict(available_runs=len(available),mean=(statistics.mean(available) if len(available)==3 else None),
                sample_sd=(statistics.stdev(available) if len(available)==3 else None))
        for name in ('Corr6201','Rooms6101'):
            runs=[r for r in rows if r['map']==name]
            if len(runs)!=3:raise RuntimeError('Expected exactly three declared runs per map')
            n=sum(r['task_metric_status']=='CONFIRMED_REACHED' for r in runs)
            m=sum(r['task_metric_status']=='EXPLICITLY_UNREACHED_IN_OBSERVED_WINDOW' for r in runs)
            k=sum(r['task_metric_status']=='UNKNOWN' for r in runs)
            reached=[r['t95_sim_s'] for r in runs if r['task_metric_status']=='CONFIRMED_REACHED']
            groups.append(dict(map=name,declared_runs=3,confirmed_reached=n,explicitly_unreached=m,unknown=k,
                T95_all_three=stats([r['t95_sim_s'] if r['task_metric_status']=='CONFIRMED_REACHED' else None for r in runs]),
                T95_reached_only=dict(n=n,mean=statistics.mean(reached) if reached else None,
                    sample_sd=statistics.stdev(reached) if len(reached)>1 else None),
                end_coverage=stats([r['last_coverage'] if r['task_metric_status']!='UNKNOWN' else None for r in runs]),
                full_engineering_qualified=sum(r['full_engineering_qualified'] is True for r in runs),
                clean_exit=sum(r['clean_exit'] is True for r in runs),runs=runs))
        started=[r for r in lines(TASK/'execution.jsonl') if r['state']=='HOST_STARTED']
        save(TASK/'rows.json',rows)
        save(TASK/'SUMMARY.json',dict(schema='navigation-clearance-six-summary-v1',groups=groups,
            actual_unique_HOST_STARTED=len({r['slot'] for r in started}),declared_slots=len(rows),
            historical_references=plan['historical_references'],scope='Fresh six A0 runs; old A0 references descriptive only, no pooling or automatic replacement'))
        return
    plan,slot,ready=select(args.plan,args.slot)
    output=TASK/'post-exit'/slot['id']
    if args.operation=='preflight':
        print(json.dumps(preflight(plan,slot,ready)))
    elif args.operation=='verify':
        output.mkdir(parents=True,exist_ok=False)
        verify(plan,slot,ready,output/'proof.json')
    else:
        analyze(plan,slot,ready,output)


if __name__=='__main__':main()

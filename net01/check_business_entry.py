"""Current production profile handoff with process launch intercepted.

Real Gateway ROS entities and production raw wire factory, controlled Hub only.
Synthetic case source binding never grants or starts a Gazebo experiment.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from rclpy.clock import ClockType
from rclpy.time import Time
import gateway
from execution_profile import (SIM_BUSINESS_PROFILE_ID,SIM_BUSINESS60_PROFILE_ID,
    SIM_BUSINESS_PROFILE_FILES,NATIVE_RAM60_SCOPE,load_profile,BUSINESS60_PROFILE_IDS,FIXED_START60_PROFILE_ID,FIXED_START_ADAPTER_FILES)
from time_control_runtime import controlled_config,CONTROLLED_BUSINESS180_SCOPE,CONTROLLED_BUSINESS60_SCOPE,CONTROLLED_FIXED_START60_SCOPE
from time_control_state import TimeControlState

ROOT=Path(__file__).resolve().parents[1]

def module(relative,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profile',choices=tuple(SIM_BUSINESS_PROFILE_FILES),default=SIM_BUSINESS_PROFILE_ID)
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=False)
    selected_profile=args.profile
    physical60=selected_profile in BUSINESS60_PROFILE_IDS
    fixed_start=selected_profile==FIXED_START60_PROFILE_ID
    profile=load_profile(selected_profile)
    result=dict(status='FAIL',checks={},scope='Production handoff/component checks; Hub controlled; subprocess exec and case admission marker intercepted; no Gazebo/ns3/Nav2 run')
    def check(name,value):
        if not value:raise AssertionError(name)
        result['checks'][name]=True
    keys=['host_run.py','tools/packet_hub.py','execution_profile.py','business_peer.py','bound_peer.py','action_wire.py','gateway.py',
        'boot_network.py','run_network_case.py','time_control_state.py','time_control_runtime.py',
        'config/'+SIM_BUSINESS_PROFILE_FILES[selected_profile]]
    if fixed_start:keys += list(FIXED_START_ADAPTER_FILES)
    keys += ['../net01e/followup01/'+name for name in ('production_gateway.py','production_host.py','raw_destination_wire.py')]
    keys += ['../net01e/controller/'+name for name in ('graceful_controller_bootstrap.py','graceful_spin.py','GRACEFUL_ADMISSION.json','host_run.py')]
    net=dict(execution_profile=selected_profile,controller_exit_adapter='net01e-graceful-v1',
        raw_destination=True,mode='B',adapter_sha256={k:hashlib.sha256((ROOT/'net01'/k).read_bytes()).hexdigest() for k in keys},
        controlled_time=dict(engineering_scope=(CONTROLLED_FIXED_START60_SCOPE if fixed_start else CONTROLLED_BUSINESS60_SCOPE) if physical60 else CONTROLLED_BUSINESS180_SCOPE))
    if physical60:
        net.update(native_evidence_scope=NATIVE_RAM60_SCOPE,native_evidence_ram=str(output/'not-created-ram'),
            native_ledger_mode='serial',native_async_ledger=False,native_cpu_profile=False)
    config=dict(network=net,**profile['run_bounds'],
        authorized_net01_execution=True,arm='rl',case_path=str(output/'never-started'))
    document=output/'synthetic-component-input.json'
    # Permission below exists only in this explicitly synthetic component input;
    # all process execution and the admission marker are intercepted below.
    document.write_text(json.dumps(config,indent=2)+'\n')
    g=None
    class Intercepted(Exception):pass
    try:
        check('explicit_40ms_profile_selected',profile['token_wall_period_ns']==40_000_000)
        state=TimeControlState(profile['token_wall_period_ns']);state.native('ready',0);state.gateway_clock_ready=True
        state.begin_step(100)
        check('pace40_is_real_token_schedule',state.next_wall_ns==40_000_100)
        check('new_controlled_contract_selectable',controlled_config(config) is net['controlled_time'])
        if physical60:
            import host_run
            check('physical60_has_absolute_host_ceiling820',host_run.host_wall_limits(config,net['controlled_time'])==(True,820))
            old180=dict(config,sim_budget=180,autonomous_wall=960,outer_wall=1200,
                network=dict(net,execution_profile=SIM_BUSINESS_PROFILE_ID,
                    controlled_time=dict(engineering_scope=CONTROLLED_BUSINESS180_SCOPE)))
            check('legacy180_host_ceiling1300_unchanged',host_run.host_wall_limits(old180,controlled_config(old180))==(True,1300))
            for name,changed in (
                ('missing_RAM_scope',dict(net,native_evidence_scope=None)),
                ('missing_RAM_path',dict(net,native_evidence_ram=None)),
                ('async_diagnostics',dict(net,native_async_ledger=True)),
                ('CPU_diagnostics',dict(net,native_cpu_profile=True)),
                ('session_RAM_is_different_backend',dict(net,native_ledger_mode='session-ram-v1'))):
                try:controlled_config(dict(config,network=changed))
                except ValueError:check('physical60_rejects_'+name,True)
                else:raise AssertionError('Physical60 accepted '+name)
            try:controlled_config(dict(config,sim_budget=180))
            except ValueError:check('physical60_rejects_other_sim_budget',True)
            else:raise AssertionError('Physical60 accepted180sim')
        old=dict(config,network=dict(net,controlled_time=dict(engineering_scope='NET01 controlled-time 180sim common A1/B baseline; original safety gates')))
        try:controlled_config(old)
        except ValueError:check('old_scope_cannot_claim_new_profile',True)
        else:raise AssertionError('old contract accepted')
        host=module('net01e/followup01/production_host.py','business_production_host')
        with patch.object(sys,'argv',['production_host','--ready',str(document)]),patch.object(host.os,'execv') as execute:
            host.main()
        check('production_host_reaches_existing_controller_host',execute.call_count==1 and execute.call_args[0][1][2].endswith('net01e/controller/host_run.py'))
        boot=module('net01/boot_network.py','business_boot')
        original_open=Path.open
        def open_without_admission(path,*args,**kwargs):
            if path.name.endswith('.admission-used.json'):raise Intercepted()
            return original_open(path,*args,**kwargs)
        with patch.object(sys,'argv',['boot','--ready',str(document)]),patch.object(boot.frozen,'validate_ready',return_value=config),patch.object(Path,'open',open_without_admission):
            try:boot.main()
            except Intercepted:check('boot_passes_profile_bounds_source_gate_before_admission',True)
            else:raise AssertionError('Expected admission interception')
        if physical60:
            for field,value in (('autonomous_wall',960),('outer_wall',900)):
                with patch.object(sys,'argv',['boot','--ready',str(document)]),patch.object(boot.frozen,'validate_ready',return_value=dict(config,**{field:value})):
                    try:boot.main()
                    except ValueError:check('physical60_boot_rejects_wrong_'+field,True)
                    else:raise AssertionError('Physical60 boot accepted wrong '+field)
        check('no_admission_marker_written',not (output/'never-started.admission-used.json').exists())
        production=module('net01e/followup01/production_gateway.py','business_production_gateway')
        class Hub:
            def __init__(self,*args,**kwargs):self.receive=None
        def component_main(*,gateway_factory):
            nonlocal g
            g=gateway_factory('A','controlled-no-socket',output,701,execution_profile=selected_profile)
            g.install_wires()
            return 0
        environment=dict(NET01_RAW_DESTINATION='1',NET01_EXECUTION_PROFILE=selected_profile,
            NET01_CONTROLLER_EXIT_ADAPTER='net01e-graceful-v1',NET01_DIRECT_REFERENCE='0')
        with patch.dict(os.environ,environment),patch.object(sys,'argv',['production_gateway','--execution-profile',selected_profile]),patch.object(gateway,'HubClient',Hub),patch.object(gateway,'main',component_main):
            check('production_gateway_factory_executes',production.main()==0)
        check('production_uses_declared_destination_wires',all(type(w).__name__==('ConsumerTraceTopicWire' if fixed_start else 'RawDestinationTopicWire') for w in g.wires.values()))
        check('production_Action_C_R_business_clocks_are_sim',all(a.business_clock_basis=='ros-sim-v1' for a in (g.action_c,*g.action_r.values())))
        check('production_journal_uses_sim_clock',g.journal_timer.clock is g.c.get_clock())
        check('administrative_status_and_local_stop_keep_steady_clocks',g.status_timer.clock.clock_type==ClockType.STEADY_TIME and all(s.timer.clock.clock_type==ClockType.STEADY_TIME for s in g.guards.values()))
        for node in (g.c,g.r):node.get_clock().set_ros_time_override(Time(seconds=123))
        check('actual_Gateway_Action_clock_nanoseconds',g.action_c.now()==123_000_000_000 and all(a.now()==123_000_000_000 for a in g.action_r.values()))
        result.update(status='PASS',profile=selected_profile,run_bounds=profile['run_bounds'])
    except BaseException as error:result['error']=repr(error);raise
    finally:
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if g is not None:
            if g.wires is not None:
                for action in (g.action_c,*g.action_r.values()):action.close()
            for executor,node,context in zip(g.executors,g.nodes,g.contexts):
                executor.shutdown(timeout_sec=0);node.destroy_node();context.shutdown()
            if g.gc_original_enabled:gc.enable()
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

"""One reviewed NET admission, existing frozen bounds/owned cleanup retained."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from time_control_runtime import controlled_config
from execution_profile import SIM_BUSINESS_PROFILE_ID,BUSINESS60_PROFILE_IDS,SIM_BUSINESS_PROFILE_FILES,FIXED_START_PROFILE_IDS,FIXED_START_ADAPTER_FILES,REPAIR120_PROFILE_ID,REPAIR_ADAPTER_FILES,REPAIR_PROFILE_IDS,COMPARISON40_PROFILE_IDS,COMPARISON_PROFILE_IDS,COMPARISON_ADAPTER_FILES,ROS_DELAY_PROFILE_ID,A0_CADENCE_PROFILE_ID,ROS_LOCAL_NAV_PROFILE_IDS,ROS_DELAY_V1_PROFILE_ID,ROS_DELAY_V2_PROFILE_ID,ROS_DELAY_ADAPTER_FILES,PHYSICS_DELAY_PROFILE_ID,PHYSICS_DELAY_ADAPTER_FILES

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/"workspace/gz01"),str(HERE.parent/"workspace/src/multi_robot_exploration")]
import boot as frozen


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ready",type=Path,required=True)
    parser.add_argument("--host-hard-deadline-ns",type=int)
    args=parser.parse_args()
    ready=frozen.validate_ready(args.ready)
    net=ready["network"]
    if net.get('execution_profile') in (ROS_DELAY_V1_PROFILE_ID,ROS_DELAY_V2_PROFILE_ID):
        raise ValueError('ROS delay v1/v2 are preserved retired evidence, not executable cohorts')
    if ready.get("authorized_net01_execution") is not True:raise ValueError("No NET-01 root admission")
    controlled=controlled_config(ready)
    direct_reference=net.get("direct_reference",False)
    controller_exit_adapter=net.get('controller_exit_adapter','original-v1')
    if controller_exit_adapter not in ('original-v1','net01e-graceful-v1'):
        raise ValueError('Unknown controller exit adapter')
    if controller_exit_adapter=='net01e-graceful-v1':
        required={'../net01e/controller/'+name for name in
            ('graceful_controller_bootstrap.py','graceful_spin.py','GRACEFUL_ADMISSION.json','host_run.py')}
        if not required.issubset(net['adapter_sha256']):
            raise ValueError('NET-01E admission must bind its common controller adapter and host entry')
    raw_destination=net.get('raw_destination',False)
    if type(raw_destination) is not bool:
        raise ValueError('raw_destination must be an explicit JSON bool')
    if raw_destination:
        sim_business=net.get('execution_profile') in SIM_BUSINESS_PROFILE_FILES
        if (controller_exit_adapter!='net01e-graceful-v1' or net.get('execution_profile') not in
                ('controlled1000-clock100-q10ms-pace20-raster-simhealth',*SIM_BUSINESS_PROFILE_FILES)):
            raise ValueError('Common raw destination requires an explicit graceful/pace20 version')
        required={'../net01e/followup01/'+name for name in
            ('production_gateway.py','production_host.py','raw_destination_wire.py')}
        if sim_business:
            required.update(('host_run.py','tools/packet_hub.py','execution_profile.py','business_peer.py','bound_peer.py','action_wire.py','gateway.py',
                'time_control_state.py','time_control_runtime.py','config/'+SIM_BUSINESS_PROFILE_FILES[net['execution_profile']]))
        else:
            required.update(('../net01e/followup01/PRODUCTION_ADMISSION.json',
                'config/EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE20_RASTER_SIMHEALTH.json'))
        if net.get('execution_profile') in FIXED_START_PROFILE_IDS:
            required.update(FIXED_START_ADAPTER_FILES)
        if net.get('execution_profile') in REPAIR_PROFILE_IDS:
            required.update(REPAIR_ADAPTER_FILES)
        if net.get('execution_profile') in COMPARISON_PROFILE_IDS:
            required.update(COMPARISON_ADAPTER_FILES)
        if net.get('execution_profile') in ROS_LOCAL_NAV_PROFILE_IDS:
            required.update(ROS_DELAY_ADAPTER_FILES)
        if net.get('execution_profile') == PHYSICS_DELAY_PROFILE_ID:
            required.update(PHYSICS_DELAY_ADAPTER_FILES)
        if not required.issubset(net['adapter_sha256']):
            raise ValueError('Common raw destination source/config binding missing')
    if type(direct_reference) is not bool:
        raise ValueError("direct_reference must be an explicit JSON bool")
    if direct_reference:
        if net["mode"]!="A" or controlled is None:
            raise ValueError("A0 requires mode A and the existing controlled-time profile")
        if not {"a0_gateway.py","a0_runtime.py","a0_controller_bootstrap.py"}.issubset(net["adapter_sha256"]):
            raise ValueError("A0 admission must bind its three external source files")
    bounds=(ready["sim_budget"],ready["startup_wall"],ready["autonomous_wall"],ready["outer_wall"],ready["cleanup_wall"])
    allowed_bounds=(((120,180,420,900,90),(180,180,420,600,90)) if controlled is not None
        else ((180,180,420,900,90),))
    if controlled is not None and net.get('execution_profile') in (
            'controlled1000-clock100-q10ms-pace10-raster-simhealth',
            'controlled1000-clock100-q10ms-pace20-raster-simhealth'):
        allowed_bounds+=((180,180,720,900,90),)
    if net.get('execution_profile')==SIM_BUSINESS_PROFILE_ID:
        allowed_bounds=((180,180,960,1200,90),)
    if net.get('execution_profile') in BUSINESS60_PROFILE_IDS:
        allowed_bounds=((60,180,480,720,90),)
    if net.get('execution_profile') in REPAIR_PROFILE_IDS:
        allowed_bounds=((120,180,720,1000,90),)
    if bounds not in allowed_bounds:
        raise ValueError("NET-01 fixed bounds changed")
    qos_events=net.get('adapter_qos_events','sdk-default')
    if qos_events not in ('sdk-default','warning-free-v1'):
        raise ValueError('Unknown adapter QoS event version')
    capture=net.get('capture_central_map',False)
    if type(capture) is not bool or (capture and direct_reference and net.get('execution_profile') not in COMPARISON_PROFILE_IDS):
        raise ValueError('Central map capture requires an explicit A1/B/C business wire')
    if net["mode"] not in ("A","B","C") or ready["arm"]!="rl":raise ValueError("Only fixed A/B/C RL")
    if net.get('execution_profile') in COMPARISON40_PROFILE_IDS:
        conditions={'A0':('A',True,'B'),'A1':('A',False,'B'),'B':('B',False,'B'),'C':('C',False,'C')}
        expected=conditions[net['comparison_condition']]
        if (net['mode'],direct_reference,net.get('native_profile'))!=expected:
            raise ValueError('Comparison condition differs from actual transport composition')
        if not raw_destination or not capture or net.get('native_transport')!='tcp-mtu-v2':
            raise ValueError('Comparison requires common raw capture and tcp-mtu-v2 composition')
        for key in ('native_rng_seed','native_rng_run'):
            if type(net.get(key)) is not int or net[key]<=0:raise ValueError('Comparison requires explicit '+key)
    if net.get('execution_profile') in ROS_LOCAL_NAV_PROFILE_IDS:
        delay=net['ros_delay'];condition=delay['condition'];milliseconds=delay['one_way_wall_ms']
        expected_ms={'A0':None,'D0':0,'D100':100,'D200':200,'D300':300,'D400':400,'D500':500}[condition]
        if (milliseconds!=expected_ms or (milliseconds is not None and type(milliseconds) is not int)
            or direct_reference!=(condition=='A0') or net['mode']!='A'
            or net.get('comparison_condition')!=('A0' if direct_reference else 'A1')
            or net.get('native_profile')!='B' or not raw_destination or not capture
            or net.get('native_transport')!='tcp-mtu-v2'):
            raise ValueError('ROS wall delay differs from declared literal/proxy composition')
        for key in ('native_rng_seed','native_rng_run'):
            if type(net.get(key)) is not int or net[key]<=0:raise ValueError('ROS delay requires explicit '+key)
    if net.get('execution_profile') == PHYSICS_DELAY_PROFILE_ID:
        delay=net['physical_delay']
        expected={'D0':0,'P500':500_000_000}[delay['condition']]
        if (type(delay['delay_physical_ns']) is not int or delay['delay_physical_ns']!=expected
            or delay['activation_anchor_physical_ns']!=20_000_000_000
            or direct_reference or net['mode']!='A' or net.get('comparison_condition')!='A1'
            or net.get('native_profile')!='B' or not raw_destination or not capture
            or net.get('native_transport')!='tcp-mtu-v2'):
            raise ValueError('Physical delay differs from declared ACK FIFO composition')
        for key in ('native_rng_seed','native_rng_run'):
            if type(net.get(key)) is not int or net[key]<=0:raise ValueError('Physical delay requires explicit '+key)
    navigation_progress = net.get('navigation_progress')
    if navigation_progress is not None:
        from nav_progress_guard import VERSION, CONTRACT_FILE, load_contract
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_progress != {'revision': VERSION}):
            raise ValueError('Owned Goal progress revision requires explicit ROSDelayV3 literalA0')
        if not {'nav_progress_guard.py', CONTRACT_FILE}.issubset(net['adapter_sha256']):
            raise ValueError('Navigation progress helper/contract must be source-bound')
        load_contract(navigation_progress['revision'])
    navigation_recovery = net.get('navigation_recovery')
    if navigation_recovery is not None:
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_progress != {'revision': 'owned-goal-source-odom-progress-v1'}
                or navigation_recovery != {'revision': 'followpath-context-backup-v2'}):
            raise ValueError('Navigation recovery requires explicit progress-v1 literalA0')
        if not {'nav2_recovery_launch.py',
                'config/NAVIGATE_TO_POSE_CONTEXT_BACKUP_V2.xml',
                'config/NAVIGATION_RECOVERY_CONTEXT_BACKUP_V2.json'}.issubset(net['adapter_sha256']):
            raise ValueError('Navigation recovery launch/XML/contract must be source-bound')
    navigation_peer_geometry = net.get('navigation_peer_geometry')
    if navigation_peer_geometry is not None:
        from peer_geometry import CONTRACT_FILES as GEOMETRY_CONTRACTS, load_contract as load_geometry_contract
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_recovery != {'revision': 'followpath-context-backup-v2'}
                or set(navigation_peer_geometry) != {'revision'}
                or navigation_peer_geometry['revision'] not in GEOMETRY_CONTRACTS):
            raise ValueError('Peer geometry requires explicit recovery-v2 literalA0')
        GEOMETRY_CONTRACT=GEOMETRY_CONTRACTS[navigation_peer_geometry['revision']]
        if not {'peer_geometry.py','nav2_peer_geometry_launch.py',GEOMETRY_CONTRACT}.issubset(net['adapter_sha256']):
            raise ValueError('Peer geometry helper/launch/contract must be source-bound')
        load_geometry_contract(navigation_peer_geometry['revision'])
    navigation_planner = net.get('navigation_planner')
    if navigation_planner is not None:
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_peer_geometry not in ({'revision': 'peer-body-postfilter-inflation-v3'},
                                                    {'revision': 'peer-body-postfilter-circumscribed-v5'})
                or navigation_planner != {'revision': 'smac2d-floor-planner-v4'}):
            raise ValueError('Smac planner requires explicit geometry-v3/v5 literalA0')
        if not {'nav2_smac_launch.py','config/NAVIGATION_SMAC2D_FLOOR_V4.json','nav2_goal_guard.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Smac planner launch/contract/goal guard must be source-bound')
    spawn_reply_qos = net.get('spawn_reply_qos')
    if spawn_reply_qos is not None:
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_peer_geometry != {'revision': 'peer-body-postfilter-inflation-v3'}
                or navigation_planner != {'revision': 'smac2d-floor-planner-v4'}
                or spawn_reply_qos != {'revision': 'gazebo-spawn-reply-maxblocking1s-v1'}):
            raise ValueError('Spawn reply QoS requires explicit conservative geometry-v3/Smac-v4 literalA0')
        if not {'net_scene_launch.py','config/SPAWN_REPLY_QOS_V1.json',
                'config/SPAWN_REPLY_MAXBLOCK_1S_V1.xml'}.issubset(net['adapter_sha256']):
            raise ValueError('Spawn reply QoS source/contract/XML must be bound')
    navigation_controller = net.get('navigation_controller')
    if navigation_controller is not None:
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_peer_geometry != {'revision': 'peer-body-postfilter-inflation-v3'}
                or navigation_planner != {'revision': 'smac2d-floor-planner-v4'}
                or spawn_reply_qos != {'revision': 'gazebo-spawn-reply-maxblocking1s-v1'}
                or navigation_controller != {'revision': 'dwb-padded-footprint-obstacle-prevention-v1'}):
            raise ValueError('Footprint critic requires explicit conservative q literalA0')
        if not {'nav2_footprint_critic_launch.py',
                'config/NAVIGATION_DWB_FOOTPRINT_PREVENTION_V1.json'}.issubset(net['adapter_sha256']):
            raise ValueError('Footprint critic launch/contract must be source-bound')
    navigation_shared_map = net.get('navigation_shared_map')
    from shared_navigation_map import (
        ACTIVE_ROUTE_VERSION, ENV as SHARED_MAP_ENV, SEED_ROUTE_ENV, SEED_ROUTE_VERSION,
        VERSIONS as SHARED_MAP_VERSIONS)
    if navigation_shared_map is not None:
        if (net.get('execution_profile') != ROS_DELAY_PROFILE_ID or not direct_reference
                or navigation_controller != {'revision': 'dwb-padded-footprint-obstacle-prevention-v1'}
                or navigation_shared_map not in ({'revision': revision} for revision in SHARED_MAP_VERSIONS)
                or any(net.get(key) is not None for key in ('navigation_goal_checker',
                    'navigation_intent', 'navigation_pair_coordination', 'navigation_nominal_budget',
                    'navigation_frontier_representative'))):
            raise ValueError('Shared navigation maps require the explicit A0 footprint baseline')
        if not {'shared_navigation_map.py','nav2_footprint_critic_launch.py','net_scene_launch.py',
                'exploration_controller_bootstrap.py','nav2_goal_guard.py','consumer_trace.py',
                '../workspace/src/merge_map/merge_map/merge_map.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Shared navigation map producer and consumers must be source-bound')
        if navigation_shared_map['revision'] == ACTIVE_ROUTE_VERSION and not {
                'active_route_guard.py',
                '../workspace/src/multi_robot_exploration/multi_robot_exploration/allocation.py',
                }.issubset(net['adapter_sha256']):
            raise ValueError('Active Nav2 route guard and allocator must be source-bound')
    navigation_seed_route = net.get('navigation_seed_route')
    if navigation_seed_route is not None:
        if (not direct_reference or navigation_shared_map != {'revision': ACTIVE_ROUTE_VERSION}
                or navigation_seed_route != {'revision': SEED_ROUTE_VERSION}
                or '../workspace/gz01/seed_connection_ros.py' not in net['adapter_sha256']):
            raise ValueError('Approved seed routing requires the source-bound A0 active-route revision')
    navigation_intent = net.get('navigation_intent')
    if navigation_intent is not None:
        from shared_frontier_reservation import VERSION as INTENT_VERSION, CONTRACT_FILE as INTENT_CONTRACT, load_contract as load_intent_contract
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_controller != {'revision': 'dwb-padded-footprint-obstacle-prevention-v1'}
                or navigation_intent != {'revision': INTENT_VERSION}
                or ready.get('joint_participation') is not True
                or ready.get('joint_assignment_rule') != 'maximum-participation-v1'):
            raise ValueError('Shared frontier reservations require explicit footprint/maxparticipation literalA0')
        if not {'shared_frontier_reservation.py', INTENT_CONTRACT,
                'exploration_controller_bootstrap.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Shared frontier helper/contract/bootstrap must be source-bound')
        load_intent_contract(navigation_intent['revision'])
    navigation_goal_checker = net.get('navigation_goal_checker')
    if navigation_goal_checker is not None:
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_controller != {'revision': 'dwb-padded-footprint-obstacle-prevention-v1'}
                or navigation_intent is not None
                or navigation_goal_checker != {'revision': 'xy-position-goal-checker-v1'}):
            raise ValueError('Position goal checker requires explicit footprint literalA0 without frontier reservations')
        if not {'nav2_position_goal_launch.py',
                'config/NAVIGATION_POSITION_GOAL_CHECKER_V1.json'}.issubset(net['adapter_sha256']):
            raise ValueError('Position goal checker launch/contract must be source-bound')
    navigation_pair_coordination = net.get('navigation_pair_coordination')
    if navigation_pair_coordination is not None:
        from mixed_frontier_pairs import VERSION as PAIR_VERSION, CONTRACT_FILE as PAIR_CONTRACT, load_contract as load_pair_contract
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_goal_checker != {'revision': 'xy-position-goal-checker-v1'}
                or navigation_intent is not None
                or navigation_pair_coordination != {'revision': PAIR_VERSION}
                or ready.get('joint_participation') is not True
                or ready.get('joint_assignment_rule') != 'maximum-participation-v1'):
            raise ValueError('Mixed frontier pairs require explicit Position/maxparticipation literalA0 without intent lease')
        if not {'mixed_frontier_pairs.py', PAIR_CONTRACT,
                'exploration_controller_bootstrap.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Mixed frontier helper/contract/bootstrap must be source-bound')
        load_pair_contract(navigation_pair_coordination['revision'])
    navigation_nominal_budget = net.get('navigation_nominal_budget')
    if navigation_nominal_budget is not None:
        from nominal_goal_budget import VERSION as BUDGET_VERSION, CONTRACT_FILE as BUDGET_CONTRACT, load_contract as load_budget_contract
        if (net.get('execution_profile') not in ROS_LOCAL_NAV_PROFILE_IDS or not direct_reference
                or navigation_goal_checker != {'revision': 'xy-position-goal-checker-v1'}
                or navigation_intent is not None or navigation_pair_coordination is not None
                or navigation_nominal_budget != {'revision': BUDGET_VERSION}
                or ready.get('joint_participation') is not True
                or ready.get('joint_assignment_rule') != 'maximum-participation-v1'):
            raise ValueError('Nominal goal budget requires fixed Position/maxparticipation literalA0 without lease or mixedpair')
        if not {'nominal_goal_budget.py', BUDGET_CONTRACT, 'fixed_startup.py',
                'exploration_controller_bootstrap.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Nominal budget helper/contract/fixed gate/bootstrap must be source-bound')
        load_budget_contract(navigation_nominal_budget['revision'])
    if net.get('execution_profile') == A0_CADENCE_PROFILE_ID:
        from execution_profile import load_profile
        cadence_profile=load_profile(A0_CADENCE_PROFILE_ID)
        required_navigation={
            'navigation_progress':'owned-goal-source-odom-progress-v1',
            'navigation_recovery':'followpath-context-backup-v2',
            'navigation_peer_geometry':'peer-body-postfilter-inflation-v3',
            'navigation_planner':'smac2d-floor-planner-v4',
            'spawn_reply_qos':'gazebo-spawn-reply-maxblocking1s-v1',
            'navigation_controller':'dwb-padded-footprint-obstacle-prevention-v1',
            'navigation_goal_checker':'xy-position-goal-checker-v1'}
        if (not direct_reference or net.get('ros_delay')!={'condition':'A0','one_way_wall_ms':None}
                or any(net.get(key)!={'revision':revision} for key,revision in required_navigation.items())
                or any(net.get(key) is not None for key in
                    ('navigation_intent','navigation_pair_coordination','navigation_nominal_budget'))
                or ready.get('joint_participation') is not True
                or ready.get('joint_assignment_rule')!='maximum-participation-v1'
                or ready.get('decision_limit')!=130
                or ready.get('startup_contract')!=cadence_profile['startup_contract']):
            raise ValueError('New cadence requires exact literalA0 Position+FP, original130ceiling and its46slot contract; budget/lease/pair disabled')
    representative_diagnostic=net.get('navigation_representative_diagnostic')
    if representative_diagnostic is not None:
        from representative_diagnostic import VERSION as DIAGNOSTIC_VERSION, CONTRACT_FILE as DIAGNOSTIC_CONTRACT, load_contract as load_diagnostic_contract
        if (net.get('execution_profile')!=A0_CADENCE_PROFILE_ID
                or representative_diagnostic!={'revision':DIAGNOSTIC_VERSION}
                or ready.get('diagnostic_only') is not True or ready.get('performance_cohort') is not False):
            raise ValueError('Representative observation requires explicit current cadence nonperformance diagnostic')
        if not {'representative_diagnostic.py',DIAGNOSTIC_CONTRACT,
                'exploration_controller_bootstrap.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Representative observation helper/contract/bootstrap must be source-bound')
        load_diagnostic_contract(representative_diagnostic['revision'])
    frontier_representative=net.get('navigation_frontier_representative')
    if frontier_representative is not None:
        from frontier_representative import VERSION as FRONTIER_VERSION, CONTRACT_FILE as FRONTIER_CONTRACT, load_contract as load_frontier_contract
        if (net.get('execution_profile')!=A0_CADENCE_PROFILE_ID
                or frontier_representative!={'revision':FRONTIER_VERSION}
                or representative_diagnostic is not None or ready.get('diagnostic_only') is True):
            raise ValueError('Frontier representative requires current cadence behavior with diagnostic capture disabled')
        if not {'frontier_representative.py',FRONTIER_CONTRACT,
                'exploration_controller_bootstrap.py'}.issubset(net['adapter_sha256']):
            raise ValueError('Frontier representative helper/contract/bootstrap must be source-bound')
        load_frontier_contract(frontier_representative['revision'])
    startup_match_witness=net.get('startup_match_witness')
    if startup_match_witness is not None:
        witness_contract_path=HERE/'../local-runs/direct-nav-startup-match-diagnostic-20261117/WITNESS_CONTRACT.json'
        witness_contract=json.loads(witness_contract_path.read_text())
        if (startup_match_witness!={'revision':witness_contract['revision']}
                or net.get('execution_profile')!=A0_CADENCE_PROFILE_ID
                or ready.get('mode')!='stationary_only' or ready.get('stop_diagnostic') is not False
                or ready.get('phase_probe') is not False or ready.get('gzserver_batch_gdb') is not False
                or ready.get('diagnostic_only') is not True or ready.get('performance_cohort') is not False
                or representative_diagnostic is not None or frontier_representative is not None):
            raise ValueError('Spawn match witness requires exact stationary-only nonperformance cadence startup with noHQ selector/diagnostic')
        if not set(witness_contract['required_adapter_paths']).issubset(net['adapter_sha256']):
            raise ValueError('Spawn match witness source/contract/ELF must be explicitly bound')
        if any(os.environ.get(k) for k in witness_contract['no_overwrite']):
            raise ValueError('Existing preload/audit configuration requires separate review')
    for relative,expected in net["adapter_sha256"].items():
        if frozen.sha(HERE/relative)!=expected:raise ValueError("Transport adapter changed: "+relative)
    revision=net.get("common_execution_revision","net01e-common-v2")
    if net.get('execution_profile') in REPAIR_PROFILE_IDS and revision!='nav2-simclock-common-v1':
        raise ValueError('Exploration repair120 requires its explicit Nav2 sim-clock revision')
    if revision not in ("net01e-common-v2","static-footprint-common-v1","nav2-simclock-common-v1"):
        raise ValueError("Unreviewed common execution revision")
    if revision in ("static-footprint-common-v1","nav2-simclock-common-v1"):
        relative="../net01e/followup02/static_footprint_launch.py"
        if net["adapter_sha256"].get(relative)!=frozen.sha(HERE/relative):
            raise ValueError("Admission must bind the candidate launch entry")
    if revision=="nav2-simclock-common-v1":
        relative="nav2_simclock_launch.py"
        if net["adapter_sha256"].get(relative)!=frozen.sha(HERE/relative):
            raise ValueError("Admission must bind the explicit Nav2 sim-clock revision")
    os.environ["NET01_COMMON_EXECUTION_REVISION"]=revision
    if representative_diagnostic is not None:
        os.environ['NET01_REPRESENTATIVE_DIAGNOSTIC_REVISION']=representative_diagnostic['revision']
    else:
        os.environ.pop('NET01_REPRESENTATIVE_DIAGNOSTIC_REVISION',None)
    if frontier_representative is not None:
        os.environ['NET01_FRONTIER_REPRESENTATIVE_REVISION']=frontier_representative['revision']
    else:
        os.environ.pop('NET01_FRONTIER_REPRESENTATIVE_REVISION',None)
    if startup_match_witness is not None:
        os.environ['NET01_SPAWN_MATCH_WITNESS_CONTRACT']=str(witness_contract_path.resolve())
    else:
        os.environ.pop('NET01_SPAWN_MATCH_WITNESS_CONTRACT',None)
    case=Path(ready["case_path"]);case.parent.mkdir(parents=True,exist_ok=True)
    used=case.with_name(case.name+".admission-used.json")
    with used.open("x") as stream:json.dump(dict(ready_path=str(args.ready.resolve()),
        ready_sha256=frozen.sha(args.ready),boot_start_utc=datetime.now(timezone.utc).isoformat(),
        case=str(case),no_implicit_retry=True),stream,indent=2)
    os.environ.update(ROS_DOMAIN_ID="92",TURTLEBOT3_MODEL="waffle",
        GAZEBO_MASTER_URI="http://127.0.0.1:11692",GAZEBO_MODEL_DATABASE_URI="",
        DISPLAY=":92",QT_QPA_PLATFORM="offscreen",LIBGL_ALWAYS_SOFTWARE="1",
        PYTHONDONTWRITEBYTECODE="1",GZ01_CASE=str(case),NET01_MODE=net["mode"],
        NET01_SESSION_ID=str(net["session_id"]),NET01_SOCKET=net["socket_container"])
    os.environ['NET01_DISPATCH_PROFILE']='1' if net.get('dispatch_profile',False) else '0'
    os.environ['NET01_MAIN_THREAD_SAMPLE']='1' if net.get('main_thread_sample',False) else '0'
    os.environ['NET01_CONTROL_TRACE']='1' if net.get('control_trace',False) else '0'
    os.environ['NET01_EXECUTION_PROFILE']=net.get('execution_profile','')
    if navigation_progress is not None:
        os.environ['NET01_NAVIGATION_PROGRESS_REVISION'] = navigation_progress['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_PROGRESS_REVISION', None)
    if navigation_recovery is not None:
        os.environ['NET01_NAVIGATION_RECOVERY_REVISION'] = navigation_recovery['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_RECOVERY_REVISION', None)
    if navigation_peer_geometry is not None:
        os.environ['NET01_NAVIGATION_PEER_GEOMETRY_REVISION'] = navigation_peer_geometry['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_PEER_GEOMETRY_REVISION', None)
    if navigation_planner is not None:
        os.environ['NET01_NAVIGATION_PLANNER_REVISION'] = navigation_planner['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_PLANNER_REVISION', None)
    if spawn_reply_qos is not None:
        os.environ['NET01_SPAWN_REPLY_QOS_REVISION'] = spawn_reply_qos['revision']
    else:
        os.environ.pop('NET01_SPAWN_REPLY_QOS_REVISION', None)
    if navigation_controller is not None:
        os.environ['NET01_NAVIGATION_CONTROLLER_REVISION'] = navigation_controller['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_CONTROLLER_REVISION', None)
    if navigation_shared_map is not None:
        os.environ[SHARED_MAP_ENV] = navigation_shared_map['revision']
    else:
        os.environ.pop(SHARED_MAP_ENV, None)
    if navigation_seed_route is not None:
        os.environ[SEED_ROUTE_ENV] = navigation_seed_route['revision']
    else:
        os.environ.pop(SEED_ROUTE_ENV, None)
    if navigation_intent is not None:
        os.environ['NET01_FRONTIER_INTENT_REVISION'] = navigation_intent['revision']
    else:
        os.environ.pop('NET01_FRONTIER_INTENT_REVISION', None)
    if navigation_goal_checker is not None:
        os.environ['NET01_NAVIGATION_GOAL_CHECKER_REVISION'] = navigation_goal_checker['revision']
    else:
        os.environ.pop('NET01_NAVIGATION_GOAL_CHECKER_REVISION', None)
    if navigation_pair_coordination is not None:
        os.environ['NET01_MIXED_FRONTIER_PAIR_REVISION'] = navigation_pair_coordination['revision']
    else:
        os.environ.pop('NET01_MIXED_FRONTIER_PAIR_REVISION', None)
    if navigation_nominal_budget is not None:
        os.environ['NET01_NOMINAL_GOAL_BUDGET_REVISION'] = navigation_nominal_budget['revision']
    else:
        os.environ.pop('NET01_NOMINAL_GOAL_BUDGET_REVISION', None)
    os.environ['NET01_DIRECT_REFERENCE']='1' if direct_reference else '0'
    os.environ['NET01_CONTROLLER_EXIT_ADAPTER']=controller_exit_adapter
    os.environ['NET01_RAW_DESTINATION']='1' if raw_destination else '0'
    os.environ['NET01_ADAPTER_QOS_EVENTS']=qos_events
    os.environ['NET01_CAPTURE_CENTRAL_MAP']='1' if capture else '0'
    if net.get('execution_profile') in ROS_LOCAL_NAV_PROFILE_IDS:
        os.environ['NET01_ROS_DELAY_WALL_MS']=str(0 if direct_reference else net['ros_delay']['one_way_wall_ms'])
    else:os.environ.pop('NET01_ROS_DELAY_WALL_MS',None)
    if net.get('execution_profile') == PHYSICS_DELAY_PROFILE_ID:
        os.environ['NET01_PHYSICAL_DELAY_NS']=str(net['physical_delay']['delay_physical_ns'])
    else:os.environ.pop('NET01_PHYSICAL_DELAY_NS',None)
    if direct_reference:
        os.environ['NET01_A0_SAFETY_SOCKET']=str(case/'a0-safety.sock')
    if controlled is not None:
        if os.environ.get('NET01_TIME_CONTROL')!='1' or not Path(os.environ['NET01_TIME_CONTROL_PLUGIN']).is_file():
            raise ValueError('Controlled host artifact mounts/sidecars missing')
    os.environ["GAZEBO_MODEL_PATH"]="/project/assets/gazebo_models:"+os.environ.get("GAZEBO_MODEL_PATH","")
    os.environ.pop("GZ01_HOST_GDB",None)
    if ready.get("gzserver_batch_gdb",False):os.environ["GZ01_BATCH_GDB"]="1"
    else:os.environ.pop("GZ01_BATCH_GDB",None)
    result=dict(start_utc=datetime.now(timezone.utc).isoformat(),native_exit=None,outer_timeout=False,cleanup_timeout=False)
    xvfb=runner=None
    try:
        with case.with_name(case.name+".xvfb.log").open("x") as stream:
            xvfb=subprocess.Popen(["Xvfb",":92","-screen","0","1280x800x24","-nolisten","tcp"],stdout=stream,stderr=subprocess.STDOUT)
            # Same-host CLOCK_MONOTONIC survives the rootfs; these are the
            # existing work/host bounds, not new phase budgets.
            work_deadline_ns=time.monotonic_ns()+int(ready["outer_wall"]*1e9)
            os.environ['NET01_RUNNER_WORK_DEADLINE_NS']=str(work_deadline_ns)
            os.environ['NET01_HOST_HARD_DEADLINE_NS']=str(
                work_deadline_ns if args.host_hard_deadline_ns is None else args.host_hard_deadline_ns)
            os.environ['NET01_RUNNER_CLEANUP_WALL_S']=str(ready['cleanup_wall'])
            runner=subprocess.Popen([sys.executable,"-B",str(HERE/"run_network_case.py"),"--ready",str(args.ready.resolve())],start_new_session=True)
            case.with_name(case.name+".owned-runner.json").write_text(json.dumps(dict(
                pid=runner.pid,case=str(case),marker="GZ01_CASE="+str(case))))
            try:result["native_exit"]=runner.wait(timeout=ready["outer_wall"])
            except subprocess.TimeoutExpired:
                result["outer_timeout"]=True;runner.send_signal(signal.SIGINT)
                try:result["native_exit"]=runner.wait(timeout=ready["cleanup_wall"])
                except subprocess.TimeoutExpired:
                    result["cleanup_timeout"]=True;frozen.kill_owned(case)
                    os.killpg(runner.pid,signal.SIGKILL);result["native_exit"]=runner.wait()
    finally:
        if xvfb is not None:
            xvfb.terminate()
            try:xvfb.wait(timeout=3)
            except subprocess.TimeoutExpired:xvfb.kill();xvfb.wait()
        result["end_utc"]=datetime.now(timezone.utc).isoformat()
        case.with_name(case.name+".boot-exit.json").write_text(json.dumps(result,indent=2))
    return 1 if result["outer_timeout"] or result["cleanup_timeout"] else result["native_exit"]


if __name__=="__main__":raise SystemExit(main())

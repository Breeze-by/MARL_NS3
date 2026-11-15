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
from execution_profile import SIM_BUSINESS_PROFILE_ID,BUSINESS60_PROFILE_IDS,SIM_BUSINESS_PROFILE_FILES,FIXED_START_PROFILE_IDS,FIXED_START_ADAPTER_FILES,REPAIR120_PROFILE_ID,REPAIR_ADAPTER_FILES,REPAIR_PROFILE_IDS,COMPARISON40_PROFILE_IDS,COMPARISON_PROFILE_IDS,COMPARISON_ADAPTER_FILES,ROS_DELAY_PROFILE_ID,ROS_DELAY_V1_PROFILE_ID,ROS_DELAY_V2_PROFILE_ID,ROS_DELAY_ADAPTER_FILES

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
        if net.get('execution_profile') == ROS_DELAY_PROFILE_ID:
            required.update(ROS_DELAY_ADAPTER_FILES)
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
    if net.get('execution_profile') == ROS_DELAY_PROFILE_ID:
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
    os.environ['NET01_DIRECT_REFERENCE']='1' if direct_reference else '0'
    os.environ['NET01_CONTROLLER_EXIT_ADAPTER']=controller_exit_adapter
    os.environ['NET01_RAW_DESTINATION']='1' if raw_destination else '0'
    os.environ['NET01_ADAPTER_QOS_EVENTS']=qos_events
    os.environ['NET01_CAPTURE_CENTRAL_MAP']='1' if capture else '0'
    if net.get('execution_profile') == ROS_DELAY_PROFILE_ID:
        os.environ['NET01_ROS_DELAY_WALL_MS']=str(0 if direct_reference else net['ros_delay']['one_way_wall_ms'])
    else:os.environ.pop('NET01_ROS_DELAY_WALL_MS',None)
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

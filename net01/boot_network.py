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

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/"workspace/gz01"),str(HERE.parent/"workspace/src/multi_robot_exploration")]
import boot as frozen


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ready",type=Path,required=True)
    parser.add_argument("--host-hard-deadline-ns",type=int)
    args=parser.parse_args()
    ready=frozen.validate_ready(args.ready)
    net=ready["network"]
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
        if (controller_exit_adapter!='net01e-graceful-v1' or net.get('execution_profile')!=
                'controlled1000-clock100-q10ms-pace20-raster-simhealth'):
            raise ValueError('Common raw destination requires the reviewed graceful/pace20 version')
        required={'../net01e/followup01/'+name for name in
            ('production_gateway.py','production_host.py','PRODUCTION_ADMISSION.json','raw_destination_wire.py')}
        required.add('config/EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE20_RASTER_SIMHEALTH.json')
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
    if bounds not in allowed_bounds:
        raise ValueError("NET-01 fixed bounds changed")
    qos_events=net.get('adapter_qos_events','sdk-default')
    if qos_events not in ('sdk-default','warning-free-v1'):
        raise ValueError('Unknown adapter QoS event version')
    capture=net.get('capture_central_map',False)
    if type(capture) is not bool or (capture and direct_reference):
        raise ValueError('Central map capture requires an explicit A1/B/C business wire')
    if net["mode"] not in ("A","B","C") or ready["arm"]!="rl":raise ValueError("Only fixed A/B/C RL")
    for relative,expected in net["adapter_sha256"].items():
        if frozen.sha(HERE/relative)!=expected:raise ValueError("Transport adapter changed: "+relative)
    revision=net.get("common_execution_revision","net01e-common-v2")
    if revision not in ("net01e-common-v2","static-footprint-common-v1"):
        raise ValueError("Unreviewed common execution revision")
    if revision=="static-footprint-common-v1":
        relative="../net01e/followup02/static_footprint_launch.py"
        if net["adapter_sha256"].get(relative)!=frozen.sha(HERE/relative):
            raise ValueError("Admission must bind the candidate launch entry")
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

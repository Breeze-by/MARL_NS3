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
from time_control_runtime import controlled_config

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/"workspace/gz01"),str(HERE.parent/"workspace/src/multi_robot_exploration")]
import boot as frozen


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ready",type=Path,required=True)
    args=parser.parse_args()
    ready=frozen.validate_ready(args.ready)
    net=ready["network"]
    if ready.get("authorized_net01_execution") is not True:raise ValueError("No NET-01 root admission")
    controlled=controlled_config(ready)
    if (ready["sim_budget"],ready["startup_wall"],ready["autonomous_wall"],ready["outer_wall"],ready["cleanup_wall"])!=((120 if controlled is not None else 180),180,420,900,90):
        raise ValueError("NET-01 fixed bounds changed")
    if net["mode"] not in ("A","B","C") or ready["arm"]!="rl":raise ValueError("Only fixed A/B/C RL")
    for relative,expected in net["adapter_sha256"].items():
        if frozen.sha(HERE/relative)!=expected:raise ValueError("Transport adapter changed: "+relative)
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
    os.environ['NET01_CONTROL_TRACE']='1' if net.get('control_trace',False) else '0'
    os.environ['NET01_EXECUTION_PROFILE']=net.get('execution_profile','')
    if controlled is not None:
        if os.environ.get('NET01_TIME_CONTROL')!='1' or not Path(os.environ['NET01_TIME_CONTROL_PLUGIN']).is_file():
            raise ValueError('Controlled host artifact mounts/sidecars missing')
    os.environ["GAZEBO_MODEL_PATH"]="/project/assets/gazebo_models:"+os.environ.get("GAZEBO_MODEL_PATH","")
    os.environ.pop("GZ01_BATCH_GDB",None);os.environ.pop("GZ01_HOST_GDB",None)
    result=dict(start_utc=datetime.now(timezone.utc).isoformat(),native_exit=None,outer_timeout=False,cleanup_timeout=False)
    xvfb=runner=None
    try:
        with case.with_name(case.name+".xvfb.log").open("x") as stream:
            xvfb=subprocess.Popen(["Xvfb",":92","-screen","0","1280x800x24","-nolisten","tcp"],stdout=stream,stderr=subprocess.STDOUT)
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

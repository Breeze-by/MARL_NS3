"""Host-only owner for one native hub and one reviewed rootfs experiment.

Does not start Gazebo without both existing GZ and NET authorizations. No host
interface/route/capability changes; no retries; only its own process groups end.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
PHASE=REPO.parent


def terminate_recorded(case):
    """Timeout-only teardown, exact recorded PGID plus original case marker."""
    files=[case/"owned_processes.jsonl",case.with_name(case.name+".owned-runner.json")]
    expected=("GZ01_CASE=/mnt/"+str(case.relative_to(REPO))).encode()
    for path in files:
        if not path.exists():continue
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            pid=row["pid"];proc=Path("/proc")/str(pid)
            try:
                if expected in (proc/"environ").read_bytes().split(b"\0") and os.getpgid(pid)==pid:
                    os.killpg(pid,signal.SIGKILL)
            except (FileNotFoundError,ProcessLookupError):pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ready",type=Path,required=True)
    args=parser.parse_args();ready=json.loads(args.ready.read_text())
    if ready.get("authorized_net01_execution") is not True or ready.get("authorized_gz01_execution") is not True:
        raise ValueError("Root has not admitted this specific NET/Gazebo case")
    net=ready["network"]
    case=REPO/ready["case_relative_phase"]
    outcome=case.with_name(case.name+".host-exit.json")
    if case.exists() or outcome.exists():raise FileExistsError("Single-use case already attempted")
    case.parent.mkdir(parents=True,exist_ok=True)
    socket=REPO/net["socket_relative_repo"]
    evidence=REPO/net["hub_output_relative_repo"]
    native=PHASE/"build/network-full-payload/net01-payload"
    command=[sys.executable,"-B",str(HERE/"tools/packet_hub.py"),"--socket",str(socket),
        "--native",str(native),"--output",str(evidence),"--profile",("C" if net["mode"]=="C" else "B"),
        "--wall","1000","--clock-source","gazebo"]
    result=dict(start_utc=datetime.now(timezone.utc).isoformat(),hub_argv=command,runner_exit=None)
    hub=runner=None
    hub_log=case.with_name(case.name+".hub.log").open("x")
    try:
        hub=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=hub_log,text=True,start_new_session=True)
        readable,_,_=select.select([hub.stdout],[],[],10)
        if not readable:raise TimeoutError("Owned native IPC startup did not complete in 10wall")
        line=hub.stdout.readline();hub_log.write(line);hub_log.flush()
        if line.strip()!="IPC_LISTENING "+str(socket):raise RuntimeError("Owned native hub failed before ROS/Gazebo")
        relative=args.ready.resolve().relative_to(REPO)
        with case.with_name(case.name+".native.log").open("x") as log:
            runner=subprocess.Popen(["bash",str(HERE/"ros-python.sh"),"/mnt/net01/boot_network.py",
                "--ready","/mnt/"+str(relative)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:result["runner_exit"]=runner.wait(timeout=1000)
            except subprocess.TimeoutExpired:
                result["host_timeout"]=True;os.killpg(runner.pid,signal.SIGINT)
                try:result["runner_exit"]=runner.wait(timeout=100)
                except subprocess.TimeoutExpired:
                    terminate_recorded(case)
                    os.killpg(runner.pid,signal.SIGKILL);result["runner_exit"]=runner.wait()
        try:result["hub_exit"]=hub.wait(timeout=15)
        except subprocess.TimeoutExpired:
            result["hub_timeout_after_runner"]=True;os.killpg(hub.pid,signal.SIGINT)
            try:result["hub_exit"]=hub.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(hub.pid,signal.SIGKILL);result["hub_exit"]=hub.wait()
    except BaseException as error:
        result["error"]=repr(error)
        raise
    finally:
        for process in (runner,hub):
            if process is not None and process.poll() is None:
                if process is runner:terminate_recorded(case)
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        hub_log.close();result["end_utc"]=datetime.now(timezone.utc).isoformat()
        outcome.write_text(json.dumps(result,indent=2))
    saved={}
    for name in ("network-gateway-saved.json","bound-mask-recording-saved.json","peer-recording-saved.json"):
        path=case/name
        saved[name]=json.loads(path.read_text()) if path.exists() else dict(saved=False,reason="missing")
    integrity=all(row["saved"] for row in saved.values()) and result["runner_exit"]==0 and result["hub_exit"]==0
    case.with_name(case.name+".network-integrity.json").write_text(json.dumps(dict(
        record_saves=saved,network_run_integrity=integrity,
        scope="Runtime/source/stop remain separately in original result; no metric PASS implied"),indent=2))
    return 0 if integrity else 1


if __name__=="__main__":raise SystemExit(main())

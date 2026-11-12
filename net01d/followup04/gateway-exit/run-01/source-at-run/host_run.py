"""Host-only owner for one native hub and one reviewed rootfs experiment.

Does not start Gazebo without both existing GZ and NET authorizations. No host
interface/route/capability changes; no retries; only its own process groups end.
"""
import argparse
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
from time_control_runtime import ControlledRuntime,controlled_config

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
PHASE=REPO.parent


def capture_native_load(hub,native,libraries,expected_names,case):
    """One post-READY read of the actual Hub child, before ROS/Gazebo starts."""
    children=(Path('/proc')/str(hub.pid)/'task'/str(hub.pid)/'children').read_text().split()
    matches=[]
    for pid in children:
        proc=Path('/proc')/pid
        argv=[word.decode() for word in (proc/'cmdline').read_bytes().split(b'\0') if word]
        if argv and Path(argv[0]).resolve()==native.resolve():matches.append((proc,argv))
    if len(matches)!=1:raise RuntimeError('Actual owned native child missing/ambiguous')
    proc,argv=matches[0]
    maps=(proc/'maps').read_text()
    case.with_name(case.name+'.native.maps.txt').write_text(maps)
    paths={row.split(None,5)[5] for row in maps.splitlines()
        if len(row.split(None,5))==6 and Path(row.split(None,5)[5]).name.startswith('libns3.40-')}
    status=(proc/'status').read_text()
    parent=int(next(line.split()[1] for line in status.splitlines() if line.startswith('PPid:')))
    exe=Path(os.readlink(proc/'exe'))
    row=dict(pid=int(proc.name),hub_pid=hub.pid,parent_pid=parent,argv=argv,exe=str(exe),
        start_ticks=int((proc/'stat').read_text().rsplit(')',1)[1].split()[19]),
        mapped_ns3_paths=sorted(paths),expected_root=str(libraries),
        exact_names={Path(p).name for p in paths}==set(expected_names),
        all_in_expected_root=bool(paths) and all(Path(p).resolve().parent==libraries for p in paths),
        actual_exe_matches=exe.resolve()==native.resolve(),actual_parent_is_Hub=parent==hub.pid)
    case.with_name(case.name+'.native-load.json').write_text(json.dumps(row,indent=2)+'\n')
    if not all(row[key] for key in ('exact_names','all_in_expected_root','actual_exe_matches','actual_parent_is_Hub')):
        raise RuntimeError('Actual native ELF/library load proof failed before ROS/Gazebo')
    return row


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
    direct_reference=net.get("direct_reference",False)
    if type(direct_reference) is not bool:
        raise ValueError("direct_reference must be an explicit JSON bool")
    if direct_reference and (net["mode"]!="A" or controlled_config(ready) is None):
        raise ValueError("A0 requires mode A and the existing controlled-time profile")
    case=REPO/ready["case_relative_phase"]
    outcome=case.with_name(case.name+".host-exit.json")
    if case.exists() or outcome.exists():raise FileExistsError("Single-use case already attempted")
    case.parent.mkdir(parents=True,exist_ok=True)
    socket=REPO/net["socket_relative_repo"]
    evidence=REPO/net["hub_output_relative_repo"]
    native=PHASE/net["native_identity"]["binary"]["relative_phase"]
    runtime=net.get('native_runtime')
    native_env=None
    if runtime is not None:
        libraries=Path(runtime['library_directory']).resolve(strict=True)
        native_env=dict(os.environ,LD_LIBRARY_PATH=str(libraries))
        for name in ('LD_PRELOAD','LD_AUDIT'):native_env.pop(name,None)
    bounded180=controlled_config(ready) is not None and ready['sim_budget']==180
    ledger_mode=net.get('native_ledger_mode','serial')
    if ledger_mode not in ('serial','session-ram-v1'):
        raise ValueError('Unknown reviewed native ledger mode')
    session_ram=ledger_mode=='session-ram-v1'
    if session_ram and not bounded180:
        raise ValueError('Session RAM candidate requires the existing bounded180 host owner')
    runner_wall=ready['outer_wall']+ready['cleanup_wall']+10 if bounded180 else 1000
    # Check the actual executable/header before any native model is started.
    for key,path in (("binary",native),("generated_header",PHASE/net["native_identity"]["generated_header"]["relative_phase"])):
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=net["native_identity"][key]["sha256"]:
            raise ValueError("Reviewed native "+key+" changed")
    command=[sys.executable,"-B",str(HERE/"tools/packet_hub.py"),"--socket",str(socket),
        "--native",str(native),"--output",str(evidence),"--profile",("C" if net["mode"]=="C" else "B"),
        "--wall",str(runner_wall+20 if bounded180 else 1000),"--clock-source","gazebo"]
    if net.get('control_trace',False):command.append('--control-trace')
    native_transport=net.get('native_transport','udp')
    if native_transport not in ('udp','tcp-v1','tcp-mtu-v2'):raise ValueError('Unknown reviewed native transport')
    command += ['--native-transport',native_transport]
    if net.get('native_evidence_ram') is not None:
        command += ['--native-evidence-ram',net['native_evidence_ram']]
    result=dict(start_utc=datetime.now(timezone.utc).isoformat(),hub_argv=command,runner_exit=None,
        runner_outer_wait_wall_s=runner_wall)
    if runtime is not None:result['native_loader_environment']=dict(LD_LIBRARY_PATH=str(libraries),
        LD_PRELOAD='UNSET',LD_AUDIT='UNSET')
    hub=runner=None
    controlled=ControlledRuntime(ready,REPO,case) if controlled_config(ready) is not None else None
    hub_log=case.with_name(case.name+".hub.log").open("x")
    host_begin=time.monotonic()
    host_deadline=host_begin+runner_wall if bounded180 else None
    if session_ram:command += ['--native-ledger-mode',ledger_mode,
        '--finalize-hard-deadline-ns',str(int(host_deadline*1e9))]
    def remaining(limit):
        return limit if host_deadline is None else max(0.,min(limit,host_deadline-time.monotonic()))
    try:
        startup_deadline=time.monotonic()+10
        if controlled is not None:
            controlled.start(startup_deadline)
            command += ['--step-observer',str(controlled.ack_relative)]
        hub=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=hub_log,text=True,start_new_session=True,env=native_env,
            **({'cwd':str(REPO)} if controlled is not None else {}))
        readable,_,_=select.select([hub.stdout],[],[],
            10 if controlled is None else max(0.,startup_deadline-time.monotonic()))
        if not readable:raise TimeoutError("Owned native IPC startup did not complete in 10wall")
        line=hub.stdout.readline();hub_log.write(line);hub_log.flush()
        if line.strip()!="IPC_LISTENING "+str(socket):raise RuntimeError("Owned native hub failed before ROS/Gazebo")
        if runtime is not None:
            result['native_load']=capture_native_load(hub,native,libraries,runtime['expected_ns3_names'],case)
        relative=args.ready.resolve().relative_to(REPO)
        with case.with_name(case.name+".native.log").open("x") as log:
            runner_command=(["bash",str(HERE/"ros-python.sh"),"/mnt/net01/boot_network.py",
                "--ready","/mnt/"+str(relative)] if controlled is None else
                controlled.python_command(['/mnt/net01/boot_network.py','--ready','/mnt/'+str(relative)]+
                    ([] if host_deadline is None else
                        ['--host-hard-deadline-ns',str(int(host_deadline*1e9))])))
            runner=subprocess.Popen(runner_command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:result["runner_exit"]=runner.wait(timeout=remaining(runner_wall))
            except subprocess.TimeoutExpired:
                result["host_timeout"]=True
                if bounded180:
                    terminate_recorded(case)
                    os.killpg(runner.pid,signal.SIGKILL);result["runner_exit"]=runner.wait()
                else:
                    os.killpg(runner.pid,signal.SIGINT)
                    try:result["runner_exit"]=runner.wait(timeout=100)
                    except subprocess.TimeoutExpired:
                        terminate_recorded(case)
                        os.killpg(runner.pid,signal.SIGKILL);result["runner_exit"]=runner.wait()
        finalize_deadline=None
        hub_wait=15
        if session_ram:
            marker=evidence/'poststop-finalize.json'
            # END is normally read before the Gateway and runner exit. If not
            # yet observed, this earlier host90s bound cannot add a second90s.
            hub_wait=90
            if marker.exists():
                finalize=json.loads(marker.read_text());result['poststop_finalize']=finalize
                finalize_deadline=finalize['deadline_monotonic_ns']/1e9
                hub_wait=max(0.,finalize_deadline-time.monotonic())
        try:result["hub_exit"]=hub.wait(timeout=remaining(hub_wait))
        except subprocess.TimeoutExpired:
            result["hub_timeout_after_runner"]=True
            os.killpg(hub.pid,signal.SIGKILL if session_ram else signal.SIGINT)
            try:result["hub_exit"]=hub.wait(timeout=0 if session_ram else remaining(5))
            except subprocess.TimeoutExpired:os.killpg(hub.pid,signal.SIGKILL);result["hub_exit"]=hub.wait()
    except BaseException as error:
        result["error"]=repr(error)
        raise
    finally:
        for process in (runner,hub):
            if process is not None and process.poll() is None:
                if process is runner:terminate_recorded(case)
                os.killpg(process.pid,signal.SIGKILL if remaining(5)==0 else signal.SIGTERM)
                try:process.wait(timeout=remaining(5))
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        if controlled is not None and controlled.directory.exists():result['controlled_time']=controlled.close()
        hub_log.close();result["end_utc"]=datetime.now(timezone.utc).isoformat()
        result['host_wall_s']=time.monotonic()-host_begin
        if bounded180:result['host_force_escalation_wall_s']=runner_wall
        outcome.write_text(json.dumps(result,indent=2))
    saved={}
    save_names=["network-gateway-saved.json","bound-mask-recording-saved.json","peer-recording-saved.json"]
    if direct_reference:save_names.append("a0-direct-safety-saved.json")
    for name in save_names:
        path=case/name
        saved[name]=json.loads(path.read_text()) if path.exists() else dict(saved=False,reason="missing")
    path=case/"network-gateway-exit.json"
    gateway_exit=json.loads(path.read_text()) if path.exists() else dict(native_exit=None)
    cleanup=saved["network-gateway-saved.json"].get("cleanup",{})
    integrity=(all(row["saved"] for row in saved.values()) and result["runner_exit"]==0
        and result["hub_exit"]==0 and gateway_exit["native_exit"]==0
        and cleanup.get("resources_destroyed") is True and cleanup.get("end_frame_flushed") is True)
    if controlled is not None:integrity=integrity and result['controlled_time']['integrity']
    if direct_reference:
        actual=saved['a0-direct-safety-saved.json']
        integrity=integrity and actual.get('direct_reference') is True and \
            actual.get('business_wires_installed') is False and \
            actual.get('registered_owned_unknown_or_active')==0 and actual.get('safety_connections')==0
    case.with_name(case.name+".network-integrity.json").write_text(json.dumps(dict(
        record_saves=saved,gateway_exit=gateway_exit,network_run_integrity=integrity,
        scope="Runtime/source/stop remain separately in original result; no metric PASS implied"),indent=2))
    return 0 if integrity else 1


if __name__=="__main__":raise SystemExit(main())

"""Single-use <=30wall P1 diagnostic, not full-load P5 or Gazebo admission.

A1 is the original Gateway A queue with real native control/empty WiFi model.
No Policy/Nav2/Goal, no artificial health injection, no 89/95 capacity claim.
"""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
EXTERNAL=Path('/home/zhuyulab/ns3-workspace')
NATIVE=EXTERNAL/'net-01/build/followup03-release-portable-native/net01-payload'
BASELINE=EXTERNAL/'base-01-econ'
SITE=Path('/home/zhuyulab/.local/lib/python3.10/site-packages')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--arm',choices=('A1',),required=True)
    parser.add_argument('--case',choices=('health-profile-01',),required=True)
    parser.add_argument('--native',type=Path,default=NATIVE)
    parser.add_argument('--baseline',type=Path,default=BASELINE)
    args=parser.parse_args()
    # Explicit existing dependencies. Do not copy, rebuild or alias old binaries.
    if not args.native.is_absolute() or not args.native.is_file():raise FileNotFoundError(args.native)
    if not args.baseline.is_absolute() or not (args.baseline/'isolation/rootfs').is_dir():
        raise FileNotFoundError(args.baseline/'isolation/rootfs')
    base=REPO/'net01d/runs'/args.case
    base.mkdir(parents=True,exist_ok=False)
    for role in ('source','peer','gateway'):(base/role).mkdir()
    home=base/'runtime-home';home.mkdir()
    inner='/mnt/'+str(base.relative_to(REPO))
    started=time.monotonic();deadline=started+30.
    processes={};logs=[];forced=[];commands={};error=None;identities={}
    def ros(argv):
        return ['bwrap','--unshare-user','--uid','0','--gid','0','--die-with-parent',
            '--ro-bind',str(args.baseline/'isolation/rootfs'),'/', '--tmpfs','/tmp',
            '--bind',str(home),'/root','--ro-bind','/proc','/proc','--dev-bind','/dev','/dev',
            '--ro-bind','/sys','/sys','--ro-bind',str(args.baseline),'/project',
            '--bind',str(REPO),'/mnt','--chdir','/mnt','--ro-bind',str(SITE),'/tmp/rl02-python',
            '/usr/bin/env','-i','PATH=/usr/sbin:/usr/bin:/sbin:/bin','HOME=/root','LANG=C.UTF-8',
            'ROS_DOMAIN_ID=92','ROS_LOCALHOST_ONLY=1','RMW_IMPLEMENTATION=rmw_fastrtps_cpp',
            'PYTHONNOUSERSITE=1','PYTHONDONTWRITEBYTECODE=1','OPENBLAS_NUM_THREADS=1',
            'OMP_NUM_THREADS=1','MKL_NUM_THREADS=1',
            '/bin/bash','--noprofile','--norc','-c',
            'source /opt/ros/humble/setup.bash; source /project/workspace/install/setup.bash; '
            'export PYTHONPATH=/mnt:/mnt/net01:/mnt/workspace/gz01:/mnt/workspace/rl04:'
            '/mnt/workspace/rl02:/mnt/workspace/rl01:/mnt/workspace/src/multi_robot_exploration:'
            '/tmp/rl02-python:${PYTHONPATH:-}; exec python3 -B "$@"', 'bash',*argv]
    def launch(role,argv,marker=None):
        commands[role]=argv
        (base/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        err=(base/(role+'.stderr.txt')).open('x');logs.append(err)
        out=subprocess.PIPE if marker else (base/(role+'.stdout.txt')).open('x')
        if marker is None:logs.append(out)
        process=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True,text=True)
        processes[role]=process;identities[role]=dict(pid=process.pid,pgid=process.pid,argv=argv)
        (base/'owned-processes.json').write_text(json.dumps(identities,indent=2)+'\n')
        if marker:
            readable,_,_=select.select([process.stdout],[],[],max(0.,min(5.,deadline-time.monotonic())))
            line=process.stdout.readline() if readable else ''
            (base/(role+'.startup.txt')).write_text(line)
            if line.strip()!=marker:raise RuntimeError('Expected actual startup marker: '+marker)
        return process
    scope=dict(arm='A1',delivery='IDEAL-DIRECT-ADAPTER; original reliable Action installed but no Goal sent',
        source_window_wall_s=16,hard_wall_s=30,session_id=2026110912,
        roles=['coordinator','hub/native','peer','gateway','mock_physics','source'],
        profile='controlled1000-clock100-q10ms',source_clock_contract='frozen-source-clock',
        dispatch_profile=True,control_trace=True,guard='original actual C masks+health to R intake; unarmed',
        source_sizes=dict(map=[250,220],local_costmap=[200,200],bound_mask=[400,400]),
        source_rates='odom30sim + odomTF; wheel10sim both in same message; scanheader5sim; '
            'costmap strict ROS>.5 in5wall poll; map5wall period; correction50wall latest_scan+.2; '
            'feedback100wall; exactzero_cmd20wall; Peer masks/health10sim unchanged',
        missing_flows=[89,95],scope='P1 independent-source size/cadence approximation, not SLAM/full-system/P5',
        native=str(args.native),baseline=str(args.baseline),Gazebo=0,Nav2=0,Goal=0,NN=0,arm_guard=False)
    (base/'scope.json').write_text(json.dumps(scope,indent=2)+'\n')
    try:
        launch('coordinator',ros(['/mnt/net01/time_controller.py','--ack-socket',inner+'/step.sock',
            '--output',inner+'/time-controller.json','--session-id','2026110912',
            '--hold-file',inner+'/HOLD','--stop-file',inner+'/COORDINATOR_STOP']),
            'TIME_CONTROL_READY '+inner+'/step.sock')
        launch('hub',[sys.executable,'-B',str(REPO/'net01/tools/packet_hub.py'),
            '--socket',str(base/'wire.sock'),'--native',str(args.native),'--output',str(base/'hub'),
            '--profile','B','--wall','29','--clock-source','gazebo','--control-trace',
            '--step-observer',str(base/'step.sock')],'IPC_LISTENING '+str(base/'wire.sock'))
        children=Path('/proc')/str(processes['hub'].pid)/'task'/str(processes['hub'].pid)/'children'
        identities['native_children']=children.read_text().split()
        (base/'owned-processes.json').write_text(json.dumps(identities,indent=2)+'\n')
        role='/mnt/net01d/replay_roles.py';stop=inner+'/STOP'
        launch('peer',ros([role,'--role','peer','--directory',inner+'/peer','--stop-file',stop]))
        # Both roles start before bootstrap physical tokens can be granted.
        gateway=launch('gateway',ros([role,'--role','gateway','--directory',inner+'/gateway',
            '--stop-file',stop,'--mode','A']))
        launch('mock_physics',ros(['/mnt/net01/followup04/mock_physics.py',
            '--output',inner+'/mock-physics.json','--stop-file',stop]),'MOCK_PHYSICS_READY')
        # Gateway stdout is a file: its independent source waits on real DDS
        # gateway_state connected/anchor, as in the original source fixture.
        source=launch('source',ros([role,'--role','source','--directory',inner+'/source','--stop-file',stop]))
        source.wait(timeout=max(.01,deadline-time.monotonic()-6.))
        if source.returncode:raise RuntimeError('Source returned nonzero')
    except BaseException as exc:error=repr(exc)
    finally:
        (base/'HOLD').write_text('Fixture resource HOLD; not physical stop certification')
        while not (base/'HOLD.ack').exists() and time.monotonic()<deadline-3:
            if 'coordinator' not in processes or processes['coordinator'].poll() is not None:break
            time.sleep(.005)
        if not (base/'HOLD.ack').exists() and error is None:error='Actual resource HOLD not confirmed'
        (base/'STOP').write_text('Fixture owned resource close, no business state')
        for role in ('source','peer','gateway','mock_physics','hub'):
            process=processes.get(role)
            if process is None:continue
            try:process.wait(timeout=max(.01,deadline-time.monotonic()-1.))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();forced.append(role)
                if error is None:error='Hard bound forced own role: '+role
        (base/'COORDINATOR_STOP').write_text('After actual Hub/native exit')
        process=processes.get('coordinator')
        if process is not None:
            try:process.wait(timeout=max(.01,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();forced.append('coordinator')
                if error is None:error='Hard bound forced coordinator'
        result=dict(scope=scope,error=error,wall_s=time.monotonic()-started,
            exits={role:p.returncode for role,p in processes.items()},forced=forced,
            judgement='Process completion only; actual supply/health receipts/profile require offline review')
        (base/'process-exit.json').write_text(json.dumps(result,indent=2)+'\n')
        for log in logs:log.close()
    print(json.dumps(result),flush=True)
    return int(error is not None or any(p.returncode!=0 for p in processes.values()))


if __name__=='__main__':raise SystemExit(main())

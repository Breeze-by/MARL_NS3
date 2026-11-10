"""Single-use no-motion diagnostic; P1 16/30wall or P5 32/60wall.

A1 is the original Gateway A queue with real native control/empty WiFi model.
B uses the same source/roles and original actual V3 WiFi, with RAM evidence.
No real Policy/Nav2/Gazebo or artificial health injection. P1 has no Goals/89/95;
P5 adds controlled generated Action plus original merge/journal traffic.
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
    parser.add_argument('--stage',choices=('profile','full'),default='profile')
    parser.add_argument('--arm',choices=('A1','B'),required=True)
    parser.add_argument('--case',choices=('health-profile-01','health-profile-wifi-01',
        'full-load-local-01','full-load-wifi-01'),required=True)
    parser.add_argument('--native',type=Path,default=NATIVE)
    parser.add_argument('--baseline',type=Path,default=BASELINE)
    parser.add_argument('--native-evidence-ram',type=Path)
    parser.add_argument('--payloads',type=Path)
    args=parser.parse_args()
    full=args.stage=='full'
    expected_case=({'A1':'full-load-local-01','B':'full-load-wifi-01'} if full else
        {'A1':'health-profile-01','B':'health-profile-wifi-01'})[args.arm]
    if args.case!=expected_case:raise ValueError('Use the preregistered arm/case pair')
    if (args.arm=='B') != (args.native_evidence_ram is not None):
        raise ValueError('B requires its explicit exclusive RAM evidence path; A1 retains disk')
    # Explicit existing dependencies. Do not copy, rebuild or alias old binaries.
    if not args.native.is_absolute() or not args.native.is_file():raise FileNotFoundError(args.native)
    if not args.baseline.is_absolute() or not (args.baseline/'isolation/rootfs').is_dir():
        raise FileNotFoundError(args.baseline/'isolation/rootfs')
    if full:
        if args.payloads is None or not (args.payloads/'manifest.json').is_file():
            raise FileNotFoundError('Explicit prepared full Grid payloads required')
        payloads='/mnt/'+str(args.payloads.resolve().relative_to(REPO))
    base=REPO/'net01d/runs'/args.case
    base.mkdir(parents=True,exist_ok=False)
    for role in ('source','peer','gateway'):(base/role).mkdir()
    if full:
        for role in ('source-tb1','source-tb2','source-tb3','merge','client'):(base/role).mkdir()
    home=base/'runtime-home';home.mkdir()
    inner='/mnt/'+str(base.relative_to(REPO))
    hard_wall=60. if full else 30.
    started=time.monotonic();deadline=started+hard_wall
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
    scope=dict(arm=args.arm,delivery=('IDEAL-DIRECT-ADAPTER' if args.arm=='A1' else 'actual ns3 V3 B WiFi')+
            '; original reliable Action installed but no Goal sent',
        source_window_wall_s=32 if full else 16,hard_wall_s=hard_wall,session_id=2026110912,
        roles=['coordinator','hub/native','peer','gateway','mock_physics','source'],
        profile='controlled1000-clock100-q10ms',source_clock_contract='frozen-source-clock',
        dispatch_profile=True,control_trace=True,guard='original actual C masks+health to R intake; unarmed',
        source_sizes=dict(map=[250,220],local_costmap=[200,200],bound_mask=[400,400]),
        source_rates='odom30sim + odomTF; wheel10sim both in same message; scanheader5sim; '
            'costmap strict ROS>.5 in5wall poll; map5wall period; correction50wall latest_scan+.2; '
            'feedback100wall; exactzero_cmd20wall; Peer masks/health10sim unchanged',
        missing_flows=[89,95],scope='P1 independent-source size/cadence approximation, not SLAM/full-system/P5',
        native=str(args.native),baseline=str(args.baseline),
        native_evidence_ram=None if args.native_evidence_ram is None else str(args.native_evidence_ram),
        Gazebo=0,Nav2=0,Goal=0,NN=0,arm_guard=False)
    (base/'scope.json').write_text(json.dumps(scope,indent=2)+'\n')
    if full:
        scope.update(stage='full',normal_t0='actual C client all three Action facades ready and first Goal about to send',
            delivery=('IDEAL-DIRECT-ADAPTER' if args.arm=='A1' else 'actual ns3 V3 B WiFi')+
                '; controlled real Action transport; 3 normal +1 negative; no physical Nav2/Policy',
            source_window='Independent R supplies prewarm plus whole client32wall normal window and negative, until SUPPLY_STOP/finalSTOP',
            normal_Goals=3,negative_active_Goals=1,Goal=4,missing_flows=[],
            roles=['coordinator','hub/native','peer','gateway','mock_physics','source-tb1','source-tb2','source-tb3','merge','client'],
            source_sizes='Six original Grid templates in explicit payload manifest; unchanged cells/frame/origin/shape, new fixture-time fields',
            guard='Original actual masks/health and original actual arm services; normal automatic gates effective',
            arm_guard=True,payloads=str(args.payloads),
            negative='after normal32wall and RPCdrain, fourth tb3 accepted/GetResult ACKed; B realRADIOoff .8wall with sources continuing, A1 stop observations .8wall; local real cancellation/PAUSE required',
            scope='P5 no-motion complete business fixture; not real SLAM/Nav2/physics or scientific radio comparison')
        (base/'scope.json').write_text(json.dumps(scope,indent=2)+'\n')
    def wait_file(name,until):
        while time.monotonic()<until:
            failure=base/'FIRST_FAILURE.json'
            if failure.exists():raise RuntimeError('First normal guard/transport failure: '+failure.read_text())
            for role,process in processes.items():
                if process.poll() is not None:raise RuntimeError('Role exited before phase complete: '+role)
            if (base/name).exists():return
            time.sleep(.005)
        raise TimeoutError('Original diagnostic phase bound: '+name)
    try:
        launch('coordinator',ros(['/mnt/net01/time_controller.py','--ack-socket',inner+'/step.sock',
            '--output',inner+'/time-controller.json','--session-id','2026110912',
            '--hold-file',inner+'/HOLD','--stop-file',inner+'/COORDINATOR_STOP']),
            'TIME_CONTROL_READY '+inner+'/step.sock')
        launch('hub',[sys.executable,'-B',str(REPO/'net01/tools/packet_hub.py'),
            '--socket',str(base/'wire.sock'),'--native',str(args.native),'--output',str(base/'hub'),
            '--profile','B','--wall',str(int(hard_wall-1)),'--clock-source','gazebo','--control-trace',
            '--step-observer',str(base/'step.sock')]+
            (['--allow-radio-fault'] if full and args.arm=='B' else [])+
            ([] if args.native_evidence_ram is None else
                ['--native-evidence-ram',str(args.native_evidence_ram)]),
            'IPC_LISTENING '+str(base/'wire.sock'))
        children=Path('/proc')/str(processes['hub'].pid)/'task'/str(processes['hub'].pid)/'children'
        identities['native_children']=children.read_text().split()
        (base/'owned-processes.json').write_text(json.dumps(identities,indent=2)+'\n')
        role='/mnt/net01d/replay_roles.py';stop=inner+'/STOP'
        launch('peer',ros([role,'--role','peer','--directory',inner+'/peer','--stop-file',stop]))
        # Both roles start before bootstrap physical tokens can be granted.
        gateway=launch('gateway',ros([role,'--role','gateway','--directory',inner+'/gateway',
            '--stop-file',stop,'--mode',('A' if args.arm=='A1' else 'B')]+(['--full-load'] if full else [])))
        launch('mock_physics',ros(['/mnt/net01/followup04/mock_physics.py',
            '--output',inner+'/mock-physics.json','--stop-file',stop]),'MOCK_PHYSICS_READY')
        # Gateway stdout is a file: its independent source waits on real DDS
        # gateway_state connected/anchor, as in the original source fixture.
        if not full:
            source=launch('source',ros([role,'--role','source','--directory',inner+'/source','--stop-file',stop]))
            source.wait(timeout=max(.01,deadline-time.monotonic()-6.))
            if source.returncode:raise RuntimeError('Source returned nonzero')
        else:
            script='/mnt/net01d/health/full_load_client.py'
            launch('merge',ros([script,'--role','merge','--directory',inner+'/merge',
                '--stop-file',stop,'--session-id','2026110912']))
            for robot in (1,2,3):
                launch('source-tb'+str(robot),ros(['/mnt/net01d/health/full_load_source.py',
                    '--robot',str(robot),'--directory',inner+'/source-tb'+str(robot),
                    '--stop-file',stop,'--session-id','2026110912','--active-wall','32',
                    '--payloads',payloads,'--supply-stop-file',inner+'/SUPPLY_STOP']))
            launch('client',ros([script,'--role','client','--directory',inner+'/client',
                '--stop-file',stop,'--session-id','2026110912','--active-wall','32',
                '--journal',inner+'/gateway/controller/allocation-events.jsonl',
                '--normal-done-file',inner+'/CLIENT_NORMAL_DONE.json',
                '--allow-negative-file',inner+'/ALLOW_NEGATIVE_GOAL',
                '--negative-active-ready-file',inner+'/NEGATIVE_ACTIVE_READY.json']))
            wait_file('CLIENT_NORMAL_DONE.json',deadline-9.)
            wait_file('RPC_DRAINED.json',deadline-8.)
            (base/'ALLOW_NEGATIVE_GOAL').write_text('One preregistered controlled tb3 Goal only')
            wait_file('NEGATIVE_ACTIVE_READY.json',min(deadline-6.,time.monotonic()+2.))
            wait_file('NEGATIVE_TRANSPORT_READY.json',min(deadline-5.,time.monotonic()+1.))
            # First-failure phase boundary precedes the actual one-shot fault.
            (base/'NEGATIVE_PHASE.json').write_text(json.dumps(dict(
                monotonic_ns=time.monotonic_ns(),normal_complete=True,arm=args.arm)))
            if args.arm=='B':(base/'RADIO_OFF').write_text('Actual native one-shot radio-off diagnostic')
            else:(base/'SUPPLY_STOP').write_text('A1 observation stop; services continue')
            negative_until=time.monotonic()+.8
            while time.monotonic()<negative_until:time.sleep(.005)
            if not (base/'NEGATIVE_DONE.json').exists():
                raise RuntimeError('Original local CANCELED/PAUSE/futures not proved in fixed negative window')
    except BaseException as exc:error=repr(exc)
    finally:
        (base/'HOLD').write_text('Fixture resource HOLD; not physical stop certification')
        while not (base/'HOLD.ack').exists() and time.monotonic()<deadline-3:
            if 'coordinator' not in processes or processes['coordinator'].poll() is not None:break
            time.sleep(.005)
        if not (base/'HOLD.ack').exists() and error is None:error='Actual resource HOLD not confirmed'
        (base/'STOP').write_text('Fixture owned resource close, no business state')
        for role in ('source','source-tb1','source-tb2','source-tb3','client','merge','peer','gateway','mock_physics','hub'):
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
            negative_scope=('Actual local controlled cancellation; central negative Future may remain unknown; '
                'no claimed network recovery or physical stopping' if full else None),
            judgement='Process completion only; actual supply/health receipts/profile require offline review')
        (base/'process-exit.json').write_text(json.dumps(result,indent=2)+'\n')
        for log in logs:log.close()
    print(json.dumps(result),flush=True)
    # A completed negative guard fault is retained by the original coordinator;
    # exit1 there is expected, not rewritten to a clean shutdown.
    expected=(full and (base/'NEGATIVE_DONE.json').exists())
    return int(error is not None or any(p.returncode not in ((0,1) if expected and
        (role=='coordinator' or (args.arm=='B' and role=='gateway')) else (0,))
        for role,p in processes.items()))


if __name__=='__main__':raise SystemExit(main())

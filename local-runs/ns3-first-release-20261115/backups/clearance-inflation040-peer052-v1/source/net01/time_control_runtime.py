"""Owned controlled-time sidecars; no ROS import or business-data bridge."""
import json
import hashlib
import os
from pathlib import Path
import select
import signal
import subprocess
import time

from execution_profile import load_profile,SIM_BUSINESS_PROFILE_ID,SIM_BUSINESS60_PROFILE_ID,NATIVE_RAM60_SCOPE,BUSINESS60_PROFILE_IDS,FIXED_START60_PROFILE_ID,REPAIR120_PROFILE_ID,NATIVE_RAM120_SCOPE,REPAIR_PROFILE_IDS,COMPARISON40_PROFILE_ID,COMPARISON40_V2_PROFILE_ID,COMPARISON40_V3_PROFILE_ID,ROS_DELAY_PROFILE_ID

CONTROLLED_SCOPE='NET01 controlled-time 120sim engineering; not 180sim qualification'
CONTROLLED180_SCOPE='NET01 controlled-time 180sim common A1/B baseline; original safety gates'
CONTROLLED_BUSINESS180_SCOPE='NET01 sim-business-v1 controlled180sim pace40 engineering; causal qualification pending'
CONTROLLED_BUSINESS60_SCOPE='NET01 sim-business-v1 controlled60sim pace40 RAM6GiB-reserve2GiB engineering; causal qualification pending'
CONTROLLED_FIXED_START60_SCOPE='NET01 fixed-G20 attempt-G25-grid5-end80 consumer-v1 controlled60sim pace40 RAM6GiB-reserve2GiB engineering; causal qualification pending'
CONTROLLED_REPAIR120_SCOPE='NET01 exploration-repair-v1 fixed-G20 attempt-G25-grid5-end140 consumer-v1 controlled120sim pace40 RAM8GiB-reserve2GiB engineering; T95 post-exit only'
CONTROLLED_COMPARISON40_SCOPE='NET01 comparison40 repair-v1 four-condition fixed-G20 end140 source-take-v1 controlled120sim pace40 RAM8GiB-reserve2GiB; T95 post-exit only'
CONTROLLED_COMPARISON40_V2_SCOPE='NET01 comparison40-v2 repair-v1 fixed-G20 end140 attempt-enter physical-boundary barrier source-take-v1 controlled120sim absolute-pace40 RAM8GiB-reserve2GiB; original pacing gates and T95 post-exit only'
CONTROLLED_COMPARISON40_V3_SCOPE='NET01 comparison40-v3 repair-v1 all-spawn-exit0-before-first-token fixed-G20 end140 attempt-enter barrier source-take-v1 controlled120sim absolute-pace40 RAM8GiB-reserve2GiB; original pacing gates and T95 post-exit only'
CONTROLLED_ROS_DELAY_V2_SCOPE='NET01 ROS-local wall-delay-v2 original armed-guard authority lifecycle A0 calibration D0-D500 reliable FIFO source-age .70/.85sim v3 startup-fence attempt-barrier fixed-G20 end140 controlled120sim absolute-pace40 RAM8GiB-reserve2GiB; T95 post-exit only'
CONTROLLED_ROS_DELAY_V3_SCOPE='NET01 ROS-local wall-delay-v3 common receipt .60sim projectedodom .50sim source .70/.85sim A0 calibration D0-D500 reliable FIFO original armed-guard lifecycle v3 startup-fence attempt-barrier fixed-G20 end140 controlled120sim absolute-pace40 RAM8GiB-reserve2GiB; original60wall evidence grace after strict resource closure; T95 post-exit only'
CONTROLLED_ROS_DELAY_SCOPE=CONTROLLED_ROS_DELAY_V3_SCOPE
PLUGIN_CONTAINER='/tmp/net01_time_control.so'
WITNESS_CONTAINER='/tmp/net01-clock-witness'


def controlled_config(ready):
    net=ready['network'];profile=load_profile(net.get('execution_profile') or None)
    controlled=profile is not None and profile.get('controlled_physics',False)
    config=net.get('controlled_time')
    if not controlled:
        if config is not None:raise ValueError('Controlled sidecars require the explicit controlled profile')
        return None
    if net.get('execution_profile') in REPAIR_PROFILE_IDS:
        scope={COMPARISON40_PROFILE_ID:CONTROLLED_COMPARISON40_SCOPE,
            COMPARISON40_V2_PROFILE_ID:CONTROLLED_COMPARISON40_V2_SCOPE,
            COMPARISON40_V3_PROFILE_ID:CONTROLLED_COMPARISON40_V3_SCOPE,
            ROS_DELAY_PROFILE_ID:CONTROLLED_ROS_DELAY_SCOPE}.get(net['execution_profile'],CONTROLLED_REPAIR120_SCOPE)
        bounds=tuple(ready[key] for key in ('sim_budget','startup_wall','autonomous_wall','outer_wall','cleanup_wall'))
        if config is None or config['engineering_scope']!=scope or bounds!=(120,180,720,1000,90):
            raise ValueError('Explicit exploration-repair120 scope and fixed bounds required')
        if (net.get('native_evidence_scope')!=NATIVE_RAM120_SCOPE or net.get('native_evidence_ram') is None
            or net.get('native_ledger_mode','serial')!='serial' or net.get('native_async_ledger',False) is not False
            or net.get('native_cpu_profile',False) is not False):
            raise ValueError('Repair120 requires explicit serial RAM8GiB/reserve2GiB without CPU/async diagnostics')
        return config
    if net.get('execution_profile') in BUSINESS60_PROFILE_IDS:
        scope=(CONTROLLED_FIXED_START60_SCOPE if net['execution_profile']==FIXED_START60_PROFILE_ID else CONTROLLED_BUSINESS60_SCOPE)
        if config is None or (ready['sim_budget'],config['engineering_scope'])!=(60,scope):
            raise ValueError('Explicit sim-business60 RAM engineering contract required')
        if (net.get('native_evidence_scope')!=NATIVE_RAM60_SCOPE or net.get('native_evidence_ram') is None
            or net.get('native_ledger_mode','serial')!='serial' or net.get('native_async_ledger',False) is not False
            or net.get('native_cpu_profile',False) is not False):
            raise ValueError('Business60 requires its explicit serial RAM6GiB/reserve2GiB backend without CPU/async diagnostics')
        return config
    if net.get('execution_profile')==SIM_BUSINESS_PROFILE_ID:
        if config is None or (ready['sim_budget'],config['engineering_scope'])!=(180,CONTROLLED_BUSINESS180_SCOPE):
            raise ValueError('Explicit new sim-business180 engineering contract required')
        return config
    if config is None or (ready['sim_budget'],config['engineering_scope']) not in (
            (120,CONTROLLED_SCOPE),(180,CONTROLLED180_SCOPE)):
        raise ValueError('Explicit controlled120/180sim admission required')
    return config


class ControlledRuntime:
    def __init__(self,ready,repo,case):
        self.config=controlled_config(ready);self.repo=Path(repo);self.case=Path(case)
        self.execution_profile=ready['network']['execution_profile']
        self.debug_gzserver=ready.get("gzserver_batch_gdb",False)
        self.phase=self.repo.parent;self.baseline=self.phase.parent/'base-01-econ'
        self.session=ready['network']['session_id'];self.processes={};self.child_pids={};self.logs=[]
        self.directory=self.case.with_name(self.case.name+'.time-control')
        self.relative=self.directory.relative_to(self.repo)
        self.container=Path('/mnt')/self.relative
        self.ack_relative=self.relative/'ack.sock'
        self.plugin=(self.phase/self.config['plugin_relative_phase']).resolve(strict=True)
        self.witness=(self.phase/self.config['witness_relative_phase']).resolve(strict=True)

    def python_command(self,arguments,domain=92):
        # Same existing rootfs/setup/dependencies as ros-python.sh; only these
        # two reviewed artifacts gain private read-only mounts under tmpfs.
        return self.rootfs_command(['python3','-B',*arguments],domain)

    def rootfs_command(self,arguments,domain):
        debug_main=(self.debug_gzserver and arguments[:3]==
            ['python3','-B','/mnt/net01/boot_network.py'])
        debug_mounts=(['--ro-bind','/usr/bin/gdb','/tmp/gdb-host/gdb',
            '--ro-bind','/lib/x86_64-linux-gnu','/tmp/gdb-host/lib',
            '--ro-bind','/usr/share/gdb','/tmp/gdb-host/share'] if debug_main else [])
        return ['bwrap','--unshare-user','--uid','0','--gid','0','--die-with-parent',
            '--ro-bind',str(self.baseline/'isolation/rootfs'),'/', '--tmpfs','/tmp',
            *debug_mounts,
            '--bind',str(self.repo/'runtime-home'),'/root',
            '--bind' if debug_main else '--ro-bind','/proc','/proc','--dev-bind','/dev','/dev','--ro-bind','/sys','/sys',
            '--ro-bind',str(self.baseline),'/project','--bind',str(self.repo),'/mnt',
            '--ro-bind','/home/zhuyulab/.local/lib/python3.10/site-packages','/tmp/rl02-python',
            '--ro-bind',str(self.plugin),PLUGIN_CONTAINER,
            '--ro-bind',str(self.witness),WITNESS_CONTAINER,'--chdir','/mnt',
            '/usr/bin/env','-i','PATH=/usr/sbin:/usr/bin:/sbin:/bin','HOME=/root','LANG=C.UTF-8',
            'ROS_DOMAIN_ID='+str(domain),'ROS_LOCALHOST_ONLY=1','RMW_IMPLEMENTATION=rmw_fastrtps_cpp',
            'PYTHONNOUSERSITE=1','PYTHONDONTWRITEBYTECODE=1','OPENBLAS_NUM_THREADS=1',
            'OMP_NUM_THREADS=1','MKL_NUM_THREADS=1',
            'NET01_TIME_CONTROL=1','NET01_TIME_CONTROL_PLUGIN='+PLUGIN_CONTAINER,
            'NET01_TIME_CONTROL_DIRECTORY='+str(self.container),
            'NET01_SESSION_ID='+str(self.session),
            '/bin/bash','--noprofile','--norc','-c',
            'source /opt/ros/humble/setup.bash\nsource /project/workspace/install/setup.bash\n'
            'export PYTHONPATH=/mnt:/mnt/net01:/mnt/workspace/gz01:/mnt/workspace/rl04:/mnt/workspace/rl02:/mnt/workspace/rl01:/mnt/workspace/src/multi_robot_exploration:/tmp/rl02-python:${PYTHONPATH:-}\n'
            'exec "$@"','bash',*arguments]

    def start(self,deadline):
        identity={}
        for role,path in (('plugin',self.plugin),('witness',self.witness)):
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual!=self.config[role+'_sha256']:
                raise ValueError('Reviewed controlled-time artifact changed: '+role)
            identity[role]=dict(host_path=str(path),sha256=actual)
        self.directory.mkdir(exist_ok=False)  # Never create the frozen exclusive case directory.
        (self.directory/'artifact-identity.json').write_text(json.dumps(identity,indent=2)+'\n')
        (self.repo/'runtime-home').mkdir(exist_ok=True)
        commands=[('coordinator',self.python_command(['/mnt/net01/time_controller.py',
            '--ack-socket',str(self.container/'ack.sock'),'--output',str(self.container/'coordinator.json'),
            '--session-id',str(self.session),'--execution-profile',self.execution_profile]),'TIME_CONTROL_READY '+str(self.container/'ack.sock'))]
        commands += [(f'clock_{side}',self.rootfs_command([WITNESS_CONTAINER,
            str(self.container/f'clock-{side}.csv')],domain),'CLOCK_WITNESS_READY')
            for side,domain in (('R',92),('C',91))]
        for role,command,expected in commands:
            self.start_sidecar(role,command,expected,deadline)

    def start_sidecar(self,role,command,expected,deadline):
        log=(self.directory/(role+'.log')).open('x');self.logs.append(log)
        info_path=self.directory/(role+'.bwrap-info.json')
        # Native bwrap metadata, not a child-written pidfile. No PID namespace
        # is unshared, so child-pid is the host-visible exec child PID.
        with info_path.open('x') as info:
            command=[command[0],'--info-fd',str(info.fileno()),*command[1:]]
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=log,text=True,
                pass_fds=(info.fileno(),),start_new_session=True)
        self.processes[role]=process
        with (self.directory/'owned.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(role=role,pid=process.pid,pgid=process.pid,argv=command))+'\n')
        readable,_,_=select.select([process.stdout],[],[],max(0.,deadline-time.monotonic()))
        if not readable:raise TimeoutError('Controlled sidecar startup exceeded existing IPC startup bound: '+role)
        line=process.stdout.readline();log.write(line);log.flush()
        self.child_pids[role]=json.loads(info_path.read_text())['child-pid']
        with (self.directory/'owned.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(role=role,bwrap_pid=process.pid,child_pid=self.child_pids[role],
                source='bwrap --info-fd',info=str(info_path)))+'\n')
        if line.strip()!=expected:raise RuntimeError('Controlled sidecar failed before Hub: '+role)

    def close(self):
        signals={role:[] for role in self.processes};forced=[]
        for role,process in self.processes.items():
            # Keep the bwrap monitor alive: killing it would activate
            # --die-with-parent before the ROS child finishes its RAM flush.
            if process.poll() is not None or role not in self.child_pids:continue
            try:os.kill(self.child_pids[role],signal.SIGINT);signals[role].append('SIGINT_CHILD')
            except ProcessLookupError:pass
        deadline=time.monotonic()+5
        def remaining_groups():
            alive=[]
            for role,process in self.processes.items():
                process.poll()
                try:os.killpg(process.pid,0);alive.append(role)
                except ProcessLookupError:pass
            return alive
        while remaining_groups() and time.monotonic()<deadline:time.sleep(.01)
        for role in remaining_groups():
            forced.append(role)
            try:os.killpg(self.processes[role].pid,signal.SIGKILL);signals[role].append('SIGKILL')
            except ProcessLookupError:pass
        for process in self.processes.values():process.wait(timeout=1)
        rows=dict(exits={role:p.returncode for role,p in self.processes.items()},signals=signals,
            actual_bwrap_child_pids=self.child_pids,
            forced_owned_groups=forced,remaining_owned_groups=remaining_groups(),
            scope='Resource cleanup after actual Hub END/exit; no stopping certificate')
        final=self.directory/'coordinator.json'
        rows['coordinator_final']=None
        if final.exists():
            try:rows['coordinator_final']=json.loads(final.read_text())['final']
            except json.JSONDecodeError as error:rows['coordinator_record_error']=repr(error)
        rows['saved_clocks']={side:(self.directory/f'clock-{side}.csv').exists() for side in ('R','C')}
        rows['integrity']=bool(not forced and not rows['remaining_owned_groups'] and len(self.processes)==3 and
            all(p.returncode==0 for p in self.processes.values()) and all(rows['saved_clocks'].values()) and
            rows['coordinator_final'] is not None and rows['coordinator_final']['expected_shutdown'] and
            not rows['coordinator_final']['physical_RPC_inflight'])
        (self.directory/'process-exit.json').write_text(json.dumps(rows,indent=2)+'\n')
        for log in self.logs:log.close()
        return rows

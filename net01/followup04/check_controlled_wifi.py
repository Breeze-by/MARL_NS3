"""One preregistered bounded MOCK_PHYSICS/WiFi qualification, not Gazebo.

Production coordinator, native WiFi, Gateway B and BoundPeer; original steady
source rates and gates. Resource HOLD/stop files are fixture teardown only.
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

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from execution_profile import load_profile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',required=True)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--native-evidence-ram',type=Path)
    parser.add_argument('--source-clock-contract',choices=['legacy-steady','frozen-source-clock'],default='legacy-steady')
    args=parser.parse_args()
    profile_id='controlled1000-clock100-q10ms';profile=load_profile(profile_id)
    repo=HERE.parent;base=repo/'runs'/args.name;base.mkdir(exist_ok=False)
    for role in ('source','peer','gateway'):(base/role).mkdir()
    start=time.monotonic();deadline=start+30;processes={};logs=[];error=None
    prefix='/mnt/runs/'+args.name
    (base/'scope.json').write_text(json.dumps(dict(scope='MOCK_PHYSICS + actual native WiFi, not Gazebo/Policy/physical safety',
        profile=profile,native=str(args.native),source_wall_s=16,hard_wall_s=30,
        native_evidence_ram=None if args.native_evidence_ram is None else str(args.native_evidence_ram),
        source_clock_contract=args.source_clock_contract,
        mode='B',domains=dict(C=91,R=92),Gazebo=0,Nav2=0,Goal=0,NN=0,arm=False),indent=2))
    def launch(role,argv,pipe=False):
        err=(base/(role+'.stderr.txt')).open('x');logs.append(err)
        out=subprocess.PIPE if pipe else (base/(role+'.stdout.txt')).open('x')
        if not pipe:logs.append(out)
        process=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True,text=True)
        processes[role]=process;return process
    def ready(process,expected):
        readable,_,_=select.select([process.stdout],[],[],max(0,min(5,deadline-time.monotonic())))
        if not readable or process.stdout.readline().strip()!=expected:raise RuntimeError('Startup marker missing: '+expected)
    wrapper=['bash',str(HERE/'ros-python.sh')]
    try:
        coordinator=launch('coordinator',wrapper+['/mnt/net01/time_controller.py',
            '--ack-socket',prefix+'/step.sock','--output',prefix+'/time-controller.json',
            '--session-id','2026110912',
            '--hold-file',prefix+'/HOLD','--stop-file',prefix+'/COORDINATOR_STOP'],True)
        ready(coordinator,'TIME_CONTROL_READY '+prefix+'/step.sock')
        hub=launch('hub',[sys.executable,'-B',str(HERE/'tools/packet_hub.py'),
            '--socket',str(base/'wire.sock'),'--native',str(args.native),'--output',str(base/'hub'),
            '--profile','B','--wall','29','--clock-source','gazebo','--control-trace',
            '--step-observer',str(base/'step.sock')]+
            ([] if args.native_evidence_ram is None else
                ['--native-evidence-ram',str(args.native_evidence_ram)]),True)
        ready(hub,'IPC_LISTENING '+str(base/'wire.sock'))
        common='/mnt/net01/followup01/continuous_dds.py'
        launch('peer',wrapper+[common,'--role','peer','--directory',prefix+'/peer','--stop-file',prefix+'/STOP'])
        launch('gateway',wrapper+[common,'--role','gateway','--directory',prefix+'/gateway',
            '--stop-file',prefix+'/STOP','--mode','B','--execution-profile',profile_id,'--control-trace'])
        mock=launch('mock_physics',wrapper+['/mnt/net01/followup04/mock_physics.py',
            '--output',prefix+'/mock-physics.json','--stop-file',prefix+'/STOP'],True)
        ready(mock,'MOCK_PHYSICS_READY')
        source=launch('source',wrapper+[common,'--role','source','--directory',prefix+'/source',
            '--feedback-hz','100','--execution-profile',profile_id]+
            ([] if args.source_clock_contract=='legacy-steady' else
                ['--source-clock-contract',args.source_clock_contract]))
        source.wait(timeout=max(.01,deadline-time.monotonic()-6))
    except BaseException as exc:error=repr(exc)
    finally:
        # Stop physical grants while the Step server still exists. Keep the
        # coordinator and its ACK socket alive until Gateway END/hub exit.
        (base/'HOLD').write_text('Fixture resource HOLD, not a physics/safety certificate')
        while not (base/'HOLD.ack').exists() and time.monotonic()<deadline-3:
            if processes.get('coordinator') is None or processes['coordinator'].poll() is not None:break
            time.sleep(.005)
        if not (base/'HOLD.ack').exists() and error is None:error='Expected resource HOLD not confirmed'
        (base/'STOP').write_text('Fixture owned resource stop only')
        for role in ('source','peer','gateway','mock_physics','hub'):
            process=processes.get(role)
            if process is None or process.poll() is not None:continue
            try:process.wait(timeout=max(.01,deadline-time.monotonic()-1))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
                if error is None:error='Hard bound forced owned role: '+role
        (base/'COORDINATOR_STOP').write_text('After hub exit; retain ACK socket through native END')
        coordinator=processes.get('coordinator')
        if coordinator is not None and coordinator.poll() is None:
            try:coordinator.wait(timeout=max(.01,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(coordinator.pid,signal.SIGKILL);coordinator.wait()
                if error is None:error='Hard bound forced coordinator'
        result=dict(scope='MOCK_PHYSICS WiFi feasibility only; not real GZ clock/stop/180sim PASS',
            error=error,wall_s=time.monotonic()-start,hard_wall_s=30,
            exits={role:p.returncode for role,p in processes.items()},profile=profile,
            resource_control='HOLD then STOP, keep actual ACK observer through native END',
            Gazebo=0,Nav2=0,Goal=0,NN=0)
        (base/'process-exit.json').write_text(json.dumps(result,indent=2))
        for log in logs:log.close()
    print(json.dumps(result),flush=True)
    return int(error is not None or any(p.returncode!=0 for p in processes.values()))


if __name__=='__main__':raise SystemExit(main())

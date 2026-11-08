"""Consume one root-reviewed ready file and run exactly one isolated GZ-01 case.

This module never creates an admission or retries a failed invocation. Import is
ROS/Gazebo/NN free. Paths in the ready file are relative to this phase root.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from system_variants import GOAL_SEPARATION_M

PHASE = Path(__file__).resolve().parents[2]
WORKTREE = PHASE/'workspace'
MODEL_SHA = '6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def phase_path(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Admission paths must be phase relative')
    return PHASE/path


def validate_ready(path, consumed=False):
    path = Path(path).resolve()
    ready = json.loads(path.read_text())
    if ready.get('authorized_gz01_execution') is not True:
        raise ValueError('No root-reviewed GZ-01 execution admission')
    if ready['mode'] not in ('stationary_only','autonomous') or ready['arm'] not in ('rl','traditional'):
        raise ValueError('Unsupported reviewed GZ-01 mode/arm')
    active_cancel_check = ready.get('active_cancel_check', False)
    if type(active_cancel_check) is not bool:
        raise ValueError('active_cancel_check must be an explicit JSON bool')
    if active_cancel_check and ready['mode'] != 'autonomous':
        raise ValueError('Active cancellation requires explicitly admitted autonomous mode')
    if type(ready['stop_diagnostic']) is not bool or type(ready['phase_probe']) is not bool:
        raise ValueError('Followup diagnostic flags must be explicit booleans')
    if ready['stop_diagnostic'] and ready['mode'] != 'stationary_only':
        raise ValueError('Controlled stop diagnostic is not autonomous exploration')
    if ready['checkpoint_sha256'] != MODEL_SHA:
        raise ValueError('Admission does not bind the current fixed reference model')
    if not 0 < ready['sim_budget'] <= 600:
        raise ValueError('GZ-01 autonomous budget must be within 600sim')
    for key in ('startup_wall','autonomous_wall','outer_wall','cleanup_wall'):
        if ready[key] <= 0:
            raise ValueError('Admission requires positive independent wall bounds')
    if ready['outer_wall'] > 1800:
        raise ValueError('Followup02 independent wall limit is 1800 seconds')
    if ready['decision_limit'] != 130:
        raise ValueError('All GZ-01 arms require the same registered 130decision limit')
    system_variant = ready.get('system_variant','reference-v1')
    if system_variant not in GOAL_SEPARATION_M:
        raise ValueError('Unregistered GZ-01 common system variant')
    if ready['peer_guard'] != (system_variant=='peer-compact-v1'):
        raise ValueError('Peer mask node and common target checker must be enabled together')
    if ready.get('gzserver_batch_gdb', False):
        if not Path('/tmp/gdb-host/gdb').is_file():
            raise FileNotFoundError('Debug entry requires the private existing host debugger mount')
    case = phase_path(ready['case_relative_phase'])
    scene = phase_path(ready['scene_relative_phase'])
    if json.loads(scene.read_text()).get('controlled_stop_diagnostic') and ready['mode'] != 'stationary_only':
        raise ValueError('Failure-pose diagnostic scene cannot run autonomous exploration')
    checkpoint = phase_path(ready['checkpoint_relative_phase'])
    if sha(scene) != ready['scene_sha256'] or sha(checkpoint) != ready['checkpoint_sha256']:
        raise ValueError('Reviewed scene or checkpoint changed')
    world = phase_path(json.loads(scene.read_text())['world_relative_phase'])
    if sha(world) != ready['world_sha256']:
        raise ValueError('Reviewed world geometry changed')
    if sha(PHASE/'runs/selection.json') != ready['selection_sha256']:
        raise ValueError('Reviewed selected checkpoint binding changed')
    for relative, expected in ready['source_sha256_relative_worktree'].items():
        source = Path(relative)
        if source.is_absolute() or '..' in source.parts or sha(WORKTREE/source) != expected:
            raise ValueError('Reviewed source changed: '+relative)
    required = {'gz01/boot.py','gz01/run_case.py','gz01/headquarters.py','gz01/scene_launch.py','gz01/system_variants.py','gz01/seed_bridge.py','gz01/seed_connection_ros.py',
                'rl01/ros_policy.py','rl04/ros_headquarters.py','rl02/run_gazebo.py',
                'src/multi_robot_exploration/multi_robot_exploration/allocation.py',
                'src/multi_robot_exploration/multi_robot_exploration/joint.py',
                'src/multi_robot_exploration/multi_robot_exploration/control.py',
                'src/multi_robot_exploration/multi_robot_exploration/ppo.py'}
    if ready['peer_guard']:required.add('gz01/peer_keepout.py')
    if ready.get('gzserver_batch_gdb', False):
        required.update({'gz01/debug_process.py','gz01/gzserver_gdb.py','gz01/gzserver_gdb.sh','gz01/batch_gzserver.launch.py'})
    if not required.issubset(ready['source_sha256_relative_worktree']):
        raise ValueError('Admission does not bind the common execution and policy sources')
    used = case.with_name(case.name+'.admission-used.json')
    if consumed:
        if json.loads(used.read_text())['ready_sha256'] != sha(path):
            raise ValueError('Runner admission differs from consumed boot admission')
    elif used.exists() or case.exists() or case.with_name(case.name+'.xvfb.log').exists():
        raise FileExistsError('This case/admission was already used; no overwrite or retry')
    return dict(ready,case_path=str(case),scene_path=str(scene),checkpoint_path=str(checkpoint),
                active_cancel_check=active_cancel_check,system_variant=system_variant)


def kill_owned(directory):
    """Last-resort timeout teardown only for this case's recorded process groups."""
    path = directory/'owned_processes.jsonl'
    if not path.exists():
        return
    marker = ('GZ01_CASE='+str(directory)).encode()
    for line in path.read_text().splitlines():
        pid = json.loads(line)['pid']
        environment = Path('/proc')/str(pid)/'environ'
        try:
            if environment.exists() and marker in environment.read_bytes().split(b'\0'):
                if os.getpgid(pid) == pid:
                    os.killpg(pid,signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass  # The recorded child exited during teardown.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready',type=Path,required=True)
    args = parser.parse_args()
    ready = validate_ready(args.ready)
    case = Path(ready['case_path'])
    case.parent.mkdir(parents=True,exist_ok=True)
    used = case.with_name(case.name+'.admission-used.json')
    with used.open('x') as stream:
        json.dump(dict(ready_path=str(args.ready.resolve()),ready_sha256=sha(args.ready),
            boot_start_utc=datetime.now(timezone.utc).isoformat(),case=str(case),
            no_implicit_retry=True),stream,indent=2)
    os.environ.update(ROS_DOMAIN_ID='69',TURTLEBOT3_MODEL='waffle',
        GAZEBO_MASTER_URI='http://127.0.0.1:11669',GAZEBO_MODEL_DATABASE_URI='',
        DISPLAY=':69',QT_QPA_PLATFORM='offscreen',LIBGL_ALWAYS_SOFTWARE='1',
        PYTHONDONTWRITEBYTECODE='1',GZ01_CASE=str(case))
    if ready.get('gzserver_batch_gdb', False):os.environ['GZ01_BATCH_GDB']='1'
    os.environ['GAZEBO_MODEL_PATH'] = '/project/assets/gazebo_models:'+os.environ.get('GAZEBO_MODEL_PATH','')
    outcome = dict(start_utc=datetime.now(timezone.utc).isoformat(),native_exit=None,
                   outer_timeout=False,cleanup_timeout=False)
    xvfb = runner = None
    try:
        with case.with_name(case.name+'.xvfb.log').open('x') as stream:
            xvfb = subprocess.Popen(['Xvfb',':69','-screen','0','1280x800x24','-nolisten','tcp'],
                stdout=stream,stderr=subprocess.STDOUT)
            runner = subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('run_case.py')),
                '--ready',str(args.ready.resolve())],start_new_session=True)
            try:
                outcome['native_exit'] = runner.wait(timeout=ready['outer_wall'])
            except subprocess.TimeoutExpired:
                outcome['outer_timeout'] = True
                runner.send_signal(signal.SIGINT)
                try:
                    outcome['native_exit'] = runner.wait(timeout=ready['cleanup_wall'])
                except subprocess.TimeoutExpired:
                    outcome['cleanup_timeout'] = True
                    kill_owned(case)
                    os.killpg(runner.pid,signal.SIGKILL)
                    outcome['native_exit'] = runner.wait()
    finally:
        if xvfb is not None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=3)
            except subprocess.TimeoutExpired:
                xvfb.kill()
                xvfb.wait()
        outcome['end_utc'] = datetime.now(timezone.utc).isoformat()
        with case.with_name(case.name+'.boot-exit.json').open('x') as stream:
            json.dump(outcome,stream,indent=2)
    return 1 if outcome['outer_timeout'] or outcome['cleanup_timeout'] else outcome['native_exit']


if __name__ == '__main__':
    raise SystemExit(main())

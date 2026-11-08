"""Boot the one reviewed RL04 Gazebo smoke; no implicit retry or GUI launch."""
import json
import os
from pathlib import Path
import subprocess
import sys
from common import HERE, PROJECT, sha


def main():
    ready = json.loads((PROJECT/'runs/P5_READY.json').read_text())
    if not ready['authorized_rl04_execution']:
        raise ValueError('Concrete follow-up execution has not been authorized')
    if ready['allowed_mode']=='stationary_only' and '--stationary-only' not in sys.argv:
        raise ValueError('Only the non-autonomous stationary phase is admitted')
    selection_path = PROJECT/'runs/selection.json'
    if sha(selection_path) != ready['selection_sha256']:
        raise ValueError('Reviewed Gazebo selection changed')
    for relative, expected in ready['code_sha256_relative_project'].items():
        if sha(PROJECT/relative) != expected:
            raise ValueError('Reviewed Gazebo source changed: '+relative)
    case = Path(sys.argv[1])
    if case.resolve() != (PROJECT/ready['case_relative_project']).resolve():
        raise ValueError('Execution case differs from its registered admission')
    xvfb_log = case.with_name(case.name+'.xvfb.log')
    if case.exists() or xvfb_log.exists():
        raise FileExistsError('Gazebo attempt evidence already exists; no overwrite or retry')
    os.environ.update(TURTLEBOT3_MODEL='waffle', GAZEBO_MASTER_URI='http://127.0.0.1:11668',
        GAZEBO_MODEL_DATABASE_URI='', DISPLAY=':68', QT_QPA_PLATFORM='offscreen', LIBGL_ALWAYS_SOFTWARE='1')
    os.environ['GAZEBO_MODEL_PATH'] = '/project/assets/gazebo_models:'+os.environ.get('GAZEBO_MODEL_PATH', '')
    xvfb_log.parent.mkdir(parents=True, exist_ok=True)
    with xvfb_log.open('x') as stream:
        xvfb = subprocess.Popen(['Xvfb', ':68', '-screen', '0', '1280x800x24', '-nolisten', 'tcp'],
                                stdout=stream, stderr=subprocess.STDOUT)
        try:
            from run_gazebo import main as run
            sys.argv.extend(['--controller-script','/mnt/workspace/rl04/ros_headquarters.py'])
            raise SystemExit(run())
        finally:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=3)
            except subprocess.TimeoutExpired:
                xvfb.kill()
                xvfb.wait()


if __name__ == '__main__':
    main()

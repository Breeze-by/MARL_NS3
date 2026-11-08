"""Native exit1 + Xvfb cleanup fixture; no real Xvfb/ROS/Gazebo or model."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import types
from maps import PROJECT, dump, sha


def child(output):
    import gazebo_boot
    project = output/'fake-project'
    (project/'runs').mkdir(parents=True)
    selection = project/'runs/selection.json'
    dump(selection, {'fixture_only': True, 'no_checkpoint': True})
    dump(project/'runs/P5_READY.json', dict(independent_review_passed=True,
        selection_sha256=sha(selection), code_sha256_relative_project={}))
    gazebo_boot.PROJECT = project
    calls = []

    class NoProcess:
        def terminate(self):
            calls.append('terminate')

        def wait(self, timeout=None):
            calls.append('wait')
            dump(output/'cleanup.json', dict(calls=calls, actual_xvfb_spawned=False,
                ros_node_init=0, gazebo_started=0, nn_forward=0, env_step=0))
            return 0

    def no_popen(*args, **kwargs):
        calls.append('fake_popen')
        return NoProcess()

    fake_harness = types.ModuleType('run_gazebo')
    fake_harness.main = lambda: 1
    sys.modules['run_gazebo'] = fake_harness
    gazebo_boot.subprocess = types.SimpleNamespace(Popen=no_popen, TimeoutExpired=subprocess.TimeoutExpired,
        STDOUT=subprocess.STDOUT)
    sys.argv = ['gazebo_boot_fixture', str(output/'unused-case')]
    gazebo_boot.main()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    process = subprocess.run([sys.executable, '-B', __file__, '--child', str(output)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (output/'child.stdout').write_text(process.stdout)
    (output/'child.stderr').write_text(process.stderr)
    cleanup = json.loads((output/'cleanup.json').read_text())
    if process.returncode != 1 or cleanup['calls'] != ['fake_popen', 'terminate', 'wait']:
        raise AssertionError('Supervisor failure was not propagated with cleanup')
    result = dict(status='PASS', stub_supervisor_return=1, native_child_exit=process.returncode,
        cleanup=cleanup, nn_forward=0, optimizer_step=0, env_step=0, real_ros_node=0,
        actual_root_P5_READY_exists=(PROJECT/'runs/P5_READY.json').exists())
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', type=Path)
    parser.add_argument('--output', type=Path, default=PROJECT/'evidence/gazebo-boot-exit-01')
    args = parser.parse_args()
    child(args.child) if args.child else run(args.output.resolve())

"""One bounded new no-motion collection, reusing actual original ROS components.

Requires separate Root source/command admission. Does not launch Gazebo/Nav2/SLAM.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
BASELINE = Path('/home/zhuyulab/ns3-workspace/base-01-econ')
NATIVE = Path('/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp')
LIBRARY = NATIVE.parents[1] / 'build/lib'
PROFILE = 'controlled1000-clock100-q10ms-pace10-raster-simhealth'
sys.path.insert(0, str(REPO / 'net01d/followup02/native'))
from observe_lto_pair import proc, owned_tree, MODULES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=('A1', 'B', 'C'), required=True)
    parser.add_argument('--dds-take-trace', action='store_true')
    args = parser.parse_args()
    base = args.output.resolve(); inner = '/mnt/' + str(base.relative_to(REPO))
    base.mkdir(parents=True, exist_ok=False)
    for name in ('peer', 'gateway', 'runtime-home'):
        (base / name).mkdir()
    def ros(argv):
        return ['bwrap', '--unshare-user', '--uid', '0', '--gid', '0', '--die-with-parent',
            '--ro-bind', str(BASELINE / 'isolation/rootfs'), '/', '--tmpfs', '/tmp',
            '--bind', str(base / 'runtime-home'), '/root', '--ro-bind', '/proc', '/proc',
            '--dev-bind', '/dev', '/dev', '--ro-bind', '/sys', '/sys',
            '--ro-bind', str(BASELINE), '/project', '--bind', str(REPO), '/mnt', '--chdir', '/mnt',
            '--ro-bind', '/home/zhuyulab/.local/lib/python3.10/site-packages', '/tmp/rl02-python',
            '/usr/bin/env', '-i', 'PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'HOME=/root', 'LANG=C.UTF-8',
            'ROS_LOCALHOST_ONLY=1', 'RMW_IMPLEMENTATION=rmw_fastrtps_cpp', 'PYTHONNOUSERSITE=1',
            'PYTHONDONTWRITEBYTECODE=1', 'OPENBLAS_NUM_THREADS=1', 'OMP_NUM_THREADS=1',
            '/bin/bash', '--noprofile', '--norc', '-c',
            'source /opt/ros/humble/setup.bash; source /project/workspace/install/setup.bash; '
            'export PYTHONPATH=/mnt:/mnt/net01:/mnt/workspace/gz01:/mnt/workspace/rl04:'
            '/mnt/workspace/rl02:/mnt/workspace/rl01:/mnt/workspace/src/multi_robot_exploration:'
            '/tmp/rl02-python:${PYTHONPATH:-}; exec python3 -B "$@"', 'bash', *argv]
    processes = {}; logs = []; commands = {}; forced = []; error = None
    begin = time.monotonic(); deadline = begin + 60
    stop = inner + '/STOP'; prefix = '/mnt/net01e/replay/'
    def launch(role, argv, marker=None, env=None):
        commands[role] = argv
        (base / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        out = (base / (role + '.stdout')).open('x'); err = (base / (role + '.stderr')).open('x')
        logs.extend([out, err])
        process = subprocess.Popen(argv, stdout=subprocess.PIPE if marker else out, stderr=err,
                                   env=env, start_new_session=True, text=True)
        processes[role] = process
        (base / 'owned.json').write_text(json.dumps({r: dict(pid=p.pid, argv=commands[r])
                                                    for r, p in processes.items()}, indent=2))
        if marker:
            readable, _, _ = select.select([process.stdout], [], [], 5)
            line = process.stdout.readline() if readable else ''
            out.write(line); out.flush()
            if line.strip() != marker:
                raise RuntimeError('missing actual startup marker: ' + marker)
    try:
        check_command = ros([prefix + 'domain_preflight.py', '--output', inner + '/domain-preflight.json'])
        (base / 'domain-preflight.argv.json').write_text(json.dumps(check_command, indent=2) + '\n')
        subprocess.run(check_command, check=True, timeout=5)
        env = dict(os.environ, LD_LIBRARY_PATH=str(LIBRARY))
        for key in ('LD_PRELOAD', 'LD_AUDIT', 'LD_PROFILE', 'LD_PROFILE_OUTPUT'):
            env.pop(key, None)
        # Original Hub emits ready to the coordinator's bound datagram socket.
        launch('coordinator', ros(['/mnt/net01/time_controller.py', '--ack-socket', inner + '/step.sock',
            '--output', inner + '/time-controller.json', '--session-id', '2026110912',
            '--execution-profile', PROFILE, '--hold-file', inner + '/HOLD',
            '--stop-file', inner + '/COORDINATOR_STOP']), 'TIME_CONTROL_READY ' + inner + '/step.sock')
        launch('hub', [sys.executable, '-B', str(REPO / 'net01/tools/packet_hub.py'),
            '--socket', str(base / 'wire.sock'), '--native', str(NATIVE), '--output', str(base / 'hub'),
            '--native-transport', 'tcp-mtu-v2', '--profile', ('C' if args.arm == 'C' else 'B'), '--wall', '55',
            '--clock-source', 'gazebo', '--control-trace', '--step-observer', str(base / 'step.sock')],
            'IPC_LISTENING ' + str(base / 'wire.sock'), env)
        tree = owned_tree(processes['hub'].pid)
        candidates = [row for row in tree.values() if row['argv'] and row['argv'][0] == str(NATIVE)]
        if len(candidates) != 1:
            raise RuntimeError('actual Hub native child missing/ambiguous')
        native = candidates[0]
        maps = Path('/proc', str(native['pid']), 'maps').read_text()
        exe = os.readlink(Path('/proc', str(native['pid']), 'exe'))
        mapped = {line.split(None, 5)[5] for line in maps.splitlines()
                  if len(line.split(None, 5)) == 6 and Path(line.split(None, 5)[5]).name.startswith('libns3.40-')}
        proof = dict(native=native, exe=exe, mapped_ns3_paths=sorted(mapped),
                     exact13_names={Path(path).name for path in mapped} == {'libns3.40-' + name + '.so' for name in MODULES},
                     all_expected_root=bool(mapped) and all(Path(path).resolve().parent == LIBRARY.resolve() for path in mapped),
                     executable_matches=Path(exe).resolve() == NATIVE.resolve(),
                     actual_parent_is_Hub=native['ppid'] == processes['hub'].pid,
                     inherited_ELF_SHA256='0cc771a18a3eb63ebbc4eb09ee942aaba27ea93211e07a7a0805d993dcc7c4f3')
        (base / 'native.maps.txt').write_text(maps)
        (base / 'native-load-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
        if not all(proof[key] for key in ('exact13_names', 'all_expected_root', 'executable_matches', 'actual_parent_is_Hub')):
            raise RuntimeError('original native/13DSO actual load gate failed')
        launch('peer', ros(['/mnt/net01d/replay_roles.py', '--role', 'peer', '--directory', inner + '/peer',
                            '--stop-file', stop, '--execution-profile', PROFILE]))
        launch('gateway', ros([prefix + 'collect_gateway.py', '--directory', inner + '/gateway',
                               '--stop-file', stop, '--mode', ('A' if args.arm == 'A1' else args.arm)] +
                              (['--dds-take-trace'] if args.dds_take_trace else [])),
               'COLLECTION_GATEWAY_READY')
        launch('servers', ros([prefix + 'action_servers.py', '--output', inner + '/servers.json',
                               '--stop-file', stop]), 'COLLECTION_ACTION_SERVERS_READY')
        launch('source', ros([prefix + 'recorded_source.py', '--corpus', '/mnt/net01e/replay/corpus-01',
                              '--output', inner + '/source', '--stop-file', stop]), 'RECORDED_SOURCE_READY')
        launch('client', ros([prefix + 'action_client.py', '--directory', inner + '/client',
            '--stop-file', stop, '--journal', inner + '/gateway/controller/allocation-events.jsonl',
            '--normal-done-file', inner + '/CLIENT_NORMAL_DONE.json']))
        launch('clock', ros([prefix + 'mock_clock.py', '--output', inner + '/mock-clock.json',
                             '--stop-file', stop]), 'REPLAY_MOCK_CLOCK_READY')
        while time.monotonic() < deadline - 12:
            if (base / 'FIRST_FAILURE.json').exists():
                raise RuntimeError('original Guard/transport fault in new collection')
            if any(process.poll() is not None for process in processes.values()):
                raise RuntimeError('owned role exited before collection phase complete')
            if ((base / 'source/NORMAL_INPUTS_PUBLISHED.json').exists()
                    and (base / 'CLIENT_NORMAL_DONE.json').exists()):
                break
            time.sleep(.005)
        else:
            raise TimeoutError('48wall collection work bound')
    except BaseException as exc:
        error = repr(exc)
    finally:
        (base / 'HOLD').write_text('new collection resource HOLD, not physical stop proof')
        until = min(deadline - 8, time.monotonic() + 2)
        while not (base / 'HOLD.ack').exists() and time.monotonic() < until:
            time.sleep(.005)
        if not (base / 'HOLD.ack').exists() and error is None:
            error = 'coordinator HOLD unconfirmed'
        (base / 'STOP').write_text('owned new collection resource stop')
        for role in ('source', 'servers', 'client', 'peer', 'gateway', 'clock', 'hub'):
            process = processes.get(role)
            if process is None:
                continue
            try:
                process.wait(timeout=max(.01, deadline - time.monotonic() - 2))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(); forced.append(role)
        (base / 'COORDINATOR_STOP').write_text('after actual native/Hub exit')
        process = processes.get('coordinator')
        if process is not None:
            try:
                process.wait(timeout=max(.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(); forced.append('coordinator')
        result = dict(error=error, forced=forced, wall_s=time.monotonic() - begin,
                      arm=args.arm,
                      dds_take_trace=args.dds_take_trace,
                      exits={role: process.returncode for role, process in processes.items()},
                      no_Gazebo=True, new_wire_recording=True, fixed_transport_arms_run=False)
        source_path = base / 'source/result.json'; wire_path = base / 'gateway/wire-records.jsonl'
        if source_path.exists() and wire_path.exists():
            inputs = json.loads(source_path.read_text())['inputs']
            captured = [json.loads(line) for line in wire_path.read_text().splitlines()]
            emitted = Counter((row['flow'], row['cdr_sha256']) for row in inputs if row['state'] == 'PUBLISHED')
            actual = Counter((row['flow'], row['cdr_sha256']) for row in captured)
            result['source_to_wire'] = dict(planned=len(inputs), published=sum(emitted.values()),
                not_published=sum(row['state'] != 'PUBLISHED' for row in inputs),
                source_content_units_without_wire_capture=sum((emitted - actual).values()),
                extra_wire_content_units=sum((actual - emitted).values()),
                repeated_source_content_groups=sum(count > 1 for count in emitted.values()),
                semantics='Multiset flow/CDR reconciliation, not exact per-ID DDS publication matching. '
                          'Identical body repetitions and other cmd_vel zero writers can be ambiguous; '
                          'no source-to-capture loss-rate PASS from content matching alone. '
                          'Dynamic BoundPeer/Action and other real wire sources are extra, not source duplicates.')
        (base / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        for stream in logs:
            stream.close()
    return int(error is not None or bool(forced) or any(p.returncode != 0 for p in processes.values()))


if __name__ == '__main__':
    raise SystemExit(main())

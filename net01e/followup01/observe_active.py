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
import threading

REPO = Path(__file__).resolve().parents[2]
BASELINE = Path('/home/zhuyulab/ns3-workspace/base-01-econ')
NATIVE = Path('/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp')
LIBRARY = NATIVE.parents[1] / 'build/lib'
PROFILE = 'controlled1000-clock100-q10ms-pace10-raster-simhealth'
sys.path.insert(0, str(REPO / 'net01d/followup02/native'))
from observe_lto_pair import proc, owned_tree, MODULES
sys.path.insert(0, str(REPO / 'net01'))
from execution_profile import CONTROLLED_PROFILE_IDS, load_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=('A1', 'B', 'C'), required=True)
    parser.add_argument('--dds-take-trace', action='store_true')
    parser.add_argument('--raw-destination', action='store_true')
    parser.add_argument('--steady-feedback', action='store_true')
    parser.add_argument('--native-state-sample', action='store_true')
    parser.add_argument('--native-evidence-ram', type=Path)
    parser.add_argument('--execution-profile', choices=CONTROLLED_PROFILE_IDS, default=PROFILE)
    parser.add_argument('--tail-corpus',type=Path)
    parser.add_argument('--mock-clock-initial-sim-ns',type=int,
                        choices=(47_000_000_000,49_000_000_000),default=49_000_000_000)
    args = parser.parse_args()
    if args.mock_clock_initial_sim_ns==47_000_000_000 and args.tail_corpus is None:
        raise ValueError('Common47sim replay requires the explicit source schedule/tail entry')
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
    sampler_thread = None; sampler_state = {}
    normal_shutdown_confirmed=False
    normal_lifecycle=dict(client_stop_request_monotonic_ns=None,client_stop_write_return_monotonic_ns=None,
                          actual_client_wait_return_monotonic_ns=None)
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
            '--execution-profile', args.execution_profile, '--hold-file', inner + '/HOLD',
            '--stop-file', inner + '/COORDINATOR_STOP']), 'TIME_CONTROL_READY ' + inner + '/step.sock')
        launch('hub', [sys.executable, '-B', str(REPO / 'net01/tools/packet_hub.py'),
            '--socket', str(base / 'wire.sock'), '--native', str(NATIVE), '--output', str(base / 'hub'),
            '--native-transport', 'tcp-mtu-v2', '--profile', ('C' if args.arm == 'C' else 'B'), '--wall', '55',
            '--clock-source', 'gazebo', '--control-trace', '--step-observer', str(base / 'step.sock')]+
            ([] if args.native_evidence_ram is None else ['--native-evidence-ram',str(args.native_evidence_ram)]),
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
        if args.native_state_sample:
            from native_state_sample import sample_owned_native
            sampler_ready = threading.Event()
            sampler_args = argparse.Namespace(pid=native['pid'], expected_start_ticks=native['start_ticks'],
                directory=base/'native-state', stop_file=base/'STOP', failure_file=base/'FIRST_FAILURE.json',
                work_deadline_ns=int((deadline-12)*1e9))
            def observe_native():
                try:
                    sampler_state['result'] = sample_owned_native(sampler_args, sampler_ready)
                except BaseException as sample_error:
                    sampler_state['error'] = repr(sample_error)
                finally:
                    sampler_state['finished'] = True
                    sampler_ready.set()
            sampler_thread = threading.Thread(target=observe_native, name='native-state-observer', daemon=True)
            sampler_thread.start()
            if not sampler_ready.wait(timeout=min(5.,max(0.,deadline-time.monotonic()))):
                raise RuntimeError('Native observer thread startup readiness not reached')
            if 'error' in sampler_state:
                raise RuntimeError('Native observer thread failed: '+sampler_state['error'])
        launch('peer', ros(['/mnt/net01d/replay_roles.py', '--role', 'peer', '--directory', inner + '/peer',
                            '--stop-file', stop, '--execution-profile', args.execution_profile]))
        gateway_extra=[]
        if args.execution_profile!=PROFILE:
            gateway_entry='/mnt/net01e/followup01/profiled_gateway.py'
            gateway_extra=['--execution-profile',args.execution_profile]
            if args.raw_destination:gateway_extra.append('--raw-destination')
        else:
            gateway_entry = '/mnt/net01e/followup01/' + ('raw_gateway_probe.py' if args.raw_destination else 'gateway_active_probe.py')
        launch('gateway', ros([gateway_entry, '--directory', inner + '/gateway',
                               '--stop-file', stop, '--mode', ('A' if args.arm == 'A1' else args.arm)] +
                              (['--dds-take-trace'] if args.dds_take_trace else [])+gateway_extra),
               'COLLECTION_GATEWAY_READY')
        servers_entry = ('/mnt/net01e/followup01/steady_action_servers.py'
                         if args.steady_feedback else prefix + 'action_servers.py')
        launch('servers', ros([servers_entry, '--output', inner + '/servers.json',
                               '--stop-file', stop]), 'COLLECTION_ACTION_SERVERS_READY')
        source_entry=prefix+'recorded_source.py'; source_extra=[]
        if args.tail_corpus is not None:
            source_entry='/mnt/net01e/followup01/recorded_with_tail.py'
            source_extra=['--tail-corpus','/mnt/'+str(args.tail_corpus.resolve().relative_to(REPO))]
        launch('source', ros([source_entry, '--corpus', '/mnt/net01e/replay/corpus-01',
                              '--output', inner + '/source', '--stop-file', stop]+source_extra), 'RECORDED_SOURCE_READY')
        launch('client', ros([prefix + 'action_client.py', '--directory', inner + '/client',
            '--stop-file', inner+'/CLIENT_STOP', '--journal', inner + '/gateway/controller/allocation-events.jsonl',
            '--normal-done-file', inner + '/CLIENT_NORMAL_DONE.json']))
        launch('normal_control',ros(['/mnt/net01e/followup01/normal_stop_control.py',
            '--directory',inner+'/normal-control','--trigger-file',inner+'/AUTHORITY_EXIT_CONFIRMED.json',
            '--ack-file',inner+'/STOP_OBSERVE_ACK.json','--stop-file',stop,
            '--work-deadline-ns',str(int((deadline-12)*1e9))]),'NORMAL_STOP_CONTROL_READY')
        clock_entry=prefix+'mock_clock.py';clock_extra=[]
        if args.mock_clock_initial_sim_ns!=49_000_000_000:
            clock_entry='/mnt/net01e/followup01/mock_clock.py'
            clock_extra=['--initial-sim-ns',str(args.mock_clock_initial_sim_ns)]
        launch('clock', ros([clock_entry, '--output', inner + '/mock-clock.json',
                             '--stop-file', stop]+clock_extra), 'REPLAY_MOCK_CLOCK_READY')
        while time.monotonic() < deadline - 12:
            if (base / 'FIRST_FAILURE.json').exists():
                raise RuntimeError('original Guard/transport fault in new collection')
            if sampler_state.get('finished'):
                raise RuntimeError('Native observer ended before collection complete: '+repr(sampler_state))
            if any(process.poll() is not None for process in processes.values()):
                raise RuntimeError('owned role exited before collection phase complete')
            if ((base / 'source/NORMAL_INPUTS_PUBLISHED.json').exists()
                    and (base / 'CLIENT_NORMAL_DONE.json').exists()):
                break
            time.sleep(.005)
        else:
            raise TimeoutError('48wall collection work bound')
        normal_lifecycle['client_stop_request_monotonic_ns']=time.monotonic_ns()
        (base/'CLIENT_STOP').write_text('Normal source window complete; close actual logical authority first')
        normal_lifecycle['client_stop_write_return_monotonic_ns']=time.monotonic_ns()
        remaining=deadline-12-time.monotonic()
        if remaining<=0:raise TimeoutError('Original work deadline before actual client exit')
        processes['client'].wait(timeout=min(2.,remaining))
        normal_lifecycle['actual_client_wait_return_monotonic_ns']=time.monotonic_ns()
        client_result=json.loads((base/'client/result.json').read_text())
        actual_results={row['robot']:row['status'] for row in client_result['records']
                        if row['kind']=='rl_actual_nav2_goal_result'}
        if (processes['client'].returncode!=0 or client_result['error'] is not None
                or not client_result['normal_done'] or actual_results!={'tb1':4,'tb2':4,'tb3':5}):
            raise RuntimeError('Actual client exit0 and matching three normal terminal results not established')
        if (base/'FIRST_FAILURE.json').exists():
            raise RuntimeError('Original Guard/transport fault before normal authority proof')
        authority=base/'AUTHORITY_EXIT_CONFIRMED.json'
        authority_temporary=authority.with_suffix('.tmp')
        with authority_temporary.open('x') as stream:
            stream.write(json.dumps(dict(client_pid=processes['client'].pid,
                client_exit=processes['client'].returncode,normal_done=client_result['normal_done'],
                actual_results=actual_results,monotonic_ns=time.monotonic_ns()))+'\n')
        authority_temporary.rename(authority)
        until=min(deadline-12,time.monotonic()+2.)
        while time.monotonic()<until:
            if (base/'FIRST_FAILURE.json').exists():
                raise RuntimeError('Original Guard/transport fault during normal revocation')
            if ((base/'STOP_OBSERVE_ACK.json').exists() and (base/'NORMAL_REVOKED_CLOSED.json').exists()):
                processes['normal_control'].wait(timeout=max(.001,until-time.monotonic()))
                if processes['normal_control'].returncode!=0:
                    raise RuntimeError('Actual public stop_observe control process failed')
                normal_shutdown_confirmed=True
                break
            if processes['normal_control'].poll() not in (None,0):
                raise RuntimeError('Actual public stop_observe request failed')
            time.sleep(.001)
        if not normal_shutdown_confirmed:
            raise TimeoutError('Original Guard revoked/PAUSE/empty ownership proof not observed in2wall/work bound')
    except BaseException as exc:
        error = repr(exc)
    finally:
        (base / 'HOLD').write_text('new collection resource HOLD, not physical stop proof')
        until = min(deadline - 8, time.monotonic() + 2)
        while not (base / 'HOLD.ack').exists() and time.monotonic() < until:
            time.sleep(.005)
        if not (base / 'HOLD.ack').exists() and error is None:
            error = 'coordinator HOLD unconfirmed'
        (base/'CLIENT_STOP').write_text('Owned authority resource close, no synthetic business result')
        (base / 'STOP').write_text('owned new collection resource stop')
        if sampler_thread is not None:
            sampler_thread.join(timeout=max(0.,min(1.,deadline-time.monotonic()-2)))
            if sampler_thread.is_alive():
                forced.append('native_observer_thread')
            if 'error' in sampler_state and error is None:
                error='Native observer failed: '+sampler_state['error']
        for role in ('source', 'servers', 'client', 'normal_control', 'peer', 'gateway', 'clock', 'hub'):
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
        profile_alignment=dict(expected=args.execution_profile, actual={}, aligned=False)
        try:
            actual_gateway=json.loads((base/'gateway/network-gateway.json').read_text())['execution_profile']
            actual_peer=json.loads((base/'peer/bound-mask-recording-saved.json').read_text())['execution_profile']
            actual_coordinator=json.loads((base/'time-controller.json').read_text())['final']
            profile_alignment['actual']=dict(gateway=actual_gateway['id'],peer=actual_peer,
                coordinator=actual_coordinator['execution_profile'])
            profile_alignment['actual_token_wall_period_ns']=dict(
                gateway=actual_gateway['token_wall_period_ns'],coordinator=actual_coordinator['token_wall_period_ns'])
            expected_token=load_profile(args.execution_profile)['token_wall_period_ns']
            profile_alignment['aligned']=(all(value==args.execution_profile for value in profile_alignment['actual'].values())
                and all(value==expected_token for value in profile_alignment['actual_token_wall_period_ns'].values()))
        except (FileNotFoundError,ValueError,KeyError) as profile_error:
            profile_alignment['error']=repr(profile_error)
        if not profile_alignment['aligned'] and error is None:
            error='Actual common execution profiles/token periods are not aligned'
        result = dict(error=error, forced=forced, wall_s=time.monotonic() - begin,
                      arm=args.arm,
                      dds_take_trace=args.dds_take_trace,
                      raw_destination=args.raw_destination,
                      steady_feedback=args.steady_feedback,
                      native_state_sample=args.native_state_sample,
                      native_evidence_ram=None if args.native_evidence_ram is None else str(args.native_evidence_ram),
                      native_observer=sampler_state,
                      execution_profile=args.execution_profile,
                      profile_alignment=profile_alignment,
                      normal_shutdown_confirmed=normal_shutdown_confirmed,
                      normal_lifecycle=normal_lifecycle,
                      tail_corpus=None if args.tail_corpus is None else str(args.tail_corpus),
                      mock_clock_initial_sim_ns=args.mock_clock_initial_sim_ns,
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
        tail_result=base/'source/tail-result.json'
        if tail_result.exists():
            tail=json.loads(tail_result.read_text())
            result['closing_tail']=dict(planned=tail['planned'],published=tail['published'],
                censored=tail['censored'],source_close_monotonic_ns=tail['source_close_monotonic_ns'],
                separate_from_main_input=True,scope=tail['scope'])
            if 'source_to_wire' in result:
                result['source_to_wire']['semantics']+=' Captured wire also includes separately ledgered closing-tail traffic; this is not an exact per-phase DDS loss calculation.'
        (base / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        for stream in logs:
            stream.close()
    return int(error is not None or bool(forced) or any(p.returncode != 0 for p in processes.values()))


if __name__ == '__main__':
    raise SystemExit(main())

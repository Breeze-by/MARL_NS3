#!/usr/bin/env python3
"""Actual packet_hub.main close-order qualification; no ROS or ns3 model."""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
sys.path.insert(0, str(REPO/'net01'))
from hub_client import HubClient


def wait_file(path, seconds=3):
    until = time.monotonic()+seconds
    while not path.exists():
        if time.monotonic()>=until:raise TimeoutError(str(path))
        time.sleep(.005)


def gone(pid):
    try:os.kill(pid, 0)
    except ProcessLookupError:return True
    return False


def native(args):
    # Stand-in protocol peer only: actual Hub owns this subprocess and END.
    (args.output/'fixture-native.json').write_text(json.dumps(dict(pid=os.getpid()))+'\n')
    print('READY', flush=True)
    for line in sys.stdin:
        if line == 'END\n':
            (args.output/'END_SEEN').write_text('END')
            wait_file(args.output/'ALLOW_EXIT', 8)
            return
        raise ValueError('stand-in accepts only END')


def hub(args):
    spec = importlib.util.spec_from_file_location('qualified_packet_hub', args.hub_source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original_write = Path.write_text
    if args.fifo:
        def blocked_write(path, data, *positional, **keywords):
            if path == args.output/'hub-ingress.json':
                original_write(args.output/'IO_BLOCK_BEGIN.json', json.dumps(dict(monotonic_ns=time.monotonic_ns()))+'\n')
                # Real synchronous FIFO open/write holds this Hub event loop.
                with args.fifo.open('wb') as stream:stream.write(b'controlled-poststop-IO')
                original_write(args.output/'IO_BLOCK_END.json', json.dumps(dict(monotonic_ns=time.monotonic_ns()))+'\n')
            return original_write(path, data, *positional, **keywords)
        Path.write_text = blocked_write
    namespace = argparse.Namespace(socket=args.socket, native=SELF, output=args.output,
        profile='B', native_transport='tcp-mtu-v2', native_ledger_mode='serial',
        finalize_hard_deadline_ns=None, wall=12, allow_radio_fault=False,
        clock_source='gazebo', control_trace=False, native_cpu_profile=False,
        native_evidence_ram=None, step_observer=None)
    try:asyncio.run(module.main(namespace))
    finally:Path.write_text = original_write


def client(args):
    connection = HubClient(args.socket)
    begin = time.monotonic_ns(); error = None
    try:
        connection.finish_poststop(begin+3_000_000_000)
    except (EOFError, ConnectionError, OSError) as caught:
        error = dict(type=type(caught).__name__, repr=repr(caught))
        raise
    finally:
        (args.output/'client-tail.bin').write_bytes(connection.finish_tail)
        (args.output/'client.json').write_text(json.dumps(dict(begin_monotonic_ns=begin,
            end_monotonic_ns=time.monotonic_ns(), state=connection.finish_state,
            error=error, deliveries=len(connection.deliveries)))+'\n')
        connection.close()


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    # Exact sealed predecessor, not a hand-written copy of the Hub algorithm.
    old = subprocess.run(['git', 'show', '2438808:net01/tools/packet_hub.py'],
                         cwd=REPO, capture_output=True, check=True).stdout
    old_source = args.output/'old-packet-hub-2438808.py'; old_source.write_bytes(old)
    results = []
    for mode in ('old', 'fixed', 'reset'):
        directory = args.output/mode; directory.mkdir()
        output = directory/'hub'; address = directory/'hub.sock'
        fifo = directory/'persist.fifo'
        if mode != 'reset':os.mkfifo(fifo)
        script = old_source if mode == 'old' else REPO/'net01/tools/packet_hub.py'
        logs = []
        def logfile(name):
            stream = (directory/name).open('wb'); logs.append(stream); return stream
        command = [sys.executable, '-B', str(SELF), '--role', 'hub', '--output', str(output),
            '--socket', str(address), '--hub-source', str(script)]
        if mode != 'reset':command += ['--fifo', str(fifo)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=logfile('hub.stderr'))
        consumer = None; connection = None
        try:
            if not select.select([process.stdout], [], [], 3)[0]:raise TimeoutError('actual Hub READY')
            assert process.stdout.readline().decode().strip() == 'IPC_LISTENING '+str(address)
            if mode == 'reset':
                connection = HubClient(address)
                connection.end(); connection.socket.setblocking(True)
                connection.socket.sendall(connection.outgoing); connection.outgoing.clear()
                wait_file(output/'native/END_SEEN')
                # Actual close with unread Hub READY bytes; no synthetic raise.
                connection.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                connection.close(); connection = None
                (output/'native/ALLOW_EXIT').write_text('allow')
            else:
                (output/'native/ALLOW_EXIT').write_text('allow')
                consumer = subprocess.Popen([sys.executable, '-B', str(SELF), '--role', 'client',
                    '--output', str(directory), '--socket', str(address)],
                    stdout=logfile('client.stdout'), stderr=logfile('client.stderr'))
                wait_file(output/'IO_BLOCK_BEGIN.json')
                # Declared deterministic test intervention, not historic timing.
                time.sleep(3.4)
                with fifo.open('rb') as stream:assert stream.read() == b'controlled-poststop-IO'
            hub_exit = process.wait(timeout=5)
            client_exit = None if consumer is None else consumer.wait(timeout=1)
            saved = json.loads((output/'result.json').read_text())
            state = saved['owner_shutdown']
            evidence = dict(mode=mode, hub_pid=process.pid, hub_exit=hub_exit,
                native_pid=json.loads((output/'native/fixture-native.json').read_text())['pid'],
                client_pid=None if consumer is None else consumer.pid, client_exit=client_exit,
                hub_status=saved['status'], owner_shutdown=state)
            assert (output/'hub-ingress.json').exists() and (output/'hub-deliveries.json').exists()
            if mode == 'reset':
                assert hub_exit != 0 and saved['status']=='FAIL' and state.get('owner_close_error')
                assert saved.get('error')
            else:
                received = json.loads((directory/'client.json').read_text())
                begin = json.loads((output/'IO_BLOCK_BEGIN.json').read_text())['monotonic_ns']
                end = json.loads((output/'IO_BLOCK_END.json').read_text())['monotonic_ns']
                evidence.update(client=received, controlled_IO_block_ns=end-begin)
                assert hub_exit==0 and saved['status']=='PASS' and state['owner_END_received']
                assert received['deliveries']==0 and end-begin>=3_400_000_000
                if mode == 'old':
                    assert client_exit != 0 and received['error']['type']=='TimeoutError'
                    assert not received['state']['peer_eof']
                else:
                    assert client_exit==0 and received['error'] is None and received['state']['peer_eof']
                    assert state['owner_close_completed_monotonic_ns'] <= begin
                    assert received['state']['peer_eof_monotonic_ns'] < end
            evidence['all_exact_PIDs_gone']=all(gone(pid) for pid in
                (process.pid,evidence['native_pid'],evidence['client_pid']) if pid is not None)
            assert evidence['all_exact_PIDs_gone']
            results.append(evidence)
        finally:
            if connection is not None:connection.close()
            for child in (consumer, process):
                if child is not None and child.poll() is None:child.kill();child.wait()
            pid_file=output/'native/fixture-native.json'
            if pid_file.exists():
                pid=json.loads(pid_file.read_text())['pid']
                if not gone(pid):os.kill(pid, signal.SIGKILL)
            for stream in logs:stream.close()
    (args.output/'result.json').write_text(json.dumps(dict(status='PASS', cases=results,
        scope='Controlled actual-Hub close-order component qualification, not Gazebo/native model or historical unique-cause proof.'),indent=2)+'\n')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=('hub','client'))
    parser.add_argument('--socket', type=Path)
    parser.add_argument('--hub-source', type=Path)
    parser.add_argument('--fifo', type=Path)
    parser.add_argument('--profile')
    parser.add_argument('--transport')
    args = parser.parse_args()
    if args.profile:native(args)
    elif args.role == 'hub':hub(args)
    elif args.role == 'client':client(args)
    else:raise SystemExit(main(args))

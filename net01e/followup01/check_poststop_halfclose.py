"""Bounded Unix IPC qualification of poststop END/EOF only; no ROS/native model."""
import argparse
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'net01'))
from hub_client import HubClient

TAIL = b'opaque-poststop-tail' * 131072
BODY = b'queued-before-END' * 65536


def peer(args):
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(args.socket)); listener.listen(1); listener.settimeout(5)
    args.ready.write_text('ready')
    connection, _ = listener.accept(); connection.settimeout(5)
    result = dict(mode=args.peer, END_received=False, client_write_EOF=False)
    try:
        if args.peer == 'success':
            # Large simultaneous output/input reproduces the duplex pressure.
            connection.sendall(TAIL)
            data = bytearray()
            while block := connection.recv(65536):
                data.extend(block)
            result['client_write_EOF'] = True
            frames = []
            while data:
                header, _, rest = data.partition(b'\n')
                meta = json.loads(header); size = meta['bytes']
                body = bytes(rest[:size]); data = bytearray(rest[size:])
                frames.append((meta, body))
            assert frames == [({'kind': 'test-queued', 'bytes': len(BODY)}, BODY),
                              ({'kind': 'end', 'bytes': 0}, b'')]
            result['END_received'] = True
        elif args.peer == 'no-eof':
            while block := connection.recv(65536):
                pass
            result['client_write_EOF'] = True
            # Keep our output side open beyond the client's single 3s budget.
            time.sleep(3.3)
        else:
            # Close with unread queued input: the client's transport must fail.
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    finally:
        connection.close(); listener.close()
        args.output.write_text(json.dumps(result)+'\n')


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for mode in ('success', 'no-eof', 'reset'):
        directory = args.output/mode; directory.mkdir()
        address = directory/'peer.sock'; ready = directory/'READY'
        process = subprocess.Popen([sys.executable, '-B', __file__, '--peer', mode,
            '--socket', str(address), '--ready', str(ready), '--output', str(directory/'peer.json')])
        client = None
        try:
            limit = time.monotonic()+2
            while not ready.exists():
                if process.poll() is not None or time.monotonic()>=limit:
                    raise RuntimeError('isolated peer did not become ready')
                time.sleep(.005)
            client = HubClient(address)
            client.frame(dict(kind='test-queued'), BODY)
            def forbidden(*unused):
                raise AssertionError('poststop tail must not enter business receive')
            client.receive = forbidden
            start = time.monotonic_ns(); deadline = start+3_000_000_000
            error = None
            try:
                client.finish_poststop(deadline)
            except (EOFError, ConnectionError, OSError) as caught:
                error = dict(type=type(caught).__name__, repr=repr(caught))
            elapsed = time.monotonic_ns()-start
            state = client.finish_state
            if mode == 'success':
                assert error is None and state['end_frame_flushed'] and state['write_half_closed'] and state['peer_eof']
                assert bytes(client.finish_tail) == TAIL
                assert state['return_monotonic_ns'] <= deadline
            elif mode == 'no-eof':
                assert error is not None and error['type']=='TimeoutError' and not state['peer_eof']
                assert state['deadline_monotonic_ns'] == deadline
                assert 2_900_000_000 <= elapsed < 3_300_000_000
            else:
                assert error is not None
            assert client.deliveries == []
            (directory/'opaque.bin').write_bytes(client.finish_tail)
            client.close(); client = None
            exit_code = process.wait(timeout=5)
            assert exit_code == 0
            peer_result = json.loads((directory/'peer.json').read_text())
            if mode == 'success':
                assert peer_result['END_received'] and peer_result['client_write_EOF']
            results.append(dict(mode=mode, elapsed_ns=elapsed, state=state,
                actual_error=error, peer_exit=exit_code, peer_pid=process.pid,
                peer_gone=process.poll() is not None, peer_result=peer_result))
        finally:
            if client is not None:client.close()
            if process.poll() is None:
                process.kill(); process.wait()
    (args.output/'result.json').write_text(json.dumps(dict(status='PASS', cases=results,
        scope='Explicit expected-negative component qualification; no ROS/native model or physical-safety claim.'), indent=2)+'\n')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--peer', choices=('success', 'no-eof', 'reset'))
    parser.add_argument('--socket', type=Path)
    parser.add_argument('--ready', type=Path)
    args = parser.parse_args()
    if args.peer:
        peer(args)
    else:
        raise SystemExit(main(args))

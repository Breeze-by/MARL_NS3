#!/usr/bin/env python3
"""Single-owner Unix IPC adapter for the actual native ns3 event process.

Only native RX supplies delivered body bytes. Control is limited to STEP/END;
the Unix socket is not a second data path between ROS consumers.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import time


async def read_frame(reader):
    line = await reader.readline()
    if not line:
        return None, None
    meta = json.loads(line)
    body = await reader.readexactly(meta.get("bytes", 0))
    return meta, body


def prepare_native_evidence(ram, destination):
    if not ram.is_absolute() or ram.parent != Path('/dev/shm'):
        raise ValueError('Native RAM evidence must be an exclusive direct /dev/shm child')
    space = os.statvfs('/dev/shm')
    available = space.f_bavail * space.f_frsize
    memory = next(int(line.split()[1]) * 1024 for line in
        Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if available < 16 * 1024**3 or memory < 24 * 1024**3:
        raise RuntimeError('Native RAM evidence requires 16GiB tmpfs and 24GiB MemAvailable')
    ram.mkdir(mode=0o700, exist_ok=False)
    return dict(backend='owned_tmpfs_then_copy_after_native_exit', source=str(ram),
        destination=str(destination), available_tmpfs_bytes=available,
        MemAvailable_bytes=memory, source_retained=True)


def copy_native_evidence(storage, native_exit, control_trace):
    started = time.monotonic()
    storage['native_exit'] = native_exit
    try:
        if native_exit is None:
            raise RuntimeError('Cannot copy evidence while actual native child is alive')
        source, destination = Path(storage['source']), Path(storage['destination'])
        files = {str(path.relative_to(source)): path.stat().st_size
            for path in source.rglob('*') if path.is_file()}
        storage.update(source_files=files, source_bytes=sum(files.values()))
        shutil.copytree(source, destination)  # New destination only; retain RAM even on failure.
        copied = {str(path.relative_to(destination)): path.stat().st_size
            for path in destination.rglob('*') if path.is_file()}
        storage.update(copied_files=copied, copied_bytes=sum(copied.values()))
        if files != copied:
            raise RuntimeError('Native evidence copied file/size set differs')
        required = {'configured-lock.json', 'packet-ledger.jsonl', 'ledger-status.json',
            'native-summary.json', *(f'wifi-{node}-0.pcap' for node in range(4))}
        if control_trace:
            required.add('control-step-trace.jsonl')
        if not required.issubset(files) or any(files[name] == 0 for name in required):
            raise RuntimeError('Native evidence is incomplete')
        ledger = json.loads((destination/'ledger-status.json').read_text())
        summary = json.loads((destination/'native-summary.json').read_text())
        if (native_exit != 0 or ledger['failed'] or
                not (ledger['attempted'] == ledger['captured'] == ledger['written']) or
                summary['counts'].get('transport_end') != 1):
            raise RuntimeError('Native evidence lacks successful END/complete ledger')
        storage['complete'] = True
    except Exception as error:
        storage.update(complete=False, error=repr(error))
        raise
    finally:
        storage['copy_wall_s'] = time.monotonic() - started


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    native_output = args.output / "native"
    storage = None
    if args.native_evidence_ram is None:
        native_output.mkdir()
    else:
        try:
            storage = prepare_native_evidence(args.native_evidence_ram, native_output)
        except Exception as error:
            (args.output/'result.json').write_text(json.dumps(dict(status='FAIL',
                phase='before_native_start', error=repr(error)), indent=2)+'\n')
            raise
        native_output = args.native_evidence_ram
    stderr = (args.output / "native.stderr.txt").open("xb")
    command = [str(args.native.resolve()), f"--output={native_output.resolve()}", f"--profile={args.profile}"]
    if args.control_trace:command.append('--controlTrace=1')
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE if args.control_trace else stderr)
    result = dict(argv=command, scope="Unix IPC to actual ns3 full-payload transport", status="FAIL")
    if storage is not None:result['native_evidence_storage'] = storage
    server = None
    owner = None
    finished = asyncio.Event()
    received_steps = asyncio.Queue()
    errors = []
    deliveries = []
    ingress = []
    next_message = 0
    known_horizon = 0
    control_trace=[]
    native_boundaries=[]
    native_stderr=[]
    step_observer=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) if args.step_observer else None
    if step_observer is not None:step_observer.setblocking(False)
    last_native_horizon=0
    def observe_native(kind,horizon):
        # Administrative progress only; never payload, goal or policy input.
        if step_observer is not None:
            step_observer.sendto(json.dumps(dict(kind=kind,horizon_ns=horizon,
                monotonic_ns=time.monotonic_ns())).encode(),str(args.step_observer))
    def control_event(kind,**fields):
        if args.control_trace:control_trace.append(dict(kind=kind,monotonic_ns=time.monotonic_ns(),**fields))

    async def native_diagnostics():
        while line := await process.stderr.readline():
            received=time.monotonic_ns()
            native_stderr.append(line)
            if line.startswith(b'NET01_CONTROL '):
                row=json.loads(line[len(b'NET01_CONTROL '):])
                row['hub_receive_monotonic_ns']=received
                native_boundaries.append(row)

    diagnostics_task=asyncio.create_task(native_diagnostics()) if args.control_trace else None

    async def native_rx():
        nonlocal last_native_horizon
        try:
            while line := await process.stdout.readline():
                words = line.decode().split()
                if words[0] == "RX":
                    sender, receiver, flow, mid, source, stamp, size = map(int, words[1:])
                    detailed=args.control_trace and (size>=16384 or flow in (31,51,71))
                    if detailed:control_event('hub_payload_read_begin',message_id=mid,bytes=size)
                    payload = await process.stdout.readexactly(size)
                    if await process.stdout.readexactly(1) != b"\n":
                        raise ValueError("Native body framing mismatch")
                    if detailed:control_event('hub_payload_read_end',message_id=mid,bytes=size)
                    meta = dict(kind="delivered", sender=sender, receiver=receiver, flow=flow,
                        message_id=mid, source_stamp_ns=source, ns3_rx_ns=stamp,
                        hub_receive_monotonic_ns=time.monotonic_ns(), bytes=size)
                    deliveries.append(meta)
                    if owner is None:
                        raise RuntimeError("Native delivery without an owned endpoint session")
                    if detailed:control_event('hub_owner_output_begin',message_id=mid,bytes=size)
                    owner.write(json.dumps(meta).encode()+b"\n"+payload)
                    await owner.drain()
                    if detailed:control_event('hub_owner_output_end',message_id=mid,bytes=size)
                elif words[0] == "STEP":
                    control_event('hub_native_STEP_received',horizon_ns=int(words[1]))
                    last_native_horizon=int(words[1])
                    observe_native('step',last_native_horizon)
                    await received_steps.put(int(words[1]))
                else:
                    raise ValueError("Unexpected native output")
        except BaseException as error:
            errors.append(repr(error))
            finished.set()

    async def endpoint(reader, writer):
        nonlocal owner, next_message, known_horizon
        if owner is not None:
            writer.close()
            return
        owner = writer
        try:
            writer.write(b'{"kind":"ready","bytes":0}\n')
            await writer.drain()
            while True:
                meta, body = await read_frame(reader)
                if meta is None:
                    raise RuntimeError("Owner disconnected without END")
                op = meta["kind"]
                if op == "send":
                    sender, receiver, flow = meta["sender"], meta["receiver"], meta["flow"]
                    if sender not in range(4) or receiver not in range(4) or sender == receiver or not body:
                        raise ValueError("Invalid endpoint route/body")
                    next_message += 1
                    source = meta.get("source_stamp_ns", 0)
                    ingress.append(dict(meta, native_message_id=next_message, hub_ingress_monotonic_ns=time.monotonic_ns()))
                    admission=meta.get("admission_ns")
                    if args.clock_source=="gazebo" and (admission is None or admission>known_horizon):
                        raise ValueError("Actual-clock source admission not established")
                    header=(f"SEND {sender} {receiver} {flow} {next_message} {source} {len(body)}\n" if admission is None else
                        f"SENDAT {sender} {receiver} {flow} {next_message} {source} {len(body)} {admission}\n")
                    health=args.control_trace and flow in (31,51,71)
                    if health:control_event('health_native_write_before',flow=flow,message_id=next_message)
                    process.stdin.write(header.encode()+body+b"\n")
                    if health:control_event('health_native_write_returned',flow=flow,message_id=next_message)
                    await process.stdin.drain()
                    if health:control_event('health_native_drain_returned',flow=flow,message_id=next_message)
                elif op=="observed_clock" and args.clock_source=="gazebo":
                    horizon=meta["horizon_ns"]
                    if horizon<known_horizon:raise ValueError("Actual observed clock rollback")
                    known_horizon=horizon
                    process.stdin.write(f"KNOWN {horizon}\n".encode());await process.stdin.drain()
                elif op=="position":
                    robot=meta["robot"];x,y,z=meta["xyz"]
                    process.stdin.write(f"POSITION {robot} {x:.17g} {y:.17g} {z:.17g}\n".encode());await process.stdin.drain()
                elif op == "clock":
                    horizon = meta["horizon_ns"]
                    control_event('hub_clock_frame_received',horizon_ns=horizon)
                    if args.clock_source=="gazebo" and horizon>known_horizon:raise ValueError("Network attempted to lead real /clock")
                    control_event('hub_native_STEP_write',horizon_ns=horizon)
                    process.stdin.write(f"STEP {horizon}\n".encode())
                    await process.stdin.drain()
                    control_event('hub_native_stdin_drain_returned',horizon_ns=horizon)
                    returned = await asyncio.wait_for(received_steps.get(), timeout=2)
                    writer.write(json.dumps(dict(kind="clock_return", horizon_ns=returned,
                        hub_clock_return_monotonic_ns=time.monotonic_ns(), bytes=0)).encode()+b"\n")
                    await writer.drain()
                    control_event('hub_clock_response_drain_returned',horizon_ns=returned)
                elif op == "radio_fault" and args.allow_radio_fault:
                    process.stdin.write(f"RADIO {int(meta['enabled'])}\n".encode())
                    await process.stdin.drain()
                elif op == "end":
                    process.stdin.write(b"END\n")
                    await process.stdin.drain()
                    process.stdin.close()
                    finished.set()
                    break
                else:
                    raise ValueError("Unsupported control; no payload bypass or arbitrary host operation")
        except BaseException as error:
            errors.append(repr(error))
            finished.set()

    try:
        if await asyncio.wait_for(process.stdout.readline(), timeout=10) != b"READY\n":
            raise RuntimeError("Native model did not become ready")
        observe_native('ready',0)  # Native initialized at0; no Run before READY.
        receive_task = asyncio.create_task(native_rx())
        server = await asyncio.start_unix_server(endpoint, path=str(args.socket))
        os.chmod(args.socket, 0o600)
        print("IPC_LISTENING "+str(args.socket),flush=True)
        await asyncio.wait_for(finished.wait(), timeout=args.wall)
        if errors:
            raise RuntimeError("; ".join(errors))
        native_exit = await asyncio.wait_for(process.wait(), timeout=10)
        await receive_task
        if native_exit:
            raise RuntimeError(f"Native exited {native_exit}")
        if errors:
            raise RuntimeError("; ".join(errors))
        result.update(status="PASS", native_exit=native_exit, ingress_messages=len(ingress),
            delivered_messages=len(deliveries))
    except BaseException as error:
        result["error"] = repr(error)
        raise
    finally:
        late_observer_error=None
        primary_failed='error' in result
        if server is not None:
            server.close()
            await server.wait_closed()
        if process.returncode is None:
            process.terminate()
            await process.wait()
        if owner is not None:
            owner.close()
        if step_observer is not None:
            try:observe_native('closed',last_native_horizon)
            except OSError as error:
                late_observer_error=error
                result['step_observer_close_error']=repr(error)
                result['status']='FAIL'
            finally:step_observer.close()
        if diagnostics_task is not None:
            await diagnostics_task
            stderr.writelines(native_stderr)
            (args.output/'native-control-boundaries.json').write_text(json.dumps(native_boundaries,indent=2)+'\n')
        stderr.close()
        (args.output/"hub-ingress.json").write_text(json.dumps(ingress, indent=2)+"\n")
        (args.output/"hub-deliveries.json").write_text(json.dumps(deliveries, indent=2)+"\n")
        if args.control_trace:(args.output/'hub-clock-control.json').write_text(json.dumps(control_trace,indent=2)+'\n')
        if args.socket.exists():
            args.socket.unlink()
        copy_error = None
        if storage is not None:
            try:copy_native_evidence(storage, process.returncode, args.control_trace)
            except Exception as error:
                copy_error = error
                result['native_evidence_error'] = repr(error)
                result.setdefault('error', repr(error))  # Keep the first runtime error.
                result['status'] = 'FAIL'
        (args.output/"result.json").write_text(json.dumps(result, indent=2)+"\n")
        if late_observer_error is not None and not primary_failed:
            raise late_observer_error
        if copy_error is not None and not primary_failed:
            raise copy_error


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("B", "C"), default="B")
    parser.add_argument("--wall", type=float, default=120)
    parser.add_argument("--allow-radio-fault", action="store_true", help="Independent no-motion negative fixture only")
    parser.add_argument("--clock-source", choices=("synthetic","gazebo"), default="synthetic")
    parser.add_argument('--control-trace',action='store_true')
    parser.add_argument('--native-evidence-ram',type=Path,
        help='Explicit owned /dev/shm directory; copy all native evidence after actual exit')
    parser.add_argument('--step-observer',type=Path,
        help='Explicit independent controlled-time receiver; only real native progress, no business data')
    asyncio.run(main(parser.parse_args()))

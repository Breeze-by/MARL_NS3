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
import time


async def read_frame(reader):
    line = await reader.readline()
    if not line:
        return None, None
    meta = json.loads(line)
    body = await reader.readexactly(meta.get("bytes", 0))
    return meta, body


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    stderr = (args.output / "native.stderr.txt").open("xb")
    native_output = args.output / "native"
    native_output.mkdir()
    command = [str(args.native.resolve()), f"--output={native_output.resolve()}", f"--profile={args.profile}"]
    if args.control_trace:command.append('--controlTrace=1')
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE if args.control_trace else stderr)
    result = dict(argv=command, scope="Unix IPC to actual ns3 full-payload transport", status="FAIL")
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
        try:
            while line := await process.stdout.readline():
                words = line.decode().split()
                if words[0] == "RX":
                    sender, receiver, flow, mid, source, stamp, size = map(int, words[1:])
                    detailed=args.control_trace and size>=16384
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
                    process.stdin.write(header.encode()+body+b"\n")
                    await process.stdin.drain()
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
        if server is not None:
            server.close()
            await server.wait_closed()
        if process.returncode is None:
            process.terminate()
            await process.wait()
        if owner is not None:
            owner.close()
        if diagnostics_task is not None:
            await diagnostics_task
            stderr.writelines(native_stderr)
            (args.output/'native-control-boundaries.json').write_text(json.dumps(native_boundaries,indent=2)+'\n')
        stderr.close()
        (args.output/"hub-ingress.json").write_text(json.dumps(ingress, indent=2)+"\n")
        (args.output/"hub-deliveries.json").write_text(json.dumps(deliveries, indent=2)+"\n")
        (args.output/"result.json").write_text(json.dumps(result, indent=2)+"\n")
        if args.control_trace:(args.output/'hub-clock-control.json').write_text(json.dumps(control_trace,indent=2)+'\n')
        if args.socket.exists():
            args.socket.unlink()


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
    asyncio.run(main(parser.parse_args()))

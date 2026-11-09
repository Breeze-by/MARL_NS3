#!/usr/bin/env python3
"""One bounded, actual ns3 WiFi full-byte fixture. No ROS, robot or model import."""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def generated_header(config):
    scalars = {
        "kSeed": config["rng_seed"], "kRun": config["rng_run"],
        "kQueuePackets": config["mac_queue_packets"], "kQueueDelay": config["mac_max_delay_sim_s"],
        "kMtu": config["mtu_bytes"], "kReferenceLoss": config["reference_loss_db"],
        "kExponentB": config["profiles"]["B"]["pathloss_exponent"],
        "kExponentC": config["profiles"]["C"]["pathloss_exponent"],
        "kTxB": config["profiles"]["B"]["tx_power_dbm"], "kTxC": config["profiles"]["C"]["tx_power_dbm"],
        "kReassemblyDeadline": config["reassembly_deadline_sim_s"],
    }
    rows = ["#pragma once"]
    for name, value in scalars.items():
        rows.append(f"constexpr {'unsigned' if isinstance(value, int) else 'double'} {name}={value};")
    positions = [config["ap_position_m"], *config["STA_static_prototype_positions_m"], config["central_node_position_m"]]
    rows.append("constexpr double kPositions[5][3]={" + ",".join("{" + ",".join(map(str, p)) + "}" for p in positions) + "};")
    rows.append('constexpr const char* kRawConfig=R"lock(' + json.dumps(config) + ')lock";')
    return "\n".join(rows) + "\n"


def fixture_input():
    commands = bytearray()
    messages, expected, blackout = {}, set(), set()
    horizon = 0
    next_id = 1

    def step(n=1):
        nonlocal horizon
        for _ in range(n):
            horizon += 100_000_000
            commands.extend(f"STEP {horizon}\n".encode())

    def send(sender, receiver, size, deliver=True, source=None):
        nonlocal next_id
        message_id = next_id
        next_id += 1
        # Mixed 0..255 bytes prevent a size/token-only proxy from matching content.
        payload = bytes((i * 37 + message_id * 19 + i // 251) % 256 for i in range(size))
        stamp = horizon if source is None else source
        commands.extend(f"SEND {sender} {receiver} 1 {message_id} {stamp} {size}\n".encode())
        commands.extend(payload + b"\n")
        messages[message_id] = dict(sender=sender, receiver=receiver, payload=payload, source_stamp_ns=stamp, ingress_horizon_ns=horizon)
        if deliver:
            expected.add(message_id)
        return message_id

    step(5)  # Actual WiFi association; no fabricated connected flags.
    for robot in (1, 2, 3):
        send(0, robot, 64)
        send(robot, 0, 64)
    step(5)  # These real byte messages also resolve ARP through the model.
    for robot in (1, 2, 3):
        for sender, receiver in ((0, robot), (robot, 0)):
            for size in (64, 55_000, 160_000):
                send(sender, receiver, size)
                step()
    concurrent_ids = []
    for robot in (1, 2, 3):
        concurrent_ids += [send(0, robot, 160_000), send(robot, 0, 160_000)]
    step(6)
    commands.extend(b"RADIO 0\n")
    for robot in (1, 2, 3):
        blackout.add(send(0, robot, 64, False))
        blackout.add(send(robot, 0, 64, False))
    step(8)  # Real MAC residence > locked500ms; no receive copying or side exit.
    commands.extend(b"RADIO 1\n")
    recovered = []
    for robot in (1, 2, 3):
        recovered += [send(0, robot, 64), send(robot, 0, 64)]
    step(6)
    damaged = next_id
    commands.extend(f"DISCARD {damaged} 1164\n".encode())
    send(0, 2, 160_000, False)  # Discard one actually received fragment, not a PHY claim.
    step(8)
    late_header = send(3, 0, 4096, source=1)  # Old header is not a schedule-into-the-past request.
    step(2)
    commands.extend(b"END\n")
    return bytes(commands), messages, expected, dict(blackout=sorted(blackout), concurrent=concurrent_ids,
        recovered=recovered, receiver_fault_message=damaged, late_source_message=late_header, end_horizon_ns=horizon)


def parse_output(raw):
    received, steps = {}, []
    pos = 0
    ready = False
    while pos < len(raw):
        end = raw.index(b"\n", pos)
        words = raw[pos:end].decode().split()
        pos = end + 1
        if words[0] == "READY":
            ready = True
        elif words[0] == "STEP":
            steps.append(int(words[1]))
        elif words[0] == "RX":
            sender, receiver, message_id, stamp, size = map(int, words[1:])
            if message_id in received:
                raise AssertionError("Duplicate whole-message output")
            payload = raw[pos:pos+size]
            pos += size
            if raw[pos:pos+1] != b"\n":
                raise AssertionError("Invalid receiver byte framing")
            pos += 1
            received[message_id] = dict(sender=sender, receiver=receiver, rx_ns=stamp, payload=payload)
        else:
            raise AssertionError("Unknown native output frame")
    return ready, received, steps


def pcap_summary(path):
    # Native PCAP record framing and actual NET1 wire bytes, not a synthetic counter.
    with path.open("rb") as stream:
        header = stream.read(24)
        endian = "<" if header[:4] == b"\xd4\xc3\xb2\xa1" else ">"
        magic, major, minor, _, _, snaplen, linktype = struct.unpack(endian+"IHHIIII", header)
        if magic != 0xa1b2c3d4 or (major, minor) != (2, 4):
            raise AssertionError("Unsupported actual pcap header")
        count = net1 = octets = 0
        while record := stream.read(16):
            sec, usec, size, original = struct.unpack(endian+"IIII", record)
            frame = stream.read(size)
            if len(frame) != size:
                raise AssertionError("Truncated actual pcap")
            count += 1
            octets += size
            net1 += b"NET1" in frame
    return dict(path=str(path), records=count, frame_octets=octets, frames_containing_net1=net1, linktype=linktype)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ns3", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    build = args.build.resolve()
    build.mkdir(parents=True, exist_ok=True)
    config_path = ROOT / "config/NETWORK_LOCK_V3.json"
    config = json.loads(config_path.read_text())
    (out / "fixed-config.json").write_bytes(config_path.read_bytes())
    (build / "network_config.h").write_text(generated_header(config))
    result = dict(scope="Independent actual ns3 full-payload WiFi; controlled synthetic clock ONLY, no ROS/Action/Gazebo/safety certification",
        status="FAIL", ROS_Node=0, Gazebo=0, NN=0, host_network_changes=0, phases=[])
    try:
        for label, command in [
            ("configure", ["cmake", "-S", str(ROOT/"native"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", f"-DNS3_DIR={args.ns3.resolve()}", f"-DCONFIG_HEADER_DIR={build}"]),
            ("build", ["cmake", "--build", str(build), "-j2"]),
        ]:
            with (out / f"{label}.stdout.txt").open("x") as stdout, (out / f"{label}.stderr.txt").open("x") as stderr:
                finished = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=120)
            result["phases"].append(dict(name=label, argv=command, native_exit=finished.returncode))
            if finished.returncode:
                raise RuntimeError(f"{label} native exit {finished.returncode}")
        native = out / "native"
        native.mkdir()
        command = [str(build/"net01-payload"), f"--output={native}", "--profile=B"]
        data, messages, expected, cases = fixture_input()
        (out / "fixture-operations.json").write_text(json.dumps(dict(cases, messages=[dict(id=i, **{k:v for k,v in m.items() if k!="payload"}, bytes=len(m["payload"])) for i,m in messages.items()]), indent=2)+"\n")
        started = time.monotonic()
        process = subprocess.run(command, input=data, capture_output=True, timeout=90)
        (out / "native-output.bin").write_bytes(process.stdout)
        (out / "native.stderr.txt").write_bytes(process.stderr)
        result["phases"].append(dict(name="actual_native_wifi", argv=command, native_exit=process.returncode, wall_s=time.monotonic()-started))
        if process.returncode:
            raise RuntimeError(f"actual native WiFi exit {process.returncode}")
        ready, received, steps = parse_output(process.stdout)
        if set(received) != expected:
            raise AssertionError(f"Whole-message set differs: missing={sorted(expected-set(received))}, unexpected={sorted(set(received)-expected)}")
        for message_id, rx in received.items():
            tx = messages[message_id]
            if rx["payload"] != tx["payload"] or (rx["sender"], rx["receiver"]) != (tx["sender"], tx["receiver"]):
                raise AssertionError(f"Actual whole bytes or flow mismatch {message_id}")
            if rx["rx_ns"] < tx["ingress_horizon_ns"]:
                raise AssertionError("Message scheduled into source-header past")
        records = [json.loads(line) for line in (native/"packet-ledger.jsonl").read_text().splitlines()]
        deliveries = [r for r in records if r["kind"] == "message_deliver"]
        actual_fragments = [r for r in records if r["kind"] == "udp_rx"]
        if any(r["ns3_ns"] > cases["end_horizon_ns"] for r in records):
            raise AssertionError("Model ahead of known test horizon")
        if not any(r["kind"] == "test_receiver_discard_fragment" for r in records) or not any(r["kind"] == "incomplete_expired" and r["message_id"] == cases["receiver_fault_message"] for r in records):
            raise AssertionError("Missing actual receive fragment-discard/expiry evidence")
        if not any(r["kind"] == "wifi_sniffer_rx" for r in records):
            raise AssertionError("No real WiFi RX PHY trace")
        pcaps = [pcap_summary(path) for path in sorted(native.glob("*.pcap"))]
        if len(pcaps) != 4 or not all(p["frames_containing_net1"] > 0 for p in pcaps):
            raise AssertionError("No real payload PCAP on each AP/STA")
        result.update(status="PASS", ready=ready, fixed_config=str(config_path), message_count=len(messages),
            completed_exact_messages=len(received), complete_payload_bytes=sum(len(r["payload"]) for r in received.values()),
            actual_udp_received_fragments=len(actual_fragments), native_summary=json.loads((native/"native-summary.json").read_text()),
            checks=dict(all_three_STA_bidirectional=True, sizes_bytes=[64,55000,160000], six_large_simultaneous=True,
                whole_received_bytes_exact=True, radio_off_no_whole_delivery=True, recovery_new_messages_exact=True,
                incomplete_received_fragment_not_delivered=True, source_stamp_not_schedule_time=True,
                max_test_horizon_step_ns=100_000_000, actual_PHY_MAC_packets=True, no_source_blob_lookup=True),
            pcap=pcaps, limits=["Synthetic controlled ticks do not validate real Gazebo clock or wall heartbeat", "Receiver fragment discard is an explicit reassembly fault, not a claimed PHY loss model", "Only independent packet transport; no ROS Action, no-network-bypass ROS graph or network safety PASS"])
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        with (out / "result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()

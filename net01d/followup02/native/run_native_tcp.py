"""Three explicit, separately admitted native-only cases. Never starts ROS/Gazebo."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "net01"))
from hub_client import HubClient

CASES = {"stream-01": "ntcp-s1", "radio-01": "ntcp-r1", "budget-01": "ntcp-q1"}
ROUTES = [(0, 1), (1, 0), (0, 2), (2, 0), (0, 3), (3, 0)]


def body_for(rpc, size):
    pattern = bytes((rpc + i * 17) % 256 for i in range(256))
    return (pattern * ((size + 255) // 256))[:size]


def ledger_summary(path):
    counts = Counter()
    intervals = defaultdict(list)
    overlap_rows, partial_rows = [], []
    attributes, budget_rows = [], []
    carries = defaultdict(int)
    read_groups, active_reads = [], {}
    for line in path.open():
        row = json.loads(line)
        kind = row["kind"]
        counts[kind] += 1
        if kind == "tcp_stream_read":
            key = (row["local"], row["remote"])
            if key in active_reads:
                read_groups.append(dict(active_reads.pop(key), carry_after=carries[key]))
            active_reads[key] = dict(local=key[0], remote=key[1], ns3_ns=row["ns3_ns"],
                                     received_bytes=row["bytes"], carry_before=carries[key],
                                     decoded_frames=0)
            carries[key] += row["bytes"]
        elif kind == "tcp_frame_rx":
            key = (row["to"], row["from"])
            carries[key] -= 36 + row["body_bytes"]
            if carries[key] < 0:
                raise ValueError("Actual Recv/frame byte accounting underflow")
            active_reads[key]["decoded_frames"] += 1
        if kind == "tcp_write" and row["frame_offset"] and len(partial_rows) < 12:
            partial_rows.append(row)
        if kind in ("tcp_default_attributes", "tcp_effective_attributes"):
            attributes.append(row["attributes"])
        if kind == "tcp_queue_budget_exceeded":
            budget_rows.append(row)
        if kind != "tcp_tx" or not row["payload_bytes"]:
            continue
        key = (row["local"], row["remote"])
        low, high = row["tcp_seq"], row["tcp_seq"] + row["payload_bytes"]
        covered = intervals[key]
        overlap = sum(max(0, min(high, b) - max(low, a)) for a, b in covered)
        if overlap and row["ns3_ns"] >= 4_220_000_000 and len(overlap_rows) < 24:
            overlap_rows.append(dict(row, previously_transmitted_overlap_bytes=overlap))
        merged = []
        for a, b in sorted([*covered, (low, high)]):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        intervals[key] = merged
    for key, row in active_reads.items():
        read_groups.append(dict(row, carry_after=carries[key]))
    split = [r for r in read_groups if r["carry_before"] and r["decoded_frames"]]
    coalesced = [r for r in read_groups if r["decoded_frames"] > 1]
    return dict(counts=dict(counts), partial_frame_writes=partial_rows,
                actual_overlapping_TCP_sequence_extents=overlap_rows,
                default_attributes=attributes, budget_errors=budget_rows,
                Recv=dict(read_count=len(read_groups), split_completion_reads=len(split),
                          coalesced_reads=len(coalesced),
                          split_branch="OBSERVED" if split else "NOT OBSERVED",
                          coalesced_branch="OBSERVED" if coalesced else "NOT OBSERVED",
                          split_examples=split[:6], coalesced_examples=coalesced[:6],
                          remaining_carry=[dict(local=k[0], remote=k[1], bytes=v)
                                           for k, v in carries.items()]))


def main(case, native, output_name=None, native_transport="tcp-v1",
         native_ledger_mode="serial", finalize_hard_deadline_ns=None):
    name = output_name or CASES[case]
    output, ram = BASE / "runs" / name, Path("/dev/shm") / ("net01d-f02-" + name)
    output.mkdir(parents=True, exist_ok=False)
    if ram.exists():
        raise FileExistsError(ram)
    started = time.monotonic()
    deadline = started + 20
    result = dict(case=case, scope="Opaque native stream bytes, not generated ROS/Action/CDR",
                  status="RUNNING", ROS_init=0, Node=0, Gazebo=0, NN=0, training=0,
                  target_sim_s=0 if case == "budget-01" else 8, active_wall_bound_s=20,
                  total_wall_bound_s=30, TCP_attributes_changed=native_transport == "tcp-mtu-v2",
                  native_transport=native_transport,
                  native=str(native), RAM_source=str(ram),
                  raw_native_failure_preserved=True, deadline_pass_claim=False)
    if finalize_hard_deadline_ns is not None:
        result.update(finalize_hard_deadline_ns=finalize_hard_deadline_ns,
            total_wall_bound_s=(finalize_hard_deadline_ns-time.monotonic_ns())/1e9,
            native_ledger_mode=native_ledger_mode,
            post_END_wait_scope='Opt-in remaining absolute whole-case deadline; active20/ENDflush1 unchanged; old default5/start27 unchanged without argument')
    submitted, received, expected, checks = [], [], {}, {}
    hub = client = None
    resources = dict(forced_signals=[])
    hub_stdout = hub_stderr = None

    def owned_group_exists():
        if hub is None:
            return False
        try:
            os.killpg(hub.pid, 0)
            resources["owned_PG_probe"] = "EXISTS"
            return True
        except ProcessLookupError:
            resources["owned_PG_probe"] = "ESRCH"
            return False

    def owned_native_running():
        running = []
        if hub is None:
            return running
        for pid in resources.get("actual_native_child_pids", []):
            path = Path("/proc") / pid
            try:
                command = path.joinpath("cmdline").read_bytes().split(b"\0")
                state = path.joinpath("stat").read_text().rsplit(") ", 1)[1].split()[0]
                if (command[0] == os.fsencode(native) and os.getpgid(int(pid)) == hub.pid
                        and state != "Z"):
                    running.append(int(pid))
            except (FileNotFoundError, ProcessLookupError):
                pass
        return running

    def hard_stop(signum, frame):
        if owned_group_exists():
            os.killpg(hub.pid, signal.SIGKILL)
            resources["forced_signals"].append("EXTERNAL_HARD_BOUND_KILL_OWNED_PG")
        raise TimeoutError("External native-case hard bound")

    signal.signal(signal.SIGTERM, hard_stop)

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)

    def pump():
        if time.monotonic() >= deadline:
            raise TimeoutError("20wall native case active bound")
        if hub.poll() is not None:
            if case == "budget-01":
                time.sleep(.0005)
                return  # Validate the actual budget error, never accept arbitrary failure.
            raise RuntimeError("Owned Hub exited before case completion")
        try:
            client.poll()
        except (EOFError, BrokenPipeError, ConnectionResetError) as error:
            if case != "budget-01":
                raise
            resources["budget_IPC_close_observed"] = repr(error)
        time.sleep(.0005)  # Host I/O polling only; no paced-wall timing claim.

    def until(predicate):
        while not predicate():
            pump()

    def submit(sender, receiver, flow, rpc, size, source):
        body = body_for(rpc, size)
        expected[rpc] = (sender, receiver, flow, source, body)
        submitted.append(dict(sender=sender, receiver=receiver, flow=flow, rpc_id=rpc,
                              bytes=size, source_stamp_ns=source,
                              sha256=hashlib.sha256(body).hexdigest(),
                              requested_at_horizon_ns=client.horizon_ns))
        client.send(sender, receiver, flow, body, rpc, source_stamp_ns=source)

    def receive(meta, body, rpc):
        actual_file = output / "received" / (str(rpc) + ".bin")
        with actual_file.open("xb") as stream:
            stream.write(body)  # Preserve actual received bytes before checking.
        sender, receiver, flow, source, wanted = expected[rpc]
        equal = (body == wanted and meta["sender"] == sender and
                 meta["receiver"] == receiver and meta["flow"] == flow and
                 meta["source_stamp_ns"] == source)
        received.append(dict(meta, rpc_id=rpc, body_bytes=len(body),
                             actual_body_sha256=hashlib.sha256(body).hexdigest(),
                             exact_body_route_source_equal=equal))
        check("actual_RX_" + str(rpc), equal)

    try:
        if not native.is_absolute() or not native.is_file():
            raise FileNotFoundError(native)
        (output / "received").mkdir()
        command = [sys.executable, "-B", str(REPO / "net01/tools/packet_hub.py"),
                   "--socket", str(output / "wire.sock"), "--native", str(native),
                   "--native-transport", native_transport, "--output", str(output / "hub"),
                   "--profile", "B", "--wall", "25", "--control-trace",
                   "--native-evidence-ram", str(ram)]
        if native_ledger_mode!="serial":command += ["--native-ledger-mode",native_ledger_mode]
        if finalize_hard_deadline_ns is not None:
            command += ["--finalize-hard-deadline-ns",str(finalize_hard_deadline_ns)]
        if case == "radio-01":
            command += ["--allow-radio-fault"]
        with (output / "argv.json").open("x") as stream:
            json.dump(command, stream, indent=2)
        hub_stdout = (output / "hub.stdout.log").open("x")
        hub_stderr = (output / "hub.stderr.log").open("x")
        hub = subprocess.Popen(command, stdout=hub_stdout, stderr=hub_stderr,
                               start_new_session=True)
        resources.update(hub_pid=hub.pid, hub_pgid=hub.pid)
        while not (output / "wire.sock").exists():
            if hub.poll() is not None:
                raise RuntimeError("Owned Hub failed before IPC listen")
            if time.monotonic() >= deadline:
                raise TimeoutError("Owned Hub startup bound")
            time.sleep(.005)
        children = Path(f"/proc/{hub.pid}/task/{hub.pid}/children")
        resources["actual_native_child_pids"] = children.read_text().split()
        client = HubClient(output / "wire.sock")
        client.receive = receive
        until(lambda: client.ready)
        if case == "budget-01":
            # 8MiB body plus original RPC/fragment headers exceeds fixed 8MiB.
            submit(0, 3, 70, 9001, 8 * 1024 * 1024, 0)
            until(lambda: not client.outgoing)
            until(lambda: (ram / "transport-config.json").exists())
        else:
            for i, (sender, receiver) in enumerate(ROUTES):
                submit(sender, receiver, 500 + i, 1000 + i, 64, 0)
            for horizon in range(10_000_000, 8_000_000_001, 10_000_000):
                if horizon == 4_010_000_000:
                    check("six_real_bidirectional_TCP_RX_before_business",
                          {row["rpc_id"] for row in received} == set(range(1000, 1006)))
                    # IPC READY is deliberately not the handshake certificate.
                    if case == "stream-01":
                        for i, (sender, receiver) in enumerate(ROUTES):
                            submit(sender, receiver, 600 + i, 2000 + i, 160704, 4_000_000_000)
                            submit(sender, receiver, 700 + i, 3000 + i, 1024 * 1024, 4_000_000_000)
                if case == "radio-01":
                    if horizon == 4_210_000_000:
                        client.radio_fault(False)  # Actual native Range gate at N4.20.
                    if horizon == 4_230_000_000:
                        for i, (sender, receiver) in enumerate(ROUTES):
                            submit(sender, receiver, 600 + i, 2000 + i, 160704, 4_220_000_000)
                    if horizon == 4_310_000_000:
                        client.radio_fault(True)  # Actual native restore at N4.30.
                client.clock(horizon)
                until(lambda: client.horizon_ns == horizon)
            check("fixed8sim_reached", client.horizon_ns == 8_000_000_000)
            check("all_original_messages_received_exactly_once",
                  Counter(row["rpc_id"] for row in received) == Counter(expected.keys()))
    except BaseException as error:
        result.update(status="FAIL", first_error=repr(error))
    finally:
        if client is not None:
            try:
                if hub.poll() is None:
                    client.end()
                    end_deadline = min(started + 22, time.monotonic() + 1)
                    while client.outgoing and time.monotonic() < end_deadline:
                        client.poll()
                        time.sleep(.0005)
                resources["END_frame_flushed"] = not client.outgoing
            except (OSError, EOFError) as error:
                resources["IPC_close_error"] = repr(error)
            finally:
                client.close()
        if hub is not None:
            try:
                hub.wait(timeout=(max(0.,(finalize_hard_deadline_ns-time.monotonic_ns())/1e9)
                    if finalize_hard_deadline_ns is not None else
                    max(.01, min(5, started + 27 - time.monotonic()))))
            except subprocess.TimeoutExpired:
                os.killpg(hub.pid, signal.SIGTERM)
                resources["forced_signals"].append("SIGTERM_OWNED_PG")
                try:
                    hub.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(hub.pid, signal.SIGKILL)
                    resources["forced_signals"].append("SIGKILL_OWNED_PG")
                    hub.wait(timeout=1)
            resources["hub_exit"] = hub.returncode
            if owned_group_exists():
                os.killpg(hub.pid, signal.SIGKILL)
                resources["forced_signals"].append("SIGKILL_REMAINING_OWNED_NATIVE_PG")
                end = time.monotonic() + .5
                while owned_native_running() and time.monotonic() < end:
                    time.sleep(.01)
            resources["remaining_owned_native"] = owned_native_running()
            resources["owned_PG_exists_after_cleanup"] = owned_group_exists()
        if hub_stdout is not None:
            hub_stdout.close()
            hub_stderr.close()
        result.update(checks=checks, submitted=submitted, received=received,
                      resources=resources, wall_s=time.monotonic() - started)
        with (output / "process-result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
    # Analyze exactly this case's native ledger once, after its process exited.
    hub_result = {}
    try:
        summary = ledger_summary(ram / "packet-ledger.jsonl")
        config = json.loads((ram / "transport-config.json").read_text())
        hub_result = json.loads((output / "hub/result.json").read_text())
        result.update(native_ledger_summary=summary, native_config=config, raw_Hub_result=hub_result)
        if result["status"] != "FAIL":
            if case == "budget-01":
                check("actual_native_budget_failure_no_partial_admission",
                      len(summary["budget_errors"]) == 1 and not received and
                      config["end_state"]["queued_frames"] == 0 and
                      config["end_state"]["queued_unsent_bytes"] == 0 and
                      summary["counts"].get("tcp_write", 0) == 0 and
                      hub_result["native_evidence_storage"]["native_exit"] == 1 and
                      not resources["forced_signals"] and not resources["remaining_owned_native"])
                result["status"] = "EXPECTED_BUDGET_ERROR"
            else:
                check("actual_three_connected_and_accepted",
                      summary["counts"].get("tcp_connected") == 3 and
                      summary["counts"].get("tcp_accepted") == 3)
                check("actual_selected_transport", config["transport"] == native_transport)
                if native_transport == "tcp-mtu-v2":
                    effective = config["attributes"] + config["listener_attributes"]
                    check("v2_all_listener_and_endpoint_effective_attributes",
                          len(config["attributes"]) == 6 and len(config["listener_attributes"]) == 3
                          and config["TCP_attributes_changed"] is True
                          and config["configured_overrides"] == {"SegmentSize": 1448}
                          and all(a["SegmentSize"] == 1448 and a["InitialCwnd_segments"] == 10
                                  and a["InitialCwnd_bytes"] == 14480
                                  and a["Timestamp"] and a["Sack"] and a["WindowScaling"]
                                  and a["SndBufSize"] == 131072 and a["RcvBufSize"] == 131072
                                  and a["MinRto_ns"] == 1_000_000_000
                                  and a["ConnTimeout_ns"] == 3_000_000_000
                                  and a["DelAckTimeout_ns"] == 200_000_000
                                  and a["TcpNoDelay"] and a["SocketType"] == "ns3::TcpCubic"
                                  for a in effective))
                check("actual_partial_frame_send_path", bool(summary["partial_frame_writes"]))
                check("actual_native_success_no_forced_cleanup",
                      hub_result["native_exit"] == 0 and resources["hub_exit"] == 0
                      and hub_result["status"] == "PASS"
                      and hub_result["native_evidence_storage"]["complete"] is True
                      and not hub_result.get("error") and not hub_result.get("native_evidence_error")
                      and not resources["forced_signals"]
                      and not resources["remaining_owned_native"])
                check("actual_Recv_carry_equals_END_partial_stream_state",
                      all(next(e["partial_stream_bytes"] for e in config["end_state"]["endpoints"]
                               if (e["local"], e["remote"]) == (r["local"], r["remote"])) == r["bytes"]
                          for r in summary["Recv"]["remaining_carry"]))
                if case == "radio-01":
                    check("real_channel_blackout_and_restore",
                          summary["counts"].get("channel_blackout") == 1 and
                          summary["counts"].get("channel_restored") == 1)
                    check("actual_TCP_overlapping_sequence_retransmission_after_business_blackout",
                          bool(summary["actual_overlapping_TCP_sequence_extents"]))
                result["status"] = "PASS_NATIVE_BYTES_ONLY"
    except BaseException as error:
        result["status"] = "FAIL"
        result.setdefault("first_error", repr(error))
    finally:
        result["wall_s"] = time.monotonic() - started
        if finalize_hard_deadline_ns is not None and time.monotonic_ns()>=finalize_hard_deadline_ns:
            result["status"]="FAIL"
            result.setdefault("first_error","Opt-in absolute whole-case deadline exceeded")
        with (output / "result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(dict(status=result["status"], case=case, wall_s=result["wall_s"],
                          original_native_failure=hub_result.get("error"))))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(CASES), required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output-name", help="Exclusive output/RAM case name; original defaults unchanged")
    parser.add_argument("--native-transport", choices=("tcp-v1", "tcp-mtu-v2"), default="tcp-v1")
    parser.add_argument("--native-ledger-mode",choices=("serial","session-ram-v1"),default="serial")
    parser.add_argument("--finalize-hard-deadline-ns",type=int,
        help="Test opt-in absolute whole-case monotonic deadline; replaces only post-END Hub wait")
    args = parser.parse_args()
    raise SystemExit(main(args.case,args.native,args.output_name,args.native_transport,
        args.native_ledger_mode,args.finalize_hard_deadline_ns))

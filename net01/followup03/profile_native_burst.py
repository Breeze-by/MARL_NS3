#!/usr/bin/env python3
"""One fixed native-only CPU observation, not ROS/WiFi capacity acceptance."""
import argparse
import json
import os
import resource
from pathlib import Path
import signal
import subprocess
import sys
import time

TOOLS=Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(TOOLS))
from check_network import parse_output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--native",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--no-cpu-profile",action="store_true")
    parser.add_argument("--async-ledger",action="store_true")
    parser.add_argument("--compare",type=Path)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False)
    native_dir=args.output/"native";native_dir.mkdir()
    commands=bytearray();messages={};next_id=1
    def send(sender,receiver,flow,size):
        nonlocal next_id
        body=(bytes(range(256))*((size+255)//256))[:size]
        commands.extend(f"SEND {sender} {receiver} {flow} {next_id} 0 {size}\n".encode()+body+b"\n")
        messages[next_id]=dict(sender=sender,receiver=receiver,flow=flow,bytes=size,payload=body)
        next_id+=1
    for tick in range(1,6):commands.extend(f"STEP {tick*100000000}\n".encode())
    for robot in (1,2,3):
        send(0,robot,65535,64);send(robot,0,65534,64)
    for tick in range(6,11):commands.extend(f"STEP {tick*100000000}\n".encode())
    # Exact initial large-message sizes from sealed continuous15; opaque bytes,
    # not claimed ROS fields. Only this final 100ms STEP is the CPU target.
    for robot in (1,2,3):
        send(0,robot,robot*20+10,160611)
        send(robot,0,robot*20+1,55112)
    commands.extend(b"STEP 1100000000\nEND\n")
    (args.output/"input.commands.bin").write_bytes(commands)
    (args.output/"input-scope.json").write_text(json.dumps(dict(
        mode="B locked V3",warmup_end_ns=1000000000,measured_step_end_ns=1100000000,
        messages=[dict(id=k,**{key:value for key,value in m.items() if key!="payload"}) for k,m in messages.items()],
        no_ROS=True,no_Gazebo=True,no_Goal=True,no_NN=True,
        purpose="CPU hotspots only; no real-time, AoI, safety or sustained load PASS"),indent=2)+"\n")
    argv=[str(args.native.resolve()),f"--output={native_dir.resolve()}","--profile=B","--controlTrace=1",
        f"--cpuProfile={int(not args.no_cpu_profile)}",f"--asyncLedger={int(args.async_ledger)}"]
    usage_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    start=time.monotonic();process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True)
    error=None
    try:stdout,stderr=process.communicate(bytes(commands),timeout=18)
    except subprocess.TimeoutExpired:
        error="native measurement exceeded18wall; owned group killed"
        os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
    usage_after=resource.getrusage(resource.RUSAGE_CHILDREN)
    (args.output/"native-output.bin").write_bytes(stdout)
    (args.output/"native.stderr.txt").write_bytes(stderr)
    boundaries=[json.loads(line[len(b"NET01_CONTROL "):]) for line in stderr.splitlines() if line.startswith(b"NET01_CONTROL ")]
    (args.output/"native-boundaries.json").write_text(json.dumps(boundaries,indent=2)+"\n")
    result=dict(argv=argv,native_exit=process.returncode,error=error,wall_s=time.monotonic()-start,
        total_process_cpu_s=(usage_after.ru_utime+usage_after.ru_stime)-(usage_before.ru_utime+usage_before.ru_stime),
        status="MEASURED" if process.returncode==0 and error is None else "FAIL",
        scope="Native CPU diagnostic ONLY; no ROS, real-time qualification, policy or safety validation")
    if process.returncode==0:
        ready,received,steps=parse_output(stdout)
        result.update(ready=ready,received=list(received),missing=sorted(set(messages)-set(received)),steps=steps,
            received_exact=all(r["payload"]==messages[i]["payload"] and (r["sender"],r["receiver"])==(messages[i]["sender"],messages[i]["receiver"]) for i,r in received.items()))
        if result['missing'] or not result['received_exact']:
            result['status']='FAIL';error='Actual whole-payload receipt differs from fixed input'
        result["ledger"]=json.loads((native_dir/"ledger-status.json").read_text())
        if args.compare is not None:
            def events(path):
                return [{k:v for k,v in json.loads(line).items() if k!="monotonic_ns"}
                    for line in path.read_text().splitlines()]
            reference=args.compare/"native"
            pcaps={p.name:p for p in native_dir.glob('*.pcap')}
            result['comparison']=dict(ledger_events_except_mono_equal=events(native_dir/'packet-ledger.jsonl')==events(reference/'packet-ledger.jsonl'),
                stdout_protocol_and_payload_exact=stdout==(args.compare/'native-output.bin').read_bytes(),
                pcap_bytes_equal=set(pcaps)=={p.name for p in reference.glob('*.pcap')} and all(p.read_bytes()==(reference/name).read_bytes() for name,p in pcaps.items()))
            if not all(result['comparison'].values()):result['status']='FAIL';error='Reference event/payload/PCAP mismatch'
    result['error']=error
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)
    return 0 if process.returncode==0 and error is None else 1


if __name__=="__main__":raise SystemExit(main())

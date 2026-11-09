#!/usr/bin/env python3
"""One fixed native-only CPU observation, not ROS/WiFi capacity acceptance."""
import argparse
import json
import os
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
    argv=[str(args.native.resolve()),f"--output={native_dir.resolve()}","--profile=B","--controlTrace=1","--cpuProfile=1"]
    start=time.monotonic();process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True)
    error=None
    try:stdout,stderr=process.communicate(bytes(commands),timeout=18)
    except subprocess.TimeoutExpired:
        error="native measurement exceeded18wall; owned group killed"
        os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
    (args.output/"native-output.bin").write_bytes(stdout)
    (args.output/"native.stderr.txt").write_bytes(stderr)
    boundaries=[json.loads(line[len(b"NET01_CONTROL "):]) for line in stderr.splitlines() if line.startswith(b"NET01_CONTROL ")]
    (args.output/"native-boundaries.json").write_text(json.dumps(boundaries,indent=2)+"\n")
    result=dict(argv=argv,native_exit=process.returncode,error=error,wall_s=time.monotonic()-start,
        status="MEASURED" if process.returncode==0 and error is None else "FAIL",
        scope="Native CPU diagnostic ONLY; no ROS, real-time qualification, policy or safety validation")
    if process.returncode==0:
        ready,received,steps=parse_output(stdout)
        result.update(ready=ready,received=list(received),missing=sorted(set(messages)-set(received)),steps=steps,
            received_exact=all(r["payload"]==messages[i]["payload"] and (r["sender"],r["receiver"])==(messages[i]["sender"],messages[i]["receiver"]) for i,r in received.items()))
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)
    return 0 if process.returncode==0 and error is None else 1


if __name__=="__main__":raise SystemExit(main())

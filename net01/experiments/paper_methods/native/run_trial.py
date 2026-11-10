"""Run exactly one pre-registered, synthetic native trial; no ROS or host network."""
import json
import subprocess
import sys
import time
from pathlib import Path

cases = {
    "reliability-udp-01": ["--trial=reliability", "--transport=udp"],
    "reliability-tcp-01": ["--trial=reliability", "--transport=tcp"],
    "position-immediate-01": ["--trial=position", "--placement=immediate"],
    "position-scheduled-01": ["--trial=position", "--placement=scheduled"],
}
name = sys.argv[1]
arguments = cases[name]
source = Path(__file__).resolve().parent
phase = source.parents[4]
case = source / "results" / name
case.mkdir(parents=True, exist_ok=False)
command = [str(phase / "build/paper-method-trials/paper-methods"), *arguments,
           "--output=" + str(case / "native")]
(case / "command.json").write_text(json.dumps(command, indent=2) + "\n")
begin = time.monotonic_ns()
with (case / "stdout.txt").open("x") as out, (case / "stderr.txt").open("x") as err:
    try:
        result = subprocess.run(command, stdout=out, stderr=err, timeout=29)
        code, timed_out = result.returncode, False
    except subprocess.TimeoutExpired:
        code, timed_out = None, True  # subprocess.run kills and waits for its exact child
row = {"exit_code": code, "timeout": timed_out,
       "wall_s": (time.monotonic_ns() - begin) / 1e9,
       "scope": "0 ROS/Gazebo/Nav2/Goal; synthetic native experiment"}
(case / "process-exit.json").write_text(json.dumps(row, indent=2) + "\n")
print(json.dumps(row))
sys.exit(1 if timed_out else code)

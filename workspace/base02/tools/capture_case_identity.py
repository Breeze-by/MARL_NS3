#!/usr/bin/env python3
"""Capture a clean source/harness and built driver identity BEFORE a case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--driver', choices=['libbase01_diff_drive.so','libbase01_diff_drive_diagnostic.so'], required=True)
parser.add_argument('--kind', choices=['base02_traditional_regression'], required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
repo = root/'workspace'
def git(*argv):
    return subprocess.check_output(['git','-C',str(repo),*argv],text=True).strip()
if git('status','--porcelain'):
    raise RuntimeError('Source worktree must be clean before a case')
commit = git('rev-parse','HEAD')
tools = {}
for path in (root/'tools').iterdir():
    if not path.is_file():
        continue
    pinned = subprocess.check_output(['git','-C',str(repo),'show',f'{commit}:base02/tools/{path.name}'])
    if pinned != path.read_bytes():
        raise RuntimeError('Unpinned tool: '+path.name)
    tools[path.name] = hashlib.sha256(pinned).hexdigest()
baseline = root.parent/'base-01-econ'
baseline_commit = subprocess.check_output(['git','-C',str(baseline/'workspace'),'rev-parse','HEAD'],text=True).strip()
if baseline_commit != '12b366564842fbc98de57e0fc679a9b22d125543':
    raise RuntimeError('Accepted runtime underlay identity changed')
library = baseline/'workspace/install/base01_diff_drive/lib'/args.driver
# colcon symlink-install was built inside /project; translate that one known
# mount prefix when the pre-case identity is collected from the host.
if library.is_symlink():
    target = library.readlink()
    if target.is_absolute() and target.is_relative_to('/project'):
        library = baseline/target.relative_to('/project')
identity = dict(utc=datetime.now(timezone.utc).isoformat(), kind=args.kind, commit=commit,
    tree=git('rev-parse','HEAD^{tree}'), driver=args.driver, runtime_underlay_commit=baseline_commit,
    runtime_mode='read-only BASE-01 /project + central Python overlay /mnt',
    driver_sha256=hashlib.sha256(library.read_bytes()).hexdigest(), tools=tools,
    safety=dict(linear_mps=0.01, angular_rps=0.03, stable_wall_seconds=1.5,
                stable_sim_seconds=0.5, stop_window_wall_seconds=12, min_pair_distance_m=0.70))
with args.output.open('x') as stream:
    json.dump(identity,stream,indent=2)
print(json.dumps(identity,indent=2))

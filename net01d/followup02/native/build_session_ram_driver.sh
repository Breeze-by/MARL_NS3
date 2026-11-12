#!/usr/bin/env bash
# Recipe only until independent source acceptance/root build admission.
# Builds one new driver; never builds ns3 DSOs or starts a native/ROS/Gazebo model.
set -euo pipefail
[[ ${1:-} == run ]] || { printf 'Usage: %s run\n' "$0" >&2; exit 2; }
ws=/home/zhuyulab/ns3-workspace
repo="$ws/net-01d/workspace"
libraries="$ws/net-01d/ns3-lto-portable-followup02/build"
revision=${2:-}
candidate="$ws/net-01d/native-session-ram-followup02${revision:+-$revision}"
rtk proxy mkdir "$candidate"
rtk proxy mkdir "$candidate/driver-src" "$candidate/evidence"
cd "$repo"
rtk proxy rsync -a --relative -- net01/native/payload_transport.cc net01/native/event_ledger.h \
  net01d/followup02/native/tcp_stream_draft.inc "$candidate/driver-src/"
rtk proxy cp "$ws/net-01d/ns3-lto-portable-followup02/driver-src/CMakeLists.txt" "$candidate/driver-src/CMakeLists.txt"
rtk proxy timeout --signal=TERM --kill-after=5s 60s cmake \
  -S "$candidate/driver-src" -B "$candidate/driver-cache" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' -DNS3_BUILD_DIR="$libraries" \
  -DCONFIG_HEADER_DIR="$ws/net-01/build/network-full-payload" \
  > "$candidate/evidence/configure.stdout" 2> "$candidate/evidence/configure.stderr"
rtk proxy timeout --signal=TERM --kill-after=5s 180s cmake --build "$candidate/driver-cache" \
  --target net01-payload-tcp -j2 > "$candidate/evidence/build.stdout" 2> "$candidate/evidence/build.stderr"
rtk proxy readelf -d "$candidate/driver-out/net01-payload-tcp" > "$candidate/evidence/readelf.txt"
rtk proxy env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$libraries/lib" \
  ldd "$candidate/driver-out/net01-payload-tcp" > "$candidate/evidence/ldd.txt"
rtk proxy python3 -B - "$candidate" "$libraries" <<'PY'
import hashlib,json,re,subprocess,sys
from pathlib import Path
root,libraries=map(Path,sys.argv[1:]);repo=Path.cwd()
modules='wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge stats'.split()
loaded={}
for line in (root/'evidence/ldd.txt').read_text().splitlines():
    match=re.match(r'\s*libns3\.40-(\S+)\.so\s+=>\s+(\S+)',line)
    if match:loaded[match[1]]=Path(match[2])
if set(loaded)!=set(modules) or any(p.resolve().parent!=(libraries/'lib').resolve() for p in loaded.values()):
    raise RuntimeError('Driver loaded dependency closure is not the reviewed13 LTO DSOs')
flags=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/flags.make').read_text()
link=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/link.txt').read_text()
for text in (flags,link):
    if '-flto' not in text or '-ffp-contract=off' not in text:raise RuntimeError('Driver LTO/FP flags missing')
driver=root/'driver-out/net01-payload-tcp'
identity=dict(status='DRIVER_BUILD_LINK_INSPECTION_ONLY; no model starts',
    source_snapshot_base='e5ba7ea076caf317b040e0b58c0547255913c3b0',
    actual_build_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    changed_source_copies={p:hashlib.sha256((root/'driver-src'/p).read_bytes()).hexdigest()
        for p in ('net01/native/payload_transport.cc','net01/native/event_ledger.h')},
    driver=dict(path=str(driver),bytes=driver.stat().st_size,sha256=hashlib.sha256(driver.read_bytes()).hexdigest()),
    existing13_library_artifact_identity='net01d/followup02/native/lto-build-01/BUILD_IDENTITY.json',
    existing13_library_identity_commit='fbe269dd9f98f869b289ec81361b7fc20886642b',
    dependency_paths={k:str(v) for k,v in loaded.items()},driver_flags=flags,driver_link=link,
    old0cc_and13DSOs_unmodified=True,library_rebuilds=0,model_starts=0,
    RAM_mode='session-ram-v1 opt-in; default serial unchanged;32M records/8GiB conservative owned capacity, not RSS')
with (root/'evidence/BUILD_IDENTITY.json').open('x') as stream:json.dump(identity,stream,indent=2);stream.write('\n')
print(json.dumps(dict(status=identity['status'],driver=identity['driver'],model_starts=0)))
PY

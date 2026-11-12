#!/usr/bin/env bash
# Source-ready recipe; only root admission may invoke run. No model execution.
set -euo pipefail
[[ ${1:-} == run ]] || { printf 'Usage: %s run\n' "$0" >&2; exit 2; }
ws=/home/zhuyulab/ns3-workspace
repo="$ws/net-01d/workspace"
reference="$ws/net-01d/ns3-lto-portable-followup02"
candidate="$ws/net-01d/native-copy-cost-followup03"
rtk proxy mkdir "$candidate"
rtk proxy mkdir "$candidate/driver-src" "$candidate/evidence"
rtk proxy rsync -a "$reference/driver-src/" "$candidate/driver-src/"
rtk proxy patch --batch --forward --fuzz=0 -p1 -d "$candidate/driver-src" \
  -i "$repo/net01d/followup03/native/TCP_COPY_CANDIDATE.patch" \
  > "$candidate/evidence/patch.stdout" 2> "$candidate/evidence/patch.stderr"
rtk proxy timeout --signal=TERM --kill-after=5s 60s /usr/bin/time \
  -v -o "$candidate/evidence/configure-time.txt" cmake \
  -S "$candidate/driver-src" -B "$candidate/driver-cache" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' -DNS3_BUILD_DIR="$reference/build" \
  -DCONFIG_HEADER_DIR="$ws/net-01/build/network-full-payload" \
  > "$candidate/evidence/configure.stdout" 2> "$candidate/evidence/configure.stderr"
rtk proxy timeout --signal=TERM --kill-after=5s 180s /usr/bin/time \
  -v -o "$candidate/evidence/build-time.txt" cmake --build "$candidate/driver-cache" \
  --target net01-payload-tcp -j2 > "$candidate/evidence/build.stdout" 2> "$candidate/evidence/build.stderr"
rtk proxy env -u LD_PRELOAD -u LD_AUDIT -u LD_PROFILE -u LD_PROFILE_OUTPUT \
  LD_LIBRARY_PATH="$reference/build/lib" ldd "$candidate/driver-out/net01-payload-tcp" \
  > "$candidate/evidence/ldd.txt"
rtk proxy python3 -B - "$candidate" "$reference" "$repo" <<'META'
import difflib,hashlib,json,re,subprocess,sys
from pathlib import Path
root,ref,repo=map(Path,sys.argv[1:])
paths=['CMakeLists.txt','net01/native/payload_transport.cc','net01/native/event_ledger.h',
       'net01d/followup02/native/tcp_stream_draft.inc']
diff=''.join(''.join(difflib.unified_diff((ref/'driver-src'/p).read_text().splitlines(True),
    (root/'driver-src'/p).read_text().splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in paths)
patch=(repo/'net01d/followup03/native/TCP_COPY_CANDIDATE.patch').read_text()
if diff!=patch:raise RuntimeError('Isolated driver source difference is not exactly the one admitted TX patch')
loaded={}
for line in (root/'evidence/ldd.txt').read_text().splitlines():
    m=re.match(r'\s*libns3\.40-(\S+)\.so\s+=>\s+(\S+)',line)
    if m:loaded[m[1]]=Path(m[2])
modules=set('wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge stats'.split())
if set(loaded)!=modules or any(p.resolve().parent!=(ref/'build/lib').resolve() for p in loaded.values()):
    raise RuntimeError('Link closure is not the same reviewed13 LTO libraries')
flags=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/flags.make').read_text()
link=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/link.txt').read_text()
if any('-flto' not in x or '-ffp-contract=off' not in x for x in (flags,link)):
    raise RuntimeError('Original LTO/FP flags missing')
binary=root/'driver-out/net01-payload-tcp'
identity=dict(status='DRIVER_BUILD_LINK_ONLY; model_starts0',
    actual_recipe_HEAD=subprocess.check_output(['rtk','proxy','git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
    reference_ELF=str(ref/'driver-out/net01-payload-tcp'),
    reference_SHA_reused='0cc771a18a3eb63ebbc4eb09ee942aaba27ea93211e07a7a0805d993dcc7c4f3',
    source_origin=str(ref/'driver-src'),source_origin_identity=str(ref/'evidence/BUILD_IDENTITY.json'),
    source_difference=diff,source_difference_is_exact_admitted_patch=True,
    driver=dict(path=str(binary),bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),
    existing13_library_identity='net01d/followup02/native/lto-build-01/BUILD_IDENTITY.json',
    dependency_paths={k:str(v) for k,v in loaded.items()},driver_flags=flags,driver_link=link,
    configure_time='evidence/configure-time.txt',build_time='evidence/build-time.txt',
    library_rebuilds=0,old0cc_and13DSOs_unmodified=True,model_starts=0)
with (root/'evidence/BUILD_IDENTITY.json').open('x') as f:json.dump(identity,f,indent=2);f.write('\n')
print(json.dumps(identity['driver']))
META

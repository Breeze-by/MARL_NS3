#!/usr/bin/env bash
# Root-admitted copy/config/build/link inspection only. Never starts the model.
set -euo pipefail
[[ ${1:-} == run ]] || { printf 'Usage: %s run\n' "$0" >&2; exit 2; }
ws=/home/zhuyulab/ns3-workspace
repo="$ws/net-01d/workspace"
old="$ws/net-01/ns3-release-portable-followup03"
candidate="$ws/net-01d/ns3-lto-portable-followup02"
rtk proxy mkdir "$candidate"
rtk proxy mkdir "$candidate/src" "$candidate/driver-src" "$candidate/evidence"
trap 'code=$?; printf "%s\n" "$code" > "$candidate/evidence/overall.exit"' EXIT

run_stage() {
  local stage=$1 code begin end
  shift
  printf '%q ' "$@" > "$candidate/evidence/$stage.command"
  printf '\n' >> "$candidate/evidence/$stage.command"
  begin=$(rtk proxy python3 -B -c 'import time; print(time.monotonic_ns())')
  printf 'Starting %s\n' "$stage"
  if "$@" > "$candidate/evidence/$stage.stdout" 2> "$candidate/evidence/$stage.stderr"; then code=0; else code=$?; fi
  end=$(rtk proxy python3 -B -c 'import time; print(time.monotonic_ns())')
  printf '%s\n' "$code" > "$candidate/evidence/$stage.exit"
  printf '%s\n' "$((end-begin))" > "$candidate/evidence/$stage.wall_ns"
  printf '%s exit=%s wall_ns=%s\n' "$stage" "$code" "$((end-begin))"
  return "$code"
}

read -r version < "$old/src/VERSION"
[[ $version == 3.40 ]]
entries=(bindings build-support contrib doc examples scratch src utils AUTHORS CHANGES.md
  CMakeLists.txt CONTRIBUTING.md LICENSE README.md RELEASE_NOTES.md VERSION ns3
  pyproject.toml setup.cfg setup.py test.py utils.py .clang-format .clang-tidy .editorconfig)
sources=(); for entry in "${entries[@]}"; do sources+=("$old/src/$entry"); done
run_stage source-copy rtk proxy rsync -a -- "${sources[@]}" "$candidate/src/"
cd "$repo"
run_stage driver-copy rtk proxy rsync -a --relative -- net01/native/payload_transport.cc \
  net01/native/event_ledger.h net01d/followup02/native/tcp_stream_draft.inc "$candidate/driver-src/"
printf 'source=%s\nVERSION=%s\nold_source_and_build_unmodified=true\n' "$old/src" "$version" > "$candidate/evidence/source-origin.txt"
printf 'set(ns3rc_examples_enabled OFF)\nset(ns3rc_tests_enabled OFF)\n' > "$candidate/private.ns3rc"
modules='wifi;internet;csma;mobility;propagation;spectrum;antenna;energy;network;core;traffic-control;bridge'
run_stage ns3-configure rtk proxy timeout --signal=TERM --kill-after=10s 120s cmake \
  -S "$candidate/src" -B "$candidate/cmake-cache" -G 'Unix Makefiles' \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DCMAKE_C_FLAGS=-ffp-contract=off -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DNS3_OUTPUT_DIRECTORY="$candidate/build" -DNS3RC:FILEPATH="$candidate/private.ns3rc" \
  -DNS3_ENABLED_MODULES="$modules" -DNS3_NATIVE_OPTIMIZATIONS=OFF -DNS3_LINK_TIME_OPTIMIZATION=ON \
  -DNS3_ASSERT=OFF -DNS3_LOG=OFF -DNS3_WARNINGS_AS_ERRORS=OFF -DNS3_CCACHE=OFF \
  -DNS3_FETCH_OPTIONAL_COMPONENTS=OFF -DNS3_CPM=OFF -DNS3_VCPKG=OFF \
  -DNS3_EXAMPLES=OFF -DNS3_TESTS=OFF -DNS3_PYTHON_BINDINGS=OFF \
  -DNS3_VISUALIZER=OFF -DNS3_ENABLE_BUILD_VERSION=OFF

# Upstream can report unsupported IPO without failing configure. Stop before
# compilation unless every selected object/library target really enables LTO.
run_stage ns3-flags rtk proxy python3 -B - "$candidate" <<'PY'
from pathlib import Path
import json, re, sys
root=Path(sys.argv[1]); modules='wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge stats'.split()
if 'Link-time optimization (LTO) is supported.' not in (root/'evidence/ns3-configure.stdout').read_text():
    raise RuntimeError('Official ns3 IPO check did not confirm support')
rows=[]
for module in modules:
    base=root/'cmake-cache/src'/module/'CMakeFiles'
    flags=(base/f'lib{module}-obj.dir/flags.make').read_text()
    compile_flags=next(line for line in flags.splitlines() if line.startswith('CXX_FLAGS ='))
    link=(base/f'lib{module}.dir/link.txt').read_text().strip()
    for text in (compile_flags,link):
        if not re.search(r'(?<!\S)-flto(?=\s|$)',text):raise RuntimeError(f'Missing plain -flto: {module}')
        if '-ffp-contract=off' not in text:raise RuntimeError(f'Missing FP contract restriction: {module}')
        if any(flag in text for flag in ('-ffast-math','-Ofast','-march=native','-mtune=native','-flto=auto','-flto=jobserver')):
            raise RuntimeError(f'Unregistered codegen/resource flag: {module}')
    if 'NS3_ASSERT_ENABLE' in flags or 'NS3_LOG_ENABLE' in flags:raise RuntimeError(f'Unexpected log/assert: {module}')
    if '-O3' not in compile_flags or '-DNDEBUG' not in compile_flags:raise RuntimeError(f'Wrong Release flags: {module}')
    rows.append(dict(module=module,compile_flags=compile_flags,link=link))
with (root/'evidence/ns3-flags.json').open('x') as out:json.dump(rows,out,indent=2)
print(json.dumps(dict(modules=len(rows),actual_plain_flto=True,FP_contract_off=True)))
PY
run_stage ns3-build rtk proxy timeout --signal=TERM --kill-after=10s 20m cmake \
  --build "$candidate/cmake-cache" --target libwifi libinternet libcsma -j8

cat > "$candidate/driver-src/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(net01_lto_candidate LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_ok OUTPUT ipo_error LANGUAGES CXX)
if(NOT ipo_ok)
  message(FATAL_ERROR "LTO unavailable: ${ipo_error}")
endif()
add_executable(net01-payload-tcp net01/native/payload_transport.cc)
target_include_directories(net01-payload-tcp PRIVATE "${NS3_BUILD_DIR}/include" "${CONFIG_HEADER_DIR}")
# Match C3's twelve explicit dependencies; stats remains a new-root transitive DSO.
foreach(module wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge)
  find_library(ns3_${module} NAMES ns3.40-${module} PATHS "${NS3_BUILD_DIR}/lib" NO_DEFAULT_PATH REQUIRED)
  target_link_libraries(net01-payload-tcp PRIVATE "${ns3_${module}}")
endforeach()
find_package(Threads REQUIRED)
target_link_libraries(net01-payload-tcp PRIVATE Threads::Threads)
set_target_properties(net01-payload-tcp PROPERTIES INTERPROCEDURAL_OPTIMIZATION TRUE
  BUILD_RPATH "${NS3_BUILD_DIR}/lib" RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/../driver-out")
CMAKE
run_stage driver-configure rtk proxy timeout --signal=TERM --kill-after=5s 60s cmake \
  -S "$candidate/driver-src" -B "$candidate/driver-cache" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' -DNS3_BUILD_DIR="$candidate/build" \
  -DCONFIG_HEADER_DIR="$ws/net-01/build/network-full-payload"
run_stage driver-build rtk proxy timeout --signal=TERM --kill-after=10s 3m cmake --build "$candidate/driver-cache" -j8
run_stage driver-readelf rtk proxy readelf -d "$candidate/driver-out/net01-payload-tcp"
run_stage driver-ldd rtk proxy env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$candidate/build/lib" ldd "$candidate/driver-out/net01-payload-tcp"

run_stage identity rtk proxy python3 -B - "$candidate" "$repo" <<'PY'
from pathlib import Path
import hashlib, json, re, sys
root,repo=map(Path,sys.argv[1:]); modules='wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge stats'.split()
flags=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/flags.make').read_text()
compile_flags=next(line for line in flags.splitlines() if line.startswith('CXX_FLAGS ='))
link=(root/'driver-cache/CMakeFiles/net01-payload-tcp.dir/link.txt').read_text().strip()
for text in (compile_flags,link):
    if not re.search(r'(?<!\S)-flto(?=\s|$)',text) or '-ffp-contract=off' not in text:raise RuntimeError('Driver actual LTO/FP flags missing')
    if any(flag in text for flag in ('-ffast-math','-Ofast','-march=native','-mtune=native','-flto=auto','-flto=jobserver')):raise RuntimeError('Unregistered driver flags')
ldd=(root/'evidence/driver-ldd.stdout').read_text(); loaded={}
for line in ldd.splitlines():
    match=re.match(r'\s*libns3\.40-(\S+)\.so\s+=>\s+(\S+)',line)
    if match:loaded[match[1]]=Path(match[2])
if set(loaded)!=set(modules):raise RuntimeError(f'Wrong ns3 DSO closure: {loaded}')
for path in loaded.values():
    if path.resolve().parent!=(root/'build/lib').resolve():raise RuntimeError(f'Mixed old DSO: {path}')
if str(root/'build/lib') not in (root/'evidence/driver-readelf.stdout').read_text():raise RuntimeError('Missing new-root RPATH')
old=json.loads((repo/'net01d/followup02/native/mtu-build-01/BUILD_IDENTITY.json').read_text())
expected={Path(row['path']).relative_to(repo).as_posix():row['sha256'] for row in old['files'] if str(repo)+'/' in row['path']}
expected['net01/native/event_ledger.h']=old['ledger_formatter_identity_reused']['sha256']
sources=[]
for relative,wanted in expected.items():
    path=root/'driver-src'/relative; digest=hashlib.sha256(path.read_bytes()).hexdigest()
    sources.append(dict(path=str(path),sha256=digest,bytes=path.stat().st_size,matches_C3=digest==wanted))
    if digest!=wanted:raise RuntimeError(f'Driver source differs from C3: {relative}')
artifacts=[]
for path in [root/'driver-out/net01-payload-tcp',*[loaded[m] for m in modules]]:
    artifacts.append(dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
result=dict(status='BUILD_AND_LINK_INSPECTION_ONLY',source_VERSION=(root/'src/VERSION').read_text().strip(),
    old_C3_identity_reused=str(repo/'net01d/followup02/native/mtu-build-01/BUILD_IDENTITY.json'),
    source_copies=sources,artifacts=artifacts,driver_compile_flags=compile_flags,driver_link=link,
    explicit_libraries=modules[:-1],transitive_libraries=['stats'],all_13_new_root=True,
    actual_runtime_maps='NOT MEASURED: native model not admitted or started',model_starts=0,
    numerical_constraint_difference='Candidate explicit -ffp-contract=off; old C3 did not explicitly set it')
with (root/'evidence/BUILD_IDENTITY.json').open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps(dict(status=result['status'],libraries=len(loaded),source_copies_match_C3=True,model_starts=0)))
PY
printf 'Build/link inspection complete; native model and paired runs NOT STARTED.\n'

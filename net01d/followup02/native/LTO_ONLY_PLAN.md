# 同源 portable LTO 候选：仅准备，尚未准入

目标只检验编译生成代码的工程收益，不改模型、协议、日志、输入、源率或安全期限，不保证加速。旧 C3 ELF、旧 ns-3 源/build/results 均保留。不安装、不启动模型；以下命令全部等待 root 另行准入，并串行避开其它测量。

## 固定路径和范围

- 已有依赖：`/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03/{src,cmake-cache,build}`，VERSION=3.40。
- 新独占根：`/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02`，内含 `src/cmake-cache/build/driver-src/driver-cache/driver-out/evidence`；CMake 只可向新源写自己的 lock。
- 12个显式模块：wifi/internet/csma/mobility/propagation/spectrum/antenna/energy/network/core/traffic-control/bridge；加原 stats 依赖，合计13个新 DSO，名称仍为 `libns3.40-<module>.so`，无 profile 后缀。
- 复用 C3 `payload_transport.cc`、`event_ledger.h`、`tcp_stream_draft.inc` 字节和相对目录结构；原 `network_config.h` 仍来自 `net-01/build/network-full-payload`，不重新生成模型参数。
- 保持 Release、O3/NDEBUG、ASSERT/LOG OFF、NATIVE OFF、PCH原默认ON；不开 fast-math/Ofast。只启官方 LTO 优化；全部新库和 driver 显式 `-ffp-contract=off`。

旧 cache 没有显式 `-ffp-contract=off`，因此后者是本候选额外保守数值限制，不能把对旧 C3 的全部差异严格归因为一个 LTO flag。全部重建13库也不代表跨共享库边界自动全程序内联；普通共享库布局不变。

## 待准入命令

以下在同一个 bash 中执行，工作目录为 `net-01d/workspace`；所有目录排他创建，不复用失败目录。阶段用原 `run_stage` 模式分别保存实际 argv、stdout、stderr、exit，首非零立即停止，不换 flags 重试。

```bash
set -euo pipefail
ws=/home/zhuyulab/ns3-workspace
repo="$ws/net-01d/workspace"
old="$ws/net-01/ns3-release-portable-followup03"
candidate="$ws/net-01d/ns3-lto-portable-followup02"
modules='wifi;internet;csma;mobility;propagation;spectrum;antenna;energy;network;core;traffic-control;bridge'
rtk proxy mkdir "$candidate"
rtk proxy mkdir "$candidate/src" "$candidate/driver-src" "$candidate/evidence"
# 与原已审 recipe 相同的源名单；不复制 build/cache/lock/运行结果。
entries=(bindings build-support contrib doc examples scratch src utils AUTHORS CHANGES.md
  CMakeLists.txt CONTRIBUTING.md LICENSE README.md RELEASE_NOTES.md VERSION ns3
  pyproject.toml setup.cfg setup.py test.py utils.py .clang-format .clang-tidy .editorconfig)
sources=(); for entry in "${entries[@]}"; do sources+=("$old/src/$entry"); done
rtk proxy rsync -a -- "${sources[@]}" "$candidate/src/"
rtk proxy rsync -a --relative -- net01/native/payload_transport.cc net01/native/event_ledger.h \
  net01d/followup02/native/tcp_stream_draft.inc "$candidate/driver-src/"
printf 'set(ns3rc_examples_enabled OFF)\nset(ns3rc_tests_enabled OFF)\n' > "$candidate/private.ns3rc"
rtk proxy timeout --signal=TERM --kill-after=10s 120s cmake \
  -S "$candidate/src" -B "$candidate/cmake-cache" -G 'Unix Makefiles' \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DCMAKE_C_FLAGS=-ffp-contract=off -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DNS3_OUTPUT_DIRECTORY="$candidate/build" -DNS3RC:FILEPATH="$candidate/private.ns3rc" \
  -DNS3_ENABLED_MODULES="$modules" -DNS3_NATIVE_OPTIMIZATIONS=OFF \
  -DNS3_LINK_TIME_OPTIMIZATION=ON -DNS3_ASSERT=OFF -DNS3_LOG=OFF \
  -DNS3_WARNINGS_AS_ERRORS=OFF -DNS3_CCACHE=OFF -DNS3_FETCH_OPTIONAL_COMPONENTS=OFF \
  -DNS3_CPM=OFF -DNS3_VCPKG=OFF -DNS3_EXAMPLES=OFF -DNS3_TESTS=OFF \
  -DNS3_PYTHON_BINDINGS=OFF -DNS3_VISUALIZER=OFF -DNS3_ENABLE_BUILD_VERSION=OFF
rtk proxy timeout --signal=TERM --kill-after=10s 20m cmake \
  --build "$candidate/cmake-cache" --target libwifi libinternet libcsma -j8
```

先核官方 IPO 实际启用，再进入编译：本机 ns3 `build-support/macros-and-definitions.cmake:672–684` 在不支持 IPO 时只输出 STATUS，不使配置失败。必须要求 “LTO is supported” 且生成的13模块 `lib<module>-obj.dir/flags.make` 和 `lib<module>.dir/link.txt` 实际含 `-flto`；仅 cache 的 ON 不够。本机 CMake3.22 `Modules/Compiler/GNU.cmake:69–83` 当前生成 `-flto;-fno-fat-lto-objects`，不是 `-flto=auto`；保此默认串行 LTO worker 和 Make `-j8`，不得偷偷启用无限自动并行。

在 `driver-src/CMakeLists.txt` 新建以下独立配置（不修改生产 CMake 或源）：

```cmake
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
foreach(module wifi internet csma mobility propagation spectrum antenna energy network core traffic-control bridge)
  find_library(ns3_${module} NAMES ns3.40-${module} PATHS "${NS3_BUILD_DIR}/lib" NO_DEFAULT_PATH REQUIRED)
  target_link_libraries(net01-payload-tcp PRIVATE "${ns3_${module}}")
endforeach()
find_package(Threads REQUIRED)
target_link_libraries(net01-payload-tcp PRIVATE Threads::Threads)
set_target_properties(net01-payload-tcp PROPERTIES INTERPROCEDURAL_OPTIMIZATION TRUE
  BUILD_RPATH "${NS3_BUILD_DIR}/lib" RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/../driver-out")
```

```bash
rtk proxy timeout --signal=TERM --kill-after=5s 60s cmake \
  -S "$candidate/driver-src" -B "$candidate/driver-cache" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CXX_FLAGS=-ffp-contract=off \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' -DNS3_BUILD_DIR="$candidate/build" \
  -DCONFIG_HEADER_DIR="$ws/net-01/build/network-full-payload"
rtk proxy timeout --signal=TERM --kill-after=10s 3m cmake --build "$candidate/driver-cache" -j8
```

按 root 构建准入意见，driver 保持 C3 的12个显式依赖，stats由相同依赖闭包传递加载；最终仍必须是13个新根 DSO。实际执行 recipe 为同目录 `build_lto_only.sh`，复用原 run_stage 保存命令、日志、退出及 wall，任一阶段失败停止。

同样核 driver 的实际编译/链接 `-flto`、`-ffp-contract=off`，13库的实际 compile flags 无 nativeISA/fast-math/Ofast，ASSERT/LOG OFF。旧 ns-3 已有的 `-fno-semantic-interposition` 保持，不新增其它优化。不能只编 driver 后称全部模型已 LTO。保存新产物身份一次，不重新计算旧树哈希。

## 加载隔离与唯一固定配对（仍未准入）

构建后单次 `readelf -d` 及清除 LD_PRELOAD/LD_AUDIT/旧 LD_LIBRARY_PATH 的 `ldd` 记录，要求候选13个 ns3 DSO 全部解析到新 `build/lib`，不允许旧库混载。driver RPATH 固定新根；候选运行时再将 LD_LIBRARY_PATH **仅**设为新 `build/lib`，基线对应旧 `build/lib`，其余系统依赖照常。

```bash
rtk proxy readelf -d "$candidate/driver-out/net01-payload-tcp" > "$candidate/evidence/driver-dynamic.txt"
rtk proxy env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$candidate/build/lib" \
  ldd "$candidate/driver-out/net01-payload-tcp" > "$candidate/evidence/driver-ldd.txt"
```

实际配对启动后，从本次已知 owned runner→Hub→native 父子关系核对 native argv，单次保存其 `/proc/PID/maps`；要求13个 ns3 DSO 均为本臂指定根。只读该 owned 树，不扫描全机进程。maps 缺失就标证据不足，不以 ldd 代替实际加载证明；该小观测接线需在执行准入前落定，不改模型/业务 IPC。

固定先旧 C3、再新候选，各一次，不并行、不重试。命令工作目录仍为 repo；旧 C3 身份复用 `mtu-build-01/BUILD_IDENTITY.json`。外层可用已有 `/usr/bin/time -v` 保存 runner及其子树总 user/system CPU，明确它含 Hub、复制和离线摘要，不冒称纯 Native CPU；原 `ledger-status.model_cpu_ns` 和 STEP/barrier trace 另列主线程 CPU/墙钟。

```bash
rtk proxy env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$old/build/lib" \
  /usr/bin/time -v -o "$candidate/evidence/reference-total-time.txt" \
  timeout --signal=TERM --kill-after=2s 30s python3 -B net01d/followup02/native/run_native_tcp.py \
  --case stream-01 --output-name ntcp-lto-r1 --native-transport tcp-mtu-v2 \
  --native "$ws/net-01d/build/followup02-native-tcp-mtu-v2/net01-payload-tcp"
rtk proxy env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$candidate/build/lib" \
  /usr/bin/time -v -o "$candidate/evidence/candidate-total-time.txt" \
  timeout --signal=TERM --kill-after=2s 30s python3 -B net01d/followup02/native/run_native_tcp.py \
  --case stream-01 --output-name ntcp-lto-c1 --native-transport tcp-mtu-v2 \
  --native "$candidate/driver-out/net01-payload-tcp"
```

复用原 stream-01：N0六份64B；N4六份160704B和六份1MiB；N8结束，STEP10ms；20active/30hard；原 seed/run/header/18payload/路由/RPC/源时刻相同，controlTrace ON、cpuProfile/asyncLedger/radiofault OFF。独占输出 `followup02/runs/ntcp-lto-{r1,c1}` 和 RAM `/dev/shm/net01d-f02-ntcp-lto-{r1,c1}`，不覆盖旧件。

两臂要求原 byte/resource predicates、Hub/native0、copy complete及owned清理；18份实际 RX 对原输入和跨臂逐字相等；四个 PCAP 同文件集且逐字相等；每条 ledger 只移除 `monotonic_ns` 后按原序规范化，键及所有数值/字符串严格相等，不放宽浮点。counts、TCP实际属性、queue/debt/expiry和终点一致；诊断 wall/CPU 字段另作测量。不一致停止，不为加速豁免事件差异。

记录 STEP Run与含barrier的 sum/median/p95/max 墙钟、主线程CPU、runner子树总CPU/总wall；原生 CPU 优势不能抵销原300ms失败。此一对只为开发判断，不是统计性能研究、完整ROS或Gazebo准入。

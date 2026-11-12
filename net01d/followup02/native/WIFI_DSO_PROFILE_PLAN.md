# Wi-Fi DSO diagnostic: SOURCE_READY, not executed

Only one proposed native case: `ntcp-prof-wifi-01`. **Do not execute until Root
confirms the Hub error-evidence fix and its required fixture acceptance, then
separately admits this case.** No Network DSO second case or Gazebo follows
automatically. No model/profile/sprof command has been executed for this plan.
The local installed `sprof(1)`/`ld.so(8)` manuals supplied the syntax; perf's
paranoid4 and all system settings stay unchanged.

Exact future command, cwd `/home/zhuyulab/ns3-workspace/net-01d/workspace`:

```sh
rtk proxy env -u LD_PROFILE -u LD_PROFILE_OUTPUT -u LD_PRELOAD -u LD_AUDIT python3 -B net01d/followup02/native/observe_wifi_profile.py
```

The unmodified `run_native_tcp.py --case stream-01` supplies its original18
bodies/routes/RPCs/source stamps,8sim/800 STEP inputs and success conditions.
The old0cc serial native is
`/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp`.
All13 DSOs use that same existing tree's `build/lib`; no rebuild, RF parameter,
seed, transport, PCAP switch, source rate, policy or ROS code changes.

`native_profile_wifi_exec.py` is passed as the original runner's native path.
It writes its exact source, incoming arguments and prepared exec/environment,
then `os.execve`s the actual old0cc with all Hub arguments unchanged and only
`--cpuProfile=1` appended. Only that final native exec receives:

```text
LD_PROFILE=libns3.40-wifi.so
LD_PROFILE_OUTPUT=/home/zhuyulab/ns3-workspace/net-01d/workspace/net01d/followup02/native/wifi-profile-01/ld-profile
LD_LIBRARY_PATH=/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/build/lib
```

Parent runner, Hub, time/timeout and analysis Python environments omit
LD_PROFILE/LD_PROFILE_OUTPUT; no environment is exported globally. The thin
observer reuses existing `proc`/`owned_tree` helpers and saves actual native
`/proc/exe`, argv, selected environment,13 DSO maps/roots and owned ancestry,
plus absence of LD_PROFILE on other observed owned processes. It snapshots
the exact wrapper/observer/original runner/Hub/helper source at execution time.
Hub's native_cpu_profile metadata remains false because its CLI option is not
used; the actual leaf argv, native CPU boundary records and exec metadata prove
the wrapper-selected CPU mode. Do not mislabel that Hub field as actual mode.

Outputs are exclusive `native/wifi-profile-01`, `runs/ntcp-prof-wifi-01` and
`/dev/shm/net01d-f02-ntcp-prof-wifi-01`. A fresh profile directory prevents the
loader's append behavior from mixing earlier data. No old profile is deleted.
The expected retained profile is `ld-profile/libns3.40-wifi.so.profile` (loader
gmon-format data). No normal Python process is started with LD_PROFILE.

One absolute deadline is observer start+60wall seconds. Original active20,
END flush≤1/start22, Hub active25 and serial native post-END wait10 remain.
The already authorized test runner opt-in waits only until the same absolute
whole60; no new60 is appended. `/usr/bin/time -v` wraps the original runner and
waited subtree including END/copy/runner analysis. Subsequent sprof and limited
PCAP comparison must also finish inside the remaining same whole60. Timeout/
forced cleanup/partial profile is a truthful failure, not a reason to rerun or
widen any bound. The original runner uses the exec-wrapper pathname for one
cmdline cleanup probe; after exec the thin observer additionally tracks the
actual native PID/start ticks and disappearance, with the original owned-PG
cleanup retained. Wrapper pathname is never passed off as the actual ELF.

After the admitted model exits, the same harness saves these two read-only
postprocessing outputs, using the existing sprof:

```text
/usr/bin/sprof -p <same-build/lib/libns3.40-wifi.so> <fresh-libns3.40-wifi.so.profile>
/usr/bin/sprof -c <same-build/lib/libns3.40-wifi.so> <fresh-libns3.40-wifi.so.profile>
```

Actual argv, exit and stdout/stderr go to `sprof-flat*` and `sprof-call-pairs*`.
Keep raw profile and full header, including its actual sampling interval/tick
counts. Missing/incompatible/empty data or insufficient samples stay explicit;
do not synthesize a hot-function conclusion.

Own-callback CPU comes from the actual native `--cpuProfile=1`
`cpu_step_begin/end` cumulative differences over matched horizons, by the
existing fields/event/sniff/packet_trace/rx_drop/receive/transmit categories.
Inclusive parents overlap and must not be summed; exclusive scopes cover only
their instrumented portions, not the full ns-3 model. Original control-step
Run CPU/wall and GNU time whole-cost text are saved separately, with all profile
overhead included. This diagnostic is not an uninstrumented speed benchmark.

PCAP remains on. The four saved PCAPs are compared byte-for-byte to the existing
serial `ntcp-ram-r1` reference after this one model exits; no new reference run
is planned. Original18-body checks stay effective. CPU diagnostic records and
wall timestamps are not required to match; do not use a model PASS to assert
profile/clock-event equivalence or full-load300 ms success.

Interpretation is limited to **one selected Wi-Fi DSO**. `sprof` samples/ticks
and exported-interface call-pair counts are not all native CPU, all ns-3 CPU,
Wi-Fi airtime or complete cross-DSO stacks. Calls into libm/libc/other DSOs are
outside this selected object and may appear UNKNOWN; expensive libm work is
not recovered by assigning the Wi-Fi percentages to total Run CPU. LTO inline,
merged/hidden/internal functions and missing exported symbols can hide or merge
hot paths. Short statistical samples and this extra instrumentation limit
resolution. Own-callback clocks, selected-DSO samples and whole-process CPU
must remain distinct rather than combined into a false additive accounting.

Source ownership is only these new diagnostic files. The existing runner,
producer's Hub/native/host and all failed evidence remain unchanged. Deliver
source readiness now and stop; execution needs the prerequisite acceptance and
Root's separate START.

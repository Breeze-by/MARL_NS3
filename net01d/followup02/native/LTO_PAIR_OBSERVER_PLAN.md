# Thin LTO pair observer — fixed admitted native pair sealed

Root admitted the original reference→candidate pair once after accepting the
independent build identity. No fullROS/Gazebo admission follows from this file.

`observe_lto_pair.py` wraps the unchanged original runner once per selected arm.
Root separately admits reference then candidate; candidate refuses to launch if
the reference wrapper byte/resource/load proof did not pass. All fixed inputs,
8sim/20active/30hard+2TERM, C3/v2, seed/header/protocol/PCAP remain the existing
LTO_ONLY_PLAN and stream-01. No source/runner/Hub/native modification.

Each arm explicitly replaces LD_LIBRARY_PATH with only its old or new library
directory and removes LD_PRELOAD/LD_AUDIT. `/usr/bin/time -v` records its raw
output in the existing candidate evidence directory as registered in the main
plan. Those CPU/wall figures include runner and waited Hub/native/copy/summary,
not pure Native. Observer parent's CPU is excluded; one startup observation
also has nonzero host cost and is not a statistics-quality experiment.

Only descend from the actual launched time PID via each owned process's task
children, no whole-machine scan. Match native's absolute argv/exe and require
runner+Hub in its ancestry. Wait for the owned Hub socket (created only after
actual nativeREADY), then read maps exactly once; require the exact13 ns3 DSO
names, all from this arm's intended root. Save raw maps/paths/ancestry/startticks.
Stop polling immediately after capture, even if proof fails. Missing maps is
NOT_OBSERVED/failure, never substituted with ldd; mixed/ambiguous load is FAIL.

Original runner owns bounds and PG cleanup. This wrapper never sends signals or
adds its own cleanup loop; it waits for the original30s timeout and records its
true exit, runner result and a single final probe of previously observed PIDs
(startticks checked). Leftovers/forced/partial evidence retain FAIL. It neither
reads raw ledger/PCAP nor performs the independent cross-arm equality review.

Exact commands each executed once from repository root after root admission:

```
rtk proxy python3 -B net01d/followup02/native/observe_lto_pair.py --arm reference
rtk proxy python3 -B net01d/followup02/native/observe_lto_pair.py --arm candidate
```

They produce exclusive `runs/ntcp-lto-r1`, `runs/ntcp-lto-c1` and the corresponding
`/dev/shm/net01d-f02-*` paths. Observer evidence is under
`native/lto-pair-01/{reference,candidate}`. Both started only after the runtime
agent released the build window and root admitted the exact pair. No automatic
fullROS/Gazebo/retry.

Actual sourcec8ace75: reference outer0/4.979wall, candidate0/4.583wall; both
PASS_LOADED_NATIVE_BYTE_SCOPE. NativePIDs3855001/3855071 had the exact requested
ELF/owned ancestry and the actual13DSOs only in their respective roots. Each
original runner reports18/18 exact actualRX, Hub/native0, complete evidencecopy,
no forced/remaining process/PGESRCH. Allmaps/paths/time-v/exit originals retained.
Cross-arm all-event/PCAP/RX equality and CPU breakdown remain the unique
independent reader's job; elapsed time alone is not a result. Baseline compiler
FPdefault versus candidate explicitFPcontractoff is additional toLTO, so the
pair does not isolate a single compiler flag. Old fullROS failures stay FAIL.

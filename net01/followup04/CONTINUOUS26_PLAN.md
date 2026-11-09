# Unique26 low-overhead native-wait observation — pending root admission

26 is one targeted diagnostic after25 failed/incompleteEND, not a WiFi qualification retry or B permission. 24's original wall limits FAIL,25's original hardkill/incompleteSTEP CPU and allraw remain unchanged. No production/Hub/model/packet/clock/source/network changes; no ptrace, new kernel setting or package.

`native_wait26.sh` six-lineexec forwards all original argv to originalRelease82bc through the separately reviewed `native_wait_wrapper.py`. NativeFD0/1/2 inherit directly, no protocol proxy or copiedpayload. The wrapper exclusively creates `/dev/shm/net01-native-wait-26`, logs originalargv/PID and realtime+mono, and samples only its directactualchild `/proc/<PID>/{stat,schedstat,wchan,syscall}` nominally5ms. Rows are RAM-backedJSONL/lineflush, non-atomic four-file snapshots; permission errors and actualsample gaps remain raw. Nativewrite-like syscallFD targets are read-only. `wait4` preserves childexit/signal/rusage; original fixture owns hard30wall bound. Wrapper's childtermination finally is owned-only and cannot turn forcekill into normalPASS.

The existing single stdlibchild check had two checker-oracle errors (diagdirincluded inargv expectation; literalstderr escaping). Originalchecker exit1 remains. `offline-review.json` checks those same original bytes/trace without childrerun: childexit7,28samples/stdio/originalargv retained. Sourcewrapper actualCPU19.6ms over145wallms is **nonzero observer cost**, not a performance guarantee. No repeatcheck is proposed. Root/independentmetric already reviewed mechanism as LIMITED ACCEPT for diagnostic use only.

Exact proposed command from `/home/zhuyulab/ns3-workspace`:

```
rtk proxy python3 -B net-01/workspace/net01/followup04/check_controlled_wifi.py --name continuous-dds-26-native-wait-diagnostic --native /home/zhuyulab/ns3-workspace/net-01/workspace/net01/followup04/native_wait26.sh
```

Same24/25 source16wall/hard30wall includingstartup/teardown, V3/AP+3STA/fullactualCDR/Release82bc serialCPUoff/controlTraceon, controlled1000-clock100-q10ms/.5nominalwallpacer/20msactualnativecredit, TF50/30/20Hz+odom30Hz+FB100Hz+exactzero20Hz perwall perrobot,200²costmap2Hz and originalmaps, Peer10Hzsim, bounded Gateway/Peer autoGC. Every original.12lag/.4/.55source/.2receipt/.3heartbeat/mask limit remains active. 0Gazebo/Nav2/Policy/Goal/arm/NN. Flows89/95 remain ungenerated; actualA10 offered-rate differences retained, not changed to make diagnostic pass.

After the one fixture returns, retain `/dev/shm`original and copy it intact into new `runs/continuous-dds-26-native-wait-diagnostic/native-wait-trace/`. Confirm exactwrapper/native childPIDs or thiscase argv have exited; only thisownedgroup may be forced by the originalbound, recordedFAIL. Save command/exits and all native/clock/source/Peer/Gateway/coordinator raw. No oldoverwrite/deletion, repeat, extra timeout or changedrate.

Analysis is limited to longest actualnativeRun/offCPU windows and samples bracketing them: runningCPU delta vsrunqueuewait, sampledstate/wchan/syscall/actualFD, majorfault changes, samplerownCPU/maxgap. If completeSTEP CPU is missing, clearly use only availablepartialboundaries, do not invent fullRun traces. Four-file observations canrace and5ms sampling canmissshort waits; singlewchan cannot uniquely prove cause. No corresponding sample is an uncertainty, not proof scheduler/disk fault. This timing outcome is notqualification and cannot unlockB or erase24FAIL.

This is the final proposed wait diagnostic thisround. If it still cannot distinguish the originaloffCPU, stop diagnostics and finish accurateBLOCKED report/ledger/localbackup; do not create27 or consume remainingGazebo slot3 automatically. Any realGZ/B needs separate root decision/READY.

# Single25 native-wait diagnostic — pending root admission

This is a waiting-cause diagnostic, not a qualification retry. Qualification24 FAIL and its raw records remain unchanged; no B/Gazebo permission follows. No production/Hub/native/model/physics/queue/QoS/clock/source/guard changes.

Installed `/usr/bin/strace`5.16 successfully traced a newly spawned own `/bin/true` child (exit0,87.25ms). Evidence: `evidence/native-wait-tool-01/`; no permission/kernel change or package installation. This check did not start native/ROS/Gazebo.

The six-line `native_wait25.sh` forwards all argv to the existing Release82bc ELF, under `strace -f -ttt -T -yy -s0`. It traces only write/writev/pwrite64/fsync/fdatasync/futex/read/pread64/nanosleep/clock_nanosleep/sched_yield. Actual stdout/stderr business/control protocol is untouched. Exclusive `/dev/shm/net01-native-wait-25` is created on invocation (an existing directory fails visibly); trace is memory-backed, no payload text is retained by `-s0`. FD names identify ledger/PCAP/stdout/socket/kernel calls. A real system-time sample bracketed by monotonic samples is saved before exec, for alignment to native STEP mono timestamps. It is not a synthesized native clock or ACK.

Exact proposed command from workspace root `/home/zhuyulab/ns3-workspace`:

```
rtk proxy python3 -B net-01/workspace/net01/followup04/check_controlled_wifi.py --name continuous-dds-25-native-wait-diagnostic --native /home/zhuyulab/ns3-workspace/net-01/workspace/net01/followup04/native_wait25.sh
```

All prior24 conditions remain: actual V3 WiFi/full serialized payload/Release82bc serial CPUoff/controlTraceon; same MOCK_PHYSICS controlled1000-clock100-q10ms, fixed20mswall schedule and20ms real-native credit; source16wall, hard30wall including cleanup; TF50/30/20/odom30/FB100 and zero20 perwall perrobot,200²costmap2wallHz, same maps, Peer10Hzsim, bounded Gateway/Peer cyclicGC, all original.12/.4/.55/.2/.3 gates. 0Gazebo/Nav2/Goal/arm/Policy/NN. Synthetic pressure is intentionally unchanged despite A10 measured lower odom/costmap/wheel offer. Missing89/95 fixture coverage remains disclosed.

After the unique bounded fixture returns, record a second realtime/mono bracket, then copy `/dev/shm/net01-native-wait-25` intact into new `runs/continuous-dds-25-native-wait-diagnostic/native-wait-trace/`; preserve originals, wrapper command/exit and all native/control records. No old run overwrite/deletion. A failed or incomplete trace is explicit, no automatic retry or timeout extension. Any forced own-process cleanup remains FAIL.

Analysis only aligns the longest native Run windows to strace calls: long write with actual FD, futex, sleeps, or absence of corresponding blocking syscalls. Distinguish thread CPU from offCPU and strace observer overhead. No-call gaps cannot uniquely separate scheduler descheduling, page faults or untraced kernel activity; do not claim a unique OS cause. A heavily traced timing outcome is not qualification PASS and cannot unlock B or change original limits. No scan of quantum/source/network parameters, no native source edit, no new GZ.

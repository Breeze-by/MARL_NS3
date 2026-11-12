# Synchronous ledger formatting candidate

Preregistration below retained. Root checkpoint `5a1e774` and independent source
review admitted the new build and conditional fixed pair. Both cases are now
sealed and independently compared. Old ELF `1e8fdb4…` remains intact. No full
ROS/Gazebo admission follows from this native development pair.

The CPU diagnostic measured exclusive event 11.38%, sniff 9.12%, packet trace
7.25%, fields .53%, drop .45%, receive 3.33%, transmit .23%; residual 67.71%
includes model, PCAP and unwrapped formatting. These are diagnostic shares, not
a prediction of recoverable CPU or proof that logging alone causes failure.

The candidate changes only serial ledger line construction, serial sniffer and
packet-trace fields, and TCP trace numeric fields. Reserved strings and standard
`to_chars` replace chained streams/temporary strings. Floating SNR/signal/noise
retain general precision 12. Serial output uses one `ofstream.write` per record;
stream exceptions and buffering remain. Async writer, fields(Fragment), PCAP,
event order/counts/source stamps, payloads, TCP attributes, Wi-Fi, timers and
all safety thresholds are unchanged. No worker thread or additional flush.

Build proposal (requires separate root admission): existing CMake recipe and
same Release-portable libraries/header, new directory
`/home/zhuyulab/ns3-workspace/net-01d/build/followup02-native-ledger-sync`;
target `net01-payload-tcp`. Do not overwrite the original TCP build/ELF.

## Fixed development pair, not a performance study

Two serial, independently retained starts, old then new, no concurrent CPU
experiment. Cwd is the repository root. Each existing `stream-01` workload has
unchanged seed/run/topology, 3 TCP connections, six 64-byte probes at N0, six
160704-byte plus six 1MiB bodies at N4, fixed N8 end, original RPC bytes and
10ms STEP quantum; cpuProfile off, controlTrace on, asyncLedger off, same RAM
backend. Active 20wall, outer 30wall + original 2wall TERM escalation. Only ELF
and exclusive output/RAM name differ. A failed run is retained, not retried.

```
rtk proxy timeout --signal=TERM --kill-after=2s 30s python3 -B net01d/followup02/native/run_native_tcp.py --case stream-01 --output-name ntcp-o1 --native /home/zhuyulab/ns3-workspace/net-01d/build/followup02-native-tcp/net01-payload-tcp
rtk proxy timeout --signal=TERM --kill-after=2s 30s python3 -B net01d/followup02/native/run_native_tcp.py --case stream-01 --output-name ntcp-n1 --native /home/zhuyulab/ns3-workspace/net-01d/build/followup02-native-ledger-sync/net01-payload-tcp
```

Exclusive destinations are `followup02/runs/ntcp-o1`, `ntcp-n1` and
`/dev/shm/net01d-f02-ntcp-o1`, `net01d-f02-ntcp-n1`. Original runner defaults
and prior cases are unchanged.

Before reporting benefit, require both original runner byte/resource predicates;
all 18 received files byte-identical across the pair and to their intended bytes;
all four PCAP files byte-identical with the same file set; every ledger row in
the same order has identical parsed key set and numeric/string values after
removing only `monotonic_ns`. No SNR tolerance or post-result relaxation. All
native summary/model counts, TCP defaults, queue/debt/expiry and final horizon
must also agree; diagnostic wall/CPU timestamps are compared as measurements,
not equality fields. Any mismatch stops progression.

Use existing control-step traces for per-Run CPU/wall sum, median/p95/max;
native stderr control boundaries for ledger barrier CPU/wall; ledger-status
`model_cpu_ns` for total Native main-thread CPU (not all host-process CPU), plus
original runner wall/copy timings. CPU categories are off in both paired runs.
One pair gives development evidence only, not statistical superiority or a
300ms ROS/Gazebo qualification. Full ROS requires separate review/admission.

## Execution record

`native/sync-build-01/`: configure0/1.126wall, build0/31.297wall. New ELF
524472B, SHA256 `eb7a3984f07a9715786491c82d26de7e81ea174a7c00a4ad7cbf58228d928daa`;
ldd0 and all13 ns3 DSOs in the original registered Release-portable root.
Header/CMake/old ELF identities reused without rehashing the old tree.
`native/sync-pair-01/` holds exact argv/stdout/stderr/exits for both starts.
Old/new outer exits0/0 (8.520/8.386wall), both existing runner byte/resource
checks passed18/18 with Hub/native0, full copy, no force or remaining owned
process.

Independent `analysis/sync-format-pair/comparison.json` verifies all294775
ordered ledger rows per case equal after removing only monotonic_ns, exact
parsed numeric values including SNR, all four PCAPs and18 RX files byte-equal,
and matching counts/configuration/debt/summary. Run CPU sum3789.794→3469.016ms
(-8.46%), Native main-thread CPU3886.444→3566.980ms(-8.22%), Run wall sum
3803.664→3484.221ms(-8.40%). Runner wall8.150→7.956s(-2.39%). Median/p95
STEP cost did not improve; maximum new STEP remains144.154wallms. One fixed
pair is development evidence, not statistical superiority or300ms capacity.

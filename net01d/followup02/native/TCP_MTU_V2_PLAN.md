# tcp-mtu-v2: fixed MTU-based transport baseline proposal

Minimal source candidate checkpointed `ca9ea8c`; root admitted one independent
Release build and one fixed native stream case, now sealed and independently
accepted for byte/packetization scope. The subsequently admitted first real ROS
full qualification tcp-mtu-01 failed; no Gazebo run or retry is automatic.
Original UDP, tcp-v1/536 and all previous failures remain available/unchanged.
This is a new transport baseline configuration, not a claim that536 is a bug,
not a pure logging optimization and not an RF/safety/rate parameter search.

## One explicit change

Add transport enum `tcp-mtu-v2`. In `setupTcp`, only for this enum, set
`ns3::TcpSocket::SegmentSize=1448` before creating any client/listener socket.
No setter in the established accepted callback. Listener fork inherits TCB;
record actual attributes of all3 listeners and all6 connected endpoints.
For tcp-v1, do not set the default: its existing536 remains. Each invocation
selects one version; no silent fallback, reconnect or in-process version switch.

Fixed local source facts: MTU1500 on Wi-Fi and CSMA, IPv4 without options20B,
ordinary TCP data header20+timestamp10+padded2=32B, giving1448data bytes.
`analysis/TCP_PACKETIZATION_REVIEW.md` records the exact installed ns3.40
source/line references, including Fork and the established-socket setter abort.
1460 would produce1512B IPv4 with the current timestamps; do not use it.

No change to36B Fragment wire headers,1164B fragment payload, original full
message bytes/IDs/flows/from/to/source time, native queue8MiB per endpoint,
.5sim reassembly,3 full-duplex connections, source order, RTO/DelAck/noDelay,
buffers, congestion algorithm, initial window **segment count**, wireless,
source rates/QoS, frozen policy, safety deadlines or stop/ownership semantics.
InitialCwnd remains10segments but its byte amount changes5360→14480; ACK,
airtime/error/queue and congestion trajectories may change. HOL/default1sim
MinRto remain limitations. Do not call a byte-window change CPU-only benefit.

## Minimal file boundary

- `net01/native/payload_transport.cc`: admit enum, route both TCP versions to
  existingTCP functions, preserve UDP default and TCP END/error paths.
- `net01d/followup02/native/tcp_stream_draft.inc`: the conditional pre-creation
  default, actual listener/endpoint attributes, correct version/config evidence.
  No new send/receive algorithm or frame format.
- `net01/tools/packet_hub.py`, `net01/host_run.py`, `net01d/run_replay.py`:
  explicit enum passthrough, defaults unchanged; no hidden version selection.
- `native/run_native_tcp.py`: optional explicit enum (defaulttcp-v1), reused
  original stream workload and exclusive output name. No copied runner.

Use the already verified synchronous formatter; preserve original1e8/eb7 ELF
and build directories. New build proposal `build/followup02-native-tcp-mtu-v2`,
same Release CMake, libraries/header; a build needs separate root admission.

## Minimum first validation, separately admitted after source review

One fixed stream case, same RNG/config and input as the old18-message proof:
six64B handshake probes N0; six160704B and six1MiB bodies N4; endN8; STEP10ms;
20activewall/30outer+2TERM; control trace on/cpuProfile off; exclusive RAM.
Proposed command from repository root (not admitted):

```
rtk proxy timeout --signal=TERM --kill-after=2s 30s python3 -B net01d/followup02/native/run_native_tcp.py --case stream-01 --output-name ntcp-m2 --native-transport tcp-mtu-v2 --native /home/zhuyulab/ns3-workspace/net-01d/build/followup02-native-tcp-mtu-v2/net01-payload-tcp
```

Require actual3connect/3accept, all18 original body/route/RPC/source exact,
bounded partialSend/GetTxAvailable/SendCallback and Recv framing accounting,
no firsterror/expired/forced cleanup, real Hub/native0 and complete evidence.
Record actual partial/coalesced paths, not assume their observation fromv1.

Record actual effective SegmentSize1448 at3 listeners and6 endpoints, plus
Timestamp/Sack/WindowScaling, InitialCwnd segments/derivedbytes, all existing
buffer/RTO/DelAck/noDelay/Cubic attributes; explicitly list only SegmentSize
as configured. Confirm data timestamps/options from actual packets rather than
defaults alone. Original v1 attributes are already recorded, no old tree rehash.

Parse all4 native Wi-Fi PCAPs: for actual IPv4 frames require total_length<=1500
**and MF=0 and fragment_offset=0**, and for ordinary TCPdata header_length32,
payload<=1448. At least one full1448 data segment must be observed; SYN/ACK
options are reported separately. Smaller fragments also satisfy total<=1500,
so that size test alone is insufficient. Use existing available tooling or one
small offline reader for the actual native PCAP linktype, no dependency install.

PCAP bytes, packet counts, segmentation and model event trace may legitimately
differ fromv1. Verify semantic application bytes/IDs/order/Goal inputs, not
identical packetization. Native opaque bytes do not themselves test real Goal:
subsequent root-admitted full32normal/60hard realROS replay must retain typed
Goal CDR/UUID/feedback/result/cancel and original guards/ownership checks.
Only after these data can root decide further Gazebo qualification. Neither a
stream pass nor a lower event/CPU count guarantees the unchanged300ms bound.

Future A0/A1/B/C comparisons must preregister this common new baseline and
measure native/control/encoding cost separately; old results are not rewritten.

Implementation note: the actual installed TypeIds confirm `InitialCwnd` in
tcp-socket.cc:85 and `WindowScaling`, `Sack`, `Timestamp` in
tcp-socket-base.cc:109–124. The six-source candidate changes no other setter.
New records use `tcp_effective_attributes` / `tcp_listener_effective_attributes`,
not a misleading defaults label; saved transport/override boolean/map reflect
the selected version. New v1 still uses536 but receives the same additional
passive attribute observations. All old ELF/raw results remain unchanged.
Existing tcpdump is available; tshark is not installed. PCAP validation is an
offline independent requirement, separate from runner byte-only PASS, not a
reason to install tools or silently infer the absence of fragmentation.

Build execution: configure0/1.168wall, build0/32.079wall, zero model starts.
`native/mtu-build-01/` contains exact commands/logs/exits/identity/flags/link.
New ELF528440B SHA256
`c3e9913c4ad77cf76399f43f7e7aa559634b81440c360edc69b5ff20dc50d1d4`;
ldd0,13 ns3 libraries in the original registered Release-portable root.
The subsequent admitted `ntcp-m2` actual run exited0 (outer4.732wall,
runner4.309wall),18/18 byte/route/source exact,3listener+6endpoint effective
MSS1448 andInitialCwnd10segments/14480B, all original RTO/buffer/option assertions
passed. Actual Send offset resumes observed, Recv split5163/coalesced1071.
Hub/native0, complete copy, no force or remaining process; small result and
argv/exit are in `native/mtu-stream-01/`. Independent review
`review/TCP_MTU_V2_ACTUAL_REVIEW.md` confirms all four actual PCAPs: no IP
fragment/unknown decode, dataheader32 and payload<=1448/full1448 observed,
using a reader calibrated against old536 rather than a zero tcpdump filter.
This is native byte/packetization scope, not300ms/full capacity.

Root5a11fad admitted the exact `TCP_MTU_FULL_ADMISSION.json` command once.
Real ROS tcp-mtu-01 exits1 (outer11.866wall, host9.907wall), first host fault
sample tb1 bound_mask_receipt_stale; normal32 incomplete. Three accepted
controlled Goal UUIDs each had actual local Cancel0/GetResult5/PAUSEtrue,
cleanup marker before STOP, no forced/remaining owned process. Original failure
is preserved; unique auditor handles actual firstlatch/native/transport cause.

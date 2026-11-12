# TCP copy candidate — source ready, execution not authorized

Base: immutable old0cc driver-src in `/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-src/`, not current RAM-capable driver source. Production and followup02 source/evidence remain unchanged. New external artifact root: `/home/zhuyulab/ns3-workspace/net-01d/native-copy-cost-followup03`.

`tcp_stream_draft.inc:190–193` copies each TX chunk into a temporary Packet, prepends the36-byte Fragment, then copies the entire frame to a vector. `tcpPump:49–50` later creates the actually sent Packet from that vector. The patch removes the first physical payload Buffer write/read: keep one Packet at the same scope/lifetime using `Packet(header.length)` virtual zeros, original AddHeader, CopyData only36header bytes, then copy actual body directly into the same vector. Queue sizes, offsets, subsequent socket packets and event sites are unchanged. No speedup claimed.

ns3 packet.cc:179–219 shows both sized and data constructors allocate the same single global PacketUID and identical metadata(uid,size). packet-metadata.h:709–720 and packet-metadata.cc:650–680 show why an empty Packet is insufficient: enabled metadata would lose one payload/chunkUID insertion. Sized virtual zeros preserve that insertion and original AddHeader. Original Fragment::Serialize still executes once; no new Packet, RNG or scheduled event is introduced. The temporary is never socket-sent/traced/tagged. Buffer allocator/free-list/zero-area trajectories legitimately differ; do not claim identical allocation/cache behavior.

RX audit (`tcpReceive:75–93`, payload_transport.cc:136–164): actual socket bytes are copied to incoming, a36-byte probe Packet is made, then a full-frame Packet and final reassembly copy. These are concrete costs but unchanged here; bypassing the shared receiveFragment path would broaden this candidate and its PacketUID/metadata proof.

Prepared recipe: `rtk proxy bash net01d/followup03/native/build_tcp_copy_driver.sh run`. It copies only the immutable driver-src snapshot, applies the single patch there, uses its CMake and unchanged13 LTO libraries/O3/LTO/-ffp-contract=off, records exact one-patch source diff, actual build timing/exit, ELF identity and link closure. It does not rebuild libraries or start models.

Prepared arm commands, only after separate root admission:
- `rtk proxy python3 -B net01d/followup03/native/run_copy_pair_arm.py --arm reference`
- `rtk proxy python3 -B net01d/followup03/native/run_copy_pair_arm.py --arm candidate`

The thin entry imports the unchanged old stream runner and changes only BASE to followup03/output names and explicit ELF. Original18opaque bodies/8sim/800steps, serial ledger and20active/30whole/END/cleanup bounds remain. Existing f02-prefixed RAM naming is retained with new exclusive `ntcp-copy-r1/c1` names. Root must serialize arms; no automatic candidate/retry. Existing loader-observer helpers can wrap these entries to save actual ELF/13DSO maps and owned-chain proof before accepting the pair.

Minimum semantic comparison: all18 actual bodies/routes/source/IDs exact; ordered complete ledger identical after removing only real monotonic timestamps; all native simulated timestamps and packetUIDs exact; all4PCAP bytes exact; same effective transport/radio/attributes; complete END/owned exit. This catches UID/global side effects visible in actual packets/events as well as encoded-frame drift. It is a bounded fixture, not a proof of every future scheduling path. Performance must compare actual RunCPU/wall and waited-subtree CPU separately; only a clear benefit plus source review justifies a later original Full qualification. No automatic Gazebo.

Static only: patch application check and shell/Python syntax. No builds/models at SOURCE_READY.

Actual isolated build: configure exit0/1.62wall; build exit0/35.53wall; identity and timing raw bytes copied to native/copy-build-01. New ELF SHA5a176ead03765473a5880f681d2b792cb94629079bc86525c77042614cbf232d. Exact admitted one-patch source delta and same13 linked library closure passed.

Actual maps wrapper source: `observe_copy_pair.py --arm reference|candidate`, gated by false TCP_COPY_PAIR_ADMISSION.json. It reuses proc/owned_tree/MODULES from existing observer, discovers only this launched subtree, reads one actual READY maps, then stops observing and waits original runner exit. GNU time includes native TX outside Run. Pair analysis must also use ledger-status model_cpu_ns (after finish) and separate perSTEP RunCPU; no new cpuProfile instrumentation needed. No pair execution at this stage.

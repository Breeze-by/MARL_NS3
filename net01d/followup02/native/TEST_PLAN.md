# TCP-v1 native validation — built; individually admitted cases

Retain the original SEND/KNOWN/STEP/POSITION/END/RX IPC, 36B Fragment header,
<=1164B payload, ID/offset/flow/source, and original 0.5sim reassembly deadline.
Carry these frames on three true full-duplex ns3 TCP connections. Read/record
TCP defaults rather than changing them. TCP recovery after the original message
deadline can still legitimately expire; reliable bytes do not prove 300wallms.

First proposed native-only test uses the actual new ELF plus existing Hub:
three robots, both directions, 160k bound-size bodies and an opaque body larger
than the default SndBuf, unique IDs and exact original bytes. Demonstrate actual
GetTxAvailable backpressure and SendCallback resumption, frame-offset progress,
real Recv split/coalesced parsing, exact complete RX and no sender-cache RX.
Socket acceptance is not remote delivery. Record actual TCP attributes,
SYN/data/ACK/sequence extents and original MAC/PHY/PCAP. No hidden reconnect.

A separately preregistered blocked/restored phase may examine retransmission,
unchanged expiry and HOL, without RTO tuning/fallback or a deadline-PASS claim.
Exact3case duration/count/argv are fixed in CASES_ADMISSION.json; all three are sealed under separate root admissions. Any first failure is preserved;
there is no automatic ROS/Gazebo progression.

After native correctness, reuse independent real-DDS full replay, original
four-Goal Action/health/mask/89/95/source contract and 32normal/60hard. Record
protocol CPU/bytes/ACK/HOL cost independently of RF. All later comparisons must
freeze the new transport version beforehand. A1's ideal local backend is not a
TCP timing baseline; do not silently pool its dispatch cost with modeled TCP.
No policy, safety threshold, source rate, QoS, wireless or host NIC change.

Fixed before results: each of six direction endpoints has an8MiB unsent-byte budget, including all36B headers. Check body+allframeheaders atomically before queue admission; budget overflow is an explicit native error, with no drop-old/truncation/rate change/reconnect. Send acceptance decreases only unsent bytes; socket-buffered bytes remain separately visible and do not mean application delivery. END lists actual unsent IDs/fragment offsets/accepted-prefix, queue current/peak/budget and partial-RX/socket-buffered right-censoring; never claim FIN/drain from global completed. A direct native over-budget negative must prove no partially queued message/transport fallback, under its own reviewed process bound.

Buildconfigure/build both0, ELF1e8 fixed; compiled source4f78de8 and runner7cc6f5f. Stream18/18 exact bodies, realpartial-frame writes and6240Recv split completions; coalesced branch NOT OBSERVED. Current default actual NoDelay=true/Cubic/MSS536/MinRto1Nsec, read from sockets, not set. All TCP native cases are unpaced logical-time and not original300wall qualification.

Radio12/12 exact RX but required TCP overlap not observed: original diagnostic
assertion FAIL retained, not a byte-delivery or300ms failure. Budget expected
atomic rejection retains actual native1/HubFAIL. Subsequent real ROS full
tcp-current-01 and CPU diagnostic tcp-cpu-01 both FAIL and remain separate.
The synchronous-format development pair is registered in SYNC_FORMAT_PLAN.md;
its equivalent native bytes/events and lower aggregate CPU do not establish
full ROS/Gazebo timeliness.

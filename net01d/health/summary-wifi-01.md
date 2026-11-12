# P1 B health-profile-wifi-01: no historical137ms recurrence

Sources: saved new case Gateway/Peer trace; no ledger/PCAP/bag. Reusable
`analyze_trace.py` produced [summary-wifi-01.json](summary-wifi-01.json), exit0;
the targeted source/receipt split is [gap-wifi-01.json](gap-wifi-01.json).
Producer-side analysis only. Six roles0/23.127814wall/no forced termination;
control plus actual WiFi, synthetic sources, no89/95/Goal/Policy/SLAM/Nav2/Gazebo.

| Same-sequence span, ms | flow31 p95 / max | flow51 p95 / max | flow71 p95 / max |
| --- | ---: | ---: | ---: |
| Raw health DDS return→C callback |13.862 /16.297|14.351 /16.825|17.125 /19.075|
| Raw return→actual R guardian receipt |36.749 /47.100|44.112 /57.768|52.703 /63.060|
| Health queue→kernel complete flush |.126 /.169|.104 /.229|.112 /.160|

Peer trace contains81 source sequences, C captures75/75/75 and R intake75/75/74.
Do not replace these counts with a zero-loss claim. The helper retains per-stage
coverage. C serialization maximum.089941ms, C callback.429754ms,
R decode.239461ms, guardian call.065247ms.

Three whole-role receipt intervals exceed300ms:301.354721/305.595966/312.650892ms.
All are **seq7→8 bootstrap**, old source `ready=false,missing_odom` and new source
first `ready=true`; every guardian is unarmed. Source raw-return interval was
287.010240ms, plus new-minus-old delivery path14.344481/18.585726/25.640652ms.
Do not characterize this as an armed normal-phase failure or hide it.
Consecutive source-ready pairs each have n72, max278.257979/281.131403/269.613264ms,
zero>300ms. Source readiness and intake acceptance do not certify actual armed safety.

No individual wait/handler/hub/journal span reaches10ms. Largest C/R wait calls
3.679862/4.098031ms; largest C handler boundmask2.844703ms; largest R handler
readiness1.608318ms; hub poll8.635514ms, journal.424290ms. Only inclusive poll
(147.198232wall/146.716038threadCPUms) and startup inclusive progress
(54.445082/54.341225ms, installation) exceed10ms. These are accumulated/nested
work, not100ms health-blackout owners. STEP queued→actual ACK n811,
p9550.784327/max85.306752ms, includes IPC/dispatch/Run/ACK, not simulated airtime.

The old B137.93ms wait is not reproduced or repaired. No trace establishes a
single>100ms function, OS stall or unique DDS cause. Full-load/armed operation
remains to be implemented and separately admitted; no safety limit is changed.

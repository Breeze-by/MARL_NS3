# Native service-cost independent review

**Limited acceptance of the exported conditional service statistics.** This does not upgrade A0/process/NETD status or complete overall cost attribution. Read only new B02/C JSON, manifest, execution record and previously reviewed schema/extraction source. No original ledger, Gateway, PCAP, bag or stderr was reread; no test/model was run by this reviewer.

Actual exit0/activationfde3cdbf completes one full stream per correct sibling `.network/native/packet-ledger.jsonl`: B02 18,693,385rows/3,123,224,761B/191.729123s; C18,722,606rows/3,124,389,295B/187.390982s. Manifest opens1 each, no retry or prohibited original reads. Loose process-clock observations are not exact spawn/exit timestamps.

## Identity, framing and population

B02 matches **10799/10799** selected IDs and C **10801/10801**, with no cache-metadata missing/ambiguous IDs, ingress/deliver duplicates, missing stage or integrity/extent mismatch. Original cache sender/receiver/flow/bytes matches native from/to/flow/whole total, including the8B RPC prefix. Completion ns matches Gateway native RX ns.

The real TCP application frame has **36B header plus body**, with1164B body chunks; there is no additional4B TCP-frame length prefix. Expected framed bytes are903,990,653/904,140,696, exactly equal to offered/accepted Send totals. Body/RX totals876,580,325/876,725,292B and chunks761398/761539 also agree. More Send calls than frames (extra69230/70175) reflects incomplete frame prefixes including GetTxAvailable-limited calls. Offered and accepted totals are equal: this is not evidence that Socket::Send returned fewer bytes than offered. Prefix/offset/chunk checks handle actual multi-call frames.

The denominator is already conditional on **normal R-consumed health/mask IDs**, not all source/native ingress or a loss denominator. Native events before the R-clock bracket remain linked (5/3 ingress IDs), preserving causes rather than truncating every stage to the intake window. These joins establish the selected cohort's identities and complete byte extents, not all-flow delivery qualification.

## Simulation service statistics

| Scheduled admission→complete reassembly | B02 | C |
| --- | ---: | ---: |
| n | 10799 | 10801 |
| median sim ms | 8.910198 | 27.665324 |
| p95 sim ms | 17.317561 | 53.256243 |
| p99 sim ms | 19.315920 | 60.688117 |
| max sim ms | 23.582208 | 82.456931 |

Nearest-rank percentiles/arithmetic median and explicit unavailable0 are retained. Worst B02 message123367 has admission101100000000→complete101123582208ns; worst C28247 has32390000000→32472456931ns. Their differences match the reported maxima; original message/flow/sequence/bytes and Send witnesses remain in the output. No negative differences are recorded.

`admission_ns` is scheduled native injection, not ROS source/header time or necessarily ingress event time. First positive Socket::Send acceptance is at the same **simulation timestamp** as admission for this cohort; reported0sim gap does not mean0wall/CPU or absent host scheduling work. Last-Send and completion spans include application/TCP queue, protocol and Wi-Fi retry/reassembly service. They are not PHY TX timestamps, isolated RF airtime or per-packet CPU. Stages/quantiles cannot be summed or subtracted to partition CPU and radio costs.

Run/STEP wall/CPU remains UNMEASURED by this export because boundaries are stderr and were not read. Only witness monotonic stamps are present, not a measured full wall/CPU decomposition. Cross-arm trajectories/offered loads/achieved RTF differ; descriptive C service being larger does not by itself causally explain exploration T95. Overall seven-question attribution remains **PARTIAL**, A0 controller1/process FAIL and final NO-GO remain; no further read or experiment is authorized here.

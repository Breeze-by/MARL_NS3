# Four-arm Gateway cost independent review

**Limited acceptance as descriptive exported costs, with the Peer interval label clarified below.** No case/process/NETD qualification is upgraded. Read SUMMARY/read manifest and selected fields from the four small arm JSON outputs; source/statistic logic was previously reviewed. No original Gateway/A0 safety/native ledger/PCAP/bag was reread or test/model run by this reviewer.

The actual manifest records one Gateway decode per arm, one additional16.85MB A0 safety decode, no native/PCAP/bag reads and no complete cache copy. Source identities are actual launched AAE/2be/AAE/bd663. A0's explicit PROCESS_INTEGRITY_FAIL/controller1 remains alongside raw host0/networktrue; good cost/CDR/cohort values do not erase it.

## Peer timing is wall, not full callback CPU

`Peer/batch_entry_to_health_return` has1800 samples per arm and unit **wall_ms**. Actual original source measures `publish_masks()` entry through health publish return: snapshot, three grid/build/data/publish operations and health serialization/publish are enclosed. The later `event_lines.append(json.dumps(...delivery_timing...))` is outside this interval. Therefore SUMMARY's “Peer整批p95 wallms” means **Peer entry→health-publish-return p95 wall**, not the complete callback or CPU. Its p95 values29.379746/23.483786/28.284094/26.487036ms need no recomputation.

`peer_timing=false` disables the separate optional timed-call/threadCPU wrapper; it does not remove these original unconditional inline wall timestamps. No full Peer callback CPU measurement is manufactured here. Source snapshot-only p95 is separately0.146074/0.121727/0.139777/0.135626wall ms.

## Matching, clocks and sample populations

All applicable exported joins have missing0/ambiguous0 and excluded ambiguous-index rows0. A1 explicitly counts16200 not-applicable joins; those socket/native-business costs are not zero-delay measurements. Selected health totals are5400/5400/5399/5400, with B02 tb1=1799; selected masks5400/5400/5400/5401, with C tb2=1801. These are separately bounded intake/accept cohorts, not loss or duplicate-message estimators. Accepted gap predecessors may lie before the normal bracket. The read windows preserve original sim endpoints and discrete actual R-clock monotonic bounds rather than assuming exact Observer endpoint equivalence.

| Arm | tb3 health publish-begin→intake p95 wall ms | tb3 wrapper-capture→mask accept-before p95 wall ms |
| --- | ---: | ---: |
| A0 | 3.314087 | 9.121419 |
| A1 | 19.548386 | 26.843634 |
| B02 | 102.311895 | 133.442568 |
| C | 125.249894 | 165.934741 |

Each table entry has1800 measured samples; min/median/p95/p99/max, units, stage attempts and unavailable counts are retained. Source uses nearest-rank percentiles/arithmetic median. The review checks reported output/logic, not independent raw-data recomputation. Wall, threadCPU and sim fields remain distinct. Publish-end signed spans/receiver work can overlap; inclusive dispatch and source stages or separate quantiles cannot be summed/subtracted into a pure RF/CPU partition.

Whole Guard latched_INVALID counts are0 for these four records, but exact per-message receipt_sim and continuous source-age/receipt safety margins remain **UNMEASURED**. B02/C tb3 mask wallgap bracket maxima307.979652/310.647150ms describe wall cost, not violations of the authorized sim300 receipt contract or proof of legacy wall300 compliance. Observed R-clock source ages use explicitly different A0 after-call and adapter before-call snapshots; they are not exact receipt_sim.

## CDR and acceptance scope

A1/B02/C health producer→C and C→R existing hash/byte checks respectively measure5400/5399/5400 equal samples; mask binding→original publication measures5400/5400/5400/5401 equal samples across all arms. Missing/ambiguous/mismatch counts are0 in those measured joins. A0 direct health has no corresponding CDR hash oracle and remains NOT_MEASURED. Matching samples and whole-flow multiset counts have different boundaries; neither establishes all-flow delivery or network PASS.

Actual RTF, input availability, trajectories and A0 source placement differ. A0 removes direct/adapted topology and conversion work together, so arm differences do not isolate serialization or PHY causes. The separately admitted B02/C native pass is still outside this review until its small outputs arrive; no native service/TX/airtime or per-message CPU is inferred from the Gateway table. Original A0 process FAIL and overall NO-GO remain.

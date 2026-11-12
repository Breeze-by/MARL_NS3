# A1 actual-phase: sealed normal-window audit

Actual C marker interval: `519708730329220` to `519740731232131` monotonic ns, **32.000902911 wall s**, 16.01 simulated s, RTF 0.500298. All distributions below use this normal interval; the later intentional stop-supply negative is excluded.

All displayed intervals are wall ms; source ages are explicitly sim ms. Quantiles use nearest rank; median uses the usual midpoint. Full n/min/median/p95/p99/max for all fields and all robot combinations are in `normal-window.json`.

## Health receipts

| Robot | n | min | median | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| tb1 | 160 | 180.331 | 199.522 | 211.722 | 220.283 | 221.852 |
| tb2 | 160 | 180.307 | 199.541 | 210.995 | 220.282 | 221.824 |
| tb3 | 160 | 180.025 | 199.729 | 214.608 | 223.392 | 225.383 |

All 480 health intakes were armed, returned true, and have no fault before/after. The first interval on each robot starts at its real preceding receipt, which precedes C t0; this boundary is recorded explicitly. Incoming source-age maxima are 70 sim ms for odometry and 40 sim ms for correction. Previously held odometry reaches 170 sim ms; held correction reaches 130/130/140 sim ms at tb1/tb2/tb3 intake. These use the actual R node clock recorded at intake, not native ACK or an inferred clock. These sampled maxima do not assert a continuous maximum across every guard timer evaluation.

## Mask acceptance intervals

| Robot | n accepted | rejected | gap lower max (ms) | gap upper max (ms) |
|---|---:|---:|---:|---:|
| tb1 | 160 | 0 | 227.871 | 228.158 |
| tb2 | 160 | 0 | 225.080 | 225.333 |
| tb3 | 160 | 0 | 224.840 | 225.110 |

The true acceptance instant lies between before/after calls. Gap lower = next-before minus previous-after; gap upper = next-after minus previous-before. The first preceding acceptance may be before t0. Exact mask-consumer Rsim was not recorded, so no exact mask-accept source-age distribution is invented.

## TF metadata (R take entries inside normal window)

| Flow/writer | n | sourceTS→receivedTS median/p95/p99/max (ms) | receivedTS→take median/p95/p99/max (ms) |
|---|---:|---|---|
| (23, 'both_wheel_TF') | 161 | 0.032 / 0.062 / 2.576 / 3.165 | 20.354 / 27.628 / 45.699 / 65.062 |
| (63, 'map->odom') | 1601 | 0.075 / 0.139 / 0.470 / 7.106 | 11.632 / 29.307 / 52.378 / 75.369 |
| (23, 'map->odom') | 1598 | 0.108 / 0.145 / 0.403 / 3.968 | 8.152 / 24.976 / 55.772 / 88.543 |
| (43, 'map->odom') | 1598 | 0.074 / 0.126 / 1.399 / 3.685 | 10.281 / 35.092 / 70.962 / 111.292 |
| (43, 'odom->base_footprint') | 481 | 0.039 / 0.058 / 0.121 / 2.738 | 11.643 / 20.721 / 77.438 / 90.839 |
| (43, 'both_wheel_TF') | 160 | 0.032 / 0.050 / 0.077 / 0.108 | 23.348 / 38.532 / 103.994 / 108.181 |
| (63, 'odom->base_footprint') | 480 | 0.038 / 0.063 / 0.542 / 15.973 | 9.279 / 28.965 / 54.712 / 76.067 |
| (23, 'odom->base_footprint') | 480 | 0.037 / 0.056 / 2.359 / 4.096 | 10.225 / 21.468 / 47.337 / 69.380 |
| (63, 'both_wheel_TF') | 160 | 0.032 / 0.058 / 2.022 / 2.937 | 15.175 / 22.370 / 50.027 / 68.764 |

Normal takes: 6719; strict joins unmatched=0, duplicate identities=0. Join is flow + writer kind + actual source timestamp inside the source publish realtime bracket. No nearest-time or repeated-header identity is used. System-time differences are kept separate from monotonic publication-return→take, which is also recorded. RMW received_timestamp is not independently established as earliest arrival or reader-ready. Whole-case `summary.json` includes bootstrap/negative and is not substituted for these normal distributions.

## Actual supply and physical credit

| Robot | normal odom / odomTF / wheelTF / correction publications | normal map / costmap | final configured skips |
|---|---|---|---|
| tb1 | 480 / 480 / 160 / 1597 | 6 / 27 | {'odom': 0, 'wheel': 0, 'scan': 0} |
| tb2 | 480 / 480 / 160 / 1597 | 6 / 27 | {'odom': 0, 'wheel': 0, 'scan': 0} |
| tb3 | 480 / 480 / 160 / 1600 | 6 / 27 | {'odom': 0, 'wheel': 0, 'scan': 0} |

Publication counts are actual emitted records whose publish-before monotonic stamp is inside the C window, not full-source cumulative ticks. Active/quiet tick baselines, clock origin, scan header and actual full-supply wall/sim intervals are retained in JSON. Final skips are zero throughout all three source runs; bootstrap ticks are not counted as emitted normal observations.

Normal physical ACKs=1600; all success/10 steps; E−latest observed G counts={'0': 1600}. All 1600 normal tokens satisfy physical end ≤ fixed anchor + actual native ACK + 20 ms (actual credit median10/p95/max20 sim ms). Pacer lateness median 0.723, p95 1.292, max 29.623 wall ms.

## Audit execution and limit

`analyze_dds_audit.py --case net01d/runs/actual-phase-local-01 --out net01d/health/actual-phase-local-01` was executed once via `rtk proxy python3 -B`, exit0. Its first Gateway read supplied the common health/control/component export and whole-case TF join summary. A root-authorized second Gateway read in `summarize_normal.py` supplied only the missing exact normal TF cohort; the original summary was not overwritten. That script exited0. Subsequent table generation reads only `normal-window.json`. No production source, report, original raw evidence or Git state was changed; no node, native simulation, Gazebo, bag replay, new trial or hash scan was run. This is controlled stationary fixture evidence, not real SLAM/Nav2/Gazebo physical qualification.

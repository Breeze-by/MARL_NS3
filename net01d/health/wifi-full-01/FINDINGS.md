# Complete Wi-Fi B01: first normal-phase freshness failure

Original case `net01d/runs/full-load-wifi-audit-01`, b043830. Producer-side
read-only analysis; no rerun, source edit, ledger/PCAP scan or new simulation.
Action/89/95 and cleanup verdicts remain with their assigned reviewers.
Derived exact fields: [first-fault-subset.json](first-fault-subset.json),
[hub-native-subset.json](hub-native-subset.json), [TF joins](dds/summary.json).
The normal32wall phase stopped early; the planned negative phase was not reached.

## Actual first fault and affected records

- tb3 original health-heartbeat trip mono517272.979286441, Rsim2.65. Last
  health seq25 receipt517272.674910945, age304.375496ms at trip. Seq26's
  receive_health first checks that old interval, then stores new receipt at
  .979939688; the already-expired interval remains latched.
- tb1 mask-receipt trip517273.002173583. Last accepted mask25 receipt is
  bracketed by accept call517272.690175531–.690338564: age311.835–311.998ms.
  New mask26 is actually complete and decoded; its accept begins.002080108,
  checks the old interval and returns false after the original trip.
- tb2 mask-receipt trip517273.044692720. Last accepted25 is bracketed by
  517272.734181293–.734313872: age310.379–310.511ms. No complete new26 is
  observed at R before the fault. tb3's old mask was not yet300ms old.
- Host FIRST_FAILURE517273.052757240 is later detection, not first trip.
  Gateway.failure remains null; per-robot actual guards are genuinely invalid.
  Original limits and tick-before-update behavior explain the faults.

Peer25 and26 are both ready, with good original odom/correction stamps/ages.
This is not the previous A1 stale-correction failure. Source state snapshots
are517272.591466389 and.855837555:264.371166ms apart for.1sim advance.
Snapshot→health publish-before takes59.978120 and62.503090ms, containing the
original three-mask construction/publication path. These are separate from
already-published message waiting. No instantaneous source/header rewrite is used.

## Exact tb3 health25→26 decomposition

All following wall boundaries use same-host monotonic seconds517272+fraction.
No simulated network elapsed time is subtracted from these wall timestamps.

| Observed stage | seq25 | seq26 | Path25 /26 ms |
| --- | ---: | ---: | ---: |
| Underlying raw health DDS publish return |.651678384|.918571051|—|
| C flow71 callback entry |.655415149|.936574688|3.736765 /18.003637 from raw|
| Hub complete ingress |.655791488|.945015307|.376339 /8.440619 from C|
| Hub reads actual complete native RX |.673101411|.976892884|17.309923 /31.877577 from ingress|
| Actual guardian new receipt |.674910945|.979939688|1.809534 /3.046804 from Hub RX|

Source raw-return interval266.892667ms; old raw→receipt23.232561ms,
new61.368637ms. Actual receipt interval305.028743ms is exactly
266.892667 +61.368637 −23.232561. Do not add both path delays to the source period.
After the new raw return, only56.339894ms remained to the old300ms deadline
.974910945. Hub's complete RX already follows that deadline by1.981939ms;
new guardian receipt follows it by5.028743ms. There is no137ms C-capture gap:
ordinary source cadence and path variation jointly exhaust the original budget.

## Actual native/IPC stages, not all air propagation

Seq26 health is native ID2815, admission2.63sim, actual RX2.632037257sim:
2.037257ms of simulated elapsed delivery. Old seq25 ID2646 was admission2.52,
RX2.522188414:2.188414simms. Simulated delivery elapsed did not suddenly become
the61ms wall path. Hub ingress to native RX includes command/STEP admission,
model CPU/output and IPC dispatch, as well as simulated queue/wireless effects.

The relevant STEP2.64 runs mono517272.964152698→517273.011042361:
46.889663wall/46.449632threadCPUms. It includes all events in that batch,
not just health2815. Actual health output is read before the whole STEP ends.
Total stdout output inside that step is.635053wall/.235492CPUms,14 messages,
164634B; this does not support attributing most of the step to stdout blocking.
Remaining CPU includes model/ledger/trace work; it is not measured pure RF cost.
Earlier STEP2.53/2.54 also use28.171/47.059wallms with nearly matching CPU.

New masks26 are actual ingress IDs2816/2817/2818 at.945231999/.945977342/
.948806205. Mask1 completes with actual RX2.636161288sim and Hub wall.997427826,
then late actual R accept above. Mask2/3 lack complete R receipt before the fault
and final horizon2.64. Fault HOLD truncates further simulated progress: absence
of those completions is censored evidence, not sufficient proof of wireless loss
or proof that they would certainly arrive after resuming.

## DDS and Gateway profile exclusion

968 TF takes strictly match actual source realtime publication brackets, with
zero unmatched/duplicate identities. All9 writers have matched-reader count1
from their first publication. map→odom source-return→take maximum is
49.737010/46.655913/50.833009ms for23/43/63. Neither old1s TF delay nor old137ms
health-capture delay is reproduced; those old failures remain unresolved.

In this first-fault window no individual wait/handler/pump/journal >=10ms span
is recorded. Inclusive outer polls are approximately128–144wallms with nearly
matching caller-thread CPU, but internally alternate C/R handlers and pump.
Those parent durations are not stand-alone health blackouts and cannot be added
to child spans. No evidence here supports changing QoS, prioritizing health,
clearing SHM, using last-value clock as completion, or relaxing original gates.

The supported conclusion is a real **wall-budget failure under the complete
coupled load**: slower source cadence leaves little remainder and measured
adapter/STEP/native service variation consumes it. A single correctness bug or
single RF loss point has not been established. No repair or additional run is
authorized or performed by this analysis; no Gazebo qualification follows.

## Ten-step critical path, final bounded read

[ten-step-accounting.json](ten-step-accounting.json) follows complete native
Runs2.49 through2.58, from start2.49 to start2.59:265.006733wallms for.1sim,
with sub-ms boundary phase difference from the Peer snapshot interval above.
Run wall143.864212/CPU142.626065ms; between Runs121.142521ms. The latter is
exactly Run-end→Gateway ACK31.212921 + ACK→next queue77.480331 + queue→next
native-start12.449269ms. Model CPU alone is not an established absolute ceiling.

[control-clock-critical-path.json](control-clock-critical-path.json) independently
splits that causal route: Run-end→coordinator ACK11.863480ms, ACK→physical grant
1.145537ms, grant→coordinator observed actual clock9.829120ms, that same observed
clock→Gateway R clock callback82.989233ms, callback→next STEP queue2.865882ms.
The independent clock callback proves the sample already existed; it is not an
invented DDS source timestamp. Remaining queue→native cost is as above.
Token lateness714.5–797.0ms proves the nominal20wallms pacer was not binding;
changing the target RTF cannot remove these already-permitted waits.

The mock's physical E is actual/clock+5ms. Under the literal current20ms
physical-end credit formula each ACK permits one10ms token, leaving5ms unused;
the following token exceeds that credit by5ms. This conservative phase behavior
contributes to the ACK→new-clock→next-STEP serial route, but obeys current code
and registered contract. Adding5ms or re-anchoring to physical E would change
that literal credit boundary and cannot be labelled a proven semantics-neutral
bug fix. There is no evidence here for a silent pacing/credit/QoS/priority change,
IPC replacement, arbitrary startup delay or generic multi-thread rewrite.
Current implementation capacity is insufficient in this observed busy window;
irreducible model capacity and a specific correctness defect remain different,
unproven claims. Any next candidate must explicitly preserve/review the actual
credit meaning and test the measured clock-selection path rather than RF delay.

Subsequent read-only actual-contract check: old real A10/B01 have G=E at every
recorded physical ACK (14322/10951 cases), unlike this deliberately5ms-phase
MOCK. See [actual phase evidence](../real-gazebo-phase-01.md). The busy-window
capacity observation above is specific to that stress fixture; it cannot be
promoted to an actual Gazebo capacity limit. This qualification does not erase
the stress failure or establish that a corrected phase0 fixture would pass.

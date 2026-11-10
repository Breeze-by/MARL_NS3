# DDS audit01: calibrated observations, old1s delay not reproduced

Original sealed case: `net01d/runs/full-load-dds-audit-01`, fixed c4e95cf.
Producer-side analysis, not independent acceptance or a behavior repair.
No production edit, node, replay, ledger/PCAP scan or added experiment here.
`analyze_dds_audit.py` read the31.8MB Gateway once and three source records;
the separately requested normal-health analysis made one additional targeted
Gateway read. Component copies allow other reviewers to avoid loading it again.

## Unique source identity and time bases

All6930 nonempty TF takes have exactly the actual metadata keys
`source_timestamp` and `received_timestamp`, no writerGID/sequence. Every source
timestamp is nonzero and lies **strictly inside** one actual source publisher's
realtime-before/after bracket for that flow/writer-kind. All6930 join uniquely,
zero unmatched, duplicate identities or source publications unobserved. Repeated
TF header times are not treated as unique IDs. Publication ordinals are source
diagnostics only; no transport payload was changed.

This establishes source_timestamp's system-time interpretation in this actual
sample set. Received timestamps are also nonzero, numerically in that same epoch,
after source time and before take-start realtime for every joined sample. This
is consistency evidence, **not independent proof of earliest DDS arrival or
reader-ready time**. System-time differences are kept separate from monotonic
elapsed time; thread CPU is only compared in the same Gateway thread.

All nine source writers report one matched reader from publication ordinal1
through the last. This is endpoint matching, not a receipt ACK. The old failed
case has no matched-count or metadata evidence, so its1s cause stays unresolved.

| Writer | n23/43/63 | First source-return→take ms23/43/63 |
| --- | --- | --- |
| map→odom |1634 /1634 /1682|2.567 /9.615 /1.206|
| odom→base |490 /490 /504|4.568 /4.102 /3.026|
| both wheels |164 /164 /168|10.303 /7.714 /20.804|

## Remaining tails: before take, not1s

| map→odom source-return→take ms | median | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: |
| flow23 |8.613|37.098|70.076|103.151|
| flow43 |11.334|47.848|79.854|114.898|
| flow63 |10.036|38.632|73.732|108.445|

For those respective worst samples, sourceTS→RMW receivedTS is.075714/.062291/
.106216ms, while receivedTS→take-start realtime is103.133083/114.893095/
108.417069ms. The long measured remainder therefore follows the recorded RMW
receipt timestamp in this run. It does not distinguish an internal DDS-ready
delay from executor selection, cached waitsets or other caller-thread work.
The old approximately1s startup delay was **not reproduced**, not corrected.

## Observation cost and normal interval

[observation-cost.json](observation-cost.json) derives only from saved source
rows. Emit-entry mono→pre-publish realtime's following mono sample includes
matched-count query and early bookkeeping, maximum184.028us over all samples,
per-writer p95 at most31.663us. First samples range7.923–74.399us. None hides a
one-second blocking query. Matched-change recording occurs after this measured
endpoint; these numbers are **not total diagnostic overhead**. New take spans
also contain the original native take/conversion and cannot be called pure
instrumentation cost. Changed scheduling/interleaving remains possible.

[normal-health.json](normal-health.json) covers actual common t0→Done
32.000097981wall: each flow160 intakes, all armed and no-fault; max receipt
interval232.919416/232.935786/229.730895ms, none above300ms. At recorded intake
Rsim, incoming odom age<=.08sim/correction<=.07sim, previous-held state before
update odom<=.18/correction<=.17. These are **sampled maxima**, not all guard-timer
continuous maxima. Peer160 normal snapshots are ready; max source odom receipt
age86.590744ms. Action/negative/89/95 verdict belongs to the independent reviewer;
[component-subset.json](component-subset.json) preserves their small original fields.

## One bounded next direction, no extra run requested

Keep the same passive fields in root's separately chosen single full-load B
qualification. If a long wait recurs, source bracket/matched state plus the split
sourceTS→receivedTS versus receivedTS→take directly tests late matching/late RMW
receipt against the remaining reader/executor path. Do not add another large
test, delay startup by an arbitrary second, clear SHM, change QoS/priority or
declare the observation itself a fix. If it does not recur, retain both old
failures and explicitly leave their unique underlying cause unresolved.

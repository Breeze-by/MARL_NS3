# Cleanup regression01: supplied stop precedes expiry; no old1s TF recurrence

Read-only saved-case analysis; no source edit, rerun, node or native-ledger read.
This task does not independently accept Action cleanup. Original regression
`passed=false`, first failure and all raw evidence remain unchanged.

The initial interpretation "natural source failure before the planned trigger"
is contradicted by the original phase records:

- ACTIVE_GOALS_READY mono519024.894811490: all3 accepted Goals, actual pending
  GetResult and confirmation state recorded; guards armed and fault-free.
- Host trigger519024.898117504 writes SUPPLY_STOP. The three source records
  actually stop observations at.899681255/.899658570/.898892691, Rsim1.20.
  Their local services remain active as designed.
- Peer seq12/gen1.2 is still ready. Seq13/gen1.3 is ready=false, sole failure
  tb3 stale_odom: source odom receipt age.223887737wall exceeds original.2wall.
  Its odom stamp age.13sim and correction age.03sim do not breach.4/.55sim.
- Each R receives that actual seq13 and changes faultNone to
  health_original_sources_stale at Rsim1.3: mono519025.099628418/.101065356/
  .108844753. Host FIRST_FAILURE.152116663 is subsequent detection.

Thus this is actual expiry after the deliberate observation stop, not a new
pre-trigger TF/source failure and not evidence the old DDS one-second gap recurred.
[phase-source-check.json](phase-source-check.json) retains exact old records.

All174 observed TF takes uniquely match their source realtime publish brackets;
all9 writers report one matched reader from first publication. Source→take
maximum is76.741264ms, with no100ms/1s sample; metadata source/received values
retain the same calibrated/limited semantics as earlier audits. Source1/2 have
26 map-TF publications each, source3 has72 because actual source activation
times differ; that is not loss or a late-take inference. [summary.json](summary.json)
keeps source/capture coverage and original timestamps.

No transport/initialization repair follows from this case. Cleanup marker's
strict record-completion issue is separately reviewed by root/producer/metric;
the source-freshness result here cannot turn that regression result into success.

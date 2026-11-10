# P1 health timing audit — offline history complete, no new live run

Owned scope: this directory only. Core integration belongs to the main producer
after root review. No production changes, Git operation, ROS init, node, native
model, Gazebo, training, parameter change or new run has been performed here.

## Historical boundary already established

Case: `net-01/workspace/runs/net01-b-corridor-6201-01` in the original worktree.
Sources: `net01/followup04/B01_EVIDENCE_SUMMARY.json:first_heartbeat`, original
Peer/Gateway records, and `net01/followup05/HEALTH_PATH_REVIEW.md`.

| Observed boundary for seq1033 | same-host monotonic seconds |
| --- | ---: |
| Peer composite health publication returns | 458208.186454543 |
| C flow31 Python capture callback begins | 458208.324384468 |
| tb1 guardian latches stale heartbeat | 458208.327175423 |
| Hub receives the new health frame | 458208.329918123 |
| R destination complete-message handling | 458208.330829963 |

Composite return→C capture = **137.929925ms**. C capture→R complete handling =
**6.445495ms**, including serialization, IPC, network calculation/delivery and
destination dispatch. The latter is not isolated radio delay. Old receipt age
at the first guard was at least **332.878802ms**, beyond the unchanged 300ms.
The late packet cannot retrospectively clear that interval.

Frozen Peer `publish_masks` (workspace/gz01/peer_keepout.py:217–268) creates state,
publishes three masks, then calls `self.health.publish`. Its before/after timing
surrounds `ObservedPublisher.publish`, **not just the underlying DDS publisher**.
`bound_peer.py:28–34,51–70,105–108` publishes raw health first, then serializes,
binds and publishes three mask envelopes. Therefore 137.929925ms is a lower bound
from raw-publisher-return to C capture. It is not a pure DDS measurement.
The existing entry/snapshot mono pair brackets source state construction;
`generated_sim` is a ROS simulation timestamp, not an exact wall generation stamp.

TopicWire capture (`topic_wire.py:80–96`) begins after typed DDS take/conversion,
before serialize. Its old row does not time serialization or send completion.
Gateway health receipt (`gateway.py:242–263`) performs decode and guardian receipt
before TopicWire deserializes and republishes. Thus public publish time is not
the guardian's actual receipt timestamp.

Historical B has no dispatch CPU profile. Its global C/R maxima and poll gaps
are inclusive aggregates without this gap's timestamp; no attribution follows.
An absence of Gateway rows does not prove OS descheduling. The independently
observed physical clock also stopped at103.33 under genuine Native-credit hold:
physical ACK103.33 at458208.160635003, latest Native ACK103.30; Native ACK103.31
only at458208.332623457, after the guard. The missing Native-command/Run/ACK
subinterval remains **UNRESOLVED** until actually matched to its existing trace.

## Reuse existing observations before adding anything

- `gateway.py:40–93,334–434,463–467`: opt-in `--dispatch-profile` already records
  wait-ready / original handler / pump / hub / journal mono+thread-CPU aggregates
  and every span >=10ms in RAM. Enable it unchanged in any separately admitted
  causal fixture. Parent/child inclusive spans must not be added together.
- C/R contexts and executors share the caller thread. Cached ready sets and
  fixed quantum4 preserve original order and entity-count caps, not wall bounds.
  One long handler, DDS typed take, waitset construction or pump can defer health.
  Installed Humble `_take_subscription` drops MessageInfo (`executors.py:398–402`);
  a Python callback cannot reconstruct an earlier DDS arrival timestamp.
- `hub_client.py:25–33,53–92`: existing byte offsets establish queued→kernel-flush
  for clock frames only. Poll drains all complete buffered frames; nonblocking
  socket access is not a CPU/wall bound on that whole operation.
- `tools/packet_hub.py:180–214`: existing ingress provides native message ID;
  the endpoint awaits actual STEP completion before reading the next owner frame.
  This is a concrete possible queue stage, not proof of its contribution to P1.
- `native/payload_transport.cc:275–324`: native is the stdin command-loop process,
  calls `Simulator::Run()` synchronously, records STEP begin/end mono+thread CPU,
  then ledger barrier and actual STEP output. There is no independent native
  command-processing worker. Existing ledger ingress/TX/RX/deliver carries native
  ID and ns3+mono. Original ledger must not be rescanned concurrently with others.

## Minimal additional passive fields for main-producer integration

Opt-in RAM rows only; persist after the original owned processing ends. No extra
timers, threads, subscription, business payload fields, QoS or callback reordering.
Reuse the current profile for general work; do not copy full message bodies into
a second log or reserialize grids for diagnostics.

Every new row: case/session, PID and caller-thread identity (record once), stage,
flow/robot and health sequence where actually decoded, mono_ns + thread_cpu_ns,
available ROS_sim_ns and actual last Native-ACK ns (explicitly last-observed).
The namespace identifies its clock base; unavailable stamps are null, never zero
used as a fabricated generation stamp. Record exception/return in finally while
preserving the original return/exception and original call order.

| Stage | Small observation to add |
| --- | --- |
| Peer source | Reuse entry/snapshot state-construction bracket and generated_sim. Health-only external publisher records raw publish before/after, then binding after. Distinguish these from existing composite wrapper return. |
| C health callback | Before extra diagnostic parsing: entry mono/CPU; original serialize before/after; original send return; callback finally. Parse the existing String once for sequence and retain that sequence only in diagnostic RAM. |
| Gateway→Hub queue | Reuse actual ordered frame byte offsets for health flows31/51/71 as for clock. Queue marker/flush marker share an offset identity; do not change frame/CDR or make flush an ACK. |
| Hub ingress→native | Associate flow+per-flow ordinal/frame identity with assigned native_message_id; original stdin write before/after and drain return. No additional transport field. Verify count/order; any ambiguous join stays unresolved. |
| Native path | Reuse native_message_id ingress/TX/all-fragment RX/message_deliver and STEP/Run/barrier trace. Network elapsed ns3 time and host wall execution time are separate statistics. |
| Hub→Gateway | Reuse actual native ID and hub receive. Record health owner.write/drain and Gateway complete-message entry; retain incoming-frame order. |
| R decode/guardian | Record decode before/after; original receive_health before/after with old sequence/receipt, new sequence, armed/fault, exact newly stored receipt. Preserve tick-before-update semantics. Do not call reason()/tick() extra to collect a field. |
| R public consumer | Existing TopicWire publish before/after is publisher evidence only. Guardian is the safety consumer measured above. Observer subscription callback entry, if needed, must be passively wrapped externally; publish return never proves that consumer ran. |

## How evidence distinguishes causes

Match **the same sequence** across source→C→each R. Use source sequence plus exact
captured CDR identity and flow; native message ID connects actual network events.
Do not nearest-time match an absent sequence or infer a missing packet's arrival.
An exact-hash mismatch across independent DDS serializations is not itself field
corruption (padding is known); unmatched historical pairs stay unresolved.

For each matched span report n/coverage, min, median, nearest-rank p95/p99, max,
and fractions >10/100/300ms as descriptive thresholds, not replacement gates.
Report missing/ambiguous joins and censored source samples separately. Old source
wrapper→C can be negative when C executes before binding returns: retain it and
label lower-bound semantics, never claim negative physical transport latency.
Actual guard receipt interval and original .3wall decision remain the safety test.
Compare CPU deltas only within the same PID/thread; cross-process mono is valid
only for this same-host capture. ROS/Gazebo sim, ns3 sim, realtime and mono must
not be subtracted across bases. Clock metadata's source timestamp calibration
does not calibrate a future String-health witness; received_timestamp is not
independently established as first middleware arrival.

- Overlapping CPU-heavy handler/serialize/pump spans identify work owner, not
  automatically its necessity or causal exclusivity. Nested spans count once.
- Large wall with little same-thread CPU narrows to blocking/descheduling; it
  does not select OS scheduling, disk or a mutex without further evidence.
- Source publish cadence gap means the next sequence was not yet published;
  a timely raw publication but late C callback localizes before C processing.
- Timely C capture/queue but late hub ingress/flush localizes IPC admission;
  timely native ingress with late actual TX/RX distinguishes other stages.
- If these boundaries still cannot separate DDS-ready timing from scheduling,
  propose a separately reviewed **read-only C++ health witness** using original
  depth1 reliable volatile QoS, original sequence+writerGID, source/received DDS
  stamps and mono/realtime brackets. No publisher/republisher. First calibrate
  its nonzero source stamp to actual String publisher realtime brackets; absence
  or witness callback lateness alone is not proof of absence at the Gateway.

## Read-only analysis entry (executed once after root authorization)

`analyze_history.py` reads one saved124.8MB Gateway JSON once, the two small Peer
JSONL files, no native ledger/PCAP/bag, no ROS imports. Explicit B-only autonomy
cohort15.76..103.33; exact existing hash+flow joins, no new SHA computation.
It can describe source-wrapper duration/cadence, source→C lower bounds, matched
C→R destination and R public-publish spans, plus known1032/1033 rows. It cannot
invent missing callback CPU/serialize/queue/guard subspans.

Sole offline entry, <=20wall, output exclusive; actual exit0/6.923442559wall.
See `history-01/{argv.json,stdout.log,stderr.log,process-exit.json}` and
`HISTORICAL_FINDINGS.md`. No repeated Gateway or native scan.

```sh
rtk proxy timeout --signal=TERM --kill-after=2s 20s python3 -B \
  net-01d/workspace/net01d/health/analyze_history.py \
  --case net-01/workspace/runs/net01-b-corridor-6201-01 \
  --out net-01d/workspace/net01d/health/history-01
```

No new no-motion ROS/native fixture budget is requested yet. Its exact source,
four causal groups, message load, hard wall and process ownership must be reviewed
with the main producer's plan first. Root owns the two-repair-round accounting.
No SHM change, new scheduling policy, relaxed300ms gate or prior-result rewrite.

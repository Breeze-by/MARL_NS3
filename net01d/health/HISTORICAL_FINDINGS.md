# P1 historical health boundary — B01, read-only findings

This is producer-side evidence preparation, not independent acceptance. No ROS,
native model, Gazebo, replay, production change or new hash computation occurred.
The original failed run and its safety decision remain unchanged.

## Actual analysis and coverage

`analyze_history.py` ran once under the approved20wall limit: exit0,
6.923442559wall. [Command/output/exit](history-01/) are preserved exclusively.
It read Gateway124,752,433B once and two small Peer JSONLs totaling4,439,709B;
no multi-GB native ledger, PCAP or bag was read. The supplement read only those
small Peer files and the already-extracted result, not Gateway again.

The saved source cohort `generated_sim in [15.76,103.33]` independently contains
876 Peer rows and876 distinct bound-health hashes, one hash per sequence.
Each flow31/51/71 has876 unique source→C→R identity pairs in this saved cohort.
This establishes observed cohort coverage, not an assertion about unrecorded
source messages, other flows, other phases or future loss-free operation.

Statistics in milliseconds; nearest-rank p95/p99, negative values retained.
10/100/300ms exceedance fractions are descriptive, not new safety criteria.

| Span | n | min | median | p95 | p99 | max | >100ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Source composite health-publish call |876|2.320|5.340|5.960|6.196|35.825|0/876|
| Adjacent source wrapper returns |875|123.078|216.640|232.725|241.144|249.841|875/875|
| Wrapper return→C capture, flow31 lower bound |876|-6.429|.187|9.266|11.509|137.930|1/876|
| Same, flow51 |876|-5.321|1.429|9.592|11.844|142.307|1/876|
| Same, flow71 |876|-4.932|4.199|12.641|15.460|142.641|1/876|
| C capture→R complete, flow31 |876|3.170|17.558|32.654|36.930|45.765|0/876|
| Same, flow51 |876|3.345|22.056|41.290|48.850|59.420|0/876|
| Same, flow71 |876|6.014|24.342|47.929|57.548|67.412|0/876|

Full precision and >10/100/300ms proportions, including R public-publish spans,
are in [historical_timeline.json](history-01/historical_timeline.json).
Wrapper-return→C has428/331/197 negative observations because the wrapper still
does binding work after raw DDS publish, while the other process may already
consume. These are **not negative DDS/physical latencies**. Raw publisher-return,
serialization, queue/flush, internal guardian receipt and per-stage CPU remain
unmeasured in this old run; no distribution for them can be supplied honestly.

## First-gap source cadence and old-message age

[Exact saved boundaries and arithmetic](historical-gap-supplement.json):

- seq1032 generated_sim103.2: state construction is bracketed by timer entry
  mono458207.901260004 and snapshot.901363590. Wrapper before.961904402,
  composite after.967462353. tb1 R complete.993844265, public publish before.994153794.
- seq1033 generated_sim103.3: entry458208.121364605, snapshot.121440275;
  wrapper before.181254433, composite after.186454543. C capture.324384468,
  R complete.330829963. Snapshot→wrapper before is59.814158ms of the existing
  preceding mask-computation/publication path, not part of the subsequent137ms.
- The state-construction interval is220.001015–220.180271ms; wrapper-before
  interval219.350031ms and wrapper-after interval218.992190ms.
- Original source timer is.1sim. At nominal.5RTF this is200mswall, leaving only
  approximately100ms of a300ms receipt budget under a constant-path example.
  Actual Native-credit stalls can delay the next sim-timer generation. This is
  separate from waiting after a new message was already generated/published.
- Last valid tb1 health was seq1032. Its exact internal receipt is not stored,
  but source order brackets it within R destination.993844265→public publish
  before.994153794. At the first guard458208.327175423 its age was therefore
 333.021629–333.331158ms. This tightens, rather than contradicts, the older
  broader summary's >=332.878802ms bound.
- At seq1033's composite publish return, only107.389722–107.699251ms remained
  before that old receipt's300ms deadline. The next137.929925ms to C capture
  already used more than this remainder; downstream delivery was another6.445495ms.
- Exact observable-boundary decomposition: tb1 R-complete interval336.985698ms
  = source wrapper-before interval219.350031ms + new path149.575530ms
  − old path31.939863ms. Do not add both path latencies to the source period.
  These are complete-handler boundaries, not invented exact guardian timestamps.

The source interval alone did not exceed300ms; neither does the small new-packet
C→R span prove the old receipt interval was acceptable. Both cadence and path
variation matter. Original .3wall/.2wall/.12sim and generation rules stay frozen.

## Native and control-chain exclusion supplied by root's original-trace read

The following exact values were independently extracted by root and supplied to
this task; they were not obtained by a second scan here. Original paths:
`<B>.network/native/control-step-trace.jsonl`,
`<B>.network/{hub-clock-control,native-control-boundaries}.json`,
`<B>/network-gateway.json['clock_control_trace']['events']`.
All timestamps below are same-host monotonic seconds458208 + the displayed fraction.

| Existing observation | fraction |
| --- | ---: |
| Native STEP103.30 Run begin / end |.139853183 / .144840738|
| Hub actual STEP return receive / response drain |.145017276 / .145168760|
| Gateway receives clock_return103.30 |.149471167|
| Gateway queues observed_clock103.31 / flushes it |.325171377 / .325228536|
| Gateway queues STEP103.31 / flushes it |.325254004 / .328028308|
| Hub receives STEP / writes native stdin / drain returns |.328256039 / .328264808 / .328299090|
| Native STEP103.31 Run begin / end |.328337588 / .332067293|

STEP103.30 Run used4.987555wall/4.984375threadCPUms; STEP103.31 used
3.729705wall/3.726908threadCPUms. Their183.496850ms gap is between Runs.
The137.93ms health gap is not inside `Simulator::Run`, nor waiting on the already
returned103.30 ACK downstream. There is175.700210ms from Gateway receiving the
old actual ACK to queueing its next actual clock observation. This narrows the
candidate owner to Gateway-side readiness/handler/pump/take/scheduling before
the next observation is queued. It does **not** prove an idle native process,
OS freeze, DDS bug, Python GIL cause, or one particular expensive callback.
Later STEP103.32 (.337665175→.380381257) is a different42.716082wall/42.057CPUms
window and must not be moved backward to explain this earlier gap.

## Minimal next implementation, no new experiment implied

Main producer integrates opt-in passive calls, preserving callbacks/order and
original payload/QoS. Reuse existing dispatch-profile and native/control trace;
see [PLAN.md](PLAN.md). [trace.py](trace.py) is the small single-caller RAM helper:
`HealthTrace().stamp(stage, sequence=None, flow=None, **fields)` returns its
appended mutable row; `snapshot()` returns identity+rows. No parser, writer,
thread, timer, serializer, hash or control predicate is introduced by this helper.
No new C++ health witness is needed at this stage. New no-motion loaded execution
still needs root's exact source/budget review. This investigation does not justify
changing clock IPC, safety limits, frozen Peer/SLAM/Nav2/RL, or network parameters.

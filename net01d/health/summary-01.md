# A1 health-profile-01: measured owner boundaries

Source: `net01d/runs/health-profile-01/{gateway/network-gateway.json,peer/health-trace.json,process-exit.json}`.
One read of the14.37MB Gateway JSON; no native ledger/bag/old Gateway rescan.
Full precision, stage aggregates and overlapping spans: [summary-01.json](summary-01.json).
This is producer-side analysis, not independent acceptance.

The six owned roles exited0,21.967807wall, no forced cleanup. This is direct data
delivery with a control-only native process, independent source/Peer/Gateway,
synthetic fixed pose and grid load, unarmed guards. No89/95, real Action goals,
actual Nav2/SLAM/Gazebo or policy workload. Old B's137.93ms wait was **not reproduced**.

All86 observed Peer sequences pair to86 C and86 actual R guardian intakes on each
health flow. Statistics below include this saved whole-role trace, including
startup/teardown; they are not a new autonomous-task cohort. All units are ms.

| Measured span | median | p95 | p99/max |
| --- | ---: | ---: | ---: |
| Peer underlying raw DDS publish, n86 |.138513|.194307|.459352|
| Subsequent binding work, n86 |4.655458|5.301978|6.680646|
| Raw publish return→C callback, flow31 |8.469980|14.596176|16.359936|
| Same, flow51 |9.172219|15.301188|17.078109|
| Same, flow71 |13.018043|19.226229|21.101553|
| Raw return→actual guardian receipt, flow31 |8.932246|15.054855|16.846729|
| Same, flow51 |9.499595|15.614373|17.428840|
| Same, flow71 |13.435831|19.552971|21.486736|

No raw→C sample exceeds100ms. C health serialization max.085929ms; C health
callback max.354102ms across flows. R health decode max2.421935ms (flow31),
guardian call max.121028ms. Unarmed real intake/update is measured; this is not
an armed safety qualification. Publisher-return evidence alone is not intake.

## Executor/pump facts

| Stage | calls (where relevant) | accumulated wall / thread CPU ms | maximum call wall ms |
| --- | ---: | ---: | ---: |
| C wait-ready yielding work |2339|1133.095 /1128.813|2.346440|
| C empty wait query |1707|1416.665 /1384.654|1.895182|
| R wait-ready yielding work |14956|5558.752 /5553.007|2.726124|
| R empty wait query |484|587.007 /576.787|2.540649|
| C largest original handler: bound-mask flow30 |86|108.372 /108.412|2.147403|
| R largest handler: feedback flow246 |1600|148.358 /148.624|2.559521|
| Direct-delivery batch |17593|2284.109 /2283.302|5.824317|
| Hub poll, control only |17658|431.575 /431.833|.257448|
| Journal call, no actual journal file workload |868|89.438 /89.502|.389106|
| Outer poll inclusive |363|17403.877 /17337.251|137.873775|

No wait/handler/direct/hub/journal **individual** span reached10ms. The only
>=10ms recorded categories are outer-poll inclusive and startup transport
progress inclusive (wire installation,45.752624wall/45.696821CPUms). The longest
outer poll was137.873775wall/137.561231CPUms: many short operations accumulated,
not a137ms single callback. The loop continues C/R alternation and pumping
inside a poll, so this outer number is not a health blackout duration.

Worst raw→C case is seq82/flow71: raw return513980.332918862,
C entry513980.354020415, actual guard receipt513980.354405598; delay21.101553ms.
Its enclosing poll was513980.252749856–.384164118
(131.414262wall/129.229278CPUms), with no overlapping >=10ms child span.
That parent overlap does not assign the21ms to one handler or prove OS starvation.

Subtraction wall−threadCPU is only current-thread unaccounted wall, not evidence
of I/O/OS cause. Parent/child totals are inclusive and must not be summed.
This case shows substantial executor ready-query CPU and no rare historical
stall; it does not establish a repair or justify clock/QoS/scheduling changes.
Next full-load source remains separately reviewed and unexecuted.

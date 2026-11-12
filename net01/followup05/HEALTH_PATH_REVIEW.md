# Health publication to central capture: read-only review

Scope: current integration source and existing B01 evidence. No production edits, Git operation, ROS initialization, simulator execution or network changes.
Conclusion: **do not replace clock IPC as the immediate repair for the137.930ms health wait.**
The small SHM trial shows lower read/parse CPU, not that the current health gap is caused by clock IPC.
Existing evidence narrows the boundaries but does not uniquely name DDS, one Python handler, native computation or OS descheduling.

## Actual health path and observation boundaries

Paths below are relative to net-01/workspace unless an explicit rootfs path is shown.

| Stage | Current source | Meaning |
| --- | --- | --- |
| C Peer health production | workspace/gz01/peer_keepout.py:248–268 | Original three masks, then health, then RAM timing/JSON record |
| External publication wrapper | net01/bound_peer.py:28–34,51–70,105–108 | health.publish first calls the real publisher, then binds/publishes the three actual mask envelopes |
| C health subscriptions | net01/topic_wire.py:31–40,71–82 | flows31/51/71 independently subscribe to the same original /peer_keepout_state; depth1 volatile QoS |
| Capture timestamp | net01/topic_wire.py:80–94 | Recorded on Python callback entry, after DDS take/typed conversion, before serialize_message and send |
| Actual transport | net01/gateway.py:188–202; net01/hub_client.py:25–39,53–92 | Complete CDR+RPC identity passes through actual B backend; no health source-cache replacement |
| R health delivery | net01/gateway.py:242–261 | Actual complete received String is passed to the local guardian, then original public-topic publication |

The stored Peer health_publish_after_monotonic wraps ObservedPublisher.publish, including its binding.health work.
It is not a separately instrumented raw DDS publisher-return timestamp. The real health publication is earlier in that same call.
Thus137.930ms from this stored return to C callback remains a real lower bound on raw-health-publication-return to capture, not a pure measured DDS latency.
The three reliable bound-mask publications can also create an associated burst; this is a source-order fact, not proof that the burst caused the wait.

## Concrete B01 evidence

Source: net01/followup04/B01_EVIDENCE_SUMMARY.json:first_heartbeat and original runs/net01-b-corridor-6201-01 artifacts.
All times in this table use same-host monotonic; no system/monotonic subtraction.

| Boundary | monotonic seconds |
| --- | ---: |
| Peer seq1033 composite health publication returns | 458208.186454543 |
| C flow31 callback capture | 458208.324384468 |
| First tb1 guard trip | 458208.327175423 |
| Hub ingress of the new health | 458208.329918123 |
| R actual destination receives the new health | 458208.330829963 |

Publish-return→C capture is137.929925ms; subsequent capture→R destination is6.445495ms.
Old receipt age was at least332.878802ms at the first guard, beyond the original300ms wall bound. This is not evidence of a false alarm.
The source wait precedes actual Wi-Fi admission for this new health; it cannot be assigned wholly to the subsequent radio transit.

One sequential read of the119MB Gateway JSON, no native-ledger scan, establishes:

- No Gateway records occur strictly inside the137.930ms interval; only the endpoint flow31 capture is at its end.
- C captured-array zero-based3215/3216/3217 are old flows31/51/71 at monotonic458207.962770796/.963208896/.970298993.
- C captured3218/3219/3220 are new flows31/51/71 at458208.324384468/.328761535/.329095370.
- R captured55900 (flow43) is458208.142283381; next55901 (flow22) is458208.337228132:194.944751ms between those R capture entries.
- B has no dispatch_cpu_profile. Global max C accumulated service span217.181ms, R405.094ms, outer poll gap520.289ms lack the required first-fault timestamps and include pump work. They are not single-handler durations or attribution of this gap.

The R silence is not independent proof of whole-Gateway OS starvation: the physical source also stopped progressing under actual credit.
Independent clock-R.csv rows10333/10334 observe103.32/103.33sim at458208.144053052/.158679964; no new R clock in the target interval.
The next R witness clock103.34 arrives at458211.283567659, after fault-stop observation was authorized.
Clock-C.csv rows10333/10334 observe103.32/103.33 only at458208.325256202/.336780130.
Coordinator JSON records zero-based41336 has successful physical ACK103.33 at458208.160635003; its latest Native ACK was103.30.
It receives Native ACK103.31 at record41339/458208.332623457, after the first guard. Its credit check therefore legitimately prevents another normal physical token meanwhile.
These observations identify a control-progress wait and a C health delivery wait; they do not identify where the Native command/Run/ACK spent its wall time.

## Gateway scheduling and clock ownership

- gateway.py:116–141 creates two separate ROS contexts/domains and SingleThreadedExecutors, but main:527–530 invokes both through the **same Python caller thread**. There is no Python clock worker to remove from that thread.
- R has its explicit control-clock subscription and ModelStates subscription; both nodes additionally get a TimeSource clock subscription because use_sim_time=True. C receives the R-relayed /clock. DDS middleware has its own internal threads, which this source review does not profile.
- Installed rclpy/time_source.py:62–71,118–123 subscribes BEST_EFFORT depth1 and updates ROSClock in its callback; it does not independently advance the clock on a background Python timer.
- drain_current_ready:51–93 keeps the public executor iterator, resumes productive ready sets, and executes one original handler at a time. _poll:334–383 alternates at most4 C and4 R handlers, preserving per-poll entity-count caps. This is a handler-count bound, not a wall-time bound.
- C empty retry is deferred10ms only after an actual empty probe. It can add adapter delay, but alone is not an explanation for137.930ms. Four R handlers plus their pumps can take more than10ms.
- progress_transport is called after each completed handler and at the outer boundary. A long handler, public waitset construction or hub.poll batch cannot be preempted by that fairness policy.
- hub_client.py:53–92 uses select(timeout0), one up-to1MiB recv and an uncapped loop over all complete buffered frames. Each receive may deserialize/publish a large mask or other message. Nonblocking socket I/O does not make the entire call bounded in CPU/wall time.
- C export_controller_records:305–317 reads/parses until current EOF; one journal timer can perform a variable amount of actual file/JSON work. R readiness timers query real service/graph endpoints (action_wire.py:72–91); they share the same caller with C health handling.

Installed source read directly, not imported: base-01-econ/isolation/rootfs/opt/ros/humble/local/lib/python3.10/dist-packages/rclpy/.
executors.py:398–402 drops MessageInfo and returns only the message. Ordinary Python health callbacks cannot supply a DDS receive timestamp after the fact.
executors.py:547–570 handles ready tasks before the waitset;712–753 visits timers then subscriptions/guards/clients/services, yielding each ready entity from its cached set;755–787 terminates that set at Timeout0 and rebuilds only when the iterator is exhausted.
A newly ready health reader can await the remainder of that cached set, plus the other domain and pump work. One Timeout0 is not proof that all reader queues are empty.
Current task.py:306–330 suspends an await on Future until resume, rather than blindly re-running every unresolved request each spin. Two unknown C RPCs alone do not prove a busy loop or a mutex blocking health.
This records the currently installed implementation, not a newly hashed historical identity of B01's SDK.

## Minimal next diagnostic and contingent repair

1. On the next **separately admitted** combination run, enable existing --dispatch-profile instead of adding a second framework or immediately changing IPC. Its existing >=10ms RAM spans cover public wait-ready, original handler (including DDS take/typed conversion), transport pump, direct delivery and journal call, with mono+threadCPU boundaries and entity labels (gateway.py:40–48,64–92,216–238,298–303,327–331,385–404).
2. Align one actual health source seq/publication interval with these spans. A long handler/pump/wait span overlapping it, and wall versus CPU, discriminates active work from blocking/descheduling. Inclusive parent and child spans must not be summed. No single global max or aggregate is enough.
3. Only if these spans leave DDS-ready timing unresolved, propose one independent C-domain health witness recording actual seq/publisherGID, DDS metadata and mono+system brackets, without republishing. Existing calibrated clock metadata is not automatically a calibration of String health. This is a conditional diagnostic proposal, not a new node authorized here.
4. Apply the smallest fix to the measured owner: bounded journal lines/bytes with exact cursor/order continuation; or bounded complete-frame transport work retaining the remaining ordered bytes; or full original-CDR raw Grid handling if typed conversion is the actual long span. Preserve full payload, QoS, source stamps, per-robot ordering, real delivery and all old safety/ownership gates. Do not add topic priority, drop old messages or rewrite frozen Peer/policy merely to pass.

A clock SHM candidate becomes directly justified only if measured control_clock/clock-frame processing or its head-of-line queue accounts for the limiting span.
It must preserve both actual observed GZ time and the independently completed Native ACK, identities/epochs and stale/exit detection. A last-GZ-clock slot cannot stand in for completed Native work.
The fixed-01 synthetic trial (net01/experiments/paper_methods/clock/RESULT.md) measured about4.41us vs45.33us median read CPU at1kHz. Production here is100Hzsim/approximately50Hzwall with real ROS business, so that result cannot attribute a137.93ms wait or predict its removal.
The same trial visibly retained141ms reader gaps and>351ms source-age under pauses. It supports lower IPC overhead as an optional later engineering change, not wall-clock freshness or original300ms safety qualification.

No new trial, profiler process, ROS node, IPC replacement, safety change or production code patch was made for this review.

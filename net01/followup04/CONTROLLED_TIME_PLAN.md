# Controlled time: one preregistered common .5RTF target

The previous original1000 free-running full-WiFi qualification20 FAIL is retained. No750/.45/other rate scan. Frozen policy/physics1ms/V3/TTL/.12sim lag/.3wall health/.2wall receipt/180sim and420autonomywall remain unchanged. No Gazebo admitted.

A thin WorldPlugin provides /net01/physics_step Trigger. Public World::Step(10) runs in the existing GazeboROS background executor, not update thread; reply only after actual post-physics completion, with before/after ns/iterations. Nonpaused/incomplete motion is failure. It never publishes clock/pose/cmd.

The independent time owner has one physical RPC at a time. Normal credit is next physical end <= fixed offset + actual nativeACK +20ms. Physical simTime is only a credit check, never a fabricated clock/Native target; unchanged Gateway is still the only native clock driver using actual /clock. Before first real anchor, at most2quanta bootstrap. The hub's opt-in Unix control datagrams carry only actual nativeREADY/STEP/closed and monotonic, no business data.

The coordinator's independent best-effort clock subscription is observational and detects rollback in its received sequence. It is not an extra credit prerequisite: the hub already rejects STEP beyond its known actual clock. Therefore an actual native ACK retains real clock provenance when this separate reader misses or receives a sample late. No terminal clock is republished and no physical end-time is injected into the native model.

**Fixed wall plan:** one10ms physical token has nominal earliest start every20mswall (.5RTF). Plan begins at the first permitted actual token; successful RUN permission after HOLD can restart this wall schedule, never fixed native anchor. Native credit and this schedule must both permit a token. Misses/actual start/RTF are recorded; no invented clock, skipped physics or lowered source frequency. Normal STOP_COUPLED retains both constraints. Fault-stop observation after already-latched error plus actual authority exit still uses real10ms steps/20ms schedule; it only bypasses dead native credit, not physical ACK validation.

Reason:20 measured native .60->.79 RunCPU310.963ms (.611 CPU-only RTF ceiling); total native stage423.802ms (.448 observed RTF), an initialburst not steady proof. Target.5 may have capacity with overlap but is unproven; original180/420 requires >=.4286. Plain strict serial would add physical update periods, hence bounded2quantum overlap. .5 aligns A/B wall pacing and reduces WallRate confound; misses still cause actualRTF differences and forbid scientific wireless-advantage claims.

HOLD stops new grants, waits only current physical RPC, then Observer still calls actualGazebo pause. Controlled unpause only releases RUN permission, never free-runs physics. Normal stop retains nativeACK and actual terminal flow until drained; ExpectedShutdown seals only after real physical stop and admittedRPC cleanup. Alreadyfailed transport+authority-exit permits independent physical stop observation, preserving original1.5wall/.5sim/newzero/3pause/UUID gates; wrong physicalACK always hardHOLD. All raw postshutdown alarms remain recorded, never disable safetyguards for zero alarms.

Next admission request will be one0GZ MOCK_PHYSICS fixture: a tiny actualDDS Step service with syntheticclock/10iterationACK, real coordinator+actual nativeWiFi, original16wallsource/30wallbound,200x200costmaps, unchanged perwall TF/odom/FB and Peer10Hzsim, no Policy/Goal/ODE. It is only a no-deadlock/RTF/health feasibility upperbound; actual physics remains unverified. Any source/clock/health failure or measuredRTF<.4286 stops without Gazebo or scanning. Flow89 mergedmap/95 journal remain ungenerated and disclosed.

## Exact qualification21 entry, pending independent admission

```
rtk proxy python3 -B net-01/workspace/net01/followup04/check_controlled_wifi.py --name continuous-dds-21-controlled-wifi --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload
```

Reserved domains are C91/R92, with no current owned NET actors. Coordinator binds its admin ACK datagram socket before actual native startup; hub emits only actual READY/STEP/closed. The mock service starts at synthetic5ms, advances exactly10 integer1ms iterations per request, emits clock at100Hz sim thresholds (10ms sample deliberately precedes15ms token end), and responds with actual mock counters. It never publishes a terminal clock to unblock control. Source subscribes to that clock instead of publishing another source; TF50/30/20Hz perrobot, odom30Hz, feedback100Hz, exactzero20Hz, costmap200x200 every.5wall and map250x220 every5wall remain original wall rates. This is conservative offered-rate load, not a claim that real Nav2 WallRate/sim rate is unchanged.

One shared30wall deadline includes startup and teardown. Six seconds are reserved after source completion deadline for cleanup; the actual source still runs16wall once existing real link qualification succeeds within its original2wall limit. Normal fixture teardown first HOLDs physics while Step service remains alive, verifies inflight completion/expected seal, then stops source/peer/Gateway/mock and keeps the coordinator ACK socket alive through actual Gateway END/native exit. Separate final coordinator-stop is resource control only; forced owned SIGKILL is recorded FAIL, never normal shutdown. No new retry or deadline extension.

Outputs are separate raw source/Peer/Gateway/native/controller/mock records and process exits. Acceptance requires real native whole-body delivery and bound masks/health/source ages, original gate/lag limits with no fault, nondeadlock, actual synthetic sim advance/wall >=180/420, original receipts and END/cleanup. Process0 alone is not PASS. Source offer counts/intervals and controller actual starts/misses/physical/native horizon are measured, not inferred from requested rates. This cannot prove physical completion, actual ROS/Gazebo clock, stop safety or180sim runtime memory bounds. Any failed21 is retained and stops this candidate; no alternate.45/.75 rate.

## Startup-order repair after retained21 FAIL; proposed22

21 ended6.716wall before business qualification: two initial mock clock publications10/20ms occurred before Gateway construction completed (lastclock to processingstart364.775ms); no Gateway anchor/nativeSTEP. It is not a full-load result. The coordinator now requires actual matching-session Gateway state confirming its clock reader exists and its R executor timer is running, plus real `r.count_publishers('/clock')>0` discovery, before either of the original maximum2 bootstrap tokens. Existing50ms state timer carries these facts; no new timer, sleep, token allowance or clock replay. Actual publisher discovery is not declared a delivery ACK; missing clock/dependency still fails within the original deadline. After an actual anchor, normal credit remains real nativeACK+20ms; approved failed-stop observation after authority exit is not blocked by initialization readiness.

22 is an independently named single-use attempt with exactly the same16wallsource/30wallhard bound, frequencies, quantum, fixed wall schedule, V3/native and gates as21. No retries are authorized by this document. Actual admission remains with root:

```
rtk proxy python3 -B net-01/workspace/net01/followup04/check_controlled_wifi.py --name continuous-dds-22-controlled-wifi --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload
```

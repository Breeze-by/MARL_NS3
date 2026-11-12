# Gateway exit fixture — inert, source only

Runtime source: `aae271f49a8d041285b9a903b3f58d9546985574`. `ADMISSION.json.execution_authorized=false`; no execution performed. Production source locked.

`check.py` extracts actual Gateway `close/_close/persist/poststop_phase` and actual `gateway_closed_proof/end_gateway` from pinned local source; it does not import ROS or duplicate lifecycle rules. Two fake executors/nodes/contexts and a fake Hub replace resources; observer stop/seal is an explicit mock precondition. These checks prove lifecycle/exit handling only, never ROS/Nav2/physical stopping. No bag, real network, ns3, model, weights or heavy logs are opened.

Four serial child processes use real, unscaled default bounds: (1) actual closure then22wall injected wait then actual persist and exit0 (~22s), (2) Hub END blocks inside actual _close/no marker → original TERM20/KILL25 (~25s), (3) actual persist blocks in passive-capture hook after valid closure → TERM50/KILL55 (~55s), (4) actual close/persist saved then child fails to exit → same kill/negative process outcome (~55s). Each has one absolute65wall fixture-parent cap; actual supervision total remains60 including TERM/KILL. Expected suite ~160s; the entire single suite has a separate200wall hard cap (and2s forced escalation). Child groups are owned and reaped, first failure stops the suite and preserves artifacts; no auto retry.

Short checks use actual host `runner_command` assignment for controlled120 `host_deadline=None` (old1000 semantics/no added CLI), controlled180 and noncontrolled. Actual marker reader rejects missing/stale PID/session/case/monotonic proof. Actual supervisor is separately exercised with injected monotonic time/signals for repeated-call no renewal and short parent bounds; these FSM checks are not real wall-bound evidence.

Prepared command, **not yet authorized** (cwd repository):

```
rtk proxy timeout --signal=TERM --kill-after=2s 200s python3 -B net01d/followup04/gateway-exit/check.py --directory net01d/followup04/gateway-exit/run-01
```

Root must pin fixture/review and activate admission first. Source snapshots, argv, stages, real signal/exit timing and owned disappearance are retained in the unique directory. Synthetic waits do not measure JSON/GC speed or identify the exact historical post-save cause. Original B remains FAIL; no automatic Gazebo run follows.

The22wall branch is only a controlled delay plus a small actual persist; it is not a351MB serialization stress or ROS capacity measurement.

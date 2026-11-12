# ZeroRobot Gateway exit fixture — actual single suite

Source `aae271f49a8d041285b9a903b3f58d9546985574`, activation `4d8028c`; exact admitted200wall command ran once, exit0. Four cases completed; no retry/source modification. All parent/registered child PIDs are gone.

| Actual branch | Process exit | Case wall | Measured shutdown sequence | Outcome |
|---|---:|---:|---|---|
| Actual closure → injected22s delay → actual persist | 0 | 22.205794s | SIGINT → exit0 at22.067635s | Closure proof allowed finite grace; saved and normal exit |
| Hub END stalls inside actual _close | −9 | 25.159841s | TERM20.000499s, KILL25.000182s, exit25.020457s | No closure marker, no extension |
| Actual persist stalls in passive capture hook | −9 | 55.158119s | TERM50.000201s, KILL55.000178s, exit55.020453s | Closure marker allowed grace; no saved, failed process |
| Actual close/persist saved, then child never exits | −9 | 55.167740s | TERM50.000610s, KILL55.000154s, exit55.020593s | Saved did not bypass real process-exit requirement |

Actual timing uses production60s total/50s grace/5s TERM/5s KILL observation, clipped by65s fixture parent; complete suite outer bound200s. Summed case wall157.691494s. No phase received a fresh60s budget.

Short checks passed using actual source: three host command branches including controlled120/None; missing/stale PID/session/case/mono marker rejection; injected-clock supervisor reentry/no renewal and short parent bounds. These short FSM checks are not real wall-bound measurements.

The child calls actual selected Gateway close/_close/persist and phase methods with explicit fake resources. No ROS, Nav2, robot, ns3 or Gazebo ran. The22s delay and tiny actual persistence are lifecycle fault injection, not351MB stress or capacity evidence. Three expected negative processes genuinely exited−9. This suite does not flip original B network-integrity FAIL or identify its exact post-save finalizer cause.

Original `result.json`, each case `supervisor.json` and `network-gateway-close-phases.jsonl`, source-at-run snapshots, actual argv/PID/startticks in `execution.json`, and selected `small-result.json` are retained. No original run evidence was altered.

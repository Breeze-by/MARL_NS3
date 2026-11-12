# Controller exit reporting — source only

Confirmed original A0 evidence: the controller actually exited1 after the budget SIGINT, while old host/runner/Gateway/Hub/network records remained0/true. The original controller traceback, raw host0/networktrue and failed episode are immutable; retrospective `analysis/gz-simhealth-a0-01` labels the controller exit failure explicitly. Exact exception onset and subscription/message type remain unresolved. This reporting fix does not handle, suppress or reinterpret that exception.

Only two external production files change:

- `net01/run_network_case.py`: in the existing post-stop `persist_observer_records`, save `network-controller-exit.json` with whether the actual controller was started, its PID and actual `Popen.poll()` returncode, session/case, and the observation monotonic timestamp. The timestamp is evidence observation, not an invented exact exit instant. A naturally pre-exited controller is captured too; a not-created or still-running controller has null returncode. No stop order, signal, wait, physics seal or frozen behavior changes.
- `net01/host_run.py`: after existing owned cleanup, load that marker into the host exit record and network integrity record. Network integrity additionally requires `started is True` and actual `returncode==0`, so command exit becomes1 for a nonzero/unknown/not-started/missing controller record. Existing save/Gateway/Hub/control/A0 registry gates still apply. Old successful A1/B controller0 cases satisfy the same predicate; their historical artifacts are not rewritten or rerun.

No other production file, frozen file, exception handler, stop12, safety/source/radio/Policy/budget was changed. Root pinned the reviewed two-file source at `197a21aa86b45fc67be41f9b6cd5ec811cc29125`. After independent fixture review and explicit activation47a2b53/START, the one reporting fixture below actually passed all five cases, exit0/0.613227wall s. [Actual result](evidence/controller-exit-reporting-01/RESULT.md) and adjacent original JSON/launch/exit/stdout/stderr are retained; no model was executed.

## Minimal zero-model verification — original plan, now executed once

Reuse the existing AST-isolation approach from `check_contract.py`, with standard-library temporary directories and real short-lived Python child processes only. Extract the actual external persistence method and actual host post-cleanup integrity/return block from current source; stub unrelated old parent persistence/ROS calls. Do not duplicate the new predicate in a separate implementation. Preserve each original output and compare its actual marker/host record/network record and final return value.

One bounded invocation, no ROS Node, native model, Gazebo, Policy, bag or old evidence write:

| Case | Expected actual reporting |
|---|---|
| Real Python controller exits0; all other existing gates clean | Exact PID/session/case and returncode0 retained; network integrity true and return0. Covers unchanged normal A1/B semantics. |
| Real Python controller exits1; all other existing gates clean | Exact returncode1 retained; host/network report1/false. Explicit regression for A0's swallowed nonzero exit. No exception catch or fake0. |
| Controller never created | Null returncode/startedfalse retained; integrity false/return1. |
| Controller remains alive (fixture terminates its own child afterward) | Null returncode/startedtrue retained; integrity false/return1, no hidden wait/signal/extra deadline added by reporting. |
| Missing controller marker | Host retains `missing controller exit evidence`; integrity false/return1, without constructing a fake controller result. |

The entry is `check_controller_exit_reporting.py` with `CONTROLLER_EXIT_REPORTING_ADMISSION.json`; Root activated its previously inert flag for this sole invocation. One10wall outer timeout, real short-lived Python children, actual owned alive child terminated/waited in finally. Exact argv is recorded in the admission and launch record; output is the exclusive `evidence/controller-exit-reporting-01` directory. The actual host block was exercised with its original A0 and controlled-sidecar gates clean, not a copied integrity predicate. Only the new actual persistence write statement was extracted; unrelated ROS/frozen persistence was not imported.

This verifies reporting only. It cannot prove the underlying rclpy defect fixed, physical safety, A0 Gazebo qualification or a new successful episode. Root/independent fixture review preceded test authorization; no model replay is proposed by this plan. A0 remains failed and C needs a separate Root admission/START.

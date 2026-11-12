# Post-stop lifecycle fixture independent review

**Limited acceptance; supports Root separately admitting one same-condition180sim B02 regression.** It does not pre-accept B02, authorize an automatic retry or revise original B1's−9/network FAIL.

Read actual `check.py`, `ADMISSION.json`, `execution.json`, `result.json` and all four small supervisor/phase streams. Source is `aae271f49a8d041285b9a903b3f58d9546985574`, admission activation `4d8028c`. No tests, models or large scans were performed by this reviewer.

| Real child | Wall seconds including launch | Actual exit | Observed behavior |
| --- | ---: | ---: | --- |
| closed_slow_persist_exit0 | 22.205794139 | 0 | Same-PID/session/case closure proof after SIGINT; extension granted; actual persistence/return complete |
| unclosed | 25.159841302 | −9 | Only close_begin; no proof/save/extension; TERM≈20s/KILL≈25s |
| persist_stall | 55.158118619 | −9 | Closure proof, persist_begin only; TERM≈50s/KILL≈55s |
| saved_exit_stall | 55.167740128 | −9 | Closure proof and saved/persist_end/close_return; still TERM≈50s/KILL≈55s |

All four child PIDs are observed gone. Supervisor records retain one begin+60s total and50s grace, with5s TERM/5s KILL observation reserved inside it; marker arrival does not restart the deadline. Saved does not substitute for actual exit0. The actual unclosed branch verifies new-profile no-proof escalation; old-profile delegation remains source-reviewed rather than an additional real legacy test.

The separate short checks cover actual host command construction including controlled120/None, missing/wrong/stale proof, repeat-call nonrenewal and a shorter parent deadline. They are AST/extracted-method checks with injected clocks/signals, not real wall timing. Four subprocess branches instead use the unscaled production60/20/5/5 numbers, each65wall outer bound, within the declared200wall suite.

Hub/executors/nodes/contexts and safe-stop/seal prerequisites are explicit mocks. Actual close/_close/persist and supervisor functions are extracted unchanged from source. The22s pause is injected before small persistence; it is not351MB throughput, realROS resource closure, physical stopping or historical GC/destructor attribution. No native/RF/Guard/NN improvement is established.

One separately admitted B02 may now test actual Gateway exit0 and overall process/network integrity with original runtime behavior,180sim budget, stop12, shared outer/cleanup/host bounds and first-failure preservation. Actual stop, proof and exit status must be evaluated in that run. No future PASS is signed here.

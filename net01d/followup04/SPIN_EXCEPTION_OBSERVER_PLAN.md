# Spin exception observation — SOURCE ONLY

Root confirmed this scope after the second domain97 DDS diagnostic remained INCONCLUSIVE. The reviewed three-file source is pinned at `bd663824d77983cb2b2721e90241ef97bf06461f`. After explicit activationc617ba5/START, the sole5s pure-Python fixture actually passed, exit0/0.637519wall s; [actual result](evidence/spin-exception-observer-01/RESULT.md) retains the limited scope. No third synthetic ROS replay/model/dependency installation/Git mutation was performed. The old C READY is not modified. New source must be separately bound in a traced READY before any C START.

Two existing bootstrap files and one narrow parent-event observation change. `net01/controller_bootstrap.py` defines the shared `observed_spin` wrapper; `a0_controller_bootstrap.py` imports it alongside its existing journal helper. Each bootstrap saves the original `frozen.rclpy.spin`, temporarily installs the wrapper around its existing `frozen.main()` call, and restores the original spin in its existing finally. `NetworkObserver.event` in `net01/run_network_case.py` adds `controller_signal_event_monotonic_ns` only to an existing `process_signal` event whose process is `exploration`, then calls the original super event unchanged. Frozen files, Python/ROS signal behavior, return values, original exception handlers, policy/Goal/cancel/clock/stop paths and reportgate197a are untouched.

Normal wrapper behavior is one original call and return, with no log, polling, timer, handler, thread or cancellation. On **BaseException**, the first diagnostic operation captures `time.monotonic_ns()`. It records PID/session, exception type/repr, cause/context repr and complete chained traceback in the original controller directory's exclusive `controller-spin-exception.json`. Traversal selects only actual traceback frames named `_take_subscription`, recording filename/line and public `sub.topic_name`, `sub.msg_type` class module/qualname, `sub.raw`. There is no new subscription/take, ROS message/CDR serialization or raw message content, and no saved frame/subscription reference. Per-field read failures become metadata error type names; whole diagnostic/write failures become only a bootstrap-state observation type name. The wrapper then uses **bare raise**, preserving the original exception. Existing frozen main owns all handling/close_controller cleanup.

KeyboardInterrupt is also an observed raw spin exception, not a fault verdict. Its original frozen catch remains authoritative; the existence of this file must never by itself mark a run failed. Timestamp means wrapper observation time, not invented exact handler-error creation time. Metadata can remain unavailable, and a partial/failed write is never claimed as a complete capture. This cannot establish the historical A0 message type or exception cause retroactively.

The parent signal marker shares CLOCK_MONOTONIC with the child exception observation. It is sampled at the existing event call **before** the unchanged helper's os.killpg, so it is a pre-send lower bound, not exact signal completion/receipt. Only that controller process-signal event gains a field; no new signal or hot-path event stream is added. A future same-clock ordering still cannot by itself prove unique SIGINT causality or the exception's exact creation time.

## Minimal zero-model regression — executed once after review

Use the actual helper directly; its module-level imports are standard library only and frozen HQ is imported only inside main, which is not called. Dummy public subscription attributes only; no import or execution of rclpy, HQ, NN, native or Gazebo. Do not duplicate the helper. Original-spin restoration in both existing finally blocks is checked by source review, without additional bootstrap fixtures.

- Normal original callable returns a sentinel: wrapper preserves object identity/args and creates no observation file/state event.
- Original `_take_subscription(sub)` raises a sentinel RuntimeError with known cause/context and valid public fields: catch the **same object** with the same cause/context, retain the original frame/full traceback and exact topic/type/raw metadata. The wrapper's terminal raise AST must have no exception expression.
- A public-field getter fails: preserve the original error, full traceback and other readable metadata, mark only that field unavailable. No second take or handle method is permitted.
- Diagnostic path open/write fails while the original raises a sentinel KeyboardInterrupt: the same original object still propagates; state records only diagnostic failure type, never success or a replacement exception. KeyboardInterrupt is not a synthetic guard fault/verdict.

Additionally extract the actual event override AST with a fake base event and deterministic monotonic callable: only exploration/process_signal gains the marker; original kind/PID/signal/other fields pass unchanged, other process_signal and unrelated events gain nothing. No ROS load or signal is executed.

One short bounded pure-Python invocation only after Root pins/reviews the source and fixture. This is observer transparency evidence, not a successful DDS reproduction, A0 qualification or C model run. No cooperative SIGINT, library repair or exception suppression is proposed.

Entry: `check_spin_exception_observer.py` with `SPIN_EXCEPTION_OBSERVER_ADMISSION.json`, previously inert and activated by Root for one run, output `evidence/spin-exception-observer-01`, four direct-helper cases plus the restoration/bare-raise/narrow-event checks above. No test was executed during preparation; the admitted actual argv/cwd are retained in the launch record. Cwd is the repository:

```sh
rtk proxy timeout --signal=TERM --kill-after=1s 5s python3 -B net01d/followup04/check_spin_exception_observer.py --admission net01d/followup04/SPIN_EXCEPTION_OBSERVER_ADMISSION.json
```

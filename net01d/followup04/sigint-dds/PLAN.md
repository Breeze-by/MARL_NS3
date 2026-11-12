# Single DDS/SIGINT observation — inert

One script, one publisher process and one owned receiver child. Current run-02 ADMISSION=false, not executed; run-01 first failure is preserved below. Source reference is the preserved A0 AAE process-integrity failure; this does not change its result or the final NO-GO. Production/system/frozen sources remain untouched. Four-arm costs are not executed and C remains absent at this preparation point.

Same existing `net01/ros-python.sh` rootfs/setup/Humble/rmw_fastrtps_cpp, exclusive domain97. Fixed synthetic typed OccupancyGrid400x400/int8=160000cells, 20wallHz for12wall seconds, reliable/transientlocal/depth1, typed raw=False. Actual CDR byte size is recorded once. Callback only counts received messages. No per-message hot trace, payload rewrite, alternate types, clock/physics/NN/Nav2/controller or deliberate converter intervention. This is representative fixed message conversion input, not full Gazebo traffic or a capacity benchmark.

Receiver calls rclpy.init(SignalHandlerOptions.NO) as the actual frozen headquarters does, records that Python SIGINT still equals default_int_handler, and calls actual rclpy.spin. Parent sends exactly one SIGINT to this receiver PID after the fixed supply window. It does not aim the signal at C++ construction or retry. Parent/child argv/PID/ppid/start observations, source/admission-at-run, source count and first/last publish, actual signal before/after monotonic times and exit are preserved.

A top-level receiver exception observer records monotonic/UTC timestamp, type/message, cause/context and complete original traceback. It walks only existing traceback frames; for `_take_subscription`, it reads existing `sub.topic_name`, `sub.msg_type` module/name and `sub.raw` before cleanup. No private_take call, executor/type monkeypatch or system replacement. Metadata-read failure is recorded without replacing the original. Bare raise preserves the original exception and nonzero exit; finally destroys Node and shuts context, recording actual callback count/cleanup.

If the exact generic RuntimeError occurs, report MATCHING_RUNTIMEERROR_OBSERVED with actual subscription/signal timing, not a proven KeyboardInterrupt/null converter cause. If a normal KeyboardInterrupt or no matching RuntimeError occurs, report NOT_REPRODUCED; rare errors, different message types or the historical workload are not excluded. A real child exception/nonzero is propagated by the parent, never caught into exit0. No retry/matrix or Gazebo rerun follows.

30wall internal absolute bound,35wall outer+2kill; after SIGINT at most5wall to observe receiver exit, then failure cleanup sends owned TERM/1s and KILL/1s, no second SIGINT. Early failure is preserved without waiting for a signal or creating a false reproduction. First failure stops.

Prepared exact command (cwd repository), not yet authorized:

```
rtk proxy timeout --signal=TERM --kill-after=2s 35s bash net01/ros-python.sh /mnt/net01d/followup04/sigint-dds/check_sigint_dds.py --output /mnt/net01d/followup04/sigint-dds/run-02
```

Only AST syntax parsing has been performed. Root must review/pin/START and do immediate unique/domain/resource prechecks before this one diagnostic.

## Preserved run-01 / source-only run-02 correction

run-01 exited1 before0publish/0SIGINT because the direct x-open readiness file became visible before JSON completion. Its original result, traceback and at-run source/admission are unchanged. Current save helper only adopts the existing same-directory tmp x-write then atomic rename pattern. This does not alter message input, signal handling, budgets, ROS/system/production source, or prove the target issue absent. run-02 is a new unique inert output pending Root review/START; no retry has executed.

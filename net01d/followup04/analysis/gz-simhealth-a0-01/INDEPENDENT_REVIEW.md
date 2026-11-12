# gz-simhealth-a0-01 independent review

**Process-integrity FAIL: actual exploration controller exits1.** Preserve raw host/runner/network0/true as recorded, but do not present them as all-process success or A0 acceptance. B02 success does not resolve this A0 failure; no C admission follows. Bounded autonomy and subsequent physical-stop/ownership facts remain separately useful.

Read selected control-tail35/complete traceback, process-stop events, original small case result and AAE bootstrap/frozen main/shutdown source. No model, test, source edit, active bag, native ledger or PCAP read was performed. Read-scope exception: a file labelled `small-raw/a0-direct-safety.json` proved16.85MB and was mistakenly loaded once, with its arrays emitted into truncated tool output. This was disclosed to Root; it is not used for new cohort metrics or causal claims and was not reread.

## Observed stage and identity

The original autonomy window G22.83→202.83 reaches180sim/284.228446wall with35 actual inferences. Fourteen actual accepted UUIDs end in13 successes (6/3/4) and one tb1 cancellation, UUID `cb4c8515cce94742ab5791aab79fa4b1`, terminal5. These are actual Nav2 statuses; no synthetic outcome is inferred from registration or safety ACK.

Original smoke_bound is wall1794394908.482001; supervisor sends exploration PID860524 SIGINT at1794394908.4831517/G202.83. Actual process exit1 is observed1794394910.1910439/G203.89. Thus the **observed nonzero exit is post-budget and follows the shutdown signal**. The traceback itself lacks an exception timestamp; exact throw time relative to SIGINT is unrecorded and is not inferred from process exit alone.

The full stack is `a0_controller_bootstrap.py:52 → frozen gz01/headquarters.py:245 rclpy.spin → executor handler → executors.py:400 _take_subscription → sub.handle.take_message`, ending in `RuntimeError: Unable to convert call argument to Python object`. No subscription topic/type/entity/actual argument is printed. It is not a `close_controller()` traceback. SIGINT interaction, message/type-support conversion, callback/entity lifetime and the exact failing message remain **UNRESOLVED**; none is established as the unique cause. No source/mask/Policy/clock violation follows merely from that error string.

## Shutdown versus independent safety evidence

AAE's A0 bootstrap invokes the original main without replacing its executor/shutdown. Frozen `gz01/headquarters.py:254` always calls `close_controller` in finally; `rl04/ros_headquarters.py:156` calls `halt('rl04_controller_shutdown')` while ROS is alive, then closes events/node/ledger/context. Original `rl01/ros_policy.py:211` stops the allocator and dispatches `cancel_goal_async()` to current handles. One post-budget CANCELED UUID is consistent with that path; precise cancellation attribution needs the selected halt/cancel records, not the final status alone. `active_cancel_pass=false` remains the original round classification.

The subsequently supplied `halt-and-cancel-selected.json` confirms original allocator_halted at1794394908.483686571 and rl_halt_requested at1794394908.484242977, both reason `rl04_controller_shutdown`/sim202.83, after SIGINT. Selected actual statuses for the remaining UUID are2→3→5. Separate actual Cancel caller/request/response timing and GetResult5 response are **UNRESOLVED in the selected cache**; status5 is not renamed GetResult evidence and the exact cancellation issuer is not proved solely by this sequence.

After controller exit, original stop observation independently records physical stopping, three PAUSE acknowledgements and authority/request/UUID ownership closed, no unresolved UUIDs, error/hazard null. Those facts justify safe cleanup despite a failed authority process; they do not certify a clean controller return. Gateway, bag and launch later exit0. Original seal requires actual authority exit and physical/RPC closure, not authority exit code0; therefore valid stop/seal and controller1 can coexist without inventing failed physical stopping.

## Reporting boundary and smallest next step

Frozen `run_case.py:582` records `process_exit.code` but returns on any actual exit. The AAE external adapter's seal checks that the controller has exited; its general network integrity separately checks Gateway evidence/exit. This explains the recorded host/runner/network success alongside controller1. **All required process exit codes must be included in the external final integrity verdict**, retaining original raw files and distinguishing safe physical cleanup from clean execution. A failed controller must not be washed out by a save marker, empty ownership or a successful B run.

Do not catch/ignore this RuntimeError, turn every post-SIGINT exception into KeyboardInterrupt, relax safety rules, or modify frozen Policy/source to obtain exit0. The concrete underlying conversion repair is not identified yet. A narrow future source/fixture proposal may preserve the exact exception and identify the failing subscription/signal phase; no new run or instrumentation is authorized by this review. Canonical R metrics, if produced offline, can describe this completed bounded component but cannot change the controller-integrity FAIL.

## Canonical bounded metric component

Original R canonical small output subsequently reports one analysis, exit0/12.029943wall, original autonomy22.83→202.83/ROI15558: initial11.126109%→final99.884304% (15540cells),163/172 quality-valid, final valid at receipt202.75/source201.70. Quality-valid T50/80/90/95/98 are12.06/33.46/37.47/37.47/46.51sim. Natural completion remains false. These describe the preserved task-window data; they do not change process-integrity FAIL or establish a causal benefit over B02.

## Upstream source hypothesis and minimal diagnostic boundary

The open [joint_state_publisher issue117](https://github.com/ros/joint_state_publisher/issues/117) reports a comparable Humble shutdown leaf stack under load, using CycloneDDS rather than this case's FastRTPS. It is corroborating context, not a fix or attribution of this episode.

Upstream Humble [subscription.cpp](https://github.com/ros2/rclpy/blob/humble/rclpy/src/rclpy/subscription.cpp#L108) takes a typed message, converts it, then makes a Python tuple. [utils.cpp](https://github.com/ros2/rclpy/blob/humble/rclpy/src/rclpy/utils.cpp#L117) wraps the converter result without an explicit null-result/PyErr check. The [rosidl generator](https://github.com/ros2/rosidl_python/blob/humble/rosidl_generator_py/resource/_msg_support.c.em#L512) returns null if Python message construction fails. [pybind11 v2.9.1 make_tuple](https://github.com/pybind/pybind11/blob/v2.9.1/include/pybind11/cast.h#L911) emits the matching generic error when an argument object is null. This is a concrete possible propagation path; these upstream branches/reference version have not been proved identical to the installed compiled converter/pybind version. A KeyboardInterrupt during Python construction could fit it, but the episode contains no captured PyErr establishing that cause.

A minimal separately reviewed future diagnostic can use one no-motion real-DDS fixed workload under the same installed RMW, then one actual SIGINT with the original handler. A top-level exception observer can log monotonic time, cause/context and existing traceback-frame subscription metadata (`sub.topic_name`, message class/module, raw flag), then **re-raise the original error and preserve finally cleanup**. This adds no per-message hot logging, private take, payload rewrite or system-library replacement. If the single episode does not reproduce, record NOT_REPRODUCED rather than automatically repeating or rerunning Gazebo. Exact script/load/bounds still require Root admission; no diagnostic was executed here.

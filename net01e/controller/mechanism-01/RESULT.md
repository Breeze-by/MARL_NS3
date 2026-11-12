# Controlled constructor-entry SIGINT — installed mechanism observed

Root START/pin `ea497ba993c4d9bb8e1c455306ea08401b2cfec3`. One fixed control/intervention pair, actual outer exit1, internal2.010474wall. Original target RuntimeError/nonzero were preserved. This proves **installed typed-DDS conversion is susceptible to an artificially timed Python SIGINT**, not the unique historical A0 trigger or historical failing topic.

Both cases used the same legal160104B OccupancyGrid body, domain97, rawFalse, original Python default SIGINT handler and rclpy SignalHandlerOptions.NO. Strict entire-message CDR equality passed. Public sys.setprofile matched the exact installed OccupancyGrid.__init__.__code__, only below this real subscription's `_take_subscription:400`, then removed itself. No message class/private take/system library was patched.

| Observed case | Control | Artificial SIGINT intervention |
|---|---|---|
| Child PID/raw exit |1095130/0|1095172/1|
| Actual source publishes/callbacks |7/3|5/0|
| Matched hook |Real DDS take, no signal|Real DDS take, one signal.raise_signal(SIGINT)|
| Exception |None|Target generic RuntimeError at take_message|

Intervention hook entry620201850773884ns; single raise_signal request620201850795647ns; RuntimeError observed620201851157735ns (0.362088ms later). Exception cause/context are both None; no historical PyErr is reconstructed. Exception subscription metadata is `/net01e/controller/mechanism_grid`, `nav_msgs.msg._occupancy_grid.OccupancyGrid`, rawFalse, identity138979561000096, exactly matching the hook's actual take subscription. The full preserved stderr/exception stack ends at real installed executors.py:400 → take_message with the same generic error as historical A0.

Node destruction begins620201852577576ns after exception observation, ends620201859620648ns, then context is closed. Thus this controlled sample does not require prior entity destruction to produce the error. It also does not require an illegal body/NaN/type mismatch: the fixed body was legal and its unchanged no-signal control had three actual callbacks. This excludes those requirements **for this mechanism sample**, not all unobserved historical inputs.

Continuous source lasted through each child's actual exit observation; parent sent no cleanup signal. Parent1095062 and exact children1095130/1095172 are gone; postcheck found no mechanism_probe.py process or domain97 UDP31650–31899 participant. No policy/Goal/Nav2/Gazebo/ns-3/robot motion or production/system change. No second pair or repair executed.

Next candidate, only if separately source-reviewed/admitted: external bootstrap's public guard-woken spin_once boundary avoids raising Python KeyboardInterrupt inside converters and retains original ROS-alive close_controller halt/cancel. Do not catch-ignore RuntimeError or modify frozen Policy/main to obtain success. Historical A0 process-integrity FAIL remains unchanged.

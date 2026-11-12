# SIGINT/DDS run-01 — fixture failure before workload

Runtime197a, activation47a2b53; unique admitted command exited1. First failure is parent JSONDecodeError (empty char0) reading receiver-ready.json. Driver window0.496337s; **0messages and0SIGINT**. No target RuntimeError/KeyboardInterrupt observation exists, so this is NOT_TESTED, not NOT_REPRODUCED.

The fixture writes readiness with open(x) followed by json.dump while parent checks path.exists(); file creation precedes complete content. Parent consumed it during that window. The same retained readiness file is now valid JSON with the expected default Python SIGINT handler. This is the concrete readiness publication race, not a ROS conversion diagnosis. No source edit or retry was made.

Parent863877/receiver863895 are gone and domain97 UDP range is clear. Failure cleanup sent only owned SIGTERM; receiver actually exited−15. No receiver cleanup marker was produced, so normal receiver Python-finally/context closure is not claimed. Parent context did close. No SIGINT or second attempt was sent.

Preserved: original result.json/driver full traceback, receiver-ready.json, launch.json, receiver stdout/stderr, diagnostic/admission-at-run and external stdout/stderr/precheck. small-result.json records the selected failure and current owned/port evidence. Historical A0 process-integrity FAIL is unchanged; no diagnostic, controller or Gazebo acceptance follows.

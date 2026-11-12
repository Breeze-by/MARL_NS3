# DDS/SIGINT run-02 — inconclusive receiver exit timeout

Runtime197a/activatione05d3cf; unique actual command exit1, driver17.729362s. Ready publication succeeded atomically. Same installed FastRTPS receiver reports Python default SIGINT handler and typed OccupancyGrid/rawFalse. Actual publisher completed240calls of160104B CDR over fixed12wall/20Hz; actual receiver callback count is UNMEASURED because final cleanup record was never reached.

One SIGINT was sent to receiver864413 at mono613129139273176–613129139342730. It did not exit within the fixed5s wait. No receiver exception/cleanup JSON or stderr was produced; there is no `_take_subscription` frame or KeyboardInterrupt/target RuntimeError sample. Parent preserved TimeoutExpired/exit1, then owned failure cleanup sent SIGTERM only; receiver actualexit−15. No secondSIGINT, source change, extra message, repeat or model was performed.

Parent864392 and receiver864413 are gone; domain97 UDP range empty; ALL_OWNED_GONE/HEAVY_DONE. Parent context closed. Receiver normal Python-finally/context closure is not claimed from process disappearance.

This is INCONCLUSIVE/diagnostic failure, not target reproduction, full NOT_REPRODUCED or repair evidence. Successful os.kill does not establish Python handler execution. The fixed protocol stopped message supply before SIGINT and provided no later DDS input, differing from continued Gazebo traffic. With no live stack sample, exact blocked location and cause remain UNRESOLVED; no executor/ROS/privateAPI intervention was added. Historical A0 process-integrity FAIL and run-01 fixture race evidence remain unchanged.

Preserved original result.json/driver full exception, launch.json, receiver-ready.json, signal.json, receiver stdout/stderr, source/admission-at-run, external stdout/stderr/precheck and selected small-result.json. No further action is authorized by this result.

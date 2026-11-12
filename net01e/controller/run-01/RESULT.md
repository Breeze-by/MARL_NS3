# Continuous DDS run-01 — pre-exposure fixture FAIL

Actual command exited1. Driver PID1080121 failed at strict public typed CDR roundtrip equality before creating a child or initializing a ROS context/Node: `ValueError: Public typed CDR roundtrip mismatch`. Original result, exception and source/admission-at-run remain unchanged. Internal duration0.085556wall. Counts:0publish,0SIGINT,0child,0Node. Target conversion fault is NOT TESTED.

Root/reviewer identified the fixture's `.05` Python double versus ROS float32 resolution representation; full message equality was too early on an unnormalized float32 field. The subsequent source correction normalizes this single source field using struct float32 pack/unpack and retains strict whole-message equality, without tolerances or payload changes in the ROS representation. No automatic repeat followed the failure.

Read-only postcheck found no `continuous_dds.py` processes or domain97 UDP participants in31650–31899. No child was ever created; no cleanup signal was sent. Parent context is closed/uninitialized, recorded false.

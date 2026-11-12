# Equivalent broadcast raster: finite checks and local CPU result

The frozen `workspace/gz01/peer_keepout.py` was not edited. The candidate replaces dense `np.indices` coordinates with integer `np.arange` row/column coordinates, preserving coordinate arithmetic order, peer iteration, expanded radius, square/add/threshold operations and `np.where(...).astype(np.int8)`. It introduces no cache, thread, source-frequency, safety or NumPy configuration change. The production helper's function AST matches the measured helper.

The first attempt stopped before timing: its first mask was byte-identical, but independently serialized OccupancyGrid messages differed at offsets21–23. Raw originals and `first-CDR-diff.json` remain. One separately authorized same-object/same-data serialization diagnostic reproduced those three alignment-padding differences without any raster change. This is the padding after fixed `odom\0` before MapMetaData's next int32, not a mask difference. Comparing decoded values against the unquantized Python grid was also inappropriate for float32 resolution; r2 instead compares decoded messages against each other.

The approved r2 completed all15 cases: two actual logged stationary Peer snapshots through all three owner transforms, plus nine finite axial/diagonal tangent/nextafter cases. Every400×400 int8 mask byte matched the actual frozen function. For real ROS OccupancyGrid serialization, every byte outside the explicitly identified padding21–23 matched and decoded objects were equal. Actual CDR buffers were not normalized; **raw CDR equality is not claimed**. These finite checks do not establish all-input mathematical equivalence.

One predeclared benchmark ran in the actual rootfs Python3.10.12/NumPy1.21.5, with no concurrent timed work. After two warmup three-robot batches per implementation, six AB/BA pairs each measured five batches. No timing occurred in the failed first attempt, and no timed rerun followed r2.

| Mean per three-robot batch | Frozen oracle | Broadcast | Ratio |
|---|---:|---:|---:|
| Thread CPU |48.924140ms|6.074799ms|0.124168|
| Process CPU |48.922322ms|6.073124ms|0.124138|
| Monotonic wall |48.928704ms|6.075650ms|0.124174|

The measured batch saves about42.849ms thread CPU,87.6%, for `3×mask_poses + 3×peer_mask` on the selected fixed state. It excludes grid construction/setter, CDR, publication, executor, transport and native model cost. Historical18–19ms per-robot built spans were wall intervals, not isolated CPU; this benchmark does not reclassify all historical63ms as computation or prove Full freshness/RTF improvement. Outer r2 exit0/wall3.9091s; Node/ROS init/native/Gazebo were all0.

The separately authorized minimal integration is now SOURCE_READY: external BoundPeer retains `ORIGINAL_PEER_MASK`, explicitly selects original by default on each construction, and only selects `broadcast-v1` under the new `controlled1000-clock100-q10ms-pace10-clocklane-raster` profile. It sets the process-local module function before constructing Peer, without copying `publish_masks`. The saved marker records actual profile/implementation. New profile numeric/source/safety settings equal the prior clocklane profile; function/source/static selection checks passed in `integration-checks.json`. The producer handles the three profile-forwarding sites independently. No Full/Gazebo execution or source commit was performed by this task; independent review and separate qualification are still required.

Evidence: original failure/diagnostic files at this directory, preserved source/command snapshots and all12 timed batches in `r2/`, with the small result at `r2/result.json`.

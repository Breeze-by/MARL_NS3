# Setup, dependencies and future network boundary

## Supported clone-time check

Run the README CPU replay on Python3.10, using the pinned CPU dependencies. The included actual check used3forwards/113076parameters, matched original encoded inputs/conditional masks/actions/rawlogits and recorded goal positions, no gradients or optimizer. `evidence/verification-exit.json` also records the unchanged existing one-case synthetic storage-order test; it is not a full ROS, candidate reconstruction or navigation test. Fresh pip installation itself was not exercised during packaging; actual library versions are in the replay result.

## Source/build acquisition for ROS/Gazebo

Historical environment: Ubuntu22.04, ROS2Humble, GazeboClassic11.10.2, custom bundledSLAM2.6.0, bundlednav2_bringup1.1.16 with installed Nav2 controller/planner/costmap filters1.1.20. The mixed versions are intentional recorded facts, not one blanket Nav2 version. `provenance/historical-dependency-inventory.json`, package.xml files and validated-loaded-driver.json document the original build/source linkage.

Get ROSHumble from its official Ubuntu repositories, Gazebo ROS packages/Navigation2/TurtleBot3 description+simulation dependencies, rosdep andcolcon, then resolve bundled package dependencies without replacing the source fork:

```bash
source /opt/ros/humble/setup.bash
cd workspace
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select \
  base01_diff_drive nav2_bringup slam_toolbox multi_robot merge_map multi_robot_exploration rviz2-panel
source install/setup.bash
```

These are environment reconstruction instructions, **not a newly validated portable Gazebo launch**. Archive/recreate the recorded package versions before a comparable run; current apt repositories may differ. The complete modified driver and its CMake compiler switch/plugin environment hook are bundled, not a replacement of system libraries. Preserve the original TurtleBot3 mesh/SDF resources and package licenses. `assets/gazebo_models` provides the inherited licensed SUV model for legacy supplied worlds; current fixed comparison layouts are the declared box worlds.

`workspace/gz01/python.sh` and historical `rl*/ros-python.sh` are preserved byte-for-byte: they reference bwrap, `base-01-econ/isolation/rootfs`, `/project`, sibling `rl-04` and historical host Python packages. This Git package intentionally contains neither that rootfs nor its host installation. Do not run those wrappers expecting them to download/reconstruct their environment. Likewise upstream generic mapping launches are historical utilities, not an automatically equivalent frozen three-robot benchmark. Rebuild/rebind the environment and create a new explicit run admission before reproducing Gazebo; no old READY authorization is distributed.

Frozen high-level source lives in `workspace/gz01/headquarters.py`, `rl04/ros_headquarters.py`, `rl01/ros_policy.py`, and the allocation/joint/encoding modules. `inputs/scenes` declares common triangleposes/world/seed/reference; scene_launch uses one pose list for physical spawn and map calibration. `config/validated/<map>/<arm>` contains the actual six YAML sets. No global/source constant may be silently edited to make a new installation pass.

## Training provenance

The sole6d checkpoint is the unchanged RL04 pre-TESTVAL-selected512joint/16additionalAdam prefix, not the completed2048 checkpoint. The parent run completed2048/64Adam and inherited RL03 weights. Original selection, summary andprocess-exit JSONs are preserved under `runs`; their local paths and historical `formally_frozen=false` are originaltime records. The checkpoint metadata includes configuration/formal-lock lineage; training source and locks remain under `workspace/rl01..04`, with originalRL04 report inprovenance. Old corpus/raw run directories are not cloned here, so exact retraining provenance is indexed rather than falsely claimed reproduced. No training was run for release or after followup10.

## Future ns-3 / real Wi-Fi

ns-3.40/ns3-gym are a future separately installed dependency; this release does not vendor ns-allinone or resume an older wireless scheduling project. No transport bridge, constrained network result or hardware deployment is certified.

For an actual communication comparison, freeze this policy/execution version, establish a matched ideal-delivery reference, then make relevant maps/poses/taskfeedback/goal+cancel delivery pass through the constrained transport. Preserve source stamps, receipts, frame and ownership identity; no idealROS/shared-memory bypass for data that failed delivery. Network scheduling/priorities/compression can vary while policy semantics stay fixed. Timeouts/local disconnect safety, source age, clocks and deliveredAction cancellation must be validated independently before nonideal or hardware runs. Do not add a hidden goal allocator, retrain for a communication arm, or silently resizeROI/change candidate rules. Such changes require a new comparable version.

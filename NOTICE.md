# Attribution and component licenses

The root LICENSE reproduces the original MIT license of `multi_robot_exploration` (copyright 2024 CHAN JIAN LE). It is **not a blanket relicensing** of this distribution. Each component's original LICENSE/COPYING, source headers and package.xml remain authoritative; retain them when redistributing.

- Base workspace: [econsystems/ros2-multi-robot-automap](https://github.com/econsystems/ros2-multi-robot-automap). Original README/Technical Manual are preserved in `docs/UPSTREAM_*`; nonruntime demo videos/debug and SLAM documentation images are intentionally omitted.
- Modified multirobot SLAM Toolbox: [acachathuranga/slam_toolbox, multirobot_ros2](https://github.com/acachathuranga/slam_toolbox/tree/multirobot_ros2), package2.6.0; `workspace/src/slam_toolbox/LICENSE` and `lib/karto_sdk/LICENSE` preserve LGPL2.1/third-party terms. Complete included source is available, not just a binary.
- Nav2 bringup: [ros-navigation/navigation2](https://github.com/ros-navigation/navigation2); bundled bringup source1.1.16 declares Apache-2.0 in package.xml; its source headers are retained and the full license text is supplied in `LICENSES/Apache-2.0.txt`. Historical installed controller/planner/filter libraries were1.1.20, not a uniform single Nav2 version.
- `base01_diff_drive` derives from Gazebo ROS differential drive; complete modified source, CMake/state-sync variants, plugin hook and original BSD copyright/license are in `workspace/src/base01_diff_drive`.
- `multi_robot` robot meshes, `merge_map`, `rviz2-panel` and every other src package retain their individual licenses. `assets/gazebo_models/LICENSE` accompanies the inherited SUV asset needed by older supplied example worlds; runtime robot meshes must not be replaced by documentation placeholders.

Research modifications include received-observation goal allocation/PPO, source-bound execution contracts and engineering adapters. Original comments and copyrights are preserved. No license is inferred from a different subdirectory's MIT file. Some historical source tools refer to original local paths; see SETUP for the supported CPU entry and environment reconstruction limits.

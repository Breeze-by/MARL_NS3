# BASE-01 Econ 三机器人传统探索基座：最终复现与交接报告

本次在独立工作区完成了 Econ 架构下的**正确性修补版传统探索基座**。最终正式回合 `baseline-fixed-01` 完成 180 秒仿真自主探索，三台均有真实 Nav2 成功、反馈及再次分配，SLAM 与融合地图更新，可信停止通过。结论为 **SOURCE PASS、BUILD PASS、三机器人 RUNTIME PASS、BASELINE SMOKE PASS**；不认定完整探索任务完成或实机可靠性通过。

原 `REPORT.md`、`REVIEW_RESPONSE.md` 和其清单是对应阶段的历史报告，保留不改；其中 BLOCKED、未应用驱动补丁、尚无新版运行等陈述描述当时状态。本报告及最终证据更新当前状态。后续继续工作先读本报告，再按需追溯历史。

## A. 环境、源码与版本

项目根目录：`/home/zhuyulab/ns3-workspace/base-01-econ/`。

| 项目 | 实际状态 |
| --- | --- |
| 宿主系统 | Ubuntu 22.04.5 LTS，x86_64，内核 6.8.0-138-generic |
| 硬件 | 双 Intel Xeon Gold 6148，80 逻辑 CPU，125 GiB RAM；工作分区约 1.8 TiB，初始约 1.6 TiB 可用 |
| 原始 ROS 环境 | 无可执行 ROS/Gazebo；环境变量残留指向已不存在的 `/opt/ros/humble`；初始未发现运行中的机器人实验 |
| 隔离方式 | 项目内 Ubuntu Base 22.04.5 rootfs + Bubblewrap；不向主机安装/覆盖 ROS，不修改其他 overlay |
| ROS | Humble；ros-base 0.10.0-1jammy.20260915.225919 |
| Gazebo | Classic 11.10.2+dfsg-1；gazebo_plugins 3.9.0-1jammy.20260915.221351 |
| Python / CMake | 隔离 `/usr/bin/python3` 3.10.12 / 3.22.1 |
| colcon / rosdep | colcon-core 0.21.3+upstream-1 / rosdep 0.27.0-1 |
| Nav2 | Humble 二进制运行组件 1.1.20；仓库 nav2_bringup 源码声明 1.1.16 |
| SLAM | Econ 内嵌修改版源码，package.xml 声明 2.6.0；真实编译，没有换成系统 SLAM |
| TurtleBot3 | gazebo 包 2.3.8-1jammy.20260915.233431；description 2.3.6-1jammy.20260907.200214；Waffle |
| 运行隔离 | ROS domain 61、localhost；Gazebo master `127.0.0.1:11661`，Xvfb :61，软件渲染；不启动 RViz/gzclient |

原始环境与安装记录见 [host-audit.txt](evidence/initial/host-audit.txt)、[isolated-versions.txt](evidence/initial/isolated-versions.txt)。所有依赖安装在用户拥有的 `isolation/rootfs/`，没有宿主 sudo 安装、卸载或全局配置覆盖。Bubblewrap 用于依赖隔离，不声称它是针对不可信程序的安全沙箱。

### 固定源码身份

| 对象 | 身份 |
| --- | --- |
| 指定上游 | [econsystems/ros2-multi-robot-automap](https://github.com/econsystems/ros2-multi-robot-automap) |
| 上游分支 / commit | main / `9825c57f83c2bfb52790cb55b51d30009cbb346f` |
| 原版 | `upstream/`，标签 `base-01-upstream`，工作树干净 |
| 原交付固定提交 | `6ace727938f3e1ede3887e2c921855dc785034a1`，分支 `base-01/reproduce` |
| 正确性修补提交 | `46e072e4f234f87f69b4be34a6f0be3c34befcc9` |
| 驱动、仪表化与运行方案 | `8c6d58bfe4960ff08058bae9bc9b5b8c6df2b517` |
| 180秒正式回合源码/工具 | **`de5b8a033f77338eb3524f8b0d21d1f006ef52b7`**，tree `3e0df530d1469c1f22752527a58d9a5c623e9828`，分支 `base-01/review-corrections` |
| 活动目标取消补证源码/工具 | **`985cb095e01c7f2896c55bddd71c36ba3d0da0ea`**；仅修改监督工具及方案，`src/`与180秒版本无差异，驱动二进制相同 |

最终文档提交另记录在 [delivery-identity.json](evidence/final/delivery-identity.json)，不把后来添加的报告提交冒充运行时提交。实际工具入口是根目录 `tools/`，Git 内 `workspace/base01/tools/` 是逐文件相同的身份副本。每个有效新回合运行前固定源码、工具和二进制，启动后用实际 gzserver 的 `/proc/PID/maps` 与 inode 再绑定加载库。

官方资料以 [固定 README](https://github.com/econsystems/ros2-multi-robot-automap/blob/9825c57f83c2bfb52790cb55b51d30009cbb346f/README.md) 和 [固定 Technical Manual](https://github.com/econsystems/ros2-multi-robot-automap/blob/9825c57f83c2bfb52790cb55b51d30009cbb346f/Technical_Manual.md) 为参照，结论以本地源码和证据为准。

Econ 没有根目录统一 LICENSE。multi_robot、merge_map、multi_robot_exploration 附 MIT 文件，multi_robot 元数据许可仍有 TODO；nav2_bringup 声明 Apache-2.0，SLAM 声明 LGPL。SLAM README 引用 acachathuranga 的 multirobot_ros2 分支，但嵌入目录没有独立 Git 历史，不能证明其完整等同某一 fork commit；复现基准是 Econ 固定源码加本地 diff。

SUV 缺失资源取自 [osrf/gazebo_models 固定版本](https://github.com/osrf/gazebo_models/tree/8163eb4b5e7e21985c6591d1c0bfb56468c0093f/suv) `8163eb4b5e7e21985c6591d1c0bfb56468c0093f`，原 CC BY 3.0 许可保留在 assets；未替换 world 或删除障碍。驱动源来自 gazebo_ros_pkgs 3.9.0、commit `ae6e5793a31f5927df89cb58007d2a5eb567baa8`，完整原版权/许可注释保留于新增包 LICENSE、源码及头文件；原文称 BSD License 2.0，含不背书条款，以完整原文为准。

## B. 实际架构与中央算法

```text
workspace/src/
  multi_robot/              Waffle 模型、原 world、launch、tb1–tb4 Nav2 参数
  slam_toolbox/             Econ 修改版 multirobot_slam_toolbox_node
  merge_map/                MergeMapNode / merge_maps
  multi_robot_exploration/  HeadquartersControl / 传统 Frontier
  nav2_bringup/             随仓库提供的 bringup
  base01_diff_drive/        独立命名、可追溯的差速状态修补与诊断库
  rviz2-panel/              可选，本轮不构建
```

链条为：**Gazebo LiDAR → 每机修改版 SLAM → 校准坐标下地图融合 → Frontier → HeadquartersControl → 各机 NavigateToPose → Nav2 → 差速关节/物理运动**。Nav2 使用仓库 `multi_robot/launch/nav2_bringup/` 配置，顶层 nav2_bringup 也已构建，不混称为全部使用系统 bringup。

| 真实接口 | 类型、作用 |
| --- | --- |
| `/tbX/scan` | LaserScan，360 点，0–6.28 rad，0.12–10 m，SDF 5 Hz |
| `/tbX/odom` | Odometry，30 Hz，编码器积分；各自 odom→base_footprint |
| `/tbX/tf`、`/tbX/tf_static` | TFMessage；每机隔离的 map/odom/base 帧，同名 frame 不跨话题混用 |
| `/tbX/map` | OccupancyGrid，每机 SLAM，0.05 m 分辨率 |
| `/merge_map` | OccupancyGrid，中央共同坐标；不是自动地图配准 |
| `/tbX/navigate_to_pose` | NavigateToPose Action，含目标、接受、反馈、结果与取消 |
| `/tbX/cmd_vel_nav` → `/tbX/cmd_vel` | 本地 Nav2 控制/平滑至底盘 |
| `/gazebo/model_states`、`/tbX/contacts` | 仅监督与评估，不输入探索决策 |
| `/tbX/drive_diagnostics` | 驱动接收、消费、实测轮速、内部状态和实际关节目标，仅诊断 |

三台出生位置沿用官方数组：tb1=(5,4)、tb2=(-4.5,4)、tb3=(6,-1.5)，yaw=0；原第四台仍保留，robot_count=3 时只切片启用前三台。三个参数文件、SLAM、Nav2、融合和中央控制器数量均为 3，无 tb4 实例。

### 坐标、SLAM 与融合

原 WORLD 默认里程计已显式改成 ENCODER=0。实际首次 odom 三台都接近 (0,0)，不是各自世界出生坐标。每机 TF 内发布 `merge_map → map` 已知初始相对位姿，再由 SLAM 发布 `map → odom`，差速发布 `odom → base_footprint`。启动快照和持续查询覆盖到 base_scan；没有另启 AMCL 争抢 map→odom。

**初始相对位姿来自场景声明，是标定假设。** 本轮没有自动配准或在线真值定位输入；实机必须提供可获得的初始标定/定位，不能照抄仿真出生坐标当实机测量。Gazebo 真值只用于轨迹和安全核验。

`merge_maps(maps, frame_id, map_poses)` 使用显式 common←local-map 标定，支持地图 origin 旋转和不同分辨率，按输出格中心逆投影采样；已知占据值取最大，未知不覆盖已知，自由不擦除障碍；输出单位四元数，时间戳取最旧输入。它是固定标定下的栅格融合，没有回环配准/位姿图优化。中心采样及保守占据冲突可能带来锯齿、误差和保留旧障碍，不能称为实机地图融合已解决。

### HeadquartersControl 的替换边界

文件：`workspace/src/multi_robot_exploration/multi_robot_exploration/control.py`。

| 函数/状态 | 真实作用 |
| --- | --- |
| `costmap()`、`frontierB()` | 障碍膨胀；提取邻接未知区的自由格 |
| `assign_groups()`、`dfs()`、`fGroups()` | 八邻域分组；显式栈保持原遍历顺序；保留前五个且大小>2的组 |
| `findClosestGroup()`、`exploration()` | 保留组大小/质心距离评分和原距离限制；取近质心的实际可达 Frontier 自由格 |
| `map_callback()`、`robot_odom_callback()` | 共享地图；odom 时刻经各机 TF 转到 merge_map 的位置 |
| `local_map_callback()`、`nav_goal_in_local_map()` | 发送前检查目标属于该机器人本地图内自由格 |
| `start_exploration()` | 原每机线程，8 秒墙钟检查 idle 并分配；不是联合优化求解器 |
| `ASSIGNED`、`VISITED`、`FAILED` | 预留、成功访问、逐机本回合失败排除；取消/临时不可用释放预留 |
| `send_goal()` | 共同目标变换到各机 map，发送合法四元数的 Nav2 Action |
| `goal_response_callback()`、`goal_result_callback()` | 接受与真实终态分开；成功、失败、取消后释放/更新状态 |

本轮没有增加 Policy 层。未来 RL 的最小替换位置是 `HeadquartersControl.start_exploration()` 中对 `exploration()` 的任务选择调用，以及 `findClosestGroup()` 的传统评分部分：把共享地图、Frontier、`robot_positions`、`robot_states` 和任务反馈交给中央 RL 联合分配，再复用 `send_goal()` 与 Nav2。届时联合触发/状态编码需另行设计，不能将当前三线程误称为已实现联合 RL 接口。

`feedback_callback()` 仍不参与策略决策；监督器确实订阅并保存 Nav2 feedback。删除了“全部 idle 就保存地图/当成完成”的错误路径。失败位置在该机器人本回合保守排除，不随地图更新自动重试；可能留下未探索区，本轮没有新增自然探索结束算法。

## C. 构建、必要修复与复现命令

准确环境引导、顶层 apt 包名与用途及安装失败原件见历史 [REPORT.md](REPORT.md) 的 C 节。主要依赖为 ROS Humble base/navigation2/gazebo-ros-pkgs、TurtleBot3 gazebo/description、joint-state-publisher、xacro、tf2-tools、Ceres/Boost/Eigen/Qt、Python NumPy/OpenCV、colcon、Xvfb。当前实际控制器已移除未使用 SciPy import；不依赖它实现新算法。

未安装系统二进制 SLAM/bringup 替代源码。rosdep 数据库未初始化，`rosdep keys` 失败原件保留；**当前隔离环境真实构建通过，不等于已验证全新机器 rosdep 一键安装**。apt 源随时间变化，完整版本清单和现存 rootfs 才是本轮环境记录。

本轮执行的构建包括以下各组；日志保留完整输出，不掩盖 stderr：

```bash
cd /home/zhuyulab/ns3-workspace/base-01-econ
tools/in-rootfs.sh -c '
  source /opt/ros/humble/setup.bash
  cd /project/workspace
  export CMAKE_BUILD_PARALLEL_LEVEL=8 MAKEFLAGS=-j8
  colcon build --symlink-install --packages-select nav2_bringup slam_toolbox \
    --parallel-workers 2 --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
'
tools/in-rootfs.sh -c '
  source /opt/ros/humble/setup.bash
  source /project/workspace/install/setup.bash
  cd /project/workspace
  export CMAKE_BUILD_PARALLEL_LEVEL=8 MAKEFLAGS=-j8
  colcon build --symlink-install --packages-select slam_toolbox merge_map multi_robot_exploration multi_robot \
    --parallel-workers 2 --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
'
tools/in-rootfs.sh -c '
  source /opt/ros/humble/setup.bash
  source /project/workspace/install/setup.bash
  cd /project/workspace
  export CMAKE_BUILD_PARALLEL_LEVEL=8 MAKEFLAGS=-j8
  colcon build --symlink-install --packages-select base01_diff_drive \
    --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
  colcon build --symlink-install --packages-select multi_robot --cmake-args -DBUILD_TESTING=OFF
'
```

六个必要包均真实构建/发现，实际运行加载源码修改版 SLAM、各 Nav2 节点及新增独立驱动。最新驱动构建约 90 秒，Gazebo CMake FindPkgConfig 命名不一致为 dev warning，不是构建失败；后续 launch 包重建通过。先前 SLAM 构建曾因会话中断恢复，安装曾有 fontconfig 未配置并在隔离环境修复，原日志均保留。

### 修复范围

1. robot_count 与原数组同步，保留四台能力；增加非自主/headless 开关；mapping 下禁用 AMCL；修 mesh 绝对路径与时钟初始跳变。
2. 修改版 SLAM 补 scan_header 更新，修复真实 map→odom 缺失；补地图 origin 单位四元数，未改优化器或建图方法。
3. Nav2 修 `goal_checker_plugins` 错字段；半径 0.25 m 包络约 0.237 m 底盘 collision 外接半径。没有改 Nav2 源码或为覆盖率调速度。
4. 坐标、占据融合、Frontier 合法性、迭代 DFS、Action 终态与失败状态修补；线程异常可见地传播至进程。详见 [REVIEW_RESPONSE.md](REVIEW_RESPONSE.md) R1–R8。
5. 差速执行状态同步修补，见下节。原摩擦、collision、轮距0.287 m、轮径0.066 m、扭矩20和加速度1.0均未为停止效果调参；停止阈值未放宽。

这些是 Econ 架构下的**修补变体**。融合冲突、合法代表点、失败排除和编码器坐标合同确实改变行为，不能宣称与原版逐动作相同，也不能把新旧回合混为同一策略的性能对照。没有引入新的任务分配优化算法。最终源码差异可用 `git -C workspace diff base-01-upstream de5b8a033f77338eb3524f8b0d21d1f006ef52b7 -- src` 审查，副本为 [econ-base01-final.patch](evidence/final/econ-base01-final.patch)。

## D. 停止归因与三机器人真实运行

### 失败原件与停止修复

| 回合 | 结果与证据边界 |
| --- | --- |
| run-01 | 冷启动 sim_time=1996.381 导致 spawn 超时；保留原件 |
| run-02 | 三台启动但 SLAM map→odom 缺失；保留原件 |
| run-03 | 原交付 180 秒自主链运行，停止 FAIL；零命令接收/轮速未记录，不能事后断定唯一根因；物理暂停仅收尾 |
| stop-original-01 | **无效诊断，NOT PASS**；事前身份捕获因主机无法解析 `/project` 绝对库链接失败，旧 shell 未 fail-fast 仍启动，发现后在受控运动前中断。此外实际记录 sim7.4 的 Python 参数转换异常、cancel service 超时、pause service 超时；没有 traceback，无法确定异常来源或与中断的因果关系。身份路径修复不能解释成已经定位/修复此转换异常。该回合不进入因果比较 |
| stop-original-02 | 有效原算法仪表化诊断：三台原地0.6 rad/s转4秒仿真后停。12秒停止标准也通过，但已消费零目标后仍出现反向/过强电机目标与残留内部状态，组件缺陷得到真实执行证据 |
| stop-fixed-01 | 同协议固定版诊断通过，约2.47秒墙钟确认停止；零目标下内部状态与关节目标归零，未用物理暂停 |
| baseline-fixed-01 | 最终新版正式自主180秒，完整冒烟通过，下表详列 |
| active-cancel-01 | 补证工具原先错误要求Action状态周期更新；发现后在前置检查期间中止，smoke_started=false。退出时tb2取消服务不可用，未确认停止，以物理暂停收尾；**不是PASS**。原件保留，不冒充活动取消证据 |
| active-cancel-02 | 修正为EXECUTING的同UUID新鲜反馈后，31.6秒自主区间捕获三台实际运动，各取消1个活动目标，同UUID均CANCELED=5，真实停止及退出通过 |

前置 [BASE01_REQUIREMENTS.md](BASE01_REQUIREMENTS.md) 和 [STOP_DIAGNOSTIC_PLAN.md](STOP_DIAGNOSTIC_PLAN.md) 已在新增运动前固定要求与中止判据。最新用户续做授权解除此前“仅离线/不追加运行”限制；新增诊断与一轮修补版正式冒烟用于闭合真实阻断。独立复核随后指出正式结束时无活动目标，依 [ACTIVE_CANCEL_PLAN.md](ACTIVE_CANCEL_PLAN.md) 只补取消活动目标这一缺证项，没有重复完整180秒或为覆盖率选图/调参。

原算法的问题是加速度分支把修正量累加到旧指令，近目标分支又不更新该内部状态。原算法有效诊断在零目标已接收并由物理线程消费后，每台有7行“电机目标绝对值大于实测值”的记录，出现方向反转，末尾内部轮缘指令仍约[-0.0402,+0.0402] m/s。修补近目标分支同步期望值，其他分支使用“实测值 + 限幅增量”。相同固定版诊断该类行数为0，内部状态归零。详见 [comparison.json](evidence/stop-diagnostics/comparison.json) 及各回合 CSV。

这证明了组件状态缺陷和修补版实际停止能力，**不证明 run-03 残余运动全部或唯一由该缺陷造成**。原算法本次也能在窗口内停，不将其写成停止失败。

驱动独立包编译两个库：诊断库保留原执行算法，固定库启用状态同步；只在不同 Gazebo 进程选一个，不覆盖系统库。正式加载固定库 SHA256：

```text
8d54d39a687de851c95137ddee4a7ebbab90c3373e07d96fad338870d4317fc0
```

实际接收序号、接收 ROS 时刻、物理线程消费的linear/angular、实测轮缘速度、期望轮速、内部指令、实际 joint vel 目标和 state_sync 标志共14字段，完整保存到 `drive_diagnostics.csv`；不是仅观察 cmd_vel 话题来代替执行确认。[loaded-driver.json](evidence/baseline-fixed-01/loaded-driver.json) 与 `gzserver.maps` 绑定真实加载文件。

### 最终正式回合

本次已执行命令如下；原目录存在时脚本拒绝覆盖。不得为了重现报告自动再次运行；若以后明确要求新增实验，换新的身份文件和回合目录。

```bash
set -e
python3 tools/capture_case_identity.py evidence/baseline-fixed-01.identity.json \
  --driver libbase01_diff_drive.so --kind autonomous_smoke
tools/in-rootfs.sh tools/run-baseline.sh /project/evidence/baseline-fixed-01 \
  --sim-seconds 180 --wall-seconds 420
```

监督器实际先启动 `ros2 launch multi_robot gazebo_multirobot_mapping_with_nav2.launch.py robot_count:=3 drive_plugin:=libbase01_diff_drive.so enable_exploration:=false enable_rviz:=false enable_gui:=false enable_drive:=false`，检查 scan/odom/map/TF/contacts/drive、Nav2 active、模型数量/间距与静止后才恢复 Nav2，并运行 `ros2 run multi_robot_exploration control --ros-args -p robot_count:=3 -p use_sim_time:=true`。

正式回合不调用诊断旋转方法；非零速度来自 Nav2，本轮没有 set_model_state/人工移动。每2秒墙钟检查观测新鲜度、SLAM/planner/controller/bt节点和 map→base_scan TF，出现异常即停止。自主区间开始清零运动/目标/反馈/地图变化指标，避免用前置启动数据凑结果。

| 指标 | tb1 | tb2 | tb3 |
| --- | --- | --- | --- |
| Nav2 接受且成功的唯一目标 | 2 | 2 | 3 |
| Action feedback 消息 | 3462 | 2912 | 7115 |
| Gazebo 路程采样和，m | 4.967 | 4.523 | 10.577 |
| 相对自主起点最大位移，m | 3.947 | 4.059 | 5.873 |
| 变化的局部地图版本 | 8 | 6 | 15 |
| 自主区间首/末地图已知格 | 1586 / 15196 | 1505 / 16395 | 1374 / 34811 |
| 最终停止线速度，m/s | 0.0000538 | 0.0000565 | 0.0000649 |
| 最终停止角速度，rad/s | 0.000000911 | 0.000000501 | -0.000000408 |

三台都有成功后再次分配，UUID、目标及终态可在 `control.log`、`events.jsonl` 对照。tb3 controller在Unix1793791926.183856记录过 `Failed to make progress`，随后同一首个目标在1793791926.972902返回成功，属于本次实际出现并恢复的Nav2进展异常；不能写成零错误运行。正式回合没有Action ABORT/REJECT终态；这些失败路径仅离线用例验证，不声称已做新的运行失败注入实验。

共享地图自主区间改变29次，首/末区间已知格4465/49729。地图仍从真实 LiDAR + SLAM 产生，PGM/NPZ保存初末样本。**已知格数不是覆盖率**，没有可探索区域分母或自然终态；后半程全部 idle 也不能解释为完整任务成功。

自主区间为 UTC **2026-11-04 11:31:45.133623–11:35:05.816442**（北京时间19:31:45–19:35:05），sim **20.6–200.6**，180.0秒，墙钟200.683秒；正常达到仿真预算，未触发420秒墙钟上限。全回合最小观测机器人中心距2.3975m，底盘接触事件0，无已记录 hazard。此为10Hz模型/接触监督的有界观察，不是连续碰撞或未来实机安全认证。

### 可信停止与退出

结束顺序为停止 HeadquartersControl → 取消各机目标 → 暂停各套 Nav2 → 20Hz零速度 → 驱动新接收且消费零值 → 核对三台新鲜真实模型速度 → 停止 launch/Xvfb。采用原判据：线速度<0.01m/s、|角速度|<0.03rad/s，连续>1.5秒墙钟且仿真继续推进>0.5秒，停止观察窗口12秒墙钟。缺机、旧样本、时钟冻结均不通过。

本轮在 UTC11:35:11.392276 确认停止，距预算结束5.576秒墙钟（含停止控制器/导航服务耗时）；合格持续期内仿真推进1.4秒。三台新消费零目标，内部与关节目标均为0，无 emergency_physics_pause。正式回合结束前目标已完成，停止时主要验证 idle 后闭环收尾；有运动到停止的执行能力另外由 `stop-fixed-01` 的动态诊断提供，不夸称覆盖了所有运行工况。

### 活动自主目标取消补证

`active-cancel-02`保持相同机器人/导航/探索/驱动源码，运行命令额外指定 `--active-cancel-check --sim-seconds 60 --wall-seconds 120`，事前身份种类 `active_cancel_check`，不发人工目标或非零诊断速度。实际自主区间仅31.6秒仿真/36.464秒墙钟，达到取消条件后立即收尾，没有重复完整180秒。

UTC11:43:52.281259、sim53.3记录三台已接受且正在反馈的Frontier目标及运动，取消响应均return_code=0且goals=1，UUID逐台对应并到达CANCELED=5：

| 机器人 | 活动且被取消的UUID | 触发时真实线速度m/s | 停止线速度m/s | 停止角速度rad/s |
| --- | --- | --- | --- | --- |
| tb1 | `106b739444574dd0a974dea2ac6724ec` | 0.252872 | 0.0000595 | 0.006287 |
| tb2 | `253e2f8747e549a993859bfff973731c` | 0.177798 | 0.0000662 | 0.013248 |
| tb3 | `221ae712669d40688ac3ffb67e5d8842` | 0.052429 | 0.0000585 | 0.001236 |

UTC11:44:02.237932确认真实停止，触发后9.957秒墙钟、最后Nav2暂停后5.731秒；稳定期仿真推进1.4秒。三台驱动新消费零值，内部和电机目标为0，未物理暂停，接触0、hazard为空。控制器与顶层launch均退出0，gzserver退出。结果为 `active_cancel_pass=true`；`baseline_smoke_pass=false`是因为此补证按活动取消条件提前结束，不是180秒主体验收，二者不混淆。详见 [active-cancel-analysis.json](evidence/final/active-cancel-analysis.json) 和 [原始result](evidence/active-cancel-02/result.json)。

控制器和顶层 launch 退出码均0，gzserver正常退出。merge_map在发SIGINT后留下KeyboardInterrupt/exit -2，部分SLAM、Nav2与joint-state等子进程也记录SIGINT对应的-2，HQ有context关闭后的rosout警告；均发生在停止确认后的退出阶段，不隐去这些日志，也不描述所有子进程均返回0。最终进程快照未发现本轮 Gazebo、导航、监督器或Xvfb残留。

## E. 证据、检查与校验

核心入口：[result.json](evidence/baseline-fixed-01/result.json)、[runtime-analysis.json](evidence/final/runtime-analysis.json)、[事前身份](evidence/baseline-fixed-01.identity.json)。

| 证据 | 路径 |
| --- | --- |
| 完整启动、控制器、监督日志 | `evidence/baseline-fixed-01/launch.log`、`control.log`、相邻 `baseline-fixed-01-supervisor.log` |
| 节点/话题/Action/进程 | 该回合 `nodes.txt`、`topics.txt`、`actions.txt`、`processes.txt`、`processes_after.txt` |
| TF结构与持续检查 | `tf_edges.json`；`events.jsonl`与监督器中的持续查询/故障路径 |
| 目标/UUID/反馈/状态、停止、异常/时刻 | `control.log`、`events.jsonl` |
| 跟踪进程退出复核 | `evidence/final/tracked-process-exit.json`、`host-processes-after.txt` |
| 本域ROS CLI daemon退出 | `evidence/final/daemon-stop.txt`、`daemon-exit.json`；只停止本项目domain61服务 |
| 真值轨迹与驱动执行 | `trajectories.csv`、`drive_diagnostics.csv` |
| 地图原件 | `tb1/tb2/tb3/merge_map` 各自 `_first/_last.npz`、`.pgm`（文件名实际用机器人名前缀） |
| Gazebo/ROS日志 | 回合 `gazebo_logs/`、`ros_logs/`；Xvfb在相邻 `.xvfb.log` |
| 构建与测试 | `evidence/revision-01/build.log`、`evidence/stop-diagnostics/driver-build.log`、`launch-build.log`；最终`evidence/final/offline-tests.txt` |
| 停止原/修补比较 | `evidence/stop-original-02/`、`stop-fixed-01/`；各自相邻identity及supervisor日志；`stop-diagnostics/comparison.json` |
| 活动目标取消/真实停止 | `evidence/active-cancel-02/`、相邻identity/supervisor日志；`evidence/final/active-cancel-analysis.json`；失败前置启动`active-cancel-01/`保留 |
| 最终源码差异与身份 | `evidence/final/econ-base01-final.patch`、`delivery-identity.json` |

![最终SLAM融合地图及自主区间Gazebo轨迹](evidence/final/map-trajectories.png)

图是保存栅格与轨迹的离线可视化，不是Gazebo/RViz截图，不替代原始数据。地图与世界轨迹共框基于本轮声明的初始标定。

14项针对修补的离线回归通过，覆盖缺机/断流/冻结时间/残余速度拒绝、坐标变换、融合冲突/旋转/分辨率、长Frontier、凹边界/不连通/局部图范围、Action状态与持续失败排除。活动取消增加记录字段后同步测试替身并执行最终同组回归，14项通过；没有新增重复测试框架。它们不是实机测试或全仓库回归；完成所需真实运行后没有再追加等价回合。

最终清单为 [FINAL_SHA256SUMS](FINAL_SHA256SUMS)，在本目录运行 `sha256sum -c FINAL_SHA256SUMS`。清单包含最终报告、补丁、实际工具、关键驱动二进制与新增原始运行/诊断证据。原 `SHA256SUMS` 和 `REVISION_SHA256SUMS` 不覆盖，原193个运行文件的保留检查在 `evidence/revision-01/original-evidence-preserved.json`，不重复扫描根文件系统或无关ns-3。

## F. 后续RL、通信与实机接口

本轮仅形成边界说明，不实现RL适配层或ns-3桥接：

| 数据流 | 后续处理边界 |
| --- | --- |
| 机器人本地scan/SLAM/odom/TF/costmap/Nav2/cmd_vel | 保持本地导航闭环 |
| 各机位姿、任务状态、局部地图/增量、必要坐标标定/定位 | 未来通过受约束无线交付到中央；中央只能使用已收到版本 |
| 中央Frontier | 中央从已交付地图生成则内部使用；若改为机载提取后上传，则也计入通信 |
| 高层目标、接受、反馈、结果、取消/重分配 | Action上下行均须纳入交付约束，不能只限制地图而让Action走理想旁路 |
| Gazebo真值、参考地图 | 评估与未来网络节点位置更新专用，不作为未通信的策略状态 |

RL替换任务选择，复用SLAM/融合坐标合同及Nav2目标执行，不输出cmd_vel。训练/验收后再冻结观测处理、输入输出语义、权重及决策规则；通信研究不得暗中更换分配器。

实机主要未解决项：初始相对位姿实测和漂移下地图对齐；真实底盘/雷达/TF标定；Nav2几何和动力学适配；本地安全停止与失联保护；真实时间同步、DDS/Action跨机交付；仿真与实测差异。当前固定标定和有界冒烟不能代替这些工作，也没有证明实机可靠性。

## G. 最终验收与本地Git状态

| 项目 | 结论 | 证据与未验证范围 |
| --- | --- | --- |
| SOURCE | **PASS** | 固定上游、来源/许可、修改版SLAM、算法与接口清楚；不声称嵌入fork历史完全可追溯 |
| BUILD | **PASS** | 五个官方必要包及独立驱动包真实构建、发现并运行；未验证干净机器全量rosdep流程 |
| 三机器人RUNTIME | **PASS（本场景有界链条）** | 新版三台scan/odom/TF/SLAM/融合/Frontier/Nav2/真实运动在同一正式回合闭合 |
| BASELINE SMOKE | **PASS** | `baseline-fixed-01`达到180秒、逐台成功/反馈/再分配、地图变化、无记录安全异常、可信停止与完整证据 |
| 安全停止与活动取消 | **PASS（本轮条件）** | 动态诊断、正式收尾与三台活动Frontier目标取消均真实停止；不承诺所有故障/实机工况安全 |
| BASELINE TASK | **未验证** | 无覆盖分母、自然终态及可靠重复任务证据 |
| 下一阶段 | 可提交独立验收并作为后续研究基座 | 本轮停止开发，不自动开展RL、ns-3或新运动实验 |

本地修改均在独立 `base-01/review-corrections` 分支，运行版本已提交且运行期间工作树干净；最终文档提交完整SHA及状态见 `evidence/final/delivery-identity.json`。`upstream/`原版保持干净，历史失败保留，没有远程推送、破坏性清理或覆盖用户旧研究文件。未实现/训练RL、未启动/接入ns-3、未进行实机操作。最终PASS仅指本轮所要求的传统基座有界冒烟，不是整个长期研究项目完成。

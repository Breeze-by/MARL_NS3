# BASE-01 独立预审处置与离线修补交接

## 当前结论与授权边界

本次响应 [独立预审 R1–R8](../reviews/BASE-01-20261104-preliminary/REVIEW.md)，并落实监督方随后指出的“不连通 Frontier、连续 ABORT、局部 Nav2 地图范围”问题。

**维持整体验收 BLOCKED。** 已修补的代码和离线通过记录不等于动态停止或新系统运行通过。run-03 的运动结束后残余速度仍是未闭合的真实问题；本次没有新的 Gazebo 启动、导航目标、取消/速度指令、物理参数调试、自主探索回合、RL 或 ns-3 工作。构建和测试均不启动机器人节点。

原预审采集于 16:58 的中间状态。其中“当时尚未取得完整构建/运行证据”成立，但不适用于后来完成的原交付：run-03 已有 tb1/tb2/tb3 分别 1/5/7 个成功目标及真实运动，原报告也明确写为 BLOCKED，未将其冒充整体验收 PASS。这些后续事实不能反驳预审中的源码反例。

## 固定身份与原件保留

| 对象 | 固定方式 |
| --- | --- |
| Econ 上游 | `9825c57f83c2bfb52790cb55b51d30009cbb346f`，原版 `upstream/` 未改动 |
| 原交付源码与工具 | 新增本地提交 `6ace727938f3e1ede3887e2c921855dc785034a1`，分支 `base-01/reproduce`；包含当时实际源码、工具副本、原报告及原 SHA256 清单 |
| 本次修补 | 独立分支 `base-01/review-corrections`；完整修补 commit、tree 和报告/工具身份见 [identity.json](evidence/revision-01/identity.json)，不只引用上游 HEAD |
| 原始运行 | `evidence/run-01/`、`run-02/`、`run-03/` 和对应 supervisor 日志保持原样；与原清单比较结果见 [original-evidence-preserved.json](evidence/revision-01/original-evidence-preserved.json) |
| 新证据 | 仅写入 `evidence/revision-01/`；本次清单为 [REVISION_SHA256SUMS](REVISION_SHA256SUMS)，不覆盖原 `SHA256SUMS` |
| 工具实际入口 | `base-01-econ/tools/`；Git 内的 `workspace/base01/tools/` 是逐文件相同的固定副本，供身份复核，入口脚本仍从项目根 `tools/` 使用 |

原 `REPORT.md` 保留为旧版运行报告。原报告关于“当时未创建本地提交”的陈述是历史状态，本次已补建上述原交付提交和修补提交。没有远程推送。

**旧 run-03 只对应原交付版本。** 新版已经更改里程计来源、地图对齐、融合语义和候选合法性等行为，因此不能拿旧回合证明新版运行，也不能混用为同一算法/通信条件下的公平比较。

## 动态停止根因分析与最小方案

### 已有证据与仍未知的部分

run-03 中取消与三套 Nav2 暂停成功，之后未记录新的非零 cmd_vel；最后三秒 tb1 仍有最高约 0.0909 rad/s 的角速度，tb3 仍有最高约 0.01147 m/s 的线速度。零命令的驱动端接收和实际轮速未记录，不能仅凭这些日志排除传输、执行端或物理模型原因。

本次没有放宽线速度 0.01 m/s、角速度 0.03 rad/s、连续 1.5 s、仿真推进及 12 s 观察窗口。物理暂停也没有被改称为刹停。原动态停止结论仍为 FAIL。

### 差速插件的组件级反例

当前隔离环境中的插件包为 `ros-humble-gazebo-plugins 3.9.0-1jammy.20260915.221351`。保存了实际 `.so` 的 SHA256 和 `OnUpdate` 反汇编，见 [plugin-identity.sha256](evidence/revision-01/plugin-identity.sha256) 与 [diff-drive-OnUpdate.disassembly.txt](evidence/revision-01/diff-drive-OnUpdate.disassembly.txt)。反汇编可见 fmin/fmax 后对旧指令状态做累加，与保存参考源码中的加速度分支相符；这不是对完整二进制与参考源码逐行等价的证明，也不能补造 run-03 的 `/proc/.../maps` 记录。

`base01/tests/driver_accel_counterexample.cpp` 直接嵌入保存参考源码中加速度更新块，使用普通 C++ 关节替身执行，不加载 ROS/Gazebo。从零内部状态出发，以有限目标/测量输入到达如下情况：

1. 请求的轮速已经为零，实测轮缘速度 0.009 m/s 进入近目标分支，输出零，但内部指令状态仍约 0.06667 m/s。
2. 下一步实测为 0.011 m/s，仍请求零，进入累加分支后反而输出约 0.05567 m/s。
3. 将累加基准改为当前测量并在近目标分支同步内部状态，候选计算在该例输出零。

结果见 [driver-counterexample-02.txt](evidence/revision-01/driver-counterexample-02.txt)。这是**确定的组件状态不一致反例，不是 run-03 唯一或主要根因的证明**；给定测量序列不是从旧回合轮速记录恢复的。

最小候选方案保存在 `workspace/base01/proposals/diff-drive-state-sync.patch`：近目标分支同步状态，其他分支以测量值加限幅增量，保留原加速度上限。**提案未应用、未构建替换驱动、未改已安装插件或 max_wheel_acceleration/摩擦/扭矩参数。** 在没有新的针对性执行端证据时，不将它升级为已修复物理停止。

为后续获准的专门停止验证，监督工具增加了零命令发送记录、零命令话题观察及 joint_states 位置/速度字段记录。话题观察明确不称为驱动确认；若 joint_states 不提供 velocity，将记录空字段而不是伪造轮速。这些新增观测尚无运行验证。本次未因此追加实验。

## R1–R8 逐项处置

### R1 停止证明使用缺失机器人的旧状态

**接受，代码修补与离线反例排除通过，动态停止运行仍未通过。**

`Observer.models()` 记录当前消息真正包含的目标机器人集合，删除缺失机器人的旧位置；三台都出现后再发生缺失会置为 hazard。每台 model_state 单独记录新鲜度，非有限状态不进入有效位姿。

`stop_motion()` 只有在当前三台均存在、每台观测新鲜、出现新的完整状态样本、速度全部合格、稳定期内仿真继续推进时才写 observed_stop。缺失、断流或异常会重置稳定期。零命令发送限制为 20 Hz，避免原紧循环反复发布干扰观察；此修改不被用来解释或宣称修复旧回合残余运动。

离线测试拒绝缺失 tb3、停止消息更新、冻结时钟和 0.091 rad/s 残余转动；真正完整且持续静止的替身序列才通过。

### R2 坐标合同与真值里程计

**接受；显式合同已实现并离线验证，实机标定和新版运行 NOT VERIFIED。**

- Waffle SDF 显式选 `odometry_source=0`，使用轮式编码器积分，不再隐含 WORLD 默认值。
- 主 launch 的场景声明初始位姿作为 `merge_map ← 各机器人初始 map` 的固定标定，传给融合器，并在各自隔离 TF 话题发布真正的共同坐标→map 静态边，替换无实际对齐意义的全局前缀零变换。
- 这是已知初始位姿的**仿真场景标定假设**，不是自动配准算法，也不是已完成实机测量。实机必须提供外部标定/定位得到的初始相对位姿；本轮没有为它编造标定精度或可靠性。
- 融合器要求显式 map_poses，不默认将不同本地图等同；同时处理地图 origin 的平移、旋转及不同分辨率。
- 中央控制器保留每台独立 TF buffer，按 odom 消息时刻把位置转换到 merge_map；缺少变换就不用该位姿，不回退到原始 odom 或 `(0,0)`。
- 目标从 merge_map 变换到各机器人 map 后发送，目标朝向也随坐标变换。原 SLAM 的轴对齐地图 origin 补上有效单位四元数。

非零平移/旋转、非单位 map→odom、逆向目标变换、旋转地图 origin 和不同分辨率均有离线用例。Launch 参数归一化检查确认标定数组被解析为 double tuple，未启动节点。

### R3 自由格覆盖后续障碍与无效四元数

**接受，代码与离线用例通过。**

融合改为将每个输出栅格中心逆投影到对应源格，再对已知占据值取最大值；未知值 -1 不压过已知，自由值不能覆盖更高的占据证据。该规则显式且与输入顺序无关。输出 origin 为单位四元数，header 深拷贝，不再修改源图 header；采用最旧输入时间戳保守标记融合信息年龄。

自由/障碍/未知/中间概率、反序输入、旋转和不同分辨率均已检查。中心采样是明确的栅格重采样规则，不是障碍面积包络或碰撞安全证明；真实融合与 Nav2 联合行为仍需另行授权验证。

### R4 递归溢出与工作线程静默死亡

**接受，等价实现修复。**

保留八邻域和原 DFS 遍历顺序，改用显式栈。1200 格连续边界可以完成；12 组固定随机种子的短边界与原提交逐组、逐点顺序一致。

工作线程异常记录明确的 worker_error，关闭当前 ROS context；main 对异常退出和 spin 正常返回两条路径都检查该错误，非零退出，使原监督器能识别控制器失败。这是线程故障传播，不引入新的分配算法。离线验证注入异常后的错误状态与 context shutdown 请求，未宣称验证了真实 ROS 子进程退出时序。

### R5 凹边界质心、不连通与局部 Nav2 范围

**接受；最小合法性检查已补，真实规划可达性 NOT VERIFIED。**

原 `组大小 / 到组质心的栅格距离` 评分和最大距离、前五组规则保留。组代表点改为该组中接近原质心、在膨胀后自由空间与机器人连通的实际 Frontier 单元中心，连通检查不穿越对角障碍角点。

发送前再检查变换后的目标落在该机器人最新局部 map 的范围内且是已知自由格；未知、占据或图外目标不发送。中央新增订阅各 `/tbX/map` 仅服务于这一边界检查，尚无本轮运行证据。

离线验证 U 形边界的障碍中心、不连通自由区、对角角点、局部占据格和图外目标。**共同地图连通与局部图内自由并不等于 Nav2 可规划**：动态障碍、costmap 膨胀、局部图更新及导航参数仍会导致失败。run-03 的图外目标错误属于旧版本，不能拿新版离线检查当作已复现排除。

### R6 VISITED、持续失败与自动覆盖保存

**接受；状态与记录语义修补，真实闭环 NOT VERIFIED。**

候选选择只作 ASSIGNED 预留，成功才进入 VISITED 和 last_successful_targets。服务器不可用或坐标信息暂缺释放预留；取消释放但不冒充已探索；ABORT/拒绝记入各机器人独立 FAILED，并在该机器人本回合排除其近邻，避免每 8 秒重选同一失败目标。其他机器人不因此被全局禁止尝试。

这是一种明确但保守的有界回合失败处置：地图后来变化后也不会自动重试该机器人已失败的位置，可能留下未探索区域，不应声称已解决完整任务完备性。没有加入新的评分、重试优化或路径分配器。

共享地图元数据、位置与预留判定使用同一个锁，避免混读地图版本和重复预留。原三探索线程架构保留。接受日志包含 Action UUID。

删除“全部 idle 就认为探索完成并保存到源码固定文件”的路径；控制器不再自动写 src/saved_map。快照由运行监督器写到拒绝覆盖的新回合目录。没有为本轮新增自然终止/覆盖率算法。服务不可用、拒绝、成功、ABORT、取消、持续 ABORT 不再重复同目标均有离线用例。

### R7 冒烟与稳定系统验收边界

**接受缺陷；反驳将旧交付解释为已冒充整体验收 PASS 的推断。** 原报告明确 BLOCKED，且本轮不改变这一结论。

工具分别记录 simulation_budget 和 wall_timeout，未达到请求仿真时长不通过；运行中持续检查每台 scan/odom/map/contacts/model_state 的新鲜度及关键节点/TF。自主区间开始时重置运动、Action、反馈与地图变化计数，不混入启动前表现。

冒烟布尔值进一步要求每台有成功终态和反馈；全 ABORT 或墙钟超时反例均被拒绝。这个布尔值仍不是完整探索、稳定性或实机安全认证。未运行新版回合，也未重写旧 result.json。

### R8 依赖元数据

**接受，元数据、导入和构建已修正；全新 rosdep 安装仍 NOT VERIFIED。**

探索包声明实际 ROS/TF/消息和 NumPy 依赖，移除原未使用的 SciPy 等 import，不为无用 import 安装新依赖。融合包把 exec_depend 移到正确的 package 层级，补 NumPy 与 launch 依赖。multi_robot 补实际入口需要的包，删除源码未使用且可能间接拉入系统 SLAM 的 turtlebot3_navigation2 依赖。

XML 检查和当前隔离环境的真实导入/构建通过。尝试 rosdep keys 时发现原隔离环境未初始化 rosdep 数据库，原错误保存在 rosdep-keys.txt；本次没有为此扩大为全新依赖安装或初始化主机配置。不能把已有环境构建成功说成已验证上游原 rosdep 流程在干净机器上完整成功。

## 与原始任务限制的冲突及处理

| 原任务限制 | 本次处理 |
| --- | --- |
| 保留原探索策略，不为覆盖率改算法 | R4 是顺序等价的实现修复；原组评分公式保留。R5 的合法代表点/连通性、R6 的失败排除、R3 的占用冲突确实改变行为，按监督授权的正确性修补单独版本化，不冒充原版复现或覆盖率优化 |
| 不提前重构中央控制架构 | 仍为原 HeadquartersControl、三探索线程和 Nav2 Action；只修坐标、共享状态与失败处理，无 Policy 层、联合优化器或学习模型 |
| 不大改 SLAM/Nav2/Gazebo | SLAM 只补地图 quaternion；Nav2 源码未改；驱动补丁只提案未应用，物理参数未调 |
| 本轮最多一次正式自主回合 | 原 run-03 已消耗该授权；本次零新增回合，源码运行状态保持未验证 |
| 保留历史证据 | 原件不写入，原交付与修补分别提交，新增证据另目录保存 |

若验收要求“传统基线算法输出完全不变”，应使用原提交 `6ace727...` 并保留其缺陷与 BLOCKED 状态；本修补分支只能称为 Econ 架构下的正确性修补版本，不能同时宣称逐动作等同上游。评分保留不意味着所有行为保持不变。

## 实际验证及未验证范围

```bash
# 无 ROS 节点或 Gazebo 运行，只导入消息类、执行生产方法与替身。
tools/in-rootfs.sh -c 'source /opt/ros/humble/setup.bash; python3 /project/workspace/base01/tests/test_review_fixes.py'

# 普通 C++ 程序，原参考源码更新块的组件级反例。
c++ -std=c++17 workspace/base01/tests/driver_accel_counterexample.cpp \
  -o evidence/revision-01/driver_accel_counterexample
evidence/revision-01/driver_accel_counterexample

# 编译不启动 Gazebo/ROS 节点。
tools/in-rootfs.sh -c 'source /opt/ros/humble/setup.bash; source /project/workspace/install/setup.bash;
  cd /project/workspace; export MAKEFLAGS=-j8 CMAKE_BUILD_PARALLEL_LEVEL=8;
  colcon build --symlink-install --packages-select slam_toolbox merge_map multi_robot_exploration multi_robot \
    --parallel-workers 2 --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release'
```

- [offline-tests-03.txt](evidence/revision-01/offline-tests-03.txt)：14 项离线检查通过。
- [build.log](evidence/revision-01/build.log)：4 个变更包构建成功，92 秒左右；未跑无关全仓库回归。
- [config-check.txt](evidence/revision-01/config-check.txt)：既有配置/Action 静态检查通过。
- [launch-parameter-check-02.txt](evidence/revision-01/launch-parameter-check-02.txt)：标定数组参数解析通过。
- 初版离线测试有 ROS array/list 比较和隔离路径 Git 访问的测试替身错误，修正后通过；首版参数探针未先 normalize 参数也报错，均保留原记录，不将其当作生产系统故障。
- 后加的零命令/关节观测只做源码语法检查，没有真实运行，也没有为此重复扩大整套测试。

**必须继续保留的 BLOCKED/NOT VERIFIED：** 动态停止真实根因及修复效果、新版编码器/已知初始位姿合同的真实联合运行、实机标定可靠性、实际融合正确性、Nav2 规划可达性及新失败处置的任务效果。14 项离线通过和 4 包构建不解除这些条件。

本次交回独立复核，不自行宣布 ACCEPT，不进入 RL 或 ns-3，不自行扩展运行授权。

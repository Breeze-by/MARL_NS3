# 第二次工程定版 v2.0.0｜ROS 直连多机器人导航底座

本版固定后续通信研究使用的 ROS 直连 A0 导航参考。三台 TurtleBot3 在 Gazebo 和 ROS 2 中运行，中央沿用 `MR3-RL-POLICY-v1.1.0` 的训练权重和 701 维观测结构来分配探索目标，由各机 Nav2 执行路径规划和运动控制。发布标签为 `MR3-NS3-INTEGRATION-v2.0.0`。[固定策略源码标签](https://github.com/Breeze-by/MARL_NS3/tree/MR3-RL-POLICY-v1.1.0) · [第一次工程定版](https://github.com/Breeze-by/MARL_NS3/releases/tag/MR3-NS3-INTEGRATION-v1.0.0)

## 导航改动

1. 三机各自在本机 SLAM 地图上完成第一个真实导航目标后，地图节点开始分发融合导航地图。各机 Nav2 独立接收各自的地图，中央收齐三张带切换标记的地图后才在候选筛选中使用它们。原始 SLAM 图继续支持保护和独立评价。
2. 新候选目标的起始 0.442 m 路径与邻机当前持有目标对应的有效 Nav2 剩余路径比较，沿用 0.55 m 净空门。局部避障、Nav2 碰撞保护和 Goal 停止链继续生效。
3. 若起点连接因找不到可信路径而失败，且已有通过验证的自体栅格排除，中央使用应用该排除的私有净空图重试。原发布地图和各机 Nav2 代价地图继续使用原数据。

第三版已在 Open1704、Open1703 和 Corr1703 分别达到 T95 111.53、109.45、52.90 仿真秒。其 Rooms1701 轮次末覆盖 91.0096%。第四版在同场景另一次实跑以 93.48 仿真秒达到 T95。该轮的 63 次起点检查均未触发重试。独立回放用原 Rooms1701 的 SLAM、代价图、邻机路径和候选状态，复现了同一机器人 17 个调度槽的阻塞。修复使每个槽从 0 个合法候选恢复为 5 个，回放未产生新的动作或覆盖记录。[定点修复和回放证据](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v2.0.0/docs/releases/ns3-integration-v2.0.0/EVIDENCE.json)

## 固定第四版的两个新种子验证

各场景保持原出生位置和 120 仿真秒预算。主指标为从自主窗口起点算起，中央质量有效覆盖首次达到 95% 所需的仿真秒数。

| 场景 | 物理种子 | 实际运行 | 中央 T95（仿真秒） | 中央末覆盖 |
|---|---:|---|---:|---:|
| Rooms6101 | 2026111801 | t1s | 109.13 | 98.9146% |
| Rooms6101 | 2026111802 | t6 | 104.05 | 99.8328% |
| OpenRing6301 | 2026111801 | t2 | 未达 | 80.5856% |
| OpenRing6301 | 2026111802 | t4 | 96.51 | 99.9460% |
| Corr6201 | 2026111801 | t3 | 75.53 | 99.8843% |
| Corr6201 | 2026111802 | t5 | 99.21 | 99.8265% |

**7 次实际启动、6 个独立合格窗口，5 个达到 T95，1 个完整窗口未达。** 原 `t1` 在进入自主窗口前遇到 native IPC 启动超时，恢复后按原地图和种子执行专门命名的 `t1s`。两次启动各有独立记录。六轮均通过原停止、Goal UUID 终态闭合、证据复制和资源退出检查。六轮共接受 80 个目标，其中 62 个成功，6 个由进展保护取消，1 个由 Nav2 中止。10 个在原记录中已确认预算取消，另 1 个随后以原生 Action 状态流确认属于预算取消。私有起点图重试触发一次，未产生连接。[六轮、失败与补充记录](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v2.0.0/docs/releases/ns3-integration-v2.0.0/EVIDENCE.json)

两个种子支持把当前实现用作固定导航参考，OpenRing 仍有未达标记录。完整窗口和零自主窗口启动失败分别计数。前期不同版本的定点运行单列，后续比较使用同一导航和评价合同。

## 配置与下一阶段

以发布的 READY 字段片段新建本机工单。A0 使用 `network.mode=A`、`network.direct_reference=true` 和 `network.ros_delay.condition=A0`。在片段指定的执行配置中，通过 `network.navigation_shared_map.revision=a0-shared-navigation-active-route-v3` 与 `network.navigation_seed_route.revision=a0-approved-shared-seed-route-v1` 共同选择内部第四版。仓库原场景模板标注 600 仿真秒和 130 次决策。生成新场景时应用片段中的 120 仿真秒和 23 个决策槽覆盖，READY 的 `decision_limit` 仍为 130。片段保留原场景入口、模型身份和时钟预算，实际执行还需要本机 ROS/Gazebo 和原生环境、构建产物及当前 source/READY 绑定。发布包含源码和紧凑证据，原始包和本机运行目录另存。[配置片段](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v2.0.0/docs/releases/ns3-integration-v2.0.0/NAVIGATION_PROFILE.json) · [本机环境](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v2.0.0/docs/LOCAL_ENVIRONMENT.md)

融合导航地图和有效路径检查在本版仅有 ROS 直连观测与验收。下一阶段的匹配 ns-3 通信比较需要在各条件保持等价导航行为和输入语义，并把该条件所需的业务输入实交付给同一消费者。离线真值用于评价。原通信集成、延时和导航试验按各自合同保留。此发布的结论限于记录的 ROS 直连场景、预算和种子。

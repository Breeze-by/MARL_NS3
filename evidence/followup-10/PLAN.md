# Followup-10：固定原DWB的三图复核

用户要求“再多测试几张地图”。本轮只评价固定09运行源76fd/6d模型；不改源码、不训练、不调参。09全部成功/失败、报告和独审不改。当前0/6新实际Gazebo，历史77，最多累计83；每例须独立具体READY，失败也计数，不自动重试或换图。

## 事前固定资源与顺序

三图均为**已暴露固定回归/跨图复核**，不叫新盲测；Hard4202还属于历史训练几何。下表在任何本轮成绩出现前锁定，选择依据为已有合法资源、类别覆盖和已知困难结构，不根据新成绩筛选。

| 顺序/预计累计 | 地图/几何 | 算法 | 可达参考分母 | 共同区三机XY，yaw均0 |
|---|---|---|---|---|
| 1/78→2/79 | Corr6201 / branching_corridors，51个身体高度box | RL→兼容传统 | 15558格 / 38.895m² | (.725,-.15),(.35,-.8),(1.10,-.8) |
| 3/80→4/81 | Rooms6101 / partition_grid，20个box | RL→兼容传统 | 40076格 / 100.19m² | (-3.4237836473654566,-3.581773649437976),(-3.7987836473654566,-4.231773649437976),(-3.0487836473654566,-4.231773649437976) |
| 5/82→6/83 | Hard4202 / 另一已知困难corridor结构，53个box | RL→兼容传统 | 15111格 / 37.7775m² | (.725,-2.125),(.35,-2.775),(1.10,-2.775) |

精确浮点坐标、world/scene身份、历史资格出处与实际碰撞矩形见 `RESOURCE_LOCK.json`。三图的物理box结构彼此不同，也都不同于Open6301，不把换seed标签当几何差异。Rooms面积约为另两图2.6倍，时间/路程逐图成对报告，不用跨图简单平均掩盖尺度差异。

共同区沿已有相对三角：tb2相对tb1(-.375,-.65)，tb3(+.375,-.65)，最小中心距离.75m，三实体不重叠；不是同一xyz。已有.25实体/实际.55 mask、参考分量/封闭边界资格复用，不运行新策略或用性能选起点。clearance列的是中心距，实体净空需减.25；own seed peer=-1代表输入mask跳过，不是最终costmap未知。Spawn和merge/TF继续由同一scene robots驱动，不改校准。

## 固定系统与公平比较

- worktree `workspace/`，branch `gz-01/followup-10`，HEAD77cb847文档交付；相对76fd只多09两份归档文档，运行代码固定 `76fd91cf937bd8d662302901dad063affbea3c38`，源码身份直接复用09实际准入。见 `FIXED_SOURCE_BINDING.json`。
- 6d checkpoint及原summary/process-exit/selection完整复用，见 `INHERITED_INPUTS.json`。无模型筛选/改权重/训练/额外NN回放。
- 三scene明确 `rotation_shim=false`（原 `dwb_core::DWBLocalPlanner`）、`peer_timing=false`，READY `observer_timing=true`，两算法完全相同。这避免已知可选peer时序归档缺陷，不宣称已修复该缺陷或发布调度间隙。
- 同一地图两臂共享world/spawn/physics seed/感知/Frontier/最大参与/路由/目标校验/Nav2/SLAM/物理/时效/停止/计时/指标。传统是兼容打分+共享执行合同，不冒称完整BASE01逐byte不变。实际初扫地图与DDS调度不保证完全相同，不能将一次配对差异都归网络权重。
- 原Quick50/slip1e-5、SLAM fine=.75及粗跳INVALID、.25实体/peerR.55/中心monitor.30/goal.80/idle.55、E2E source.4/correctionheader.55sim/receipt.2wall/heartbeat.3wall、future边界和全部原停止规则不动。
- 每例600sim/130decision；startup180、autonomy1400、outer1800、cleanup90wall；原Nav2 progress .5m/10s与90sim任务保护不变。自然终态仍None，预算退出不冒充自然完成。

## 执行条件与失败处理

六个 `.draft.json` 均无执行授权，root审配置后签具体READY。固定顺序见资源锁；每例开始前，前件原stop/UUID闭合/三pause/完整性、实际fine.75、无fatal/hazard/INVALID/持续坏图且末图质量有效，唯一metric/记录封存，全部owned与重计算退出。任何真实fatal、安全、停止或主要保存缺陷先暂停剩余，交root按原事实决定，不重试/悄换图；普通Nav失败、低覆盖或参与差不删除健康固定对照。

主期只被动读取既有日志，不活动bag/SQLite/重型计算。完成后每例原metric工具只提取一次，复用CSV绘曲线与三机轨迹。阈值未达写未达/null，不填0；零NN/零目标启动失败不写算法覆盖0，也纳实际启动成功率。

## 交付与停止

逐图表：quality有效T90/T95/T98、末correct-free覆盖、地图precision/质量、95与全期三机路程、成功及rawA/timeoutC高层失败、95前后失败/闲置、原停止/UUID、退出原因与初始观测/首决策时点。实际forward与非强制选择机会分列；不以转发数或高覆盖单项宣称稳定RL领先。

三图均已暴露，结果只能扩大固定执行系统的有限跨图证据，不冒称未见几何泛化/正式冻结或部署。无ns-3、实机、push；不引入新优化。六次最多，任何未运行原请求保留NOT RUN。报告、原件/新必要身份和本地文档交付完成即停止。

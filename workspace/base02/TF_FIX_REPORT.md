# BASE-02 TF就绪修复与最终运行验收报告

**本轮补充回归通过，BASE-02整体判定GO，范围为中央分配接口和有界传统探索闭环。** 已定位并复现静态TF读端历史配置缺陷，修复后真实运行新中央控制器180秒仿真，三台分别完成3/5/2个Nav2目标，均有成功后再分配、物理运动、SLAM/融合地图变化及可信静止退出。没有训练RL、接入ns-3、优化探索评分或开始RL-01。

真实Gazebo训练/reset后端、完整探索任务与实机部署仍未完成，不因本轮GO改变这些边界。

## 1. 固定版本、隔离与历史保留

| 对象 | 身份/路径 |
| --- | --- |
| Econ上游 | `9825c57f83c2bfb52790cb55b51d30009cbb346f` |
| 已验收BASE-01 | `12b366564842fbc98de57e0fc679a9b22d125543`，`../base-01-econ/`，原工作树保留 |
| BASE-02首轮NO-GO交付 | `3eef0e177400fa00085caccbde43ebd2cf9d3cd8`，`../base-02-central/`，不改原报告/清单/失败数据 |
| 本次修复及真实运行 | **`692b437d4d63a16a7ba58a091c5612469d0aa62e`** |
| 本次工作区/分支 | `base-02-tf-fix/workspace` / `base-02/tf-readiness-fix` |
| 最终文档提交 | 完整SHA见[evidence/delivery-identity.json](evidence/delivery-identity.json)，与运行提交区分 |

首轮[NO-GO报告](../base-02-central/REPORT.md)及[原SHA清单](../base-02-central/SHA256SUMS)原样保留，其SHA分别仍为`d0f59c31573a3f1f49ab4a740e8e130484d09e95d389b992ff68c70425f1c49b`、`5e38f2f1428b3d517303a90957550ccfa9108352e1237eec4a3254d2dfc1d008`；见[保留记录](evidence/initial-delivery-preserved.json)。不把本次成功改写为首轮成功。

使用原Ubuntu22.04/Humble/Gazebo Classic11环境。BASE-01 rootfs和工程只读，原产物挂载`/project`；本次工程挂载`/mnt`，仅PYTHONPATH覆盖中央Python包。ROS域62、Gazebo端口11662、Xvfb62，home/tmp/日志独立。本轮没有重编底座或安装依赖。

## 2. 原失败与已证实的队列缺陷

首轮在240秒启动前置窗口结束时，主Observer无法完成tb1 `map→base_scan`，新中央未启动；晚加入只读探针三台均可转换。实际安装的Humble Buffer没有自动时钟jump/clear注册，原先时钟清缓存猜测已排除。

实际源码显示，原Observer和新中央把局部地图的`TRANSIENT_LOCAL depth=1`复用到`tf_static`。每台该话题有两个独立静态发布者：robot_state_publisher的机体/雷达静态链，以及`merge_map→map`标定。Humble标准TransformListener的静态订阅使用`KEEP_LAST / TRANSIENT_LOCAL / depth=100`；源码保存在[installed-transform-listener.py](evidence/installed-transform-listener.py)。

在**真实rmw_fastrtps_cpp**中进行最小DDS测试，使用domain63、独立`/base02_tf_history_fixture/`话题和diag帧，没有Gazebo、机器人话题、目标或速度指令。两个发布者的消息均取得可靠ACK：

| 订阅配置/处理时机 | 接收静态消息 | Buffer完整变换 |
| --- | --- | --- |
| 原depth1，两个消息到齐前不spin | 仅最后1条，机体/雷达静态链被覆盖 | false，base_scan不存在 |
| 原depth1，消息之间及时spin | 2条 | true |
| 标准depth100，相同积压时机 | 2条 | true |
| 修复后从实际Observer配置读取profile | 2条 | true |
| 修复后从实际控制器配置读取profile | 2条 | true |

可靠传输ACK不表示应用回调已消费；读端KEEP_LAST=1仍会覆盖未处理的上一条。静态消息一次发布后不会为了此应用缓存缺边自动补发，而晚加入/及时处理的读者可以正常，这与首轮观测相容。

完整复现见[tf-history-reproduce.json](evidence/tf-history-reproduce.json)，实际生产配置定向验证见[tf-history-fixed.json](evidence/tf-history-fixed.json)。独立评审另在只读rootfs和隔离网络环境复现相同结果。初次测试topic token以数字开头的命名错误保留在`tf-history-before.stderr`，它不是假设结果；修正命名后才取得有效证据。

**已证实并修复的是该真实队列配置缺陷。首轮没有保存主Buffer接收细节，不能逐包证明当时具体丢了哪条边或声称历史唯一原因。** 本次修复后的冷启动主Buffer证据与实际闭环同时通过，关闭原运行阻断。

## 3. 最小修复及不变边界

- Observer和HeadquartersControl各设置独立静态TF profile，depth100；局部地图profile仍为depth1。
- Observer记录静态/动态消息计数，在就绪或失败时保存真实Buffer帧图、接收边与`can_transform` debug tuple。
- 没有重发/伪造TF，没有更换TF来源，也没有用探针结果代替主Buffer放行。

`ready`、`stop_motion`、模型/接触监督、生命周期及恢复函数AST与首轮相同；Frontier/评分、任务分配、训练合同和评价模块没有变更。证据为[unchanged-contract.json](evidence/unchanged-contract.json)。world、模型、Nav2、修改版SLAM、融合器和驱动均复用BASE-01原产物。

定向DDS测试直接从实际代码读取静态profile，并核对tf_static订阅确实使用该profile，而非仅测试一个孤立的常量。既有23项独立合同测试属于首轮固定接口；本轮未重复无关整套，验证集中在真实TF接收和本次实际运行。

## 4. BASE-02接口交付范围

完整[状态/动作/生命周期/奖励与评价合同](CONTRACT.md)保持`base02-v1`。核心模块仍为：

| 模块 | 职责 |
| --- | --- |
| frontier.py | BASE-01膨胀、Frontier提取/分组/顺序与连通检查 |
| allocation.py | traditional/外部rl/test选择器，冻结快照、候选/掩码、KEEP/WAIT、任务token/UUID及共同合法性校验 |
| control.py | ROS地图/odom/TF输入、目标坐标转换、同一Nav2执行与反馈/终态入口 |
| environment.py | reset/get_observation/get_action_mask/step/奖励分量/终态/异常停止合同 |
| evaluation.py | 统一事件指标、独立快照、相同评价时间区间与离线物理轨迹/覆盖接口 |

传统给定输入的选择已与冻结原实现做40组对照，保留候选顺序、平分、历史/预留/失败和last_target语义；仍按每机8秒墙钟检查。三模式共享同一检查/执行边界。rl仅为显式外部predict接口，无模型时明确报错，不回退传统或伪装训练；ROS自主入口本轮只允许traditional。

观测来自共享已知图、真实可获得的odom/SLAM/TF、候选与任务状态，保留版本/时间/来源；候选索引绑定快照。安全门控、重复抑制、活动任务保护、冲突检查、迟到结果所有权和可检测等待均保留。输出高层目标，不输出速度。独立参考/Gazebo真值仅用于评价，不进入策略观测。

## 5. 实际补充回归

独立前置复核通过后，先固定提交和事前身份，再执行以下已完成命令；原目录存在时拒绝覆盖，本轮不追加回合：

```bash
cd /home/zhuyulab/ns3-workspace/base-02-tf-fix
set -e
python3 tools/capture_case_identity.py evidence/traditional-tf-fixed-01.identity.json \
  --driver libbase01_diff_drive.so --kind base02_traditional_regression
tools/in-rootfs.sh --baseline-runtime /mnt/tools/run-baseline.sh \
  /mnt/evidence/traditional-tf-fixed-01 --sim-seconds 180 --wall-seconds 420
```

主Observer `tf_preflight_ready.json`三台debug均为`[1,""]`，各接收2条静态消息，实际帧图/边齐全；未再进入240秒前置超时。源码身份来自实际新中央的`implementation_identity`事件，五个模块逐个匹配692b提交；不是只凭命令推断运行版本。

`loaded-driver.json`及`gzserver.maps`确认实际加载原验收驱动SHA：

```text
8d54d39a687de851c95137ddee4a7ebbab90c3373e07d96fad338870d4317fc0
```

正式自主区间UTC **2026-11-04 13:49:11.162368–13:52:35.957880**（北京时间21:49:11–21:52:35），sim **21.7–201.7**，**180.0秒仿真/204.795秒墙钟**，达到simulation_budget，未触发420秒墙钟上限。

| 指标 | tb1 | tb2 | tb3 |
| --- | ---: | ---: | ---: |
| 真实接受且成功的唯一Nav2目标 | 3 | 5 | 2 |
| 中央日志同区间反馈数 | 4977 | 7953 | 3886 |
| Gazebo同区间物理路程m | 6.274043 | 12.916049 | 4.666016 |
| 里程计+TF估计路程m | 6.346662 | 12.982014 | 4.727595 |
| 相对自主起点最大位移m | 4.383423 | 9.417127 | 3.242867 |
| 局部地图内容变化版本 | 11 | 18 | 8 |

10个唯一UUID逐个对应中央接受/终态和独立Action Server状态2→4及反馈。每台成功后都有新分配，任务预留/终态回放无所有权重叠，最终无活动owner。共享地图内容变化37次。运动来自Frontier目标经Nav2执行；自主区间未设置模型位姿，分配器和监督器没有直接发布非零速度。三台都持续参与。

`nodes.txt`是CLI即时发现的不完整快照，不据此宣称完整节点数，也不因快照缺项误判系统缺节点。两次15节点lifecycle active记录、全程关键节点门控、三机实际SLAM/TF/Action链共同支持运行结论。

后段共有33次WAIT记录，有效候选数为0并出现显式`stalled_wait`；最后map_changed约125.7sim。**预算停止不等于自然探索完成**。没有为改善等待、覆盖率或路径而改评分、候选或地图。

运行保留了Nav2内部告警/恢复：tb3出现DWB无合法轨迹、tb2出现规划失败及子Action abort，随后对应高层NavigateToPose均成功；另有循环频率、goal checker默认选择、LiDAR范围裁剪等告警。不能描述为零错误系统。SIGINT退出阶段的部分-2、KeyboardInterrupt和rosout关闭告警与运行中恢复事件分开保留。

## 6. 安全停止和退出

无接触事件、hazard为空，最小观测机器人中心距**3.457032m**，没有应急物理暂停。结束前所有目标已成功，本轮取消响应都是0个活动目标；**本回合没有新验证运动中目标取消**，不挪用BASE-01动态取消作为新版实测。相关新接口保护由定向合同测试支持。

沿原流程停止中央、取消、暂停各套Nav2并发零，UTC13:52:41.438939确认静止，距预算结束5.481秒墙钟、最后导航暂停后1.613秒。最后1.5秒墙钟每台14个模型样本的最大值：

| 机器人 | 最大线速度m/s | 最大绝对角速度rad/s |
| --- | ---: | ---: |
| tb1 | 0.00006505 | 0.00000328 |
| tb2 | 0.00007196 | 0.00000246 |
| tb3 | 0.00006696 | 0.00000276 |

稳定期仿真推进1.4秒，驱动新接收并消费零目标，内部/电机目标归零，符合原线速度<0.01、角速度<0.03、连续>1.5秒墙钟且仿真推进>0.5秒、12秒停止观察窗口。未放宽阈值或冻结物理。

中央和顶层launch退出码均0，回合UTC13:52:52.119730结束。运行结束快照中44个跟踪PID全部退出，Xvfb由wrapper收尾；daemon检查返回未运行。完整停止/过程数据见[runtime-analysis.json](evidence/runtime-analysis.json)、[process-exit.json](evidence/process-exit.json)、[daemon-stop.txt](evidence/daemon-stop.txt)。这不是任意故障工况或实机安全认证。

## 7. 统一评价与可视化

已用同一工具对中央事件、独立监督器和物理轨迹按**[21.7,201.7]**评价，输出[evaluation.json](evidence/evaluation.json)。高层NavigateToPose成功率1.0，分配3/5/2，取消/抢占切换/重复分配/目标冲突均0。内部Nav2恢复事件不等同高层任务失败，不能用成功率隐藏告警。

`reward_components.elapsed_sim_s=178.1`是筛选后首末中央事件的跨度，**不是正式回合180秒**；正式预算耗时来自smoke_bound/runtime-analysis。`stop_reason=null`表示该区间内无HALT事件，回合结局应读`case_end_reason=simulation_budget`，不是无结局。监督器反馈计数与中央同区间采集不同，均保留原始记录，不混用为丢包估计。

共享已知面积128.635m²、已知面积正增量117.483m²是可观测代理。没有固定参考分母，`reference_coverage=null`，阈值时间没有可用结果；重复感知面积也为null，不冒充完整覆盖或自然完成。

```bash
tools/in-rootfs.sh -c 'export PYTHONPATH=/project/workspace/src/multi_robot_exploration;
 python3 -B -m multi_robot_exploration.evaluation \
 /project/evidence/traditional-tf-fixed-01/allocation-events.jsonl \
 --observer-events /project/evidence/traditional-tf-fixed-01/events.jsonl \
 --trajectories /project/evidence/traditional-tf-fixed-01/trajectories.csv \
 --start-sim 21.7 --end-sim 201.7'
```

![融合地图和自主轨迹](evidence/map-trajectories.png)

图由保存的SLAM融合栅格及Gazebo轨迹离线绘制，共框依赖原初始标定假设；不是Gazebo/RViz截图，不替代原始数据，不输入策略。

## 8. 证据入口、SHA和提交

| 证据 | 路径 |
| --- | --- |
| 事前源码/工具/库身份 | `evidence/traditional-tf-fixed-01.identity.json` |
| 首次主Buffer就绪证据 | 回合`tf_preflight_ready.json`、`tf_edges.json` |
| 实际源模块、目标/token/UUID/终态 | 回合`allocation-events.jsonl`、`control.log` |
| 实际加载库 | 回合`loaded-driver.json`、`gzserver.maps` |
| 完整launch/ROS/Gazebo/进程/话题/Action | 回合`launch.log`、`ros_logs/`、`gazebo_logs/`、各txt快照 |
| 物理运动、执行与停止 | 回合`trajectories.csv`、`drive_diagnostics.csv`、`events.jsonl`、`result.json` |
| 初末局部与合图 | 回合各机器人/merge_map的`_first/_last.npz`和`.pgm` |
| 统计/评价/退出 | `runtime-analysis.json`、`evaluation.json`、`process-exit.json` |
| 根因定向测试与门控不变 | `tf-history-reproduce.json`、`tf-history-fixed.json`、`unchanged-contract.json` |
| 新修补diff与文件清单 | `evidence/tf-fix.patch`、`evidence/changed-files.txt` |

本次[SHA256SUMS](SHA256SUMS)及核对结果`evidence/sha256-check.txt`独立生成，不覆盖首轮清单。最终文档/证据提交SHA、分支、工作树状态、报告SHA及与实际运行代码一致性见[evidence/delivery-identity.json](evidence/delivery-identity.json)。不推送远程，不清理历史。

## 9. 最终七项判定与后续边界

| 项目 | 判定 | 范围 |
| --- | --- | --- |
| BASELINE PRESERVED | **PASS** | BASE-01原产物/参数/证据保留，传统逻辑未变，真实有界闭环通过；不承诺轨迹逐点一致 |
| POLICY INTERFACE | **PASS** | 统一状态/动作/执行、无隐式RL回退，实际traditional接入成功 |
| ACTION SAFETY | **PASS** | 共同门控/所有权接口测试通过，真实回归无记录安全异常且静止收尾通过；不是全部故障/实机认证 |
| TRAINING CONTRACT | **PASS** | 按原P5“合同语义+最小可运行测试”范围；没有生产训练后端或训练结果 |
| EVALUATION INTERFACE | **PASS** | 统一时段实际日志/轨迹和指标输出，未知覆盖保留null |
| INTEGRATION TEST | **PASS** | 新中央与三机器人真实SLAM/合图/Frontier/Nav2/反馈/再分配/运动/停止链在一次180秒回归闭合 |
| OVERALL | **GO** | BASE-02接口及有界传统回归验收，可交接下一阶段；本轮停止，不自动进入RL-01 |

首轮把TRAINING CONTRACT按“能否直接Gazebo训练”保守标BLOCKED；原任务本轮要求接口合同而非完整训练后端。本报告按该范围判PASS，**实际训练准备仍BLOCKED**，后端状态没有变化，也没有为变绿补建后端。

RL-01若另行授权，先实现并验证真实world/SLAM/Nav2 episode reset、受控高层推进及奖励标量化口径，再选择网络和训练；按合同比较ROS/Gazebo路线A与必要时的轻量路线B，不能用清Python状态假重置或泄漏全图。当前未训练/冻结RL权重、未接ns-3、未做实机部署。完整探索结束条件、长期可靠性、真实标定与实机安全仍需后续工作。

已达到本轮必要证据后停止新增修补、测试和运动回合，交回独立验收。

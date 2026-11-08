# RL-04 最终报告：本轮限定工程 GO

**本轮限定工程 GO：三头真实学习、固定36例二维任务门槛、真实Gazebo三机闭环、P2全部尝试口径及可信停止均已核验。** 这不是完整自然Gazebo探索任务或实机部署证书，没有自动正式冻结策略、接入ns-3或启动下一阶段。实际新增PPO相对同v2旧权重未证明泛化优势，两例公开困难场景仍有残留问题。独立最终签发见工作区 `reviews/RL-04/`；本报告、候选合同与实际交付commit身份按末节链接封存。

## 1. 目标、版本与研究边界

本轮在独立 `rl-04/workspace` 改善 RL-03 暴露的 P1 三机参与不足及 P2 ROS 状态可用性。父版本 `991bba0bf3a9d75ac36e1674e1510b60c560f6ee` 及旧 RL-03 源码、模型、报告和原件不改写。既有 RL-03 结论仍为任务参与未达标、冻结 NOT READY；其 Gazebo 只证明旧版本的有限工程闭环。

本轮仍属于策略定版前的开发，不是固定策略后的通信优化。RL 只分配导航目标，不输出速度；实际运行由原 SLAM/Nav2/驱动完成感知、规划和运动。未接入 ns-3、通信优化或真实硬件，不推送远程，也不自动正式冻结行为策略。

| 阶段 | 实际源码身份 | 当前证据范围 |
| --- | --- | --- |
| P2 状态修复与离线诊断 | `522ab2899f5ec273a5c183def04b46238e913421` | 精确时间 TF 失败保留最近成功状态；非实际修复后 Gazebo |
| DEV01 | `bd835083e8f4b067c79213aa361da2151229ac78` | 固定6例公开开发、原46e权重、0更新 |
| DEV02 | `a6e0fc1270d71ec97a55a6c75954a666fd4a62b7` | 固定同6例，v2目标间距，0更新 |
| 新语料物理资格 | `22a112c171753ad2e0cdd5ed21070a9272dc5a63` | 8张新几何、14组起点，0策略/步进 |
| 正式训练 | `985158a3a0fd036177fb29fc62c3e41249d89ad3` | 起止同源、native0、2048joint/64Adam/12VAL |
| 一次选模 | `985158a3a0fd036177fb29fc62c3e41249d89ad3` | native0，固定选中512/16新增Adam |
| 两公开回归 / typed Mock / 36新TEST及分析 | `9fe44e379e333409b228b3262f18c7f78ace3c85` | 均native0，见下文范围及不利结果 |
| 唯一实际Gazebo | `ed4ca13a7ba8d874b9e5cf5f06c8665868a30f95` | native0；180sim、三机真实目标/运动/地图/实测停止闭合 |

正式训练48项源码/数据锁为 `rl04/FORMAL_LOCK.json`，SHA256 `d5bd5d5fcd8752384eaa8dfdfb547679dc3f2507d7aaa5dfb50fba47b08fe2e3`，训练期间未改该48项或HEAD。TEST66项锁为 `rl04/TEST_LOCK.json`，SHA256 `2ecfdbdc42d97c66ae2048f7910b65cd133353e4fbbab10f1fe43006e1fa514c`，原9fe源和原件保留；`evidence/test-source-close-01.json`确认TEST及分析native结束时66项错配0。之后才按独立意见修正P5评估器的首次推理“完成”时刻口径，未改策略/执行层。

## 2. P1/P2 修改与已知限制

P2 保持原精确时间 TF 查询。转换失败时保留上一次成功的位姿、原始时间戳及已转换速度，仍用原2秒过期门控；不重打时间戳，不改用 latest TF，不加重试线程。子类只对新成功样本转换速度，避免重复旋转。逐机器人最近 TF 错误与计数可追踪。

`evidence/pose-bag-replay-02/result.json` 的只读重放统计19137条odom、3199次转换失败（3176 future、12 past、11其他）。在37个旧调用采样时刻，按bag记录顺序重建的可用性为旧5/37、保留成功样本37/37。**这是机制反事实；bag记录顺序不等同真实executor顺序，不能算修复后真实ROS PASS。** `retained-pose-check-02` 验证保留、过期拒绝、恢复及速度只转一次；旧01夹具/重放的不利原件保留。

P1 明确采用 `rl04_approach_v2` / `rl04-shared-frontier-approach-v2`：共享Frontier没有本机已知且局部膨胀可达端点时，可给出沿该Frontier共享已知路径、在本机已观察可导航前缀内的接近点。不是随机巡航、等参与配额或真值候选。原Frontier分组/评分不改；先做可用性/去重再保留每机最多5个。路径预算23.4m仍是90s×名义0.26m/s的乐观上限，不保证Nav2在90s内完成。

v2把活动/联合目标中心间隔设为0.7m，历史失败/访问排除仍0.2m、最后成功排除仍0.5m。实际掩码与apply一致，旧合同可恢复。0.7m目标间距不保证整条运动路径不冲突，也不保证带0.25m到达容差的机体位置始终安全。静态路径诊断没有接入生产调度器。

动作语义：15个全局候选槽加KEEP/WAIT；活动任务只允许KEEP(-1)，WAIT(-2)用于无可用工作的空闲机器人。RL没有主动取消合法活动任务的动作；前沿/生命周期规则、超时和收尾取消须单独识别。

## 3. 公开开发结果：改善参与伴随时间退化

| 回合 | joint / wall秒 | 自然完成 | 三机参与 | 结论 |
| --- | --- | --- | --- | --- |
| DEV01 | 142 / 243.917331 | 5/6 | 5/6 | 有40步外部尾段；不是整体GO |
| DEV02 | 143 / 250.130436 | 5/6 | 5/6 | 目标间距没有消除远端相向路径等待 |

两轮均原生exit0、0optimizer、46e权重不变。参与定义为每台至少获1个目标且实际路径≥1m，不以接受次数替代运动。4202/502在40步上限未完成；4203/501虽完成覆盖，但有机器人实际路径不足1m。覆盖完成不抵消参与失败。

`development-forensics.json` 保留近距离/相向长时间静止及90sim超时链。目标中心相隔较远也可能路径相向阻塞，不能把所有阻塞解释成近目标竞争。原件没有逐个safe_block的完整原因标签，不把描述性关联冒充逐事件确定归因。

## 4. 语料资格、正式训练与一次选模合同

`evidence/corpus-01/` 唯一资格运行起止22a112c、native0、5.946221wall，14reset/42初扫/14stop，0Policy/NN/step/optimizer。新8图相对23张历史几何及彼此做D4判重，0.38m可导航区连通；固定种子首个物理合格三机组，最多32次采样，clearance≥0.40m、pair≥1m、初扫覆盖<0.85。没有按候选数量或策略表现筛图/起点。没有新图Gazebo加载证据。

- TRAIN：原8图×4位置，加公开RL-03六张旧TEST×2位置，共14图/44对。旧TEST已公开并转TRAIN，不再当盲测。
- VAL：5301/701、5401/701、2103/202，共3例；不进入优化器。
- 新TEST：loop5101–5103、branch5201–5203，各601/602，共12条件。仅公开结构族内新几何，不是新域。

保持原701特征、两层128隐藏Tanh、3×17 Actor与Critic、奖励及PPO。46e权重起点仅载权重，重置Adam/RNG；seed2026110604；rollout256/minibatch128/4epochs，单次最多2048joint/64Adam、7200wall含初始化/12VAL/保存/停止，预留30wall收尾。初始0、512、1024、2048各3例确定性VAL；无1536额外验证、无第二次训练。

| 检查点 | 自然 / 参与 | 平均实际T95(sim秒) | 当前解释 |
| --- | --- | --- | --- |
| 初始0 | 3/3、3/3 | 52.8 | 继承已训练权重，0新增更新 |
| 512 | 3/3、3/3 | 46.133333 | 真实16Adam；三头有非强制机会及非零梯度/变化 |
| 1024 | 3/3、3/3 | 91.0 | 明显退化；branch5401有3个90sim超时及1274safe_blocks |
| 2048 | 3/3、3/3 | 91.0 | 未改善512；与1024的三例确定性任务结果相同 |

512的独立审计在 `reviews/RL-04/prefix-512-audit.json`：机会62/59/66、Actor头ΔL2约0.03256/0.06567/0.06059，参数有限；只证明该前缀真实更新，不是最终训练/性能PASS。

父运行必须完整native0后，才按固定资格与排名一次选模。更新前缀每头≥20次真实条件非强制选择、非零专属梯度及净权重变化；初始0是继承参考。排序依次自然完成、三机参与、单列惩罚T95、总路径、较早步数；raw coverage不排序。初始胜出则明确无新增PPO收益。selected前缀新增Adam与2048父运行64Adam分别报告，不把后者全部归给所选前缀。

独立父审计 `reviews/RL-04/formal-parent-audit.json` 已通过8批实际NPZ、合法mask、GAE/return误差<1e-5、有限更新、三头/Critic张量、48锁、账本及12VAL核对；root0NN/step/update。随后唯一一次选模native0/3.820155wall，实际选择512，16新增Adam、三头机会62/59/66。模型 `rl-04/runs/formal-01/checkpoint-00512.pt`，SHA256 `6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d`；`runs/selection.json` 保存全部排名及身份。此为VAL选择结果，尚非新TEST或工程迁移结论。

## 5. 公开回归、typed Mock与新TEST

两例公开回归仅4202/502、4203/501，各≤100joint、总≤200/900wall、0更新，独立账本，不参与选模。与旧DEV02只比较各自≤40步或更早自然结束，新的≤100结果单列；不能推断旧权重在100步也失败。

实际 `evidence/public-regression-01` native0，内部92.142898/外96.015006wall、112joint/112NN/0更新、权重不变，起止9fe。4202/502在100步预算结束、最终覆盖0.913374、T95缺失、15abort/6576safe_blocks；前40步覆盖/路径及2364blocks与旧DEV02一致。4203/501在12步/59.8sim自然完成，但tb1/tb3仅0.245421/0.795421m，不满足1m参与阈值。原零候选/零目标已恢复为实际目标，仍残留路径阻塞/短运动问题；不能把机会恢复等同任务稳定，也不统称修补毫无效果。公开回归为事前登记诊断，不新增为事后验收门槛；没有据此改模型/规则。

新TEST严格36例、3臂×12条件。通常为selected-v2 / 46e-v2 / traditional-v2；若初始0胜出，预登记把重复参考换成46e旧v1，不增加第四臂，不据TEST换分支。后者明确0新增学习，不冒称盲测独立管线收益。

工程任务门槛：A至少10/12自然及10/12参与，0非法接受/安全/停止失败；自然完成至多比同合同传统C少1例，全12例惩罚T95均值≤C的1.25倍。这是预登记工程容忍界，不是统计非劣或显著优势证明。真实未达T95保持缺失，500惩罚另列；共同成功时间/路径另列，保留全部失败与路径代价，按地图簇并按结构族分层报告配对区间。

实际唯一 `runs/test-01` native0，内部1005.305991/外1009.352086wall，起止9fe；557envstep、197NN、0更新，两个模型权重均不变。36例原始case/地图/轨迹/目标/导航终态全部保留；只读compare native0/7.310155wall、0NN/step/update。

| 同v2合同下的臂 | 自然 / 参与 | 真实T95均值（可用例数） | 全12例500惩罚均值 | 全12例平均路径m |
| --- | --- | --- | --- | --- |
| A selected512 | 12/12、12/12 | 40.1（12） | 40.1 | 19.537923 |
| B 46e权重参考 | 12/12、12/12 | 37.533333（12） | 37.533333 | 17.537180 |
| C 原传统评分 | 10/12、12/12 | 77.04（10） | 147.533333 | 22.907605 |

C未完成为loop5101/602、branch5203/601，真实T95保留缺失；500只在单列惩罚指标使用。全部36例非法接受/拒绝动作0、代理停止均验证，最小机间距0.7000000000000002m；这不是物理机器人停止/安全证书。A/C惩罚时间比0.271803，生产侧绝对与相对工程门槛PASS，独立 `reviews/RL-04/locked-test-audit-02.json` 已核验36表/557step/197NN/0Adam、实际候选至目标链接、UUID闭合、步长≤0.052m、pair≥0.7及路径误差≤1.8e-14。首次ROOT审计误把同sim的完全相同停止pose重复样本判为时间错误，原FAIL保留；02只修检查器允许dt=0且pose全同，没有生产修改或重测。

A−B的配对T95均差+2.566667sim、95%地图簇/族分层区间[-1.683333,8.383333]；路径+2.000743m、区间[-0.281155,5.136017]，均跨0，**没有证明新增PPO比继承参考更好**。A−C惩罚时间差-107.433333sim，区间[-178.566667,-37.033333]；共同自然成功10对的真实T95差-40.78sim。全例路径差-3.369682m，区间[-10.015385,3.367024]跨0，不签全面路径优势。仅6张族内新几何/两位置；这些区间与差值不外推到新结构域或实机，不用新TEST冒称盲测独立管线收益。

事前合同明确selected typed Mock只验证真实模型/消息/坐标及Fake Action接口，0环境步进；它本身不证明真实Nav2或Gazebo。实际Gazebo另行绑定模型/代码并获得P5准入，最多一次knownEconA180sim；原startup240/autonomous420/outer900+90cleanup界限与原安全/停止链不变，要求新证据证明三机器人目标/反馈/运动/SLAM/合图、至少1真实SUCCEEDED、终态后新owner及实测停止/UUID闭合/native退出；本次实际结果见下节。

实际 `evidence/typed-mock-01` native0/9.786971外包wall、起止9fe，真实3NN/0envstep/0更新，原传感夹具1reset/3scan/1stop。初选[1,4,7]，5个Fake目标/终态、3个收尾取消；目标坐标、body→merge速度与编码特征、KEEP不重发、成功/失败反馈、1条仍active的保留token、halt阻止新目标均通过。无实际Nav2服务器、物理运动或实测停止。

P2实际门槛：以监督器exploration_command.sim为启动，15sim内首次完整推理；完成时刻取现有首条rl_real_inference.sim（forward和保存inference-NPZ之后的保守记录时刻），原inference_start_sim延迟另列，不能用开始时刻冒充完成。评估器修正仅发生在TEST源关闭后；纯字典边界确认开始<15但完成>15会失败、完成恰15可通过，0新NN或回合。从首次applied inclusive计算全部稳态分配，≥90%拥有有效新鲜状态，最多1次连续等待；保留2秒门控及原始戳，不选晚warmup分母。完整分配延迟和NN延迟分别报告。合成分析边界通过不算实际ROS通过。

### 实际Gazebo、P2及退出

唯一 `runs/gazebo-rl-smoke-01` 从2026-11-06T02:46:18.840700Z至02:50:38.436752Z，起止均ed4，native0；自主区间sim31→211正好180sim、200.411755自主wall、259.596090完整外包wall。实际READY SHA256为 `6538ba0f971ca3d360870f0da67bd81a5d6b6fb9df60e49bc5de6b8a11459b7d`，由本次独立准入转自未授权草稿；没有单独stationary回合、第二次尝试或模型/目标规则修改。

| 机器人 | 真实接受 / SUCCEEDED | Gazebo路径m | 最大位移m | 自主阶段SLAM变化次数 |
| --- | --- | --- | --- | --- |
| tb1 | 3 / 3 | 8.834155 | 6.630144 | 13 |
| tb2 | 4 / 4 | 12.481672 | 7.172840 | 16 |
| tb3 | 3 / 3 | 9.324986 | 6.878875 | 14 |

三台LiDAR/odom/TF/SLAM、21个Nav2 lifecycle前检、实际Action反馈及合图有效，自动阶段共享图变化43次。10个实际UUID全部成功并终结，7条终态→新token/新UUID见证、0所有权重叠、0拒绝RL动作、请求闭合与生命周期pause健康均通过。最小实体中心距2.850208m，无已记录hazard。实际实体峰速tb1/2/3约0.335568/0.292031/0.305970m/s，不能把名义0.26当作物理硬上限。

`reviews/RL-04/gazebo-bag-audit.json` 通过独立SQLite/CDR核验：34个完整输入均为真实ROS合图的独立ROI采样、有限701特征与原odom戳；10个真实候选目标→请求→bag中status4 UUID一致，三SLAM/合图及实体运动真实发生。controller只消费收到的地图、odom/TF和反馈；Gazebo真值只用于独立传感/评估/安全，没有用于政策目标选择。

P2必须分列：关闭ledger为36次分配尝试、35次forward调用、35次完整返回记录（含1次启动等待）、34个完成政策输出/已提交joint；不是35个完成政策输出。第36次在sim210局部地图构建及forward后遇到sim211预算收尾，随后同步主线程halt；没有第35个NPZ/槽位或新Nav2请求，不能凭空称线程race。最后完整0034为三台WAIT，0035不存在。`accounting-closure.json` 保存末次forward、local-grid、smoke_bound、halt和零新增请求的顺序。

原 `state-availability.json` 的34/34=100%只覆盖完整返回记录，保持原样。统一纯评估器随后读取关闭ledger，另写 `state-availability-all-attempts.json`：首次完成延迟9sim（开始延迟亦9sim，为ROS采样时刻），firstapplied索引2后稳态共35次；末尾未完成保守计入分母，34/35=97.142857%，最大末尾连续未完成1，满足原≥90%/≤1门槛。未排除尾样本、未改阈值、未重跑Gazebo。完整分配均值1.115408wall秒、NN均值0.017820秒，均以34个完整记录为延迟样本，不用NN时间替代整条决策耗时。三头实际条件非强制机会3/4/3；TF外推异常仍存在，保留原戳的最近成功状态提高了可用性，不等于TF从未报错。2秒是位姿状态门控，不是声称所有地图年龄≤2秒。

末段实测停止、10UUID闭合与控制权退出均可信：独立CSV/bag核验约1.562wall稳定、实体速度<0.00008m/s、每台56条真实消费新零目标，仿真继续2.1秒，加载驱动inode与SHA仍8d54。**全部10个目标在结束前已成功，本轮没有新增“运动中取消”证明。** 原 `active_cancel_pass=false` 表示未执行该专门检查，不能改写成新通过。

native0后发现本轮 `ros2 node list` 创建的domain68 CLI daemon残留，前检不存在且本轮process列表证明归属；仅定向 `ros2 daemon stop`，native0/1.418459wall。`post-native-process-snapshot.json` 保留清理前原件，`owned-daemon-stop.*` 保留操作，`post-cleanup-process-snapshot.json` 确认daemon、Gazebo/控制器/Xvfb及domain68/11668/:68均无残留。没有再node list重建、没有杀无关进程；不能把原native0描述成自动清理了全部辅助进程。

## 6. 证据、取消口径与部署边界

证据根为 `rl-04/evidence/`、`rl-04/runs/`。训练完整日志 `runs/formal-01.log`，资源 `formal-01.resources.txt`，外包起止身份/原生退出在 `runs/formal-01/process-exit.json`；原始轨迹、地图、intents、decisions、navigation与rollout/updates/VAL全部保留，不用截图替代。内部4570.045722wall、外包4574.759440wall，GNUtime99%CPU、峰值RSS373972KiB、0swap、exit0。104个TRAIN例含102自然完成、2决策预算、0外部尾段，不能替代held-out或Gazebo任务结果。生产侧只读计数/48源关闭检查在 `evidence/formal-close-audit.json`：2048新样本、64更新、8192replay、8批、12VAL/173joint/173NN；随后独立完整父审计已通过。

取消必须区分：任务中 `metrics.cancellations` 与 `navigation_terminals.canceled` 不同，后者包含自然完成时收尾取消的真实终态。本次TEST A/B/C任务中指标均0，但包含收尾的canceled终态分别32/29/30。两者原件均保留，不写成“全程0取消”。实际运动中取消及实测停止是否有新证据须据新Gazebo结果单独说明。

环境沿用既有用户级BASE01 Humble/Gazebo Classic与修改版SLAM/Nav2；本轮没有全局安装/卸载或重新编译/替换SLAM/Nav2。训练用host `/usr/bin/python3`及已有CPU Torch，OMP/OpenBLAS/MKL/Torch线程1；机器人侧通过 `rl04/ros-python.sh` 的只读rootfs与当前中央源码overlay运行。只读实际mount清单 `evidence/p5-source-inventory-01.json` 确认修改版SLAM源码2.6.0、源码nav2_bringup1.1.16及系统controller/planner1.1.20，不能笼统写成所有Nav2均同版。生产驱动SHA为8d54d39a687de851c95137ddee4a7ebbab90c3373e07d96fad338870d4317fc0，本次实际gzserver加载inode/哈希已核验。绝对/project符号链接在host外看似断链，已在实际wrapper内解析，不是缺运行文件。domain68/11668/:68用于本轮唯一实际回合，即时检查及最终清理原件均保留。

二维训练/评价是受约束局部地图导航代理，不是Gazebo训练，更不是真实部署。实际部署仍需初始相对位姿测量、地图对齐/漂移、真实传感/底盘/QoS/TF和时钟同步、无线硬件、实时性及安全验证。固定ROI/公开结构族、少量新图及一次工程冒烟不能证明无界探索或实机可靠性。统一指标的真实重复探索面积/比例不可识别，保留null及原因；奖励中的duplicate_new_m2只是重复新增观测代理，不能包装为真实重复探索比例0。额外逐组数据见 `reviews/RL-04/paired-results.json`，没有为此重跑分析/模型。

### 全阶段调用账本与复现入口

[`CALL_LEDGER.json`](CALL_LEDGER.json) 逐条读取实际append-only ledger，和对应summary/native记录核对，未按预期预算凑数：

| 阶段 | 真实forward调用 | 前向计账样本 | 轻量env.step | Adam |
| --- | --- | --- | --- | --- |
| DEV01 | 142 | 142 | 142 | 0 |
| DEV02 | 143 | 143 | 143 | 0 |
| 正式TRAIN | 4058 | 12186 | 2048 | 64 |
| 12VAL | 173 | 173 | 173 | 0 |
| 两公开回归 | 112 | 112 | 112 | 0 |
| selected Fake Mock | 3 | 3 | 0 | 0 |
| 36新TEST | 197 | 197 | 557 | 0 |
| 唯一真实Gazebo | 35 | 35 | 0 | 0 |
| **合计** | **4863** | **12991** | **3175** | **64** |

计账样本包含真实PPO minibatch，GZ35调用中1次政策输出中断，不能把合计全部当完成输出。真实optimizer重放8192；实际所选前缀仅16新增Adam。轻量env.reset166、传感后端reset187，差异包含仅几何/路线诊断及Mock传感夹具；真实Gazebo不计为轻量step/reset。2次固定logit stub forward与1次合成sampler另列，**不计入神经网络调用**。静态诊断、纯评估、选择Tensor读取和独立ROOT审计均0新NN/step/optimizer。离线wrapper、01夹具/序列化和临时轮询错误及ROOT误报原件/更正说明见账本，不称全程无任何失败。

实际运行命令已固化在 `runs/formal-01-process-start.json`、`evidence/public-regression-01-process-start.json`、`evidence/typed-mock-01-process-start.json`、`runs/test-01-process-start.json`、`runs/gazebo-rl-smoke-01-process-start.json`；源码入口分别为 `rl04/train.py`、`select_checkpoint.py`、`public_regression.py`、`mock_selected_ros.py`、`test.py` 与 `gazebo_boot.py`。所有case目录禁止覆盖/盲目重试，P5_READY是真实历史授权原件，不能据此自动重开。本报告交付后不追加实验。

本轮新原件仅封存 `rl-04/evidence/**` 和 `rl-04/runs/**`：2256文件、207250291字节。[RAW_SHA256SUMS](../../RAW_SHA256SUMS) SHA256为 `8fc5045bda9fc0d5854ad8ddc738ac06655ce6b4d032c2270a7de178e04bd312`。没有重扫旧RL03、BASE或ns-3历史，也不把runtime-home缓存当科学原件。关键报告/模型/合同/账本/审计的SHA见 [IMPORTANT_SHA256SUMS](IMPORTANT_SHA256SUMS)；交付后的实际commit/report/model/diff身份见 [FINAL_IDENTITY.json](../../FINAL_IDENTITY.json)，无需自引用猜测commit。

关键原件：[训练摘要](../../runs/formal-01/summary.json)、[一次选择](../../runs/selection.json)、[两公开回归](../../evidence/public-regression-01/summary.json)、[Fake Mock](../../evidence/typed-mock-01/result.json)、[36例分析](../../runs/test-01/comparison.json)、[实际Gazebo](../../runs/gazebo-rl-smoke-01/result.json)、[P2全attempt](../../runs/gazebo-rl-smoke-01/state-availability-all-attempts.json)、[末样本计数闭合](../../runs/gazebo-rl-smoke-01/accounting-closure.json)、[实测driver](../../runs/gazebo-rl-smoke-01/loaded-driver.json)、[最终进程清理](../../runs/gazebo-rl-smoke-01/post-cleanup-process-snapshot.json)。

## 7. 最终结论与后续边界

| 项目 | 当前状态 |
| --- | --- |
| 新语料物理资格 | GEOMETRY PASS，非策略/真实仿真PASS |
| 唯一正式训练 / native退出 / 账本 | 2048/64完成、native0、生产侧及独立完整父审计通过 |
| 一次选模 | 已一次选中512/16新增Adam，native0，未正式冻结 |
| 两例公开回归 | native0；恢复目标机会，仍有超时/短运动；诊断非新门槛 |
| 36例新TEST | native0；工程门槛及独立原始数据审计PASS，限6张族内新图 |
| selected typed Mock | typed Fake接口PASS，3NN/0step，非实际Nav2 |
| 新真实Gazebo / P2持续可用性 / 实测停止 | PASS；独立原始bag核验PASS，P2保守34/35，限一次knownEconA180sim |
| 本轮总体分级 | 限定工程GO；不是全域/全图自然任务或实机认证 |
| 最终行为冻结 | 未执行，交付为明确版本的候选合同；不自动冻结/进入ns-3 |
| 报告SHA256 / 最终本地Git身份 | 见IMPORTANT_SHA256SUMS及FINAL_IDENTITY；不远推 |

候选合同见 [CANDIDATE_CONTRACT.json](CANDIDATE_CONTRACT.json)：固定三机、701特征/归一化与次序的ppo.encode源SHA、v2候选/掩码、ROS5sim决策周期、下一决策消费反馈、活动KEEP与token/UUID不重发、90sim超时及实际模型身份。它记录未来明确验收冻结时必须保持的行为边界；必要的策略/输入处理修改要新版本并重建对照。本轮只完成上述验证与可审查交付，真实机器人和真实Wi-Fi部署仍是后续项目必需工作。

# GZ-01 followup-10：固定原DWB的三图配对复核

**三张固定地图的六个回合均达到有效95%覆盖、三机真实参与，完成原600sim预算与停止认证。RL并非全面领先：T95在Corr、Rooms分别快9.3/11.1sim，在Hard慢5.3sim。** 本批不改源码、权重或参数；这是固定执行系统的有限跨图验证，不是新学习、盲测泛化或正式冻结验收。

实际Gazebo 6/6，历史77→累计83；六次native0、无运行fatal/hazard，82个请求全部闭合。任务阶段81个SUCCESS、1次Rooms传统超时失败；未删失败或重试。0训练/optimizer/ns-3/硬件/push，结束后停止新增实验。

## 主结果：每图同条件RL/传统

有效T90/95/98按各回合原自主t0起算，使用固定质量门槛下首次达到阈值的收件时间；不按旧source最老header回填。覆盖为正确自由格/固定可达参考分母，不是已知格比例。三机数据按tb1/tb2/tb3排列。

| 实际/累计 | 地图/算法 | T90/T95/T98(sim) | 末正确free覆盖 | 全期路程(m) | SUCCESS | 任务失败 | 结束 |
|---|---|---|---|---|---|---|---|
| 1/78 | Corr6201 RL | 61.8/61.8/93.1 | 99.9036% | 18.81/15.72/13.06 | 4/4/4 | 0 | 600sim预算 |
| 2/79 | Corr6201 传统 | 66.7/71.1/71.1 | 99.8200% | 13.49/11.11/13.84 | 5/4/4 | 0 | 600sim预算 |
| 3/80 | Rooms6101 RL | 85.7/90.2/103.5 | 99.9027% | 21.26/19.82/25.08 | 4/6/6 | 0 | 600sim预算 |
| 4/81 | Rooms6101 传统 | 96.9/101.3/140.8 | 99.8653% | 25.51/18.63/27.50 | 6/5/7 | 1超时C | 600sim预算 |
| 5/82 | Hard4202 RL | 106.5/106.5/162.6 | 99.8412% | 31.54/3.57/5.15 | 7/2/3 | 0 | 600sim预算 |
| 6/83 | Hard4202 传统 | 57.8/101.2/105.5 | 99.7618% | 32.17/2.87/4.89 | 5/2/3 | 0 | 600sim预算 |

六例原stop/三pause/authority/UUID闭合及run_integrity均true，三机实际SLAM fine=.75均已一次性记录。唯一任务失败为Rooms传统tb2：原timeout取消后raw CANCELED，高层按既有规则记aborted，发生自主201.8sim，晚于其有效T95=101.3；不能当普通成功/仅统计rawA=0就称零失败。精确UUID和原事件在唯一metric及六例汇总中。

兼容传统使用原JointTraditionalPolicy评分及共享最大参与、Frontier/路由/目标安全/执行规则，不冒称完整BASE-01逐byte原算法。所有结果按当前同源配对解释，不将旧05/07/09不同系统成绩混成平均或选最优回合。

## 速度与路程取舍

| 地图 | 达95总路程：RL/传统(m) | 全600路程：RL/传统(m) | 本次配对结论 |
|---|---|---|---|
| Corr6201 | 25.927/28.578 | 47.592/38.444 | RL90/95较快且95前较省路；98慢22sim、全期多9.148m |
| Rooms6101 | 36.169/44.466 | 66.152/71.644 | RL90/95/98均较快、路程较少；末图精度仍分别列出 |
| Hard4202 | 25.020/24.702 | 40.264/39.931 | RL90/95/98均较慢，95前与全期路程略多 |

每图仅各臂一次冷启动，未估计时间方差或统计显著性；同world/spawn/config不保证完全相同初扫地图/ROS调度。两图T95较快是有限正向结果，Hard反例保留，不称稳定全面领先。

Corr/Rooms/Hard参考分母分别15558/40076/15111格，面积38.895/100.19/37.7775m²；Rooms约为另两图2.6倍，因此逐图报告，不用跨图简单总平均制造优势。它们的实际body-height box结构51/20/53个且布局不同，也不同于Open6301，不是只改seed标签。

## 地图质量、起始观测与选择机会

| 回合 | C0 | 自主t0/首决策/首平移sim | 有效/总帧 | 末p95(m) | free precision | false-free物理面积(m²) | 真forward/传统决策；非强制帧 |
|---|---|---|---|---|---|---|---|
| 1 | 11.0811% | 28.8/35/35.9 | 405/412 | .05 | 98.0859% | 1.0950 | 119/0；6 |
| 2 | 11.0683% | 29.0/35/35.8 | 402/409 | .05 | 98.0475% | 1.1150 | 0/119；7 |
| 3 | 6.2182% | 30.5/40/41.4 | 378/400 | .10 | 99.1523% | 1.0475 | 118/0；10 |
| 4 | 6.3005% | 29.6/35/36.3 | 405/412 | .10 | 99.1821% | 1.0175 | 0/119；16 |
| 5 | 11.6273% | 30.0/35/35.8 | 404/418 | .05 | 98.8910% | .6175 | 119/0；6 |
| 6 | 11.5413% | 28.9/35/35.9 | 392/409 | .05 | 98.6894% | .7275 | 0/119；5 |

六例末图质量均有效，早期无效帧全部保留，阈值只取质量有效帧，没有改.25m判据或做地图拟合。高correctfree覆盖不等于地图完全准确，precision及物理false-free单列。各回合C0与首决策时点不同，仍保持原自主计时，不为结果事后换起点。

三个RL共356次真实forward，三个传统各119次实际决策；“非强制帧”指至少一头有>1实际合法选项，不把多数KEEP/WAIT尾帧当自由联合目标选择。没有为解释结果再forward网络、训练或重算新的策略动作。

## 三机参与与Hard闲置的限定解释

六例三机均有≥1m真实路程及成功UUID，不能要求机械等路程。末局部图独有新增正确面积(m²)如下，它是观察重叠事实，不是首次到达因果信用：

| 地图/算法 | tb1/tb2/tb3独有新增面积 |
|---|---|
| Corr RL/传统 | 4.1775/.2400/8.1300；.2250/1.4675/8.5350 |
| Rooms RL/传统 | .6025/0/1.3450；.5575/0/2.2250 |
| Hard RL/传统 | 14.3850/3.8350/.7125；14.2050/4.0150/.5075 |

Rooms tb2末独有新增为0，但RL实际19.82m/6S、传统18.63m/5S；他机后续重观测可抹去独有性，不据此断言没有贡献。Hard短路程tb2/tb3仍完成任务并有独有新增观测，不判合作FAIL。

按root要求，轻量读取Hard RL已存119个真实决策，并按原有效95%绝对136.5sim（自主t0=30）分段：

| 阶段 | tb2：idle/无合法候选/有候选且选择 | tb3：idle/无合法候选/有候选且选择 |
|---|---|---|
| 95%前，共21决策 | 17/15/2 | 17/14/3 |
| 95%后，共98决策 | 98/98/0 | 98/98/0 |

两机95%前另各4帧busy KEEP，不混入闲置；首次idle资格0分别在绝对65/70sim，确在95%前。全期115个idle包含98个覆盖达标后的尾帧，不能将115当探索期失衡。对应帧均没有“有原合法候选却WAIT”的记录；这只排除该帧自主拒绝合法任务，不排除更早分配/轨迹选择影响后续资格，也不识别哪一个shared/own/peer/Frontier上游过滤器造成供给0。见 `evidence/HARD_RL_IDLE_SUPPLY.json`，未新读bag/重跑metric/运行策略。

## 停止、预算退出与未解决边界

六例全机静止累计分别496.9/506.8/452.0/415.9/435.5/441.9sim；主要覆盖达到后仍有长尾，不能只展示T95隐藏原600sim结果。上层自然终态规则仍None，所有回合simulation_budget退出，未验证自然任务完成/停滞区分；高覆盖、全WAIT、停稳均不冒充自然完成。

本轮无runtime fatal/INVALID/hazard，原停止、三pause及所有82UUID闭合通过，主要Observer/peer捕获记录保存行数匹配；marker只证明已捕获行保存，不是逐pubseq完整或DDS送达ACK。若最后timer被中断，rows与lastsequence可能差1，原值保留。

固定peer_timing=false，所以本轮无需该可选peer_timing.json；Observer timing=true及原peerJSONL/marker保持。没有修改09第二SIGINT打断附加诊断的缺陷，也不能由本轮未复发声称旧352ms发布间隙已根治。旧09心跳失败、保存失败、被拒绝shim及更早所有失败仍原样保留。

## 固定资源、源码与图表

三图均已暴露；Hard4202还在历史训练几何内，本轮只称固定跨图复核，不称未见几何/新族泛化。共同三角沿既有资格，同图RL/传统同world/seed/pose，yaw全0、最小中心距.75m，三实体不重叠。旧.25body、peer.55/monitor.30、goal.80/idle.55、Quick50/slip1e-5、SLAMfine.75/粗跳INVALID、source.4/correctionheader.55sim/heartbeat.3wall、原停止及全部wall界限未松。

运行源码固定 `76fd91cf937bd8d662302901dad063affbea3c38`，模型固定6d4c51ba…，DWB/rotation_shim=false、peer_timing=false、observer_timing=true；本轮没有源码diff、候选优化、参数扫描或新测试。起始HEAD77cb只比该运行源多09两份归档文档，最终10文档提交另列 `DELIVERY_IDENTITY.json`。旧源/模型身份直接复用，三新scene/复制world仅各核一次。

- [Corr RL曲线/轨迹](evidence/corridor-common-6201-rl-fixed-dwb-01-metric-v2/coverage-and-trajectories.png) / [传统](evidence/corridor-common-6201-traditional-fixed-dwb-01-metric-v2/coverage-and-trajectories.png)
- [Rooms RL曲线/轨迹](evidence/rooms-common-6101-rl-fixed-dwb-01-metric-v2/coverage-and-trajectories.png) / [传统](evidence/rooms-common-6101-traditional-fixed-dwb-01-metric-v2/coverage-and-trajectories.png)
- [Hard RL曲线/轨迹](evidence/hard-common-4202-rl-fixed-dwb-01-metric-v2/coverage-and-trajectories.png) / [传统](evidence/hard-common-4202-traditional-fixed-dwb-01-metric-v2/coverage-and-trajectories.png)

每例只执行一次原metric提取；六图复用其CSV/NPZ和已记录真实轨迹，无新bag解码。原件在 `runs/<case>/`，逐项指标/原UUID/失败事件及原时序保留。`RUN_LEDGER.json`明确retrospective引用原boot/result时间，不补造实时记录；`RESOURCE_LOCK.json`/`PLAN.md`在新结果前锁定，未按成绩换图/起点/分母。六份READY均按已签健康前件顺序执行，无并行重计算或自动retry。

## 验收分级与结束

| 项目 | 本轮作用域内结论 |
|---|---|
| METRIC | PASS：六份原指标/质量/曲线完整，门槛未改 |
| BASELINE | PASS limited：三既暴露布局各一同源RL/兼容传统配对 |
| DIAGNOSIS | 仅轻量Hard供给统计；历史根因/新导航私有因果未补证 |
| OPTIMIZATION | 本轮无新优化/学习，仅固定系统测试 |
| IMPROVEMENT | MIXED：两图T95较快，Hard较慢；未证统计稳定或全面优势 |
| COOPERATION | PASS limited：六例三机均运动+成功，贡献不要求等路程 |
| SAFETY | PASS limited：六例原停止/闭合/三pause/无hazard范围，非所有部署条件保证 |
| FREEZE | NOT READY；NET NO-GO：自然终态、未见图稳定性及历史可用性风险仍开放 |

本批六实际/累计83结束，全部owned与唯一指标/绘图计算退出。只交付本报告、原件/必要新身份与本地文档，停止新增Gazebo、源码修复、调参、训练、ns-3、实机、冻结或push。独立评审在 `../reviews/GZ-01/followup-10/` 另行封存，不修改09或更早原件。

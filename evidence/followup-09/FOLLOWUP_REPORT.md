# GZ-01 followup-09：关键记录链解耦与导航转向候选验证

本批接收 **A 的关键记录边界修补**；**不采纳 B rotation shim 为默认，整体 GZ-01 / FREEZE / NET 仍 NOT READY / NO-GO**。同源、同 peer 诊断条件下，shim-on RL 的有效 T95=204.6sim、11次高层失败，shim-off 控制为113.4sim、0次失败。范围仅为已暴露 Open6301 共同起点开发条件，不代表多图稳定优势或新 PPO 学习。

六次实际 Gazebo 启动全部保留，历史71→累计77，预算6/6结束。五例完整600sim，一例控制器构造未完、0NN/0目标时因原心跳门限中断。无训练、权重更新、ns-3、硬件、远推或正式冻结。

## 六例实绩

时间采用各回合原自主开始到首次**地图质量有效**覆盖阈值的 sim 秒；覆盖为 correct-free / 固定40707格（101.7675m²），不是已知格比例。三机路程和成功数按 tb1/tb2/tb3 排列。失败=raw ABORTED + 原规则判失败的 timeout raw CANCELED；停机取消另计。

| 实际/累计 | 系统/算法 | T90/T95/T98(sim) | 末覆盖 | 全期路程(m) | 成功数 | 任务失败 | 结束/原完整性 |
|---|---|---|---|---|---|---|---|
| 1/72 | A记录边界/RL | 102.1/110.3/195.4 | 99.8354% | 15.99/31.44/18.20 | 7/10/6 | 1A+2超时C=3 | 600预算/native0/true |
| 2/73 | A记录边界/传统 | 154.0/158.5/172.0 | 99.8723% | 14.85/17.73/28.39 | 7/4/8 | 0A+2超时C=2 | 600预算/native0/true |
| 3/74 | B shim早期/RL | 未评估 | 未评估 | 各约0.00056 | 0/0/0 | 0，控制器未构造完 | 3.5sim心跳fatal/native1/false |
| 4/75 | B+peer诊断/RL | 191.5/204.6/209.0 | 98.6120% | 39.99/12.36/13.22 | 9/3/4 | 7A+4超时C=11 | 600预算/native0/true |
| 5/76 | B+peer诊断/传统 | 94.5/103.4/未达 | 96.9342% | 14.52/19.05/15.46 | 4/5/5 | 2A+5超时C=7 | 600预算/native0/true |
| 6/77 | 同源诊断 shim-off/RL | 101.3/113.4/113.4 | 99.9066% | 18.92/22.99/17.59 | 7/6/6 | 0 | 600预算/native0/true |

第3例进入监督自主窗口3.5sim，但控制器仍在 ROS Node 参数服务构造中，无实际 forward/目标；不填“算法覆盖0%”，不评价 shim 导航效果。原 observed_stop=false、缺 request journal、integrity=false 不追认。旧 `open-common-traditional-path-heading-shim-01.ready.json` 因前件失败保持 **NOT RUN**，不是第5例的覆盖或重试。

传统为原兼容评分的 JointTraditionalPolicy，加共同 maximum-participation/路由/执行合同，不冒称完整 BASE-01 逐字相同。A 两臂与 B 两臂分别在同系统内比较，不跨系统拼接均值。所有原 result 保留；第5/6例附加诊断保存失败另列，不能由原 integrity=true 掩盖。

## 同源控制与效率取舍

| 回合 | 达95时三机路程(m) | 达95总路程(m) | 全期总路程(m) | 全机静止时长/600sim |
|---|---|---|---|---|
| 1 | 14.603/17.039/11.644 | 43.286 | 65.634 | 396.3 |
| 2 | 14.568/12.159/25.049 | 51.775 | 60.970 | 415.7 |
| 4 | 30.775/12.348/13.204 | 56.326 | 65.573 | 67.2 |
| 5 | 11.470/15.256/13.285 | 40.010 | 49.024 | 129.1 |
| 6 | 11.866/17.116/13.306 | 42.287 | 59.504 | 468.2 |

A 的 RL 比同系统传统 T95 快48.2sim，但 T98 慢23.4sim、全期路程更多，不是全面稳定领先。第4/6例均76fd、peer_timing=true、同journal顺序/6d/地图起点，仅 shim flag 不同；第6例 T95 快91.2sim、末覆盖更高且0任务失败，支持本轮拒绝 shim 候选。实际初始地图和调度仍不同，单次冷启动不能定量分离全部因果。A背景与76fd多出的诊断开销/journal顺序也不同，不能将第1→4退步唯一归shim。

后段静止与探索失败分开：第1例95已于绝对139.7sim达到，tb1/tb2约241.5sim结束活动，tb3至246.4sim才结束，不能写241.5后全机无活动。第6例468.2sim静止主要在覆盖达到后；仍没有自然完成事件。五个完整回合均为 simulation_budget 退出，natural_complete=false/上层自然规则None，不能把全WAIT或停稳改写成自然完成。

## 地图质量、计时与调用

| 回合 | C0 | 有效/总帧 | 末质量p95(m) | free precision | false-free物理面积(m²) | 首决策/首真实forward sim | >1合法选项决策帧 |
|---|---|---|---|---|---|---|---|
| 1 | 5.3775% | 387/402 | 有效/.05 | 99.7176% | .3525 | 40/40 | 15 |
| 2 | 5.3529% | 398/409 | 有效/.05 | 99.4690% | .6650 | 40/非NN | 12 |
| 3 | 未评估 | 未评估 | 未评估 | 未评估 | 未评估 | 无/0次 | 0 |
| 4 | 5.4389% | 398/406 | 有效/.05 | 98.6090% | 1.7300 | 35/35 | 20 |
| 5 | 5.3431% | 396/406 | 有效/.05 | 99.4820% | .6225 | 35/非NN | 16 |
| 6 | 5.3873% | 389/399 | 有效/.05 | 99.4710% | .6625 | 40/40 | 11 |

初始已观测地图并不相同，仍按原自主t0计时，不事后换起点。早期质量无效帧完整保留，阈值仅取有效帧。第1/4/6真实forward为118/119/118，共355；传统118/119次决策。表中非强制机会仅指至少一头有>1合法选项，不能把全KEEP/WAIT尾帧当有意义联合选目标。0额外NN回放、0optimizer。

## A：明确的记录边界修补

08已证 Observer 长 models/drive 回调阻挡health处理，但低thread CPU不唯一证明磁盘IO。e8cb只改 `run_case.py` 与 `peer_keepout.py`：全phase即时更新state/seen/危险/控制输入，按原时刻复制行或序列化JSON到RAM；events/trajectory/drive/map/TF诊断及producer记录在原停机/退出后写出。没有线程/服务、丢行、刷新时间戳；controller_end 原增量控制输入、ownership读取和全部guard顺序不变。

A两臂行数/字段闭合，models/peer/drive回调约0.2–1.7ms；controller_end仍123–226ms，另有高CPU spin约229ms，不是消除全部IO或硬实时保证。原 `finished` 仅表示运行/清理结束，完整交付还需保存后的result/native/marker，不能单finished判PASS。正常/原fatal路径保存检查通过，SIGKILL丢RAM的边界没有消失。

## B：导航机制证据与拒绝结论

08唯一封存点tb2 UUID9ce761c3…：global path7.35m且端点匹配，前.44m与ROS朝向约155°，local中心与前缀cost0、peer距5.286m；local只纯转。首10sim路径.00794m，world角速积分净.125/绝对.371rad，命令主要±.05263rad/s反复切换。不是已证peer硬挡或RotateToGoal误用裁剪终点，也没有私有critic评分ACK，不能唯一指控某critic。

19d9 opt-in标准rotation_shim包装原DWB，事前固定.6rad/s、π/4、.5m采样、acc3.2、预测1.7s/closed-loop，终点yaw仍DWB；原progress .5m/10s、90sim期限、7critics、geometry/peer/安全不变。标准footprint检查对配置空间R.55可能额外保守并回退DWB，不靠缩几何处理。第4/5例实际三机插件加载已证；第6例三机日志明确创建原DWB。整体数据不支持采纳shim为默认。

最小机制对应在 `evidence/B_FIRST_TASK_MECHANISM_CORRESPONDENCE_02.json`：新两臂首tb1北向目标bearing约1.496rad，仅为初始yaw0的方向代理，不是08同一私有path前缀。截到首UUID终态，平移.816/.797m且SUCCESS；角速绝对积分3.506/3.411rad，命令含原DWB阶段max1.0，不能全部归shim .6，也不能说原155°故障被严格重现/普遍修好。01跨终态10sim初稿保留，02明确修正范围；没有为此再解bag或扩大critic分析。

## 发布端空隙、journal与附加保存失败

第3例seq330 health返回mono360459.501899782→Observer收.504664472仅2.765ms；下一timer入口.854107068，空隙352.207ms。seq331 health返回.918113953晚于原drain结束.913710469，fatal时新health尚未发布。旧330 source累计仍<.4，但heartbeat .409>.3原判定有效，不放宽heartbeat/延长drain/重盖stamp。controller traceback是原SIGINT导致的KeyboardInterrupt，不证明其自行构造异常。

76fd的opt-in peer时序只在RAM记录真实 receive_tf/odom/project_latest/publish_masks整个回调、/clock和原global executor public spin_once，没有更换调度器或加wait。第4例完整保存的三个>.3s gap都在preflight .2/1.9/4.8sim，因此历史**自主352ms NOT REPRODUCED、根因未定**。早期spin等待1817ms不能跨回合当根因；617.7sim tb3 TF/project约75ms高CPU只是本次事实，不等同历史空隙。

同提交把原allocation-events独占open移为CheckpointHeadquarters构造第一行、Node构造前；原record→send不变。0Node受控构造中断检查证明真实文件已创建，没有为历史第3例补stub。其物理窄核37.9–48.8sim三机各110body/325drive、新零序列317→545、XY≤.000071m/s、|wz|≤.000050rad/s、净XY≤.323mm支持实体静止；仍不追认缺journal的原停止认证。

**新增诊断SAVEFAIL独立保留：** 第5/6例主要地图/动作/trajectory/drive/peerJSONL证据完整、原stop通过，但peer退出时第二次KeyboardInterrupt打断 `persist_timing` 的json.dumps，`peer_timing.json`缺失、peer子exit1。原run_integrity未覆盖这个附加文件，不追认为诊断完整；raw marker仅证明JSONL捕获记录写完，不是timing保存或DDS送达ACK。第4例时序不能补造5/6时序，未修工具/重跑。

C类Spawn回复丢失仍为08独立启动故障，本批未重现，不与A/B混改，不称已修。

## 任务失败时间线

自主elapsed sim如下；精确UUID/raw状态/95前后逐条见 `evidence/FINAL_SIX_RUN_SUMMARY.json`。停机取消不混入任务失败。

| 回合 | 高层失败时间线 | 95前/95后 |
|---|---|---|
| 1 | tb3@124.0；tb1@212.1；tb3@217.0 | 0/3 |
| 2 | tb2@156.1；tb1@201.0 | 1/1 |
| 4 | tb2@110.2/139.6/166.3；tb3@178.7；tb1@353.2/447.5/548.8；tb2@511.0/535.5/560.3/584.6 | 4/7 |
| 5 | tb1@133.6；tb3@133.8；tb2@187.0/287.1/387.0/482.0/582.0 | 0/7 |
| 6 | 无 | 0/0 |

## 原件、验证与源码

- A：`e8cb43747daf921a38d76432e3bab7db9665b56a`，两文件63+/38−，实际已测参考；原字段/顺序/guard/stop及正常异常保存直接检查通过。
- B：`19d9ec639e1b5018892da994eba4daef074b7d30`，scene_launch 8行opt-in；三机YAML check02只增加wrapper，defaultoff保留DWB配置，工具首次StopIteration失败01保留。
- 最后运行源：`76fd91cf937bd8d662302901dad063affbea3c38`，三文件80+/5−，peer纯RAM时序+scene opt-in+既有journal前移；20项0Node直接检查native0。不冒称76fd逐字等于已测A，shim和peer_timing默认关闭。最后文档commit另列在交付身份。
- 固定6d权重/701/最大参与/路由、SLAMfine.75及粗跳INVALID不变；Quick50/slip1e-5/.25实体/R.55/.30报警、source .4/correction .55sim/heartbeat .3wall、原stop/600sim/130决策/全部wall边界未放松。
- 六例原件在 `runs/<case>/`，包括原result/events/UUID日志/drive/trajectory/peer状态/Observer timing/launch/bag。`RUN_LEDGER.json`显式retrospective引用原boot/result时间，不补造实时记录。旧身份复用，无旧历史重hash。

以下五图复用唯一已提取metric，没有第二次bag解码：

- [A-RL曲线/轨迹](evidence/open-common-rl-critical-records-01-metric-v2/coverage-and-trajectories.png)
- [A-传统曲线/轨迹](evidence/open-common-traditional-critical-records-01-metric-v2/coverage-and-trajectories.png)
- [B诊断RL曲线/轨迹](evidence/open-common-rl-peer-dispatch-diagnostic-01-metric-v2/coverage-and-trajectories.png)
- [B诊断传统曲线/轨迹](evidence/open-common-traditional-peer-dispatch-diagnostic-01-metric-v2/coverage-and-trajectories.png)
- [同源shim-off控制曲线/轨迹](evidence/open-common-rl-peer-dispatch-shim-off-control-01-metric-v2/coverage-and-trajectories.png)

## 八项验收分级

| 项目 | 本批限定结论 |
|---|---|
| METRIC | 五有效运行原指标/质量/图表完整；零NN早停例不填算法覆盖0；两例附加时序SAVEFAIL独立 |
| BASELINE | A与B各有同系统传统；76fd开/关shim控制仅RL各1，不造多图均值 |
| DIAGNOSIS | A记录耦合已证；B大回转缺平移有机制证据；历史producer352ms未复现/未唯一归因 |
| OPTIMIZATION | A记录边界限定PASS、journal顺序修正可保留；B shim不采纳默认 |
| IMPROVEMENT | 无新学习；同源shim-off本例更好，稳定RL任务优势仍NOT DEMONSTRATED |
| COOPERATION | 五完整例三机均≥1m且有成功UUID；不等于全程导航质量或自然完成 |
| SAFETY | 五例原停机/闭合/三pause通过，一例缺journal原FAIL保留；不签硬实时或全部完整性PASS |
| FREEZE | NOT READY；NET NO-GO；不进入ns-3/实机/正式冻结 |

本批6/6及两个主要候选已结束。后续应另立有界修补计划：可靠保存附加诊断、定位producer调度缺口与后段真实导航停滞；不放宽时效/物理/超时，不据本图调PPO。交付报告/源diff/新重要原件身份及本地文档后停止，不追加源码、检查、实验或训练。独立Review另在 `../reviews/GZ-01/followup-09/` 封存，不并入旧冻结身份后改SHA。

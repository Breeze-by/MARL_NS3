# GZ-01 followup-09 独立评审

**接收 A 的记录边界修正与启动 journal 顺序修正；拒绝将本轮 rotation-shim 候选纳入默认导航。GZ-01 全范围仍为 INSUFFICIENT EVIDENCE，正式冻结 NOT READY、NET NO-GO。**

最有用的结果是：同源、同诊断开关、同 RL 模型下，原 DWB 回合 **113.4sim 达到95%，最终99.90665%，19个目标全部成功**；shim 回合为204.6sim、98.6120%、11次任务失败。支持当前保留 DWB 的工程选择，不证明插件在所有环境中无效，也不证明 RL 已跨地图稳定领先。

## 固定审查对象和预先标准

| 对象 | 身份 |
|---|---|
| 继承的08交付 / 运行源码 | `1a290a2beef20e804ac0cd5244bcc72e357d6c41` / `c7985466305e1113c1c69e53b2d5c3cf28885dca` |
| A记录边界源码 | `e8cb43747daf921a38d76432e3bab7db9665b56a` |
| B导航候选源码 | `19d9ec639e1b5018892da994eba4daef074b7d30` |
| 最后三回合源码 | `76fd91cf937bd8d662302901dad063affbea3c38` |
| 最终文档提交（仅两份文档） | `77cb84760af9e096ffa3f7391904a8602bf86437` |
| 不变 checkpoint | `gz-01-followup-09/runs/formal-01/checkpoint-00512.pt` |
| checkpoint SHA256 | `6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d` |

源码与文档交付分开识别，不以文档提交冒充运行源码。源码身份清单为本阶段 `evidence/{A_CANDIDATE_SOURCE_IDENTITY,B_CANDIDATE_SOURCE_IDENTITY,PEER_DISPATCH_TIMING_SOURCE_IDENTITY}.json`。本轮沿用已核基线，不重新签发 BASE/RL 历史阶段的全面验收。

root另核最终HEAD到运行源之间只改`gz01/FOLLOWUP09_REPORT.md`和`gz01/FOLLOWUP09_DELIVERY_INDEX.json`、工作树干净，主报告与Git归档逐byte相同。报告SHA256为`5d4ab6291425d987987a56c6c733244b46616a610ba0da8afb282652165b317f`；交付索引SHA256为`9594063819ffde9b43beb26d6aeed83d0c99390e338779aed6c0abaebd7fdaf8`，均经本次小文件身份核对；未重复扫原bag。生产交接见`gz-01-followup-09/DELIVERY_IDENTITY.json`与重要新原件清单`EVIDENCE_MANIFEST.json`。PROJECT已记录本批完成/停止，旧历史保持。

先于本轮运行登记的标准见 [REVIEW_PLAN.md](REVIEW_PLAN.md)：明确 A 发布—接收关键路径问题与 B 大角度路径缺乏平移问题；固定模型、地图/共同三角起点、40707格分母、几何、SLAM、时效、Nav2进展和停止规则；最多6次实际启动、两项主要候选，失败也计数。保持合法目标、真实 Nav2/物理运动/SLAM、完整失败记录；不把局部回调变快、零环境检查或高覆盖单项当系统完成。

最后一单是针对实际混杂因素的同源 shim-off 控制，预先签具体配置，未换模型/seed/地图/参数；不是新候选。第5例额外时序存档失败后，明确仅按主要导航、地图及安全证据继续最终控制，保留 DIAGNOSTIC SAVEFAIL，没有放宽物理/时效/覆盖判据或追认诊断完整。

## 实际阅读清单

- 08生产与独立评审、09 `PLAN.md`、`PROBLEM_MATRIX.md`、`B_NAV2_SHIM_PLAN.md`；09三次源码差异及实际工作树/staging身份。
- 实际源码 `gz01/run_case.py`、`gz01/peer_keepout.py`、`gz01/scene_launch.py`、`rl01/ros_policy.py` 的变更与相关停止/初始化路径。读完整 A 两项直接检查、B YAML检查、最后20项组合检查源码/原生结果；没有把0Node检查写成真实ROS PASS。
- `runs/open-common-rl-critical-records-01/`、`open-common-traditional-critical-records-01/`、`open-common-rl-path-heading-shim-01/`、`open-common-rl-peer-dispatch-diagnostic-01/`、`open-common-traditional-peer-dispatch-diagnostic-01/`、`open-common-rl-peer-dispatch-shim-off-control-01/` 的原 result、必要 Observer timing、事件/控制日志及 launch 创建/退出片段。
- 五个完整回合各自唯一的 `evidence/<case>-metric-v2/result.json`，A两份与B诊断两份记录闭合JSON、最后回合原停止/权属/保存字段；不重新提取同一指标。
- `B_FIRST_PROGRESS_POINT_DIAGNOSIS.md`、`B_FIRST10_ANGULAR_PROGRESS.json`、`B_RL_EARLY_HEARTBEAT_TIMELINE.json`、`B_EARLY_FAILURE_STOP_PHYSICS.json` 及最小首任务对应的范围说明。没有假称读过未记录的私有critic评分。
- `RUN_LEDGER.json`、`FINAL_SIX_RUN_SUMMARY.json`、生产者 `FOLLOWUP_REPORT.md`；目视检查 shim-on RL 和同源 shim-off RL 的覆盖/轨迹图。

root只操作评审文件与具体运行授权，生产者/实现Agent修改源码和执行实验。Reviewer没有发送运动/导航指令、运行新Gazebo/训练或重新解bag计算覆盖；也没有重扫历史哈希。原始结果先于生产者最终结论核对。完整数值表见 [PERFORMANCE_REVIEW.md](PERFORMANCE_REVIEW.md)，A字段/计数审查见 [A_REVIEW.md](A_REVIEW.md)。

## 按严重程度的问题与风险

### P2，已证实：附加诊断存档会被重复中断打断

- **定位：** `workspace/gz01/peer_keepout.py:280`、`:303`；第5/6例原 `launch.log` 退出尾，及第5例 `B_DIAGNOSTIC_TRAD_RECORDING_CLOSURE.json`。`run_case.py:927` 的原 integrity 范围不含新增时序文件。
- **事实/原因：** 原spin因SIGINT退出，原peer JSONL及marker保存后，第二次 KeyboardInterrupt 在 `persist_timing` 的 `json.dumps` 中发生；两例 `peer_timing.json` 缺失、peer子进程exit1，父监督native0/原integrity=true不能证明全部诊断保存成功。
- **影响：** 这两例无法用于完整publisher时序归因；主要地图、轨迹、Action及原停止证据仍存在，不等于主期物理失控。第5例6371行/lastseq6372也不能称序号逐行完全闭合。
- **最小建议/验证：** 后续在已经退出spin的纯归档阶段处理重复中断，独立报告附加文件保存结果；用一次无机器人受控重复信号检查证明文件完整及失败如实暴露。本轮不改工具再重跑，不把缺失补成PASS。

### P2，尚未排除的风险：自主期publisher入口间隙仍未唯一定位

- **定位：** 第3例 `events.jsonl` 的seq330/331、`observer_timing.json` 与 `B_RL_EARLY_HEARTBEAT_TIMELINE.json`。
- **事实：** 330发布返回→接收仅2.765ms；到331下一timer入口隔352.207ms，331的新health晚于原最终检查。最后源龄仍<.4sim，但heartbeat .409wall>.3，发生真实原规则FAIL；0NN/0导航目标。
- **原因边界/影响：** 空隙在发布端下一入口前；具体其他回调、执行调度、DDS或OS未唯一分清，不能归旧Observer输出阻塞或shim导航。存在偶发启动中断风险。
- **最小建议/验证：** 可靠保留现有callback/clock/spin短时序，下一次出现同类真实事件时匹配原因；不先更换调度器或放宽心跳。第4例未复现只能写NOT REPRODUCED，不能写已根治。原journal缺口已用真实open前移修正并检查，旧第3例formal stop FAIL保持。

### P2，已知功能边界：没有自然探索终态证明

- **定位：** `workspace/gz01/run_case.py:668` 和五份唯一metric的 `natural_completion_verified=false`；原上层自然规则None。
- **事实/原因：** 五个完整回合全部因600sim预算退出；高覆盖后长时间静止或全WAIT不是自然完成事件。
- **影响：** 能验证覆盖任务表现，不能签发完整任务自然终止PASS。第6例468.2sim累计静止主要在高覆盖后，不应全部算作95%之前失败。
- **最小建议/验证：** 后续单独定义基于真实可观测Frontier、任务和地图更新的自然完成/停滞区别，测试仍有可执行任务不会误判完成；不得使用评价真值在线结束或降低覆盖阈值。

### P2，重要验证缺口：当前组合只有单个已暴露开发场景

- **定位：** 本轮 `RUN_LEDGER.json` 六例与全部scene身份，均为Open6301共同起点几何。
- **事实/原因：** 三个RL完整回合的推理118/119/118，共355次，但有非强制选项的帧仅15/20/11；多数尾帧KEEP/WAIT。当前没有多图稳定统计或学习收益消融。
- **影响：** 不能据355次forward或一次19目标全成功宣称RL普遍优于传统或具备冻结条件。传统为兼容打分加共享最大参与/执行规则，不能冒称BASE-01逐byte原算法。
- **最小建议/验证：** 保留原DWB和当前模型，事先锁定Corridors/Rooms及初态，用相同执行层做有界复核；逐个失败目标区分候选/规划/控制/SLAM/生命周期，随后才决定是否需要RL改动，不先扩大二维训练。

本轮没有证据支持编造P0或P1。B是**被拒绝的实验候选**，不是已经替换默认基座的缺陷修复。标准插件的额外footprint检查叠加配置空间peer可能更保守，是事前登记风险；本次没有足够私有状态证明它是所有失败的唯一原因。

## 结果与生产者报告交叉核对

同76fd、同peer/Observer诊断、同6d模型的RL开关对照：T95从204.6降至113.4sim，末覆盖98.6120%→99.90665%，高层失败11→0，三机路程39.995/12.361/13.217→18.920/22.994/17.589m，成功目标7/6/6。第6例各局部地图独有新增正确观测5.61/3.6925/2.6775m²，支持三机实际参与，不作第一到达因果信用。

这是单次同源开发控制，初始SLAM观察/ROS时序仍不同，不证明唯一因果或统计显著。A→B还混有诊断/journal差异，不混平均；传统shim虽103.4sim达95%，但600sim未达98%、末96.9342%且7失败，不能据单一阈值说全面更好。

生产者主表、355真实forward、六次预算、失败时间线及SAVEFAIL与已核原件相符。没有发现最终报告把Mock、零NN启动或父进程native0冒称完整Gazebo成功。原result.integrity的范围比新增诊断窄，生产报告已单列该差异；不据这个字段独自给全证据PASS。第3例仍为原FAIL，无事后补journal；其实体静止/新零窄证据与原formal stop缺证分别保留。

## 独立验收分级与最小处置

| 项目 | 独立结论 |
|---|---|
| GAZEBO METRIC VALIDITY | PASS，五份主要任务指标；零决策例不伪造覆盖0 |
| GAZEBO BASELINE | PARTIAL，仅当前单场景开发对照 |
| ROOT CAUSE DIAGNOSIS | PARTIAL，A边界有据；历史publisher间隙和Nav私有失败机理未闭合 |
| OPTIMIZATION VALIDITY | PASS，有明确假设/固定候选/共享执行/控制实验；不代表候选有效 |
| GAZEBO IMPROVEMENT | NOT DEMONSTRATED；B候选在同源RL对照中观察到REGRESSION，拒绝纳入 |
| MULTI-ROBOT COOPERATION | PARTIAL；最后控制单例三机有效参与成立，未证跨图稳定 |
| NAVIGATION SAFETY | PASS，当前已完成76fd回合的物理停止/UUID/三pause范围；历史第3例formal FAIL不覆盖 |
| FREEZE READINESS | NOT READY |

**最小处置：** 保留A记录解耦和真实journal初始化修正，使用原DWB；保留但不启用被拒shim实验。后续优先补可靠诊断归档、自然终态定义和固定多图验证，依据失败任务决定Nav2/候选修补，不以增加PPO训练代替定位。源码仍只提供高层目标，未改SLAM/Nav2核心、未给RL速度权限；未重新做硬件部署验收。

**最终：局部工程变更 ACCEPT WITH CONDITIONS；B候选 REJECT；GZ-01完整目标 INSUFFICIENT EVIDENCE。POLICY FREEZE NOT READY，NEXT STAGE NO-GO。** 六次实际预算结束，全部本轮owned Gazebo已退出；停止新增源码优化、实验和训练，不自动冻结或进入NET-01。

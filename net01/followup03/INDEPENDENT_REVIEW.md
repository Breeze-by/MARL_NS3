# NET-01 followup03 独立评审

评审者：`/root`。生产者负责实现与运行；主审及两条独立审查线负责源码、原件和评价复核。

**结论：本轮有限修补及其隔离证据可接受；NET-01正式验收仍为 BLOCKED，NO-GO NET-02。** 没有新的Gazebo机器人业务经Wi-Fi完成探索闭环，不能宣布任务完成。没有发现本轮伪造成功或覆盖历史失败的证据。

## 1. 固定审查对象

| 身份 | 固定对象 |
|---|---|
| 生产者完整交付/报告 | `63fe1f057eba13a228737125fb63b66eaf318f79`，本目录 `REPORT.md`、`RUN_LEDGER.json`、`DELIVERY_IDENTITY.json` |
| 最终运行源码候选 | `5401af455156b0371ba2d440f3a439149c6faf08`；只在continuous19隔离验证，未做Gazebo回归 |
| A07真实运行源码 | `6a9232522b3e2d71f3fd367639ab63b2bcf1501f` |
| A08真实诊断源码 | `d21e20632736bf7bab4257e9faed5c148884ae08`；未包含最终暂缓GC修补 |
| 不变发布tag/提交 | `MR3-RL-POLICY-v1.1.0` / `a014ef11d4b77fe45832268467993dfdeb4398f6` |
| 原行为源码 | `76fd91cf937bd8d662302901dad063affbea3c38` |
| checkpoint-00512.pt | SHA256 `6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d` |
| 新native ELF | `82bc8ecff7d1e88d826931be534335fac21971fa8e6a23731af805f291c7e184`；依赖独立构建记录 `d5528e2e7421c3a6c0837a35fc32a262188ec6e3` |

主审核对了tag仍指向a014；15b53至5401的变更均在`net01/`，没有修改冻结行为源码目录。5401至63fe仅新增报告、指标与身份材料。重要文件身份见生产者Manifest，未进行无关全树重复哈希。

新执行profile为500Hz wall update、100Hz仿真时间clock发布、10ms native量子；物理dt仍1ms。它改变WallRate相对sim时间的关系，必须重新建立共同A/B参考，不能拿历史600sim成绩作为本轮配对结果。

## 2. 先验通过标准

审查按原NET-01要求判定：冻结策略及执行语义不被网络侧改写；业务包实际经过Wi-Fi；双向消息、Action身份和断链负例成立；时钟、源龄及停止规则不放宽；真实三机完成有界感知—决策—Nav2—反馈闭环；失败、未完成阈值与退出证据如实保留。隔离测试和CPU优化均不能替代真实Gazebo闭环。事后未降低覆盖率、间距、源龄或停止阈值。

## 3. 实际审查材料与证据矩阵

源码：`gateway.py`、`bound_peer.py`、`bound_mask_wire.py`、`topic_wire.py`、`run_network_case.py`、`boot_network.py`、native CMake/记录实现，以及冻结`peer_keepout.py`、`run_case.py`、`ros_policy.py`、`execution_evidence.py`的相关路径。审过profile、故障后排空、暂停对齐、时钟参数查询、longspan/GC观察及最终GC候选的实际diff。

原件：continuous15–19的Gateway/退出记录及对应native边界；固定burst的完整输出比较结果；新依赖实际编译/链接身份；A07/A08的result、事件、Peer记录、Gateway记录、Action所有权、drive/trajectory；A07只运行一次原离线评价器。startup独立GDB记录与工具失败均保留。没有启动独立Reviewer控制回合或给机器人发目标。

| CLAIM | SOURCE / ACTUAL EVIDENCE | 独立判断 |
|---|---|---|
| 首clock失败由大输出堵塞造成 | `MEASUREMENT_15.json`及native实时边界：首fault晚于STEP入口37.565ms；首大输出54.926ms后才开始 | 此解释被证伪。输出阻塞是后继问题，故障后排空修补不能冒称解决首因 |
| 异步记录能解决计算瓶颈 | `ASYNC_LEDGER_PAIR_SUMMARY.json`：事件/字节相等，但RunCPU仅降3.43%，总CPU增18.03% | 不采纳默认；失败收益保留正确 |
| Release构建有效 | 原CPUoff Run118.963→77.038ms；7883条记录、完整payload/stdout/PCAP、除mono外事件全等；13库实际同新根 | 接受约35%固定负载工程收益，不外推所有无线轨迹；不能和有诊断开销的166ms混比 |
| 满载Wi-Fi可以持续传关键状态 | continuous17原件：三机各80批ready mask/health，maxlag .09sim，原间隔/持有源龄检查未超限 | 有限隔离PASS；12376入网中12052完整交付，不能称零丢失，未arm且不是Gazebo时间 |
| A07完整探索成功 | `runs/net01-a-corridor-6201-07/`：9.96sim，1NN，三机各1个真实目标及运动，随后receipt fatal | FAIL。任务期0成功；保护停机3个CANCELED不算探索成功 |
| A08长空隙来自GC | 原GC start431086717302799/end431086858174914：gen2扫描140.872115ms/CPU140.865667ms、collected0，包含在142.741ms R-ready query中 | 此处机制已证实；但它在末heartbeat首fault前约6秒，不能倒推首fault或A07同因 |
| 最终GC修补有效 | continuous19：处理起止实际GCfalse、无GC事件、close恢复原true及[700,10,10]；峰RSS115840KiB | 接受有限机制验证。引用计数保留，循环内存可增加；未验证180sim或长期服务 |
| 19消息内容完整 | 已捕获Topic上行7316/下行246与Action5090的逐流/内容计数在对侧一致；三机连续80批ready mask | 证明捕获后到对端发布入口未变/未漏，不证明任意DDS源、全部最终消费者零丢失 |
| Gazebo—Wi-Fi真实闭环已完成 | B/C均NOT RUN；A07/A08都是direct业务，native仅作真实clock探针 | BLOCKED。三机运动与ns-3有数据分别成立，不能拼成该闭环PASS |

## 4. 按严重程度的问题

### P1-1：真实组合仍存在接收/心跳断档，无法持续探索

- **性质：已证实验收阻断，精确上游根因尚未闭合。** 证据为A07/A08原result、Peer/Gateway记录及`A08_FIRSTFAULT_TIMELINE.json`；相关源码`workspace/gz01/peer_keepout.py:175,234`、`net01/delivery_guard.py:20,38`。
- **事实与原因边界：** A07中央Peer seq255的tb2/tb3 receipt为.216839/.215767wall，超过原.2；源龄/校正较新，C转发约.1–.3ms，较晚odom在失败快照后才被Gateway捕获。A08三机health间隔约306.55/307.15/302.48ms，超过原.3；同段C clock relay间隔308.866ms，Peer发布定时器间隔309.068ms。该首fault附近没有长GC或单handler证据，尚不能区分Gazebo实际发布节奏和reader排队。
- **影响：** direct参考都不能完成180sim，无法进入公平Wi-Fi对照，不能推断RL或Nav2性能退化。
- **最小修复范围：** 用同一clock身份补齐源端与网关入口的单调时钟对应，按实际占时修发布/接收调度；不刷新旧状态、不放宽原门限、不继续调RL或扫描网络参数。
- **修后验证：** 新预算下先通过同profile实际direct参考的源龄/心跳/真实停止，再单独准入匹配Wi-Fi。当前没有此验证。

### P1-2：模型模块初始化前早退出，真实请求日志缺失，原停止认证无法闭合

- **性质：已证实认证/启动生命周期缺口，不是已证实体失控。** A08 `result.json`与事件；源码`workspace/rl01/ros_policy.py:16,68`、`workspace/rl02/execution_evidence.py:10`、`workspace/gz01/run_case.py:498`。
- **事实与原因：** A08只有.11sim/0NN/0目标；模块级numpy/torch导入先于constructor首行exclusive journal open，早期终止可能没有真实日志。原closure明确报`Expected controller request log missing`，停止稳定窗口因此不成立。原`observed_stop=false`必须保留。
- **影响：** 不能认证所有权闭合或NETWORK SAFETY。独立已存pose/drive同时支持实体近静止、新零指令消费和三Nav2暂停；不能把认证失败写成已发生实体失控。
- **最小修复建议：** 在允许的外部启动/权威记录边界建立早于重依赖导入的真实活动记录；如需改冻结实现，另立版本并重新评审。不能给旧回合补造空journal，也不能将0目标默认等同闭合。
- **修后验证：** 在权威尚未初始化、已初始化未发目标、已有活动目标三种退出点，分别证明真实日志/所有权与物理停止；先隔离验证，后有界真实验证。

### P2-1：A07中央GetResult仍未决，不能用本机UUID关闭替代全Action链完整

- **性质：已证实收尾缺项，根因未唯一定位。** A07 `network-gateway.json.cleanup`记录3个C GetResult RPC未决、C executor shutdown=false；同回合R端三UUID的真实GetResult=5及取消返回成立。
- **影响：** 本机停机事实有效，但中央消费终态及完整退出尚未证明，影响Action端到端验收。
- **最小修复建议：** 检查故障/就绪代际变化下原UUID终态的交付与未决Future关闭，保持取消/终态原身份，不伪造Nav2结果或恢复新目标权限。
- **修后验证：** 隔离Action取消/迟到结果负例中中央端也获得可追踪终态并结束未决RPC，再进入真实网络运动验证。19没有目标，不能覆盖此问题。

### P2-2：GC阻塞候选已修，但实际Gazebo效果尚未验证

- **性质：原缺陷已证实；最终候选的真实运行效果仍未验证。** 源码`net01/gateway.py:147,434`，A08原GC/longspan与19原件。
- **原因/影响：** 活跃路径自动循环扫描曾占140.872ms，直接造成一段长读取空隙。5401只在受外层wall约束的Gateway阶段暂缓，收尾恢复，未改策略/Peer/HQ或阈值。
- **最小建议与验证：** 保留19有限通过，下一实际匹配回合检查消息空隙、源龄、峰值内存和收尾恢复。当前不可称彻底解决A07/A08，也不可不加验证用于长期部署。

## 5. 原要求核对与可读性能结果

| 要求/验收项 | 独立结论 |
|---|---|
| 冻结策略/历史保护 | PASS：代码变更边界及tag保持；新执行profile的WallRate影响已披露 |
| ns-3真实Wi-Fi模型 | PASS（独立模型/包路径范围） |
| 独立双向传输 | PASS（17有限满载）；完整实际机器人业务组合BLOCKED |
| 无DDS旁路 | 既有受控隔离负例保留；本轮实际Wi-Fi—Gazebo组合NOT VERIFIED，不签完整部署PASS |
| 多时钟同步 | BLOCKED：最终候选只有隔离验证；旧15/16clock FAIL不能混称5401实际maxlag失败 |
| Action/消息端到端完整性 | BLOCKED：真实direct局部闭合，中央未决与早退journal缺项未解决；Wi-Fi Nav2未运行 |
| 网络异常安全 | BLOCKED：A07原停止成立，A08原认证FAIL；没有本轮运动中无线断链安全证明 |
| Gazebo—ns-3闭环 | BLOCKED / B、C NOT RUN |
| 新覆盖率/公平性能证据 | INSUFFICIENT：没有健康新A/B，不能用旧600sim成绩替代 |
| 下一阶段 | NO-GO NET-02；不训练、不推送、不启动新回合 |

| 回合/算法 | 条件 | 自主sim时间 | 90% / 95% | 覆盖与运动 | 结束原因 |
|---|---|---:|---|---|---|
| A07 / 固定RL | Corr6201，原共同三角，新共同profile，direct | 9.96s | 未达到 / 未达到 | 原始末49.6336%，但13/13地图质量无效；有效覆盖无可认证值。自主路程.9745/.1353/.9732m，各1目标、0任务成功 | odom receipt超线；停止期三取消另计 |
| A08 / 固定RL | 同条件，新增只读profile/GC观察 | .11s | 未测量 / 未测量 | 0NN/0目标，未形成可评价探索；没有填0覆盖率 | 三机health超时；journal缺失使原停机认证失败 |
| B/C | 真实Wi-Fi条件 | NOT RUN | 未测量 | 未测量 | 未准入 |

A07原评价器只处理一次sealed bag，分母15558格/38.895m²。末图在自主8.32sim收到，occupied alignment p95=.4m超过原.25m，不能把raw49.63%包装成可信探索完成率。该早期失败样本也不足证明整个SLAM算法长期失效。

## 6. 与生产者报告交叉核对

63fe版报告已区分旧clock FAIL和最终候选未验证、direct FAIL和Wi-Fi未运行、GC长段和末heartbeat、实体静止与所有权认证。未发现需要指控的虚假成功结论。主审复核后只纠正了这两处分级措辞，未改实验标准。本文对CDR计数的范围进一步限定为已捕获消息到对侧发布入口，不外推最终所有DDS消费者。

历史GZ SIGSEGV只在一次60wall隔离启动内未重现，且辅助Peer导入缺口保留；不宣称修复。A07 inventory的clear:false来自脚本自身bash文本误匹配，已读原argv确认，不据此编造旧actor或新增清理。失败没有被后续成功覆盖。

## 7. 最小退回集合与未验证风险

1. 闭合clock生产—读取—C仿真时间—health生成的连续性证据及对应修补，解决真实接收间隔问题。
2. 闭合早退出时真实权威/请求记录与原停止认证；解决中央未决终态，而非补造成功日志。
3. 预算重新授权后，用同一profile/固定策略做最小实际direct参考，再做真实Wi-Fi业务闭环；检查最终GC修补的内存与停止效果。

在此之前，180sim持续能力、真实Wi-Fi下三Nav2生命周期、网络中断物理安全、完整任务覆盖和实际部署均未证明。不得先改RL、候选、Nav2、世界或安全阈值来制造通过。

## 8. 最终意见及交接

**有限工程修补：ACCEPT WITH CONDITIONS。NET-01阶段完成：REJECT / INSUFFICIENT EVIDENCE，整体BLOCKED。存在P1，建议不进入下一阶段。**

本轮3/3实际Gazebo（startup、A07、A08），累计92；1次真实NN、3个实际目标，0训练/优化器更新。19后无新增运行。B/C未执行。交付报告、当前源码和失败原件可交接；Git bundle由主审在本评审入库后建立。bundle保存源码/配置/轻量报告与历史提交，不包含被忽略的原始bag/PCAP、rootfs及构建产物；它们仍在本机原目录，不能把Git备份称为完整实验数据备份。

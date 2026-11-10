# NET-01D 独立验收意见

**结论：BLOCKED / NO-GO。** 两轮修补已经用完，九个无运动case已封存，实际Gazebo为0/8；A0、C以及四臂自主探索比较均未运行。本轮没有证明完整Wi-Fi接入可稳定支撑既定业务，不能进入Gazebo矩阵或NET-02。

本意见来自独立只读源码审查、封存的小结果、原Action/清理事件、已有CDR身份和Hub精确消息ID关联。没有由Reviewer启动节点、网络模型、Gazebo、推理、训练或新测试；没有改生产源码、旧证据或Git。最终运行源为81710e6739311a59ed4bef945a0fbd871d274a64；身份沿用主审必要核验，不重复计算历史hash。详细原事实分别保存在本目录既有机器可读证据及分项评审，避免重复分析大文件。

## 十一项用户门禁

| 用户门禁 | 独立结论 | 范围及理由 |
|---|---|---|
| RL FROZEN INTEGRITY | **PASS** | 已审差异保持v1.1.0权重、701编码、Frontier、动作/KEEP/WAIT、Nav2、SLAM及决策语义；没有训练。身份部分依主审已执行的必要核验。 |
| GATEWAY CORRECTNESS | **BLOCKED** | 有限编解码、可靠Action和实际路由正证；完整B正常窗口仍因R输入积压后的原源龄门限失败，尚不能签整个接入正确可用。尚无证据唯一指为Gateway逻辑Bug。 |
| HEALTH TIMELINESS | **FAIL** | 最终B正常段Rsim4.66持有tb2 correction4.10，.56sim>.55；32wall未完成。P1未arm全段曾有301–313ms间隔，也保留原样。 |
| ACTION RELIABILITY | **BLOCKED** | f05有限真实Wi-Fi重送/确认及本轮真实CDR、UUID、反馈成立；最终B中央三个GetResult仍未知、R响应待确认。不能用本机取消成功补成中央RPC全闭合。 |
| ROS MESSAGE INTEGRITY | **PASS** | 在本轮实际捕获/交付样本范围，原Goal完整CDR逐字节相等、原UUID未改；最终B 89/95实际C-R身份与订阅内容一致。不是所有DDS源消息无丢或最大容量证明。 |
| CLOCK CONSISTENCY | **PASS** | 限定已核Mock时基/原10ms量子及20ms实际NativeACK信用、旧真实A10/B01相位原件。最终B466个ACK的G=E，相位0生效。不是本轮真实Gazebo同步性能或目标RTF通过。 |
| NO DDS BYPASS | **FAIL（验收证据不足）** | 两DDS域、B仅实际nativeRX交付、无本地业务fallback的静态证据及旧f05 Action切链证据可有限沿用；本轮完整B正常先失败，未执行持续供给下的全流radio-off负例。未证明存在旁路，也不能签全流断链验证PASS。 |
| WIFI PACKET EVIDENCE | **PASS** | 有真实完整业务经过ns3与明确分片UID的AP MAC/PHY→STA MAC/PHY→UDP→完整消息链。限定已核正向样本，不代表每条业务都成功或无线零丢。 |
| SAFETY SEMANTICS | **PASS** | 原时限/失败锁存/未知结果语义保留；最终B原源龄失效实际触发取消、GetResult5及三PAUSE，本机清理先于STOP；中央未知保留。仅为语义与无运动本机服务证据，**实体物理停稳本轮未验证**。 |
| GAZEBO CLOSED LOOP | **BLOCKED** | 0/8，所有臂NOT RUN。模拟源、受控Action服务与MockPhysics不等于真实LiDAR/SLAM/Nav2/ODE或探索覆盖结果。 |
| CAUSAL ATTRIBUTION | **PARTIAL** | 两个收尾缺陷与真实修补回归闭合；模型内交付、wall耦合和R取件前积压已分段。旧137.93ms、启动约1s及当前具体SDK/调度责任仍未唯一归因。 |

## Class A–E 因果矩阵

标签严格区分已观测现象、已确认责任、假设和未验证内容；同一事件可同时有D保护结论及上游E缺口。

| 类别 | 实际证据与判断等级 | 不应推出的结论 |
|---|---|---|
| **A 已证软件Bug** | **CONFIRMED CAUSE**：首fault后共享STOP过早撤R服务/Gateway处理机会；第一轮marker又把Future.done误作done_callback完成。源码与实际反例支持。第二轮要求真实Cancel/GetResult记录；cleanup02及最终B封存原件支持局部修补。 | 不能追认这两项是原health首故障原因；原cleanup01仍FAIL。 |
| **B 已证实现/调度开销** | **OBSERVED**：最终B 1765次TF严格关联，source→take中位616.900–638.871ms；元数据source→received最多3.171ms，主要剩余等待在received时间戳→R take。最大外poll226.947wall/226.103CPUms，包含多handler/pump，单wait/handler无≥10ms。另已分出NativeRun与Run外信用/输送成本。 | 正常必要模型CPU不是Bug；received_timestamp不是最早reader-ready证明，不能把该等待唯一归DDS、Python SDK或OS。 |
| **C 已证Wi-Fi影响** | **OBSERVED / CONFIRMED PATH**：完整B中实际消息经过真实无线模型，selected两个健康消息每片UID有MAC/PHY/UDP链。最终B已完整交付业务N延迟p95=6.108973ms、max21.800361ms；关键health45/46六ID皆完整RX。 | N为模型内完整应用交付成本，含CSMA/AP/无线排队与重组，非纯传播、非Linuxwall；不能说这六条丢包造成最终首故障。 |
| **D 合法安全响应** | **CONFIRMED CAUSE（保护触发）**：最终B旧seq45所持tb2校正4.10在Rsim4.66确实超.55；旧interval先检查，新seq46不能抹去失效。三原UUID随后本机真实Cancel/GetResult5/PAUSE。 | 保护合法不证明上游正常；不得放宽TTL、等新包再隐藏原FAIL或把本机结果伪造成中央已收。 |
| **E 尚未解决** | **OBSERVED / UNRESOLVED**：旧health发布后137.93ms、首A1启动约1s、本次持续R取件延后责任已缩小但具体机制仍不足；无唯一可确认删改的SDK逻辑错误。原DDS发现/缓存、执行器和调度解释需分别保留假设边界。 | 不强归无线，不把未复现旧窗口叫修复，不因一次A1成功宣称所有负载/时序稳定。 |

## 修补和测试条件是否有效

`FAILURE_TEARDOWN_REVIEW.md`保留两项具体缺陷和反例。cleanup02原active→停供trigger→首fault→LOCAL→STOP顺序成立；三原UUID各Cancel0/匹配列表/GetResult5/PAUSE、owned空/本机未决0，等待58.486393ms。原firsterror未擦。该结论接受**外部harness收尾局部修补**，不签物理安全。

真实相位校准不是把压力失败改判：旧A10全部14322及B01全部10951个ACK前G=E有原件支持；默认stress5ms保持，新actual-corr6201仅初始0，仍10ms步进、20ms信用/节拍、原clock/offset/TTL。两新actual组均RAM，但A1空业务Native与B真实网络CPU/IPC/同步差异仍在；A1→B总wall差不能全算纯无线。

actual A1完成32.000903wall正常窗口、三真实结果4/4/5及第四目标取消5，原RPC/确认全0；这是有限无运动正证，不是旧约1s现象已经修好。正常逐样本health/mask数值如由runtime另补，应引用该case的原样本统计，不能借先前另一次A1结果代替。

## 最终B的实际组件与传输结果

- 三R真实arm、三真实Goal接受，完整原CDR与UUID一致，反馈各525；没有正常终态，中央三个GetResult未知。正常32wall、第四目标和radio-off均未到。
- 本机真实三UUID Cancel0/精确列表/GetResult5/PAUSE、owned空/本机future0；LOCAL mono519992551240490先于STOP519992556999037，等待94.606391ms。中央pending3、R各response待ACK1、executor[false,true]照实保留。
- 89实际4份、95实际6条，C-R已有CDR身份计数相等，三R诊断订阅各消费4/6。路由0→1后R同DDS域fanout，不伪称三STA独立无线复制；真实MergeMapNode生成共享图，但原地图来自fixture模板而非本轮SLAM。
- Hub业务4767入/4587完整，关联负值/ID异常0；首guard前4422入网消息截止均完整，但不代表源DDS无丢或按wall及时。180未完整中177在故障后最终N4.65入网，之后没有N推进机会，属于截至观察未交付，不能全部计永久无线丢包。
- 原三health流各40/40；seq45/46六ID均完整交付，延迟.194589–2.771138N-ms。真实空口存在与持续R取件积压可以同时成立，不互相替代。

机器原事实及各flow分布见 `ACTUAL_PHASE_WIFI_01_COMPONENTS.json`、`ACTUAL_PHASE_WIFI_01_NETWORK_DELIVERY.json`；两条真实UID链见 `FULL_B_PHY_MAC_CHAINS.json`（前一stress完整B，未冒充最后case）。原失败、截止未决和首次现场均保留。

## 后续最小方向与停止

如另获授权，最有价值的下一步是针对**已收到元数据到R取件之间的持续等待**，利用现有逐源ordinal、metadata与outerpoll/handler记录区分可复核的积压/处理吞吐责任；仅在能提出明确、可证伪的机制时实施一项有界修复，再验证完整正常负载及真实全流断链。不能先扫TTL、QoS、量子或无线参数，也不需扩大为新框架。若更改调度/批量处理，必须保持原消息语义及公平四臂基线。

当前没有授权由本意见再执行上述建议。两轮已耗尽，九case封存，**停止新增运行、第三修补、Gazebo、训练和下一阶段**。RL理想通信发布版本仍可保留，NET-01D接入与因果实验资格仍为BLOCKED。

## 主审封存复核与按严重程度排列的问题

本节由主审补充。已独立读取最终报告、源码差异/身份、cleanup02原ACTIVE/LOCAL/STOP记录及actual A1正常窗口统计；原NET工作树保持干净，当前`workspace/`、`policy/`、`config/`、场景、行为合同及发布Manifest与v1.1.0无差异，最后实测运行源仍为81710e6739311a59ed4bef945a0fbd871d274a64。认可上述BLOCKED / NO-GO，不签下一阶段准入。

**P1 — 正常Wi-Fi业务下定位输入过期，阻断完整闭环（现象已证，唯一软件缺陷原因未定）。** 定位入口为`net01/gateway.py:375`，直接证据为`../health/actual-phase-wifi-01/first-fault.json`及`FINDINGS.md`。R时钟4.66仍持有tb2的4.10修正，真实源龄0.56超过0.55；新修正仍在产生。1765次取件与实际发布时间严格关联，主要等待在RMW报告收件时间至R取件之间；该时间戳不等于reader-ready，不能把一个SDK函数定为已证Bug。影响是32秒正常负载失败，无法测得新的可信Gazebo覆盖或无线性能损失。最小下一工作是隔离该已定位边界的可服务速率与队列责任，先用不丢样、不改消息语义的受控诊断提出机制，再选择修复；验证须复用相同完整负载、原时效要求及真实无线消息身份，成功后才进入有界Gazebo。

**P2 — 首故障收尾过早撤销本机服务（已证并完成有限修补）。** 原502ba02版本共享STOP路径与`net01/gateway.py:523`的无本机轮询关闭过程形成窗口；当前修补位于`net01d/run_replay.py:227`。原因是资源销毁早于取消/结果回调完成，可能留下未决本机状态；不能唯一追认旧tb2未决正是该窗口造成，更不是首源龄失败原因。最小修补为保留原首故障，停观测后在原总预算内至多等待2秒真实本机清理再关闭；中央无线UNKNOWN不清除。cleanup02及最终B已验证精确UUID、真实取消/结果5/暂停、owned和本机Future清空且LOCAL早于STOP；实际物理停稳仍未验证。

**P2 — Future.done被误用为回调处理完成（已证并修补）。** 当前完成条件见`net01d/replay_roles.py:75`；反例是cleanup01原LOCAL记录缺少GetResult回调，而随后最终记录才出现结果5。SDK先置Future完成再调度回调，取消回调还可能创建后续GetResult，因此旧标记会过早允许关闭。最小修补是每个`g.stopped` UUID已有真实取消响应及终态结果记录，保留原owned/暂停/Future条件；回归继续严格检查结果5。cleanup01失败不改，cleanup02真实回归及最终B94.606ms本机排空提供了有限验证，不等于中央结果闭合或物理安全认证。

**P2 — 全流断链与四臂比较证据尚未闭合（测试缺口，非已证旁路）。** 证据为最终B在正常段已失败，第四任务、预注册radio-off与Gazebo均未执行；真正A0直连入口的同等安全/所有权接线也尚未实现，不能用旧modeA替代。影响是不能签发全流无旁路或理想通信/Wi-Fi因果比较通过。最小补证应在输入时效问题闭合后，先完成源持续供给时的真实断链负例和安全处理，再依预注册条件完成四臂；本轮没有实施授权，禁止补造数据。

actual A1后补统计已核为本次原始数据的离线审计：正常32.000903墙钟秒，各机160次健康收件、最大间隔225.383ms；各160张mask全部接受，间隔上界最大228.158ms；正常6719条TF严格关联，取件前等待最大111.292ms；1600次物理确认G=E且信用不超过20ms。见`../health/actual-phase-local-01/RESULT.md`。它支持该次A1有限正常结果，不能覆盖旧失败或解释最后B的长等待。

关键文件校验索引见`../SHA256SUMS`；最终封存提交、完整本地Git备份及原始证据位置见阶段外层`../../../FINAL_IDENTITY.json`。该封存身份与实测源码身份分列，不将后续文档提交伪称为运行时版本。

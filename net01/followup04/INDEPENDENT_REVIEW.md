# NET-01 followup04 独立评审

评审者：`/root`；实现和实验由生产者执行。本审查依据实际源码、原始运行记录及独立只读诊断形成，随后与生产报告交叉核对。

**最终结论：正式NET-01验收REJECT / BLOCKED，真实Wi-Fi B01运行FAIL，NO-GO NET-02。** 有限工程修补有真实进展，但不能以native子程序PASS、日志完整或两台机器人有运动替代三机探索闭环。没有发现本轮覆盖历史失败或伪造通过的证据。

## 1. 审查对象与身份

- 生产者最终交付提交：`f59bb8c21c83dce039b3f6e773e7d1599958eebd`，分支`net-01/followup-04`；本报告针对该固定提交及对应A09/A10/B01封存原件。
- 原发布：`MR3-RL-POLICY-v1.1.0` / `a014ef11d4b77fe45832268467993dfdeb4398f6`；原行为源码`76fd91cf937bd8d662302901dad063affbea3c38`。
- `checkpoint-00512.pt` SHA256：`6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d`。
- B01实际准入提交`45bdfdbf468ab7a222fb5cd6e0a659eb9a6fa47c`；生产适配候选`b7f5e92353d2580e90881d0b39342c840c56694f`。B没有运行新合成夹具来代替真实Gazebo发布者。
- native仍为Release-portable的`82bc8ecff7d1e88d826931be534335fac21971fa8e6a23731af805f291c7e184`。B薄插件为新`a49b00dedab1f6c2352bdef1e9eb849dcdba2662a7990f9e15ebe75428941ecf`；旧A10仍使用e224插件。
- 重要源文件、artifact及运行配置身份见各`*_ADAPTER_BINDING.json`、READY和交付Manifest。本审查核对690202b至B准入的修改均位于`net01/`，没有修改冻结策略源码目录；未重复哈希无关文件树。

本轮事前限定最多3次实际Gazebo启动，实际A09/A10/B01为3/3，历史累计95；C没有运行。新共同工程窗口在A09之前固定为120仿真秒/420自主墙钟秒，原启动、收尾、时效、间距、停止与覆盖质量门限不变。原180秒能力没有被追认通过。

## 2. 先验通过标准

按原NET-01要求：固定RL及SLAM/Frontier/Nav2/机器人行为边界；关键业务必须真实经过ns-3 Wi-Fi且无直接DDS回退；真实消息和Action身份完整、时间关系可审计；三机形成实际感知—中央forward—目标—Nav2运动—反馈闭环；原安全停止与完整退出成立；所有失败和预算如实保留。无运动资格、Mock、CPU测试和direct参考均不能替代真实Wi-Fi Gazebo验收。

不放宽300ms心跳/绑定、200ms位姿收件、400/550ms源龄、120ms映射lag或原停止规则。修正夹具的源时钟必须依据冻结源码，不能按结果降低负载；原更重压力的失败仍保留。

## 3. 实际审查清单与证据矩阵

源码及差异：`action_wire.py`、`controller_bootstrap.py`、`gateway.py`、`bound_peer.py`、`bound_mask_wire.py`、`time_control_state.py`、`time_controller.py`、`time_control_runtime.py`、薄plugin、`run_network_case.py`、`host_run.py`、`packet_hub.py`、clock witness和夹具调度；冻结`workspace/gz01/run_case.py`的停止规则及相关实际配置。

证据：A09/A10/B01原result、journal、Gateway/Peer、实际进程退出、clock/token/nativeACK、trajectory/drive及封存地图；20–28资格和诊断摘要、源时钟合同、构建/隔离检查原件。B的Action和停机另由独立审查线及工具作者只读定位；工具作者诊断不被当作独立验收。原离线bag评价由生产者每case运行一次，评审不重复运行。

| CLAIM | SOURCE → ACTUAL EVIDENCE | 独立判断 |
|---|---|---|
| 直接适配120秒可运行 | A10：120sim/239.994wall，12个Nav2目标全成功，完整clock及停止记录 | 有界direct闭环成立；poststop旧gzserver−6另列，不能签所有退出PASS |
| A09也是完整成功 | A09：119.2sim即heartbeat故障；保存还被信号中断 | FAIL，虽然故障前已到95%，不能抹掉晚期故障 |
| 页等待是实测瓶颈 | 26：PCAP及ledger的writev期间连续D状态/folio_wait_bit_common，CPU与运行队列计数不变 | 本次同步文件页等待成立；不能倒推所有历史空隙唯一同因 |
| RAM记录解决了全部实时问题 | 27同原压力仍超过300ms，原FAIL保留；B九文件3,942,740,394字节复制完整 | 记录路径机制改善成立；实时性与系统通过不成立 |
| 28资格等于Gazebo | 28固定源时钟资格16wall、原时效通过；0arm/0NN/0真实运动，缺89/95业务 | 只接受有限传输校准，99条未完整交付也保留；不能外推B |
| B native PASS即系统PASS | B network/result：native退出0、76761入口/75959完整交付；主result为fatal/integrityfalse | 子项PASS不能升级成系统PASS |
| B已完成三机导航 | B：17次实际forward，但仅tb2/tb3各1笔实际接受，tb1几乎不动 | FAIL；三机实体存在与三机有效任务执行不同 |
| B Goal已经到Nav2，只是到不了 | 两请求有C捕获/Hub入口/native udp_tx，无R完整接收或响应 | 此解释不成立；先修传输/Action完整性，不能先归RL或局部导航 |
| 真实地图/journal只是本地代理token | B原flow89：138捕获/137交付，约7.03MB整图CDR；flow95：9捕获/8交付，R原记录8条 | 确有真实内容过Wi-Fi，亦确有未完整交付；没有证明所有消息都到达 |
| B observed_stop=false说明实体失控 | 原停止规则还要求所有权闭合；两请求保持未知，原三PAUSE成立 | 原认证确实FAIL；不能仅据该布尔值宣称机器人仍在运动 |
| 新plugin退出已改善 | B `launch.log:7243`实际gzserver clean exit | 本回合退出回归成立；不声称唯一证明A10旧崩溃原因 |

## 4. 按严重程度的问题

### P1-1：Action请求单次无线交付丢失后永久未决，三机任务链不成立

- **性质：已证实缺陷和验收阻断。** `net01/action_wire.py:110–119,157–162,171–193`；B主`result.json`、`network-gateway-saved.json`及原native ledger。
- **可复核事实：** tb1 UUID `d0f0f07af4ef4822a32bb57afd2096b4`、tb3 UUID `5bfac829d999453a8692a5aed7238052`的原SendGoal，分别对应native ID12874/flow220及23962/flow260。Hub入口记录后确有105字节udp_tx；ledger行1351870及2156177可定位。没有对应Hub目的端完整交付、Gateway R消费和响应。中央最后两Future和两个retired service仍在途，C executor未正常闭合。
- **原因：** C准入请求只发一次并无限等待原Future；R已有同RPC去重/缓存，但C没有可靠交付与确认闭合。具体无线丢失的PHY/MAC/队列环节尚未唯一确定，不伪称Nav2已接收或拒绝。
- **影响：** 机器人拿不到探索任务，原目标所有权未知，停止认证与端到端Action验收失败；近理想Wi-Fi也不能被假定为零丢包。
- **最小修复建议：** 在通信适配层为关键Action服务提供保留原session/RPC/UUID的有界可靠交付、幂等处理和明确不可交付状态；不能通过重建新UUID、重复执行Goal或合成Nav2接受/成功掩盖丢失。保留原探索及安全规则。
- **修后验证：** 无运动隔离环境分别丢请求、丢响应、重复/迟到响应、撤权后取消/结果，证明原身份最终闭合且不重复Nav2调用；通过后另行准入真实有界回合。本轮没有这些新验证。

### P1-2：真实Wi-Fi回合心跳超时，持续运行仍未通过

- **性质：已证实失败；首故障底层原因尚未闭合。** B `result.json`和原guard/Peer/Gateway/native时间线。
- **事实：** 自主87.57sim/186.8545wall后出现`health_heartbeat_stale`。最终result展示tb3，协调器首先保存tb1，不能只按最后错误文字归因单一机器人。独立核对Peer seq1032/1033均ready；1033发布返回mono458208.186454543，C网关捕获.324384468，间隔137.930ms；Hub接收.329918123、R实际消费.330829963，而tb1 guard已在.327175423锁存。由上次真实收件括号可知锁存时旧心跳至少332.879ms，确实超过原300ms；新包晚3.65ms抵达不能消除原故障。原120秒窗口未完成，故障未被后续日志覆盖。
- **影响：** 无法建立健康A/B公平探索比较，也不能宣称时间/状态交付已稳定；P1-1发生更早，不能把全部低覆盖归于最后心跳。
- **最小修复建议：** 优先查上述真实发布返回→C捕获的137.930ms未观测段，补齐必要的源writer/reader调度边界；已有证据不能唯一归DDS或CPU，也不能把全部延迟称为无线空口。保留其后Hub→R消费链，不刷新旧源戳、不放宽原门限，不先训练RL或扫描无线参数。
- **修后验证：** 原固定负载及源时钟下首先通过有限隔离时效检查，再证明真实Gazebo业务120秒和原停止链；只见进程退出0不足以通过。

### P1-3：故障停止的所有权认证未闭合，不能签NETWORK SAFETY PASS

- **性质：已证实安全验收阻断；不是已证实体失控或碰撞。** B `time-control-observer.json`、`events.jsonl:4768,5729`、`network-gateway-saved.json`；冻结`workspace/gz01/run_case.py:434–518`。
- **事实：** 实际权威进程退出0，三Nav2 PAUSE成功；FAULT_STOP_OBSERVE产生618次真实10步ACK，103.33→109.51sim，最终HOLD且无物理RPC故障。但上述两未知请求使原`ownership_closed=false`，原12秒窗口不能认证`observed_stop`；不得事后删除请求或改原规则追认PASS。
- **独立CSV复核：** 在上述103.33–109.51sim实际停机推进窗口，每机有62个位姿样本，覆盖103.36–109.50sim，最大墙钟样本间隔.2081秒；最大线速分别约.000070/.000076/.000070m/s、最大绝对角速均低于.000050rad/s。各机181/182/182条stop阶段drive记录的目标均为零，实际消费序号分别426→1247、695→1070、838→1644。这些支持本窗口实体低速、新零消费与持续观测，仍不代替缺失的原所有权闭合认证。
- **影响：** 不能开始自主运动中的主动全网断链，也不能进入NET-02。正常回合的旧安全证据不能替代当前无线故障安全。
- **最小修复建议：** 先闭合P1-1的请求交付与所有权状态，让独立安全层能核对实际机器人侧接收/执行状态；物理停止事实和业务确认分别记录，不能用物理静止伪造Action终态。
- **修后验证：** 无运动的请求丢失/断链/恢复先验及原身份闭合，再单独准入运动故障测试；本轮没有主动运动断链验证。

## 5. 性能结果与逐项验收

时间均从各回合自主t0起算，覆盖使用固定15558格/38.895m²可达自由空间分母和原质量门限。以下并非统计或RL算法改进结果。

| 回合 | 条件 | 实际自主sim/wall | T90 / T95 | 末有效覆盖 | 三机路径m | 结束 |
|---|---|---:|---|---:|---|---|
| A09 | direct工程参考 |119.2 /238.514|63.82 /71.32|98.8559%|12.3225 /5.4402 /11.4642|heartbeat故障、保存缺项，FAIL|
| A10 | direct工程参考 |120 /239.994|74.26 /76.73|99.8907%|20.1732 /5.6251 /17.3798|预算退出；原停止成立，旧gzserver退出−6|
| B01 | 真实近理想ns-3 Wi-Fi |87.57 /186.855|未达到 /未达到|57.4303%|.0026 /.2510 /.9644|heartbeat故障，两Goal未知、认证FAIL|
| C | 非理想Wi-Fi |NOT RUN|未测量|未测量|未测量|未运行，不用旧回合补齐|

A10不比A09更快：T95增加且总路程增加；工程修补收益是完整120秒时效和记录，不能写成RL性能提升。B另改RAM记录路径及插件析构修补，A10与B并非所有工程条件严格同一，不用于统计通信收益。均没有自然完成证据。

B末图在绝对102.76sim收到（自主87.0秒），源图戳101.73sim；104/112评价帧质量有效，末occupied对齐p95=.05m、自由空间precision98.2383%。8935/15558格正确观测，剩可达unknown16.51m²。不能将57.43%低覆盖归为“全部地图质量无效”，也不能把源戳回填成更早的收件覆盖时间。任务期tb3一个成功、tb2一个ABORTED；两个未知请求不算导航失败终态，不能省略。原主result路径含少量不同阶段样本，上表统一采用离线任务窗口路径。

| NET-01原要求 | 独立等级与边界 |
|---|---|
| FROZEN POLICY INTEGRITY | PASS：权重/701编码/探索决策及SLAM/Nav2核心未改；外部受控时间与WallRate关系披露 |
| NS3 WIFI MODEL | PASS：真实MAC/PHY、原V3、完整payload及PCAP；不表示零丢包 |
| BIDIRECTIONAL TRANSPORT | PASS限于实际双向传输存在；关键Action交付完整性FAIL |
| NO DDS BYPASS | PASS（受控作用域）：原隔离负例及B真实路由复核；两无线丢失Goal没有经DDS旁路到Nav2，不外推所有故障情形 |
| TIME SYNCHRONIZATION | PASS（本次受控时间对应的有限作用域）：真实Step/clock/nativeACK与固定10ms offset有证，末physical/Rclock109.51与nativeACK109.50对应、Gateway failure=null；未宣称未重算的全期maxlag、零观测丢样、120秒能力或精确硬实时。心跳交付时效另FAIL |
| ACTION AND MESSAGE INTEGRITY | FAIL：两个真实SendGoal未决；原身份未闭合 |
| NETWORK SAFETY | BLOCKED：原B停止认证FAIL；物理低速、三PAUSE、退出事实独立保留 |
| GAZEBO NS3 CLOSED LOOP | FAIL：真实尝试已发生，但未形成可靠三机闭环，不能写NOT RUN或PASS |
| PERFORMANCE EVIDENCE | DEVELOPMENT ONLY / INSUFFICIENT：单图单次、失败纳入，无统计性能结论 |
| OVERALL | NET-01 BLOCKED；本次B运行FAIL，NO-GO NET-02 |

## 6. 交叉核对、剩余风险与最小退修集合

已读取固定f59bb8c的最终`REPORT.md`、`RUN_LEDGER.json`、`B01_EVIDENCE_SUMMARY.json`、`DELIVERY_IDENTITY.json`及owned退出记录，并核对45bdfdb至f59bb8c只增加交付证据/文档/原数据图，没有B后生产代码修改。最终报告与独立发现一致，没有把“native transport子PASS”升级为系统PASS；明确保留目标发出与Nav2接受、三机实体与三机参与、低速事实与停止证书、direct与Wi-Fi、资格28与真实Gazebo的区别。

中间草稿曾仍写B/C NOT RUN及当前未实施I/O修复，它不是最终验收对象，不能当作最终虚假结论。文档收尾发现的“99条消息”误写“flow99”及未限定历史时间的旧状态句，已由生产文档助手在f59bb8c之前纠正；未改原运行证据。最终没有发现与主审结论冲突的PASS声明。主审另目视检查了B既有数据图：覆盖很早停在约57.4%、轨迹局限于出发区，与数据相符，不是新的实验。

尚未排除：无线丢失的精确MAC/队列机制、首心跳空隙具体责任段、长期暂缓循环GC的内存增长、联合仿真WallRate与真实实时系统的差距、运动中断链/恢复、跨地图网络可靠性及实机性能。没有完整的新全流时延/队列重传/AoI统计；不从入口交付总数直接推算全部底层丢包原因，也不把不同时间基准直接相减报告AoI。它们不能凭单个失败或短资格直接升为已证P0；本轮没有新发现的P0证据。

最小退修集合是P1-1可靠Action闭合、P1-2心跳首因、P1-3无线故障停止所有权；不涉及RL重新训练、Nav2调参、地图/起点/阈值选择或NET-02通信优化。准确保留本轮已修的早期日志、迟到响应服务寿命、记录I/O、sidecar收尾、plugin实际正常退出，不因最终失败否认这些有限成果。

**正式NET-01验收：REJECT / BLOCKED；不进入下一阶段。** 已验证的有限工程修补及诚实失败交付可以接收，不代表批准平台通过。本轮3次实际额度已用完，所有失败封存；停止新Gazebo、训练、无线扫描、推送和NET-02。最终代码及轻量报告本地Git备份，原PCAP/bag/rootfs另在本机保留，不能将Git bundle描述为包含全部大证据。

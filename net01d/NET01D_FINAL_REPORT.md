# NET-01D 故障因果审计与有限修复交付

**BLOCKED / NO-GO。** 实际 Corr6201 相位的完整 B 无运动回放在正常段触发三机原 `health_original_sources_stale`：Rsim4.66持有seq45的tb2 correction4.10，年龄.56>.55sim；未完成32wall正常窗口。本轮停止所有后续运行，不做第三轮修补。实际 Gazebo 四臂 **A0/A1/B/C 全部 NOT RUN，0/8、各0/2**；无运动回放不能充当 Gazebo 配对。

独立 worktree `net-01d/workspace`、分支 `net-01d/fault-causal-audit`，起点 `cee0c7024ccf06d88d7ff458a47c39cdf605a7f3`。旧 NET/raw/tag 不改，不推远程。冻结6d权重/701、Frontier、masks、KEEP/WAIT、Nav2、SLAM、实体物理、所有权及原 .3/.2wall、.4/.55sim、.12lag 均保持；没有训练或网络参数搜索。root 已一次重核权重与 Manifest 一致，未重复全树 hash。Native 仍原82bc/ns3.40/V3，无新 build/install/宿主网络修改。

## 结论边界

- 旧 B 的137.930ms主要已定位在新 health 发布返回→C Gateway 捕获，原 ACK 已收到到新 R clock 被处理约175.700ms；旧窗没有逐 handler profile，不能唯一指定 DDS、handler、OS 或全归无线。旧 A09 是另一段：Peer entry间隔333.918ms、health返回335.170ms，guard时新 health 尚未发布，不能强并同因。
- 新首 A1 完整回放复现约1s的整个 tb1 TF 读端延迟，原 correction 源龄合法超线；随后带真实 DDS metadata 的相同负载未复现。**原因 E 保留，不是已修复。** 已收到的6930次take严格匹配源发布 realtime 括号；metadata只含实际source/received timestamp，缺GID/seq不造值，received时间不冒称最早DDS入队。
- 旧 stress5ms 完整 B 的305.029ms收件间隔，由源266.893ms周期与新旧路径延迟增量38.136ms叠加；新包模型内完整交付仅2.037ms。10次Run占143.864wall/142.626CPUms，Run外121.143ms含ACK→新STEP排队77.480ms等分布式选择/同步成本，不能全归纯RF或磁盘。
- 该 stress 的初始World5ms使物理完成E比实际Clock G多5ms。对旧真实A10全部14322、B01全部10951个物理ACK，独立原件核实ACK前已见 **G=E**。因此显式新增 actual-corr6201 初始0模式校准回放；旧默认5ms和全部FAIL保留，未加信用/改量子/放期限。
- 两轮只修外部测试编排：首故障后保活本机服务并等实际清理；再强化为真实Cancel/GetResult回调证据均已记录后才STOP。`cleanup-drain-02`证实三精确UUID Cancel0/GetResult5/PAUSE真、owned空/localfuture0，marker先于STOP；不签物理停止。

## 九次实际无运动记录

| case | 固定源 / wall | 实际结果与限制 |
|---|---|---|
| health-profile-01 A1 | cee0+当时观测diff /21.968 | 16wall独立源，无skip；health全段max266.235ms。未arm、无Goal/89/95，非P5 |
| health-profile-wifi-01 B | 38e0+已审host diff /23.128 | 全段301–313ms超限保留，均seq7 missing_odom→8首ready bootstrap；ready→ready另列<282ms，未arm非P5 |
| full-load-local-01 A1 | 502ba02 /6.371 | **FAIL**：三arm/三Goal后Rsim1.22持有correction.66，.56>.55；tb1三TFwriter源→Rcapture约1s，正常/第四负例未完 |
| full-load-dds-audit-01 A1 | c4e95cf /41.089 | 正常32wall真4/4/5及第四活动本机取消5完成；旧1s未复现，非因果修复 |
| full-load-wifi-audit-01 B | b043830 /10.273 | **FAIL**：stress5ms正常段mask/heartbeat超限；未到第四/radio-off；本机tb2 GetResult仍pending1，不能说清理全闭合 |
| cleanup-drain-01 A1 | 580610d /6.545 | **FAIL**：确已主动停供；原Future.done marker早于GetResult回调记录。后来3结果5不能回填旧marker |
| cleanup-drain-02 A1 | 81710e6 /8.048 | **有限清理回归PASS**：原首error保留，三真实Cancel0/GetResult5/PAUSE/owned空/local0；58.486ms等待、marker先于STOP |
| actual-phase-local-01 A1 | 81710e6 /41.397 | 初相0、RAM；正常32wall4/4/5、第四活动任务真实取消5、原RPC全闭合；已有正常逐样本health/mask离线核验，限无运动接口；非真实物理/SLAM PASS |
| actual-phase-wifi-01 B | 81710e6 /15.316 | **FAIL**：正常段三guard原始源龄失效（tb2 correction .56>.55sim），Gateway failure=null；未到32wall/第四/计划radio-off。首error保留，94.606ms内本机清理marker完成 |

全部0Gazebo/0真实Nav2/0Policy forward/0训练。所有实际PID/退出原件保留，无强杀。coordinator1在预定负例或原首fault时保留，不伪写0；host0只代表预注册判据完成。首P1实际源为cee0+运行时工作diff，38e是事后封存同源，不倒写运行时HEAD。

## 回放合同、观测与比较

源为独立三R进程，经真实DDS进入Gateway：odom30sim/同源TF、双wheel10sim同包、5sim scanheader holder、map→odom50wall latest_scan+.2、200² costmap原strict ROS>.5/5wall检查、map5wallperiod、执行中Action反馈100wall。Peer原400²/.05m/10Hzsim。每源ticks/skips/原header/实际emit保存；Clock停时sim源不刷旧戳，wall流可保持原旧scanheader。不按捕获均值降载。

六完整Grid模板仅从旧bag一次SQLite只读提取，map34800/42740/52816B、三costmap40104B，只替fixture时间字段，cells/frame/origin/shape保持。这是真实规模近似，**不是最大容量上界、真实SLAM或实体物理**。C端真实MergeMapNode产生89，受控真实ActionClient和原journal产生95；明确fixture_origin/Policy_forward=false，三R spy同域fanout不算三次WiFi。

正常阶段从C三facade/merge已就绪、首Goal将发的共同t0计32wall；原guard真实arm，不用fresh注入。三正常Goal期望4/4/5后，第四仅tb3真接受/GetResult已确认pending，才可进入固定.8wall负例。A1停观测而服务保活；B应一次真实RADIOFalse且源继续发布。本次actual B正常先失败，**该计划断链/禁止DDS旁路负例未执行，不能签其通过**。

当前四臂定义：A0真ROS直接且无Gateway业务；A1原完整适配+有序本地队列；B固定V3 B、C固定V3 C。未来共同120sim（用户≤180sim上限）、startup180/autonomy420/outer900/cleanup90wall、10ms token、20ms真实ACK信用、.5RTF计划，均未实际GZ。A1→B含模型CPU/IPC/同步+无线，不是纯空口。旧stress A1 Disk/B RAM差异披露；新actual A1/B统一RAM完整证据，仍有A1空业务Native与B真实网络计算差异。

被动埋点仅profile开启：raw health publish→C entry/serialize/send→Hub queue/flush/ingress→R decode/原guard intake；原wait/handler/pump/journal长span及ThreadCPU保留。TF metadata executor仅覆写固定SDK的同一次take，原消息/None/异常/执行闭包不变；没有新线程、QoS或调度规则。活动期RAM，结束后持久化。必要0Node验证仅一次实际模板generated消息往返/时间字段复原相等（exit0/2.392s）及SDK take透明性6检查（exit0/1.608s）；后者不构造executor、不init ROS/Node，不充实际DDS生命周期PASS。

## actual B 首故障的最终责任段

最早tb1于mono519992.417146585、Rclock4.66锁存原sourcefresh；tb2/tb3随后相同原因。旧seq45 correction为4.27/4.10/4.27，所以tb2年龄.56>.55；odom年龄.19sim、health receipt约218.7ms，**不是.4sim odom或300ms heartbeat首错**。新seq46本身ready、correction4.27/4.30/4.27，原guard先tick已持有旧interval，不能让新包擦除原FAIL。

1765次TFtake全部strict source_timestamp匹配实际发布realtime括号；九writer从首发均matched1。所有三TF topic/三writer kind都有持续等待：source→take中位616.900–638.871ms、最大926.126ms；source_timestamp→RMW received_timestamp最大3.171ms，主要其余等待发生在该middleware时间戳→实际Rtake之间。**received_timestamp不是独立证明最早DDS到达/reader-ready**，仍不能唯一分executor调度与middleware内部。首fault前源继续生成4.67/4.70/4.67的校正、ticks skip0，并非源停产；tb2最新4.70发布于519992.412514743。

没有≥10ms的单wait或ROS handler；最大外层poll226.947wall/226.103CPUms包含交替handler与pump。证据支持持续R输入积压/服务吞吐不足，未证可不改语义的唯一SDK逻辑Bug，不再用局部性能猜测启动第三修补。终止时未take的尾ordinal是右删失，不称已证DDS丢包。

全部466个实际Mock物理ACK处G=E，原20ms信用保持；首token至末ACK推进4.66sim/10.491027wall，RTF.444189（含startup，非正常32评分），pacer最晚1229.677ms。相位校准真实生效，单靠相位没有消除源龄FAIL。见 [原小证据](health/actual-phase-wifi-01/FINDINGS.md)。

## 实际接口、清理和证据完整性

actual A1：正常三结果4/4/5，反馈2515/2426/2470；第四UUID `0000000078c3ffc00301000000000000` 真实接受且最终5。无FIRST_FAILURE；正常RPC_DRAINED三guard armed/faultNone/reasonNone、全部9计数0。NEGATIVE_DONE本机5/三PAUSE/local0。最终Gateway END真/executor[true,true]/RPC与确认全0，persist1.604756s；空业务native RAM1111972B完整copy.005475s。1740个MockStep全10ms、E整10ms，不是实际ODE证明。已有原件的主审授权离线补数（不是新实验）：正常32.000902911wall /16.01sim，RTF.500298；三机各160次health均armed、无fault，receipt max221.852/221.824/225.383ms；各160mask全accept、0reject，真实receipt bracket gap upper max228.158/225.333/225.110ms。按实际Rclock的intake采样，新odom≤70/correction≤40simms；持有旧odom≤170、旧correction≤130/130/140simms，不冒称全部guard timer连续max。正常TF6719次strictjoin，receivedTS→take max111.292ms（receivedTS非首入队证明）；正常1600物理ACK均G=E、credit≤20ms。每机normal480odom/odomTF、160双轮、correction1597/1597/1600、map6/costmap27，final配置skip全0。[正常机器原件](health/actual-phase-local-01/normal-window.json) / [可读分布](health/actual-phase-local-01/RESULT.md)。

actual B：三正常Goal真实进入受控服务并各收到525反馈，C结果仍未知。首错后本机三UUID真实清理证据见独审组件；LOCAL_CLEANUP_DRAINED519992551240490先于STOP519992556999037，等待94.606ms，owned空/localfuture0/三PAUSE真。中央三GetResult仍pending，R各一response待确认，executor[false,true]保留；不假闭合、不把中央UNKNOWN当成Nav2拒绝。Gateway resourcesdestroyed/END真、persist.499055s、native0；RAM158800339B全部copy.214303s且原件保留。含6条Link为4773入口/4593完整；业务4767入/4587完整，已交付N p95=6.108973ms/max21.800361ms。首guard前4422条入网最终全完整，不代表wallfresh或源DDS零丢；总180未收中177在故障后最终N4.65入网且无后续推进，不能称180条全部无线丢失或零丢包。关键health45/46三流六ID都实际RX，最大2.771138Nms，不以猜测无线丢失替代首源龄因果。

此前stress完整B业务2927入/2803完整，124截至未完整中103在首guard后最终N2.64入网却未继续推进。已交付模型内全业务N p95=5.926429ms/max19.145048ms，另P1 B p95=6.584ms。MAC/PHY两条健康分片实际串起AP→STA→UDP→完整RX。**N不是Linuxwall，也不是纯PHY传播。** 真实PHY存在、native结果PASS/完整copy不能覆盖原guard FAIL。

首A1的95八pub仅三spy各收7；stress完整B89四/95六完整C-R及三spy实际收4/6。各历史缺项原样保留，不补成全送达。Action原同RPC/UUID/CDR/确认去重保持，GetResult长等与传输确认分段；不是TCP，不合成accepted/Result，不清pending造PASS。

## 用户原11项门禁

采用用户规定等级；有限PASS仅签已测范围，root/metric独审另行固定。

| 原门禁 | 等级 | 证据与边界 |
|---|---|---|
| RL FROZEN INTEGRITY | **PASS** | 6d/701及核心行为保持，沿用主审一次身份核验，无训练 |
| GATEWAY CORRECTNESS | **BLOCKED** | 清理生命周期有限修复有实证；actual B正常未过，完整无饥饿/服务吞吐保证未建立 |
| HEALTH TIMELINESS | **FAIL** | actual B correction .56>.55sim，非300ms heartbeat首错；A1正常时效仅对应范围PASS |
| ACTION RELIABILITY | **BLOCKED** | 真实CDR/UUID/终态/本机取消正证；B中央3GetResult未知、R响应待ACK，不假闭合 |
| ROS MESSAGE INTEGRITY | **PASS** | 实收Goal完整CDR、89/95 body Counter、实际consumer/journal字段相等；不含零丢保证 |
| CLOCK CONSISTENCY | **PASS（有限）** | actual A1正常1600、B全466 ACK G=E、信用≤20ms；本轮GZ未运行，不等全部wall时效 |
| NO DDS BYPASS | **FAIL** | 本轮全流负例证据未闭合，**非已证旁路**；B正常先失败，第四/radio-off未到，静态路径/旧F05子测不替代 |
| WIFI PACKET EVIDENCE | **PASS** | 原V3真实MAC/PHY/PCAP/UDP重组和双向whole-CDR；限有原件的路径，不是零丢 |
| SAFETY SEMANTICS | **PASS（有限）** | 原gate合法锁存，不清unknown/造Result；本机精确Cancel0/GetResult5/PAUSE及marker先于STOP，非实体停稳 |
| GAZEBO CLOSED LOOP | **BLOCKED** | 全部NOT RUN，0/8 |
| CAUSAL ATTRIBUTION | **PARTIAL** | 已分离模型Ndelay/来源/输入等待；DDS内部与executor/CPU具体首因未唯一，旧E保留 |

整体 **BLOCKED / NO-GO**，不自动进入下一阶段。

## Gazebo四臂表（不混入无运动结果）

| 臂 | 定义 | 实际GZ/上限 | 状态 | 覆盖/T90/T95/路径/真实Goal/延迟/物理停止指标 |
|---|---|---|---|---|
| A0 | 原ROS直接，无Gateway业务 | 0/2 | NOT RUN | **NOT MEASURED** |
| A1 | 同适配/Action确认去重/端点/日志，本地有序后端 | 0/2 | NOT RUN | **NOT MEASURED** |
| B | 固定V3 B真实WiFi | 0/2 | NOT RUN | **NOT MEASURED** |
| C | 固定V3 C真实受限WiFi | 0/2 | NOT RUN | **NOT MEASURED** |

共同计划120sim≤用户180sim上限；旧GZ不移入此表，未为填表耗用预算。

## 无运动实测pre-delay/Ndelay及失效原因

| 条件 | 网络前/输入等待实测 | 模型内Ndelay | 实际失效/结果 |
|---|---|---|---|
| actual A1正常32wall | 6719TF strictjoin，receivedTS→Rtake max111.292ms；完整publish→Hub-admission pre-delay分布 **NOT MEASURED**，不拿该等待替代 | 业务走本地队列，Native业务0；WiFi Ndelay **NOT APPLICABLE**，不能填0假比较 | 正常无fault；随后计划停供导致原保护/第四真实取消5 |
| actual B截至首错/收尾 | TF source→Rtake中位616.900–638.871/max926.126ms；sourceTS→receivedTS≤3.171ms。该段在Rcapture前，非空口；完整publish→Hub-admission pre-delay分布 **NOT MEASURED** | 完成者全case N p95=6.108973/max21.800361ms；seq45/46六health均RX/max2.771138Nms。非Linuxwall/纯空口 | R4.66旧seq45的tb2corr4.10=.56>.55sim，normal32/第四/radio-off未达，C未知保留 |

Ndelay分布只针对完成者，未收者不填零/无穷推算；此B表含bootstrap/故障收尾，不冒充完成32wall正常证书。已有P1/stress数据属于另case。

## A–E分类与证据强度

| 类别 | 本轮事实 | 强度与限制 |
|---|---|---|
| A 软件/适配Bug | FIRST_FAILURE共享STOP过早撤本机服务；Future.done早于done_callback，marker证据未排空 | **CONFIRMED** 生命周期缺口；两轮harness修补、cleanup02及actualB收尾有限验证，非旧heartbeat根因 |
| B 实现调度开销 | actualB九TFwriter长等待，外poll226.947wall/226.103CPU含交替handler/pump；stress十Run外同步空窗 | **OBSERVED** 排队/吞吐成本；唯一handler/SDK逻辑Bug仍是**假说**，未证即不改业务/QoS |
| C 已证WiFi | 原V3真实MAC/PHY/重组、完成者Ndelay；截止未完成含停止horizon截尾 | **CONFIRMED路径/Ndelay**；不把617ms读端等待或180条未完整都归空口/永久RF丢失 |
| D 合法保护 | .56>.55原sourcefresh锁存，接新包不擦旧interval；精确UUID本机取消/PAUSE，C未知不伪成功 | **CONFIRMED** 正确失效边界，不是误报/放宽阈值理由 |
| E 未解底层 | 旧137.93ms、首A1约1s、actualB队列等待中executor与middleware具体责任 | **UNRESOLVED**；旧窗未复现不等已修，不强归OS/GC/无线 |

Mock stress5ms是事前声明的压力条件，**不是软件Bug**；actual-corr6201是有真实原件支持的fixture合同校准，旧stress FAIL永久保留。

## 重点原始路径与PCAP索引

相对路径以本报告目录net01d为基准；GB raw原处保留而不纳入Git。

| 内容 | 索引 |
|---|---|
| actualB首fault/本机清理/退出 | runs/actual-phase-wifi-01/{FIRST_FAILURE.json,LOCAL_CLEANUP_DRAINED.json,process-exit.json}；gateway/network-gateway.json |
| 三独立源/Peer/DDS/控制 | 同case source-tb1/2/3/、peer/、mock-physics.json、time-controller.json；health/actual-phase-wifi-01/{first-fault.json,summary.json,phase-credit.json,FINDINGS.md} |
| Hub/native与4PCAP | 同case hub/{hub-ingress.json,hub-deliveries.json,native-control-boundaries.json,result.json}；hub/native/{packet-ledger.jsonl,wifi-0-0.pcap,wifi-1-0.pcap,wifi-2-0.pcap,wifi-3-0.pcap} |
| RAM原件与copy | /dev/shm/net01d-full-load-actual-phase-wifi-01、对应local-01保留；各hub/result.json逐文件记录exit后copy字节/耗时 |
| actualB关键health | seq45/46 nativeIDs4455/4456/4457与4577/4578/4581均wholeRX，见review/ACTUAL_PHASE_WIFI_01_NETWORK_DELIVERY.json/md；本case未另解析PCAP，不伪造帧号 |
| 既核MAC/PHY分片链 | review/FULL_B_PHY_MAC_CHAINS.json保留stresscase healthIDs2646/2815的ledger行/UID链，不冒充actualB逐帧核验 |
| actualA1正常数字 | health/actual-phase-local-01/normal-window.json、RESULT.md，及对应runs实际client/source/GW与markers |
| Action/89/95/UNKNOWN | review/ACTUAL_PHASE_{LOCAL,WIFI}_01_COMPONENTS.json与REVIEW.md；原source-tb1/2/3/full-source.json、client/full-client.json、GW对应记录 |
| 两轮清理原FAIL与回归 | runs/cleanup-drain-01、02的ACTIVE/LOCAL/STOP、cleanup-regression.json、process-exit.json，01不覆盖 |
| 旧长等待/真实GZ相位 | health/HISTORICAL_FINDINGS.md、historical-gap-supplement.json、real-gazebo-phase-01.json，原NET所有raw仍旧worktree |

## 停止条件与仅建议的下一诊断方向

actual相位B正常出现原关键源龄FAIL，两轮修补用完，已触发停止条件。全部owned角色实际退出、无强杀，Native结束及完整copy有据；首fault/中央UNKNOWN不清除。停止ROS/ns3/Mock/GZ试验及运行源码修改，不因空表启动A0/C/GZ，不训练/推进NET02/推远程。

如未来用户另批有界计划，最小诊断方向仅为**区分已定位的R TF middleware timestamp→take等待属于哪段执行/队列**，复用现profile、同一次take及source ordinal对已有owner时间段细分；不先换executor/QoS/优先级，不改混合源合同、保护阈值或信用。旧137ms未被本次唯一解释；SHM/TCP/放宽门限不能由本结果直接宣称会解决。这里只建议，**本轮没有实现或运行授权**。

两轮修复已用完，没有第三轮参数/调度/业务修补，没有A0/C或Gazebo试验。本轮收束源码、原失败和最小可审证据，由root固定本地提交、独审和Git备份；不推远程。源差异及15个重要运行源一次SHA见 SOURCE_DIFF.md / DELIVERY_IDENTITY.json；本地交付commit由root固定，不再新增实验。

[计划](PLAN.md)、[故障清单](FAULT_INVENTORY.md)、[九例账本](RUN_LEDGER.json)、[独审组件](review/)、[health因果分析](health/)保留所有首次失败与观测限制。

最终独立验收见[独立评审](review/INDEPENDENT_REVIEW.md)，结论同为BLOCKED / NO-GO。关键文件校验见[SHA256清单](SHA256SUMS)；本地完整封存提交、Git备份及原始数据位置在提交完成后记录于阶段外层[最终身份](../../FINAL_IDENTITY.json)。实测源码完整提交为`81710e6739311a59ed4bef945a0fbd871d274a64`，不将文档封存提交伪称为实测运行源。本轮无远程推送。

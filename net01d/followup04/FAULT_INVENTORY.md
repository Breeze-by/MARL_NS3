# NET-01D故障与未决事项清单

当前整体 **NO-GO**。本清单区分原故障、已修实现/报告问题、有限验证和仍未知的原因。新合同通过或高覆盖不会改写旧失败；修补/观测夹具不是对应历史回合通过。C已完成并有限接受；Gateway首阶段已一次导出，native条件cohort单stream已完成；最终裁定/commit留Root，本清单不触发任何运行。

## 严重程度、归因与最小遗留集合

严重程度针对缺陷影响；已修问题保留原等级。A=已证软件Bug，B=实现/调度成本，C=已建模通信影响，D=合法安全响应，E=未解决。归因等级与是否达到探索阈值分别判断。

| 项目 | 级别 / 分类 / 证据强度 | 定位与影响 | 最小处置及后续验证 |
| --- | --- | --- | --- |
| F04-06 控制器实际退出失败 | **P1 / E / OBSERVED；CAUSE NOT VERIFIED** | [原完整栈](analysis/gz-simhealth-a0-01/small-raw/control-tail35.txt)、[独审](analysis/gz-simhealth-a0-01/INDEPENDENT_REVIEW.md)。`rclpy.spin`消费转换异常、controller1，使直接参考完整性未闭合 | **当前唯一系统验收阻断项**。保留透明取证，先定位实际topic/type/异常与停止时序；不得吞异常或盲改冻结策略。修复后需原条件有界验证controller正常退出、真实停止及UUID闭合 |
| F04-07 非零退出漏报 | **P1 / A / CONFIRMED，已修** | 当前`net01/host_run.py:207`要求actual controller0；原门使controller1仍得到host0/networktrue | 197a最小外部报告修补；[五种实际子进程验证](evidence/controller-exit-reporting-01/RESULT.md)通过。未来不允许以保存或外层0代替controller状态 |
| F04-02 未ARM就启动全局运行超时 | **P1 / A / CONFIRMED，已修** | `net01/time_control_state.py:43`实际ARM一次激活；初始化停顿原先被当作运动期故障，阻断启动 | 2be修补已有49unit/19ROS及后续完整任务验证；原物理RPC2wall和startup180继续有效，不重放原失败为成功 |
| F04-05 安全收尾后Gateway进程被旧退出期限终止 | **P2 / A / CONFIRMED，已修** | `net01/run_network_case.py:377`停后监督；B1真实安全停止后Gateway−9，证据与过程验收失败 | aae仅在实际安全与资源闭合后给固定证据阶段；四分支负例及B02/C正常退出已验证，保存卡死仍失败 |
| F04-01/03 记录器锁与缺件 | **P2 / E / OBSERVED，唯一锁因未证** | [锁故障时间线](analysis/gz-simhealth-a1-01/BAG_FAILURE_TIMELINE.md)。原指标不可验收，不能补造metadata | 禁止运行期打开活动bag/SQL；后续原append观察与停后一次canonical已实施。不能由后续正常倒推旧锁owner |
| F04-04 原tb3导航abort | **P2 / E / OBSERVED，CAUSE NOT VERIFIED** | 原01运行期status6，非已证收尾取消 | 保留原失败；没有日志支持时不修改Nav2或归咎RL。需对应UUID和内部planner/controller现场才能定修法 |
| F04-08/09 DDS诊断工具 | **P2 / A及E / 工具Bug已证；ROS原因未证** | 第一次就绪发布竞态已修，未产生信号样本；第二次有信号但超时，诊断不确定 | 原件保留，不追加合成重试或将工具结果当机器人资格；没有证据时不改系统库或忽略原异常 |
| 当前Gateway墙钟与native服务成本 | **B/C / OBSERVED，局部SUPPORTED** | [Gateway摘要](analysis/costs-four-arm-01/SUMMARY.md)、[native独审](analysis/native-costs-01/INDEPENDENT_REVIEW.md)。模型服务含TCP/队列/WiFi；墙钟还含计算与耦合 | 分开报告时钟、母数与阶段；不把合法成本一律当Bug，不把条件已消费样本当全输入丢包率或纯RF份额 |
| 旧wall300过期后的停止 | **D / OBSERVED；上游含B，个别成因E** | 旧源周期及延迟变化实际使状态过期，保护按原规则触发 | 保留旧停止和UNKNOWN。新sim300是用户批准的新合同，不是证明旧wall300已修复 |

当前没有新证实的P0。未测的每包CPU/airtime、旧137.93ms唯一原因与历史缺失现场保留为研究限制；不以虚构修复扩大该最小遗留集合。

## 本轮实际故障与处置

| ID / 原case | 已证事实与原结果 | 当前处置/验证 | 仍未解决或不得推断 |
| --- | --- | --- | --- |
| F04-01 `gz-simhealth-a1-01` 记录器 | bag抛SqliteException/SQLITE_BUSY5，随后进程存活门fatal；自主156.2/180sim，原FAIL | 保留全部原件；此后live阶段禁止任何activebag打开/只读SQL/PRAGMA，仅原append日志/exactowned观察 | 真实锁owner、各query精确起止与exception mono缺失。获准只读SQL可能干扰，但不能认定唯一因；不能把约41s前writer日志当同一时刻。未调SQLite超时/关闭录制 |
| F04-02 `gz-simhealth-a1-02` 启动 | 未ARM/noGoal时globalRUN watchdog已计龄；lastRclock.02→fault2.000528899wall，下一.03晚78.382443ms；原preflightFAIL、0NN/Goal | source2be使clock/native全局保护从same-session任一真实RGuard ARM一次启用，actual progress stamps不伪刷新。49unit/19ROS、新A1Full与A1-03业务验证 | 原败保留；physicsRPC2wall所有mode、startup180、LocalStop2wall、源龄/receipt门不放宽。不是取消进度保护 |
| F04-03 canonical缺件，01/02 | 01缺bag metadata；02无controller journal。原canonical各一次在DB读取前失败 | 未造metadata/journal、跳坏shard或补停后地图 | 覆盖/T50…T98为不可验收/不适用，不是0覆盖或“阈值未达” |
| F04-04 01真实tb3 abort | 自主阶段真实status6，早于bag fatal约78.7s；不能归收尾PAUSE | 原abort与FAIL保留，没有调整Nav2/DWB/Policy | 原UUID/内部Nav2失败原因细分仍UNRESOLVED；不是仅凭停稳就可取消的故障 |
| F04-05 `gz-simhealth-b1-01` poststop | 180sim/原R指标和停止/ownership成立，但GatewayROS727580按INT20→TERM5→KILL退出−9；nativeleaf/Hub0，host1/networkfalse | aae仅加有真实安全闭合证明的证据退出阶段，固定总≤60且夹原cleanup/outer/host界；4分支mock资源actual-method夹具通过，B02实际Gateway/host0 | 原B1FAIL不改；saved不是exit0。persist19.589717s不是全部退出成本，saved至kill约3.74s内部GC/析构/返回细分无栈、UNRESOLVED；不是把nativeleaf误记−9 |
| F04-06 `gz-simhealth-a0-01` controller | 180sim与有效R指标成立；预算后SIGINT请求事件后观测controller实际exit1，栈在rclpy `_take_subscription→take_message` RuntimeError；A0 **PROCESS FAIL/NOT ACCEPTED** | 原trace、raw host0/runner0/networktrue及独立物理stop/PAUSE/UUID闭合均保留；无A0重跑/异常吞掉 | 栈缺exception mono/topic/type；SIGINT、转换、对象生命周期的唯一原因UNRESOLVED。真实status5不是已捕获Cancel caller/GetResult5时序；不能用T95=37.47或raw0抹掉controller1 |
| F04-07 controller非零漏报 | 原完整性门漏要求实际controller0，所以F04-06原raw仍0/true | 197a只补actualpoll退出证据及host/network gate；真实短child0/1、未创建、仍活、marker缺失5case通过；非0/未知均fail | 报告门修复不是rclpy异常修复；不回写原A0host码，也不冒称历史A1/B02运行过197a新门 |
| F04-08 DDS工具run-01 | ready文件直接x-open后dump，父读到空JSON；0publish/0SIGINT，exit1；失败清理child−15 | 原件保留；仅save采用既有同目录tmp写完→rename，另立run-02 | **工具失败/NOT_TESTED**，不是目标RuntimeError或NOT_REPRODUCED |
| F04-09 DDS工具run-02 | 240publish/160104B、12s20Hz目标/1SIGINT；5s无receiver退出/异常/cleanup，父TimeoutExpired/exit1，清理child−15 | 父子gone/domain97清空；无第二SIGINT、额外消息、run03或seed矩阵 | **INCONCLUSIVE**。供给先停后发信号，之后无DDS输入；无live栈与Python handler执行证据。不能当稳定复现、完整未复现、异常修复或真实GZ负载覆盖 |
| F04-10 观测透明性 | 历史A0失败时没有所需订阅/异常mono | bd663仅在外部bootstrap原spin调用外观测BaseException/现有frame公共topic/type/raw并bare raise；窄controller pre-signal mono；4合成分支与AST/event透明检查通过 | 不改系统/private_take/信号或原catch；KB文件不等于故障。合成RuntimeError不是DDS复现，不补造历史topic/type或唯一cause |
| F04-11 C与成本 | C一次完成180sim/11UUID全4/controller及主要进程0，R T95=37.15、末99.890732%；Gateway四组一次导出完成 | C有限诊断接受；Gateway适用匹配无missing/ambiguous、缺测/原A0FAIL保留；native单stream已由另agent按Root独准完成各1open | 普通KeyboardInterrupt被原frozen处理不等于A0 RuntimeError修复；单轨迹不证明RF/CPU优越。native服务时间已有条件cohort统计；每包CPU/wall份额UNMEASURED，不能填未测值 |

证据入口：[最终报告](NET01D_FINAL_REPORT.md)；[01](analysis/gz-simhealth-a1-01/RESULT.md)、[02](analysis/gz-simhealth-a1-02/RESULT.md)、[B1](analysis/gz-simhealth-b1-01/RESULT.md)、[B1退出审计](analysis/gz-simhealth-b1-01/GATEWAY_EXIT_AUDIT.md)、[B02](analysis/gz-simhealth-b1-02/RESULT.md)、[A0结果](analysis/gz-simhealth-a0-01/RESULT.md)/[独审](analysis/gz-simhealth-a0-01/INDEPENDENT_REVIEW.md)、[197a五case](evidence/controller-exit-reporting-01/RESULT.md)、[bd663四case](evidence/spin-exception-observer-01/RESULT.md)、[DDS01](sigint-dds/run-01/RESULT.md)、[DDS02](sigint-dds/run-02/RESULT.md)。这些是小报告/缓存入口；本次文档工作没有重读Gateway/native/bag/PCAP。

## 跨轮旧失败与候选边界：全部保留

| 历史项 | 保留的实际结论 | 本轮不能如何改写 |
| --- | --- | --- |
| 旧wall300健康/mask时效 | f02 B3/B4分别6.27sim/0.61sim首败；B3 gap322.415wallms、B4 gap307.664wallms；pace10 Full也曾mask间隔304.597wallms首败 | 新授权sim300不是旧wall300被修好。新profile改变时效合同/实际wall业务率/输入时机，须重新建立同条件四组参考 |
| f03最终真实WiFi B | `gz-raster-b1-01`自主3.72sim/8.425wall、0NN/0Goal，原maskreceipt约320wallms>300触保护；整体FAIL | 旧wall合同、原seal失败/UNKNOWN/保护证据保持；新合同长任务不能回签它PASS |
| clocklane候选 | SDK15check仅有限通过，B/A1 Full都曾源龄首败；实际R已3.26而旧odom2.85为.41>.4，非已证future-clock错误；最终profile撤掉额外lane | 不把SDK当Full/GZ，也不说一切根因是clocklane或放宽源龄；当前不含该lane/新reader方案 |
| ARM one-shot测试源bootstrap | `tcp-raster-local-01`已收到merge但3ARM暂态拒绝后future未重置，0Goal/未进入normal | 91bee只修测试源安全ARM握手，原失败不是本地性能结论；未改Guard/Goal重发层 |
| RAM ledger错误尾证据 | B4异常finally旧Hub直接TERM native造成RAM账本缺失；owner-reset错误路径有定向修复与负例 | 原丢失证据不可恢复。RAM模式未采用；完整serial/4PCAP保留，不为性能弱化失败证据 |
| 历史137.93ms窗口 | 原窗口缺逐函数边界，精确栈与唯一原因 **UNRESOLVED**。后续另窗127.313ms journal读取长阻塞/低CPU/D态有证据，O_NOATIME定向后新例未再出现同长读 | 不用后续窗口、SQLite或任何新例反填137.93ms唯一根因，不把全部等待归WiFi损失 |
| 观测/CPU候选 | 原LTO、RAM/PCAP/采样都有各自有限范围；native-copy fixed pair无CPUgain，Python-frame局部微收益未接生产；profiling工具失败/部分DSO范围保留 | 不能把单一诊断开销比例外推全GZ或宣布一个函数主导；未减少4PCAP/全ledger，未推广copy/测量shim |
| raster首次CDR夹具差异 | 首次rawCDR比较失败，实际差在已定位3B对齐padding；独立序列化自比较证实padding波动，r2仅比较副本排已知padding，其余字段/data位同 | 原首败保留；不能说全部rawCDR逐byte相同或少量边界测试是全域数学证明。当前broadcast-v1只做已测实现替换、无缓存/源率改变 |
| 停止/daemon/旧原件 | 历史seal失败、centralUNKNOWN、case-owned ROS daemon漏登记与后来标准补清事实分别保留；Domain69不动 | physicalstop/emptyownership/END或补清不洗掉原过程失败，不把补清后的gone说成原自动登记已实现 |

跨轮权威说明：[f02最终报告](../followup02/NET01D_FINAL_REPORT.md)、[f03最终报告](../followup03/NET01D_FINAL_REPORT.md)及其独审/一次读取清单。原失败run、tag v1.1.0、冻结6d Policy、原场景/物理/Nav2/SLAM及消息语义不被本清单覆盖或重写。

## 合同与资格尚未闭合的事项

- 当前新profile仅health/mask收件.3使用实际R ROS sim；原monotonic日志、源龄.4/.55sim、Peerodom.2wall、Gatewaystatus.3wall、独立2wall/原stop12和冻结行为各自保留。旧wall300未修，未验证实机/真实WiFi的相同安全效果。
- Gateway四组stage已导出；实际正常每包exactreceipt_sim仍UNMEASURED、B02/C条件模型服务已有单stream统计，每包CPU/wall份额仍UNMEASURED；没有用source header/generated_sim代替收件。已测native服务时间仍含TCP/队列/WiFi/重组，不是纯airtime或每包CPU。
- A0过程FAIL；C仅有限诊断接受；每组一条轨迹不能隔离纯RF/adapter因果或证明策略自然完成。没有训练/新策略、NET-02、实机部署或新的性能GO。
- 后续只按Root明确授权推进当前已锁case/离线读取；该文档不授权重跑、延预算/阈值、删日志、改协议或安装环境。最终交付commit与总判定由Root补定。

C与Gateway新增小证据：[C RESULT](analysis/gz-simhealth-c1-01/RESULT.md)/[独审](analysis/gz-simhealth-c1-01/INDEPENDENT_REVIEW.md)、[Gateway SUMMARY](analysis/costs-four-arm-01/SUMMARY.md)/[read manifest](analysis/costs-four-arm-01/read-manifest.json)。Peer p95是入口→health发布返回wall跨度，不含末尾event JSON追加、不是完整callback/CPU；数据未重算。C observed普通KI/cause-contextNone/controller0与历史A0转换RuntimeError明确分开；61.312681ms仅pre-send→观察差，不证明唯一cause。

Native最终新增：[SUMMARY](analysis/native-costs-01/SUMMARY.md)。B02/C原ledger各完整1stream，10799/10801条件ID全match，p95服务17.317561/53.256243simms。无Gateway/bag/PCAP重读。该cohort不是全输入loss母数，模型服务不是纯RF/airtime，逐包CPU/wall仍未测；A0FAIL/整体NO-GO不变。

最终证据门与预算入口：[11项Gate/7问](NET01D_FINAL_REPORT.md)、[交付身份](DELIVERY_IDENTITY.json)、[外部生产差异](PRODUCTION_DIFF.patch)、[实际预算账本](RUN_BUDGET_LEDGER.json)。本轮7GZ/210forward/1056.2sim含失败，0训练；Gate为生产者限定建议，Root最终裁定。原ROS完整消费/A0controller1仍FAIL、Gazebo与因果PARTIAL，整体NO-GO，不进NET-02。

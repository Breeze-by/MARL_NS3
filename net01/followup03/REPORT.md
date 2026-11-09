# NET-01 followup03：工程诊断与有界修补，整体仍 BLOCKED

本轮修实了部分通信执行代码问题，并在无运动真实 Wi-Fi 满负载下通过一次有限资格；**没有完成新的 Wi-Fi–Gazebo 探索闭环**。三次实际 Gazebo 启动额度已用完，累计92次。B/C未运行，不进入NET-02，不追加实验、训练或推送。

读者最应关心的实际结果是：A07只自主9.96仿真秒，三机各收到一个目标并运动，随后因中央Peer的里程计接收间隔超限停止；末收到地图的原始覆盖49.6336%，但13帧地图全部质量无效，不能称有效覆盖。A08仅自主0.11秒，尚无NN或目标就触发心跳保护，且末停止认证缺真实请求日志。两次均是FAIL，不能用代码改进或短夹具成功替代。

## 固定内容与共同执行配置

冻结发布a014ef11、行为76fd91、checkpoint6d4c51、701输入/ROI/候选/联合掩码/生命周期、原DWB、SLAMfine=.75、地图与共同三角不改。V3无线参数不改；源龄.4/.55sim、odom接收.2wall、heartbeat.3wall、clocklag.12sim、几何与原停止认证都保留。0训练/权重更新/NET02/系统网络更改/push。

新共同执行配置在结果前登记为**pace500-clock100-q10ms**：只把外部effective world的墙钟update_rate设500，物理积分dt仍.001；只对gzserver显式传/gazebo.publish_rate100的YAML；Gateway每STEP最多.01sim，仍只推进到真实已观测horizon，固定anchor不重锚。一次0Node生成检查确认原Nav2/SLAM配置不变。IncludeLaunchDescription不提供LaunchContext隔离，未将其误称scoped；Nav2各自显式params_file不混用。

这是新的时间执行profile，不是网络或RL优化。Gazebo传感器sim频率与Nav2等WallRate的相对关系会改变，因此未来A/B必须同profile，旧180/600秒成绩不能直接配对。synthetic资格仍保持原每wall秒TF/odom/feedback数量，CPU负载更保守，但不证明真实Gazebo较低odom频率下的receipt-gap。

## 全部尝试与失败账本

计时单位分别注明CPU毫秒、墙钟秒和Gazebo仿真秒；没有跨时钟直接相减推断无线时延。机器可读记录和具体原件链接见[RUN_LEDGER.json](RUN_LEDGER.json)。

| 尝试 | 层次 | 实际结果与边界 |
|---|---|---|
| startup-01工具入口 | 无GZ | bwrap缺/diag挂载点，未启动ROS/GDB inferior；失败保留，不计实际GZ |
| startup-02（实际1，累计90） | 60wall GDB三机启动 | 三spawn，无SIGSEGV重现；Peer PYTHONPATH/import工具缺口，不能称完整基座健康/物理停止PASS |
| continuous15 | 真实Wi-Fi/synthetic clock | FAIL；原clock保护在native首大payload输出前触发，不是先由大stdout背压造成 |
| native-cpu-burst-01 | 0ROS原生CPU诊断 | .1sim Run166.469CPUms；自有回调exclusive30.94%，69.06%未分配，含测量开销，不全归PHY/PCAP |
| pace-launch-generation-01 | 0Node配置生成 | 12项有限PASS；world只改wall update，原dt/导航参数保留 |
| continuous16 | 新profile、旧ns3库 | FAIL；原clocklag仍超线；故障后排IPC修补让END/native正常退出，不追认运行PASS |
| serial固定burst | CPUprofileoff基线 | Run118.963CPUms，7883条captured=written |
| async固定burst | 记录线程候选 | 完整payload/stdout/PCAP与除mono外ledger全等；RunCPU只降3.43%、总CPU增18.03%，拒绝默认采用 |
| Release-portable独立构建/固定burst | 同ns3.40源新依赖 | RunCPU118.963→77.038ms，降35.24%；相同事件/payload/stdout/PCAP，7883完整记录，仅固定burst等价证据 |
| continuous17 | 新profile+Release，真实Wi-Fi | 有限synthetic资格PASS：三机各80批ready health/mask、maxlag.09sim；12376入网中12052整消息完成，324未完整交付，非零丢失 |
| A07（实际2，累计91） | 真实GZ、direct适配 | FAIL；9.96sim、1NN/3accepted/反馈与运动；receipt超.2wall，原物理停稳/3PAUSE/本机UUID闭合，但中央未决RPC保留 |
| continuous18 | 0GZ direct/profile | A07的175ms空窗未复现；R ready-query单段65.99ms CPU，反馈捕获有缺额，不能称零丢失 |
| A08（实际3，累计92） | 真实GZ、direct诊断 | FAIL；.11sim/0NN/0Goal，三guard心跳超.3wall；GC证明另一长空窗机制，未解释末heartbeat；末认证因缺journal失败 |
| continuous19 | 0GZ、Gateway暂缓循环GC | 有限机制PASS；存活阶段实际GCfalse/0自动事件、close恢复原true/阈值，已捕获CDR全部等价到达；不替代真实GZ回归 |
| B / C | 真实GZ Wi-Fi | **NOT RUN**；最后预留B额度前瞻重分为A08诊断，没有新Wi-Fi机器人性能结果 |

旧15b53报告、02原件、全部首次失败、工具缺口及上述失败目录均原地保留。startup诊断由独立helper隔离运行，原件在[辅助目录](../../../gz-startup-followup03/README.md)。A07前只读inventory误匹配自身bash命令文本，原clear:false保留于[A07_PRESTART_OWNED.json](A07_PRESTART_OWNED.json)；它不证明有旧actor，独审确认后本次仍按唯一READY执行，没有补扫或清理无关domain69。

## 已证机制与实际代码

15的首clockfault发生在STEP开始37.565ms后；首大输出在54.926wall/54.927CPUms后才开始。后续hub owner.drain/native stdout卡住是后继现象，不倒作首因。[原始阶段摘录](MEASUREMENT_15.json)。故障后Gateway现在继续非阻塞排真实IPC/保存ACK和payload，在receive副作用前拒绝业务，不重发到Policy/Nav2；通道关闭只记一次，原firstfault与本机停止继续，closed不伪造END。

CPU测量没有支持继续盲调代理小参数。标准库异步ledger语义比较通过，但总CPU增加、整轮wall几乎无益，保持opt-in默认off。[拒绝依据](ASYNC_LEDGER_PAIR_SUMMARY.json)。更直接的同源Release-portable独立依赖从原O2/assert-logON改为官方O3/assert-logOFF/nativeISAOFF，无fastmath/LTO，不改PHY/网络参数；新头文件、全部库/RPATH同一根，旧库未覆盖。35.24%是CPUprofileoff的一个固定burst比较，不能拿有profile开销的166ms做收益基线，也不外推所有无线轨迹。[比较及身份](RELEASE_PORTABLE_BURST_SUMMARY.json)、[ELF身份](RELEASE_NATIVE_IDENTITY.json)。

A07从R TopicWire全部capture的mono429862.043378到.219025存在175.647ms空白。三机下一odom capture均晚于seq255快照，C publish仅约.1–.3ms，C Peer消费不是主要空隙。seq255里tb2/tb3的C Peer原receipt分别.216839/.215767wall>.2，source和correction仍新；不能称源TF过期。A07没有单段profile/GC记录，故未唯一归因给GC、DDS或某handler。

A08在更早preflight确切复现另一149.964ms R capture空窗：public ready-query142.741ms内，generation2 GC占140.872wall/140.866CPUms、collected0。这是实时关键进程扫描存活对象的已证长段，而不是假定磁盘阻塞。但末firstfault附近只有小于.35ms的gen0，无大GC/单段handler卡顿，不能说暂缓GC解决了末heartbeat。[首故障与GC分层摘录](A08_FIRSTFAULT_TIMELINE.json)。

最终5401af4候选仅在全部ROS资源构造完成后的、有原外层wall约束的独立Gateway进程里暂缓自动循环GC，引用计数继续；原_close完成或异常finally恢复原enabled/阈值，移除自身观察callback，再persist。没有forcecollect/改阈值/影响Peer/HQ/Policy，所有A/B/C同适配。循环对象可留到收尾增加内存，不适合未经验证的长期服务。19的16wall夹具记录start/end均false、0GC事件、close恢复true/[700,10,10]，一次close RSS峰值115840KiB（约113.1MiB，持久化前）；18无RSS，**不能做内存前后配对或保证180sim内存**。R最大capturegap52.989ms，已捕获Topic7316上行/246下行与5090条Action CDR在目的端逐flow/完整内容计数相等；三机TF/odom/FB实际源计数全部被捕获，但只证明此synthetic条件，不是所有场景零丢失。[19摘要](CONTINUOUS19_SUMMARY.json)。

## 两次实际自主运行：覆盖、运动与停止

采用原离线评价器、固定Corr6201分母15558/38.895m²、原ROI/质量标准，A07 sealed bag只处理一次，没有新Node/NN/GZ或新评价器。曲线原数据见[coverage.csv](offline-metrics/net01-a-corridor-6201-07/coverage.csv)与[完整指标](offline-metrics/net01-a-corridor-6201-07/result.json)。

| 回合 | 自主sim | T90/T95/T98 | 末覆盖/质量 | 自主三机路程m | NN/接受目标 | 结束与原停止 |
|---|---:|---|---|---|---|---|
| A07 | 9.96 | 全未达 | raw49.6336%；**有效覆盖NOT VERIFIED**，0/13帧qualityvalid，末p95=.4m>.25 | .9745 / .1353 / .9732 | 1 / 3（各1） | receipt fatal；原observed_stoptrue、3PAUSE、3本机UUID CANCELED闭合；integrityfalse |
| A08 | .11 | NOT MEASURED（未运行至可评估探索） | 未评估，不填0 | 无有效自主运动（全期仅约.2mm数值漂移） | 0 / 0 | heartbeat fatal；observed_stopfalse、3PAUSEtrue、missingjournal，integrityfalse |

A07末图是在绝对receipt23.95/source23.042、自主8.32sim收到；不是完整9.96秒终点的即时真图。初图raw11.1518%，末free precision98.3275%、false-free .445m²，初末occupied p95约.5809/.4m，全部13帧无效；不能凭precision较高绕过原几何门槛。任务期0成功/0原Nav2失败/0取消，停止期3CANCELED另列；不把保护取消记作探索任务成功。

A07本机exact-owned Cancel/GetResult5、物理近静止和三PAUSE有实际证据；Gateway中央executor shutdown=false及3个C GetResult_RPC未决也保留，不能称全部传输清理无误。A08在18–20sim的已存pose/drive显示三机近静止、新消费零速且三PAUSE成功，**但原停止认证仍FAIL**：CheckpointHeadquarters.__init__第一行虽已有exclusive journal open，模块级numpy/torch等导入在constructor之前，早故障可使真实journal尚未创建。原request_closure报告Expected controller request log missing，稳定计时不放行；没有为旧case补造空日志或用0Goal充PASS。

A08末heartbeat链与前述GC是两个问题：seq164/165的Peer entry间隔309.068ms，真实Gateway C clock relay16.4→16.5相隔308.866ms；R三health接收间隔约306.55/307.15/302.48ms，全部>.3wall。新包来到时先核旧interval并正确锁存，不能等恢复撤销。首fault附近转发很快，尚未分清上游真实clock发布节奏与R reader调度分别占多少；不放宽门限、不刷戳或推责RL/Nav2。

## 分项验收与剩余问题

| 项目 | 等级 | 本轮实际边界 |
|---|---|---|
| FROZEN POLICY | PASS | 原模型/701/核心目标与执行合同未改；只有外部配置/依赖/传输诊断与有界GC适配 |
| NS3 WIFI MODEL | PASS（限定模型/包路径） | 同源V3真实MAC/PHY/PCAP，Release固定burst全等；不代表机器人闭环 |
| BIDIRECTIONAL TRANSPORT | BLOCKED | 17真实WiFi有限满载关键流通过、仍324不完整；19是direct，真实B/C未运行 |
| NO DDS BYPASS | BLOCKED（部署总验收） | 两域/真实完整CDR受控路径证据保留；没有实际WiFi–GZ业务闭环可签完整部署 |
| TIME SYNCHRONIZATION | BLOCKED | 15/16是旧候选clockFAIL；最终5401只有synthetic验证。A07 receipt/A08 heartbeat超线不能混称maxlag超限，实际完整时间验收未过 |
| ACTION AND MESSAGE INTEGRITY | BLOCKED | A07 direct真实3UUID闭合；A08缺journal，实际WiFi Nav2未验证，受控旧子测不升级 |
| NETWORK SAFETY | BLOCKED / A08认证FAIL | 本机停机事实与认证分列；没有本轮运动中WiFi断链物理停止证书 |
| GAZEBO NS3 CLOSED LOOP | BLOCKED（B/C NOT RUN） | direct A07/A08各FAIL，无新健康180sim；未执行真实WiFi机器人闭环，不宣称该闭环已实测FAIL |
| PERFORMANCE | INSUFFICIENT | CPU工程收益不等于RL探索收益；无健康匹配A/B，不作优劣结论 |
| OVERALL / NET-02 | BLOCKED / NO-GO | 原失败不追认，3/3预算结束 |

剩余最小范围是实际clock/接收执行节奏与.3wall健康间隔之间的协调、早中止时的真实journal生命周期和地图质量；原Gazebo -11也只在一次隔离启动内未复现，缺历史栈不宣称修复。下一轮若继续，必须另立有界匹配计划，保持原政策/安全/网参，先明确控制输入产生与消费时序；本轮不实现新协调器或继续优化。

## 本地交付

最终运行候选源码为5401af455156b0371ba2d440f3a439149c6faf08；A07实际6a92325、A08实际d21e206分列，最后GC修补**未在新Gazebo回归**。精确相对15b53的运行源差异见[SOURCE_CONFIG.diff](SOURCE_CONFIG.diff)，重要文件/ELF身份见[DELIVERY_IDENTITY.json](DELIVERY_IDENTITY.json)。Release ELF SHA复用已核82bc8ecf…、依赖独立d5528e2，不重新扫描历史树/原袋。原件保留在各runs目录，Git只提交代码、轻量摘要/配置/指标，不把原bag/大环境重新打包。

到此停止：3/3新实际Gazebo、累计92；19后无新运行/测试/源码优化/训练/NET02/push。正式独立验收由root另行封存。

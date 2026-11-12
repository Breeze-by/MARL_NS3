# followup04 最终独立复核

**验收结论：统一common58版本的六次有界工程重复、原停止/退出链及新自动daemon清理，在本轮条件下有限PASS；A1/B性能因果归因仍为INSUFFICIENT EVIDENCE。** 六例均完成180sim并达到质量有效T95，不等于自然任务完成、所有目标成功、独立RF重复或NET-02准入。没有需要靠新增测试解决的本轮工程验收阻断。

本审只读六例READY与共同metadata、`metrics.small-result.json`、`metrics.exit.json`、`uuid-summary.json`、`pre-analysis-exit-proof.json`、原host/result/network-integrity的小字段及行政失败证明；不读bag、coverage_curve、大Gateway/ledger/PCAP，不重跑canonical、模型、ROS/Gazebo、测试、构建或哈希，不Git提交。既有协议源审与helper审分别见[PROTOCOL_REVIEW](PROTOCOL_REVIEW.md)及[followup03独审](../followup03/INDEPENDENT_REVIEW.md)。

## 共同身份与协议符合性

六READY的adapter表均为58项，实际metadata完整等于[COMMON_BINDING_58](gz-requests/COMMON_BINDING_58.json)；共同变更表[COMMON58_DELTA](gz-requests/COMMON58_DELTA.json)为旧57中56项继承、host更新、helper新增，无删除。实际source/adapter均记 `cec5c5676f8ba156a6cdab05ce8fc94575987df5`；本审比较的是已封metadata，不重新声明源字节/模型/DSO哈希验证。六例冻结参数表、冻结源码map、scene/world/checkpoint/共同出生点及预算字段与首真实例整项相同。

执行顺序为A1→B、B→A1、A1→B；相应session为1267、1262、1263、1264、1265、1266（均以202611为前缀）。首A1按明确行政修订使用fresh02，不是另一个物理失败样本的补跑。其余slot身份与协议一致，全部独立READY三授权为true；A1 mode=A、B mode=B，均direct_reference=false/GDBoff。static-footprint-common-v1、graceful/raw、pace20、原63e738诊断插件及精确180sim scope一致，没有回合间调策略、导航、RF或保护参数。原180sim/130decisions及180/720/900/90/1000/12wall预算、2wall等门槛保持。

三对只是部分平衡先后，非随机顺序。物理seed2026110601、network seed2026110901/run1固定；相同seed不等于不同业务过程逐事件相同，更不是三个独立RF种子。旧bc18及更早版本均未混入本轮三次统计。

## 六例实际结果与证据索引

表内T95/T98均为原canonical首次质量有效阈值的自主相对sim秒；末覆盖为**末有效地图样本**，不伪称恰好180sim时刻的直接采样。所有末样本质量有效，采样位置相对179.26—179.97sim；六例 `natural_completion_verified=false`，原结束原因是预算。

| pair/arm；小证据 | T95 | T98 | 末覆盖比例 | 有效/全部地图样本 | 唯一UUID原终态 |
|---|---:|---:|---:|---:|---|
| r01 A1 fresh02：[指标](gz-analysis/corr6201-common58-r01-a1-fresh02/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r01-a1-fresh02/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r01-a1-fresh02/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r01-a1-fresh02.ready.json) | 39.46 | 52.07 | .9983931096541973 | 217/217 | 11 SUCCEEDED(4) |
| r01 B：[指标](gz-analysis/corr6201-common58-r01-b/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r01-b/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r01-b/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r01-b.ready.json) | 35.61 | 90.97 | .9995500707031753 | 244/254 | 10 SUCCEEDED(4)+1 ABORTED(6) |
| r02 B：[指标](gz-analysis/corr6201-common58-r02-b/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r02-b/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r02-b/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r02-b.ready.json) | 40.42 | 99.31 | .9993572438616789 | 232/246 | 10 SUCCEEDED(4) |
| r02 A1：[指标](gz-analysis/corr6201-common58-r02-a1/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r02-a1/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r02-a1/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r02-a1.ready.json) | 62.25 | 112.26 | .9982645584265329 | 206/217 | 11 SUCCEEDED(4)+1 ABORTED(6) |
| r03 A1：[指标](gz-analysis/corr6201-common58-r03-a1/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r03-a1/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r03-a1/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r03-a1.ready.json) | 72.01 | 74.51 | .9987787633371898 | 204/217 | 11 SUCCEEDED(4) |
| r03 B：[指标](gz-analysis/corr6201-common58-r03-b/metrics.small-result.json) / [UUID](gz-analysis/corr6201-common58-r03-b/uuid-summary.json) / [退出](gz-analysis/corr6201-common58-r03-b/pre-analysis-exit-proof.json) / [READY](gz-requests/corr6201-common58-r03-b.ready.json) | 48.68 | 57.31 | .998843038951022 | 237/247 | 9 SUCCEEDED(4) |

原六份metrics.exit均returncode0，各自唯一canonical的原回执保留。本审没有再求阈值或重新分析地图。64个owned UUID为62个SUCCEEDED和2个ABORTED(6)，原未终结/ownership错误均空，没有raw CANCELED(5)或任务timeout需要混写。工程过程PASS并不擦除r01B的tb3一次失败或r02A1的tb2一次失败；这两次原status6不能套用旧bc18中“高层timeout但原status5”的口径。

## 停止、退出与自动清理资格

六例原result的observed_stop、lifecycle_pause_healthy、run_integrity均true，hazard/error均null；原UUID ownership闭合。六例runner/Hub/已启动controller/coordinator/clock R/C退出均0，network-integrity为true、原gateway native_exit=0。原停止观测与资源收束各自有证据，不以其中一个替代另一个。

六次新host均在原资源关闭后实际匹配一个本case/session/domain92/UID1000/完整ros2cli argv和startticks的daemon，pidfd单次SIGINT，target_process_exited/cleanup_pass为true；非子进程exit_code仍null，不能虚写daemon0。六份proof各有56条 `proc_exists=false` 的已知PID记录，精确case/session残留和owned groups为空；不是仅保留旧55名单，也不是停后手动补救。host end_utc均晚于helper end_utc，实际清理计入总wall。

实际自动回收daemon依执行顺序为2140884、2156415、2159670、2162961、2166405、2169243。由此，**新自动host hook已获得六次完整真实运行后的正向集成证据**，不再只是followup03的组件资格/源码审；原helper错误session无signal的负例仍见旧资格记录，不需复测。有限通过不宣称所有异常退出路径均穷尽验证或未来绝不残留。

## 首行政失败与明确偏离

原session2026111261的host失败完整保留，原因是新phase IPC父目录缺失、Hub本地bind FileNotFound；native虽起并在错误收尾中退出0，ROS主运行器/Gazebo/NN/Goal未启动。见[原failure-and-exit](gz-analysis/corr6201-common58-r01-a1/failure-and-exit.json)、[事前fresh02证明](gz-requests/FRESH02_ADMIN_FAILURE_PROOF.json)及[Root修订](ROOT_PRE_GAZEBO_AMENDMENT.md)。其owner END未正常收到、native证据不完整，不因native0或helper无match改写PASS，也没有canonical任务成绩。

本审接受已明示的狭窄行政层“不重试”例外：只补自有IPC父目录，以全新fresh02/session1267重新单独READY/START，在任何探索成绩出现之前锁定；不是删除测得的物理失败再补有利样本。最终应同时记**7次host尝试=1次行政失败+6次真实180sim Gazebo**。没有第七次物理运行，原任务/RF/种子/顺序未因结果修改。后续真实失败仍须按协议暂停，不由此获得一般性重试权。

## 描述性比较及因果边界

预注册pair的B−A1 T95分别为−3.85、−21.83、−23.33sim秒；三对中B的该阈值较短，是本轮事实。首对T98却为B90.97、A152.07，顺序反转，因此不能从单一阈值推广“全面更快”。n=3、固定seed/run、固定部分交替顺序下，仅作逐例/配对描述，不作统计显著性、纯RF优势或通信优化因果结论。

共同源码/出生点不是共同观察。首决策A1均G25，候选数6/5/8、choices各异；B首决策G20/G25/G20、候选均7，地图stamp分别17.72/22.66/18.262，与A1的23.021/22.7/22.514不同。初始覆盖接近也不能消除这一输入/候选/时序差异，候选动作号不当成共同语义标签。目标分工、反馈、地图更新和观察共同演化，未固定逐包双向输入。

A1主阶段wall约359.986/359.983/359.989秒，B约420.463/408.076/409.523秒；既有physical-progress RTF记录A1约.497、B约.427—.439。后者含其原物理进度起止窗，不与自主主窗硬混为同一估计。同步等待、ROS适配/CPU竞争及steady wall反馈每sim负荷可能参与差异，现有六例不能唯一分离；没有独立CPU段测量的项目保持缺测，不能把更慢推进直接叫RF延迟或CPU根因。A1本地Gateway并非A0，B真实业务过网的既有路径资格也不等于本轮T95差的纯RF归因。

旧SIGSEGV与历史A0精确唯一原因均不由此恢复或签修复；保留原未知/BLOCKED和历史FAIL，但不把无法复原的历史episode当作本轮有限工程工作永远无法完成的门禁。static-footprint候选的原局部机制与本轮真实可执行性已有支持，尚无匹配旧配置随机对照来证明它单独造成T95改善。

## 交付范围与必要文书问题

本轮可按**六例有界共同执行、停止/进程/自动资源收束有限PASS**收束。描述性结果有据，因果不足须一并交付；不据此启动训练、RF优化、NET-02、实机或第七物理例，不追加测试来修饰已经完成的结果。

本审首次读取RUN_LEDGER时仍为5 completed/slot6 NOT_RUN的过渡状态；已通知Root在最终账本/报告中更新到6物理/7host，并保留行政FAIL。此为交付一致性事项，不是实验失败或要求新运行。最终总体报告/封存身份由Root负责，本独审不代其Git封存或改生产。

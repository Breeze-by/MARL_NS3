# 探索修复基线与通信因果边界

2026-11-15。最新已接受[ROS wall延时V3正式70窗口](../local-runs/ros-delay-v3-20261114/REPORT.md)：78次实际启动、70个完整120sim合格任务窗，T95达标55/70、明确未达15、未知0。8次无自主startupFAIL的原stop/PAUSEFAIL、RAM/raw与canonical保留，完整工程/clean为70/78；主表是自主窗口条件比较，全部启动可靠性另列。此前无WiFi的V1五/V2二十七attempt及旧WiFi四路40窗均不池化。
唯一覆盖完成指标为首次质量有效T95；未达为null，失败/缺测另列，不用预算补值，不把仅达标样本的条件均值冒充整组T95均值。T95是观察到的覆盖达标，不等于控制器自然终止；评价真值不回灌策略。

## 最新ROS wall延时V3：方法与因果边界

两图×七条件×五配对seed块，共同120sim/G20/23边界/绝对40wall节拍与有限保护。A0直连仅代理校准；D0..D500共用本地代理，业务双向每次跨端新增单向实际wall-ms，无新增loss/reorder。全部无ns-3 WiFi业务、native服务延时N/A。源→HQ主量仍是已有R Observer map/odom/tf/tf_static同次take构成的publication cohort，原DDS publication→HQ native take返回wall-ms；不是generation AoI或全publisher无损。FIFO hold是capture→就绪释放，不冒实际接收，窗外/closing drain不进120窗hold均值。

七条件共同锁定source .70/.85sim、Gateway/Observer receipt .60sim与producer .50sim，真实四owner/PID/实例/复制binding记录核验，原wall进度/UUID/碰撞/停止边界不改。全部70窗原7工程门、full/clean及10个七条件RTF门通过，最大对称跨度0.08674458%<1%。Corr按A0/D0/D100/D200/D300/D400/D500达标5/5/5/4/4/4/5，Rooms为4/5/3/4/2/3/2次（均分母5）；时延增大，任务结果非逐档单调，不签统计显著性或唯一RF任务因果。

八次零自主startup是本地spawn响应发送超时或factory查询挂起，未进延时任务链；原8FAIL与named事后后继单列，不假定缺失随机、不据成绩选样。f016[AM3](../local-runs/ros-delay-v3-20261114/METHOD_AMENDMENT03.json)为另一种事后离线纠错：窗后未准入capture复用last-ID触发原摘要冲突，经真实queue/meta/单调close/窗外且source-key不交集证据仅单列15条NOT_ADMITTED_POST_CLOSE，实际admitted摘要继续严格校验。原BLOCK/UNKNOWN不改，一次独立分析复用原真proof/T95（未重跑任务/T95），9主窗字段一致，最终T95=108.94。79-runtime始终共同，9method只有这一analyzer换版，旧15原无冲突路径静态等价不重算。

本批代表差例f006完整有效未达与Nav2真实路径/局部规划受阻并存：17accepted、8abort，原UUID EXECUTING→ABORTED；没有代理撤权拒绝或自主期保护零速。DWB/BaseObstacle及恢复CollisionAhead是预测，组合costmap各层贡献未分清，不能唯一归D200或实际碰撞。原差例保留，未改策略/导航/无线来挑预期结论。全部仿真已停，59页中文PDF/MD已通过Root渲染视觉与独立文本验收并复制交付，见[实际文件与QA来源](../local-runs/ros-delay-v3-20261114/REPORT.md#权威来源与交付状态)；不自动新实验。

## 此前独立Wi-Fi四路40窗口与42次attempt（历史）

两地图Corr6201/Rooms6101×四路径A0/A1/B/C×五次比较**已完成**。每组n=5运行等权mean±样本SD，native/A1 witness sim-ms与publication→HQ take wall-ms分列；条件交付率不等于RF包丢失率，Rooms A0/A1也有观测cohort未在HQ看到。T95走廊均5/5、房间4/3/4/3；房间组仅达标条件均值不可冒充全部五次均值或用于整体排序。以下v1/v2为历史：原v1四个实际Gazebo例整体冻结为discovery：a01s/A0、a02/A1、a03/C中央T95为78.14/80.66/83.10sim秒；a04/B在G50因决策槽错过工程阻塞，自主窗口30.07sim，T95仍null。socket父目录缺失、Gazebo/机器人runner未启动的setup a01单列（coordinator/clock ROS sidecars已启动，物理0step、无任务观察）。四例连同三个成功例全部不计新正式均值，亦不与已接受的独立er13基线或历史RF六例混样本。来源见[PRIOR_DISCOVERY](../local-runs/communication40-v2-20261113/PRIOR_DISCOVERY.json)。

共同测量复用已有R Observer map/odom/tf/tf_static的同次take，组成“实际观察到的原源publication cohort”；A0直接匹配原RMW源时刻，A1/B/C通过原source capture、实际FIFO/native ID及目的publish括号回溯，主时延是原DDS publication→HQ native take返回的wall-ms。它包含队列和软件处理，不是生成AoI；条件交付率不是所有publisher排放的成功率。B/C入网→native RX的sim-ms与A1本地FIFO clock-witness间隔另列，不以wall×RTF换算。重复timestamp、无GID或不可唯一匹配保留未知/歧义和分母，不能拿C/R回调数相减作loss。

前三discovery例的HQ追踪均有完整flush证据；a04只有1999行、915次sim10.53..11.62的prewarm take，缺少完成summary，原flush被KeyboardInterrupt中断。原24325源“0 HQ收件”的分析是测量缺失，**不是无线零交付**。新离线`trace-completion-audit-v2`核原source/HQ summary行数、连续ID和原Gateway saved标记；a04修正为`HQ_TRACE_INCOMPLETE`、源全部UNKNOWN、成功率点值及主wall统计N/A、界0–1，旧raw/分析保留并附[显式勘误](../local-runs/communication40-20261113/post-exit/a04/MEASUREMENT_ERRATUM_V2.json)。独立wire交付统计不能代替缺失的HQ观测。

v2为防止错过固定决策槽增加物理边界ACK，20项状态/实际ROS与42项四路入口组件通过；原10sim-ms步长、40wall-ms绝对节拍和2wall-s保护门均未放宽。这是组件资格，不是40例集成完成。首例b01预热G2.25时gzserver实际SIGSEGV，原physics RPC保护随后超时；native ACK停在G2.24、HQ未启、未到G20/G25。旧v1/v2队列关闭，旧b02未启。事后检查没有OOM或资源耗尽证据，详见[B01_STARTUP_DIAG](../local-runs/communication40-v2-20261113/B01_STARTUP_DIAG.json)；不得把崩溃后的RPC失联归为无线时延。

独立静止GDB诊断`sg41/d01`无HQ/NN/Goal，未复现SIGSEGV，三机spawn成功；首Step实测4.305686wall秒触发原2s门。原停止/复制资格FAIL：复制11,040B一致但原native complete仍false（0step trace为空），所有已知owners退出，原RAM与disk raw保留。见[DIAGNOSTIC_RESULT](../local-runs/startup-gdb-20261113/DIAGNOSTIC_RESULT.json)。这既不是正式样本，也不证明崩溃修复。

后续独立v3 G0 probe `sg42/d01`（session2026111691）通过12项初始化事实：三个原spawn进程实际退出0、同World实体查询成功后才发首physics token；行政ready本身不推进clock/native/physics、不改deadline。首server Step为13.888ms，首实际ACK为0→10ms；observed stop/copy为真、57个已知owners退出。但原GDB bind检查错误仍使preflight=false/host=1，不能称整例PASS，也没有证明SIGSEGV根因已修。详见[PROBE_RESULT](../local-runs/communication40-v3-20261113/PROBE_RESULT.json)。

新v3正式40例已于2026-11-13 13:44:04 UTC实际启动，统一77项runtime/8项method绑定；所有正式例GDB=false，源码确认跳过该debug helper。地图、seed/run、执行顺序、120sim、2s/40wall/G25边界门保持共同合同，原业务/策略不变。全部40窗口已完成：40份window测量资格、10个同map/block四臂RTF对称跨度门通过；完整工程/clean exit各36/42 actual attempts。AM1以严格同PID/session/case资源闭合、persist/close_return/main_return意图在原supervisor SIGTERM下界之前的证据，事后保留c04/c06/c09/c14完整窗口；其原host/network FAIL、实际-15及原row/journal保留，非全工程PASS。AM2仅修负坐标--positions= CLI并恢复未执行的c05 T95一次。AM3/4对两次0RUN/无自主窗口的tb3 spawn响应超时分别明确授权c16s/c29s，同原条件/seed；原c16/c29启动与stopFAIL/RAM保留，T95=N/A_NO_AUTONOMY而非120未达，两次均Corr/C且不假定缺失随机，底层RMW根因未定/未修复。Corr/C实际7attempt/5窗口，主表属于进入自主窗口后的条件比较，全部启动可靠性另报。全部运行共用同77-runtime；批次后的退出小修独立处理，不追溯4次FAIL或冒称Gazebo复验。实际状态以[执行记录](../local-runs/communication40-v3-20261113/execution.jsonl)与[计划](../local-runs/communication40-v3-20261113/PLAN.draft.json)为准，旧discovery、两次独立诊断和er13基线均不混样本。

## 此前独立探索修复单例

唯一`er13/a`以独立72路径绑定、原d53 B Wi-Fi执行120sim预算，按原停止链结束；没有在线真值评价/新STOP/复制冻结main。三视图T95为local43.15 / 中央主43.17 / R43.18sim秒；首次有效中央样本G63.17覆盖97.024%，相对59.44sim实际样本已覆盖98.978%，不是延长到120才达标。末中央/R99.6529%、local99.7622%。每视图289样本，C/R有效269/无效20、local289/0，无missing及raw≥95却quality无效。

原pacing门通过：12000token、RTF0.249999836、迟到p95=2.575wall-ms，>40ms10个（0.08333%≤1%），最大214.623ms保留。23个G25..135槽lateness0、23forward、0WAIT；16Goal全部接受，12success/1abort/3budgetcancel闭合。已知owner/writer均退出，native6,348,446,912B完整复制<8GiB预算；本taskRAM已定点释放、diskraw保留。

- Nav2时钟：修补四个缺失节点的use_sim_time，三机生效YAML七节点均true，其他运动/保护参数不变。真实installed Wait组件证明暂停/推进语义；本例未逐节点采运行GetParameters，不混淆这两类证据。
- 候选几何：旧7格L∞硬膨胀换为Nav2圆半径.25m及R+res/√2=.285355m的保守grid-centre几何。原收到图、原权重/701结构及其余peer/任务门保持；本例实际23次调用，无idle合法候选耗尽。连续/动态路径仍由Nav2检查。
- Goal guard：只对原实际map-frame Goal点/token/UUID与鲜度≤2sim own-map明确NavFn round格100走原取消/真实终态链；unknown/stale不触发。真实ROS Action组件通过，本例assignment rejection=0、active cancel=0，主动分支未在ns-3集成触发，不能计作性能原因。

这是一例合并三改动的新行为基线，候选/目标取消触发及Nav2时钟不同于旧60sim组。达到T95早于60sim说明本例不只是“预算加倍才通过”，但未做消融或重复，不能分摊各改动收益、保证以后每次达标或称导航中止彻底消除；无线因果仍未证。详见[本例报告](../local-runs/exploration-repair-20261113/REPORT.md)、[总小件](../local-runs/exploration-repair-20261113/RESULT.json)、[原pacing](../local-runs/exploration-repair-20261113/post-exit/a-pacing/result.json)。

## 前一通信因果资格六例（历史合同）

以下段落仅指前一60sim通信合同：Corr6201、固定PPO v1.1.0、701编码/Frontier/联合mask/目标生命周期、SLAM/Nav2与机器人行为保持其当时原合同；不要套用为上述新修复基线“全行为未变”的声明。两臂都走实际B业务链，VhtMcs9、16dBm、TCP与队列/发布率/保护阈值不变，唯一组间配置因素为LogDistance指数2→3。保持physics seed2026110601、network seed2026110901/native run1；这是相同种子的fresh-process重复，不是三个独立RF种子。

共同[profile](../net01/config/EXECUTION_PROFILE_FIXEDSTART_CONSUMERTRACE_V1_60SIM.json)固定R自主起点G20，原allocation attempt为G25+5k、[25,80)，容差10sim-ms。准备只检查原合法readiness、无运动和经原flow95到达的初始化marker，不按观察/候选/覆盖/NN结果选起点。WAIT和缺观察仍算attempt，不移T0、不补理想输入、不换失败样本。计划顺序为B/L3、L3/B、B/L3。

|顺序/对|逻辑例/物理目录|Wi-Fi指数|local T95|中央 T95（主）|R T95|末中央覆盖|迟到p95 wall-ms|
|---|---|---:|---:|---:|---:|---:|---:|
|1/对1|g/g|2|null|null|null|89.97%|5.299|
|2/对1|h/h|3|37.23|38.50|38.53|96.79%|7.770|
|3/对2|i/m|3|null|null|null|88.88%|4.924|
|4/对2|j/j|2|null|null|null|87.02%|3.439|
|5/对3|k/k|2|null|null|null|90.37%|2.168|
|6/对3|l/l|3|null|null|null|90.55%|2.197|

表中T95单位为相对G20的sim秒；null均为60sim内未达。六例每视图145个评价样本、无missing；末覆盖是窗口末附近的实际观察，并非恰好60秒采样。B达到0/3、L3达到1/3；没有一对两臂都达到T95，配对时间差保持null。此结果不能写成“受限无线必然更差”，也不能说明L3稳定更优或具有统计显著性。

六例运行/网络/物理停稳/自有任务闭合/完整native复制通过，主runner、Hub、native、controller及受控clock/coordinator均退出0，已知PID和daemon退出证明完整。这不等于每个ROS子进程或Goal都成功。

66个原定槽均实际在G25..75执行、sim lateness0，66次原NN；WAIT记录按g/h/i/j/k/l为2/0/0/4/1/0，未删除。每例6000token，共36000；按原绝对计划网格计迟到，无重锚/删慢token。每臂RTF .25±2%、迟到p95≤20wall-ms、>40wall-ms比例≤1%、每对RTF相对差≤1%全部通过。>40ms均0，p95范围2.168–7.770wall-ms，三对RTF差0.00161953%/0.00155438%/0.00314049%。

l在shutdown前未观察到G80的显式permission_closed callback，单列`close_event_missing_at_shutdown/UNOBSERVED`；不能伪造观察关闭。原send_goal入口[25,80)代码及组件保证保留，实际六例均无≥80新Goal入口；此前放行的inflight反馈/取消/停止不被改写。G80入口门不是DDS发包或Nav2接受时刻。

## 前一通信合同的修复与验证范围

|问题|当前实现与检查|
|---|---|
|Action/Peer/journal混用时钟|新sim-business profile显式用整数ROS sim-ns处理业务期限、有效odom收件龄和journal机会；[ActionWire](../net01/action_wire.py)、[BusinessPeer](../net01/business_peer.py)、[Gateway](../net01/gateway.py)。原CDR/RPC/重试次数/源stamp、独立wall保护不变；失败TF不续旧有效pose龄。|
|启动时机与首决策不同|[fixed_startup](../net01/fixed_startup.py)预热并复用同一个自有HQ进程，[consumer bootstrap](../net01/consumer_controller_bootstrap.py)在同一HQ/唯一executor接入原graceful spin。最终19项startup和23项真实ROS入口检查通过；入口检查拦截exec/Gazebo/native，不冒充物理回合。|
|a初始化marker未到R|a本地marker已生成，但C exporter白名单在入网前过滤，G20原readiness/无运动通过却初始化收件false，启动FAIL，不能归RF。最小修复只在新profile准`fixed_startup_initialized`，其他原四种导出不变。真实原exporter→DDS→Hub/原d53 Wi-Fi→R raw CDR→实际Observer callback组件通过：新marker一次、原full-CDR一致、旧profile仍过滤，无强退。|
|消费者边界只有bag推测|[consumer trace](../net01/consumer_trace.py)保留同一次native take的原消息对象与真实RMW信息，原callback一次；成功state/cache应用、实际TF lookup返回、原observation读取/拒绝分支和build/use引用闭合，首701复用原NPZ，无额外推理。最终consumer组件04实际DDS/缓存检查通过。|
|PCAP/证据写出干扰节拍|原d53、serial native全证据存独占tmpfs，退出后复制。6GiB证据+2GiB保留、8GiB准入、MemAvailable≥24GiB；host820wall/Hub840wall，60/180/480/720/90预算固定；旧180默认16GiB不降低。不是session-RAM，没有关闭PCAP或压缩业务。|
|无线对照同时改多个参数|[RF_SINGLE_FACTOR](../net01/config/RF_SINGLE_FACTOR_V1.json)显式B-loss3，仅指数2→3；不以sleep制造无线延迟。CPU诊断/async均false，MCS/Tx/发布率/保护不调。|
|评价下行等待与任务进展混合|[三视图T95](../tools/analyze_t95_views.py)按local最新图并集、中央Gateway callback、R bag收件分别评价；显式`--budget-s 60`。各case只读四map话题一次，C被动capture；不回填header到达时刻或追加尾部。|

原a永久计入总attempt；旧b–f READY退役、未启动，原文件/绑定不覆盖。修复后的g–l独立成组（逻辑i物理目录m），Gazebo START共7次，已达到本task上限，没有自动第8例。scope、预算与source binding在新例开始前共同锁定。

## 前一六例输入与消费者边界

六例首NN均为G25，但初始输入不逐值相同。原保存NPZ直接逐值比较，三对701差83/89/73个元素，共享栅格差405/322/244格。B同臂g/j、g/k、j/k的701差91/80/82；L3同臂h/i、h/l、i/l差71/57/67。六组同臂实际候选记录均不同。前两对首tb1物理目标相同、tb2/3不同；第三对tb1/2相同、tb3不同，不能把动作编号变化都称为新物理目标。

六例共66次policy use，每例均有33条原peer/localgrid/seed读取分支。成功缓存来源与实际分支分开：cache可用不证明每个costmap进入701。337839个实际被take的无线转发消息均有唯一已观测publish bracket候选，4982个C本地派生take单列，unknown/ambiguous/pending为0。匹配依据同topic实际RMW source_timestamp处于实测publish realtime括号；没有GID，称唯一“已观测候选”，不冒称完整跨端消息身份，更不证明所有原源消息均送达、无丢失或无队列覆盖。

callback→use为成功更新该state/cache的回调开始→policy-use开始间隔（包含回调处理，`use.begin - callback.begin`），**不是generation→use AoI**。共享map该间隔中位数g/h/i/j/k/l分别490/250/550/520/40/360sim-ms，peer均100sim-ms；未见L3一致更差。源生成时刻、精确原R publisher边界和TF发布/插值来源仍未测；merge_map header是最旧贡献stamp，不是生成时间。sim与wall分别解释，不能相减混用或用C/R回调数相减作loss。

[离线consumer工具](../tools/analyze_consumer_trace.py)最初O(N×M)匹配被根批准终止（原退出143保留），仅离线工具增加topic/时间区间索引，经13例与原谓词/候选顺序等价检查后，每例各一次完成。runtime67绑定未变。l初次离线汇总假设一定有G80关闭事件而StopIteration，已改为显式null/UNOBSERVED；这不是运行失败，也没有补跑实验。

## 保留的历史与尚未完成的归因

原B180磁盘例完整运行并停稳、中央T95=35.16sim秒，但255/18000token超过40wall-ms（1.4167%>1%），时序FAIL保留。已有无运动固定9605消息RAM比较保持完整模型输出一致并缩小最大wall尾部，支持PCAP/存储对推进成本敏感，不等于模拟无线时延或唯一存储根因证明。旧b2/l2两例工程PASS、中央37.07/null及其native服务审查仍在前一合同目录，不与本轮混样本；旧common58历史也不覆盖当前结论。

前一六例的结论是工程/功能/有限时序资格通过，**没有建立一致的无线任务退化或唯一RF因果链**。同臂自然波动和首观察差异实测存在；合法无线作用也可通过后续路线分叉体现，不能要求全程轨迹相同或用理想数据强行对齐。已安装Nav2仍有wall循环，本轮资格不等于所有ROS行为只依赖sim时间，也不等于实机毫秒响应或安全认证。

后续需另行预声明同输入/同位置运输反事实及精确源生成到实际使用的边界，检验可重复损失，不能为预期结论挑样本、改策略或加回合。未训练、未改导航/压缩/发布率、未开展NET-02或实机。

## 前一合同证据入口

前一通信合同本机结果位于`local-runs/causal-followup-20261113/`，不是随Git完整发布的可移植原始包：

- [短报告与完整T95表](../local-runs/causal-followup-20261113/REPORT.md)、[六例总小件](../local-runs/causal-followup-20261113/COHORT_RESULT.json)、[预声明计划](../local-runs/causal-followup-20261113/PLAN.json)。
- [六例节拍](../local-runs/causal-followup-20261113/PACING_SUMMARY.json)、[消费者范围](../local-runs/causal-followup-20261113/six-cases.consumer-summary.json)、[同臂原NPZ逐值比较](../local-runs/causal-followup-20261113/same-arm-first-input-comparison.json)。
- [最终67路径绑定](../local-runs/causal-followup-20261113/COMMON_BINDING_POSTFIX.json)、[a失败小结](../local-runs/causal-followup-20261113/a.integration-exit-summary.json)、[真实journal运输组件](../local-runs/causal-followup-20261113/startup/journal-native-02/owner-result.json)、[startup汇总](../local-runs/causal-followup-20261113/startup/SUMMARY.json)。
- [前一合同b2/l2结果](../local-runs/causal-fix-20261113/integration60/PAIR_RESULT.json)；原B180及PCAP/RAM诊断均保留在同`causal-fix-20261113`目录。

实际native模型始终为原`d53b9143…` ELF，原构建源身份见[build identity](../local-runs/causal-fix-20261113/transport/build-identity.json)。当前native.cc含后来opt-in诊断，不冒称d53由当前树重编译；67项当前adapter源身份和实际ELF/原13DSO分别记录，未重hash冻结权重/13DSO。已复制并证明owner退出的a/g/h/i/j/k/l task RAM定点释放，各release记录与磁盘raw保留；其他RAM未动。

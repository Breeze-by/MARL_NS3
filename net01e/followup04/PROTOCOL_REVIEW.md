# followup04 协议独审

状态：**事前最小审查要点；具体计划/绑定尚未就绪，未签单例READY或START。** 用户已批准T95前差异分析及统一postcleanup版本三轮A1/B、最多6次新180sim；本审不测试、不读大bag、不改生产、不Git。Root提供当前HEAD `cec5c567`；本审未自行验证Git身份。

## 最小充分约束

1. **先锁顺序与版本。** 三轮可采用A1→B、B→A1、A1→B，明确只能部分平衡先后（奇数三轮无法两臂各先行相同次数），不得根据已见结果换序。六例均fresh独占case/session/资源，绑定同一新postcleanup源码、诊断插件、static-footprint共同配置、pace20及冻结策略/场景参数。旧bc18两例仅作为分析动机/历史参照，不能混作新hook重复或替代失败槽位。
2. **固定seed的研究边界。** 原world/初态、RF配置/seed/run保持共同；三fresh重复不是独立RF种子样本，相同seed也不保证不同业务轨迹下随机数消费与无线过程逐事件相同。A1本地Gateway与B真实native业务路线需准确标识，不能把A1写成A0。
3. **记录已有差异，不增加热路径。** 用既有case结果/预检/第一决策记录及原journal说明实际自主T0、初始有效覆盖/观测可用性、末样本质量、主wall/实际RTF、已有feedback和CPU/Step信息。初始观测无法恢复时如实标UNMEASURED，不能将相同出生点等价为相同策略输入。CPU/同步/ROS处理、wall反馈每sim负荷及native模型服务分开，已有计时包含关系不双算；不因诊断临时加高频监视节点或热路径日志。
4. **原安全与失败处理。** 原180sim及各wall上限、2wall保护、TF/source/health/mask、物理停止与UUID链不改。每例具体READY/RootSTART，首阻断软件/安全失败暂停序列并保原结果，不自动重试或以新例替换。高层任务超时/原status5、Nav2原status6、合法时效保护、进程失败各自报告；单个目标未成功不自动等价于阻断软件缺陷，资源清理成功也不替代物理停稳。若允许已分类合法保护后继续原重复，应由Root明确裁定，不能生产者自行洗成PASS。
5. **全母数与时间窗。** 六槽逐例列启动/过程状态、已达阈值及其质量、完整180sim率、物理/UUID/退出/cleanup。达T95后失败仍保T95，未达则报告实际截止与未达，不删除失败后只算成功均值；早停不填180sim末覆盖。比较同时给每例值和预注册round的B−A1，缺一臂则该配对缺失、失败单列，不补旧bc18。n=3以描述为主，不签独立RF分布、显著性或纯RF因果。

## T95前分析的必要口径

followup03 B的T95=34.25、A1=62.01是两个fresh过程事实。A1 token4于绝对G85启动，晚于T95@G80.5；其后任务timeout不能倒推为T95差的原因。分析应以各例自主相对T0至各自首次质量有效T95为窗，明确窗长不同；若按时间线展示差异，区分已有Goal/接受/运动/地图更新、初始观测以及源到消费者的已测段，不能以同时出现或局部规划文字作唯一归因。原始Nav2 status5取消与高层aborted的语义保持，不能重标成status6。

新hook已有真实helper负正资格与源码接线审；六次若后续获准，可以取得该共同执行版本的真实集成证据，事前不能宣称其端到端通过。当前未发现需要新增测试/验证框架的理由。等待具体计划/共同绑定后仅核其是否落实上述实际约束；运行期间停止重I/O，不开展并行bag分析、构建、散列或备份。后续均不自动构成NET-02、训练或实机准入。

## 实际计划小审：无协议阻断，具体绑定待核

已窄读 [PLAN.md](PLAN.md)、[PROTOCOL.json](PROTOCOL.json)、[PRIOR_PAIR_DIAGNOSIS.md](PRIOR_PAIR_DIAGNOSIS.md)，不重读历史原件或重算时间线。**实际计划落实上述最小约束，未发现需要改计划或新增测试的具体问题。** 初始草案状态不视为已执行准入；共同58绑定与首candidate尚在制作，待其就绪只核metadata及明确变更集合。

六槽预注册为session2026111261..2026111266，顺序A1、B、B、A1、A1、B，对应三对A1→B/B→A1/A1→B；case/socket/RAM/Hub/time-control/daemon-cleanup路径分别独占，当前均NOT_RUN且execution_authorized=false。无补槽、自动重试、自动下一例。physics seed2026110601、network seed2026110901/run1明确固定，部分顺序平衡和非独立RF样本边界已写入。

计划共同58从已封存57继承，只更新host并新增已审cleanup helper；原首8Step诊断库/static-footprint配置/pace20及冻结算法、RF、物理/地图/传感/安全门槛不变，没有新hotpath探针或参数优化。每例原180sim/130decisions与180/720/900/90/1000/12wall及2wall等门槛保留；新hook的12wall停后管理员清理计入host总wall，不能续自主。原资源门在每次START前实查；精确RAM副本若需释放仍须Root另审，计划没有自动删除历史或降低门槛。

失败条款包含启动/关键软件/安全/无法停稳/进程及新hook阻断即暂停余槽；目标超时、取消、aborted和合法保护仍分别保留，由Root判断能否继续既定序列，不自动等价成软件缺陷，也不自动洗PASS。结果覆盖全部6槽，达阈值后失败不删T95，未满180不填末值，缺臂配对保持缺失。旧bc18明确不填新槽或进入新均值。

既有单对诊断将27.76sim分成首次Goal前与已派发/accepted占有时间账，并明确不是CPU/RF因果分摊；记录首次候选/目标/观测已经不同，候选索引不作同语义比较。post-T95 token4、raw5与高层timeout、近似日志时间及未测CancelResponse边界也保持。该报告支持描述“分工/观测/执行共同演化”，不支持唯一原因或应盲修冻结组件。其数值本次只作既有小摘要引用，不冒称独立恢复原件。

因此可推进**具体共同绑定/首candidate审查**，无需重审旧模型、DSO或新增资格运行；单例实际START仍需Root按原流程独立签署。当前无协议层阻断，不预承诺六例成功、重复稳定性、通信收益或NET-02。

## common58与首A1候选metadata审定

已窄核 [COMMON58_DELTA.json](gz-requests/COMMON58_DELTA.json)、[COMMON_BINDING_58.json](gz-requests/COMMON_BINDING_58.json) 和 [slot1 candidate](gz-requests/corr6201-common58-r01-a1.candidate.json)。变更表为旧57中56项继承、仅host更新并新增cleanup helper，总58，无删除；已封存摘要继承，不重新计算文件哈希。本例adapter表实际58项且与共同表完整相等。source/candidate/adapter均指向 `cec5c5676f8ba156a6cdab05ce8fc94575987df5`，新helper/host停后语义沿followup03独审；原实际参数/冻结表无差由Root另行比对，本审不冒称再次核源字节。

slot1为pair1/A1，session2026111261，case `corr6201-common58-r01-a1`，独占p01-a1 socket/RAM/Hub/time-control/daemon-cleanup路径与协议一致。network.mode=A、direct_reference=false，业务为本地有序Gateway；原profile B/native用于clock，非A0或A1实际无线业务。GDBoff、static-footprint-common-v1、graceful/raw、pace20、原63e738诊断插件以及精确180sim engineering_scope均一致。180sim/130 decisions、startup180/autonomy720/outer900/cleanup90/host1000/stop12wall及原门槛保留。

三授权当前均false，slot为NOT_RUN，共同表亦不自动授权。Root已报告隔离01与原16GiB/24GiB资源门通过；本审没有重复探测。**无metadata阻断，支持Root仅为该slot1封唯一READY并明确START**；首实际case要核自动cleanup receipt、总wall与原停止/退出链，不提前认定hook端到端通过，也不准许自动启动slot2。完成此小审后暂停I/O，无新测试、哈希或后续分析。

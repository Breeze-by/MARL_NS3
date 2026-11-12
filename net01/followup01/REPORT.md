# NET-01 followup01：传输积压已复现并局部修复，真实基准仍被时效门禁阻断

**OVERALL BLOCKED，NO-GO NET-02。** 外部录包配置已恢复；已在真实连续DDS中定位Gateway接收前积压，公平ready批次与移除重复Action就绪probe改善了受控接收能力。但最后A04仍在自主8.1sim触发原校正源龄门禁，不能宣称真实网络探索闭环成功。所有3次新Gazebo启动都计入，累计84→87；B/C本续轮未运行，预算耗尽后停止。没有训练、改权重、改策略/导航/SLAM/物理/无线参数、放宽安全阈值或push。

原NET交付3c3143b、A01失败、旧REPORT/ledger/身份、冻结a014/tag/76fd/6d均不改。原独立真实WiFi、ROS静态和受控Action子测见[旧报告](../REPORT.md)，不能替代本轮真实GZ。新账本见[RUN_LEDGER](RUN_LEDGER.json)，源码精确差异见[EXTERNAL_RUNTIME.diff](EXTERNAL_RUNTIME.diff)。

## 实际回合：同Corr6201、同共同三角、同模型及原门限

每单原180sim/130decision、startup180/autonomy420/outer900/cleanup90wall。A为IDEAL-DIRECT-ADAPTER：同C91/R92网关/透明Action/独立guard，完整CDR本地交付；**未经过WiFi**，不冒称旧单DDS布局或零适配延迟。B/C只能真实ns3接收，未启用fallback。

|实际累计 / case|实际进入与首错|真实NN / 目标|三机全期路径m|原停止 / 3PAUSE / UUID闭合|完整性|
|---|---|---|---|---|---|
|85 / A02|实际pause/导航/原物理preflight通过；149.3sim STA1拒arm(bound_mask_receipt_stale)，未自主|0 / 0|.00480 / .00474 / .00469|通过 / 通过 / 0请求闭合|FAIL|
|86 / A03|三机arm；t0=31，自主12sim至43；health_original_sources_stale|1 / 3接受且反馈运动|.44869 / .23181 / .37502|通过 / 通过 / 3真实CANCELED闭合|FAIL|
|87 / A04|三机arm；t0=30.4，自主8.1sim至38.5；tb2 correction .584>.55sim|1 / 3接受且反馈运动|.58360 / .38759 / .50235|通过 / 通过 / 3真实CANCELED闭合|FAIL|
|B近理想WiFi / C基础非理想|**NOT RUN**；A前件不健康，前瞻预算重分为必要修后A参考|未测量|未测量|未测量|BLOCKED|

三次覆盖、T90/T95/T98均**未测量**，不是0或“完整180未达”。没有健康完整180sim回合满足获准的唯一metric前件，因此未运行覆盖评估、未伪造覆盖曲线/最终覆盖或拿旧600结果代替。原短自主轨迹CSV、drive、首末地图、TF、录包和事件已保存，路径是runtime原值，含启动/收尾，不冒充180sim任务效率。所有自然终态仍无；失败退出不同于自然完成。

原件：[A02](../../runs/net01-a-corridor-6201-02/result.json)、[A03](../../runs/net01-a-corridor-6201-03/result.json)、[A04](../../runs/net01-a-corridor-6201-04/result.json)。A03/A04都不是0推理、无目标或完全无运动。尚未形成成功目标→终态→重新分配的有界探索链，也没有真实GZ WiFi动作生命周期。

## 已证机制与对应修复

1. **录包缺件。** 原A01包装漏带QoS文件；外部NET配置按固定原文补件，仅替换recorder参数路径。续轮真实rootfs RecordVerb.parse_args、读取YAML及直接启动引用6项通过，0Node/GZ/NN，见[startup检查](startup-reference-check-01.json)。后续三次录包实际启动；旧A01不追认为成功。
2. **Gateway R reader捕获前积压。** A02同145–150sim原R TF比C Peer持有值新约1–1.2sim。连续DDS03实际源每机400条校正TF，R只捕获295/309/301，捕获前延迟下界中位约954/938/936ms；C实际publish调用约.12ms，不能把秒级滞后唯一归SLAM或DDS publish。见[窄源链](TF_CHAIN_145_150.json)、[03](CONTINUOUS_DDS_03_ANALYSIS.json)。
3. **公平ready批次。** runtime29c仅外部Gateway复用公开wait_for_ready_callbacks(timeout0)缓存当前ready集合、按当前实体数cap返回，原SingleThreaded handler/exception/result语义；C/R/hub轮换，不优先TF、不丢旧帧、不改QoS/源戳。相同连续DDS04全部400条/机到R/C/Peer，捕获前下界中位4.04/4.54/6.75ms；原guard定时器最大间隔65–68ms，未饥饿。这是该受控负载机制PASS，不是硬实时或真实GZ PASS。见[04](CONTINUOUS_DDS_04_ANALYSIS.json)。
4. **重复Action reader。** A03首真实目标后反馈约100Hz/机，而仅用于server_is_ready的ActionClient probe和原显式feedback/status订阅重复接收。最终runtime a41a删除probe，只复用原3 typed clients与2 typed/QoS端点；RPC/UUID/CDR/guardian/真实accept/cleanup未改。真实五端点逐缺/恢复与本机native ActionClient独立oracle14项一致、0业务请求；WARNING不当ERROR，不改实际QoS。见[readiness03](readiness-endpoints-03.json)。
5. **同实际反馈负载定点验证。** 连续DDS05同8wall源/20wall总界、实际Gateway A/BoundPeer/native-hub，另加实际generated完整feedback100Hz/机、status及3 typed服务；无Nav2/arm/goal/C真实Policy。source8.026wall，总12.102wall，四owner退出0；correction401/400/400、odom241/240/240、feedback800/799/799全部捕获/交付，捕获CDR身份一致；capture下界中位15.72/13.18/15.63ms，重复header上界73.11/74.19/71.18ms；Peer80/83ready(3 bootstrap)，guard最大69.9–75.1ms。见[05](CONTINUOUS_DDS_05_ANALYSIS.json)。不能把合成负载称A03唯一根因、真实导航/WiFi或物理断链安全通过。

重复header只能给延迟匹配上下界，不能当唯一DDS消费ACK。Peer可能在publisher返回前接收，微负下界是重叠/身份歧义，不是负无线时延。跨DDS serializer不拿未定义CDR padding作字段错误；网关捕获后正文仍完整保持。低threadCPU也不唯一证明磁盘IO。

## A03/A04：原时效失败有效，隔离改善不等于已修实

A03 seq429快照mono411702.093093持tb2 header42.398；新42.598于.171657进入Peer，晚于429快照。430快照.200339虽已新，但health返回.273824晚于首guard .210767。consumer43持429时校正龄.602>.55，不能叫guard误报、重盖header、等fresh重arm或删源龄检查。保存窗口还见R原TF领先capture，未排除真实组合残余负载；[42–43源链](A03_TF_CHAIN_42_43.json)、[实际反馈计数](A03_ACTION_LOAD_42_43.json)保留。

A04相似但不是同一包的重复：seq383生成38.3时readytrue，持tb2 header37.916。consumer38.5时该源龄.584>.55，heartbeat仅.073wall，源过期而非心跳过期。三guard首锁存mono413757.946980；seq384快照.942018已持新38.116，但health返回413758.011648，首trip后64.7ms，不能声称当时新包已可读。Gateway另于.976890记mapped_ns3_clock_lag_above_0.12sim，约首guard后29.9ms；不拿次生clock fault覆盖首源龄原因。[A04_FAILURE_SUMMARY](A04_FAILURE_SUMMARY.json)仅汇总现有RAM，无新增bag解码/测试。剩余R源捕获、clock调度、快照/原三mask计算和下游消费的真实组合余量尚未闭合；没有凭一次完整收件夹具认定真实问题根治。

A04实际无目标clock暂停.35wall时GZ9.7与映射ns3均不推进，固定anchor GZ.1→ns3 0未重锚；原Nav2三startup、停稳preflight、3arm确实通过。这只是启动阶段局部事实；后续运行clock-lag与源龄实际失败，所以整段TIME仍不通过。

## 停止、保存与遗留边界

A03/A04故障后R本地按原owned UUID真实Cancel，真实status/GetResult5与三PAUSE成功，原Observer新零驱动/稳定物理窗口/authority停止和closure均通过；无hazard。A04停稳41.2、窗口sim推进1.3，最小中心距.7294m。保存了实际记录/marker/END，host与launch已退出；只核本case四个owned PID均不在，不处理其他会话。

但两次C GetResult callback仍unknown，executor.shutdown为[false,true]；不伪造响应或用真实R终态冒充C Future已完成。资源有界销毁已记录。A04gateway exit1、runner1/hub0，保存成功不覆盖clock/source/主回合FAIL。guard/gateway实际源龄保护有效停止，**不等于运动中真实WiFi断链安全认证**；本轮没有主动运动断链、B/C未运行。

|验收项|本续轮结论|范围|
|---|---|---|
|FROZEN_POLICY|PASS|a014/76fd/6d与原算法保持；本轮共2真实forward、无训练|
|NS3MODEL / BIDIRECTIONAL|继承独立子测PASS|本轮A不经过WiFi；旧独立PCAP/全payload/断恢复证据不改|
|NOBYPASS|正式组合BLOCKED|旧静态真实WiFi子测PASS，未完成真实GZ B/C|
|ACTIONMSG|BLOCKED，局部真实Nav2成立|A03/A04各3真实UUID接受/反馈/取消终态，未形成健康180/WiFi闭环；C pending仍unknown|
|TIME|BLOCKED / 实际运行FAIL|真实固定anchor和无目标暂停通过，但A04运行lag失败|
|NETWORKSAFETY|BLOCKED|本地失效停止/UUID/3pause有证，未签真实WiFi断链运动停止|
|GZLOOP|BLOCKED / A失败|两次短自主不等于完整有界基准；B/C NOT RUN|
|PERFORMANCE|INSUFFICIENT|无健康A、无配对、覆盖阈值未测量|
|OVERALL|BLOCKED；NO-GO NET-02|3/3实际启动耗尽，失败均保留|

## 历史失败、源码与交付

本续轮isolated ledger完整保留：连续01对bwrap monitor整PG的SIGINT导致RAM未存；02循环变量覆盖case路径导致错误socket；03是首可靠积压复现(工具正常、业务陈旧)；04/05是限定受控改善。readiness01/02错误要求QoS OK，实际SYSTEM_DEFAULT产生WARNING而native已ready，03一行改正后14PASS。没有删除首次FAIL或重复旧17/21/14夹具。旧原生编译/签名、ARP、CDR oracle、长PHY-off、无client timeout和A01缺件账本仍见[原ledger](../RUN_LEDGER.json)。

实际A02源1c56a89（继承外部录包5d5fcd5）；A03源29c7cbba；最后A04源**a41a5216e95217cdbf63bf4023957699ec3a6978**，核心76fd不变。四外部运行文件相对3c交付共110+/15−；只读TF元数据2处、Gateway公平调度、Action冗余probe删除，没有新RL优化。源码绑定READINESS_ENDPOINT_BINDING.json复用旧未改身份，最终文档commit在交付身份另记。

[原PLAN](PLAN.md)→[第一前瞻预算补充](PLAN_ADDENDUM_READY_BATCH.md)→[最后额度补充](PLAN_ADDENDUM_READINESS_ENDPOINTS.md)均保留：A02失败后余2改A03→B，A03再失败后最后slot改A04必要回归，均在新成绩前根审，不把修后A冒作B。旧A01计累计84，本续轮3次计85/86/87，无第4次或隐藏启动。

后续最小方案应针对R接收/转发与clock推进的解耦或受控同步：A03已证capture前残余排队，同快照三mask/health生成交付约66–73ms又耗尽源龄余量；free-running GZ与单进程双域Gateway/native跟随调度也未维持原时钟门限。这些是传输/调度责任链，不能泛归RL/Nav2，也不能由probe移除就宣布已改善（A04仅8.1sim，真实回归FAIL）。应在固定载荷、真实Nav2反馈下验证这一整体机制，不继续堆局部检查。该后续计划不在本轮实现；不放宽.55/.12、不删guard或先调网络/导航。必须先得到健康匹配A，再审真实WiFi B/C，仍不以旧600/受控clock替代。本批停止，不自动追加运行、修补、训练、NET-02、实机或push。独立主审另封；本报告不替审查签完整PASS。

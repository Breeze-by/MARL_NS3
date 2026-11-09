# NET-01 followup02：接收/转发调度修补与真实 WiFi 前件失败

本轮结论 **BLOCKED / NO-GO NET-02**。外部适配的积压、域级饥饿和重复转换有直接证据及局部改善，但未取得健康的180sim直接参考，真实WiFi满负载测试又触发时钟保护。不能将接口子测或native重组成功当作完整通信闭环通过。

本轮最多3次新Gazebo，实际 **2/3，历史87→89**；最后1次未用，原因是WiFi时钟前件失败。B/C机器人试验均NOT RUN，无自动重试。旧337/d4eb、旧NET报告、失败和身份原件保留；本轮无训练、权重更新、网络调参、NET-02、实机或push。

## 实际机器人结果

时间单位为Gazebo仿真秒；覆盖按原ROI/15558格分母及质量门槛，阈值从自主t0起算。路径主列为原离线工具的自主窗口路径，收尾后原runtime全期路径另列。

|回合|实际源|自主窗口|最后收到的质量有效覆盖|T90/T95/T98|三机自主路径m|NN/接受目标|结局|
|---|---|---:|---:|---|---|---|---|
|A05 IDEAL-DIRECT-ADAPTER|1bb7d55|29.6→40.3，10.7sim|52.9245%，8234/15558|未达/未达/未达|0.879 / 0.754 / 0.893|1 / 3|原odom源龄fatal；FAIL|
|A06 IDEAL-DIRECT-ADAPTER|685f5a3|未进入自主，无t0|NOT MEASURED|NOT MEASURED|不适用；仅启动微动|0 / 0|gzserver −11；启动FAIL|

A05最后地图receipt39.5/source38.236，质量有效3/9帧，末p95=.05m、free precision98.2896%；T50=9.9sim。覆盖只说明中断前收到的地图，不代表持续质量或完成任务。该回合三机各接受1个目标、有反馈和实际平移；无探索SUCCESS，原停止阶段三UUID均真实CANCELED/GetResult5闭合。全期runtime路径为0.882/0.792/0.909m；原observed_stop、三PAUSE、authority停止及请求闭合成立，run_integrity=false，不能以安全收尾追认探索或通信PASS。自然完成未验证。

A06原launch第216行记录gzserver PID1626389 exit−11，早于tb3 `/spawn_entity unavailable`。tb1已spawn并加载driver，不能倒推factory未加载。首崩溃发生在后续机器人传感器初始化附近，现有日志无可定位源栈，未发现本case已保存core；未扩全机搜栈或改Gazebo库。原有界启动、owned清理完成，Gateway/hub退出0且记录保存；但observed_stop=false、三PAUSE=false、run_integrity=false，空请求日志只能证明0目标闭合，不能认证物理停稳。该回合是独立Gazebo启动故障，不称通信回归失败或算法覆盖0。

原件：[A05运行](../../runs/net01-a-corridor-6201-05/result.json)、[A05唯一离线指标](offline-metrics/A05/result.json)、[覆盖曲线CSV](offline-metrics/A05/coverage.csv)、[A06运行](../../runs/net01-a-corridor-6201-06/result.json)。两case原trajectory/drive/events/bag均留在各自runs目录；没有为本报告重放或重算旧600sim。

## 已定位的机制与修补边界

1. **比较分支纠正。** 旧夹具约.3ms是未ready全100分支。就绪Peer原数学在夹具中17–19ms/张，A03/A04约20ms/张；实际容器测量wall≈threadCPU，未证NumPy/线程环境不一致，也未证磁盘是该段主因。没有修改mask数学、源戳或发布顺序。[分层证据](MASK_BUILD_STRATIFIED.json)、[实测](MASK_COMPUTE_OBSERVATION.json)。
2. **ready集合与clockpump。** timeout0是一轮ready集合结束，不代表DDS reader队列空；productive refill保留公开cached cursor、原handler异常/result语义及初始总cap。每handler后及外层尾服务原非阻塞transport，避免整轮ROS处理期间clock完全得不到进度。06首STEP未执行而FAIL；07受控负载改善，不代表真实平台实时性通过。
3. **A05域级饥饿。** 新health401在首fatal前已发布，C约121.497ms未捕获，R却继续处理TF/feedback。R最后持有400，odom年龄.414–.418>.4，而correction年龄均<.55；首因不是本次SLAM校正过期。原health402虽在fatal附近到达，旧源检查先触发仍有效，不追认误报。见[A05时间链](A05_FAILURE_CHAIN.json)。
4. **有界公平调度。** 整域cap改为C/R固定4-handler小批轮转；任何一端用完本poll原cap则pair后返外层，不让另一端尾部独占。逐handler方案08、q4单项09仍吞吐不足，否定结果保留，未扫quantum或增加线程。
5. **真实CPU主项。** profile10空C查询1507次耗1.388CPU秒，ready等待、TF和feedback转换也有显著成本；不能把全部成本唯一归空probe。原Action feedback/status使用实际raw CDR输入与原typed publisher原生bytes发布，0Goal真实DDS验证bytes、字段、UUID/status一致。profile11 FB合计CPU约.834→.184秒，但单项仍不足。只在C真实空集合后固定10ms抑制重复空probe，无sleep/延期guard/刷新deadline；所有组同适配规则。
6. **时钟诊断。** 12的KNOWN→return约168ms没有STEP入口，不能称Simulator::Run耗时。独立ELF低频RAM控制trace区分queued/socket实际send/hub接收与STEP/Run；13最慢排队→ACK10.904ms、Run8.583wall/8.542CPU，12异常NOT REPRODUCED，不称已根治或硬实时保证。见[13摘要](CONTROL_TRACE_13_SUMMARY.json)。

上述仅外部transport/诊断变化，冻结a014/76fd/6d/701/Frontier/候选/生命周期/DWB/SLAM/physics保持。odom .4sim、correction .55sim、wall heartbeat .3、lag .12、.1量子以及V3 WiFi参数均未放松。公开handler间pump不重入ROS executor，不优先TF、不丢旧样本、不重戳；raw路径只去重复转换，不改变Action业务。当前代码不是新的RL学习或已通过的部署版本。

## 唯一真实WiFi满负载资格：14 FAIL

复用连续夹具，仅mode A→B，CPUprofileoff/controltraceon；20wall总界、连续8wall源不变，三机TF/odom/100Hz完整feedback、三张400×400 mask@10Hz及其他业务原样。fixture是synthetic clock、无Nav2/Goal/arm/NN/Gazebo，不可当真实GZ时间或网络物理安全试验。

实际11.893wall，源8.022wall；三机map→odom发送401/400/400，odom241/240/240，feedback800/800/799。真实三STA完整HELLO/ACK成立后才开业务订阅。首transport fault在synthetic1.6sim/mono420802.125481（guard随后.125524），为 `mapped_ns3_clock_lag_above_0.12sim`，原保护有效；不是负载测试成功后的人为结束。

H=.9：Gateway queued420802.078390→socket实际send完成.079344→hub接收.079408→native STEP写入/drain .079414/.079427。到首fault仍没有STEPreturn。socket/send/drain不等于native ACK；最后确认horizon=.8。

**首fault前Gateway仅完整收到7条：6握手、1个filter_info，0 mask。** native之后仍执行真实MAC/PHY/UDP并重组大图和mask：首160626B mask native完成.177740、hub读取.178829，均晚于fault。完整native `message_deliver`前缀19条、hub读取18条、Gateway交付7条，层次不能混淆；R bound_masks=0，Peer91帧全未ready。native接收后完整CDR重组不等于ROS消费者有效接收，更不能追认保护触发前可用。

Hub最终等STEP超时，END未flush，native被有界清理终止；native RAM STEP-end摘要未保存，ledger保留7903完整行和末行partial，PCAP原样保存。不能从缺失的终态trace唯一分出Run CPU、调度和payload输出/IPC背压份额；也不能用失败后capture数量证明持续吞吐。source/peer退出0、Gateway/hub退出1，全部owned已退出。三个unresolved_local_cleanup_futures各1（没有真实Nav2响应PAUSE），不能将资源清理完成或空owned目标当作网络安全PASS。未重试/调V3/延长20wall或使用最后GZ槽。原件：[14运行目录](../../runs/continuous-dds-14-wifi/)、[首链摘要](WIFI14_SUMMARY.json)。

## 隔离试验账本与等级

|既有夹具|实际结论，均0GZ/0Goal/0arm/0NN|
|---|---|
|06|clock FAIL，首STEP未执行|
|07|direct受控有限通过；捕获前14条FB缺额保留|
|08/09|进程退出0但吞吐/Peer源新鲜度FAIL，不当PASS|
|10|CPU测量有效，容量仍FAIL；不是性能验收|
|11|raw转换CPU下降，整体负载仍FAIL|
|12|原clock lag FAIL；168ms阶段未唯一定位|
|13|direct受控有限通过，TF/odom完整；FB源800/799/798→796/796/795，捕获前4/3/3缺额；12异常未复现|
|14|真实WiFi全负载clock前件FAIL，无完整mask到R消费者|

每次原件、退出码和失败在[RUN_LEDGER](RUN_LEDGER.json)保留；01–05及旧接口失败仍按旧账本引用，不删除或池化成成功率。raw DDS单测、调度/计时语义检查只签各自受控机制，不替代真实Action/Nav2/网络停机。

|正式门禁|本轮等级|
|---|---|
|FROZEN POLICY|PASS：核心/权重未改；非新任务性能PASS|
|NS3 MODEL / BIDIRECTIONAL|既有独立子测PASS；本轮全负载交付不足|
|NO BYPASS / ACTION MESSAGE|受控原件有限PASS；真实网络Nav2完整闭环BLOCKED|
|TIME|FAIL：14真实WiFi负载触发原lag保护|
|NETWORK SAFETY|BLOCKED：无运动子测不等于网络断链物理安全；A05原停机另列|
|GZ LOOP|FAIL真实回归 / BLOCKED网络闭环：A05中断，A06启动崩溃|
|PERFORMANCE|INSUFFICIENT：无健康180sim参考/无线配对|
|OVERALL|BLOCKED，NO-GO NET-02|

## 最小后续范围（仅设计，未实现/未运行）

需要在现有.1sim量子、严格已观测horizon与独立Gazebo推进之间，显式协调真实满负载STEP、payload输出和IPC背压，分别测实际无线处理、native输出、hub与ROS消费的容量/时序。不能以延后检查、放宽TTL、刷源戳或改RL/Nav2/网参求PASS；也不能将synthetic direct成功自动外推WiFi/Gazebo。A06启动−11须作为独立Gazebo环境故障保留，当前没有源栈可定责。本轮不实现新coordinator、不继续CPU小修或实验。

实际A05 runtime为1bb7d55，A06为685f5a3；14在685f5a3上仅增加夹具mode透传。最终源码/配置相对d4eb差异见[SOURCE_CONFIG.diff](SOURCE_CONFIG.diff)，独立ELF与复用header身份见[CONTROL_TRACE_NATIVE_IDENTITY](CONTROL_TRACE_NATIVE_IDENTITY.json)，重要新交付身份见[DELIVERY_IDENTITY](DELIVERY_IDENTITY.json)。源码/文档仅本地提交，独审另存reviews/NET-01/followup02，不推送。交付后停止。

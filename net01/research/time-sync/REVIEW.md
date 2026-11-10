# Gazebo—ROS 2—ns-3 时间同步文献评估

评审日期：2026-11-10。审查对象：用户 `paper/` 中五篇论文、作者公开材料，以及本项目固定提交 `24ed61500985f55a99b6ed4f406641771c8a1e61` 的 NET-01 followup04 实现与运行证据。主审与三条并行只读研读线交叉核对，全文研读共62个本地PDF页，查看关键架构、算法和结果图；不只依据摘要。

本次是文献与源码评估，**没有运行任何新Gazebo/ns-3实验、训练、论文软件或构建，没有更换生产同步器。** 原论文只读，未把论文PDF、整篇抽取文本和第三方源码副本发布进Git。源码可读、算法能重写、原实验可复现、迁移后适合本项目，是四个不同结论。

## 1. 直接回答：谁更适合当前项目

**目前选择保留现有真实步进/完成ACK的时间协调骨架，先修关键任务的可靠交付和中央收件等待；不整体切换到这五篇中的任何一个框架。** 这个选择来自适用故障、公开实现完整性和迁移成本，不代表现方案最优，也不是一次性能对比实验的结论。

论文里确有比当前实现更值得采用的部分：

- **DUSC** 对“机器人状态先于网络计算、网络反馈又影响运动”的依赖划分更明确；其带时间戳的逐机器人位置队列，尤其值得用于完善我们网络节点位置更新的时间语义。
- **MUNILS** 和 **CORNET 2.0** 的每机器人网络隔离、物理/本地控制与协同通信分路，适合未来真实DDS业务过网和实机接口设计。当前完整CDR代理虽实际过ns-3，却不等于原生DDS/RTPS包级仿真。
- **SynchroSim及Reliable Middleware** 对可靠传输的重视与本次Goal丢失直接相关；可借鉴TCP/确认机制的原则，但速度差调窗口不等于可靠RPC，更不等于Nav2已接受目标。
- **MUNILS的共享内存clock通道** 有降低本地控制开销的潜力；需要另行小规模验证。它的单向节流规则本身不解决“ns-3计算赶不上Gazebo”，也不处理当前健康消息发布到网关捕获的137.930ms等待。

| 判断维度 | 更有优势的方案/思想 | 结论的实际边界 |
|---|---|---|
| 网络处理落后时约束物理推进、可审计停止 | 当前Step/实际ACK/有限credit | 本项目已有有限真实证据；不是任意负载下可靠或全事件零误差 |
| 明确运动—网络因果依赖、跨主机协调 | DUSC | 论文设计更系统；公开完整实现未找到，批量和闭环移植需工作 |
| 原生应用网络隔离、接近实际端点部署 | MUNILS、CORNET 2.0 | 架构更强；不能绕开本项目必须过网的中央状态或改换网络模型冒充同一实验 |
| 单机clock低开销传播 | MUNILS的共享内存思路 | 理论优势；没有本机对比测量，也不保证订阅端没有调度延迟 |
| 直接解决两笔SendGoal丢失后永久等待 | 五篇均没有可直接接入的Nav2实现 | 必须单独补可靠交付、同UUID幂等与未知所有权处理 |
| 已有本机可运行、可审计的实现 | 当前项目适配实现 | 它仍有已证阻断；其它公开材料也不满足直接替换后即通过 |
| 谁总体更快、覆盖更高、消息尾延迟更低 | **尚不能判定** | 没有统一负载、相同策略及相同时间口径的实测比较 |

## 2. 实际论文身份与阅读范围

下文页码均指本地PDF页，避免混用会议连续页码。完整来源索引见 [PAPERS.json](PAPERS.json)。

| 编号 | 实际阅读版本 | 页数 | 主要机制 | 核查入口 |
|---|---|---:|---|---|
| P1 | Dey、Walczak、Anwar、Roy，A Reliable and Low Latency Synchronizing Middleware…，arXiv:2211.05359v1，2022-11-10 | 10 | 速度差可调窗口、TCP、ROS1/ROS2桥接 | [原预印本](https://arxiv.org/abs/2211.05359v1) |
| P2 | Acharya、Amrutur、Bharathesa、Simmhan，**CORNET 2.0**，arXiv:2109.06979v2，2022-06-08 | 7 | Mininet-WiFi、容器隔离、按物理时间释放/丢弃包 | [预印本](https://arxiv.org/abs/2109.06979v2)、[COMSNETS 2022 DOI](https://doi.org/10.1109/COMSNETS53615.2022.9668501) |
| P3 | Park、La、Lee、Kim，Devising a Distributed Co-Simulator for a Multi-UAV Network，Sensors 2020,20,6196 | 19 | DUSC/DTMA、分布式适配器、按位置事件批次推进 | [正式全文](https://www.mdpi.com/1424-8220/20/21/6196) |
| P4 | Lee、Yu、Lee、Lee，MUNILS，Drones 2026,10,387 | 18 | 每UAV namespace、双数据路径、共享内存clock、ns-3软节流 | [正式全文](https://www.mdpi.com/2504-446X/10/5/387) |
| P5 | Dey、Hossain、Roy、Busart，SynchroSim，arXiv:2208.06569v1，2022-08-13 | 8 | 速度差可调同步窗口、ROS1/TCP | [预印本](https://arxiv.org/abs/2208.06569v1)、[DCOSS 2022 DOI](https://doi.org/10.1109/DCOSS54816.2022.00061) |

需要保留的版本区别：

1. P2文件名没有“2.0”，但正文确实是CORNET 2.0，使用Mininet-WiFi；不能套用2020年原CORNET的ns-3实现。
2. P1与P5来自相关研究路线，公式高度相近，不能当作两套彼此独立的严格同步验证。P1 arXiv关联的2023 ICCCN正式条目标题变为“A Novel ROS2 QoS Policy-Enabled Synchronizing Middleware…”，作者数也变化；本次没有取得该正式版正文，不能将其潜在新增内容归给本地v1。[正式条目](https://doi.org/10.1109/ICCCN58024.2023.10230109)
3. P3本地PDF实际19页，内页总页数印为20；已用publisher HTML核对结论、参考文献1–45及末尾声明，未发现多出的正文算法，但正式PDF下载遭限流，不能保证两个PDF字节身份或推定第20页内容。
4. P4正式发表日期为2026-05-18，官网列出05-21版本更新；本文按本地PDF的明确公式和实验图评估，不将出版网页修改时间当作新实验日期。[版本记录](https://www.mdpi.com/2504-446X/10/5/387/notes)

## 3. 当前实现究竟在同步什么

### 3.1 三种时间必须分别处理

| 时间 | 在本项目中的作用 | 不能互相替代的原因 |
|---|---|---|
| Gazebo仿真时间G | 物理状态、传感器、ROS仿真时间及任务覆盖时间 | 负载、暂停和受控步进会使其与墙钟比例变化 |
| ns-3逻辑事件时间N | Wi-Fi MAC/PHY、排队、重传和分片到达事件 | 处理10ms逻辑事件可以消耗远超过10ms的墙钟 |
| 单调墙钟W | 原300ms健康期限、进程预算和真实停止时效 | 不能因仿真暂停就刷新旧消息或暂停实际安全期限 |

曾经的主要推进故障是：自由运行的Gazebo继续前进，而处理一个10ms网络区间需约30–51ms CPU，ns-3逐渐落后并触发原lag保护。当前方案在正常阶段约束物理领先，避免这类无限积累；**它没有让CPU凭空变快。**

### 3.2 锚点建立后的正常推进合同

- Gazebo物理步长仍1ms。外部薄WorldPlugin一次真实执行`World::Step(10)`，核对实际时间增加10ms和实际迭代增加10。
- Gateway按真实`/clock`建立固定锚点a；ns-3只处理已实际观察到的时间范围，按10ms量子执行`Simulator::Run()`。其内部Wi-Fi事件仍保留ns-3事件时间分辨率，不能说所有包被取整成10ms。
- 时间owner依据**实际native执行完成ACK**，约束下一物理完成时间不超过 `a + N_ack + 20ms`；单物理RPC在途。控制请求发出、socket写完均不冒充完成ACK。
- 名义每20ms墙钟发一个10ms物理token，目标RTF约0.5；实际负载下降时可能更慢，不能写成恒定0.5。
- HOLD等待在途物理请求完成后停止新token；故障后的物理停止观察有独立安全推进条件，退出自主任务指标窗口，不冒充继续正常网络闭环。

```mermaid
flowchart LR
  G[Gazebo真实物理步] -->|真实 /clock| W[Gateway与Hub]
  W -->|已观测horizon| N[ns-3事件运行]
  N -->|实际完成ACK| T[独立时间owner]
  T -->|受credit约束的Step 10ms| G
```

这条控制环与经过Wi-Fi的地图、状态、Goal、Feedback等业务环分离；不能借同步控制通道给Policy补送业务数据。

源码依据：[`time_control_state.py:6–96`](../../time_control_state.py)、[`time_control_plugin.cc:21–50`](../../time_control_plugin/time_control_plugin.cc)、[`gateway.py:163–202,396–413`](../../gateway.py)、[`payload_transport.cc:280–324`](../../native/payload_transport.cc)、[`packet_hub.py:133–158,194–212`](../../tools/packet_hub.py)。

### 3.3 已有实测与当前方法自身的不足

| 已有事实 | 能说明什么 | 不能说明什么 |
|---|---|---|
| A10 direct完成120sim，95%覆盖76.73sim、末99.8907% | 固定策略在当前直接适配参考中可工作 | 不是Wi-Fi闭环通过 |
| B真实Wi-Fi运行87.57sim后失败，末覆盖57.4303% | 真正运行过网络组合且性能不足 | 不是新方法对照实验，更不是RL学习无效 |
| B末物理/ROS时间109.51、native ACK109.50，锚点0.01s | 本次受控时间对应有限成立 | 没有由此证明全期每包因果正确、完整120sim或长期稳定 |
| B两SendGoal有udp_tx却无R完整交付，C Future一直未决 | 关键RPC可靠性缺口已证 | 不是时钟一对齐就能消失的问题 |
| B health发布返回→C捕获137.930ms；原心跳至少332.879ms才触发guard | 进网前有真实交付等待、原300ms确实失守 | 不足以唯一归因DDS、CPU或无线空口 |

原件与完整独审见 [followup04报告](../../followup04/REPORT.md)、[独立评审](../../followup04/INDEPENDENT_REVIEW.md)、[B摘要](../../followup04/B01_EVIDENCE_SUMMARY.json)。本次没有重算bag指标。

当前方案自身仍有四个重要限制：

1. **有限clock领先不等于全事件因果证明。** G、N的差值受限，并不能自动证明每条位置更新、每个反馈在正确的逻辑时刻生效。我们没有据此签发零skew或严格HLA认证。
2. **网络节点位置更新的时间语义不够明确。** `gateway.py:178–186`读取无header的ModelStates位置，`hub_client.py:47–48`的position帧只有robot/xyz；`packet_hub.py:199–201`发POSITION，native `payload_transport.cc:298–303`随命令接收立即`SetPosition`，没有独立源时间戳与按该时间排入事件队列。此实现事实可复核，但本轮没有量化实际RF误差，也没有证据将B故障归于它。DUSC对此提供了直接相关的改进思路。
3. **sim/wall混合仍是实际限制。** Nav2/BT等有墙钟调度，原健康与安全期限使用墙钟。受控慢速会改变每仿真秒可发生的墙钟回调数；公平比较必须明确共同执行profile、测量实际RTF并区分宿主处理延迟和模型无线延迟。
4. **当前是完整CDR的应用层网络代理，不是原生DDS网络仿真。** Wi-Fi模型确实转发了真实业务字节，但自定义UDP分片不会自动继承两侧DDS的可靠QoS。本次Goal无限等待说明语义缺口真实存在。没有与论文架构同机同负载比较过控制成本、尾延迟、CPU和偏差，不能自称最优。

## 4. P4 MUNILS：最接近环境，但同步方向与当前瓶颈不同

### 4.1 方法及优势

PDF pp6–7 Fig1、§3.1–3.2：每UAV一个Linux namespace，PX4、XRCE Agent与offboard节点同处本地端点；本地姿态/传感器控制走loopback或host_veth，协同数据走wifi_tap/ns-3。**这是按数据职责选择性联网。** 原生应用包走虚拟网卡，比手写每类Action代理更有机会保留原有传输协议、DDS discovery及重传语义；同时需要处理这些流量本身的成本与旁路。

PDF pp8–9 §3.3：Gazebo是主时钟；ROS2使用sim time；专门relay将clock写入8字节POSIX共享内存。ns-3在`RealtimeSimulatorImpl::ProcessOneEvent()`中读它，比较起始锚定后的墙钟参考与Gazebo时间，仅在参考领先超过δ=20ms时clamp参考时间，再交WallClockSynchronizer sleep/spin。

优势是单机低开销clock传播、较少逐物理窗口握手和较完整的网络隔离设计。它没有要求为每个网络包都回到Python处理，原生TAP数据面有潜在效率/语义优势；这是架构判断，不是本机已经测得的加速。

### 4.2 与当前20ms不是同一回事

- 论文20ms是**ns-3节流所用参考时间领先Gazebo的阈值**，不是物理完成量超出实际网络完成ACK的credit。
- Eq(2)只在归一化墙钟参考相对Gazebo领先超过阈值时调整；该参考偏差不能直接等同实际ns-3事件执行进度差，CPU事件已落后时参考偏差仍可能为正。规则没有actual event-completion ACK对物理侧的背压。我们原来恰有“网络计算赶不上物理”的负载情况，因此不能仅换成该规则就获得同等反向保护。
- 论文修改的是调度器等待所用参考量，不是给`Simulator::Now()`改名，也不是跳过尚未执行的事件。官方ns-3.40 `ProcessOneEvent()`将`tsNow`和最后执行事件时间`m_currentTs`明确区分。[官方源码](https://github.com/nsnam/ns-3-dev-git/blob/ns-3.40/src/core/model/realtime-simulator-impl.cc#L163)
- 原子读取8字节避免半个值，并不能保证reader及时获调度。BEST_EFFORT订阅可能漏样或排队，“至多陈旧一个1ms tick”需实际证明；它不能直接消掉健康消息的137.930ms等待。
- PDF p15及Fig5/p16承认单机多UAV负载时约±0.10s偏差，以低频协同和高频本地姿态控制解释其可接受性。**均值近零、不累计漂移、所有消息最坏延迟小于20ms或1ms，是不同命题。** 不能把这些图当作本项目300ms墙钟门限已通过。

### 4.3 复现时必须澄清的版本/实现问题

论文p10给出Ubuntu22.04、Humble、Classic11.10.2、PX4v1.14、ns-3.29。ROS2/Gazebo接近本机，PX4和网络端需要额外适配，不能为了照搬降级本项目ns-3.40。

| 论文描述 | 官方实现核查 | 对复现的影响 |
|---|---|---|
| p8将`UXRCE_DDS_SYNCT=false`解释为PX4全部clock跟随ROS `/clock` | PX4 v1.14.3的参数定义无此参数；v1.15将其列为新增。v1.15 false路径设置XRCE消息时间偏移为0；v1.14 Classic模拟器由HIL_SENSOR时间推进HRT/lockstep | 需要作者真实PX4补丁/commit；不能照抄该参数作为主时钟接线 |
| p8 Classic11搭配`ros_gz_bridge`的`gz.msgs.Clock` | Classic的gazebo_ros_init直接发布ROS Clock；Humble ros_gz桥面向Ignition Transport | 需明确实际桥/额外转换及版本，不能用一个包名代替可运行配置 |
| p9修改RealtimeSimulatorImpl/共享内存；p10 Waf修补 | 本次未找到可归属本文的完整作者补丁或锁定发布仓库 | 可以重建思想，不能宣称原系统一键复现 |
| p17 Data Availability | 数据需合理申请且须资助方许可 | 无原始clock/运行矩阵可供本次独立重现统计 |

以上是可复现性需要澄清的差异，**不等于指控作者实验不存在**。可能存在未公开移植。官方依据：[PX4 v1.14.3定义](https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.14.3/src/modules/uxrce_dds_client/module.yaml)、[v1.15发布说明](https://docs.px4.io/v1.15/en/releases/1.15)、[v1.15参数](https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.0/src/modules/uxrce_dds_client/module.yaml)、[v1.15源码](https://github.com/PX4/PX4-Autopilot/blob/v1.15.0/src/modules/uxrce_dds_client/uxrce_dds_client.cpp#L455)、[v1.14 HRT来源](https://github.com/PX4/PX4-Autopilot/blob/v1.14.0/src/modules/simulation/simulator_mavlink/SimulatorMavlink.cpp#L432)、[Classic ROS clock发布](https://github.com/ros-simulation/gazebo_ros_pkgs/blob/ros2/gazebo_ros/src/gazebo_ros_init.cpp#L267)、[Humble bridge类型](https://github.com/gazebosim/ros_gz/blob/humble/ros_gz_bridge/README.md)。

**本项目选择：优先借鉴网络端点隔离和控制/业务分路；共享内存clock可作为待测候选。暂不原样替换同步器，更不引入本项目不需要的PX4/XRCE飞控层。**

## 5. P3 DUSC：因果关系和跨主机方面最值得借鉴

### 5.1 核心方法

PDF p4 Fig1：Flight Simulation Adapter(FSA)、Network Simulation Adapter(NSA)、Reporter分离，可通过TCP放在不同机器。pp5–6明确两种依赖：

- CAN：网络计算某段时间前，需要该段机器人的位置变化。
- NAC：运动决策某段时间前，需要可能影响它的网络结果。

同时严格等待彼此未来输入会死锁，论文采用位置队列与有界批次推进，并以`RegisterNetworkCallback()`把条件触发结果送回控制侧。pp6–7 Algorithm1/Fig2：每机器人一队列，收齐共同可用的位置事件后安排网络事件。**τ是位置事件条数，不是毫秒。** p8实例τ=5，若位置50Hz则对应约100ms仿真跨度。

有网络反馈影响运动时，p8 §5明确不能把一条固定轨迹发送给不同网络场景后共用运动结果，须一对一闭环或复制完整物理实例。这对未来IDEAL/WIFI-BASE/WIFI-OPT实验尤其重要。

### 5.2 比当前好的地方与代价

1. 时间戳、每机器人齐备队列与事件安排比我们当前立即应用POSITION更明确，适合补足网络移动位置时间合同。
2. 主机间逻辑协调比MUNILS单机共享内存更自然；可分摊计算/记录负载。但本机尚未证明137.930ms来自资源竞争，不能承诺拆机器就治好。
3. Reporter独立有利于隔离记录开销。我们26已定位同步写盘等待、27/B已采用RAM封存路径，不能把未来论文思想重复算成新收益。
4. 论文承认τ越大，网络反馈越迟；选择τ是精度/控制开销权衡。不能把其τ=5直接设为我们5ms，也不能无视本项目原状态期限。

pp11–12结果156.7→129.2墙钟秒、17.5%收益，是相对“先物理再网络”的串行基线。我们已并行、已限步，不能照搬这项加速比例。论文还明确放松NAC；它不是每个异步ROS Action都严格因果、无尾延迟的证明。

### 5.3 复现条件

正文可重建DTMA队列原型，但本次未找到完整可归属本文的DUSC发布代码/场景。公开[PyServer](https://github.com/juhgiyo/pyserver)只是通用连接依赖，不是DTMA本身；[RotorS](https://github.com/ethz-asl/rotors_simulator)采用ROS1/catkin等依赖，论文展示Ubuntu16.04，不能直接作为Humble Nav2执行层。

算法还需澄清：正文“至少τ”与伪码第7行`>τ`、第14行安排`min N(Si)`而第16行推进τ的对应关系。自行选择解释后只能称“依据思想重实现”，不能声称原算法精确复现。

适配到本项目需要保留真实CDR业务、同UUID/Nav2 Action结果和故障停止；论文条件callback不应代替这些业务。FSA→NSA用TCP也不表示模拟无线中的业务就自动可靠。

**本项目选择：DUSC的依赖划分、位置时间戳/齐备队列最值得局部采用；跨主机方案列为资源需求明确后的第二路线，不现在重建整套平台。**

## 6. P2 CORNET 2.0：网络隔离有价值，同步不适合当前落后问题

PDF pp2–3 Fig1–4：Gazebo物理侧与Mininet-WiFi/Containernet数据侧分离，容器/namespace与虚拟接口承载真实ROS/ROS2应用；时间和位置走独立控制平面。其端点/数据面设计适合参考。

同步规则是：网络处理提前完成时，等待补足模拟延迟；晚于物理时间期限则丢弃。p4明确承认只支持网络处理比物理侧快的一方向。其验证施加1秒网络延迟、Gazebo RTF约0.49–0.65，并非300ms最坏健康间隔测试。

因此：

- 它不能让已落后的ns-3更快；用“晚包直接丢弃”处理Goal可能使原未知请求更多。
- 当前任务要求ns-3 Wi-Fi MAC/PHY，不能切换Mininet-WiFi后仍声称使用同一网络模型和基线。Linux mac80211_hwsim/wmediumd与ns-3模型的实现和可研究参数不同。
- 命名空间/原生虚拟网卡路线可能减少手写ROS Action转接的语义损失，但未提供当前五类Action端点、UUID、断链取消或可靠停止的即用实现。

作者库 [CORNET2.0](https://github.com/rbccps-iisc/CORNET2.0/tree/80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4) 本次固定到 `80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4`。真实配置可见DockerSta/AP/wmediumd及Foxy/Gazebo11示例，复用网络拓扑思想可行；但依赖未锁定、混有Python2/ROS1/Foxy入口，已读`network_coordinator.py`仍含stub。**本次在已审入口中没有确认图4完整逐包同步接线，不推断仓库所有地方都不存在。**

静态依据：[网络配置](https://github.com/rbccps-iisc/CORNET2.0/blob/80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4/network/network_config.py)、[协调器](https://github.com/rbccps-iisc/CORNET2.0/blob/80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4/network/network_coordinator.py#L39)、[Foxy镜像定义](https://github.com/rbccps-iisc/CORNET2.0/blob/80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4/docker_container/Dockerfile.focalfoxyNWH)、[位置示例](https://github.com/rbccps-iisc/CORNET2.0/blob/80f6c0680f1f7aca4fbd45a3a02c93ff1c5f5cf4/robot/test/ros2_robot_position.py#L29)。

**本项目选择：采用其控制/数据平面分离与容器端点思路，不采用以晚包丢弃换取时间对齐的规则，不更换研究指定的ns-3网络模型。**

## 7. P5 SynchroSim：可调窗口不是可靠交付的替代

PDF pp3–4 §IV、算法1/式(2)：从人工初值w开始，取发送和接收机器人的速度，按 `wa = w + (Vp−Vs)/1000` 调窗，再`t += wa`请求下一窗；p5设置初始1ms。p4明确选择TCP以改善可靠性。

有用之处是指出同步精度和通信/运动时尺度有关，固定窗口并非所有场景都最好。窗口更小可能降低反馈生效粒度，也可能增加握手和调度开销；需要结合本项目负载实测，不能默认1ms比10ms更快。

主要边界：

- 正文没有可执行的post-physics ACK、最大领先量、暂停恢复/失败收束或墙钟健康界；公式不是完整时间协调器。
- 速度差的符号、标量/向量约定、单位系数及窗口上下界没有完整规定。按字面在某些速度差下可能得到非正窗，这是公式适用边界待澄清，**不是已证本项目机器人发生了此问题**。
- pp5–7模拟为Iris/PX4/MAVROS与两Husky、32×32图像、按距离/LOS/NLOS比较；平均延迟以10帧批次计算。p7实机是ROS Melodic两Duckiebot、小实验区；p8把ROS2/DDS列为未来扩展。
- 速度来自Gazebo可用于仿真协调/网络移动模型，但不应作为新增真值输入注入冻结RL。图像实验和真实Nav2 Action/整图/peer-mask负载不同，不能照搬约10%改善比例。

作者页面 [SynchroSim](https://pralgomathic.github.io/research/synchrosim/) 提供论文；关联实验室项目链接到RobSenCom，但没有证据该仓库就是2022实验的精确版本。当前关联公开代码存在下节所列静态阻断。

**本项目选择：保留窗口尺寸应依据误差/开销权衡的思想；不直接使用速度差公式动态改生产步长，不把TCP的可靠性归功于调窗算法。**

## 8. P1 Reliable Middleware：可靠传输方向相关，公开实现不够完整

PDF pp4–6：与P5相近的速度差公式、初始1ms窗口，增加ROS2/Foxy、ROS1桥和DDS叙述。p5式(3)仍为 `wa = w + (Vp−Vs)/1000`；没有给出当前所需的完整ACK/领先/安全停止合同。

值得借鉴的是将处理、传输、传播、排队延迟区分，并强调TCP与可靠数据传输。它没有证明DDS可靠QoS必然使用TCP，也不能让我们中间一次发送的UDP隧道自动变可靠。[ROS2官方QoS说明](https://docs.ros.org/en/foxy/Concepts/About-Quality-of-Service-Settings.html)

实验解释要谨慎：p7–8实机手动控制，以约293797字节ROSbag经netcat发送，用tcpdump和ping估计性能；不是连续LiDAR—SLAM—RL—Nav2闭环。其“ROS1 master”比较还混合了不同网络转发拓扑；不能把全部差异归于ROS1名称发现master。p9 EMANE实验也承认没有复制同一ROS实验条件。

### 8.1 两篇关联作者库：可得到，不是可直接运行的release

作者[实验室项目](https://mpsc.umbc.edu/projects/robsencom)链接 [RobSenCom](https://github.com/Emon-dey/RobSenCom)。本次检查提交 `20cfacfe74d1d159630c01b559682739417370d1`，时间2023-03-18；不认定它精确对应任一2022论文实验。

| 静态源码位置 | 已核事实 | 可复现性结论 |
|---|---|---|
| [net.cpp:105–163](https://github.com/Emon-dey/RobSenCom/blob/20cfacfe74d1d159630c01b559682739417370d1/synchronization_module/scripts/net.cpp#L105) | 截断C++声明，直接混入Python `def main`，后有重复main/TODO；引用的protobuf定义未见提供 | 不能按README直接构建；不是补依赖即可解决 |
| [phy.cpp:89–161](https://github.com/Emon-dey/RobSenCom/blob/20cfacfe74d1d159630c01b559682739417370d1/synchronization_module/scripts/phy.cpp#L89) | 截断表达式、未实现服务和重复main | 原物理/网络握手不可据此验收 |
| [模块CMake](https://github.com/Emon-dey/RobSenCom/blob/20cfacfe74d1d159630c01b559682739417370d1/synchronization_module/CMakeLists.txt) | 仅依赖查找片段，缺完整可执行目标 | 缺完整可构建工程定义 |
| [qos.cpp:10–32](https://github.com/Emon-dey/RobSenCom/blob/20cfacfe74d1d159630c01b559682739417370d1/network_module/scripts/qos.cpp#L10) | 速度变量使用序号/字符串长度，QoS创建时计算，不等于真实速度持续调TCP窗 | 不能声称论文公式已有精确实现 |
| [gazebo.cpp:198–273](https://github.com/Emon-dey/RobSenCom/blob/20cfacfe74d1d159630c01b559682739417370d1/physics_module/scripts/gazebo.cpp#L198) | 有请求驱动runWorld/响应的ROS1骨架，默认10ms；同文件仍有未定义/损坏片段 | 可借鉴局部意图，非完整1ms自适应ROS2复现 |

以上未实际试编译，故不伪造“运行build FAIL”；结论是存在清楚的**静态复现阻断**。也不由代码公开不完整推断论文结果虚假。

**本项目选择：可靠传输原则相关；原样换库不适用。** 若采用TCP，必须让业务字节、TCP重传与ACK真实经过ns-3 Wi-Fi。只把Host↔Hub控制socket换TCP、中间仍一次UDP发Goal，不会修复现故障。TCP字节到达也不等于Nav2接受/完成，仍要保留UUID幂等、真实响应和有限未知状态。

## 9. 能否解决当前问题：逐项判断

| 已有问题/需求 | 论文能直接解决吗 | 可采用的具体内容 | 尚需本项目自行完成 |
|---|---|---|---|
| ns-3事件计算曾落后Gazebo | MUNILS/CORNET单向规则不直接解决；DUSC有协调思路 | 保守时间授权、齐备事件/完成确认 | 当前实际ACK背压继续保留；性能与故障边界实测 |
| B两次Goal丢失后C永远等 | 都没有现成Nav2修复 | P1/P5可靠传输；MUNILS/CORNET原生网络端点 | 同session/RPC/UUID、有界可靠交付、幂等、真实接受/结果、未知所有权及停止闭合 |
| Peer→C捕获137.930ms | 五篇均无该路径的直接保证 | 减少不必要中转、隔离处理/记录的方向 | 确认DDS writer/reader与executor等待的具体责任段，不刷新戳或松300ms |
| 无DDS旁路、接近真实网络 | MUNILS/CORNET隔离架构更强 | namespace/TAP、明确本地/中央边界 | 为SLAM/Nav2本地链与全部中央关键流重新接线和负例验证；不能把中央状态挪到理想侧 |
| RF位置生效时间语义 | DUSC最相关 | 带时间戳的位置队列和网络事件顺序 | 定义每位置来源时间/版本、采样保持与admission，量化现误差；没有证明它导致B失败 |
| 记录I/O阻塞 | DUSC Reporter分离相关 | 控制与记录分离 | 当前RAM封存已有改善，不重复归功于新算法；不隐藏真实记录成本 |
| 高分辨率地图/大mask负载 | 没有相同场景证据 | 原生传输可保留真实协议成本 | 使用冻结真实业务负载测试，不能用小图像/ping替代 |
| 实机部署 | 都有可参考接口/部分硬件实验 | 原生端点、可靠业务、信息新鲜度分层 | 本地SLAM/Nav2、中央无线边界、真实断链/反馈处理；本轮未运行硬件 |

## 10. 复现可行性与工作量分层

以下是源码/文献评估，**没有任何一篇获得本轮“复现成功”结论**。

| 方法 | 依赖/材料可得 | 算法概念重建 | 原论文完整实验复现 | 接入当前三Waffle工程 |
|---|---|---|---|---|
| MUNILS | 通用依赖可得，完整作者patch未找到；数据需申请 | 单机SHM/单向节流可重建，低到中等工作量 | 缺版本/补丁/原始数据，尚不具备直接条件 | namespace中高；替换调度器还需ns-3.40移植及慢端验证；PX4层不需要 |
| DUSC | PyServer/RotorS可得，完整DTMA实现未找到 | 队列/授权原型可重建，低到中等；需澄清伪码 | ROS1/RotorS旧环境及精确场景缺项 | ROS2适配与全部业务透明交付工作量高，跨主机另有同步成本 |
| CORNET 2.0 | 官方库可得但依赖旧、已审同步入口有stub | 端点/分平面可参考；逐包规则可重建 | 原精确环境、同步接线需确认 | 迁移namespace可研究；更换Mininet会改变指定研究模型 |
| SynchroSim | 论文可得；关联库非精确release且不完整 | 数值窗公式容易重写，不等于完整系统 | 初窗1ms已明确；具体速度轨迹/完整负载/信道/代码版本缺项 | ROS1→Humble/Nav2并可靠Action，工作量高 |
| Reliable Middleware | 关联库存在确定静态阻断 | 可靠传输原则可独立采用；窗映射需解释 | 不具备现成构建与完整实验条件 | 原样替换不可行；需独立可靠业务层及回归 |

“低/中/高”为移植范围判断，不是工时承诺。没有自行安装旧ns-3、PX4、Docker/内核模块或给宿主配置网络，也没有向作者发消息申请代码。

## 11. 方案选择与有界的下一步建议

### 11.1 当前采用/暂不采用

1. **继续采用**现有锚点+真实WorldStep/actual-native-ACK/有限credit控制，作为当前可恢复工程基线；保持原300ms墙钟与停止合同。论文未给足证据支持立即替换更好。
2. **优先借鉴DUSC**完善网络位置时间身份和依赖描述；这是比泛泛缩小步长更明确的问题。先把位置admission、源戳/采样保持与包事件因果关系说清，不先新建完整分布式框架。
3. **可靠Action是优先修复项**。评估真实网络内TCP或保留原UUID的确认/幂等机制；把它作为恢复既定Action合同的通信适配，不作为新RL行为或性能优化算法。所有实验组使用同一冻结配置。
4. **MUNILS/CORNET端点隔离作为后续候选架构**。若当前手写代理的可靠性/原生DDS语义继续成为主要瓶颈，原生TAP/namespace值得单独方案验证；不把本地雷达/局部导航内部流全部塞入无线，也不让中央关键输入走直连。
5. **暂不采用**速度差动态调窗、CORNET晚包丢弃、直接移植MUNILS ns-3.29调度补丁或引入PX4。当前没有针对本项目的性能证据；增加握手频率、改变窗口可能反而增加主机负载。

### 11.2 若做比较，怎样才能判断“更好”

本段是后续最小验证建议，**本轮未执行、不自动启动新阶段或增加Gazebo预算**。

- 先做隔离时间/消息重放，使用相同源时间、同一实际负载、同一事件seed，比较当前协调器与一个明确候选；一次只变时间推进或传输层之一。
- 包含正常推进、RTF下降/波动、ns-3慢于物理、clock漏样、暂停恢复及节点失联；慢到不可能满足墙钟期限时，应明确失败/停机，不能靠伪造时钟或跳事件“追平”。
- 同时测绝对/相对逻辑偏差、位置与包事件顺序、墙钟延迟尾部/源龄、CPU/记录成本、漏/重/乱序、同UUID实际调用数及停止闭合；均值接近零或模型吞吐量单项不够。
- 现300ms健康、200ms收件、400/550ms源龄和原停止规则继续使用；不按候选结果调阈值。共享内存只用于允许的同步/网络位置控制，不补送Policy业务。
- 如候选在慢端、暂停与Action故障处理上不退化，并实际降低控制开销或交付长尾，再另行申请/预注册有限Gazebo对照。冻结权重不动，A/B/C共同执行条件重建，不能拿旧600sim替代新条件。

## 12. 最终评审意见

**论文给出的价值是真实的，但没有一篇已经提供适合当前三机Nav2探索、可以直接替换并解决全部问题的完整工具。** 对当前负载，真实ACK背压的保护范围比MUNILS/CORNET的单向限制更对症；对因果时间设计和网络端点架构，DUSC、MUNILS/CORNET确有当前实现应学习的部分。

“推进时钟已受控”仍须限定到已观察的有界运行。完整的消息交付、位置生效顺序、墙钟及时性和Action停止合同尚未全部闭合。该文献评估不改变followup04的 **B运行FAIL、NET-01 BLOCKED、NO-GO NET-02**，也不签发新方法性能或复现PASS。

本次交付仅新增研读、来源索引和项目入口文档，Git提交与独立分支发布用于交接；不更改冻结发布tag、权重、行为源码或历史实验。

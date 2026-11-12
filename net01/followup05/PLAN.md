# NET01 followup05：有界可靠 Action RPC 外部适配

状态：root design accepted，源码实施中；实际检查/ROS/native运行仍待root具体审入口。起点62379f6，新分支net-01/reliable-action-integration。此轮不是旧4case预算续用，不自动Gazebo。0RL/训练/Frontier/Nav2/SLAM/冻结源码/模型/物理/网络V3/旧证据修改，0host network/TAP/root。文件所有权：生产者只action_wire.py、gateway.py及followup05新文件；root/metric独审，不改其它adapter或CPU/clock/GC。

## 最简单正确候选

采用现真实ns3 WiFi UDP完整CDR路径的**应用层可靠交付**，不叫TCP。真正native TCP需改C++socket/连接生命周期/streamframing及新ELF，多业务共享流还涉及HOL与重新基线，超出当前一次RPC丢失缺口的最小范围。可靠思想来自论文/已做TCP小试，不冒称复现论文TCP算法。

原Action offsets0/2/4请求、1/3/5响应的原生成CDR、UUID/session/robot/flow/rpc完全不变。每次重送同一immutable bytes与rpc，Hub仍分配新native消息ID，所有尝试都走原实际WiFi/整包Recv；不能用源blob恢复。feedback/status/readiness现流程不改，不增加业务优先级。

新增每robot offset9仅传输元数据：2B(version1, acknowledged_original_offset)，原rpc仍Hub的8B字段；按原session/peer/offset/rpc精确匹配。ACK只证明代理已记录请求或收到真实响应，不等于Nav2 accepted/terminal。无ACK-of-ACK。

- C初送原请求，R先保完整原body并只call_async一次，再ACK请求。R重复同key/body若pending只再ACK；完成且响应仍待确认时由原cache按既定周期重送，已ACK不重新开放预算（仍可ACK该重复请求）；同key不同body为实际协议错误。
- C收到真实requestACK后停止请求重送，但不完成原Future。GetResult可以等待整段导航；响应budget只在R真实future完成并产生原CDR时开始。
- R真完成后有界重送相同原response，C匹配原pending后真实DDS send_response仍由原service完成；C重复response若与已完成原CDR完全相同，只重ACK、不再次完成Future。响应先于请求ACK也可确认原请求已被执行。
- 原retired服务必须保到真实DDS send_response成功后销毁；pending tuple/status接口保持，不因generation变动抛弃已准入真实结果。新SendGoal权限在ready撤回时立即失效；未确认/仍在重送的SendGoal不能在权限恢复后悄悄创建新目标。原R Guardian gate、late-accept exactUUID cancel保持。

## 事前锁定预算与失败

传输确认候选参数固定：重送间隔.2wall、总确认窗口1.0wall、最多5次（含初送）。这是新适配合同，不放宽原.3/.2wall/.4/.55sim/.12lag。monotonic时间，复用Gateway handler边界与outer progress，不新线程/timer、不改clock/调度。一次tick只发一次到期尝试，不追赶爆发，调度慢可能少于5次，不能超总界补发。

真实收件处理前和tick均先核已到deadline；实际处理已晚则保持unconfirmed/INVALID，不用新ACK抹去原超时。正常先处理当前hub已可读消息，再tick；同一时刻expiry边界用`now >= deadline`，有明确日志。永久断链/确认耗尽调用Gateway.fail并保留首错，停所有可靠重送；原Future、retired inflight与未知UUID仍真实未决，不能清表/合成Rejected或terminal充PASS。恢复不解锁guard、不给新UUID。物理/本机cancel/zero/PAUSE仍按原路径，Gateway.fail后原receive全部discard不开放理想cleanup通道。

这里不能承诺永久partition时既返回一个真实Nav2响应又保持原语义；有界目标是**有界检测并退出等待策略/停止，明确未知，非伪造RPC闭合**。原pending原件和停止认证FAIL必须保留。

## 最小验证预算 / 实际入口待源码固定后root准入

1. 一个0Node定向check（纯状态/受控future，不执行策略），覆盖精确body/ACK错session错offset、响应先于requestACK、ACK丢失重ACK、期满不被late包复活、旧service状态接口不变。无新泛框架。
2. 一个固定分阶段真实DDS generated Action→实际ns3.40 WiFi→真实DDS fixture，复用ControlledServer/LinkSession/HubClient/ros-python.sh与旧82bc。新文件不修改旧check_action_wifi历史断言。复用实际Gateway固定C91/R92隔离域，不新增生产domain参数，固定session本轮专用；0Nav2真实进程/无非零速度publisher（实际LocalStop零Twist/PAUSE保留）/无Gazebo/训练。总60wall（含owned Hub/native/ROS收尾），场景预算另在实际argv中固定：真实3robot五端点与原UUID，短物理blackout使首请求丢失；受控server真完成响应时的物理blackout使首响应丢失；重复/ACK丢失；长GetResult合法等待>1.0wall后真实成功；原Cancel/CANCELED与feedback/status；最后永久断链必须INVALID/unknown（原.5wall readiness撤回可先于1wall确认上限触发，不能为凑五发放宽）而非fakeclosure，验证实际Gateway.fail/receive discard及本机清理边界。

故障具体sim/wall阶段、域、fixtureargv/rootfs/owned Hub/native硬界和所有状态断言在源码READY时送root，不在本PLAN给尚未实现的命令冒充可执行。ACK级定点丢弃若为fixture应用层注入必须明确标注，不能冒称PHY丢包；请求/响应物理负例用原Range gate、V3不改。每次真实尝试按nativeID/RPC/CDR关联，不以Future.set_result或代理callback返回代替原中央client真收响应。

任何首失败保原件，必要最小接口修补必须另登记复验，不能无限跑/调重送参数。结果只证明零运动真实ROS/ns3外部适配，不自动签真实机器人网络安全、120sim闭环或NET02。既有B首heartbeat发布→Ccapture未观测137.93ms、整Rcapture空194.945ms仍独立未闭合；本轮不混改调度/GC/clock。


## 已固定生产源与唯一待准入实际命令

root固定生产源提交51c5ac75971091913ad9a77f78d8b22327093a73；生产者此后不再改action_wire/gateway。实际0Node定向check已由helper唯一执行，16PASS/exit0/1.676wall，原件evidence/reliable-state-01；非DDS/网络证据。

SOURCE_READY：`check_reliable_wifi.py`直接构造实际Gateway B（原C91/R92）、原ControlledServer和真实中央ActionClient。原rootfs/LinkSession/82bc/V3，synthetic实际DDS Clock10ms，每10wallms最多一个样本，不追赶；不宣称Gazebo时间。health/bound输入沿旧local-guard夹具方式为明确synthetic当前state，仅用于可控arm，不计作过网health资格。PAUSE为真实DDS spy、zero为真实Twist收件，仅期望全0，不签物理停机。

固定顺序：真实三STA HELLO/ACK→3五端点→.25wall物理blackout丢tb1请求→恢复/原UUID成功→tb2 GetResult首requestACK在实际RX后应用级drop一次，同RPC重送不二call，真等1.2wall合法→.25wall物理blackout时release真实GetResult以丢首response→恢复收到原result→tb3首SendGoalresponseACK在实际RX后应用级drop一次，response重送/C重ACK不二DDS完成→原Cancel/CANCELED/反馈/status→全真实pending/confirmation drain→永久物理blackout+新Goal，原readiness撤回或确认上限先到者锁存INVALID/unknown→实际Gateway.fail停止所有重送，原zero/PAUSE继续，原pending不清→Gateway.close/END/Hub退出封存。

postfailure receive-discard检查只显式把以前真native收到的完整CDR及meta交回同实际Gateway.receive，标注method-level replay，不冒充新无线收件/不构造理想cleanup旁路。断链后没有继续人为STEP绕过生产失败时钟门禁。ACK精确丢弃点有fixture-injections原件，与PHY断链区分。

工作区根待root准入命令：

```sh
rtk proxy python3 -B net-01/workspace/net01/followup05/run_reliable_wifi.py
```

runner独占evidence/reliable-wifi-01与workspace/f05-wifi-01.sock，60wall总界；Hub自有50wall（native未改）、ROS fixture活动loop45wall，close另沿原最多3秒flush；outer60wall才是包含全部收尾硬界。ROS使用原`ros-python.sh`，没有namespace/宿主网络/TAP更改。全部argv于启动前写commands.json；首次错误保留，超总界只KILL本runner自有PG并明确FAIL，不正常发全PG SIGINT伪装有序退出。root确认原91/92无本项目残留/其它业务后才准run；不触domain69。无构建、无其它CPU试验并行。该命令尚未执行。

夹具SOURCE_READY补充：创建ControlledServer前先在原R91/92节点观察实际精确Action/ManageLifecycle服务与cmd_vel外部reader均不存在（.6wall有界发现窗），否则不发送任何合成Goal。验完整Goal frame/stamp/pose/behavior_tree经标准generated序列化规范化后全typed字段相等；capture SHA与每条实际native完整CDR逐(sender,receiver,flow,rpc)对应。恢复Rangegate前明确request/response均未wholeRX，dedupe核R2.forwarded_requests恰2，不以dictkey唯一冒充只call一次。feedback/status本身仍原不可靠topic，本轮不称全面可靠。

最终本机清理断言不仅观察spy请求，还等全部原LocalStop.futures done，并逐机收到actual_local_pause_response success；仍无真实物理停止认证。


## 01首失败与唯一02复验准备（未运行）

实际01使用固定d712，outer3.639wall exit1、ROS1/Hub0/native0，无forced、ENDtrue、两executor shutdowntrue、0Goal/0ControlledServer/无pending。preflight因全图service-topic列表含12个同名客户端请求路径而FAIL；原evidence/reliable-wifi-01与原commands/结果保持，不改PASS。不是Action重送运行阶段失败，也不能据名字列表断言真实Nav2存在。

源码依据（仅只读，没有新增Node诊断）：installed Humble rclpy/node.py1795–1804将get_service_names_and_types定义为service topics；1743–1761的by_node才明确service server topics。installed client.py153–160的service_is_ready直接调用service_server_is_available。官方Humble rmw_fastrtps_shared_cpp/src/rmw_service_names_and_types.cpp53–57调用GraphCache.get_names_and_types；rmw_dds_common/src/graph_cache.cpp690–699把data_readers与data_writers一起demangle，未按服务端过滤。所以名字清单仅保诊断；改用已有九Action typedclient.service_is_ready + 三LocalStop.pause.service_is_ready真服务端判据，foreign cmd_vel readers与原Cfacade判据保持，无新Graph节点/兼容层。

02唯一准备入口（root另准才运行）：

```sh
rtk proxy python3 -B net-01/workspace/net01/followup05/run_reliable_wifi.py --case 02
```

新exclusive evidence/reliable-wifi-02与f05-wifi-02.sock，runner仅接受01/02且旧01目录已存在拒绝覆盖。所有协议/网络/时钟/故障窗口/保护/60-50-45wall与case场景原样，仅修前检oracle/新结果路径。生产ActionWire/Gateway仍51c未动。最多这一次02复验，失败先保原件不自动增03。

主源链接：https://github.com/ros2/rmw_fastrtps/blob/humble/rmw_fastrtps_shared_cpp/src/rmw_service_names_and_types.cpp#L53-L57 ，https://github.com/ros2/rmw_dds_common/blob/humble/rmw_dds_common/src/graph_cache.cpp#L690-L699 。


## 02 oracle失败与唯一03必要复验（未运行）

02原FAIL保留，16个正例断言成立；3个真实UUID原Goal字段一致、两SUCCEEDED/一CANCELED、真实物理request/response丢失恢复与ACK重送、1.2wall GetResult长等、RPC/confirmation全drain。outer6.847wall/ROS1/Hub0/native0/无forced；永久断链尚未执行。首错是哈希断言的`flow>=200`误把LinkSession65534/65535六个HELLO/ACK算成Action，Gateway捕获范围本来200<=flow<300。原132条actualdelivery恰6个unmatched全这两个握手flow，其余原Action完整body不变；不能将02整个结果追认PASS。

根审批准准备仅一行filter纠正为200<=flow<300，runner显式增加case03，生产51c/ACK协议/网络/源/seed/门限/时基/故障阶段均不改。03重复正例独立计作实际调用；01/02原目录及socket名字不复用，不增加通用框架。03仍总60/Hub50/active45+原close界。

待root锁定准入后唯一入口：

```sh
rtk proxy python3 -B net-01/workspace/net01/followup05/run_reliable_wifi.py --case 03
```

03为同固定全阶段夹具，用于完成先前因checker错误未执行的永久断链与真实Gateway.fail/原未知RPC/本机零与PAUSE响应门禁。不得自动新增04或因结果改参数重跑；这条准备不授权Gazebo/训练/NET02。

# NET01 followup05：有界可靠 Action RPC 外部适配

状态：root design accepted，源码实施中；实际检查/ROS/native运行仍待root具体审入口。起点62379f6，新分支net-01/reliable-action-integration。此轮不是旧4case预算续用，不自动Gazebo。0RL/训练/Frontier/Nav2/SLAM/冻结源码/模型/物理/网络V3/旧证据修改，0host network/TAP/root。文件所有权：生产者只action_wire.py、gateway.py及followup05新文件；root/metric独审，不改其它adapter或CPU/clock/GC。

## 最简单正确候选

采用现真实ns3 WiFi UDP完整CDR路径的**应用层可靠交付**，不叫TCP。真正native TCP需改C++socket/连接生命周期/streamframing及新ELF，多业务共享流还涉及HOL与重新基线，超出当前一次RPC丢失缺口的最小范围。可靠思想来自论文/已做TCP小试，不冒称复现论文TCP算法。

原Action offsets0/2/4请求、1/3/5响应的原生成CDR、UUID/session/robot/flow/rpc完全不变。每次重送同一immutable bytes与rpc，Hub仍分配新native消息ID，所有尝试都走原实际WiFi/整包Recv；不能用源blob恢复。feedback/status/readiness现流程不改，不增加业务优先级。

新增每robot offset9仅传输元数据：2B(version1, acknowledged_original_offset)，原rpc仍Hub的8B字段；按原session/peer/offset/rpc精确匹配。ACK只证明代理已记录请求或收到真实响应，不等于Nav2 accepted/terminal。无ACK-of-ACK。

- C初送原请求，R先保完整原body并只call_async一次，再ACK请求。R重复同key/body若pending只再ACK，完成则原cache回复；同key不同body为实际协议错误。
- C收到真实requestACK后停止请求重送，但不完成原Future。GetResult可以等待整段导航；响应budget只在R真实future完成并产生原CDR时开始。
- R真完成后有界重送相同原response，C匹配原pending后真实DDS send_response仍由原service完成；C重复response若与已完成原CDR完全相同，只重ACK、不再次完成Future。响应先于请求ACK也可确认原请求已被执行。
- 原retired服务必须保到真实DDS send_response成功后销毁；pending tuple/status接口保持，不因generation变动抛弃已准入真实结果。新SendGoal权限在ready撤回时立即失效；未确认/仍在重送的SendGoal不能在权限恢复后悄悄创建新目标。原R Guardian gate、late-accept exactUUID cancel保持。

## 事前锁定预算与失败

传输确认候选参数固定：重送间隔.2wall、总确认窗口1.0wall、最多5次（含初送）。这是新适配合同，不放宽原.3/.2wall/.4/.55sim/.12lag。monotonic时间，复用Gateway handler边界与outer progress，不新线程/timer、不改clock/调度。一次tick只发一次到期尝试，不追赶爆发，调度慢可能少于5次，不能超总界补发。

真实收件处理前和tick均先核已到deadline；实际处理已晚则保持unconfirmed/INVALID，不用新ACK抹去原超时。正常先处理当前hub已可读消息，再tick；同一时刻expiry边界用`now >= deadline`，有明确日志。永久断链/确认耗尽调用Gateway.fail并保留首错，停所有可靠重送；原Future、retired inflight与未知UUID仍真实未决，不能清表/合成Rejected或terminal充PASS。恢复不解锁guard、不给新UUID。物理/本机cancel/zero/PAUSE仍按原路径，Gateway.fail后原receive全部discard不开放理想cleanup通道。

这里不能承诺永久partition时既返回一个真实Nav2响应又保持原语义；有界目标是**有界检测并退出等待策略/停止，明确未知，非伪造RPC闭合**。原pending原件和停止认证FAIL必须保留。

## 最小验证预算 / 实际入口待源码固定后root准入

1. 一个0Node定向check（纯状态/受控future，不执行策略），覆盖精确body/ACK错session错offset、响应先于requestACK、ACK丢失重ACK、期满不被late包复活、旧service状态接口不变。无新泛框架。
2. 一个固定分阶段真实DDS generated Action→实际ns3.40 WiFi→真实DDS fixture，复用ControlledServer/LinkSession/HubClient/ros-python.sh与旧82bc。新文件不修改旧check_action_wifi历史断言。暂定C/R隔离域104/105，固定session本轮专用；0Nav2真实进程/无速度publisher/无Gazebo/训练。总60wall（含owned Hub/native/ROS收尾），场景预算另在实际argv中固定：真实3robot五端点与原UUID，短物理blackout使首请求丢失；受控server真完成响应时的物理blackout使首响应丢失；重复/ACK丢失；长GetResult合法等待>1.0wall后真实成功；原Cancel/CANCELED与feedback/status；最后永久断链耗尽必须INVALID/unknown而非fakeclosure，验证实际Gateway.fail/receive discard及本机清理边界。

故障具体sim/wall阶段、域、fixtureargv/rootfs/owned Hub/native硬界和所有状态断言在源码READY时送root，不在本PLAN给尚未实现的命令冒充可执行。ACK级定点丢弃若为fixture应用层注入必须明确标注，不能冒称PHY丢包；请求/响应物理负例用原Range gate、V3不改。每次真实尝试按nativeID/RPC/CDR关联，不以Future.set_result或代理callback返回代替原中央client真收响应。

任何首失败保原件，必要最小接口修补必须另登记复验，不能无限跑/调重送参数。结果只证明零运动真实ROS/ns3外部适配，不自动签真实机器人网络安全、120sim闭环或NET02。既有B首heartbeat发布→Ccapture未观测137.93ms、整Rcapture空194.945ms仍独立未闭合；本轮不混改调度/GC/clock。

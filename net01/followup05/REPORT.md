# NET01 followup05：可靠 Action RPC 接入结果

本轮在原 ns-3 WiFi UDP 路径接入同 RPC 有界重送与传输 ACK。**03 的零运动集成夹具通过；NET01 整体验收仍 BLOCKED。** 没有 Gazebo、真实 Nav2、Policy forward 或训练。不是 TCP，也不是整套论文中间件移植。独审见 [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md)。

生产源固定 `51c5ac75971091913ad9a77f78d8b22327093a73`；最终夹具固定 `90c2e4c44e4db999e5875817b4d83d9bb46a9b64`。仅改 `action_wire.py`、`gateway.py` 及本目录新夹具/文档。原 native 82bc、V3、冻结策略、模型、Nav2/SLAM、物理、时钟与安全门限未改。

## 实现及边界

请求与响应保持原 session/robot/flow/RPC/UUID 和完整生成 CDR。每次尝试走原真实 WiFi 整包接收路径，原 R 缓存保证同 RPC 只调用真实服务一次；同 key 不同 body 显错。新增 offset9 的 2 字节 ACK 仅表示代理收件，不表示 Nav2 接受或完成。候选固定 .2wall 重送、1.0wall 确认界、含初发最多5次。GetResult 请求确认后可合法等待真实任务，不把整段服务等待计入响应确认预算；响应预算从真实服务完成开始。

响应先到、ACK 丢失、重复响应均不二次完成原 Future；晚 ACK 不撤销到期失败。原 ready/Guardian/retired-service/send_response 生命周期保留。永久失联锁存 INVALID、停止重送并保留真实未知 Future/ownership，不合成拒绝或终态。Gateway status/落盘另列可靠确认未决计数，原停止不能因清空计数假闭合。feedback/status/readiness topic 本身没有改成可靠通道。

## 实际执行账本

| 执行 | 实际结果 | 退出与范围 |
|---|---|---|
| reliable-state-01 | 16 checks PASS | 唯一0Node检查，exit0，1.676wall；非DDS证据 |
| reliable-wifi-01 | **FAIL：前检 oracle** | 3.639wall，ROS1/Hub0/native0；0Goal，未进入业务。全图服务名称包含客户端路径，不能作为真实服务存在判据 |
| reliable-wifi-02 | **FAIL：CDR oracle** | 6.847wall，ROS1/Hub0/native0；16正例成立后，`flow>=200`错误包含6个Link握手。126条Action RX全匹配；永久断链阶段未执行 |
| reliable-wifi-03 | **有限夹具 PASS，预定永久失联负例成立** | 7.299wall，ROS0/Hub0/native0，20 checks；3个真实生成Action受控服务各接受1Goal，终态4/4/5 |

三个真实 WiFi case 均无强制终止；所有01/02 FAIL原件保留，没有追认整个case通过。两次修正只改夹具判据/独占case路径，生产51c不变。实际PID未由runner落盘，不补造；原owned进程等待退出记录保留。此轮没有第四次试验。

## 03 的实际无线与语义证据

原件：[ROS结果](evidence/reliable-wifi-03/ros/result.json)、[Gateway记录](evidence/reliable-wifi-03/ros/gateway/network-gateway.json)、[实际完整CDR](evidence/reliable-wifi-03/ros/actual-native-CDR.json)、[Hub/native结果](evidence/reliable-wifi-03/hub/result.json)、[退出记录](evidence/reliable-wifi-03/process-exit.json)。真实DDS五端点在创建受控server前均无server-ready；原C91/R92 loopback隔离、foreign cmd readers为空。没有实体机器人。

- tb1 SendGoal首发 native19 未完整到R，同RPC第二发23到R，原中央client收到接受，R只创建一个目标。全Goal的frame、stamp、pose、behavior_tree及UUID均与发送值相同；真实反馈/status与SUCCEEDED成立。
- tb2 GetResult的首次请求ACK在**真实native RX后由夹具应用层丢弃**，请求共2发、R真实调用仍仅一次。请求ACK后真实结果等待超过1.0wall而不误报传输失败。响应共2发，原native98和重送102都在恢复后收到：只能证明**响应延迟、重送和重复接收处理正确**，不能证明原响应永久丢失，也不能说重送唯一促成该响应恢复。0Node单元中的完全丢弃响应恢复证据与此分开。
- tb3 SendGoal响应ACK同样在实际RX后应用级丢一次，响应2发，原client未二次接受；真实Cancel返回原UUID列表，GetResult为CANCELED。两个ACK应用注入不冒称PHY丢包。请求/响应窗口的Range断链是实际模型传播路径故障。
- 正例结束时真实RPC和传输确认均已drain。121条实际Action RX全部匹配原源capture的完整body；另6个Link HELLO/ACK不属于Action CDR。Hub总入口146、完整交付127，包含预定故障，不能称全业务零丢失。

### 已有事件给出的 wall 边界

下表以 Gateway 原CDR初次capture至实际目的端完整收件计时，含调度/服务等待，不是空口单向延迟。原中央client确实收到响应的断言已通过，但没有单独落盘其callback完成mono，不能把C网关收件时刻冒充原DDS client返回时刻。

| RPC | 请求发数 / 响应发数 | 初发→R请求收件 | 初发→C响应收件 |
|---|---:|---:|---:|
| tb1 SendGoal …14593 | 2 / 1 | 283.738ms | 318.785ms |
| tb1 GetResult …14594 | 1 / 1 | 15.337ms | 49.684ms |
| tb2 SendGoal …14595 | 1 / 1 | 15.934ms | 40.890ms |
| tb2 GetResult …14596 | 2 / 2 | 8.164ms | 1777.627ms（含真实长等待与断链） |
| tb3 SendGoal …14597 | 1 / 2 | 23.465ms | 46.677ms（首响应） |
| tb3 GetResult …14598 | 1 / 1 | 11.062ms | 75.950ms |
| tb3 Cancel …14599 | 1 / 1 | 11.336ms | 37.203ms |

例如tb1原client已接受才发后续GetResult，故其真实接受返回落在初发后约318–347ms之间；tb2真实GetResult返回在后续tb3 Goal发出前，保守近似边界1777–1806ms。其余不补造精确客户端时间。RPC前缀均为`214834264`。

## 永久失联：检测成立，所有权仍未知

03最后一个tb1 SendGoal RPC `21483426414600` 共3发（native135/139/143），均未完整到R；不是Nav2拒绝，也不是已接受Goal取消失败。初发约499.357ms后原readiness撤权先于1.0wall确认上限，首错为 `action_goal_authority_withdrawn_unconfirmed_tb1_rpc21483426414600`。原Future保持unknown，R没有接受第四Goal。

实际Gateway.fail停止所有可靠重送、后续业务收件全部discard；保存的真实旧包方法级回放只验证此边界，不冒充新无线交付。三LocalStop均锁存，原零Twist全0、三个真实PAUSE响应success且清理Future均done。这只是本地零运动清理接口证据，**不是实体物理停机认证**。

有意保留：C unresolved RPC1、UNCONFIRMED1、retired service inflight1，R unresolved0，executor shutdown `[false,true]`，`Gateway_clean_return=false`。资源销毁和真实END flush成立，三个此前已接纳UUID分别真实终态4/4/5；未知第四请求不被伪闭合。因此不能把外层exit0解释为生产运行无fault或停止所有权认证PASS。

## 交付结论

接受范围是三机器人零运动真实DDS/真实ns-3 WiFi的同RPC交付恢复、幂等、长等待和诚实未知失败边界。原响应完全丢失的无线恢复未被本次独立证明；feedback/status仍可能丢失。真实Nav2/运动/120sim闭环、全业务压力和网络安全未验证，旧B心跳发布→C捕获137.93ms缺口未修。原NET失败不变，NET01仍BLOCKED，不自动Gazebo或NET02。本轮停止，不新增试验或生产修改。

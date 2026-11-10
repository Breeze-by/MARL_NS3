# NET-01D 独立静态初审

日期：2026-11-10。范围：当前工作树的 Action、网关队列、ROS QoS、时钟控制与四臂因果边界。仅阅读源码和既有 followup05 证据；没有运行节点、网络模型、Gazebo、测试、训练或 Git，也没有修改生产文件。本稿不代表新四臂已经实现或通过运行验证。

## 当前代码可确认的事实

1. **旧 Gateway A 是 A1，不是 A0。** `net01/gateway.py:188–216,422–443` 的 A 模式保留 TopicWire、BoundMaskWire、真实 Action 服务、确认/重送和统一 receive；只把实际 Wi-Fi 后端换为本地 FIFO。完全不经研究网关的原 ROS A0 尚不能从现有 CLI 的 A/B/C 名称推出。
2. **没有发现必须先改的确定 Action 缺陷。** `action_wire.py:85–127` 每段最多五次原身份重送、独立确认预算；`:254–270,279–305` 保留原 RPC/CDR、请求去重、真实响应后才创建响应传输，重复响应不再次完成 Future。GetResult 的传输确认与正常长时间导航等待分离。`:231–247` 先检查过期，不让迟到确认消除既成故障。
3. **永久未知不是虚假成功，也不是单独足以认定的实现 Bug。** `action_wire.py:210–225` 在未确认目标权限撤回时锁存故障；`gateway.py:489–530` 保存真实 pending、退休服务、确认未决及 clean=false。永久分区不能凭空构造 Nav2 接受、取消或终态。followup05/03 实际保留 C pending1、unconfirmed1、退休 inflight1，正是这一边界。
4. **当前调度有回调数量界限，没有墙钟执行时长保证。** `gateway.py:51–93,342–391` 以实体数和交替四个 handler 调度；单个 handler 或其中 progress 不能被抢占。`hub_client.py:53–92` 一次最多 recv 1MiB，再处理当前完整 frame；不是持续 recv 到无限流量为空，但没有独立处理时长/帧数预算。`gateway.py:312–324` 的 journal 读到 EOF，没有固定文件大小快照或条数上限。
5. **上述结构还不能唯一解释历史137.93ms等待。** 既有 `net01/followup05/HEALTH_PATH_REVIEW.md` 没有首错区间的单段 handler/CPU 归因；累计最大值不能当该窗口的单回调耗时。应先将实际发布、capture、handler、pump、CPU/墙钟边界对齐，再修改已证实责任环，而非看到 while 就认定根因。
6. **QoS没有在当前适配里被悄悄统一改成低保障配置。** `topic_wire.py:21–45,49–51` 保留逐流 depth、durability，使用默认 reliable；`action_wire.py:56–60,145–156,206–208` 保留标准状态 QoS、反馈深度及真实端点兼容检查。它们不意味着无线 UDP 会自动继承 DDS 可靠性；Action 的应用确认层是另一个明确机制。
7. **B/C源码没有业务本地回退。** `gateway.py:194–202,243–263` 仅 A 使用本地队列；B/C 从 Hub 完整目的收件进入真实发布。`topic_wire.py:96–116` 发布的是目的 CDR，`:42–45` 的共享地图和任务记录也列为业务流。外部理想 `/clock` (`gateway.py:163–177`)、ModelStates→无线 Mobility (`:179–186`)、R本地停车/管理接口必须单列为控制或本地执行，不能称其过网，也不能误称策略真值旁路。
8. **同步信用不等同业务收件确认。** `time_control_state.py:63–94` 用真实 Native ACK 和后物理完成结果限制正常推进；`tools/packet_hub.py:188–213` 不允许 STEP 超前实际已观察时钟，返回源是 Native STEP。故障停机观察有专门权限；业务故障时继续完成受控本地停止观察，不代表网络已恢复。

## 四臂最小可解释条件

- A0应真实走原ROS直接业务；A1/B/C保持同一新确认层、CDR、QoS、端点、日志及冻结策略/导航/感知。不能把旧mode A作为A0再声称隔离了适配开销。
- 物理步进、名义实时率、起点、地图分母、任务预算和自主起算规则应共同固定；若A0确有无法避免的执行差别，明确列出，不能把差值全归网关。连接/握手与初扫时间单列，不事后换自主起点。
- A0→A1是适配路径的整体开销；A1→B还包含ns-3计算、IPC、信用同步与无线传输的共同影响，不是纯射频传播损失。B→C才在同一实现上考察预先固定的网络条件变化。
- C网络条件应在看到该臂探索表现前固定；不用更换有利地图/起点补失败。两个回合只能支持有限重复观察，不能宣称稳定统计优势或未知地图泛化。
- 所有提前中断和未达阈值均保留；T95未达不能记0或只取成功回合平均。任务期、停止期和收尾失败分开，局部网络/退出子结果不能覆盖整体故障。

## 初步意见

当前允许继续做针对真实故障的观测和具体四臂方案准备；未发现需要先重构 Action、替换时钟或放宽原期限的已证实理由。137.93ms首错归因、完整业务下新可靠层与真实物理停止仍须实际证据，不能由既有无运动夹具或本次静态审查直接签通过。

## 已落方案补审与最小无运动范围

已完整读新 `net01d/PLAN.md`、`FAULT_INVENTORY.md` 和初始账本。四臂定义及保留历史失败的原则与上述源事实相符。文档中的180sim强制目标和准备项的P0严重度标法已由主审指出、生产者正在修正：180sim是上限，统一事前120sim可复用原合同；身份沿用/目录待绑定本身不是P0缺陷。这里的P0准备阶段名称不应混同问题严重程度。

可以继续实现一个最小、具体的无运动A1/B入口，必要条件收敛为：

1. **源独立于网关循环。** 用独立进程通过真实DDS发布原业务。不能像followup05受控Action夹具一样，在网关pump中为guard直接构造fresh输入；否则源也随被测程序停住，无法辨认源→capture等待。
2. **使用实际完整业务和冻结时基。** 同一源脚本/配置供给A1/B；地图和costmap/mask采用实际合法大小的完整CDR，含运行中的89共享地图与95任务记录，以及真实Action客户端/受控服务端的Goal、反馈、状态、Result和Cancel。使用已有冻结源时基合同，不以历史捕获均值降rate；sim生成事件随真实clock，原wall广播重复scanheader可保留，不能误删成“暂停时不准重复旧戳”。公开configured ticks、实际供给及skips即可。
3. **守护检查真实目的收件。** health和bound由真实发布经过C编码及A1有序本地后端/B实际Wi-Fi，到R解码后进入原guard。保留原300ms及源龄规则；bootstrap和合成内容明确标注，不能直接注入本地guard或用目的接收时间重写源戳。
4. **复用已有协议和观测。** A1/B共用同一codec、确认/去重、QoS、ROS端点和日志；保留真实UUID和原CDR。优先沿已有dispatch/control trace，并关联源seq、真实receipt区间和首失败；不能把inclusive父子耗时相加、把发送返回当目的ACK，或只凭退出0认定满载成立。

这四点足够约束下一份具体入口，不要求另建调度框架或先做更多等价测试。实际脚本/参数尚待固定后小范围代码审查；本次只允许继续实现，不是ROS、native或Gazebo运行准入。四臂最终采用统一120sim工程范围时，180sim仍作为用户最高限制保留，不追改旧回合。

## 五处被动观测差异补审

已逐读 `bound_peer.py`、`topic_wire.py`、`gateway.py`、`hub_client.py`、`tools/packet_hub.py` 的本轮工作差异及 `net01d/health/trace.py`。默认不启用诊断时原业务路径保留；启用后也未改有效业务的publish→binding次序、原CDR、QoS、TTL或原guard的tick-before-update规则。R端仍只调用一次原receive_health，没有额外reason/tick。只有小health JSON的序号解析，没有再次序列化网格。新增观测保存在RAM，收尾才写盘。

- Gateway的profile分支新增 `from net01d.health.trace import HealthTrace`，而旧 `ros-python.sh:20` 未显式包含包根 `/mnt`。从绝对 `/mnt/net01/gateway.py` 启动时不能依赖工作目录自动可导入该兄弟包。新诊断入口须显式设置正确包根；这是诊断入口接线问题，不需改变旧默认业务或增加兼容层。
- `TopicWire.capture` 的entry→serialize_return区间也包括新增的sequence JSON解析；结果应按包含诊断开销的区间解释，不能称纯serialize时间。Peer raw publish、后续binding分别有返回边界，可避免继续把composite return混成纯DDS返回。
- HubClient全流累计byte offset仍对应原有序字节流；health队列项和kernel flush共享该身份。跨层关联还需使用实际flow/序号或明确的逐流ordinal与Hub nativeID，不能最近时间猜配。flush不是Hub或目的收件ACK。
- 新拟A1入口的16wall供给/30wall、独立Source/Peer/Gateway、无89/95/Goal/noarm，允许作为P1等待定位设计继续实现；它明确不是前节完整业务资格，不能据其正常结束签P5、真实停车或运动准入。

此补审没有执行导入、测试、节点或网络模型。具体runner源码尚待落定，届时只补入口及进程/负载接线检查。

随后已读新 `replay_roles.py`：它显式加入REPO根及net01根，解决上述包导入接线；Peer在91、复用原frozen-source-clock的Source在92、Gateway为独立进程，session一致，未见直接fresh注入、arm或Goal。小health解析后新增serialize_begin，已可单列原serialize区间；R intake也补了A1的native_id身份回退。没有发现阻止该roles用于首A1/P1无运动诊断的新问题。主host入口当时尚未落定，30wall、真实空业务Native和owned收尾仍由具体入口准入核对，不以roles源码替代实际运行证据。

## P5完整负载三个helper补审

已逐读 `health/full_load_payloads.py`、`full_load_source.py`、`full_load_client.py` 及其复用的ControlledServer与MergeMapNode相关实现，未执行脚本或重复模板提取/typed检查。

- payloads仅以SQLite mode=ro取六份完整Grid CDR模板；Source明确以静止合成odom/TF和旧格内容产生新fixture观察，仅更新声明的header/load时间，不称新SLAM或历史测量重放。
- 三Source分别在domain92运行真实ControlledServer；原guard的实际arm服务决定权限，未直喂health/bound。真实Goal执行时按100wall反馈，两个Goal实际释放成功、第三个由C发真实Cancel；不是Nav2或物理导航。
- C merge复用原MergeMapNode，仅从C已交付的三图生成共享地图，具备89的实际来源；C客户端真实请求/响应/终态写入明确fixture_origin和Policy_forward=false的journal，供原95导出路径，不称策略forward。
- quiet停止观察供给但不退出服务；C normal_done后继续spin且不新建Goal。未见helper内部必须先改的确定阻断。

完整host仍需明确三Source传共享supply-stop-file，尤其B radiooff期间不置该文件，让源持续供给、服务继续接收原本机Cancel/PAUSE/Result，待实际负例证据后才STOP。否则Source默认32wall自动止供会混淆无线切断原因。封存后应直接核C记录Goal_CDR与R accepted_Goal_CDR及原guard UUID，不能只从三终态推出Goal字段一致；source_ticks累计包括active前，应由实际emit行/active marker分段报告供给。这些是既有产物的核对条件，不要求新增框架或故障矩阵。最终host固定后再给具体入口意见。

### 固定502ba02完整host最后意见

已读该固定版本的完整 `run_replay.py`、`replay_roles.py` 及helper新增负例字段，未发现阻止首A1既定32normal/60hard运行的实际缺陷。

三Source实际均传共享SUPPLY_STOP，正常起点由C三facade实际ready、首Goal之前的marker记录。先等待真实4/4/5正常终态和全部原RPC/owned清零，再允许第四tb3目标；其R真实accepted、GetResult的C/Rpending各1、Cserviceinflight1且其他counts0后才允许注入负例。phase标记先于A1停止观察供给或B的原 `radio_fault(False)`；并未退出原服务制造未知。NEGATIVE_DONE检查原R GetResult终态5、三个PAUSE成功、全部本机Future完成、owned为空，中央未知允许保留。收尾先真实HOLD ACK再STOP/END，强杀/退出1均保留独立含义。

root在0次P5运行前发现并修正过RADIO_OFF误传True（实际为恢复），本固定版本已为False；不将此夹具准备错误追认为旧B故障原因。此次意见仅接受一个具体无运动入口，不签实际运行、真实物理停止或全部P5；待原件核Goal字段/UUID、真实arm、时效和故障路径。不追加运行或验证框架。

# NET-01 followup05 独立审查：可靠 Action 交付接入

日期：2026-11-10。主审负责准入和交叉核对，生产者负责实现与执行；另一只读Reviewer独立复核源码及实际原件。

**ACCEPT WITH CONDITIONS：接受本轮外部适配实现及受控ROS 2/ns-3 Wi-Fi集成证据；NET-01整体仍BLOCKED，不签Gazebo或物理停止通过。**

## 审查对象及通过标准

生产源码固定于`51c5ac75971091913ad9a77f78d8b22327093a73`，实际通过的03夹具固定于`90c2e4c44e4db999e5875817b4d83d9bb46a9b64`。本轮只改`net01/action_wire.py`、`net01/gateway.py`及新增本目录；冻结模型、701维编码、Frontier、目标选择、Nav2/SLAM/物理、V3无线参数均无改动。实际安装入口为Gateway的A/B/C共用`install_wires()`，不是只在测试脚本中启用的替代实现。

独立通过标准：同session/robot/flow/RPC/UUID及原CDR重送；远端服务调用不重复；传输确认不冒充导航接受或终态；长GetResult合法等待；真实客户端得到原响应；过期后不复活；永久断链明确故障并保未知；退出不把未确认清成零；实际业务经过原Wi-Fi设备，不能以内存队列代替网络。

本次为**应用层确认和有界重送**，借鉴可靠传输思想，不是TCP接入或完整论文复现。原Action请求/响应CDR保持，新增offset9两字节传输ACK明确另列。每个数据传输段确认窗口1墙钟秒、间隔.2秒、最多5发；没有放宽原健康、源龄或停止期限。

新增的故障行为也明确冻结在本候选中：未确认SendGoal尚在途时若中央ready权限撤回，立即锁存传输故障，禁止恢复权限后继续暗中提交旧目标。原R Guardian门控和已准入service的实际响应寿命保留；不能把这项新增传输保护描述为整个外部适配完全没有行为变化。

## 实际审查清单

- 两个生产文件全部差异：ACK状态、原身份缓存、请求/响应各自起算时机、原退休service寿命、故障及Gateway实际进度/持久化/退出接线。
- [事前计划及后续登记](PLAN.md)、定向check与真实Gateway/Wi-Fi夹具、外层所有权/超时runner。
- [零Node原件](evidence/reliable-state-01/)、[01原失败](evidence/reliable-wifi-01/)、[02原失败](evidence/reliable-wifi-02/)、[03完整记录](evidence/reliable-wifi-03/)。
- 03实际CDR、Gateway capture/本地guard记录、Hub ingress/delivery、native packet ledger/summary/PCAP与进程退出记录；没有重跑或改写原件。
- [健康路径只读审查](HEALTH_PATH_REVIEW.md)，包含原B的发布/捕获和独立clock witness边界；未将推测写成根因。

## 证据与独立判断

| 项目 | 实际证据 | 判断 |
|---|---|---|
| 定向状态逻辑 | 一次16项检查，退出0；原Future在永久耗尽负例仍未决 | PASS，0Node，不是网络证据 |
| 真正接入 | 03直接构造生产Gateway B、真实DDS Action客户端/受控服务端、原Hub/native及AP/三STA；有实际PHY/MAC/PCAP | PASS，受控无运动范围 |
| 丢失请求恢复 | 03首请求native19仅TX无RX；同RPC新native23实际RX，服务端只接受一次 | PASS |
| 三组目标与结果 | 三个原UUID及完整Goal字段保持；每组一次接受，结果4/4/5（两成功、一取消），真实中央客户端完成 | PASS，服务端为ControlledServer，非真实Nav2导航 |
| ACK丢失和去重 | 两个指定ACK在真实nativeRX后被夹具应用丢弃；同RPC重送/重ACK，GetResult不重复调用，中央Goal不重复完成 | PASS，ACK丢弃不冒称PHY丢包 |
| 长GetResult | 等待至少1.2墙钟秒，确认后不再重送请求，等待真实服务结果，无误判1秒传输失败 | PASS |
| 完整数据 | 03共127条实际RX，121条Action完整CDR与capture对应，另6条为Link握手 | PASS |
| 响应延迟与重复 | 原Result native98和重送102均在无线恢复后RX；重复被正确处理 | PASS限于延迟/重复；**未证明原响应永久丢失，更不能把恢复全部归于应用重送** |
| 永久断链 | 后续native135/139/143均未RX；约.499墙钟秒后原readiness撤权，三guard同理由锁存INVALID，故障后无新业务capture | PASS限于故障检测/禁止新业务 |
| 本机停止接口 | 三组真实零Twist收件、三个原LocalStop PAUSE实际响应success、本机清理future完成 | PASS受控接口；**物理停稳NOT VERIFIED** |
| 未知状态和退出 | C pending1/unconfirmed1、退休inflight1、executor shutdown=[false,true]、Gateway clean=false原样保留；END、资源销毁及ROS/Hub/native退出0，无强杀 | 预期负例成立，**不是所有权/停止认证闭合PASS** |

03总墙时7.299342309秒、20项夹具断言通过。退出0是测试脚本完成预期正负例，不能覆盖末段真实INVALID与未决状态。健康和bound输入明确为synthetic夹具状态，时钟也是合成ROS `/clock`；没有真实SLAM、地图、Nav2运动或Gazebo。

## 首失败与评审纠正

1. **01：P2夹具前检误判，已修。** 3.639秒退出FAIL，未创建受控服务端、未发送Goal。把全局服务名称列表当服务端存在证据，误将自身客户端的12个图名称列为冲突；主审和另一Reviewer初审也漏过。改用已有typed客户端与PAUSE客户端的真实可用性判据，保留外部驱动订阅检查，未改生产逻辑或放松安全目的。[Humble官方可用性实现](https://github.com/ros2/rmw_fastrtps/blob/humble/rmw_fastrtps_shared_cpp/src/rmw_service_server_is_available.cpp)明确检查匹配的请求/响应端点。
2. **02：P2夹具数据范围误判，已修。** 6.847秒退出FAIL。16正例成立、三目标结果4/4/5及健康阶段清理成立，但核对器用`flow>=200`误纳6个65534/65535 Link包；独立核对其余126条Action全部匹配。修为原Action范围`200<=flow<300`，未改数据或协议。该回合未执行永久断链，不能追认整个夹具PASS。
3. **解释纠正。** 断链恢复前未收到响应不等于原响应永久丢失。02与03都记录到原Result及重送副本，故报告必须使用“延迟/重复响应处理”，不能据测试名称外推。没有为制造丢失再运行第四次。

这些修正均事前登记下一次实际入口，01/02原失败不覆盖。实际共1次零Node检查、3次native/Wi-Fi夹具启动，新增Gazebo0、训练0，无第四次或网络参数扫描。

## 未闭合边界与下一步

- 原真实B健康消息至少137.930毫秒发布到捕获等待未修复；现有证据不能归因于共享clock解析，暂不迁入SHM或混改调度。
- 真实Nav2执行中断链、晚接受后的物理取消与停止，以及真实满地图业务下的健康期限，均未由本夹具验证。
- 永久分区时中央无法获得原任务的真实应答，本实现如实保留未知，尚未具备“故障后所有权全闭合”证明；不能凭本次测试通过准入自主Gazebo故障实验。
- 新确认层在A/B/C共用，后续性能对照须使用同一新适配版本；旧A10数字不能直接当新版本公平配对。

最小下一工作仍是启用现有逐阶段profile定位真实健康收件等待，再做有针对性的零运动全业务资格；共享时钟和迟到位置丢弃暂无足够证据直接替换。冻结RL保持不变，未自动运行Gazebo、NET-02或训练。

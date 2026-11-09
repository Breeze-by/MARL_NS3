# NET-01：真实 Wi-Fi 接口成立，Gazebo 联调被启动配置缺件阻断

**结论：OVERALL BLOCKED，不进入 NET-02。** 已实现并验证真实 ns-3.40 AP+3STA 全payload业务传输、双ROS域静态消息和受控Action接口。唯一获准的A参考因录包QoS配置漏带，在自主前失败；B/C未运行。不能据网络夹具、短启动direct流量或物理静止事实签真实网络探索闭环/网络停机安全通过。

本轮实际Gazebo **1/3**（累计83→84），0真实策略forward、0optimizer、0Nav2目标，无自动retry、训练、host网络改动、系统安装、实机、NET-02或push。原冻结发布/tag/模型/旧证据未改。所有首次失败保留，详见 [RUN_LEDGER.json](RUN_LEDGER.json)。

## 固定对象、实现和真实环境

- 冻结发布：`a014ef11d4b77fe45832268467993dfdeb4398f6`，tag `MR3-RL-POLICY-v1.1.0`；运行76fd，checkpoint SHA `6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d`，P0实际重核一致。六份历史Gazebo runtime/metric/closure与36份实际配置只作来源核对，不替代本轮A。
- 原DWB、关shim/peer_timing、Observer timing开启；701输入/原ROI/候选/联合mask/生命周期/SLAM fine .75/地图/共同三角/物理/原.4/.55sim及.3wall时效/停止阈值不改。
- 实际既有 Ubuntu22.04/Humble rootfs：FastRTPS，Nav2/DWB1.1.20、gzserver11.10.2；现有driver状态同步build和SLAM来源已核。原BASE安装merge是旧源，所以保留冻结launch显式worktree merge入口；没有由目录名推断实际源码。
- 新Git `net-01/workspace` / `net-01/integration`；仅新增外部transport、安全、接线和记录。实际A源 **`be01d8a7bb2e7546ee42586257f25f8b3885ca6f`**。最终静态补件源 **`5d5fcd571f51fa523fc68c5834c64b7768a39546`**，未重跑Gazebo；最终文档commit另见交付身份。
- 原ns-3.40树/库不改、不重配置；新C++仅在NET目录Release构建并链接既有库。实际ELF SHA `8aa7c7c88b5445b278bb34f15023c697f09785ec311dfa77cb3ef3de3b7aa1ff`；生成header SHA `66e64adf26c3d712ab149fe2d828ae8858d00c7172ef8adfacfc5bd7c2ff73a2`。host在真正启动前核对，见 [NATIVE_IDENTITY](config/NATIVE_IDENTITY.json)。

完整进程/时钟/白名单/启动清理argv见 [DEPLOYMENT.md](DEPLOYMENT.md)，逐流边界见 [TRAFFIC_MATRIX.md](TRAFFIC_MATRIX.md)，P0见 [原审计](../../evidence/P0_AUDIT.json)。无TAP/netns/route/特权操作。

## 真实网络与ROS前置结果

业务路径是原完整CDR→Unix IPC→ns3 UDP/IP→AP/STA WiFi MAC/PHY→实际SocketRecv/CopyData→重组→目标DDS。不是token经网后查源blob；网络进程失效不切direct。独立native wireID避免同RPC双向及三机器人同值碰撞，RPC身份也真实在网。完整mask约160KB按1164B正文分片，丢片整条不发布/不续stamp。

首包前锁定 [NETWORK_LOCK_V3](config/NETWORK_LOCK_V3.json)：802.11ac/5GHz/ch42/80MHz/1流，B=VhtMcs9、16dBm、LogDistance exponent2；C=VhtMcs3、2dBm、exponent3；Nist、noise7dB、原固定loss/CCA、retry7/4、MTU1500、seed2026110901/run1。1024p/500ms的每设备/AC队列及有线队列在首结果前由静态突发量确定；全部TOS0/BE，没有优先级优化。原100p初稿和V1/V2均保留。

| 验证 | 实际结果 | 严格作用域 |
|---|---|---|
| 独立真实WiFi03 | 44条输入；37条预期完整、2,255,248B逐byte一致；2104实际Rx片均与原PCAP正文对应 | 6条断链消息与1条故意丢片不出完整消息；合成horizon，无ROS/GZ |
| 静态双域ROS04 | 923条实际DDS消费、10,241,544B CDR；三mask×10Hz、4,803,120B/s的2sim原负载；原字段/捕获后在网bytes精确 | 实际FastRTPS+WiFi，原QoS/源戳；短PHY关闭无新consumer、恢复仅新消息；非真实GZ时钟 |
| Action接口02 | 17项真实DDS/generated接口通过 | 受控server+内存wire，不能叫WiFi或Nav2通过 |
| Action WiFi03 | 21项通过；三机各1真实accepted，2 SUCCEEDED/1 CANCELED；UUID、所有typed字段、feedback/status/GetResult/cancel闭合 | 真实WiFi+受控无运动server；黑洞期未知不伪回复，恢复重复RPC不重发目标；非Nav2/物理停机 |
| 同批mask绑定02 | 17项通过；原3mask→health顺序/数值保持，实际CDR与同批health源戳绑定，额外558B/份 | 无Node；本机绑定校验，不是实际断链安全认证 |
| 本地guard01 | 14项通过：迟到accept同UUID取消、foreign不cancel、真实零Twist/spy PAUSE，暂停clock下steady .30376wall锁存 | 真实DDS/受控Action和spy服务，未产生物理暂停效果 |
| 组合清理01 | 9项通过，真实永久unknown Empty回调5.60ms有界销毁，无伪响应/终态；END未送出独立失败 | 真实无控制DDS + 受控pause方法AST，不是真实pause/clock证据 |

独立03有1056次MAC retry和1176次PHY drop；不能称近理想零损。PCAP/逐片关系见 [PCAP_FRAGMENT_LINK](../../evidence/network-full-payload-03/PCAP_FRAGMENT_LINK.json)。MAC/PHY/UDP原ledger、RSSI/noise/SNR样本均保留；没有完整队列驻留/所有drop归因或正式GZ的端到端AoI统计，不伪造。

静态04总wall **8.131s**，并非2wall：source生成/字段oracle的19个批间隔中位.362s，native末UDP发送→horizon返回中位106.6ms/max114.5ms（含外部调度，不是纯CPU/无线时延）。因此不能据该夹具证明实时容量、真实RTF或.3wall健康。原source/header没有generation时记0和capture时间；ns3 Tx/Rx延迟、wall开销与GZ源龄分列，不跨时域相减。

TL/reliable只是本地DDS保证，UDP没有隐藏可靠性。首次冷ARP的静态源丢失原FAIL仍在；后续真实一次HELLO/ACK后才建业务订阅，由原TL缓存给新订阅的原消息仍完整过WiFi，不保证任意丢失静态源自动补齐。长SetOff原生故障后，无运动负例仅改为 [透明Range gate](config/CHANNEL_FAULT_V1.json)：正常在LogDistance后原功率原样返回，blackout为真实−1000dBm，无Python随机drop/参数扫描。

## 唯一A真实启动及首因

原件：[result](../runs/net01-a-corridor-6201-01/result.json)、[events](../runs/net01-a-corridor-6201-01/events.jsonl)、[bag.log](../runs/net01-a-corridor-6201-01/bag.log)、[host退出](../runs/net01-a-corridor-6201-01.host-exit.json)、[网络完整性](../runs/net01-a-corridor-6201-01.network-integrity.json)。

首个错误是 recorder argparse 找不到 `/mnt/workspace/rl02/bag-qos.yaml`，错误事件时间 **2026-11-09 01:44:39.582 UTC**，尚无observer sim。原runner同时检查launch/bag，却泛写 `Launch exited before readiness`；launch退出0发生后续收尾，不是首因。我的发布选材漏了原运行sidecar，P0也未覆盖该recorder路径。原76fd Git跟踪的698B文件与10原件一致，但发布 `PACKAGING_SELECTION.json` 将其明确列 `source_excluded`，原Manifest/repo无文件。不是模型、WiFi或Nav2首因。

按审查许可，仅在NET `config/recorder-qos.yaml` 保存固定76fd原文，外部Popen适配只替换bag QoS参数路径。一次无Node argv检查通过、其余原argv和输入不变，见 [静态补件证据](../../evidence/RECORDER_QOS_STATIC_REPAIR.json)。**这不是复测成功；冻结发布、A原件及已消耗READY不改。**

| 组/固定地图 | 实际进入 | T90/T95/T98与最终coverage | 三机路径/成功 | 结束与完整性 |
|---|---|---|---|---|
| A IDEAL-DIRECT-ADAPTER / Corr6201 | 真实gzserver+三机spawn/scan/map，未进入自主 | 全部**未测量**，非0、也非“180sim未达” | 启动/停机路径0.000546/0.000448/0.000376m；0/0/0目标，0NN | recorder启动失败；原native1，integrityfalse |
| B WIFI-BASE近理想 / 同图同spawn | **NOT RUN** | 未测量 | 未测量 | A前件失败，未准入 |
| C WIFI-BASE基础非理想 / 同图同spawn | **NOT RUN** | 未测量 | 未测量 | A前件失败，未准入 |

A实际scan计53/35/21，local map回调3/2/1，合并图已实收；不是“环境完全未起来”。direct短启动/收尾有4617完整消息、52,531,168B CDR，实际端点wall延迟中位.06873ms/max8.928738ms，不是零延迟或WiFi吞吐。C捕获319/接收3662，R捕获3662/接收319；bound和readiness消息另计。三guard从未arm、owned全空，没有真实SendGoal或网络故障下物理运动试验。

首实际clock固定anchor GZ.1→ns3 0；107条真实clock到GZ10.7、native到10.6，无gateway clock fault。**真实无目标pause preflight并未执行**，不足判TIME通过。具体取自原保存数据的 [A_STARTUP_SUMMARY](A_STARTUP_SUMMARY.json)，未新增bag解码/metric。

原 `observed_stop=true`@10.7，新零驱动/稳定窗口sim推进1.4、无hazard、最小中心距.749846m、0请求闭合；但Nav2尚unconfigured，Cancel服务未就绪、三PAUSE失败，`lifecycle_pause_healthy=false`，均保留。原物理静止不等于三暂停/网络停机安全PASS。boot/runner1，launch0，gateway0，hub/native0；Peer106行、318bound记录/Gateway均已保存，END完整送出、executors均正常退出。完整性仍false，不能用保存成功覆盖主回合失败。[精确owner退出核对](OWNED_EXIT.json)没有残留本case进程。

本次没有可用探索bag、覆盖曲线或自主轨迹，故不运行空metric/伪造0曲线；原启动/停止 `trajectories.csv`、drive CSV、首末地图/clock/事件全部保留，可查原目录。

## 失败不删除，阶段不混称

完整 [账本](RUN_LEDGER.json)列所有尝试。原生构建缺include、PhyRxDrop签名缺reason、静态Point类型工具错、921→860冷ARP损失、跨DDS未定义CDR padding oracle错、bwrap挂载缺口、无client hub timeout、长PHY-off的STA beacon watchdog原生fatal、bound padding oracle错、A recorder失败均保留。后续通过只在各自已声明接口修正范围内，不把首次FAIL追认为PASS。网内捕获→接收仍要求全部bytes exact；跨DDS serializer用ROSIDL float32规范化后全typed字段精确相等，不忽略字段或放宽容差。

| 验收项 | 结论 | 边界 |
|---|---|---|
| FROZEN_POLICY | PASS | P0来源/6d重核/六份历史来源；本轮0NN，非新性能通过 |
| NS3MODEL | PASS（独立范围） | 既有3.40真实B配置AP/3STA/有线/UDP/WiFi及PCAP；C配置锁定但未执行正式C |
| BIDIRECTIONAL | PASS（独立范围） | 三STA真实双向/并发/大payload/断恢复 |
| NOBYPASS | PASS（静态受控范围） | 双域ROS04/Action03关闭无线无新业务；实际部署完整组合未证 |
| ACTIONMSG | **BLOCKED**（受控接口子测PASS） | 真generated五端点/UUID/unknown/cancel/result子测成立；实际Nav2在网生命周期未到 |
| TIME | **BLOCKED** | 真实短启动anchor成立，pause/长时/正式WiFi clock关系未到 |
| NETWORKSAFETY | **BLOCKED** | 本地受控14项不等物理网络停机；A从未arm/无目标/三pausefalse |
| GZLOOP | **BLOCKED** | A STARTUP FAIL，B/C NOT RUN，无自主/闭环网络比较 |
| PERFORMANCE | **INSUFFICIENT** | 不能比较A/B/C覆盖/速度，不拿旧600代替A |
| OVERALL | **BLOCKED** | 保留A实际错误FAIL；不进入NET-02/实机或宣称研究完成 |

## 最低后续补测计划与交付

不在本轮剩余额度里把B改名成A，也不自动重试。后续应单独登记有界计划、根审核具体新入口：先确认外部静态补件的真实recorder路径和同源A参考，包括实际pause/clock/物理停稳；A健康完整后才原参数B/C。保留本次实际启动系统失败率，若再次失败就停止定位，不扩预算、不调整RL/地图/阈值或无线参数凑通过。当前只是补测计划，无执行许可。

本地源码diff/commit、native及重要交付身份随最终交付记录；原PCAP、native/hub/ROS/source-CDR/clock与失败日志保留NET目录，不复制旧原件/重扫旧历史。独立审查见 [independent-network-review](../../../reviews/NET-01/independent-network-review.md)，根主审另封。交付后停止，不自动下一阶段。

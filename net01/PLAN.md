# NET-01：固定策略的真实 Wi-Fi 业务路径

## 本批收束（2026-11-09，实际1/3）

OVERALL BLOCKED。唯一获准A已真实启动Gazebo但因发布选材漏带原bag-qos.yaml，在自主前失败，0NN/0goal；原observed_stoptrue但三pausefalse/完整性false，不能签网络停机。B/C未准入、未运行，不重试/移作A。仅NET外部补原76fd配置并做一次argv静态检查，未复测Gazebo。完整分级/全部失败账本见 [REPORT.md](REPORT.md) 和 [RUN_LEDGER.json](RUN_LEDGER.json)，实际A源be01d8a、最终未运行静态补件源5d5fcd5分开记录。当前停止，不进入NET-02；下方组合交审及初始提案保留。

## 当时组合交审（2026-11-09）

真实独立网络03、静态双域ROS04、WiFi受控Action03、同批mask无Node02、本地受控guard01分别在限定范围通过；所有首失败保留。已落两域外部组合/owned启动清理、固定真实clock anchor、每机独立守护和三份未签180sim草稿；见 [DEPLOYMENT.md](DEPLOYMENT.md)。8个组合Python模块compile、现有ns3库增量build通过，无新的网络/ROS组合运行；Gazebo0/3，TIME/NETWORKSAFETY/GZ仍未证，首A必须具体独审后执行。下列初始设计与早期失败为历史记录，当前配置以原首包前NETWORK_LOCK_V3及已审CHANNEL_FAULT_V1为准。

## 本次范围与当前事实

独立 Git：`net-01/workspace`，分支 `net-01/integration`，从发布 commit `a014ef11d4b77fe45832268467993dfdeb4398f6` 派生；冻结仓库、tag、模型和旧证据不改。固定运行76fd/6d、原DWB、shim/peer_timing关闭、Observer timing开启。P0详见 `../../evidence/P0_AUDIT.json`。仅做无机器人/控制的前置验证；当前0新Gazebo、0Node、0NN/训练、0宿主网络修改。

已实际读发布README/PROJECT/Manifest/行为合同/SETUP/独审，重核6d模型完整SHA一致。六份发布runtime/metric/closure均与原10原件逐字节相同；36份实际Nav2/SLAM YAML均与原运行配置相同。六例均600sim、原stop/3pause/UUID完整，不能替代新网络断链安全或新180sim A组。

原rootfs的rclpy/nav_msgs/nav2_msgs/tf2_ros在只读bwrap中实际import成功（不init/建Node），实际RMW=rmw_fastrtps_cpp；driver/SLAM/gzserver动态依赖可解析，driver实际build与已验证SHA相同、编译STATE_SYNC=1。BASE安装merge是旧源，必须保持原scene的显式worktree新merge入口，不能直接用其egg-link。宿主无/opt/ros setup；历史wrapper的相对路径不能原样套新发布布局。未新启动Gazebo，不签其已恢复运行。

现ns-3 VERSION=3.40，WiFi/IP/Fd/Tap/core库已有；无Git历史，bindings关闭。lock的ENABLE_REAL_TIME=False不是组件缺失：core实际包含并导出Realtime/WallClock符号。uid1000无effective capabilities，/dev/net/tun可读写不代表可建TAP；本计划不执行sudo、TAP、route或系统包安装。官方本地tap.rst/例程已读，STA UseLocal单host-MAC边界不忽略。

## 最小结构：两个ROS域 + 非特权全payload transport

1. **R域（暂定92）**：一个Gazebo，三机原sensor/odom/TF/SLAM/Nav2、机器人侧typed endpoints与本地安全层；机器人内部导航/雷达不绕到中央。没有证据需要拆成五域。
2. **C域（暂定91）**：冻结HQ/候选/模型、原merge、原peer producer；只消费实际送达C域的R业务副本。原节点参数/算法保持；外部launch和RMW配置绑定真实domain/loopback，禁跨域DDS转发或SHM补数据。域号执行前确认无占用。
3. **唯一业务出口**：R/C端捕获原ROS序列化CDR的完整bytes，经本轮owner Unix IPC交给ns-3节点的UDP Socket；真实IP/WifiNetDevice/MAC/PHY接收回调CopyData出的全部bytes，才可返回目标端IPC、重组、反序列化并publish/respond。严禁token过网再从源缓存/共享文件/localhost恢复大图。
4. **AP与三STA**：中央节点通过模拟有线链连AP，每机器人namespace固定映射自己的STA。上/下行同路径，原始地图约45–55KB，peer mask每份160KB×3×10Hz约4.8MB/s，必须完整过网。固定1200B应用分片（包含业务头后满足1500MTU）、msgID/offset/total；丢片不publish残图，不刷新stamp，无隐式重传/恢复。整消息超时/旧epoch丢弃可审、计账，不能补旧缓存冒新。
5. **运行日志不是旁路**：原Observer增量读C端allocation-events的controller_end属于运行期halt/budget业务输入，必须经WiFi交付后写R端本地接收副本，再复用原增量读取；不能共享挂载C活跃journal供R读取。停止后可离线汇集原journal核UUID闭合，离线证据不得回填主期状态。仅独立安全停止信号可走白名单控制通道；C/R数据目录分挂，冻结源码可共享只读。
6. **控制/真值隔离**：只有/clock、实验停止和GT→网络mobility可走独立白名单控制IPC；GT/独立安全评价不能进入policy或业务补包。原地图/pose/goal/feedback/health不能借控制通道回传。

## Action与网络安全：前置阻断项

C端透明呈现原generated SendGoal/GetResult/CancelGoal三service及feedback/status两topic；R端将原request逐字段交真实Nav2，返回真实accepted/stamp、UUID、result/status/cancel列表。保留原LoggedActionClient生成/先journal记录的UUID，不新建第二目标ID，不将代理接收当accepted。RPC-ID/epoch去重，重复包不能再执行goal；迟到accept按原取消/终态语义处理。C端service存在/Action wait_for_server必须由经网实际发现的远端Nav2五端点ready驱动，不能提供永久ready的空façade。断链时不伪响应/默认闭合，所有未知在途请求须真实查证，未闭合禁止自主。

R域三STA的mask/health各自需独立交付证据，不能三份health重复publish到公共topic刷新单一Observer heartbeat掩盖某一链路断开。建议公共Observer health只使用明确单一路径，其余每机链路由独立本地watchdog检查自己的实际接收；具体入口/联锁须先审且在A/B/C相同。新health不证明旧mask已交付，mask/health分别source/receipt和epoch关联。原mask与health发布顺序/原字段均不改。

原.4sim odom/.55sim correction/.3wall heartbeat不放宽。新增本地断链安全只做停机/权限撤销，不做新目标或正常期速度控制；真实cancel→UUID终态→零命令→Nav2暂停/原物理停稳须在无运动Action隔离和本地状态测试中证明。只有中央监督者停机、不证明本地失联停机还不充分；尚无可信网络断链安全。不能做运动中主动断网试验来绕过这项前置。

## 时钟：首要可证伪设计，不假定Realtime等于Gazebo时间

原600sim需要约660–690wall，直接Realtime=wall会与/clock累积偏离。当前优先**待审**：用真实/clock单调tick驱动原生ns-3离散事件队列，网络事件时间与Gazebo同域，IP/WiFi各事件仍真实运行，不用sleep/drop模拟。原生DefaultSimulatorImpl支持Stop(delay)/Run继续同一事件队列；正常不改变Gazebo physics或策略时钟。未做该机制测试，不声称时间PASS。

每条记录保留Gazebo source/clock、ns3 Now、入/出网和consumer monotonic；网络延迟使用同一ns3时域，wall开销单列。固定提案为：每收到真实10Hz /clock，只将ns3 Run推进至该tick（无未来预跑），horizon≤.1sim；Gazebo与ns3已观测clock差超过.12sim立即停止，边界1e-6仅浮点量化，root审后才运行。入网注入时间=max(ns3当前时间、该入口已收到的Gazebo clock)，绝不按旧source stamp倒退插入。超限中止而不是推迟原peer guard；/clock若跃退视为新epoch失败停机。Pause时网络时域冻结、wall仍记录，禁止旧epoch重发；恢复不改stamp，已过期旧消息仍拒绝。wall heartbeat在pause时仍可触发原安全停止；受控无运动pause验证不冒称自主pause可无限续跑。若这条有限实现/证据不成立，TIME=BLOCKED，不转成伪wall同步硬凑Gazebo。

## 固定试验/预算（全部前置通过后才具体READY）

最多Corr6201 **A direct→B近理想真实WiFi→C基础非理想真实WiFi**各1次、每≤180sim、总3，无重试；当前0/3，尚无任何GZ准入。相同发布模型/ROI/共同三角/yaw0/分母按Corr原15558格38.895m²、SLAM.75/物理/导航/生命周期/停止/新安全层，决策保持5sim、上限不扩大原130。初稿独立wall：startup180/autonomy420/outer900/cleanup90；全部执行前锁定不跑后延长。旧600结果只历史参考，不代替新A。

候选网络初稿（结果前审定固定，不先运行）：802.11ac、5GHz/channel42/80MHz、单流；AP(0,0,1.5)，STA xy由唯一GT mobility控制更新、z=.15；中央有线1Gbps/1us；IP10.31.0.0/24，中央有线子网10.32.0.0/24，静态route、UDP、MTU1500；RNGseed2026110901/run1，FIFO queue100packets/500ms，MAC retry原库显式取值后记录。B固定VhtMcs9/Tx16dBm/LogDistance exponent2；C固定VhtMcs3/Tx2dBm/exponent3，无随机应用drop/优化/优先队列；ARP/association开销计入。当前只是提案，须P0/架构审后才写最小应用并在任何业务结果前最终锁定。

普通Nav失败/低覆盖保留健康固定对照，不据成绩删例。旁路/Action未知/时钟/保存/真实fatal或安全异常立即停止余例交root审；不自动retry/更换地图或进入NET02。

## 门禁与交付

| 门禁 | 必要实证/当前状态 |
|---|---|
| P0 冻结与环境 | 完成只读身份/配置/源码所有者审计；完整GZ恢复仍未验证 |
| P1 真实ns3模型 | 待构建；AP+3STA完整真实payload、pcap与MAC/PHY trace，不能只有吞吐/ping |
| P2 无旁路/Action | 待实现；3STA双向独立/并发/多size及阻断恢复，内容seq匹配，丢片不出ROS；generated RPC全部字段/UUID/accept/result/cancel等价 |
| P3 时间 | 待审机制/未测试；clock无增长漂移、源戳不变、pause/resume边界和自动停止 |
| P4 ledger | 全flow/robot/type/bytes/seq/source/入网/TxRx/出网/consumer/ActionID；区分MAC retry/drop、QoS、app过期、任务timeout/无新源 |
| P5 无运动验证 | 独立网络真包与真实静态ROS业务分别标记；Mock仅机制不得冒充ROS PASS |
| P6 网络安全 | BLOCKED待实证；旧六例停机不是断链停机，Action未知或本地联锁未证不得自主 |
| P7 三组Gazebo | NOT RUN；前件全部审过才3单具体READY，180sim不能延长凑95 |
| P8 研究边界 | 本轮不优化网络、不训模型、不NET02；仅报告瓶颈与后续独立建议 |

最终分列FROZEN_POLICY / NS3MODEL / BIDIRECTIONAL / NOBYPASS / TIME / ACTIONMSG / NETWORKSAFETY / GZLOOP / PERFORMANCE。不因CPU回放、ROS Mock或历史stop写OVERALL PASS。保存实际build/argv/config、pcap/packetledger/clocks、实际GZ曲线/轨迹和失败/预算/独立Git diff与提交；只清本轮owned隔离资源，无push。

## 2026-11-09当前前置执行（不替代原提案/首失败）

- 独立网络03真实全payload PASS，03 PCAP每个udp_rx片的完整header/内容均对应，无新网络重复运行；前01编译缺include/02 trace接口失败保留。03源固定本地88e84a2。
- 首包前锁 `config/NETWORK_LOCK_V3.json`：原100p初稿不足已静态改1024p/500ms，80211ac必要QoS=true且所有业务TOS0/BE，有线同1024p；V1/V2原提案保留，无跑后调网。
- 静态DDS01字段int/float工具错保留；02真实921入网/860完整native且860真实DDS消费，61初期丢失含初始TF/filterinfo，FAIL。后wireid70..921全交付。只收3片的大消息与默认ARP PendingQueueSize3相容，缺直接ARP Drop hook，不夸唯一归因；UDP端到端TL/reliable未证，未自动暖cache重跑。
- Action接口02真实FastRTPS/generated17检查PASS（controlled无运动server+内存wire，仅接口）；尚非ns3/真实Nav2/网络安全PASS。
- 正式Gazebo0/3，TIME/NETWORKSAFETY/GZLOOP尚阻断；无训练/NET02/远推。

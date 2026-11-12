# CORNET当前旗舰仓库补充评估

审查日期：2026-11-10。用户补充入口：[rbccps-iisc/CORNET](https://github.com/rbccps-iisc/CORNET)。固定读取提交：`81f0234b894977e9756b95303459cc64765bbc19`，2026-09-28。对照本项目`24ed61500985f55a99b6ed4f406641771c8a1e61`的实际实现与封存证据。

**结论：这个仓库比上一轮读到的CORNET 2.0更接近本项目，值得升级为候选适配框架；目前仍不建议直接替换生产系统。** 它有实质的现代Python实现、Humble/Classic入口和真正的ns-3 Wi-Fi代码，不能再用“只有Mininet-WiFi”评价它。但它的clock、调度器和真实业务之间仍有接线缺口，不能据README认定其同步已优于我们的Step/actual-ACK方式。

本次由主审及三条并行只读审查线核关键源码、文档、测试定义和既有结果；未运行第三方软件、测试、安装器、Gazebo、ns-3或网络配置。静态发现不冒充实际运行失败，已有仓库结果也不冒充本机复现。

## 1. 身份更正：当前旗舰不等于2020原版或2.0

仓库自己的[LINEAGE](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/docs/LINEAGE.md)列出四条线：1.0在`srikrishna3118/CORNET`、2.0在`rbccps-iisc/CORNET2.0`、3.0是另一个论文/实验归档，而用户新链接是当前Flagship重构。

上一份[五篇文献报告](REVIEW.md)对本地CORNET 2.0 PDF的版本、Mininet-WiFi和单向同步判断仍只适用于那份PDF。**不能将其旧源码缺项或Mininet限制直接套到当前旗舰。** 本补充评估将它作为软件来源S1，非新增一篇已读论文，也不认为旧论文的实验结论已自动验证本仓库。

## 2. 比旧材料更好的实际部分

| 可复核实现 | 实际价值 | 对当前项目的意义 |
|---|---|---|
| Python包、统一配置、插件configure/start/run/stop/collect、任务目录 | 比散落的研究原型更易组织环境和实验 | 可以复用组织方式，减少手工拼启动参数；不需要接管RL算法 |
| Humble/Classic11 robot插件，支持用户提供launch_file | 能把原机器人栈作为外部launch入口 | 有机会保留现有三Waffle、SLAM、Nav2，而非重建机器人 |
| ns-3 Wi-Fi C++场景 | 真实Yans、802.11ax、AP/STA、UDP应用及可选TapBridge | **确有ns-3 Wi-Fi，不是只有Mininet，也不是全Mock** |
| 明确的ns-3/NR环境通道、能力等级与已有性能日志 | 比“有上游组件即算已验证”更可审计 | 可借鉴版本与证据分级，但本机ns-3.40不在现成通道内 |
| ClockServer、PositionServer、Dispatcher、AoI工具 | 有可阅读、可单测的具体组件 | 可作为独立候选，不代表这些组件已接入真实机器人业务 |

依据：[架构](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/docs/ARCHITECTURE.md)、[Gazebo插件](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/robot/gazebo_plugin.py#L73)、[Wi-Fi场景](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/v5.1-ns3.48/wifi_basic-default.cc#L241)、[能力表](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/patches/ns3/CAPABILITY_MATRIX.yaml)。

## 3. 它现在的时间方法，与我们的不同在哪里

### 3.1 有真实clock输入，但不是实际网络完成ACK

`ros2_bridge.py:63–90`订阅ROS `/clock`，通过Unix socket发送物理时间；`ClockServer`接收后更新Python内的`physics_time`。`ns3_plugin.py:187–196`用它更新Dispatcher和AoI。

但所审Wi-Fi C++仍启用普通`RealtimeSimulatorImpl`并自由运行；没有看到该physics_time进入ns-3调度器的时间授权，也没有看到网络实际完成horizon后才允许Gazebo继续Step的接线。当前路径是“物理clock用于Python侧释放/统计”，不是本项目“真实native完成ACK约束下一物理步”。

这不排斥异步方法在合适负载下效率更高，但**不存在现成证据证明它能约束我们之前的慢网络事件执行**。低开销、较少握手是潜在优势，因果领先边界和墙钟期限仍需实测。

固定源码：[ROS bridge](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/bridges/ros2_bridge.py#L63)、[clock回调](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L187)、[Wi-Fi实时调度](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/v5.1-ns3.48/wifi_basic-default.cc#L213)。

### 3.2 Dispatcher是实质helper，但未接成真实业务链

`dispatcher.py`确有按physics_time排序的堆、RTF等待、入队时deadline判断和BER模拟。不能因为这些方法有测试，就说它们已经约束了真实Wi-Fi包。

本次在`cornet`生产包内没有找到真实业务调用`dispatcher.enqueue()`的路径；`Ns3Plugin._on_packet_dispatch()`只记录AoI，没有将payload写入TUN FD。指南中的“forward to TUN”是用途示例。另一方面，C++的TapBridge可以是另一条原生数据路径；**未接Dispatcher不等于完全没有网络代码**，但不能把helper的deadline/BER效果算到该路径上。

依据：[Dispatcher](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/middleware/dispatcher.py#L107)、[dispatch回调](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L194)、[指南](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/docs/guides/middleware.md)。

### 3.3 墙钟fallback不能用于我们的正式同步证据

`clock.py:118–125`在没有客户端时，同步进入`_wallclock_fallback()`；174–188循环直到stop，没有重回accept来等待真实clock客户端。因此，“以后真实客户端接入会接管”的注释与该路径实现不一致。这是静态可证控制流问题，未在本次执行复现。

即使修复接管，正式Gazebo实验也不能在缺真实clock时悄悄用单调墙钟充作physics_time。我们的仿真可能暂停、RTF约0.5；fallback继续1倍墙钟推进会改变时间语义。此模式可用于明确标记的无物理侧演示，不应用于证明联合同步通过。

依据：[ClockServer接收及fallback](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/middleware/clock.py#L114)。

## 4. 复现真实Wi-Fi业务前，有两个具体接口阻断

### 4.1 TUN和TAP不是同一种接口

`TunManager._create_tun()`使用`IFF_TUN | IFF_NO_PI`创建三层IP接口；两版`wifi_basic-default.cc:267–272`却用二层`TapBridgeHelper/UseLocal`打开同名设备。标准ns-3 TapCreator使用`IFF_TAP`。接口名称一致不代表接口类型/帧格式一致；TUN/TAP、FD所有权和实际收发路径必须统一后才能认定自动业务桥接可用。

这是源码接线不一致，不是本次观察到的某个实机运行报错。也不能简单把本地helper回调成功等同于MAC/PHY业务通过。

依据：[TunManager:157–175](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/middleware/tun.py#L157)、[Wi-Fi TapBridge:267–272](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/v5.1-ns3.48/wifi_basic-default.cc#L267)、[官方ns-3.40 TapCreator](https://github.com/nsnam/ns-3-dev-git/blob/ns-3.40/src/tap-bridge/model/tap-creator.cc#L305)。

### 4.2 Plugin传参和Wi-Fi程序解析不一致

Plugin默认加`--rngRun`；开启middleware还加`--tunN`、`--sensorPort`、`--controlPort`。两版Wi-Fi程序先执行标准`CommandLine::Parse`，只登记layout、positions、timing、AoI、tgax、simTime、realtime，之后才调用`ParseCornetArgs`扫描自定义参数。后置扫描不能补救前一次未登记参数的解析问题。

应先统一命令行合同，再谈自动复现；本次未实际启动，所以不伪造启动日志或将静态发现写成已跑失败。

依据：[Plugin默认seed参数](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L29)、[middleware参数](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L399)、[Wi-Fi解析](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/v5.1-ns3.48/wifi_basic-default.cc#L147)、[ParseCornetArgs](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/cornet_base.h#L38)。

## 5. 对我们两个现故障及位置时序的作用

| 项目 | 当前旗舰实际提供了什么 | 是否已经解决本项目问题 |
|---|---|---|
| 两笔SendGoal发出后未完整交付，C无限等待 | 可选原生网络桥接框架；没有所需的Nav2 Action/UUID业务实现 | **没有。** 原生DDS/TAP修通后可保留原协议可靠性，具有替代手写RPC的潜力；目前没有该真实闭环证据 |
| Peer发布到C捕获137.930ms等待 | 独立clock/position线程；ROS2 bridge仍同步sendall | **没有对应尾延迟保证。** 更换框架不使原reader更早take，需测实际等待段 |
| 网络节点位置的时间身份 | xyz及按墙钟间隔估计的速度，Wi-Fi每100mssim轮询更新 | 未提供独立源仿真戳及按该戳生效的合同，不能认为补足了我们POSITION的时间缺口 |
| 共同坐标下的位姿 | 默认bridge把每条TF局部translation直接按child名转发 | 多级TF需要真实坐标链组合与机器人身份映射；不能把轮子/局部frame当无线节点全局位置 |
| 无直接DDS旁路 | TUN地址/策略路由，Mininet有另一端点路线 | 当前所审TUN路径未证明隔离Linux local路由或DDS其他通道；这是待验证风险，不是本次已观察到旁路 |
| 原安全停止和未知所有权闭合 | 插件负责信号终止/收资源 | 没有原零速消费、物理停稳、UUID终态证书；进程退出不等于机器人停机通过 |

依据：[ROS TF转发:100–107](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/bridges/ros2_bridge.py#L100)、[位置速度转发:228–245](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L228)、[Wi-Fi位置应用:110–130](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/scripts/ns3/scratch/v5.1-ns3.48/wifi_basic-default.cc#L110)、[地址与路由](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/middleware/tun.py#L83)、[Gazebo停进程](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/robot/gazebo_plugin.py#L152)。

## 6. 现有测试与benchmark能证明到哪一层

不能把它一概称为Mock，也不能把测试文件名当作真实业务闭环。

| 证据 | 本次只读确认的范围 | 不支持的外推 |
|---|---|---|
| test_ns3_plugin | Fake组件/Fake Popen检查配置和生命周期 | 真实ns-3收发、ROS业务或同步已通过 |
| test_middleware | Dispatcher小数据测试；TUN的ioctl/ip被mock | 真实TUN/TAP与宿主路由已经接通 |
| scenario smoke/integration | 部分测试检查Python参数，所指场景模板仅argparse | 不能据integration命名认定真实NR或机器人闭环 |
| bench_results/20260927-015715 | 真实ns-3/Gazebo启动与CPU/RTF/lag负载基准；72条记录中12条combined的6条TAP变体均skipped，6条no-TAP有数据 | 不是Wi-Fi三机SLAM/RL/Nav2业务验收；缺TAP不应被统计平均掩盖 |
| wifi_basic默认流 | ns-3内部64字节UDP/10ms流及Wi-Fi设备 | 不是机器人产生的地图、状态和真实Goal字节 |

仓库现成summary自己注明`ns3-limited (no-TAP)`。这些真实负载结果有助于估计瓶颈，不等于时间/业务路径通过。本次没有重新运行上述测试或benchmark，也没有把NR结果拿来证明Wi-Fi行为。

来源：[plugin测试](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/tests/test_ns3_plugin.py#L154)、[middleware测试](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/tests/test_middleware.py#L86)、[场景测试](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/tests/test_scenario_integration.py#L54)、[模板](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/scenarios/5g_nr_urllc/run.py#L32)、[既有summary](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/bench_results/20260927-015715/summary.md)。

## 7. 迁移成本：能作为候选，但不是直接换启动命令

- **版本**：源码提供ns-3.38/NR2.4、3.47/4.2、3.48/5.1通道；没有ns-3.40验证通道。无marker时默认选3.38 scratch，不能因此自动兼容我们3.40，也不能断言普通Wi-Fi API完全不可移植。
- **无线实验条件**：新Wi-Fi例为802.11ax、20MHz、IdealWifiManager；我们固定V3为802.11ac、80MHz、ConstantRate。直接换例程会同时改变网络实验，不是仅替换时间方法。若做适配，需保留原拓扑和无线配置，另设可比候选。
- **机器人**：custom launch可利用；generic launch只做模型/RSP等基础启动，不含三机Nav2/SLAM。`uav_wifi_control`任务实际选Mininet且引用任务内未提供的`models/uav.sdf`，不能当作现成的ns-3三Waffle示例。
- **权限/资源**：真实TUN/TAP需CAP_NET_ADMIN；默认接口名和路由表会修改执行namespace的网络资源。installer还涉及系统安装及tap-creator权限。若复现，应在独立环境，不直接运行在当前已验证ns-3.40树或宿主网络上。
- **退出**：resource stop有实现，但不等于本项目全部子进程确认、真实Nav2停止及UUID闭合；原安全层必须保留。

依据：[INSTALL](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/docs/INSTALL.md#L53)、[lane选择](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/plugins/network/ns3_plugin.py#L74)、[generic launch](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/cornet/gazebo/generic_launch.py#L37)、[UAV示例](https://github.com/rbccps-iisc/CORNET/blob/81f0234b894977e9756b95303459cc64765bbc19/tasks/uav_wifi_control/config.yaml)。

## 8. 更新后的选择意见

1. **新版CORNET进入值得验证的候选名单。** 它比旧2.0及残缺的关联研究原型更接近当前环境，有实质Wi-Fi后端与工程化工具；不能一笔否定。
2. **同步器暂不整体替换。** 当前没有证明physics clock真正控制了所审ns-3调度，更没有actual-completion ACK对物理侧的限制；先接通和验证，再谈更低开销或更好精度。
3. **优先评估“原生DDS/TAP数据面＋保留现有同步/安全”这条局部路线。** 它可能减少每种Action手写代理和可靠性语义损失，但须先解决CLI、TUN/TAP、DDS隔离与真实双向业务，不把TCP ACK当Nav2接受。
4. **不用整个框架迁移来掩盖两个现故障。** 两笔Goal未知和137.930ms等待仍应独立修复/定位；即使选择CORNET组件，也要证明原目标、反馈与源龄合同保持。
5. **复现分层结论**：源码/依赖说明可得，工程复现条件优于旧材料；但真实自动Wi-Fi桥接及三机任务闭环尚未在本机执行，静态接线问题先处理。不能签“可直接复现PASS”或“换它必然更好”。

下一最小验证若获另行开展，应先零运动：统一参数接口、明确TAP/FD和namespace、发送真实有身份业务、断链负例、可变RTF/暂停/迟到clock，以及保留原UUID的接受/结果/取消闭合；不安装NR来替代当前Wi-Fi，不改变冻结RL或新增Gazebo回合。本轮只交付评估与Git文档更新，NET-01仍BLOCKED。

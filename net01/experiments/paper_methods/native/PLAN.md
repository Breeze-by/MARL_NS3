# Paper-method native trials：事前固定计划

状态：root source reviewed / admitted for isolated build; each actual model start still requires root admission。仅新独立C++应用与结果，不修改生产native82bc、旧ns3源码/库/构建或旧证据；0ROS Node/Gazebo/Nav2/Goal/训练/宿主网络/TAP。研究问题是可靠字节交付及位置事件因果，不签NET01修复或真实Action安全PASS。最多4个实际native starts，每个8sim、外层30wall硬界（含保存），不重跑替换失败；编译已获源码准入，等待clock测量窗口结束通知后执行；各模型启动仍逐例待主审。无参数扫描。

## 共同模型与构建依据

沿用NETWORK_LOCK_V3 profile B：AP0+STA1/2/3+1Gbps/1us CSMA中央4；AP/三STA/中央初始坐标同旧header；802.11ac channel42/80MHz/5GHz、VhtMcs9、control/nonunicast6Mbps、16dBm、Nist、noise7dB、LogDistance exponent2/reference1m46.78453768787386dB、原RX/CCA/retry/RTS/MTU1500/AC_BE/QoS、队列1024/500ms。无线位置对中仅STA1按固定事件改变。所有业务TOS0，无优先级。seed2026110901/run1；WiFi AssignStreams固定起点，协议自身耗用/帧数不同不声称随机事件逐点相同。

只链接已存在Release-portable ns3.40：
- NS3_BUILD_DIR=/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03/build
- include与所有lib均该根；库名libns3.40-{wifi,internet,csma,mobility,propagation,spectrum,antenna,energy,network,core,traffic-control,bridge}.so，空后缀。
- 独立源net01/experiments/paper_methods/native/CMakeLists.txt与paper_methods.cc；独立输出/home/zhuyulab/ns3-workspace/net-01/build/paper-method-trials，Release/j2，不配置或改依赖树；保留configure/build原stdout/err/exit，首次接口失败不删。
- 参考现生产CMake与payload_transport.cc的拓扑/PHY装配；不是运行/重编生产82bc。独立程序只在ns3事件队列内运行，不用RealtimeSimulator来fake物理时间。sim时间、monotonic wall与threadCPU分别记录。

## 配对R：一次UDP versus真实ns3 TCP可靠传输（starts1/2）

共同中央4→STA1，固定105B synthetic高层请求，ID与其确定性opaque body绑定；reply返回接收后得到的完整105B原内容。无源blob旁路。4byte length framing对TCP/UDP相同：109B应用wire帧；记录payload=105和framing=4分账。UDP一次发，无应用重送；TCP使用真正ns3::TcpSocketFactory，数据/ACK/重传全部走同WiFi，绝不用host TCP。

启动前固定TCP类型ns3::TcpNewReno，其余TCP参数用当前ns3.40默认并从对象记录真实值（特别MinRto/ConnTimeout/SegmentSize），不根据恢复结果改RTO。0.8sim发起TCP连接；UDP同0.8sim建立本地socket；1.4sim检查TCP连接已实际完成，否则本case FAIL不移动发送时刻/假设连接成功。AP关联与正常收件由真实MAC/socket记录确认。

请求计划（sim秒）：ID101@1.5；ID102@2.1；ID103@2.3；ID104@4.5；与首请求逐byte相同的重复ID101@5.0。同样的有限接收端cache：第一次真实收件才执行逻辑处理并生成响应；同ID/body重复只送缓存真实响应，不再执行。不同body冒同ID为FAIL，绝不覆盖。

真实物理信道blackout [2.0,3.0)sim：沿原LogDistance后透明Range gate正常MaxRange1e9，期间0（不同AP/STA节点真实PHY收到-1000dBm）；不SetOff、不Python drop/sleep。记录PHY/MAC实际drop/retry和TCP序列号重发，不在应用层藏补包。8sim结束，逐个ID报告sent/admitted/whole received/reply和时刻；UDP预期两off-window请求无回复，TCP是否恢复以实测为准，不能因没恢复改参数或重试。

主要判据：105B接收原样、app reply真实往返、每ID最多一次逻辑处理、两故障窗请求的完整交付/回复、实际TCP seq重传与空口包证据。UDP预期损失是对照事实，不当工具失败；TCP未恢复/内容错/重复执行为本实验否定结果。该合成handler不是真Nav2，TCP字节ACK不是Action accepted或UUID ownership closure。

## 配对M：即时位置 versus源sim时间Schedule（starts3/4）

共同UDP probe中央4→STA1，128B deterministic body、递增probeID，1.2–5.8sim每50ms一次；不设blackout，位置之外全部同配置。固定源事件表：

| ID | 到达/捕获sim | 原source sim | STA1目标位置m |
|---|---:|---:|---|
| M1 |1.990|2.000|(.727,-.15,.15)：初x+.002|
| M2 |2.990|3.000|(.927,-.15,.15)：初x+.202|
| M3 |3.500|3.200|(.967,-.15,.15)：初x+.242|

immediate对照到达即SetPosition（包括future/late），明确它故意不满足source因果；scheduled候选仅未来/当前事件Schedule(source−Now)，迟到M3显式拒绝且不回插过去；不重戳/外推/重放。固定source表是预先已知的synthetic eventstream，不声称真实观测可提前预测未来位姿。

主要判据：future提前生效时长/position mismatch积分（相对每段source轨迹，late包在3.5前属于未知；该区间与被拒后的误差单独列，不以总误差择优）、late拒绝计数、真实GetPosition/传播计算采样及probeRSSI/收件。M1/M2即时法仅提前10ms，低于当前20ms credit；Schedule应恰在2.0/3.0生效，M3拒绝。额外固定1.995/2.005与2.995/3.005探针（各128B、独立ID）使前后采样不同于同刻UID顺序，其余20Hz probe不变。位移是UGV小步/约.2m/s尺度的合成轨迹，不以远距离RF断链放大收益。RF/成功率如因固定距离未明显分离就如实报不明显，不能换距离重测；不要求scheduled吞吐更高。此为借鉴DUSC logical-time placement原则的小试，未实现其完整协调器。

## 保存与实际入口（批准后才执行）

单一二进制paper-methods，--trial=reliability --transport=udp/tcp 或 --trial=position --placement=immediate/scheduled。每次新exclusive结果目录，不覆盖；native内独立PCAP四无线device、事件JSONL、app请求/回包全文hex、位置事件原source/arrival/applied整数ns、TCP seq/ACK/重传、MACdrop/retry、结束summary均保留。小业务日志有界且不每PHY事件打印巨量文字。无PCAP禁用或省证据。

依次固定run names：reliability-udp-01、reliability-tcp-01、position-immediate-01、position-scheduled-01；均由同一已构建ELF执行，单次timeout30s，8sim。结果位于net01/experiments/paper_methods/native/results/<name>/。运行前记录确切argv、ELF/链接身份与进程边界；runtime错误/硬界/内容或时戳错误保原件并停后续，由主审决定，不能自动修完重跑。UDP预定两丢失或即时法因果违例属于对照，不触发误判工具失败。

结束只报告两成对问题的有限证据：不替代真实WiFi满载、ROS/Action、.3wall/物理停止认证，不自动开始NET02、生产可靠协议或新Gazebo。

## 精确待批准入口

构建（只新目录）：

```sh
cmake -S net-01/workspace/net01/experiments/paper_methods/native -B net-01/build/paper-method-trials -DCMAKE_BUILD_TYPE=Release -DNS3_BUILD_DIR=/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03/build -DCONFIG_HEADER_DIR=/home/zhuyulab/ns3-workspace/net-01/build/network-full-payload
cmake --build net-01/build/paper-method-trials -j2
```

按顺序每次只执行一个（工作区根，rtk proxy前缀沿本地规范）：

```sh
python3 -B net-01/workspace/net01/experiments/paper_methods/native/run_trial.py reliability-udp-01
python3 -B net-01/workspace/net01/experiments/paper_methods/native/run_trial.py reliability-tcp-01
python3 -B net-01/workspace/net01/experiments/paper_methods/native/run_trial.py position-immediate-01
python3 -B net-01/workspace/net01/experiments/paper_methods/native/run_trial.py position-scheduled-01
```

runner原生子进程硬timeout29wall，余1wall留kill/wait和小摘要封存；每case目录exclusive，不自动再启或续时。整个小试无子孙进程。创建目录/记录argv不算native启动，实际child start才计数；若launch本身失败保错误不自动重试。

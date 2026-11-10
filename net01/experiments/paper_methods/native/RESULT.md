# Native paper-method trials：结果

**4/4预注册native case均唯一结束，无runtime error/timeout；只证明两个有限机制，不是Nav2/NET01修复验收。** 0ROS/Gazebo/机器人/训练/宿主网络修改，无第5次试验。生产82bc、V3、冻结策略与全部旧证据不改。

## 实际执行与构建

既有Release-portable ns3.40原库、头文件同根，13个ns3 DSO未混加载。独立ELF `f1d47d33a03f8e4828b4eba770e48cc15702af9b383d7eb63b2c60a6c7e8b06f`，419248B，四例同一ELF。首configure0/build2：新源漏propagation头文件；原source/stdout/stderr/exit全留。仅补该include后build02 exit0/25.733wall；没有模型试跑失败后修改源码重跑。

| case | sim秒 | process exit | 实际runner wall秒 | 唯一请求/处理 | 真应用回复 |
|---|---:|---:|---:|---|---|
| reliability UDP |8|0|.315314|101/104各一次；102/103未收件|101两次、104一次|
| reliability TCP |8|0|.315533|101/102/103/104各一次|101两次、其余各一次|
| position immediate |8|0|.265342|97/97，各一次|97/97|
| position scheduled |8|0|.265443|97/97，各一次|97/97|

完整105B请求、105B回包或128B probe的实际接收字节与提交原文逐byte相等，实际body全文hex已保留。TCP/UDP共同4B frame另计；TCP按真实socket Recv流重组，接收端只回复实际收件/其缓存，不从源端恢复blob。每例四无线设备PCAP，共16份，包含PM01业务内容；TCP数据与ACK真实经WiFi。没有关闭PCAP/原MACPHY记录。

## 可靠传输：有限正证，有时间代价

固定真实Range gate断链2–3sim。UDP在2.1/2.3发出的ID102/103均未到目的应用，也没有回复；没有应用重送。TCP实际连接完成.822822666sim，原默认SegmentSize536、MinRto1sim、ConnTimeout3sim，未调整。

TCP原发送：seq110/109B@2.100000001、seq219/109B@2.300000001；恢复后seq110/218B@3.100000001覆盖两个已发范围，目的端3.100269103收到两个完整请求，中央3.104835422收到原样应用回复。两请求的逻辑往返延迟分别 **1.004835422sim、.804835422sim**。原summary `tcp_repeated_seq_extents=0`只数完全相同(seq,length)，因合并重传长度改变而没有命中；不能用该计数否认已经记录的重叠sequence区间，也不冒称它是完整重传包总数。无代码改写或重跑。

重复ID101在5sim重新提交，服务端只返回既有真实cache，逻辑处理计数仍1。**可靠字节传输+幂等应用ID这个方向有用，但当前是合成handler，不是真Nav2 Action/UUID。** ns3自由逻辑时间没有和wall同步，8sim约.2wall完成；这些结果不代表原.3wall/.12sim门限通过。TCP还需有限不可确认态、真实Goal响应/取消/所有权规则；可靠流的队头等待与断线也未被本小试解决。

## 源时间位置：纠正提前，不自动消灭陈旧误差

主试只有10ms future提前量和小UGV位移，无40m跳跃。额外边界probe验证：

| probe时刻sim | immediate x | scheduled x |
|---|---:|---:|
|1.995|.727|.725|
|2.005|.727|.727|
|2.995|.927|.727|
|3.005|.927|.927|

Scheduled实际在2.000/3.000sim才SetPosition，不把未来源位姿提前10ms投入模型；3.5才收到source3.2的M3，明确拒绝，不倒写过去。Immediate在1.990/2.990提前应用，M3则3.5才应用。事件原source/capture/actualapply、GetPosition边界、sniffer信号/噪声和实际probePCAP都已保存。

按已登记的分段常值synthetic参考轨迹，对[1.2,3.2]的已知future部分，位置误差积分immediate=.00202m·sim秒、scheduled=0。对源M3尚未到达的[3.2,3.5]两者均.012；在[3.5,5.8]，immediate已跟上参考为0，拒绝late的scheduled仍旧值，误差积分.092。**拒绝迟到保证不回插过去，并不保证位置估计更准。** 全部probe两例均97/97真实往返，小位移未显示吞吐可靠性收益；不据些微RSSI/CPU差称无线性能改进。预先给出的未来事件是合成输入，不能假定真实机器人能预测未来，也没有实现完整DUSC。

## 对当前工程的意义与停止边界

- TCP方向支持进一步设计真实、有界、同session/RPC/UUID的可靠Action交付；不能把本结果写成当前两个未确认真实Goal已经补救或Nav2安全恢复已验。
- 按逻辑源时间安排radio位置可防止未来状态提前作用，前提是事件确实提前可得；迟到需另行定义保守策略。不能借source时间回插网络业务，不能用真值更新策略。
- 两种协议虽用同seed/run，协议带来帧数/事件/RNG消耗不同，不保证空口随机轨迹逐点相同。自由ns3逻辑时间的TCP恢复不等于原300ms期限。
- 本小试不覆盖满业务、ROS执行器、Peer→C137.93ms等待、物理停止或ownership认证，不撤销followup04的B FAIL/NET01 BLOCKED。

依据：[事前PLAN](PLAN.md)、[四例原件与提取摘要](results/SUMMARY.json)、[构建/链接身份](results/BUILD_IDENTITY.json)、[小账本](results/RUN_LEDGER.json)。所有原件保留，停止新增运行；未Git提交/推送，由root统一交付。

构建所用`network_config.h`不是只能依赖会话驻留的私有输入：已有`net01/tools/check_network.py`的`generated_header(config)`可从版本化`net01/config/NETWORK_LOCK_V3.json`重建；本次直接只读复用既有生成header，其实际SHA/路径已记BUILD_IDENTITY，不运行重生成覆盖旧文件。新CMake的CONFIG_HEADER_DIR显式指向该header目录，NS3_BUILD_DIR显式指向原Release同根头库。

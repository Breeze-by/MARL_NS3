# 两地图四通信条件五次比较：最终结果

完成时间：2026-11-14 06:40:16 Asia/Shanghai（UTC 2026-11-13 22:40:16）。唯一串行driver与全部仿真已退出，未追加实验。

实际42次Gazebo/host启动，得到40个完整120sim比较窗口；每图每条件5个窗口，34/40达到中央首次质量有效T95。40/40窗口测量资格通过；完整工程资格与clean exit各36/42 actual attempts（在40窗口中为36/40），另有4个窗口后的退出失败与2次零自主窗口启动失败。原失败、原始记录和两次失败RAM均保留。

来源：[唯一汇总](SUMMARY.json)、[40行原始统计](rows.json)、[最终退出/复制核对](FINAL_EXECUTION_CHECK.json)、[canonical执行记录](execution.jsonl)。数据导出：[逐次窗口CSV](runs.csv)、[分组均值CSV](summary.csv)、[全部42次attempt CSV](attempts.csv)。逐robot/topic分母及延时保留在rows.json的source_cohort_by_topic/source_to_hq_latency_by_topic与每例delivery.json，未用高频TF总体均值替代地图分项。

## 共同合同与测量含义

Corr6201、Rooms6101各5个seed块，四条件同块共用physics seed2026111301..1305、native seed2026110901/run1..5；地图间复用块作配对，不是10个独立RF种子。采用原锁顺序、共同G20→140的120sim窗口、23个G25..135决策边界、40wall-ms/10sim-ms节拍和2wall-s保护。所有40窗口使用同77项runtime身份、同PPO权重/701结构和repair-v1行为；CPU/PCAP等共同诊断成本计入原时序门。

A0=ROS直连（中央应用域R92），A1=本地网关FIFO，B=ns-3较高容量/强信号档（MCS9、16dBm、路径损耗指数2），C=低速率/低功率/高损耗复合档（MCS3、2dBm、指数3）。A0/A1的native仅管理时钟，不承载业务。C不是单一RF变量；Gazebo墙不会自动形成RF遮挡，当前模型没有实测室内Wi-Fi标定。

主时延是已有R Observer map/odom/tf/tf_static四类订阅同次take所观测源cohort（非全部业务）的原DDS publication时间→实际HQ native take返回的wall-ms，包含队列和软件处理；不是generation AoI、纯RF延时或sim-ms。交付率只针对这个已观察源cohort，不是所有publisher排放或RF包丢失率。时延只对已匹配交付消息计算，必须与逐次分母、未观察数量和条件交付率一起解释；未观察消息未算入时延，不能因为慢消息缺席就宣称链路更快。40例测量均有效，所有窗口均为120sim。

## 按run等权的主结果

所有“±”为5个逐次结果的样本SD（ddof=1），不按消息数量加权。交付率的SD为百分点。T95只有质量有效且预算内首次达到才有值；未达保持null，不以120补值。Rooms四组的全部5次真实T95均值均为N/A；仅达标者均值是条件统计，不能直接当作五次T95均值或据此给全组排序。

|地图|条件|源publication→HQ take平均 wall-ms|源观测cohort条件交付率 %|T95达标|全部5次T95 sim-s|仅达标者T95 sim-s（n）|末中央覆盖 %|
|---|---|---:|---:|---:|---:|---:|---:|
|Corr6201|A0|61.499 ± 6.336|99.837 ± 0.075|5/5|76.75 ± 17.28|76.75 ± 17.28 (n=5)|99.874 ± 0.029|
|Corr6201|A1|60.197 ± 8.270|99.785 ± 0.108|5/5|70.11 ± 20.03|70.11 ± 20.03 (n=5)|99.850 ± 0.057|
|Corr6201|B|101.956 ± 6.885|99.706 ± 0.229|5/5|75.39 ± 17.05|75.39 ± 17.05 (n=5)|99.582 ± 0.572|
|Corr6201|C|108.210 ± 12.775|99.706 ± 0.314|5/5|68.94 ± 15.26|68.94 ± 15.26 (n=5)|99.725 ± 0.282|
|Rooms6101|A0|107.260 ± 2.106|86.204 ± 2.038|4/5|N/A|106.50 ± 8.92 (n=4)|97.494 ± 3.471|
|Rooms6101|A1|108.141 ± 4.066|88.642 ± 2.444|3/5|N/A|88.26 ± 22.86 (n=3)|95.925 ± 4.460|
|Rooms6101|B|152.326 ± 4.267|85.866 ± 2.050|4/5|N/A|99.66 ± 14.56 (n=4)|97.483 ± 3.018|
|Rooms6101|C|155.158 ± 4.843|87.667 ± 3.124|3/5|N/A|104.05 ± 7.82 (n=3)|92.737 ± 6.759|

## 运输机制与全部启动可靠性

下列P95是“每次运行P95”的5次均值±样本SD，不是混合全部消息后的P95；native sim-ms、A1 witness sim-ms与主wall-ms分开，A0不适用项为N/A。这里native服务只统计可匹配TopicWire capture的实际admission→native RX，不是全部Action RPC、feedback或BoundMask业务的总体P95；A1 witness为0只说明同一sim-clock刻度，不等于实际wall零延迟。

|地图|条件|wire capture→目的publish交付率 %|native service P95 sim-ms|A1 FIFO witness P95 sim-ms|实际attempt / 有效窗口 / 完整工程 / clean exit|
|---|---|---:|---:|---:|---|
|Corr6201|A0|N/A|N/A|N/A|5 / 5 / 5 / 5|
|Corr6201|A1|100.000 ± 0.000|N/A|0.000 ± 0.000|5 / 5 / 5 / 5|
|Corr6201|B|99.999 ± 0.002|5.836 ± 0.074|N/A|5 / 5 / 3 / 3|
|Corr6201|C|99.996 ± 0.005|24.533 ± 0.977|N/A|7 / 5 / 5 / 5|
|Rooms6101|A0|N/A|N/A|N/A|5 / 5 / 5 / 5|
|Rooms6101|A1|100.000 ± 0.000|N/A|0.000 ± 0.000|5 / 5 / 5 / 5|
|Rooms6101|B|99.997 ± 0.004|5.872 ± 0.165|N/A|5 / 5 / 5 / 5|
|Rooms6101|C|99.996 ± 0.003|26.084 ± 0.995|N/A|5 / 5 / 3 / 3|

B→C的native service P95均值在走廊由5.836→24.533sim-ms（4.20倍），房间由5.872→26.084sim-ms（4.44倍），确认无线档位的服务延时变差。源publication→HQ端到端平均wall延时两图也从B到C增加；与A0/A1相比，B/C平均wall延时更高。任务层没有跨两图一致的单调恶化：走廊四组均5/5，C的T95均值反而更小；房间A0/A1/B/C分别4/3/4/3达标。不能据这些小样本将所有差成绩唯一归于RF，或强求无线越差任务一定越差。

40窗原pacing/clock/23边界/停稳/UUID闭合/复制门通过。10个同map/block四臂RTF对称跨度(max-min)/((max+min)/2)均≤1%，最大0.002399%；未重锚、删迟到token或把等待从wall时间扣除。2435个已知PID实际全退，无活动GZ/native/host；42份native证据共127,611,540,763B完整复制，全部disk raw保留，40个窗口RAM按原proof释放。

## 显式事后修订与边界

- [AM1](WINDOW_METHOD_AMENDMENT01.json)：c04/c06/c09/c14原host/network退出FAIL不变。只有完整有效任务窗、完整trace/IDs、原7门与实际同PID/session/case资源闭合→persist_end→clean close_return→main_return(code0意图)，全部早于原supervisor SIGTERM下界，才将窗口数据纳入；实际OS退出仍-15，full/clean=false。c04原row的N/A保留，统一amended副本回溯前4例。没有把main_return意图冒称实际exit0。
- [AM2](OFFLINE_METHOD_AMENDMENT02.json)：Rooms负坐标被分离的--positions参数拒绝，原T95尚未读bag；仅改为--positions=<原值>并一次恢复c05 T95，delivery与实验不重跑，原解析失败日志/BLOCK保留。
- [AM3](STARTUP_REPLACEMENT_AMENDMENT03.json)/[AM4](STARTUP_REPLACEMENT_AMENDMENT04.json)：原c16/c29实际Gazebo启动时tb3的/spawn_entity响应transport timeout，无三机exit0/fence/ready，0RUN、无HQ/NN/Goal；G5.30仅STOP_COUPLED收尾。T95=N/A_NO_AUTONOMY，原stopFAIL不改；按独立审查分别明确授权一次fresh c16s/session1741、c29s/session1742，同原seed/条件/顺序。两例均Corr/C，底层RMW原因未定且未修复，不能假定缺失随机。主表是成功进入自主窗口后的条件比较，另列Corr/C实际7attempt/5窗口及全体42attempt可靠性；不是全部启动尝试的无条件性能结论，不存在自动替补规则。

本批全部运行均为相同的修复前77-runtime版本。批次后的Gateway成功退出小修已完成20项真实OS child组件验证、全部wait回收，见[独立修复结果](post-cohort-exit-fix/RESULT.json)；没有新Gazebo运行，不追溯改变上述4个poststopFAIL，也不声称已有Gazebo复验。该小修不处理两次startup的底层RMW原因。旧v1/v2 discovery、两个GDB诊断、er13单例及更早RF组全部不混入本表；无训练、NET-02、压缩或无线调参。

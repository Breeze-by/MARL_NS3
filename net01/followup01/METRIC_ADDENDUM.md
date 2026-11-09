# 失败episode离线指标补充

本补充独立于已封存33765d3报告与身份。主审撤回先前额外设置的“只有健康180sim才可运行metric”条件：失败episode也应量化已收到地图。**这不改变A03/A04的FAIL或NET-01 BLOCKED，不签网络性能/完整任务通过。** 旧REPORT、RUN_LEDGER、DELIVERY_MANIFEST、外部FOLLOWUP01_DELIVERY_IDENTITY和原bag不改；以本补充提供其中“未测量”项目的后续实际结果。

沿用冻结`gz01/analyze_recorded.py` / `metrics.py` / `bag_records.py`，经现有`ros-python.sh` rootfs纯离线执行。SQLite只读，只有消息反序列化与评价计算，没有rclpy.init/Node、Policy、Nav2、Gazebo、Action或训练调用；两个sealed bag各一次、native0，调用参数见[INVOCATIONS](offline-failed-metrics/INVOCATIONS.json)。没有改工具源码/阈值、模型或旧600结果。

仍原Corr6201/common triangle、固定ROI[-5.8,-5.6,7.25,5.3]和.05m，闭合可达分量**15558格 / 38.895m²**；原map坐标与固定标定，不做拟合/平移补偿。t0取原exploration_command，end取其后首error；只计收到图的原bag/ROS时刻，不倒推min-source header、不计stop后图。原quality同时要求足够占据证据、free precision≥.95、occupied median≤.10m/p95≤.25m及known-obstacle recall≥.80，全部不变。

|回合|原自主窗口sim|初始coverage（原始C0）|窗口末收到图：coverage|quality有效帧|T90 / T95 / T98|
|---|---|---|---|---|---|
|A03|31.0→43.0，共12.0|11.0811%，baseline质量无效|42.8sim：5847/15558 = **37.581951%**|2/9；7帧无效|均**未达**（raw及quality均null）|
|A04|30.4→38.5，共8.1|11.1133%，baseline质量无效|38.3sim：5308/15558 = **34.117496%**|1/6；5帧无效|均**未达**（raw及quality均null）|

“未达”只指实际短失败窗口，不能补填0秒、外推180sim或当完整180回合失败率；也不能把两个不同长度短窗直接排名。末收到图均通过原quality判据：A03 free precision99.0091%、occupied median0/p95.05m、obstacle recall98.0562%；A04分别98.9770%、0/.05m、98.2412%。**末帧质量有效可核，但仅2/1帧有效，不足验证持续地图质量或完整探索可靠性（NOT VERIFIED）。** 原run_integrity=false、源龄fatal、A04后续clock lag、B/C NOT RUN均保留。

原工具还给自主窗口内真实轨迹路程（与原runtime全期含启动/停机的路程不同）：A03 tb1/tb2/tb3为.41022/.15518/.30178m；A04为.54087/.31818/.44802m。每机各1请求，任务窗口内无成功/终态，故该metric的canceled=0；故障后的各3个真实CANCELED/UUID闭合属于停机阶段，不能混进自主成功或抹掉其停止证据。没有因短路程改写原三机参与门槛。

结果原件：

- [A03结果](offline-failed-metrics/A03/result.json)、[曲线CSV](offline-failed-metrics/A03/coverage.csv)、[参考及末图NPZ](offline-failed-metrics/A03/reference-and-final.npz)。
- [A04结果](offline-failed-metrics/A04/result.json)、[曲线CSV](offline-failed-metrics/A04/coverage.csv)、[参考及末图NPZ](offline-failed-metrics/A04/reference-and-final.npz)。

A02没有自主t0，不硬套本工具。此次新增0Gazebo/Node/NN/训练；累计87及续轮3/3不变，不新增运行、补丁、单元测试、完整性重扫或NET-02。完成本地docs提交后停止。

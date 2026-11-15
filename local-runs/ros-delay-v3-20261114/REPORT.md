# ROS单向wall延时消融：70窗口正式结果

截至2026-11-15，V3正式批次已停止：**78次实际启动、70个完整120sim合格任务窗口，中央质量有效T95达标55次、明确未达15次、缺测0次**。8次未进入自主窗口的启动工程失败保留，完整工程/clean exit为70/78；不能把78次启动写成全PASS。Root和独立审查均已接受[最终闭合](FINAL_EXECUTION_CHECK.json)。本报告直接使用[官方小统计投影](SUMMARY_STATISTICS.json)，未重算原bag、T95或交付指标。

## 实验与统计口径

- Corr6201与Rooms6101，每图A0、D0/D100/D200/D300/D400/D500各5次，使用5个预声明配对seed/run块和锁定顺序。每组独立重复单位为运行，以下均值±样本SD按run等权；不是把消息数当重复数。5轮/7条件仅近似平衡，不称完全Williams平衡。
- A0是新的literal ROS直连校准；D0..D500为同一本地ROS/CDR FIFO代理、额外每次跨端单向0..500 **实际wall-ms**，业务双向。纯延时比较只在D0..D500内，A0→D0是代理校准。全部70例均无ns-3 Wi-Fi业务，native服务延时N/A；不能把本轮条件交付率称无线丢包率。
- 共同G20起点、G25..135的23个原attempt、120sim预算、原10sim-ms/40wall-ms绝对节拍、2wall-s保护及停止/UUID/资源/复制门不变。PPO权重/701与探索修复行为基线固定。七条件共同source-age为odom .70sim/correction .85sim，health/mask/Observer receipt .60sim，producer projected-odom receipt .50sim；由四实际owner及真实整数ns实例证明，未用只读配置冒充应用。
- T95是相对G20的首次质量有效中央应用地图callback；A0中央域R92，D组C91。不按header补到达时间，不把未达补成120。表中全五次T95均值仅5/5达标时存在；达标者条件均值注明n，不能据此给未达组做整体速度排序。末覆盖为实际窗口末附近的中央观察，不假定精确G140采样。

## 任务结果

各组窗口/完整工程/clean均5/5；n/m/k分别为已证达标、在有效实际窗内明确未达、工程或测量未知。本批k均0。实际启动数包括额外startup失败。

|地图|条件|n/m/k|全5次T95均值±SD（sim-s）|仅达标者T95（sim-s）|末中央覆盖%±SD|实际启动|
|---|---|---|---:|---:|---:|---:|
|Corr6201|A0|5/0/0|67.86 ± 16.05|67.86 ± 16.05 (n=5)|99.86 ± 0.03|6|
|Corr6201|D0|5/0/0|79.74 ± 23.15|79.74 ± 23.15 (n=5)|99.87 ± 0.02|7|
|Corr6201|D100|5/0/0|72.45 ± 17.10|72.45 ± 17.10 (n=5)|99.86 ± 0.02|5|
|Corr6201|D200|4/1/0|N/A|71.97 ± 14.66 (n=4)|95.18 ± 10.16|5|
|Corr6201|D300|4/1/0|N/A|61.49 ± 20.29 (n=4)|95.44 ± 9.93|5|
|Corr6201|D400|4/1/0|N/A|59.59 ± 21.60 (n=4)|97.73 ± 4.77|6|
|Corr6201|D500|5/0/0|62.78 ± 14.56|62.78 ± 14.56 (n=5)|99.74 ± 0.22|5|
|Rooms6101|A0|4/1/0|N/A|91.64 ± 17.48 (n=4)|97.80 ± 2.35|6|
|Rooms6101|D0|5/0/0|95.84 ± 16.92|95.84 ± 16.92 (n=5)|98.60 ± 1.38|7|
|Rooms6101|D100|3/2/0|N/A|95.73 ± 17.82 (n=3)|93.70 ± 7.09|6|
|Rooms6101|D200|4/1/0|N/A|97.86 ± 13.25 (n=4)|95.06 ± 7.98|5|
|Rooms6101|D300|2/3/0|N/A|111.55 ± 3.69 (n=2)|88.34 ± 9.51|5|
|Rooms6101|D400|3/2/0|N/A|94.29 ± 20.93 (n=3)|96.49 ± 3.42|5|
|Rooms6101|D500|2/3/0|N/A|96.44 ± 11.00 (n=2)|96.12 ± 3.17|5|

## 通信测量

源cohort仅为已有R Observer对**map/odom/tf/tf_static四类话题的同次take**观测到的源publication。主wall时延回溯原DDS publication→HQ native take返回，包含软件处理和hold队列；不是generation AoI。条件交付率只对应这个有界观测cohort，不是全部publisher原始发送或无线包丢失率。各case保留逐robot/topic样本n与分母。

下表“P95”列是**各run P95的均值±样本SD**，不是全部消息合池后的P95。端到端wall与hold分别计；hold只是capture→FIFO就绪释放，不是实际接收/publish/HQ take，排除closing_drain及窗外释放。A0无hold，不填0。全部主通信统计available_runs=5。

|地图|条件|源条件交付%±SD|源→HQ平均wall-ms±SD|run P95 wall-ms±SD|实测hold平均wall-ms±SD|run hold P95 wall-ms±SD|
|---|---|---:|---:|---:|---:|---:|
|Corr6201|A0|99.79 ± 0.30|56.55 ± 7.96|487.36 ± 83.93|N/A|N/A|
|Corr6201|D0|99.76 ± 0.04|61.68 ± 6.50|489.79 ± 83.25|0.08 ± 0.00|0.11 ± 0.00|
|Corr6201|D100|99.60 ± 0.36|163.71 ± 9.52|606.72 ± 100.64|100.75 ± 0.05|101.91 ± 0.12|
|Corr6201|D200|99.63 ± 0.32|260.21 ± 12.33|668.77 ± 134.42|200.79 ± 0.07|202.08 ± 0.22|
|Corr6201|D300|99.63 ± 0.21|369.14 ± 7.13|871.86 ± 79.64|300.76 ± 0.06|301.94 ± 0.14|
|Corr6201|D400|99.63 ± 0.16|467.42 ± 5.61|942.51 ± 60.22|400.68 ± 0.03|401.72 ± 0.07|
|Corr6201|D500|99.27 ± 0.80|568.59 ± 12.88|1070.91 ± 139.00|500.74 ± 0.04|501.90 ± 0.07|
|Rooms6101|A0|86.06 ± 3.82|110.78 ± 7.84|1014.77 ± 51.39|N/A|N/A|
|Rooms6101|D0|87.16 ± 2.64|114.16 ± 5.67|1011.40 ± 34.64|0.08 ± 0.00|0.11 ± 0.00|
|Rooms6101|D100|86.69 ± 1.49|212.56 ± 4.96|1088.69 ± 33.12|100.73 ± 0.04|101.87 ± 0.09|
|Rooms6101|D200|86.97 ± 2.97|312.58 ± 9.57|1185.89 ± 63.14|200.80 ± 0.03|202.08 ± 0.10|
|Rooms6101|D300|85.83 ± 3.63|413.83 ± 5.28|1302.01 ± 35.37|300.77 ± 0.06|301.96 ± 0.13|
|Rooms6101|D400|85.91 ± 3.97|512.69 ± 5.12|1389.68 ± 38.88|400.70 ± 0.05|401.77 ± 0.14|
|Rooms6101|D500|86.66 ± 1.57|609.13 ± 3.52|1459.86 ± 18.18|500.79 ± 0.10|501.98 ± 0.20|

## 资格、失败与事后修订

70份原窗口/7项工程门、四owner实际应用、停止/UUID/复制/owner退出证明通过；全部进入完整120sim，无合格partial。10个同map/block七条件RTF对称跨度门均通过，最大0.08674458% < 1%，公式为(maxRTF−minRTF)/((maxRTF+minRTF)/2)。未把缺测RTF补成.25。原driver仅生成一次官方SUMMARY，实际exit0；所有已知actor/writer退出、native完整复制，队列保持关闭。

8个startup原件均为0RUN/0自主/HQ/NN/Goal，T95为N/A_NO_AUTONOMY，**不是120sim内未达**；它们占全部启动可靠性分母，原stop/PAUSE/seal FAIL、无proof、RAM及disk raw保留。7次是本地/spawn_entity响应发送timeout（涉及tb2或tb3），f028则三spawn exit0后factory实体查询进程无输出挂起（实际Gazebo transport request/response边界未观测）；底层RMW/Gazebo transport原因未定、未修复，不属于D FIFO任务消息的测量结果，也不假定缺失随机。

|原失败physical|地图/条件/块|显式named后继|事后修订|
|---|---|---|---|
|f005|Corr6201/D400/b1|f005s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT01.json](STARTUP_SUCCESSOR_AMENDMENT01.json)|
|f012|Rooms6101/D0/b1|f012s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT02.json](STARTUP_SUCCESSOR_AMENDMENT02.json)|
|f021|Rooms6101/A0/b2|f021s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT04.json](STARTUP_SUCCESSOR_AMENDMENT04.json)|
|f026|Corr6201/A0/b2|f026s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT05.json](STARTUP_SUCCESSOR_AMENDMENT05.json)|
|f028|Corr6201/D0/b2|f028s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT06.json](STARTUP_SUCCESSOR_AMENDMENT06.json)|
|f028s|Corr6201/D0/b2|f028t（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT07.json](STARTUP_SUCCESSOR_AMENDMENT07.json)|
|f049|Rooms6101/D100/b4|f049s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT08.json](STARTUP_SUCCESSOR_AMENDMENT08.json)|
|f067|Rooms6101/D0/b5|f067s（仅一次）|[STARTUP_SUCCESSOR_AMENDMENT09.json](STARTUP_SUCCESSOR_AMENDMENT09.json)|

因此主70行是“成功进入自主窗口后的条件比较”，不是全部启动尝试总体性能。Corr D0与Rooms D0各7attempt/5窗口，Corr A0、Corr D400、Rooms A0、Rooms D100各6/5，其余5/5；实际总分母78。所有后继均单独Root审查，不依据T95成绩选样或自动重试。原f028与f028s为两种不同启动失败，AM6限一次没有被改写为通用重试。

**AM3是离线方法事后纠错，不能冒称原分析已PASS。** f016原完整任务窗保留，原BLOCK/UNKNOWN/所有旧文件不改；关闭后未准入的15条capture复用最后消息ID，导致原身份检查误与合法目的消息比较。修正仅在原摘要冲突时，用唯一真实queue admission、actual send metadata、单调关闭时序及窗外/源cohort不交集证据单列NOT_ADMITTED_POST_CLOSE；真实已准入消息（包括closing drain）仍严格查CDR摘要，模糊/窗内/缺证仍BLOCK。一次独立amended分析复用原真proof与完整T95文件（无重verify/T95），新delivery仅运行一次，9个主窗字段与原一致；严格原classifier得到有效T95=108.94sim。见[METHOD_AMENDMENT03](METHOD_AMENDMENT03.json)、[恢复实录](F016_AMENDMENT03_RECOVERY.json)、[独立amended结果](post-exit/f016-AMENDMENT03/result.json)。前15例原身份错误为0，静态证明旁路新规则，未重算。

全部78次实际运行共用同79-runtime身份；9项离线方法只有上述analyzer显式AM3换版，不能称70例所有方法hash完全相同。原COMMON、消费READY及失败原件保留；[当前方法绑定](COMMON_BINDING_METHOD_AMENDMENT03.json)继承原runtime。此前V1五诊断、V2二十七次实际启动（包括其好成绩与e023缺测）分别封存，32个前序attempt均不并入本批。

## 能支持与不能支持的结论

注入hold实测接近声明wall延时，D0→D500的源→HQ平均wall延时明显增加：走廊+506.92ms、房间+494.97ms；但任务T95/达标率没有逐档、跨图一致单调恶化。例如走廊D500仍5/5达标，D200/D300/D400各4/5；Rooms D0为5/5，D300/D500各2/5，D400为3/5。保留这些非单调事实，不只展示符合预期的组，也不据5次重复宣称显著性、策略优越性或唯一RF因果。

代表性差例f006（Corr/D200/b1）是完整有效未达：17个目标真实接受，8次Nav2 UUID从EXECUTING到ABORTED；tb1多次GridBased无有效路径，tb3 DWB 0/419合法轨迹/BaseObstacle预测障碍，Spin/Backup恢复也报告CollisionAhead。自主期未见Observer guardfault/保护零速或提前撤权，代理拒绝0，首三个Goal真实成功，故不是旧代理权限latch导致静止。CollisionAhead是碰撞预测，不证明实际物理碰撞；组合costmap无法分开static/SLAM/boundary/peer贡献，不能唯一归D200或据此修改/筛除该例。

本批业务不走Wi-Fi，仅施加固定ROS业务延时；原native B仍用于共同clock/control，过去ns-3四路比较与本批不池化。传播模型真实室内校准、完整generation→use AoI、唯一RF任务因果和实机等价仍未证明。批次结束后未追加其他机器人实验，未训练、未开展NET-02；只继续使用T95。

## 权威来源与交付状态

- [官方SUMMARY](SUMMARY.json)、[95KB全部统计投影](SUMMARY_STATISTICS.json)、[原canonical执行记录](execution.jsonl)、[冻结计划](PLAN.draft.json)、[Root接受的逐attempt闭合](FINAL_EXECUTION_CHECK.json)。
- [8次startup登记](STARTUP_FAILURE_REGISTER_AMENDMENT09.json)、[初始COMMON](COMMON_BINDING.json)、[AM3方法绑定](COMMON_BINDING_METHOD_AMENDMENT03.json)。各case的原proof、三视图T95 CSV、源cohort/topic统计、hold队列与真实Goal/运动记录由PLAN/闭合中的实际路径追溯；大raw不随Git完整分发。
- 中文图表汇总已在Root完成59页渲染/关键页视觉验收、独立成品MD终审后复制交付：[PDF（59页）](/home/zhuyulab/Desktop/ROS固定延时消融图表汇总/ROS固定延时消融图表汇总.pdf) · [Markdown](/home/zhuyulab/Desktop/ROS固定延时消融图表汇总/ROS固定延时消融图表汇总.md)。完整目录`/home/zhuyulab/Desktop/ROS固定延时消融图表汇总/`含35份PNG、35份SVG及21份data文件；来源/范围和实际复制记录见[最终QA](visual-summary/qa/FINAL_QA.json)、[Desktop交付记录](visual-summary/qa/DESKTOP_DELIVERY.json)及交付目录的`REPORT_PROVENANCE.json`。图表沿既有三视图T95、真实路径与官方统计，不新增实验或重算任务指标。

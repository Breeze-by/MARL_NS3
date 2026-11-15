# 首次 ns-3 业务集成工程定版 v1.0.0

本版完成ns-3业务接入；目前结果尚未建立通信导致任务完成度下降的可靠因果证据，也不证明通信没有影响。

本版标签为 `MR3-NS3-INTEGRATION-v1.0.0`，不升级或替换固定策略标签 `MR3-RL-POLICY-v1.1.0`。已先备份含未提交源码的试验工作树，再恢复默认 **Nav2 inflation=0.55m、peer=0.55m、robot_radius=0.25m**；恢复核对通过，未为发布追加仿真。

## 本版交付

- 固定真实PPO v1.1.0与701维编码，结合Gazebo三机器人、ROS 2 SLAM/Nav2及ns-3原生Wi-Fi业务交付；PPO选择高层目标，Nav2控制运动。
- 受限通信业务使用显式跨域/CDR与Action代理，经实际ns-3 MAC/PHY交付；保留原时钟、UUID、安全停止及追踪边界。离线地图真值不输入策略。
- 备份并恢复上述0.55/0.55/0.25默认半径。0.40/0.52组合源码与证据归档于独立备份分支，不凭差例/单例成绩替换默认参数。
- 发布桌面三份中文PDF/MD及关联图片、覆盖/轨迹和紧凑表格数据：历史《通信方式对比图表汇总》、正式《40轮通信方式对比图表汇总》、正式《ROS固定延时消融图表汇总》。不把原始bag、pcap、大ledger或RAM缓存推入仓库。

## 相互独立的证据

|证据批次|实际执行与任务结果|边界|
|---|---|---|
|两图四通信条件|42次实际启动；40个完整比较窗口，34/40达中央质量有效T95；36个全工程/正常退出，4个原停后退出FAIL和2个零自主启动FAIL保留|每图A0/A1/B/C各5窗；不能把测量窗资格等同全部工程退出PASS|
|两图ROS固定wall延时|78次实际启动；70个完整合格120sim窗口，55达标/15明确未达/0未知；8次零自主启动原FAIL保留|A0为直连校准，D0..D500共用本地代理；业务不走Wi-Fi，native仅共同clock/control|
|两图导航间距试验|7次实际启动；6个完整合格窗口，走廊3/3、房间1/3达T95；原a03启动失败保留|同seed历史A0只作描述参考。0.40/0.52没有普遍加速或稳定改善证据，未替换默认|

历史通信汇总包含更早的不同合同，不与上述40/70/6结果池化。各批次的事后离线方法修订、命名启动后继和实际attempt分母在原报告内明确记录；原FAIL、缺测与原始证据不追改。评价使用T95；未达T95保持null，不把预算120填成达标时间。

## 可支持和不可支持的结论

真实通信服务/端到端延时差异已有证据，但尚未建立“通信导致任务下降”的可靠因果证据；这不是证明通信没有影响。任务T95和达标率没有跨场景一致单调恶化，不能把所有差成绩唯一归因于无线RF。70窗延时组中房间D0为5/5达标、D500为2/5的实测损失仍保留，不用整体非单调掩盖这些差结果。ROS wall延时试验亦不等价于实测室内Wi-Fi模型。导航取消/中止和CollisionAhead预测不等同于物理碰撞。

这是有限仿真场景下的研究工程参考，不是实机验证或安全认证；未为本次发布重新训练PPO、开展NET-02或追加机器人实验。原Gazebo本地spawn响应发送超时等启动基础设施问题的底层原因未定，不宣称已经修复。

## 报告包与大小

三包总计129,606,186B；PDF分别2,282,870B、4,120,274B、9,018,077B，最大单件是34,352,108B的导出轨迹JSON。均低于普通Git单文件100MiB硬限制，也低于50MiB警告线，不需要为本三包引入LFS。[GitHub官方限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

两个新报告包的Markdown相对链接全在包内；旧报告的17条历史来源链接在仓库既有 `docs/communication-comparison-zh/` 位置全部存在且已跟踪。本版保留旧报告位置，并将另外两个包分别发布于 `docs/communication40-comparison-zh/` 和 `docs/ros-delay-comparison-zh/`。PDF/图片/导出数据不等于完整可移植原始实验包。

## 固定版本报告链接

- 历史通信汇总：[PDF](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/communication-comparison-zh/%E9%80%9A%E4%BF%A1%E6%96%B9%E5%BC%8F%E5%AF%B9%E6%AF%94%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.pdf) · [MD](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/communication-comparison-zh/%E9%80%9A%E4%BF%A1%E6%96%B9%E5%BC%8F%E5%AF%B9%E6%AF%94%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.md)
- 40轮通信比较：[PDF](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/communication40-comparison-zh/40%E8%BD%AE%E9%80%9A%E4%BF%A1%E6%96%B9%E5%BC%8F%E5%AF%B9%E6%AF%94%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.pdf) · [MD](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/communication40-comparison-zh/40%E8%BD%AE%E9%80%9A%E4%BF%A1%E6%96%B9%E5%BC%8F%E5%AF%B9%E6%AF%94%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.md)
- 70窗口ROS固定延时：[PDF](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/ros-delay-comparison-zh/ROS%E5%9B%BA%E5%AE%9A%E5%BB%B6%E6%97%B6%E6%B6%88%E8%9E%8D%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.pdf) · [MD](https://github.com/Breeze-by/MARL_NS3/blob/MR3-NS3-INTEGRATION-v1.0.0/docs/ros-delay-comparison-zh/ROS%E5%9B%BA%E5%AE%9A%E5%BB%B6%E6%97%B6%E6%B6%88%E8%9E%8D%E5%9B%BE%E8%A1%A8%E6%B1%87%E6%80%BB.md)

备份分支 [`backup/ns3-workingtree-clearance-20261115`](https://github.com/Breeze-by/MARL_NS3/tree/backup/ns3-workingtree-clearance-20261115) 保存恢复前完整已跟踪源码、未提交集成源码及试验小文本来源；原HEAD另存 `backup/ns3-pre-integration-head-20261115`。恢复后定版另存 `backup/ns3-integration-restored-20261115`。

本仓库包含三个图表包及精选轻量报告、统计与勘误；深层报告中的大型raw、绝对本机路径、已消耗READY、ROS根环境和原生构建物仍只在本机保留，不是完整可移植运行环境。`check_candidate_clearance.py` 的历史原观察重放分支需要本机原始NPZ/事件记录；其源码已保留，未以缺失raw冒充可直接重跑历史试验。

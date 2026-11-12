# NET-01 当前工程与证据入口

当前固定研究策略仍为`MR3-RL-POLICY-v1.1.0`。中央RL权重、观察编码、Frontier/目标规则和Nav2/SLAM核心未因本轮文献研读改变。

面向项目评估者的完整说明见[项目现状与关键问题](../docs/PROJECT_STATUS_2026-11-10.md)，另有[Word文档](../docs/项目现状与关键问题说明_2026-11-10.docx)。正文按实际探索效果、通信接入问题、修复成效和后续研究重点展开，包含覆盖率与完成时间，并说明目前能支持的结论。

## 2026-11-10 可靠Action交付已接入

已将**同RPC确认与有界重送**接入实际Gateway的A/B/C共用任务适配器，保持原UUID、完整Goal和Action CDR；这是应用层可靠机制，不是TCP。一次零Node检查16项通过，真实ROS 2—ns-3 Wi-Fi受控夹具03的20项检查通过：丢失请求重送后只执行一次，三目标两成功一取消，响应延迟/重复与ACK丢失正确处理，长GetResult不误判。永久断链明确INVALID，三本地PAUSE真实响应成功，但中央未决任务如实保留。01/02两次检查脚本失败全部保存。

详见[生产报告](followup05/REPORT.md)、[独立审查](followup05/INDEPENDENT_REVIEW.md)、[全部新执行账本](followup05/RUN_LEDGER.json)。这仅是**无运动的真实ROS/模拟Wi-Fi接口验证**：health/bound和clock为显式合成夹具输入，未运行真实Nav2或Gazebo，没有新增覆盖率/完成时间，也没有证明物理停止。原健康发布→捕获延迟仍未修复，见[只读定位与下一最小诊断](followup05/HEALTH_PATH_REVIEW.md)。NET-01整体仍BLOCKED，不自动运行Gazebo或NET-02。

## 已有真实Gazebo结果

**NET-01 BLOCKED，尚未形成可靠的三机器人Gazebo—ROS2—ns-3 Wi-Fi探索闭环。**

| 回合 | 条件 | 95%覆盖时间 | 最后有效覆盖 | 结果 |
|---|---|---:|---:|---|
| A10 | 直接通信适配参考，120sim工程窗 |76.73sim|99.8907%|主要任务/原停止闭合成立；旧插件收尾异常另列 |
| B01 | 真实ns-3 Wi-Fi |未达到|57.4303%|自主87.57sim后heartbeat故障，两SendGoal未交付/未决，原停止所有权认证FAIL |

这些是单图开发实验，不是算法统计优势。B原始物理低速/新零、三Nav2暂停与Gazebo正常退出有证据，不能据此把业务所有权缺失追认为停止认证通过。

完整结果见 [followup04生产报告](followup04/REPORT.md)、[独立评审](followup04/INDEPENDENT_REVIEW.md)、[全部账本](followup04/RUN_LEDGER.json)。固定生产交付为`f59bb8c21c83dce039b3f6e773e7d1599958eebd`，独审提交为`24ed61500985f55a99b6ed4f406641771c8a1e61`。

## 2026-11-10 时间同步论文评估

随后按用户授权完成了[三项方法的实际隔离小试与独立审查](experiments/paper_methods/REPORT.md)：共享时钟降低读取开销；真实ns-3 Wi-Fi TCP恢复了UDP丢失的两笔合成请求；源时间调度消除位置提前生效，但迟到拒绝保留旧位置。共3个clock配对case、4个native回合，无新Gazebo/ROS/Nav2或生产替换，NET-01仍BLOCKED。这些结果不是完整论文复现或Gazebo性能提升。

已全文研读用户提供的五篇、共62个PDF页，并核关键图表及作者公开源码。详细比较见 [文献评估报告](research/time-sync/REVIEW.md)，版本/页码/来源见 [论文索引](research/time-sync/PAPERS.json)。

当前选择保留真实Step/ACK/有限credit骨架；DUSC的位置时间依赖、MUNILS/CORNET的网络隔离值得借鉴。没有证据支持立即整体更换，更没有证据表明换clock就能修复一次UDP Goal丢失后无限等待。下一最小修复仍是可靠Action交付、中央捕获等待和原停止所有权闭合。

用户随后补充的`rbccps-iisc/CORNET`为现代Flagship，已新增[专项源码评估](research/time-sync/CORNET_FLAGSHIP_ADDENDUM.md)。它确有Humble/Classic与真实ns-3 Wi-Fi代码，不能沿用2.0的Mininet-only结论；目前静态仍有CLI、TUN/TAP和clock/业务接线缺口。已列入待验证候选，未运行或更换生产系统。

本次只新增评估与入口文档，未运行新实验、安装论文环境、训练或修改生产实现。五篇论文均未在本次获得“复现成功”结论。原论文PDF及第三方源码研读副本保留本机，不随本仓库发布。

该评估不启动NET-02，不改变原失败和冻结tag。Git独立分支用于交接当前研究状态；新机器仍需按原环境说明恢复Gazebo/rootfs，不能把CPU回放当真实联合运行。

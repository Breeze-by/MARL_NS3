# A1-04：T95 后任务超时的独立小证据审查

**现有证据能确认一次真实高层 navigation timeout、对应 Nav2 原始 CANCELED=5、长时段平移很少及局部进展/恢复失败候选，最终 UUID 与物理停止闭合；仍不能确认地图/规划/控制中的唯一原因。它不是 Nav2 原生 ABORTED=6，也不能解释本例已在此前达到的 T95。**

本次先只读已关闭 `corr6201-step-timing-plain-a1-04` 的 canonical小结果、UUID摘要、final observed-stop、既有RESULT/补充退出proof及必要冻结源码；本次增量仅读主TUI一次提取的 [A1-TOKEN4-HANDOFF.json](prior-pair/A1-TOKEN4-HANDOFF.json)。followup04目录已存在；仅写本文。不重读原大journal/bag/Gateway/native ledger，不运行ROS/Gazebo/模型/测试，不修改生产源。

## 已证事实与时钟

来源：[metrics.small-result.json](../followup03/gz-analysis/corr6201-step-timing-plain-a1-04/metrics.small-result.json)、[uuid-summary.json](../followup03/gz-analysis/corr6201-step-timing-plain-a1-04/uuid-summary.json)、[原RESULT](../followup03/gz-analysis/corr6201-step-timing-plain-a1-04/RESULT.md)。运行源码为bc18d59…，A1是本地ordered Gateway业务路径，不是直接ROS A0，也不是ns-3无线业务样本。

| 项目 | 原值/证据含义 |
|---|---|
| 自主窗口 | G18.49—G198.49，180sim；预算结束，非自然完成。 |
| T95 | 原quality/raw均为elapsed62.01sim，receipt **G80.50**。 |
| 待审Goal | tb3 token4，UUID `21c7d47c52c44e29a2ae6e819d997169`，目标merge_map约(-4.025,-4.925)。 |
| 开始/接受 | handoff原行33059/33061记录reservation/request G85；33068记录accepted response G85.46，UUID吻合，均晚于T95。 |
| 原生终态 | UUID状态历史2→3→5，final_raw_status=5；canonical logical `goal_terminal` 于 **G180.46** 为aborted。 |
| 任务层 | tb3有1次timeout_cancel_dispatched、1次timeout_terminal_failure，high_level_failure_count=1；不是将失败记0。 |
| 另一取消 | token5 UUID `5b8f8e4e9dd3444a9e935c93688a6e63` 原2→3→5，分类为budget-stop；无主任务canonical logical terminal，不能与token4 timeout混为一个原因。 |
| 全部UUID | tb1/tb2/tb3 owned=3/4/5，共12；10原SUCCEEDED(4)、2原CANCELED(5)，未终结为空，未见原Nav2 status6。 |

token4从原G85到logical terminal G180.46为95.46sim，接受到终态约95sim；这包括任务计龄、检查/派发取消和终态传递，**不是已测“机器人连续95秒不动”或“取消RPC耗时95秒”**。它在T95之后才开始，所以不得用其后超时解释A1-04的62.01sim T95，或证明B的34.25sim来自更好无线。它仍是后续任务可靠性限制，不能因覆盖已达95%而删除。

## 状态分类与生命周期源码符合哪些事实

[allocation.py](../../workspace/src/multi_robot_exploration/multi_robot_exploration/allocation.py) 235–241在`now-started > task_timeout_s`时标记cancel_required；461–464的started来自原reservation，不从Nav2接受后重置。[ros_policy.py](../../workspace/rl01/ros_policy.py) 157–167对已标记的目标调用原cancel_goal_async并记录timeout原因；180–200在本token仍owned、存在自身timeout标记且收到原status5时，保存`nav2_terminal_classified(raw5, high-level aborted, navigation_timeout)`，再按高层失败释放状态/排除失败目标。

因此，**原始CANCELED与高层aborted是不同层且可同时真实成立**。在原90sim任务上限和离散决策/派发链下，95.46sim总跨度不自动构成新的生命周期bug；需要原cancel_required、dispatch、响应与result时刻才能判断超时标记到取消完成是否有额外异常。不能直接拿95.46减90，把余量全归Gateway、网络或Nav2。

canonical robot_metrics中tb3的主窗口3成功、raw canceled1，与任务层3成功+高层aborted1并存；第5个owned UUID在预算收尾取消，因此不能把主窗4个logical terminal与最终5个owned机械相等，也不能写为5全成功。

## 停止与资源证据能证明什么

[final-observed-stop.json](../followup03/gz-analysis/corr6201-step-timing-plain-a1-04/final-observed-stop.json) 在G201.2保存原停稳证书：合格窗口推进.8sim、三机消费零目标、authority_stopped/ownership_closed/lifecycle_pause_healthy=true、rpc_errors为空、三机约5.7–6.0e-5m/s线速及4.1–5.2e-5rad/s角速。它支持最终物理停止和原PAUSE链，**不单独认证token4发生取消时正处于运动中，也不证明其整段导航一直健康**。

该stop时tb3的位置已经可能受后继token5及最终停止影响，不能拿它直接量化token4终态前距原目标多远。原host0/55PID清单曾漏本case ROS CLI daemon；[post-daemon-exit-proof.json](../followup03/gz-analysis/corr6201-step-timing-plain-a1-04/post-daemon-exit-proof.json)补充56个known PID全部gone、精确daemon清理及六端点释放。daemon为非子进程，exitcode未知，不改写为exit0；停后helper新接线也不能追记为本bc18整回合已跑版本。

## 主TUI一次 handoff 已补足的实证

| 环节 | handoff原记录 | 能说明的范围 |
|---|---|---|
| 实际Goal | token4 G85，map Goal=(-5.125,-4.125)，原UUID一致 | 与merge_map目标分开保留；不是重造目标或混合坐标。 |
| 中央反馈 | **17556条**，G85.46→G180.46；remaining首/最小0.2345215678，末五条均3.7385022640 | 证明该token中央回调持续有数据；不能证明每条状态新鲜、路径在更新或机器人已接近新目标。特别是首个短remaining可能尚沿用旧BT/plan缓存，不能据它宣布新Goal曾接近成功，也未证明消息UUID串线。 |
| 超时标记 | 原行63527，cancel_required G175.48，reason=task_timeout | 原reservation后90.48sim才记录标记，仍不能当作90.48秒纯导航执行或物理不动。 |
| 取消派发与终态 | 原行64824，timeout_cancel_dispatched G180；64841—64843，raw5/classified aborted/terminal G180.46 | 标记→派发相差所记录4.52sim，符合需要区分的离散派发阶段；派发→raw result的原epoch wall_ns差约63.047ms。没有专门CancelResponse / 服务端GetResult时刻，后者仍缺测，不能把G差0.46当成精确RMW取消延迟。 |
| 独立status观察 | supervisor中本UUID G180.44为3、G180.46为5 | 与raw CANCELED链相符；不补造CancelResponse ACK。 |
| 后继Goal | token5 G185 reserved/request、G185.45 accepted；supervisor G198.49为3、G198.51为5 | 确认高层超时后真实再分配，另一次raw5属于预算收尾；不是同一超时反复上报。 |

同handoff已提取的轨迹分段显示，G85—95、95—120、120—150、150—180.46的采样路径约 **1.02 / 3.22 / 2.74 / 2.70mm**；最后一段实际末样本G180.4，不是恰好180.46。它支持这一长窗**几乎没有平移进展**，而不是只有反馈缺失。`low_translation_sim_s`是原提取阈值/采样估计；它不等于连续精确静止，也不排除旋转、微动或中间未采样运动。

Observer按UUID抽取的1900条decimated feedback中，位置首约(-1.52884,-3.77141)、末约(-1.53934,-3.77161)，也显示位置变化很小。位置字段未完整保留原current_pose header/source stamp；它和世界评价轨迹的frame、采样时刻不同，不能直接与merge_map目标混减，或用小差值认定TF有错。cached remaining与实际位移的差异是要保留的解释风险，不将其洗成“曾到目标又走远”。

## 现在可定位到的导航候选与仍未排除的风险

handoff原Nav2文字在同robot/近似时间窗内反复出现 `Failed to make progress`、follow_path `Aborting handle`，另有local costmap清理服务超时、`Collision Ahead - Exiting DriveOnHeading/Spin`及backup/spin失败。它们支持**局部跟随进展不足且恢复受阻**这个责任段，比“只是等反馈或没收到终态”更具体；内部follow_path abort不是外层NavigateToPose raw6，collision-ahead是预测/代价图判断，不是物理碰撞证书。文字缺Goal UUID，所列G由原wall/sim线性插值估算，不能强唯一绑定或当精确同sim时点。

原行11823还保留 `Failed to get result for follow_path in node halt!`，随后同节点记录取消，外层原UUID确实raw5闭合。**外层UUID/最终停稳成立不独立证明BT内部每个子Action的GetResult都正常完成**；这个内部halt错误不能因总体PASS而删除，也不能单凭它宣布整条取消链失败。

仍缺：`number_of_recoveries`、`navigation_time`（原JSON回调未保存）；专用CancelResponse / 服务端GetResult边界；当时global/local costmap及各层贡献、实际路径/速度命令和相同source-time TF。因而尚不能唯一分辨真实障碍或peer mask、残影/地图成本、局部控制旋转/可行轨迹不足、执行调度或状态缓存的组合。当前是A1本地业务，不为这些候选错误贴RF唯一原因，也没有依据改90sim任务规则、Nav2参数、冻结目标选择或训练。

**更新后的结论范围：** timeout身份/分类、持续反馈、长窗低平移、后续真实再分配和最终闭合均有证据；局部进展/恢复候选比原先更具体，但根因和完整内部取消时序未闭合。post-T95时间先后结论不变。无需为了这些已存事实重复读取原大件或追加测试。

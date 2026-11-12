# 旧bc18单对分析：先看输入、分工与执行，超时单列

本次仅一次提取封存allocation/events/trajectories/launch，未读bag/大Gateway/PCAP、未重跑canonical/模型/仿真。后续计算只读已导出的A1-extract/B-extract缓存；索引行号/原wall_ns保留，缺测不填。详见prior-pair/SUMMARY.json和A1-TOKEN4-HANDOFF.json；独审A1_TIMEOUT_REVIEW.md、PROTOCOL_REVIEW.md已复用。

B原T95=34.25sim，A1=62.01，差27.76。按照各自T0至质量有效T95、真实client request/response/result占有区间：首Goal前分别4.06/6.51，差2.45；首Goal后持续至少一个Goal已派发为30.19/55.50，差25.31。进一步“已派发但尚无accepted”分别.37/.40，其差.03；至少一个accepted占有分别29.82/55.10，差25.28。这是时间账，不是因果CPU/RF分摊；accepted也不等于物理运动。

首次决策已经不是同观察：B G20、地图source stamp17.758、6候选、choices[0,4,5]；A1 G25、stamp22.87、5候选、choices[0,3,4]。两者tb1首目标相同，tb2/tb3首目标已稍异；候选索引也非同语义标签，不能直接比较数值动作号当策略变化。更明显分工差在tb3第二目标：B G30发往(-.475,-4.575)，G49.03完成；A1 G35先往(4.125,-2.225)，G52.16完成，G55才往(-.625,-4.625)，G84.48完成。B T95在G50.19、A1在G80.5，与南侧区域观测时序相符；不证明该单因素唯一造成覆盖差，原地图生成/共享/接收、初始门控及反馈都可能参与。

T95前三机实际Gazebo采样路径B约5.000/4.498/4.461m，A1约8.617/7.973/9.656m。不同窗长、路线与合作分工有真实依据，不能把25.31sim都称为排队等待或无线延迟。初始正确自由覆盖B11.0683%、A111.1325%虽相近，也不等于首次NN输入/条件mask相同。固定权重/seed不保证相同观察与轨迹。

A1 postT95 token4 G85 reservation/request、实际接受G85.46；cancel_required G175.48，timeout_cancel_dispatched逻辑stamp180，实际GetResult callback/raw5及高层aborted G180.46，后继token5 G185请求、185.45接受。cancel dispatch事件携带缓存决策sim，不能把180→180.46当精确服务时延；选定JSON没有CancelResponse独立收件/完整GetResult发送点，保留UNMEASURED。原wall_ns原值在handoff中可独立核实，不混不同层逻辑时间。

token4中央feedback17556条，G85.46—180.46；remaining首/最小.234522、末3.738502，后段恒定。首短remaining不证明当前新目标真已接近（其反馈/路径状态语义未细分）。R域Observer每10条抽样的current_pose另存，有采样口径，不冒充每条真实反馈。number_of_recoveries/navigation_time未由现JSON回调保存，本次未为此打开bag或新加探针。

物理轨迹G85—180.4总采样路径约.00968m，平移很小且有转动；原tb3日志在近似G95.50起多次Failed to make progress/FollowPath内部Aborting handle，近似G95.52有local costmap clear服务超时，近似G118.15有Collision Ahead/backup failed。这些是控制/恢复环节异常的证据，内部FollowPath abort不等于顶层NavigateToPose status6，也不证明发生物理碰撞。无UUID的机器人+wall日志仅上下文；日志G由已存wall/sim样本线性近似映射，不能当精确ROS事件时间。

有据假设：T95前主要差异与早期候选/任务分工/路线/实际观测时序共同演化有关；postT95另有长时间无平移、局部控制/恢复失败，最终原90sim任务规则正确取消并高层失败闭合。没有足够证据唯一指认无线、同伴mask、Nav2某参数或策略缺陷，所以不盲修冻结组件/超时/门槛，下一步同一修补执行版本做固定顺序3对重复，完整保留这些合法任务失败。

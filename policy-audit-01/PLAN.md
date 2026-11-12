# 固定PPO的选择权与贡献离线审计

起点 `8914bf720b6e6141ac29d258c4de0b967b08a07c`；独立分支 `policy-audit-01/choice-authority`。本轮不启动ROS/Gazebo/机器人，不训练、不更改权重或冻结合同，不改历史证据。

## 数据与源码边界

六个NET-01E followup04 `event-cache/corr*.json` 共212次实际NN调用、64个新Goal。212个原始NPZ全部可用，包含701输入、实际logits/value、slots、条件mask和收到的地图。cache的候选是过滤后候选，不是原始Frontier。原封闭allocation journal保留完整observation（仅栅格cells另存NPZ），可补齐传统评分、基础action_mask、冲突和历史。

- `workspace/src/multi_robot_exploration/multi_robot_exploration/allocation.py::Allocator.get_observation`：原Frontier、可达性、历史/已占用/局部地图、去重与每机5候选上限；`TraditionalPolicy.select`：原组大小/距离评分及成功点否决；`Allocator.apply`：原子验收/预留。
- 同目录 `joint.py::candidate_mask/_base_slot_mask/slot_mask`：前缀冲突、忙碌KEEP、无合法候选WAIT、最大可行分配数量规则；`JointTraditionalPolicy.select`保留传统排序。
- 同目录 `ppo.py::encode/ActorCritic.act`：701浮点输入、三17-slot logits，按tb1/tb2/tb3顺序条件masked argmax。
- `workspace/gz01/headquarters.py::PolicyTrace.select/allocate_common`：实际模型→原动作→共同apply→Nav2；`workspace/rl04/ros_headquarters.py`：权重装载与实际Action追踪。

## 有界离线方法

1. 一次提取六个原关闭journal的完整决策，按cache行号/决策号配对；不读取bag、PCAP或网络大ledger。原NPZ只读。
2. 逐212观察由原encode+固定checkpoint+原act回放，核701输入、logits/value、mask/slots/动作及64Goal的预留/实际共享图目标。若缺输入或动作不吻合，停止对应反事实比较并如实记录，不伪造观察。
3. 原始Frontier层级由保存的收到地图、实际位姿和原frontier函数离线重建（原膨胀、组≥3；不是运行时直接记录），区别过滤后保留候选、单机action_mask、顺序冲突后、最大参与规则后选项。不会将重建组数称作实际可选Goal数。
4. 每联合决策枚举合法联合动作叶，统计唯一联合解/多解；每机器人分别统计忙碌KEEP、无任务WAIT、唯一候选、多选；新Goal单列64母数，不能用全时KEEP稀释分配决策。原PPO前缀各行mask仅用于事实计数。
5. 同一冻结观察比较实际训练PPO、原JointTraditionalPolicy、固定最低slot（等价常数零logits）、单个固定种子的均匀随机消融。每种策略依自己的已选前缀重新调用原slot_mask，并检查全联合叶合法性。离线比较只证动作差异，不证反事实轨迹或覆盖提升。
6. 如本地存在明确绑定的初始化checkpoint，按同输入/合同补充离线输出对照；不初始化新模型冒充历史初始权重。复核既有公平Gazebo比较的条件和结论，缺证时明确“不足以证明PPO学得更好”。

交付可审脚本、逐决策/逐机器人/逐Goal表、反事实动作、汇总和通俗报告。后续任何新真实对照仅提出具体有界方案，交Root审后决定，不自动执行。

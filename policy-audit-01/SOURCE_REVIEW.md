# 冻结策略的选择权：独立源码审查

审查对象为本次指定的 `8914bf7` 基线对应当前源码。这里只记录源码事实和推论边界；未运行模型、统计六例缓存、重做同输入对照或改动生产代码。源码路径均相对仓库根目录，行号对应本次读取。

PPO执行的是真实神经网络排名，但其任务是**在强规则预筛后的有限候选和联合合法分支中选目标**。候选生成、可达性、派工人数优先和忙碌任务保护已经由规则决定。源码不能单独证明剩余选择权在实际运行中有多大，也不能证明学习后的排名优于传统、常数或随机排名。

## 候选生成已有较强的规则约束

- `workspace/src/multi_robot_exploration/multi_robot_exploration/allocation.py:243–350`：从接收的共享地图生成 Frontier，结合机器人自身导航网格、路径预算、历史失败/成功目标、已有任务、idle body 和 peer 条件过滤；部分不可直接到达的共享前沿可转换成规则生成的 approach 目标。模型不能直接生成任意坐标。
- 同文件 `:352–367`：目标取合格格点中靠近该组中心的点；`traditional_score = len(cells)/(distance+1e-6)`，其中 distance 是机器人格点到该组中心的格点欧氏距离，不是 `path_cost_estimate_m`。
- **准确的去重和截断顺序**在 `:377–383`：先按 `traditional_score` 降序遍历，每个位置与已保留点距离不小于 0.2m 才进入 `unique`；然后只取这些点的原 index 集合，回到 `raw` 的原顺序筛出它们，最后 `[:5]`。因此是“score 优先去重后，按原序保留最多5个”，不能写成“按 score 直接取最高5个”。approach 模式此前的组顺序来自按组大小降序（`:270–272`）。
- 同文件 `:384–405`：重新编号，动作 mask 要求候选归属本机器人、有效且机器人 idle；另记录端点冲突和启用条件下的首次路线冲突。三机最多15个候选；某机不能直接认领另一机的候选 index。

## KEEP、WAIT、最大参与规则和 prefix

`workspace/src/multi_robot_exploration/multi_robot_exploration/joint.py:32–47` 明确：非 idle 机器人只能 KEEP；非当前 trigger 的 idle 机器人只能 WAIT；正常参与的 idle 机器人有合法目标时不允许 WAIT，无合法目标时才允许 WAIT。PPO没有“明知有工作但主动等待”或“取消/替换忙碌任务”的动作自由度。超时取消由 allocator 的 `tick` 独立触发（`allocation.py:235–241`），不是模型选择。

`joint.py:10–29` 根据此前机器人已选的合法候选建立 reservation，过滤距离和 candidate conflict；所以后续头的合法集合依赖此前 prefix。`joint.py:50–66` 的 `maximum-participation-v1` 继续递归检查后续机器人，仅保留可达到最大新派工人数的当前候选。它是**在NN排名之前实施的强预过滤规则**，不是NN自己学会的协作目标；它不使用 `traditional_score` 决定同等参与人数分支的胜者。这里最大化的是已有基础规则允许的顺序派工集合；由于基础规则有工作就不能 WAIT，不能描述成允许任意机器人主动让位的无约束全局优化。

## NN实际在哪里做选择

`workspace/src/multi_robot_exploration/multi_robot_exploration/ppo.py:58–92`：两层 Tanh trunk 产生3×17 actor logits，一次 forward 后按机器人顺序构造 `slot_mask(observation,row,prefix)`，把非法 logits 置为负无穷，再 deterministic argmax 或 sample。后续头的 logits 不因 prefix 重新计算，变化的是 mask。若剩余多个合法候选，NN分数决定所选分支；若只剩一个，该头不再有目标选择权。

`workspace/gz01/headquarters.py:50–53` 的真实RL入口调用原模型 `act(..., deterministic=True)`。`:75–91` 的 `raw_choices` 实际等于该次**已掩码**动作，不能把它当作未加掩码 logits 的逐头 argmax。未掩码的输出另外保存在 `raw_logits`（`:63–68`）。

必须区分以下计数口径：

- `conditional_options` 是沿本次实际 prefix、在当前头选择前的合法数；不是选中动作的一位 one-hot，也不是三个相互独立的初始选择数。`original_conditional_masks` 同样用了实际 prefix，只是尚未施加最大参与预过滤（`:83–91`）。
- 后两头只剩1，不足以证明整次联合动作唯一。若本次三头条件合法数**全部为1**，该状态在现行规则下确实只有这一条联合路径；不能反过来宣称仍有自由选择。
- 若任一头大于1，至少存在该处分支；但不能把实际路径上的三个计数相乘当成全体合法联合动作数，因为换一个前缀可能改变后续分支数。

## 传统对照共享什么、不同在哪里

`workspace/gz01/headquarters.py:128–129` 为 traditional 臂使用 `JointTraditionalPolicy`，两臂共用 `allocate_common` 的 observation、allocator 和 Nav2路径（`:176–220`）。`joint.py:77–105` 的联合传统策略逐头调用同一个最大参与 `slot_mask`，再把被排除的候选标成不符合传统资格，最后调用原 `TraditionalPolicy`。原传统排名是最大 `traditional_score`，保留末次成功目标的事后 veto（`allocation.py:124–146`）。因此共有安全/候选/联合约束，并不代表共有最终排名算法；基础 `TraditionalPolicy` 单独调用也不等于这里的联合传统基线。

## apply与Nav2没有把NN动作换成规则目标

`allocation.py:411–467` 检查 snapshot、任务所有权和联合 mask。选中候选通过检查时直接使用其 `position` 预留任务；不通过则记录/返回拒绝，没有另挑传统最高分或其他候选的回退分支。`headquarters.py:200–215` 将同一个 action 交给 apply，RL有拒绝时抛错，随后只提交 apply 返回的原目标。

`workspace/src/multi_robot_exploration/multi_robot_exploration/control.py:192–208` 将所选 merge_map 点变换到对应机器人 map，做原端点检查后发送 NavigateToPose；服务器、对齐或端点失败会结束该任务，不替换为另一个规则目标。Nav2仍负责路径规划和底盘控制，这些不是PPO动作输出。

## 同状态离线对照的公平边界

正确比较应对同一个完整 observation 分别调用冻结模型 `model.act(observation, deterministic=True)` 和 `JointTraditionalPolicy().select(observation)`。常数/随机对照也必须按各自选择产生的 prefix 逐头使用真实 `slot_mask`，不能复用PPO已经走过路径上的 mask，不能用忽略联合规则的 `TestPolicy` 替代。常数策略须说明固定的是合法槽位排名还是其他规则；逐头均匀随机合法选择须称为“条件均匀”，不等同于所有联合动作均匀。

701编码相同不自动意味着完整合法集合相同：`ppo.py:18–55` 的编码未涵盖全部 trigger、candidate conflict、idle guard 等 mask 输入。应保留完整 observation/相关约束，且不让一个策略 apply 后的 allocator状态污染另一个策略输入。

本审查可证明当前接口存在真实NN排名及强规则限制，不能凭源码判断六例中多少决策被完全强制、多少NN选择区别于传统，不能从输出不同直接推导探索收益、RL贡献率或因果优越性。这些属于主生产者的缓存计数和同状态离线对照证据，本审查没有重复执行。

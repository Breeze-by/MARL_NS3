# 当前中央PPO网络：科研示意图与维度说明

对应固定 `MR3-RL-POLICY-v1.1.0 / checkpoint-00512.pt`。图根据实际源码和checkpoint张量形状绘制，不是拟议架构。两图各提供300 dpi PNG、可编辑文字/图元的SVG、矢量PDF。SVG使用Noto CJK字体；PDF已嵌入字形。

|图|说明|文件|
|---|---|---|
|1|输入组成、共享网络层、Actor/Critic维度、条件动作约束及Nav2输出|[PNG](01-network-architecture.png) · [SVG](01-network-architecture.svg) · [PDF](01-network-architecture.pdf)|
|2|历史PPO训练、联合采样、rollout、GAE与损失、当前冻结部署流程|[PNG](02-training-and-deployment.png) · [SVG](02-training-and-deployment.svg) · [PDF](02-training-and-deployment.pdf)|

## 网络层和张量

`B`是批量大小；实际单次中央决策为`B=1`。

|模块|实现|输出形状|参数数（含bias）|
|---|---|---|---:|
|输入|Float32拼接向量|`[B,701]`|0|
|共享隐藏层1|`Linear(701,128) + Tanh`|`[B,128]`|89,856|
|共享隐藏层2|`Linear(128,128) + Tanh`|`[B,128]`|16,512|
|Actor头|`Linear(128,51)`；reshape|`[B,51] → [B,3,17]`|6,579|
|Critic头|`Linear(128,1)`；squeeze最后一维|`[B,1] → [B]`|129|
|合计|||113,076|

准确的层数表述：**两层共享隐藏层，之后分为一个Actor线性输出头和一个Critic线性输出头**。沿任一输出路径均为3个Linear层；不能把两个并行头说成第三、第四个串行隐藏层。没有CNN、卷积池化、注意力、RNN、GNN、target network或三套独立Actor。Actor的51项输出是一个线性层，按三机分组解释。

## 701维观察的真实顺序

以1起始的维度区间：地图1–512；机器人513–551；候选552–701。源码中的数组下标相应从0开始。

### 地图：512维

共享收到的占据图先投影到固定ROI `(-5.8,-5.6,7.25,5.3)`，以0.05 m采样，得到218行×261列栅格。超出收到地图的区域保留unknown。然后使用`array_split`分为16×16块，分别计算：

1. 已知比例：`cells >= 0`，共256维；
2. 完全占据比例：`cells == 100`，共256维。

两个通道按上述顺序逐块展开。这里是确定性的区块比例计算，**不是CNN提取特征**，也不是简单把真值地图缩成16×16。地图块大小不必完全相等。

### 机器人：3×13=39维

按照tb1、tb2、tb3顺序，每台机器人下列13项依次排列：

|机内位置|特征|编码|
|---|---|---|
|1–2|当前位置x、y|`x/20, y/20`|
|3–4|航向|`sin(yaw), cos(yaw)`|
|5–7|速度三个分量|`vx/0.26, vy/0.26, omega`|
|8–10|任务状态标志|`is_idle, is_pending, is_active`|
|11–12|当前任务相对目标|`(target_x-x)/20, (target_y-y)/20`；无目标为0|
|13|当前目标持续时间|`min(duration,500)/500`；无持续时间为0|

这些是冻结的确定性比例缩放，没有在线更新均值/方差的归一化器。速度是输入状态，**不是策略输出**。

### 候选：15×10=150维

候选沿实际候选列表顺序编码，每个10项；不足15个的槽整组补零。每台机器人最多保留5个自有候选；某台不能任意挑另一台的候选。

|候选内位置|特征|编码|
|---|---|---|
|1|该候选存在|`1`，padding为0|
|2–3|候选位置x、y|`x/20, y/20`|
|4|估计路径代价|`path_cost_estimate_m/20`|
|5|观测信息增益代理|`information_gain_proxy_m2/10`|
|6|候选有效|`valid`|
|7|候选可达|`reachable`|
|8–10|机器人归属|tb1/tb2/tb3三个one-hot标志|

候选由Frontier及approach规则产生。历史传统评分会影响候选去重；在剩余合法目标中的最终排名由PPO logits决定。不能把候选生成和安全规则的全部效果算作PPO学习收益。

## 动作和额外规则输入

每个机器人头的17槽为：候选索引0–14、KEEP槽15、WAIT槽16。内部动作将KEEP解释为−1、WAIT解释为−2；联合动作是3个离散选择，**不是51个目标，更不是51个速度**。

推理先一次forward计算三组logits，然后按tb1→tb2→tb3构造条件mask；后续mask依赖前机选择。mask并非另一个可学习网络，也不能画成三个互不相干的独立选择。它还依赖完整观察中的任务状态、候选冲突、归属、可达性及最大参与规则；这些完整规则数据不全都包含于701维向量。网络输入有部分有效性标志，不等于完整mask已经全部编码进网络。

当前部署采用masked argmax；训练采用条件Categorical采样。KEEP保护已有任务，WAIT只在当前规则允许时出现；不允许网络任意取消正常导航任务或输出底盘速度。候选索引经原验收、坐标变换、NavigateToPose Action交给Nav2。Critic在当前`forward`中也计算，但其值不用于部署时决定目标，不是目标成功概率。

## 训练与部署的区别

图2对应当前权重的RL04追加训练配置：继承已训练权重；rollout256、minibatch128、4epochs、Adam学习率0.0003、gamma0.99、GAE lambda0.95、PPO clip0.2、value coefficient0.5、entropy coefficient0.01、梯度范数上限0.5。PPO联合log-prob为三机条件log-prob之和；重算时使用实际采样时的mask。

训练调用二维`KinematicBackend`及统一环境合同；当前Gazebo/ROS 2运行是固定模型的推理与导航验证，**不是已经建立了Gazebo在线PPO训练系统**。训练环境中的地图真值可用于生成传感器观测/独立评价，但不直接作为Policy观察。当前通信研究不训练或更换固定网络。

图中表示实际结构，不表示已经证明PPO稳定优于传统算法；选择作用与性能收益的独立审计见[policy-audit-01报告](../../../policy-audit-01/REPORT.md)。

## 源码依据与重绘

- [ppo.py](../../../workspace/src/multi_robot_exploration/multi_robot_exploration/ppo.py)：`encode`、`ActorCritic`、条件采样、GAE、PPO损失。
- [observations.py](../../../workspace/src/multi_robot_exploration/multi_robot_exploration/observations.py)：固定ROI和0.05 m接收地图投影。
- [joint.py](../../../workspace/src/multi_robot_exploration/multi_robot_exploration/joint.py)：条件mask、KEEP/WAIT、最大参与规则。
- [rl_env.py](../../../workspace/src/multi_robot_exploration/multi_robot_exploration/rl_env.py)：实际奖励组成。
- [train-config.json](../../../workspace/rl04/train-config.json)、[train.py](../../../workspace/rl04/train.py)：当前权重对应训练配置和采样/更新过程。
- [execution.py](../../../workspace/rl02/execution.py)、[diagnose.py](../../../workspace/rl02/diagnose.py)：统一Episode和实际训练后端。

本次读取实际checkpoint的8个权重/bias张量，其维度与上表一致，总参数113,076；没有执行模型推理、训练、ROS、Gazebo或网络实验。制图工具只依赖已有Matplotlib和中文字体，不导入机器人运行模块。

重绘：在仓库根执行 `python3 docs/figures/ppo-policy-v1.1.0/draw_figures.py`。这是生成文档图片，原模型、源码、历史证据不变。

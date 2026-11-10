# MARL_NS3 — MR3-RL-POLICY-v1.1.0

**开发分支状态（2026-11-10）：** 本分支包含NET-01D通信故障审计及有限修复，尚不能作为已通过的Gazebo—ns-3完整平台。机器人、中央RL、Gateway与ns-3之间的全部信息交互、图表、实际收发数据和隔离边界见[当前系统信息交互说明](docs/CURRENT_INFORMATION_FLOW_2026-11-10.md)；本轮结论见[NET-01D报告](net01d/NET01D_FINAL_REPORT.md)。下文保留v1.1.0发布参考说明；冻结标签与main不因本开发分支而改变。

三台 TurtleBot3 使用360°二维雷达与SLAM建图，中央PPO为机器人分配高层探索目标，Nav2负责导航。本版本固定完整探索行为，供后续通信约束实验使用，是**有界 Gazebo 通信研究工程参考版本**。用户授权固定当前76fd行为与6d权重；本仓库不承诺未知地图、任意尺寸场景或实机安全，不将早期RL03全部科学验收追认为PASS。RL只选择高层目标，Nav2保留路径规划、控制与避障。

## Clone 后直接做 CPU 记录重放

不需要ROS、Gazebo或ns-3。已测Python3.10.12、Torch2.12.0+cpu、NumPy1.21.5、SciPy1.8.0，CPU单线程。只加载包内可信checkpoint（Torch pickle格式）。

```bash
git clone git@github.com:Breeze-by/MARL_NS3.git
cd MARL_NS3
git checkout MR3-RL-POLICY-v1.1.0
python3.10 -m venv .venv
. .venv/bin/activate
python -m pip install numpy==1.21.5 scipy==1.8.0
python -m pip install torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu
python tools/replay_cpu.py --output outputs/cpu-replay.json
```

一个进程对三图各自第一份真实ROS观测做3次实际forward：701编码、实际联合mask/slots/动作、原raw logits及标量、已记录目标坐标均匹配；权重未变、无梯度/optimizer/Node/环境step/Action/Gazebo。原结果见[evidence/cpu-replay.json](evidence/cpu-replay.json)。它重放已保存候选/观察，不重建SLAM、Frontier/TF或Nav2物理执行，不是新的Gazebo成功回合。输出已存在时拒绝覆盖。

## 真实 Gazebo 结果与限制

固定76fd/6d、原DWB，rotation_shim=false、peer_timing=false、observer_timing=true；三机各图从同一个紧凑集结区出发，实体不重叠。同图RL/兼容传统共用感知、候选、最大参与、导航、物理、安全与计时。

以下时间单位为Gazebo仿真秒，从各回合自主探索起点t0起算；T90/T95/T98为质量有效覆盖首次达到相应阈值的时间。

| 已暴露地图 | RL T90/T95/T98(sim) | 传统T90/T95/T98 | 末覆盖RL/传统 | 三机成功RL/传统 |
|---|---|---|---|---|
| Corr6201 | 61.8/61.8/93.1 | 66.7/71.1/71.1 | 99.9036/99.8200% | 4/4/4；5/4/4 |
| Rooms6101 | 85.7/90.2/103.5 | 96.9/101.3/140.8 | 99.9027/99.8653% | 4/6/6；6/5/7 |
| Hard4202 | 106.5/106.5/162.6 | 57.8/101.2/105.5 | 99.8412/99.7618% | 7/2/3；5/2/3 |

六回合各600sim，82UUID闭合、81SUCCESS、1次Rooms传统超时失败，原停止/三pause/完整性通过。RL在两图95较快、Hard较慢；Corr98及全期路程也有反例，不称全面稳定领先。三个布局已暴露，Hard还属于历史训练几何，每臂仅一次。覆盖是quality有效correct-free，不等于地图完全准确；precision、false-free、路程/失败/图表见[证据索引](docs/EVIDENCE_INDEX.md)。

自然探索终态仍None，所有回合预算退出，不能将全WAIT/高覆盖当自然完成。历史偶发publisher间隙未唯一定位；可选peer_timing重复SIGINT归档缺陷仍存在，本profile关闭该附加诊断。旧失败原样保留，既有严格NOT READY结论是其历史作用域；本次授权只固定有界工程参考，不是实机或后续网络实验自动准入。

## 冻结的范围

- 6d checkpoint、701编码/归一化、ROI **[-5.8,-5.6,7.25,5.3]**、.05m格、tb1/tb2/tb3顺序。
- 原候选构造/历史排除/本地可达资格、Navfn边界、peer/自身route排除、最大参与及首次联合路由mask、KEEP/WAIT、生命周期和目标权限。
- 原DWB/SLAM/driver与明确profile配置、安全时效/停止语义，完整[行为合同](docs/BEHAVIOR_CONTRACT.md)及[RELEASE_MANIFEST.json](RELEASE_MANIFEST.json)绑定源码。

同6d不等于旧v1.0.0合同：旧9c的候选/联合动作/执行规则不同。v1.0.0本地历史tag不覆盖；本v1.1.0新独立Git不搬入巨大旧Git历史，文中旧commit是原实验源身份，不保证可在此仓库checkout。

## 源码、环境与研究路线

`workspace/src`含ROS包、完整改动diff-drive driver、SLAM/Karto、原robot meshes与逐包许可证；`workspace/rl01..04`保留训练/评估来源；`config/validated`保留六臂实际Nav2/SLAM参数；`policy`只有选中权重，`runs`仅四件原始模型provenance（相对symlink不重复模型）。无rootfs/build/raw bag/demo视频/旧policy_release合同/ns-allinone。

Gazebo历史isolated harness依赖`/project`、bwrap rootfs及原宿主布局，源码原字节保留。**CPU重放可直接运行；新机器Gazebo环境必须重建，未在本次发布中验证。** 不将旧绝对路径wrapper冒充便携入口。构建、取得依赖与未来网络边界见[SETUP](docs/SETUP.md)。修改ROI、候选、mask/生命周期或导航/安全profile须新版本及新的可比基准，不能借通信优化偷偷换目标。下一步理想→受限ns-3→实机Wi-Fi，但本发布没有实现/启动后两者。

根[LICENSE](LICENSE)是主探索组件的原MIT文本，**不覆盖所有子包**。SLAM Toolbox/Karto适用各自LGPL等许可证，driver有BSD许可；逐子包LICENSE和原版权优先，见[NOTICE](NOTICE.md)。

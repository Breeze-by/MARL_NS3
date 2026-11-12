# MARL_NS3：三机器人探索与无线通信研究

当前工程更新于 **2026-11-13**。三台TurtleBot3 Waffle使用LiDAR与SLAM建图，中央固定PPO分配高层探索目标，Nav2负责导航；关键跨端业务可经过真实ns-3 Wi-Fi模型交付。

**`main`表示当前工程；`MR3-RL-POLICY-v1.1.0`标签保留原固定行为参考。** 当前工程已经接入ns-3，不再是“尚未开始RL或网络接入”的早期项目。

## 先看这些

|需要了解什么|入口|
|---|---|
|项目现状、已达到与尚未达到的目标|[当前项目说明](docs/CURRENT_STATUS.md)|
|ROS直取、网关与Wi-Fi的覆盖率、轨迹和表格|[中文图表汇总](docs/communication-comparison-zh/通信方式对比图表汇总.md) · [PDF](docs/communication-comparison-zh/通信方式对比图表汇总.pdf)|
|当前PPO到底是什么网络|[网络结构与逐项维度](docs/figures/ppo-policy-v1.1.0/README.md)|
|PPO是否真的参与选择、是否已证明更好|[实际选择审计](policy-audit-01/REPORT.md)|
|最新六次Gazebo/网络运行的详细结果|[最近实验报告](net01e/followup04/REPORT.md)|
|研究路线与本轮工作边界|[PROJECT.md](PROJECT.md)|
|旧资料在哪里、怎样恢复|[历史归档与远程备份](archive/README.md)|

## 当前结果，按实际范围理解

- 固定模型有真实训练来源，输入701维，两层128维Tanh共享骨干，Actor输出三机各17槽、Critic输出一个价值，共113,076个参数。
- 最近共同版本在Corr6201走廊地图完成本地网关、较好Wi-Fi各三次180仿真秒探索，六次均停稳并正常退出。三机都有实际运动，64个目标中62成功、2次导航中止。
- 网关三次达到95%覆盖为39.46 / 62.25 / 72.01秒；Wi-Fi为35.61 / 40.42 / 48.68秒。达到98%的排序并不一致；这些单场景结果不能解释成Wi-Fi使探索更快或纯无线损失。
- 对真实212次推理的审计发现：64次新目标分配中54次有多个合法选项，与传统选择有38个目标不同。PPO真实影响选择，但尚未证明其在Gazebo稳定优于传统方法。
- 仍是仿真研究平台：通信适配、联合调度和无线成本尚未充分独立分摊，实机等价与部署验证未完成，未启动NET-02优化。

## 代码与数据目录

|目录|当前用途|
|---|---|
|`workspace/`|冻结的机器人、SLAM、Nav2、PPO及训练来源代码；保留原行为，不在通信实验中重训练|
|`net01/`|消息代理、Action传输、ns-3桥接、共同时间与退出管理|
|`net01e/controller/`、`net01e/followup01/`|当前控制器退出适配及生产入口；旧编号是被运行代码引用的内部路径|
|`net01e/followup02/static_footprint_launch.py`|当前共同导航配置启动适配|
|`net01e/followup03/time_control_plugin/`|当前步进观测插件源码；本机已构建插件保留|
|`net01d/health/`及部分旧编号源码|当前仍使用的消息追踪、采样和原生传输依赖，不代表继续旧阶段研究|
|`net01e/followup04/`|最新六例的小型报告、指标、图表、来源绑定与一次提取的分析缓存|
|`policy/`、`config/`、`inputs/`、`assets/`|选定模型、冻结配置、CPU重放输入和机器人/场景资源|
|`docs/`、`policy-audit-01/`|当前中文说明、图表、网络示意图和独立策略审计|
|`evidence/`、`provenance/`|固定版本证据及工程来源、清理记录|
|`archive/`|归档索引；旧大日志和过时试验输出不再混入日常Git目录|

旧源码路径没有为“看起来新”而大规模改名，以免破坏冻结合同、导入关系和实际启动配置。过时实验输出已外置；本地少量旧路径链接仅供读取历史，不应继续往其中写新回合。后续数据请另建`local-runs/`并事先明确配置和预算。

## CPU记录重放

这项重放不需要ROS、Gazebo或ns-3。环境依赖见[SETUP](docs/SETUP.md)和[requirements-cpu.txt](requirements-cpu.txt)。

```bash
git clone --single-branch --branch main git@github.com:Breeze-by/MARL_NS3.git
cd MARL_NS3
python3 tools/replay_cpu.py --output outputs/current-cpu-replay.json
```

单分支克隆只取日常main，不额外下载独立备份分支的大分片。重放核对三份已保存观察的输入、模型输出和动作，**不是重新执行Gazebo探索**。输出文件已存在时应使用新名称，不覆盖原件。

## Gazebo与ns-3的本机环境

当前机器的ROS rootfs、原生网络程序、13个共享库、驱动、插件和clock witness均保留，目录见[本机运行环境](docs/LOCAL_ENVIRONMENT.md)。Git克隆不包含这些安装/构建环境，也不包含全部大型原始实验记录。

历史READY/START属于已经结束的具体回合，不是可重复执行的通用启动脚本。新运行需要新配置、独立日志和有界停止；本次整理没有新增Gazebo、训练或网络实验。

原行为边界见[BEHAVIOR_CONTRACT](docs/BEHAVIOR_CONTRACT.md)和原[发布Manifest](RELEASE_MANIFEST.json)。该Manifest描述原v1.1.0发布包，不应拿它核验后来新增文档和网络适配文件。

## 历史和许可证

清理前完整Git历史已上传[独立备份分支](https://github.com/Breeze-by/MARL_NS3/tree/backup/pre-cleanup-20261113)，恢复方法见[归档说明](archive/README.md)，具体改动见[本次整理记录](provenance/cleanup-20261113/README.md)。原始未跟踪数据在本机外置保留，不等于已云端备份。原失败和旧结论没有改写。

根[LICENSE](LICENSE)不覆盖所有子包；SLAM/Karto、机器人驱动及其他组件遵循各自许可证和版权，见[NOTICE](NOTICE.md)。

# MARL_NS3：三机器人探索与无线通信研究

当前工程更新于 **2026-11-15**。三台TurtleBot3 Waffle使用LiDAR与SLAM建图，中央固定PPO分配高层探索目标，Nav2负责导航；关键跨端业务可经过真实ns-3 Wi-Fi模型交付。

**`main`表示当前工程；`MR3-RL-POLICY-v1.1.0`标签保留原固定行为参考。** 当前工程已经接入ns-3，不再是“尚未开始RL或网络接入”的早期项目。

## 先看这些

|需要了解什么|入口|
|---|---|
|项目现状、已达到与尚未达到的目标|[当前项目说明](docs/CURRENT_STATUS.md)|
|代码复审、计时混杂与下一阶段归因验收|[通信因果审查与执行方案](docs/COMMUNICATION_CAUSAL_REVIEW.md)|
|ROS直取、网关与Wi-Fi的覆盖率、轨迹和表格|[中文图表汇总](docs/communication-comparison-zh/通信方式对比图表汇总.md) · [PDF](docs/communication-comparison-zh/通信方式对比图表汇总.pdf)|
|当前PPO到底是什么网络|[网络结构与逐项维度](docs/figures/ppo-policy-v1.1.0/README.md)|
|PPO是否真的参与选择、是否已证明更好|[实际选择审计](policy-audit-01/REPORT.md)|
|独立导航间距试验：两图各3次，4/6达T95，未建议替换默认|[中文短报告](local-runs/clearance-tuning-20261115/REPORT.md)|
|最新ROS wall延时消融：70窗口/78启动与14组统计|[正式报告](local-runs/ros-delay-v3-20261114/REPORT.md) · [统计投影](local-runs/ros-delay-v3-20261114/SUMMARY_STATISTICS.json)|
|两地图四通信条件各五次、最终均值与失败分母|[40窗口/42实际启动报告](local-runs/communication40-v3-20261113/REPORT.md) · [统计CSV](local-runs/communication40-v3-20261113/summary.csv)|
|此前独立探索修复单例、T95与三项新行为范围|[修复基线报告](local-runs/exploration-repair-20261113/REPORT.md) · [审查结论](docs/COMMUNICATION_CAUSAL_REVIEW.md)|
|前一通信合同的三对Wi-Fi重复|[历史六例结果](local-runs/causal-followup-20261113/REPORT.md)|
|此前common58网关/Wi-Fi旧六例|[历史共同版本报告](net01e/followup04/REPORT.md)|
|研究路线与本轮工作边界|[PROJECT.md](PROJECT.md)|
|旧资料在哪里、怎样恢复|[历史归档与远程备份](archive/README.md)|

## 当前结果，按实际范围理解

- **最新ROS wall延时V3：两图×A0校准及D0..D500六代理条件×五次，70个完整120sim窗口全部闭合；55达T95、15明确未达、0缺测。** 实际78次启动含8次零自主窗口startup工程FAIL，原stop/PAUSEFAIL与RAM/raw保留，不写成78例全PASS。走廊按A0/D0/D100/D200/D300/D400/D500达标5/5/5/4/4/4/5，Rooms为4/5/3/4/2/3/2（各分母5）。本批全部无WiFi业务，额外单向延时单位为实际wall-ms；A0→D0只作代理校准，纯delay比较D0..D500。主延时增加但任务结果非逐档单调，不能称无线唯一因果。见[14组均值±样本SD与完整失败分母](local-runs/ros-delay-v3-20261114/REPORT.md)。
- 全部运行共用79-runtime；离线analyzer的[AM3事后测量纠错](local-runs/ros-delay-v3-20261114/METHOD_AMENDMENT03.json)保留f016原BLOCK/UNKNOWN，只修关闭后未准入capture的身份误配，不重跑任务/T95、不混前序V1五/V2二十七。全部仿真与队列已停；59页中文图表PDF/MD已完成渲染验收并交付，入口见[本批报告](local-runs/ros-delay-v3-20261114/REPORT.md#权威来源与交付状态)。
- **此前独立两地图×四通信条件×五次比较已完成：42次真实启动、40个有效120sim窗口，34/40达到中央质量有效T95。** 走廊A0/A1/B/C均5/5；房间为4/5、3/5、4/5、3/5。各图按run等权的wall延时、源观测cohort条件交付率及样本SD见[最终报告](local-runs/communication40-v3-20261113/REPORT.md)。窗口资格40/40，完整工程/clean exit各36/42；4个窗口后退出FAIL与2次零自主窗口启动FAIL单列保留，不能写成42例全PASS。两次仅named successor是显式事后条件统计修订。
- B→C的native服务P95均值在走廊增4.20倍、房间增4.44倍，端到端wall平均延时也增加；任务T95/成功率未呈跨图一致单调恶化，不能把所有差成绩唯一归RF。源cohort条件交付率不是RF丢包率，Rooms A0/A1也仅约86–89%。所有40窗口共用原77-runtime版本，批次后退出小修不追溯改变原FAIL，未做新Gazebo复验。
- 旧v1四个真实例整体列discovery，不混入正式均值；setup a01与v2/GDB诊断另列，原错误和测量勘误保留。实际启动、事后修订和停止记录见[canonical journal](local-runs/communication40-v3-20261113/execution.jsonl)、[最终退出核对](local-runs/communication40-v3-20261113/FINAL_EXECUTION_CHECK.json)。
- v2边界ACK组件通过，但首例b01在预热G2.25发生Gazebo SIGSEGV，继而触发原2s physics RPC保护，HQ未启动。一次独立静止GDB诊断没有复现SIGSEGV；首Step实际4.306wall秒仍触发原2s门，停止/复制原资格未通过，不能称已修复崩溃或获得新的有效样本。原始记录和RAM保留。
- 共同测量已回溯已有R Observer观测cohort的原DDS发布时间至HQ native take，报告wall-ms，前三完整discovery例具备完整追踪落盘证据；这不是全部publisher发送率或生成AoI，也不证明唯一RF因果。
- **此前已接受的er13修复基线仍保留：中央T95=43.17sim秒，local/R为43.15/43.18；相对59.44sim的中央实际样本已覆盖98.978%，不是靠跑到120sim才达标。** 23次forward、16目标全部接受，12成功、1Nav2中止、3预算取消，原运行/停止/网络/节拍门通过；它是独立cohort。
- 这次明确建立新的行为基线：补Nav2节点sim clock、统一圆footprint候选几何、加入原目标NavFn格有效性guard。PPO权重/701结构不变；候选与目标取消触发语义有显式版本变化，不能并入旧RF组算收益。仅一例，guard主动取消本例未触发，未证明每次都达标或导航失败已消除。
- 固定模型有真实训练来源，输入701维，两层128维Tanh共享骨干，Actor输出三机各17槽、Critic输出一个价值，共113,076个参数。
- 此前common58版本在Corr6201走廊地图完成本地网关、较好Wi-Fi各三次180仿真秒探索，六次均停稳并正常退出。三机都有实际运动，64个目标中62成功、2次导航中止。
- 网关三次达到95%覆盖为39.46 / 62.25 / 72.01秒；Wi-Fi为35.61 / 40.42 / 48.68秒。这些单场景结果不能解释成Wi-Fi使探索更快或纯无线损失。
- 对真实212次推理的审计发现：64次新目标分配中54次有多个合法选项，与传统选择有38个目标不同。PPO真实影响选择，但尚未证明其在Gazebo稳定优于传统方法。
- 仍是仿真研究平台：通信适配、联合调度和无线成本尚未充分独立分摊，实机等价与部署验证未完成，未启动NET-02优化。
- 前一通信合同已接通业务时钟、固定G20启动/首决策槽与消费者使用链；其共同合同下按B/L3、L3/B、B/L3完成六例60sim：运行、停止、复制、66个预定槽及6×6000token原时序门限全部通过。中央T95仅L3的h达到38.50sim秒，其余五例预算内未达；B为0/3、L3为1/3，不支持“无线条件变差必然降低任务完成度”的结论。同臂和对内首701/栅格均实测不同，RF唯一因果仍未证实。
- 前一通信task的原a启动FAIL（初始化marker在进入Wi-Fi前被exporter过滤，已最小修复）及原180sim磁盘B时序FAIL永久保留；旧b–f READY退役未运行，修复后六例独立成组，共7次START到顶。当前修复、验证和证据边界见[执行与审查结论](docs/COMMUNICATION_CAUSAL_REVIEW.md)；未训练、未改固定策略/导航，未启动NET-02。

按本次用户要求，后续只使用T95作为任务覆盖完成指标，不再新算或报告T98/AUC；历史原报告保留。达到95%质量有效覆盖可判覆盖任务完成，但不等于控制器自然终止。新的[三视图T95工具](tools/analyze_t95_views.py)分别输出本地最新地图并集、中央网关融合图和R端收到图的T95；用法与验证见[当前执行说明](docs/COMMUNICATION_CAUSAL_REVIEW.md)。

## 代码与数据目录

|目录|当前用途|
|---|---|
|`workspace/`|冻结的机器人、SLAM、Nav2、PPO及训练来源代码；保留原行为，不在通信实验中重训练|
|`net01/`|消息代理、Action传输、ns-3桥接、共同时间与退出管理|
|`net01e/controller/`、`net01e/followup01/`|当前控制器退出适配及生产入口；旧编号是被运行代码引用的内部路径|
|`net01e/followup02/static_footprint_launch.py`|当前共同导航配置启动适配|
|`net01e/followup03/time_control_plugin/`|当前步进观测插件源码；本机已构建插件保留|
|`net01d/health/`及部分旧编号源码|当前仍使用的消息追踪、采样和原生传输依赖，不代表继续旧阶段研究|
|`net01e/followup04/`|历史common58网关/Wi-Fi旧六例报告与缓存|
|`local-runs/causal-followup-20261113/`|前一通信合同六例与原a失败、绑定；保留历史原始结果|
|`local-runs/exploration-repair-20261113/`、`local-runs/er13/`|此前单例修复报告/72路径绑定与短路径实际运行；本机原始结果不随Git完整发布|
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

历史READY/START属于已经结束的具体回合，不是可重复执行的通用启动脚本。新运行需要新配置、独立日志和有界停止。er13修复单例采用独立72路径绑定与120sim上界；前一六例使用67路径、60sim且旧行为，两者及common58/B180/b2/l2、新40例discovery均不混样本。v3已完成独立G0初始化probe及40窗口正式比较：三机实际spawn退出0、同World实体查询后才放行首physics；[probe记录](local-runs/communication40-v3-20261113/PROBE_RESULT.json)保留原GDB绑定检查错误，不能称整例PASS或SIGSEGV根因已修。正式批次全GDB=false，保留原120sim/2s/40wall等共同条件；原c16/c29启动FAIL和RAM保留、c16s/c29s为仅有的显式授权后继。比较结束后仿真全停，没有训练或NET-02优化。

原行为边界见[BEHAVIOR_CONTRACT](docs/BEHAVIOR_CONTRACT.md)和原[发布Manifest](RELEASE_MANIFEST.json)。该Manifest描述原v1.1.0发布包，不应拿它核验后来新增文档和网络适配文件。

## 历史和许可证

清理前完整Git历史已上传[独立备份分支](https://github.com/Breeze-by/MARL_NS3/tree/backup/pre-cleanup-20261113)，恢复方法见[归档说明](archive/README.md)，具体改动见[本次整理记录](provenance/cleanup-20261113/README.md)。原始未跟踪数据在本机外置保留，不等于已云端备份。原失败和旧结论没有改写。

根[LICENSE](LICENSE)不覆盖所有子包；SLAM/Karto、机器人驱动及其他组件遵循各自许可证和版权，见[NOTICE](NOTICE.md)。

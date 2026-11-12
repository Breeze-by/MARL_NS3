# 本机运行环境与目录

这份清单描述已有、实际使用过的环境，不是自动安装器。当前Git克隆包含代码、选定模型、CPU回放输入、最新小型证据和图表；不包含完整ROS根文件系统和全部原始运行记录。

## 当前机器的依赖位置

工作区根为`/home/zhuyulab/ns3-workspace`；当前Git工程实际路径为`net-01d/workspace`，同级`MARL_NS3`是指向它的便捷入口。

|组件|本机位置与用途|
|---|---|
|ROS / Gazebo根环境|`base-01-econ/isolation/rootfs`；Humble与Gazebo Classic既有环境|
|机器人基础安装|`base-01-econ/workspace/install`和`build`；安装内有指向构建库的链接，两者均保留|
|固定机器人与探索源码|当前工程`workspace/`、根`policy/`、`config/`及`assets/`|
|当前ns-3原生库|`net-01d/ns3-lto-portable-followup02/build/lib`；保留实际使用的13个ns-3共享库|
|当前网络程序|`net-01d/ns3-lto-portable-followup02/driver-out`；实际加载身份由原运行绑定记录|
|步进观测插件|当前工程`net01e/followup03/build/step-timing/libnet01_time_control.so`；保留对应源码|
|原步进插件依赖|`net-01/build/time-control-followup04-lifetime/libnet01_time_control.so`|
|时钟观测程序|`net-01/workspace/build/clock-witness-followup04/net01-clock-witness`|
|ns-3.40原源码及ns3-gym|`ns-allinone-3.40/ns-3.40`；不是本轮新增安装|
|完整旧记录与原始数据|`/home/zhuyulab/ns3-workspace-archive/2026-11-13/research-data`；由原路径链接读取|
|Git对象公共库|`net-01/workspace/.git`；当前工程是关联worktree，不能当成旧目录垃圾删除|
|BASE/RL/GZ旧worktree公共库|`base-01-econ/upstream/.git`；仍被旧源码worktree使用，保留|

## 清理没有改变什么

PPO及机器人源码、完整输入输出合同、共享地图/Frontier、SLAM、Nav2、物理参数、共同健康计龄和停止机制均保持。旧编号中的部分文件仍在生产调用链中，所以没有为目录美观而改名或复制另一套实现。

APT下载/索引和确认独立于运行库的CMake中间物可以重新生成；它们不等于现用ELF、共享库、机器人build/install或Git公共对象库。后续重新编译时需要重新执行相应CMake配置，不能假设旧增量缓存还存在。

新回合需要新日志目录和明确配置/预算，不复用已消费的历史READY。`local-runs/`为新的本机输出预留，默认不进Git。原输出路径的链接只用于读取已有证据，不应继续追加试验。

## 可复现范围

- CPU三观察记录重放有包内代码、模型和输入，入口见根README。
- 已有完整Gazebo回合的报告/图表可以直接阅读，原数据通过本机归档读取。
- 新机器仍需重建并绑定ROS/Gazebo/ns-3环境；不能把CPU回放或当前机器的路径清单称为已经验证了全新安装。
- 清理本身不启动机器人、网络实验或训练；它不产生新的探索性能或实机安全结论。

# 环境与运行说明

当前已接入ns-3 Wi-Fi，并完成过三机器人Gazebo完整有界运行；旧发布文档中的“未来再接入ns-3”不再描述当前main。当前状态见[项目说明](CURRENT_STATUS.md)。

## CPU记录重放

Python3.10的已使用依赖为NumPy1.21.5、SciPy1.8.0和PyTorch2.12.0 CPU，见根`requirements-cpu.txt`。只加载本项目可信checkpoint。

```bash
python3 tools/replay_cpu.py --output outputs/current-cpu-replay.json
```

它对包内三份真实观察做前向重放，核对编码、条件mask、logits和动作，不运行ROS、Gazebo、ns-3或训练。输出文件不可覆盖。

## 当前机器上的联合系统

当前环境沿用Ubuntu22.04、ROS 2 Humble、Gazebo Classic11.10.2和已有ns-3.40。打包SLAM、nav2_bringup与已安装Nav2子包的版本不是一个统一版本号，具体原始来源见`provenance/historical-dependency-inventory.json`及各包package.xml。

[本机环境清单](LOCAL_ENVIRONMENT.md)列明rootfs、机器人build/install、native程序和13个库、插件与clock witness。它们已保留，未因缓存清理被删除。完整旧运行记录已外置，目录链接用于本机读取。

## 新机器重建

本仓库不随Git传输整个ROS rootfs和编译环境。以下是依赖重建的基本步骤，不是已验证的一键Gazebo启动器：

```bash
source /opt/ros/humble/setup.bash
cd workspace
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select \
  base01_diff_drive nav2_bringup slam_toolbox multi_robot merge_map multi_robot_exploration rviz2-panel
source install/setup.bash
```

重建前应取得记录版本的ROS/Gazebo、TurtleBot3和Nav2依赖；不要用新安装包悄悄替换已冻结的驱动、SLAM或导航行为。原bwrap/`/project`脚本仍依赖本机目录，不会自动下载安装所缺环境。

网络native程序及其库还需按当前源码与原构建身份重建/绑定。具体生产链为`net01e/followup01/production_host.py`经控制器适配进入`net01/host_run.py`、网络和场景入口；历史READY是已结束回合的记录，不应原样重用启动。

## 模型和研究约束

选定模型是继承已训练权重后追加训练的RL04 checkpoint-00512，原parent run完成2048联合决策。父summary、selection、process-exit及训练来源仍保留；这不代表仓库包含全部训练原始地图和轨迹。

通信实验保持PPO、编码、Frontier、mask、目标生命周期、SLAM和Nav2不变。关键业务必须真实过网，安全与未知状态如实处理，不能将静态重放当作物理运行。新配置和实验应独立登记，而不是直接使用旧回合输出或重新训练模型。

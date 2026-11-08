# BASE-01 Econ ROS 2 三机器人自主探索与导航基座复现报告

## A 环境与版本

工作目录为 `/home/zhuyulab/ns3-workspace/base-01-econ/`。本轮仅复现传统探索基座，未实现或训练 RL，未安装、启动或接入 ns-3，未开发通信优化算法。现有 ns-3、其他工作区和历史研究文件未作覆盖或清理。

### 主机原始状态

| 项目 | 审计结果 |
| --- | --- |
| 操作系统 | Ubuntu 22.04.5 LTS，x86_64，内核 6.8.0-138-generic |
| CPU | 两颗 Intel Xeon Gold 6148，共 80 个逻辑 CPU |
| 内存 | 125 GiB，初始约 109 GiB 可用；2 GiB swap |
| 磁盘 | 工作区所在分区约 1.8 TiB，初始约 1.6 TiB 可用 |
| 图形环境 | X11，主机会话 DISPLAY=:0；本项目使用独立 Xvfb :61 |
| 原有 ROS/Gazebo | 未安装，`/opt/ros/humble` 不存在，`ros2`、Gazebo、colcon、rosdep 不可执行 |
| 环境残留 | 存在 ROS_DISTRO=humble、AMENT_PREFIX_PATH、PYTHONPATH、LD_LIBRARY_PATH 等指向已删除 Humble 的变量 |
| 既有机器人进程 | 初始进程快照未发现运行中的 ROS/Gazebo 机器人实验 |
| Docker | 有 CLI，但 daemon 不可连接；未启动或修改主机 Docker 服务 |

完整原始快照见 [host-audit.txt](evidence/initial/host-audit.txt)，隔离方案检查见 [isolation-options.txt](evidence/initial/isolation-options.txt) 和 [docker-audit.txt](evidence/initial/docker-audit.txt)。工作区目录审计仅检查用户目录下有限深度的常见工作区名称，不声称遍历全部磁盘历史。

### 实际运行环境

使用项目内 Ubuntu Base 22.04.5 根文件系统，通过已有的 Bubblewrap 用户命名空间运行。所有 apt 包均装入 `isolation/rootfs/`，不向主机 `/opt/ros`、`/usr`、apt 源或 shell 启动文件写入。构建和运行通过 [in-rootfs.sh](tools/in-rootfs.sh) 进入，清除主机残留 overlay 和 Conda 环境变量。

该环境只读绑定主机 `/proc`、`/sys` 和 DNS 配置，并绑定 `/dev` 供仿真使用；它是依赖与工作区隔离环境，不是针对不可信程序的安全沙箱。ROS 限定 localhost 和 domain 61，Gazebo master 使用 `127.0.0.1:11661`。RViz/gzclient 在本轮验证中关闭，Xvfb 为 Gazebo 深度相机提供软件图形环境。

| 组件 | 实际版本或来源 |
| --- | --- |
| ROS 2 | Humble，`ros-humble-ros-base` 0.10.0-1jammy.20260915.225919 |
| Python | 3.10.12，使用隔离环境 `/usr/bin/python3` |
| CMake | 3.22.1 |
| colcon-core | 0.21.3+upstream-1 |
| rosdep | 0.27.0-1 |
| Gazebo Classic | 11.10.2+dfsg-1 |
| gazebo_ros / gazebo_plugins | 3.9.0 系列；完整 Debian 版本在清单内 |
| Nav2 运行组件 | 1.1.20；使用官方 Humble 二进制组件 |
| nav2_bringup | Econ 仓库内源码，package.xml 声明 1.1.16 |
| slam_toolbox | Econ 仓库内修改版源码，package.xml 声明 2.6.0；本轮真实编译 |
| TurtleBot3 仿真包 | 2.3.8-1jammy.20260915.233431 |
| TurtleBot3 description | 2.3.6-1jammy.20260907.200214 |
| Ceres | 2.0.0+dfsg1-5 |

完整安装包版本见 [isolated-versions.txt](evidence/initial/isolated-versions.txt)。其中 `dpkg --audit` 未报告未配置软件包。未安装系统二进制版 `ros-humble-slam-toolbox` 或 `ros-humble-nav2-bringup`；包发现结果确认源码 overlay 生效，见 [package-discovery.txt](evidence/package-discovery.txt)。

### 上游基准与许可

- 仓库：[econsystems/ros2-multi-robot-automap](https://github.com/econsystems/ros2-multi-robot-automap)。
- 检出分支：`main`；完整 commit：`9825c57f83c2bfb52790cb55b51d30009cbb346f`。
- 原版目录：`upstream/`，本地标签 `base-01-upstream`，原始工作树保持干净。
- 修改目录：`workspace/`，独立 worktree 与分支 `base-01/reproduce`。
- 原始记录：[upstream-baseline.txt](evidence/initial/upstream-baseline.txt)，包含 remote、分支、commit、原始 Git 状态及完整跟踪文件列表。
- 官方说明：[固定版本 README](https://github.com/econsystems/ros2-multi-robot-automap/blob/9825c57f83c2bfb52790cb55b51d30009cbb346f/README.md) 与 [技术手册](https://github.com/econsystems/ros2-multi-robot-automap/blob/9825c57f83c2bfb52790cb55b51d30009cbb346f/Technical_Manual.md)。

仓库没有根目录统一 LICENSE。`multi_robot`、`multi_robot_exploration` 和 `merge_map` 附带 MIT LICENSE，但 `multi_robot/package.xml` 的许可字段仍是 TODO；`nav2_bringup` 声明 Apache-2.0，SLAM 声明 LGPL，具体沿用各组件原文件。不能将整个仓库统一表述为某一种许可证。

SLAM 修改版直接来自上述 Econ commit 内的 `src/slam_toolbox/`，没有用其他实现代替。README 引用 `acachathuranga/slam_toolbox` 的 `multirobot_ros2` 分支；本次查询到该分支为 `c07abd39dd5fc00437e730d6361f042438648947`，见 [slam-reference-ref.txt](evidence/initial/slam-reference-ref.txt)。Econ 子目录没有独立 Git 历史，不能仅凭 README 引用断言它完整等同于该 fork commit；本项目可复现的源码版本以 Econ 固定 commit 加本地补丁为准。

原 world 缺少所引用的 SUV mesh。补充资源来自 [osrf/gazebo_models 固定版本](https://github.com/osrf/gazebo_models/tree/8163eb4b5e7e21985c6591d1c0bfb56468c0093f/suv)，只下载 SUV 相关文件与根 LICENSE，未替换地图或删除障碍。该资源库 LICENSE 为 CC BY 3.0 Unported，原许可保存在 `assets/gazebo_models/LICENSE`。文件来源见 [suv-provenance.json](evidence/initial/suv-provenance.json)。

## B 实际源码架构

```text
workspace/src/
  multi_robot/                 world、Waffle SDF/URDF、启动文件与各机器人 Nav2 参数
  slam_toolbox/                修改版 C++ SLAM，含 multirobot_slam_toolbox_node
  merge_map/                   Python 地图拼接节点及 launch
  multi_robot_exploration/     Python HeadquartersControl 与传统 Frontier 算法
  nav2_bringup/                自带 bringup 包
  rviz2-panel/                 可选面板，本轮不构建、不依赖
```

实际主启动入口使用 `multi_robot/launch/nav2_bringup/` 下的自带导航 launch 文件。它并非直接调用系统 `nav2_bringup` 的启动配置；仓库顶层 `src/nav2_bringup` 仍按官方要求构建并核实发现路径。

### 传感器到运动的链条

1. Gazebo 生成三台 `turtlebot3_waffle`，各自插件发布 scan、odom、joint_states 等数据。
2. 每台机器人的 `multirobot_slam_toolbox_node` 使用自己的 scan 与 TF，发布局部 `/tbX/map` 和 `map → odom`。
3. `MergeMapNode` 等待全部三张地图，再调用 `merge_maps()` 拼接并发布 `/merge_map`。
4. `HeadquartersControl` 接收融合地图与三台机器人的 odom，提取 Frontier，为处于 idle 的机器人选择目标。
5. 控制器向 `/tbX/navigate_to_pose` 发送 `NavigateToPose` Action。
6. Nav2 的 Navfn planner、DWB controller、行为恢复与 velocity smoother 产生速度，Gazebo 差速插件执行运动。

| 接口 | 类型 | 用途 |
| --- | --- | --- |
| `/tbX/scan` | sensor_msgs/LaserScan | 360 样本，约 0 至 6.28 rad；SDF 配置 5 Hz、0.12–10 m |
| `/tbX/odom` | nav_msgs/Odometry | SLAM、Nav2 与中央位置输入，差速插件配置 30 Hz |
| `/tbX/tf`、`/tbX/tf_static` | tf2_msgs/TFMessage | 各机器人独立 TF 传输域 |
| `/tbX/map` | nav_msgs/OccupancyGrid | 独立 SLAM 地图，参数分辨率 0.05 m、更新周期 5 s |
| `/merge_map` | nav_msgs/OccupancyGrid | 中央融合地图，frame_id 为 merge_map |
| `/tbX/navigate_to_pose` | nav2_msgs/action/NavigateToPose | 中央目标、接受、反馈、结果和取消 |
| `/tbX/cmd_vel_nav` → `/tbX/cmd_vel` | geometry_msgs/Twist | 控制器经平滑器交给 Gazebo 的本地速度链 |
| `/gazebo/model_states` | gazebo_msgs/ModelStates | 本轮新增的观测接口，仅用于轨迹与安全核验 |
| `/tbX/contacts` | gazebo_msgs/ContactsState | 本轮新增的底盘接触观测，不输入探索策略 |

每个机器人内部仍使用 `map`、`odom`、`base_footprint`、`base_link`、`base_scan` 等未加前缀的 frame 名，通过不同的 TF 话题隔离。主启动文件还保留全局 `/tf_static` 上各自 `tbX/map → tbX/odom` 的原有静态边；这些边不能当作已经实现了完整的多机器人全局 TF 树。

### 地图融合及真值依赖

`merge_map/merge_map/merge_map.py` 的 `merge_maps()` 根据每张栅格的 origin 和分辨率计算联合边界，将已知单元写入尚未知的单元。发生已知值冲突时，较早遍历的地图优先。它没有地图配准、回环匹配、位姿图对齐或不同地图旋转的估计，也不查询 TF 来完成地图对齐。

Waffle SDF 未设置 `odometry_source`，实际 Gazebo ROS 差速插件默认值为 WORLD=1，其世界位姿发布实现见保存的 [gazebo_ros_diff_drive.cpp](evidence/initial/gazebo_ros_diff_drive.cpp)。运行中的初始 odom 位置与世界出生坐标相符。这使原基座能够依赖共同的世界里程计参考拼接地图，不能据此认定已经具备真实机器人上的独立地图对齐能力。

SLAM 地图仍由 LiDAR 与建图算法真实生成，运动仍由 Nav2 和物理仿真实现；本轮没有用真值地图代替 SLAM，也没有通过设置模型位置制造运动。世界真值里程计属于原项目仿真假设，必须作为后续部署迁移的待解决项。

### HeadquartersControl 的真实算法

核心文件为 `src/multi_robot_exploration/multi_robot_exploration/control.py`。

- `costmap()`：按原规则膨胀占据单元。
- `frontierB()`：寻找与未知单元相邻的自由栅格。
- `assign_groups()` / `dfs()`：八邻域递归聚类。
- `fGroups()`：按大小排序，保留前五个且大小大于两个单元的组。
- `findClosestGroup()`：计算组质心，按 `组大小 / 栅格距离` 评分，过滤原有最大距离和 VISITED 近邻条件。
- `exploration()`：调用上述流程，返回目标，维护 VISITED 和与上一目标的距离约束。
- `HeadquartersControl.__init__()`：订阅地图、odom 和 cmd_vel，创建三个 ActionClient，并为每个机器人启动探索线程。
- `start_exploration()`：每 8 秒墙钟时间检查一次 idle 状态并选择目标；这是三个线程对共享状态的传统分配，不是一个显式的联合优化求解器。
- `send_goal()`、`goal_response_callback()`、`goal_result_callback()`：提交目标、检查接受、等待真实终态、将机器人恢复到 idle。

原有 `feedback_callback()` 和 `robot_status_control()` 是空实现；本轮由独立观测器记录实际 Action feedback，不假称原控制器已经利用反馈做精细决策。`check_exploration_completion()` 以所有机器人 idle 触发地图保存，且探索线程仍持续运行；它不是严格的覆盖完成条件，本轮不据此认定完整探索任务通过。

## C 构建过程与必要修复

### 隔离环境准备

初始系统未装 ROS，本轮没有执行主机 sudo 安装。主要步骤如下，所有文件目标均位于本项目：

```bash
mkdir base-01-econ
cd base-01-econ
git clone https://github.com/econsystems/ros2-multi-robot-automap.git upstream
git -C upstream tag base-01-upstream 9825c57f83c2bfb52790cb55b51d30009cbb346f
git -C upstream worktree add ../workspace -b base-01/reproduce \
  9825c57f83c2bfb52790cb55b51d30009cbb346f

# 下载并解包 Ubuntu Base 到新的 isolation/rootfs，禁止覆盖已有用户目录
mkdir isolation
mkdir isolation/downloads isolation/rootfs
curl -fL http://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.5-base-amd64.tar.gz \
  -o isolation/downloads/ubuntu-base-22.04.5-base-amd64.tar.gz
tar -xzf isolation/downloads/ubuntu-base-22.04.5-base-amd64.tar.gz \
  -C isolation/rootfs --no-same-owner
```

根文件系统软件源与 ROS 签名 key 保存在 `isolation/rootfs/etc/apt/` 和 `usr/share/keyrings/ros-archive-keyring.gpg`。宿主只用 `apt-get download` 获取用户态辅助工具，再以 `dpkg-deb -x` 解包，不注册为宿主软件包。有效安装方式使用项目内 fakeroot 处理单 UID 用户命名空间中的包所有权，用 eatmydata 加速可重建环境的安装；关闭的 fsync 仅用于依赖安装，不用于运行证据记录。`policy-rc.d` 阻止安装脚本启动系统服务。

当前交付目录已包含这些环境和工具，无需重新安装。若在一个新的空目录重建依赖环境，先复制本报告及 `tools/`，在解包根文件系统后执行以下引导步骤；这些命令只操作项目内路径：

```bash
(cd isolation/downloads && apt-get download fakeroot libfakeroot eatmydata libeatmydata1)
for package in isolation/downloads/*.deb; do
  dpkg-deb -x "$package" isolation/rootfs
done
curl -fL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o isolation/rootfs/usr/share/keyrings/ros-archive-keyring.gpg
printf '%s\n' \
  'deb http://cn.archive.ubuntu.com/ubuntu jammy main restricted universe multiverse' \
  'deb http://cn.archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse' \
  'deb http://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse' \
  > isolation/rootfs/etc/apt/sources.list
printf '%s\n' \
  'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main' \
  > isolation/rootfs/etc/apt/sources.list.d/ros2.list
printf '#!/bin/sh\nexit 101\n' > isolation/rootfs/usr/sbin/policy-rc.d
chmod +x isolation/rootfs/usr/sbin/policy-rc.d tools/in-rootfs.sh
tools/in-rootfs.sh -c 'bash tools/apt-in-rootfs.sh update'
```

apt 软件源的未来版本可能变化；要核对本轮版本，使用已交付的完整包清单和根文件系统。本次没有宣称未来未锁定的 apt 源能自动得到逐字节相同的软件环境。源码补丁可在新检出的指定 commit 上使用 `git apply /原交付目录/evidence/source/econ-base01.patch` 应用。

准确的顶层依赖安装命令为：

```bash
tools/in-rootfs.sh -c 'bash tools/apt-in-rootfs.sh install -y --no-install-recommends \
  build-essential cmake git ca-certificates curl gnupg fakeroot eatmydata \
  python3-colcon-common-extensions python3-rosdep python3-numpy python3-scipy python3-opencv \
  libceres-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev libeigen3-dev \
  qtbase5-dev libqt5svg5-dev xvfb xauth \
  ros-humble-ros-base ros-humble-navigation2 ros-humble-gazebo-ros-pkgs \
  ros-humble-turtlebot3-gazebo ros-humble-turtlebot3-description \
  ros-humble-joint-state-publisher ros-humble-xacro ros-humble-tf2-tools ros-humble-rviz2'
```

编译工具用于源码构建；Ceres、Boost、Eigen 和 Qt 用于修改版 SLAM/其 RViz 插件；ROS/Nav2/Gazebo/TurtleBot3 包提供运行组件；NumPy/SciPy 用于原 Python 控制器与融合；Xvfb/xauth 用于隔离图形环境；TF 工具用于诊断。完整传递依赖及版本见包清单。没有盲目执行可能安装另一份 SLAM 的全量 rosdep 安装；仓库 Python 包声明也没有完整列出其实际 NumPy/SciPy 等依赖。

环境安装过程遇到 PRoot 文件操作过慢，先后保留了原始安装、原生安装和加速安装日志；切换时中断的 fontconfig 导致未配置依赖，最终在同一隔离根文件系统内通过 `apt-get install --reinstall fontconfig` 修复。相关原始日志均在 `evidence/initial/isolated-*.log`，最终 `dpkg --audit` 为空。未通过删除包管理器锁文件或修改主机系统解决。

在新目录补齐 world 所需外部资源时，固定模型仓库 commit，并只取 SUV 子目录：

```bash
mkdir -p evidence/initial
curl -fL \
  'https://api.github.com/repos/osrf/gazebo_models/git/trees/8163eb4b5e7e21985c6591d1c0bfb56468c0093f?recursive=1' \
  -o evidence/initial/gazebo-models-tree.json
python3 tools/fetch-suv.py
```

资源下载首次遇到 TLS EOF，失败日志已保留；随后只补取缺失的 OBJ、model.config 和 model.sdf。下载器对已有文件拒绝覆盖，当前环境无需重复执行。

### 实际构建命令

```bash
tools/in-rootfs.sh -c '
  source /opt/ros/humble/setup.bash
  cd /project/workspace
  export CMAKE_BUILD_PARALLEL_LEVEL=8 MAKEFLAGS=-j8
  colcon build --symlink-install --packages-select nav2_bringup slam_toolbox \
    --parallel-workers 2 --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
'

tools/in-rootfs.sh -c '
  source /opt/ros/humble/setup.bash
  source /project/workspace/install/setup.bash
  cd /project/workspace
  colcon build --symlink-install --packages-select multi_robot_exploration merge_map multi_robot \
    --parallel-workers 3 --cmake-args -DBUILD_TESTING=OFF
'
```

两组必要包均构建成功。第一次 SLAM 编译在会话中断时未完成，原日志仍保留；恢复构建复用已有产物。随后针对 world 时间修复重建 `multi_robot`、针对 TF 修复重建 `slam_toolbox`。没有修改 SLAM 的优化器、配准算法或 Nav2 运行组件源码。

| 文件或位置 | 必要修复及原因 |
| --- | --- |
| 主 mapping launch | 用 robot_count 截取原四机器人数组；三台时不启动 tb4，默认及四台能力保留；加入 enable_exploration、enable_gui 并向融合 launch 传递 enable_rviz，以允许先做非自主验证 |
| 主 mapping launch / 自带 bringup | mapping 模式关闭 AMCL localization 路径，使用外部修改版 SLAM；避免两个定位来源竞争 map→odom；给中央控制器传入 use_sim_time |
| Waffle SDF | 将开发者机器绝对 mesh 路径改为 model://turtlebot3_common；主 launch 设置模型搜索路径 |
| tb1–tb4 Nav2 参数 | 修正错误的 goal_checker_plugin 字段及破损值为 goal_checker_plugins；将机器人圆半径从 0.22 m 改为 0.25 m，以包络约 0.237 m 的底盘碰撞外接半径，不改探索评分或速度参数 |
| HeadquartersControl | 设置合法单位目标四元数；目标提交结果只判断接受，再 get_result_async 等真实终态；服务器不可用/拒绝恢复 idle；去掉不存在的 shutdown_node 调用 |
| world / Waffle SDF | 加入只观测的 Gazebo state 与底盘接触插件，供轨迹核验和异常停止，不作为新控制算法 |
| my_world.world | 将已保存的 1996.381 s 初始 sim_time 归零；保留所有模型位置，修复冷启动 ROS 时钟跳变导致的生成服务误超时 |
| slam_toolbox_multirobot.cpp | 参照同仓库异步回调更新 scan_header，使既有 TF 发布线程能发布 map→odom；未替换修改版 SLAM |

变更补丁见 [econ-base01.patch](evidence/source/econ-base01.patch)。静态检查见 [static-checks.json](evidence/static-checks.json)，覆盖出生位置、底盘半径、关键参数、Python 语法及 Action 接受/成功/失败/取消/拒绝。Frontier 提取、聚类和评分函数与上游保持一致。

## D 三机器人运行验证

### 启动命令与回合边界

有效的主启动命令为：

```bash
ros2 launch multi_robot gazebo_multirobot_mapping_with_nav2.launch.py \
  robot_count:=3 enable_exploration:=false enable_rviz:=false \
  enable_gui:=false enable_drive:=false
```

本轮实际通过监督脚本先执行上述启动、完成非自主检查与停止能力检查，再启动原控制器：

```bash
cd /home/zhuyulab/ns3-workspace/base-01-econ
# 以下是已执行命令的记录；run-03 目录已存在，脚本会拒绝覆盖。
tools/in-rootfs.sh tools/run-baseline.sh /project/evidence/run-03 \
  --sim-seconds 180 --wall-seconds 420

# 非自主检查通过后由监督程序执行：
ros2 run multi_robot_exploration control --ros-args \
  -p robot_count:=3 -p use_sim_time:=true
```

启动前不发送探索目标，且关闭独立 drive 节点。Nav2 的本地导航速度是本轮自主运动的来源；监督工具只发布零 Twist，不发布非零速度、不设置 Gazebo 模型位姿。`run_baseline.py` 和 `run-baseline.sh` 保存了实际执行与清理逻辑。

| 回合 | 实际结果 | 是否启动自主探索 |
| --- | --- | --- |
| run-01 | tb1/tb2 生成及局部 SLAM 有数据；保存 world 时间触发生成服务异常，第三台未启动；人工结束并保留失败原件 | 否 |
| run-02 | 三台真实生成，传感器、局部地图和融合地图有数据；修改版 SLAM 缺少 scan_header，map→odom 不发布；结束时使用物理暂停，未通过完整停止验收 | 否 |
| run-03 | TF 修复后通过三机器人非自主检查；完成一次 180 s 仿真时间的自主探索；结束时未满足持续静止标准，触发物理暂停后退出 | 是，本轮唯一一次 |

没有为了覆盖率选取其他地图，没有追加自主回合或调参试验。运行前两次失败是针对已定位启动/TF 缺陷的非自主验证，不计作正式自主探索成功。

### 实际验证结果

| 项目 | 证据与结果 |
| --- | --- |
| 数量及出生位置 | Gazebo 准确生成 tb1=(5,4)、tb2=(-4.5,4)、tb3=(6,-1.5)，无 tb4；最小初始中心间距约 5.59 m |
| 传感器 | 三台 scan、odom、contacts 持续接收；scan 首包参数与 SDF 一致；计数见 result.json |
| TF | 每台独立链 map→odom→base_footprint→base_link→base_scan 均可查询；tf_edges.json 保存三套边，tf-diagnostic.txt 有实际数值 |
| SLAM | 三台独立地图均生成，随运动变化；不是读取预制地图替代 SLAM |
| 地图融合 | /merge_map 实际发布 140 次，记录到 83 次数组变化；最终栅格 258×270，已知单元由 4514 增至 58682 |
| Nav2 | 三套 controller/planner/bt_navigator/behavior/velocity_smoother 生命周期均验证为 active；目标 Action 有 EXECUTING、SUCCEEDED 和最终取消记录 |
| 中央目标 | 原 Frontier 控制器给三台机器人均产生目标，control.log 保存位置、接受和终态；反馈另由观测器记录 |
| 运动 | 三台均有 Gazebo 真值轨迹和非零速度，正式区间每台约 1799 个位姿样本 |
| 异常监测 | 最小观测中心间距 0.9193 m，高于预设 0.70 m 停止阈值；未记录底盘 contact 事件，未触发高度或关键 TF/节点缺失中止 |

| 机器人 | 正式区间轨迹长度 | 相对区间起点最大位移 | Nav2 执行目标数 | 区间内成功终态数 |
| --- | --- | --- | --- | --- |
| tb1 | 2.701 m | 2.200 m | 2 | 1 |
| tb2 | 31.658 m | 12.888 m | 6 | 5 |
| tb3 | 23.005 m | 7.904 m | 7 | 7 |

这些数值从 `trajectories.csv` 按 exploration_command 到 smoke_bound 的时间区间统计，见 summary.json。`result.json` 的距离包含启动和停止阶段，因统计范围不同，不能与表内数值混用。

日志中的静态 TF 老式参数、robot_state_publisher 通过命令行读 URDF，以及 SLAM 的 20 m 配置超过 LiDAR 10 m 能力均为实际保留的警告；激光范围被实现裁剪。启动初期曾有 TF 缓存尚未就绪的 scan 丢弃，最终三套 TF 链已实际查询通过。导航期间的规划/进度失败与这些启动警告分别记录，没有把导航错误归为无影响警告。

| 地图 | 初次已知单元 | 最后已知单元 | 最后宽×高 |
| --- | --- | --- | --- |
| tb1 | 1644 | 8214 | 154×85 |
| tb2 | 1494 | 48633 | 254×222 |
| tb3 | 1376 | 45151 | 258×270 |
| merge_map | 4514 | 58682 | 258×270 |

已知单元数不是覆盖率，也不表示正确完成了全部未知环境探索；本轮没有参考地图分母、自然探索终态或重复验证证据。原策略运行中出现过目标在局部全局 costmap 外、规划失败和 tb1 progress checker 报错，原日志保留，未为提高探索表现修改目标评分。

### 时间与安全停止

- run-03 启动：2026-11-04 17:20:35.489 北京时间（09:20:35.489 UTC）。
- 自主探索开始：17:21:07.859，北京时间；仿真时间 21.3 s。
- 到达冒烟边界：17:24:30.618，北京时间；仿真时间 201.3 s。
- 自主区间：精确 180.0 s 仿真时间，202.757 s 墙钟时间，未触及 420 s 墙钟上限。
- 物理暂停后进程退出：17:24:48.390，北京时间。

开始前已验证一次零运动状态下的停止链：取消目标服务可调用、三套 Nav2 暂停成功，随后在仿真继续推进 1.3 s 的情况下观察到三台持续静止，再恢复 Nav2 并核实 active 后才启动探索。这证明启动前检查通过，不能代替运动结束后的动态停止验证。

探索结束后先结束 HeadquartersControl，再取消三台目标：tb1/tb2 各取消一个活动目标，tb3 无活动目标，三个取消返回码均为 0。三套 Nav2 暂停均返回成功；之后持续发送零速度，并要求真实模型状态同时满足线速度小于 0.01 m/s、角速度绝对值小于 0.03 rad/s，连续至少 1.5 s 墙钟时间，且仿真继续前进、观测新鲜。

**动态停止没有通过。** 在 12 s 观察窗口结束前仍未达到该条件。最后三秒数据如下，见 stop-analysis.json：

| 机器人 | 最大线速度 | 最大角速度绝对值 |
| --- | --- | --- |
| tb1 | 0.001516 m/s | 0.090901 rad/s |
| tb2 | 0.000136 m/s | 0.017274 rad/s |
| tb3 | 0.011474 m/s | 0.006165 rad/s |

Nav2 全部暂停后，记录中没有新的非零 cmd_vel 事件，但真实物理状态仍有残余运动。其来源可能涉及执行端/物理模型或命令交付，现有证据不能把具体根因定死；没有通过放宽停止阈值或修改摩擦参数来宣布成功。随后调用 /pause_physics，明确记录 emergency_physics_pause，再终止本轮启动的进程。物理暂停不等同于机器人在运行中的物理世界已可靠刹停。

最终未发现本轮遗留的 gzserver、Xvfb :61、控制器、SLAM 或机器人运行进程；domain 61 的 ROS CLI daemon 也已停止，见 owned-processes-final.txt、processes-final.txt 和 daemon-stop.txt。退出日志中一些 Python/ROS 节点对 SIGINT 给出 KeyboardInterrupt 或 -2，发生在有意结束过程中；不能把它们写成所有节点零返回码退出。

接触观测覆盖底盘碰撞体，机器人间距基于约 10 Hz 模型状态采样；它们可核验本轮未观测到的异常范围，不构成完整机器人碰撞或实机安全认证。

## E 运行证据与校验

证据保存在 `evidence/`，不覆盖失败原件。构建的完整 colcon 分包日志还保存在 `workspace/log/` 中带时间戳的目录，`latest_build` 仅是快捷链接。

| 证据 | 路径 |
| --- | --- |
| 原始环境与上游版本 | `evidence/initial/host-audit.txt`、`upstream-baseline.txt`、`isolated-versions.txt` |
| 初次编译中断及恢复 | `evidence/build-first.log`、`build-resume.log` |
| 机器人包编译 | `evidence/build-robot-packages.log` |
| 运行根因修复后的构建 | `evidence/build-world-clock-fix.log`、`build-slam-tf-fix.log` |
| 源码差异与检查 | `evidence/source/econ-base01.patch`、`diff-check.txt`、`working-status.txt` |
| 非自主失败原件 | `evidence/run-01/`、`evidence/run-02/` 及对应 supervisor 日志 |
| 正式有界回合 | `evidence/run-03/`、`evidence/run-03-supervisor.log` |
| 节点、话题、Action、进程 | 回合目录中的 `nodes.txt`、`topics.txt`、`actions.txt`、`processes.txt`、`processes_after.txt` |
| TF | `run-03/tf_edges.json`、`tf-diagnostic.txt` |
| 轨迹、时序、安全和停止事件 | 回合目录中的 `trajectories.csv`、`events.jsonl`、`result.json` |
| 中央目标和真实导航结果 | `run-03/control.log`，配合 events 中的 Action UUID、状态和反馈 |
| 地图 | 各回合 `tbX_first/last.npz`、`merge_map_first/last.npz` 与对应 PGM |
| 完整启动日志 | 各回合 `launch.log` 与 `ros_logs/` |

NPZ 保存原始 int8 占据数组、宽高、分辨率、原点和 frame；PGM 是可查看的占据栅格样本，不替代原始数据。本轮未将上游演示视频或截图作为本次运行证据，未录制大体积 rosbag。

交付文件 SHA256 清单为 [SHA256SUMS](SHA256SUMS)。它覆盖报告、支持工具、上游补丁、所修改源码、外部 SUV 资源及保存的证据文件；不对整个依赖根文件系统、编译产物或上游演示视频做无必要的全量哈希。清单本身不参与自校验。

## F 后续研究接口

### 中央 RL 替换位置

最佳替换位置是 `control.py` 的 `HeadquartersControl.start_exploration()` 所处的目标选择调度层，以及它对 `exploration()` / `findClosestGroup()` 的调用。当前三个线程各自选目标；未来要实现联合分配，需要在该类的调度处汇集三台机器人的状态，再一次性输出三台机器人的目标。`__init__()` 中启动各机器人线程的位置也属于这一替换边界。本轮未提前实现 Policy 抽象或联合调度接口。

| 所需信息 | 现有入口 |
| --- | --- |
| 共享地图、分辨率、原点、宽高 | HeadquartersControl.map_callback() 与 self.map_data 等字段 |
| Frontier 候选组与质心 | exploration() 内部 assign_groups()、fGroups()、calculate_centroid()；目前未作为独立 ROS 接口发布 |
| 三机器人位置 | robot_odom_callback() → self.robot_positions；当前仍带世界真值里程计仿真假设 |
| 当前任务状态 | self.robot_states、每线程 last_target、共享 VISITED 与 Action 终态 |
| 导航目标输出 | send_goal() → 各机器人 NavigateToPose；保留 Nav2 及其本地速度链 |

未来 RL 应输出导航目标，不直接输出 cmd_vel。先解决可部署状态来源与输入语义，再训练、验收和冻结策略；本轮未开始该阶段。

### 未来 ns-3 消息流清单

机器人本地 LiDAR→SLAM、TF→Nav2、局部 costmap、规划/控制、速度平滑与底盘控制保留本地闭环。未来需要受无线交付约束的是机器人到中央的位姿、状态、局部地图/增量，以及中央到机器人的导航目标、取消和重分配请求与返回的接受、结果和反馈。若 Frontier 在中央从已交付地图生成，它属于中央内部数据；若移到机器人侧生成并共享，则其候选与状态也进入无线数据流。

Action 的目标、接受、反馈、结果和取消必须一起审计，不能只模拟地图而让目标或反馈经理想 DDS 旁路送达。Gazebo 真值仅保留在评估/网络节点位置更新侧，不能作为未传输的策略观测。本轮只记录这些边界，没有接入通信仿真。

### 真实部署兼容性

实机仍需解决世界真值里程计替换、独立地图对齐与定位漂移、传感器及底盘几何校准、实机 TF/时钟与导航参数，以及真实无线网络上的 DDS/业务消息交付。原基座的线程状态、VISITED 和“全部 idle 即保存地图”规则也不构成可靠的任务完成判据。这些是从当前源码和运行设计识别出的后续工程问题，不代表本轮已完成部署可靠性验收。

## G 验收结论与交接状态

| 项目 | 结论 | 已验证与限制 |
| --- | --- | --- |
| SOURCE | PASS | 上游固定 commit、结构、依赖、许可、修改版 SLAM 与中央算法调用链已审查；无法从嵌入子目录反推出 fork 的完整历史关系，已明确说明 |
| BUILD | PASS | 五个必要包均真实构建，源码 SLAM/bringup 与节点入口可发现；未构建可选 RViz panel，未跑全仓库测试套件 |
| 三机器人 RUNTIME | PARTIAL，整体验收 BLOCKED | 传感器→SLAM→融合→传统目标→Nav2→物理运动链已验证；结束后的可靠动态停止尚未通过 |
| BASELINE SMOKE | BLOCKED / NOT PASS | 完成唯一一次有界自主回合，但安全停止是必要条件，不能将功能链运行包装为完整 PASS |
| 安全停止 | FAIL | 取消与 Nav2 暂停成功，残余真实速度超出预设阈值；最终以物理暂停和进程退出收尾 |
| BASELINE TASK | 未验证 | 无覆盖率分母、自然终态和可靠重复实验，不作完整探索成功结论 |
| 是否进入 RL 阶段 | 不建议 | 先针对已记录的动态停止问题完成独立修复与验证，再验收基座；本轮不追加自主回合，不自动开展下一阶段 |

本地 Git 状态：修改保留在 `workspace/` 的 `base-01/reproduce` 分支，HEAD 仍为上游 `9825c57f83c2bfb52790cb55b51d30009cbb346f`；**本轮未创建新的本地 commit**，未推送远程。原版 `upstream/` 保持干净，完整可审查变更在补丁和 working-status.txt。环境、观测工具与证据在相邻目录交付，不冒充上游文件。

后续会话先读本报告、run-03/result.json 和 stop-analysis.json。当前阻断是动态停止未可靠闭合，不是尚未安装 ROS 或尚未跑通三机器人探索链。

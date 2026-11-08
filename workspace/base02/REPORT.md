# BASE-02 中央分配器解耦与训练合同验收报告

本报告对应独立新工作区`/home/zhuyulab/ns3-workspace/base-02-central/`。中央任务接口、状态/动作、生命周期、训练合同和评价接口已实现并通过离线检查；**唯一Gazebo回归在前置TF门控失败，未启动新中央控制器，整体NO-GO**。没有训练、ns-3、实机操作或远程推送。BASE-01历史工程和证据保持不变。

## P0 基线固定

BASE-01最终提交：`12b366564842fbc98de57e0fc679a9b22d125543`，上游`9825c57f83c2bfb52790cb55b51d30009cbb346f`，独立结论ACCEPT，范围是有界传统三机器人基座；不是完整任务/实机可靠性通过。冻结清单见[evidence/base01-frozen.json](evidence/base01-frozen.json)，沿真实launch补录了三台Nav2参数、world/SDF、Waffle URDF、Nav2 bringup/navigation、修改版SLAM launch/mapper配置、中央源码、融合、驱动和验收材料。tb4/tb5/tb6参数列为非运行保留项，不充当三台配置依据。

新Git worktree分支`base-02/central-interface`，从上述验收提交创建。原BASE-01工作树干净；受保护的multi_robot、SLAM、Nav2 bringup、merge_map、base01_diff_drive源码均无差异。依据见[preserved-before-run.json](evidence/preserved-before-run.json)。

最初在新路径下对六个未变/待变包进行了隔离构建，耗时4分34秒，全部通过；这是多余的底座重编步骤，不把它描述成仅编译中央分配器或新增底座能力。新驱动按Release重编，旧验收产物是RelWithDebInfo，二进制哈希不同；未拿差异产物做运动验证。实际回归采用BASE-01只读原产物，只覆盖本轮中央Python包，后续不再重编底座。

## P1 源码解耦

架构图和完整合同见[CONTRACT.md](CONTRACT.md)。实际修改仅中央Python包、工程忽略规则，以及本轮独立工具/测试/文档。

| 文件 | 职责 |
| --- | --- |
| `frontier.py` | 提取冻结BASE-01的膨胀、Frontier、聚类、顺序和连通实现 |
| `allocation.py` | 三种选择器、统一冻结观测、候选/掩码、任务预留/UUID/终态、冲突/停滞/超时状态 |
| `control.py` | ROS地图/odom/TF输入、共同目标检查、同一Nav2 Action执行、来源和评价事件 |
| `environment.py` | reset/step/奖励/终态/异常处理合同，要求真实后端重置与安全停止确认 |
| `evaluation.py` | 统一事件指标、固定区间、可选离线参考覆盖和Gazebo轨迹 |

traditional保留原评分、候选顺序和平分、预留/访问/失败、last_target后置否决及每机8秒墙钟检查。与冻结原源码比较40组地图/历史输入，逐目标相同；核心提取函数AST相同。正常任务不被地图更新或Frontier自然消失无意义抢占。三线程调度和物理仿真仍不确定，不声称不同回合逐点轨迹一致。

rl是显式外部callable接口，未挂接即报错，没有传统/测试回退。test是确定性合同fixture，不是学习算法。ROS自主入口本轮只允许traditional，三模式离线经同一Allocator与Nav2消息转换路径检验。

## P2–P4 统一状态、动作、生命周期

观测涵盖三机位姿/速度/来源/时间、当前目标/任务token/UUID/持续时间/最近结果，带版本的共享已知地图，逐机Frontier/已知栅格最短路估计/边界面积信息代理/有效掩码，以及目标归属、候选冲突和历史。没有Gazebo真值订阅或真值全图输入。地图和候选不可被策略改写。

联合动作使用三元候选索引，KEEP=-1、WAIT=-2，绑定decision_id/map_version。支持NumPy整数，拒绝bool/浮点。统一拒绝旧快照、变更的任务所有权、非法/失效候选、冲突和活动任务改派；重复输出不重复提交Action。派发前和晚到接受都核对权限，失效handle取消，旧结果不释放新目标。

成功/失败/取消后释放当前任务再分配；无候选不冒充自然完成，连续等待显式标记stalled_wait。地图更新、冲突、可选任务超时产生事件，超时等待实际取消终态后释放。默认保持BASE-01正常导航与8秒检查行为，外部监督器负责物理安全停止；Allocator.stop本身不宣称已停稳。

## P5 训练合同与路线

reset要求后端确认world/SLAM/Nav2完整重置，新episode才能开始；step有决策预算和仿真步长边界。自然完成需要显式证书；决策预算、时钟/环境异常、Nav失败、人工终止、安全停止等原因分开。异常时先请求停止并保留停止结果，再抛出原异常，未伪造正常transition。

奖励返回带单位的分量：共享已知面积正增量m²、仿真秒、导航路程m、重复分配、切换与冲突次数。本轮不选择标量权重。共享已知面积只是可观测代理，不是覆盖率；重复感知面积在现有合图计数下不可辨识，明确为None，不用0冒充测量。安全作为硬约束。

**训练接口可在确定性fixture后端执行；真实Gazebo episode reset/训练后端尚未实现，直接开始训练仍BLOCKED。** fixture不是物理训练环境或第二套仿真器。推荐RL-01先沿路线A完成真实ROS/Gazebo重置/交互验证，再根据吞吐决定是否建立同合同轻量后端B；不在本轮实现完整轻量世界或选定神经网络。

## P6 统一评价

统一JSONL包含地图、目标/身份/终态、位姿、反馈与停止原因；指标快照不会被后续状态改写。输出各机里程计路程/参与、分配、重复分配/冲突、Nav2成功/失败率、切换/取消及结束原因。取消独立列出，不放进成功/失败率分母。

工具可附加独立Gazebo轨迹算物理路程，并从监督器Action状态补齐控制器退出后的取消/结果；事件和轨迹使用同一指定评价区间。覆盖率必须有固定参考区域与对齐掩码，无分母则为None；独立参考不进入policy观测。具体单位、来源、限制和CLI见合同。

## P7 实际验证与运行

- 六包隔离构建通过，完整日志[evidence/build.log](evidence/build.log)；CMake PkgConfig命名dev warning保留。
- 候选`2f76f42db248b77252bfb13cf23071df1af80f7d`完成22项离线/确定性测试，35.876秒，通过；见[contract-tests-final.log](evidence/contract-tests-final.log)。后续评价时序/停止原因修正只跑相关定向测试，没有重复整套；原日志保留。
- 最终运行候选 **`4a0d5285523b9236e4ed7345d64680bc95869533`**，独立评审从Git导出只读快照，在断网、无ROS节点环境运行完整23项，35.991秒全部通过。见[独立检查](../reviews/BASE-02/candidate-4a0d528/INDEPENDENT_TEST.md)。
- 初轮18项通过；独立预审的外部异常停止、指标快照、整数动作、晚到handle和时间窗口反例已对应修正并入测试；原日志保留，不声称首次草稿即完善。
- 无节点检查确认新中央模块来自`/mnt/workspace/src/.../control.py`，SLAM和机器人包仍来自`/project/workspace/install/`的BASE-01原产物。新ROS域62、Gazebo端口11662、Xvfb62、home/tmp/日志独立。
- Gazebo回归仅执行一次，前置审查通过后按以下命令启动。没有rl/test自主回合，也没有失败后重启。

### 实际命令与边界

```bash
cd /home/zhuyulab/ns3-workspace/base-02-central
set -e
python3 tools/capture_case_identity.py evidence/traditional-regression-01.identity.json \
  --driver libbase01_diff_drive.so --kind base02_traditional_regression
tools/in-rootfs.sh --baseline-runtime /mnt/tools/run-baseline.sh \
  /mnt/evidence/traditional-regression-01 --sim-seconds 180 --wall-seconds 420
```

这是已执行记录，原回合目录存在时拒绝覆盖；本轮不重跑。source/工具身份见[事前identity](evidence/traditional-regression-01.identity.json)。BASE-01只读挂载`/project`，实验工程挂载`/mnt`，只通过PYTHONPATH覆盖中央包。验收驱动预期SHA为`8d54d39a687de851c95137ddee4a7ebbab90c3373e07d96fad338870d4317fc0`，事前身份绑定该原产物。因失败早于实际库maps采集点，**本次没有loaded-driver.json/gzserver.maps，不补称实际加载已做maps核验**；运行日志与驱动遥测均有state_sync=1。

### 唯一回合失败事实

回合UTC **2026-11-04 13:04:55.469–13:09:03.139**（北京时间21:04:55–21:09:03）。启动前置窗口为240秒墙钟，拟自主180秒/墙钟420秒预算从未开始。结果：

```text
preflight=false
error="Preflight missing: ['tb1/TF map->base_scan']"
smoke_started=false
end_reason=not_started
sim_elapsed=0.0
observed_stop=true
baseline_smoke_pass=false
```

三台scan/odom/局部SLAM图和共享图消息确实收到，分别scan1084/1074/1061条、odom6375/6314/6236条、局部图48/47/46条，共享图138条；地图内容版本均为1，场景处于静止初始观测，不能当作自主探索地图更新。没有Frontier目标、Nav2目标接受/执行/反馈、新中央代码运行或自动探索运动证据。约6.5毫米位姿累计漂移是物理初始静置表现，不作为自主运动。

门控失败前未执行nodes/topics/actions快照、Nav2 active检查、主Buffer导出或实际库maps绑定；相关文件缺失是本次证据边界，不以推测填补。没有`allocation-events.jsonl`，因此本次实际中央评价日志和新控制器运行链是NOT RUN；独立接口测试不替代它们。失败指标汇总见[failure-summary.json](evidence/failure-summary.json)。

### TF定位结论

主监督器tb1 Buffer在超时点无法完成`map→base_scan`。同一次Gazebo运行期间，两次晚加入的**只读**探针看到了三台完整TF边，并在相同消息/时钟模式下三台均`can_transform=True`；scan/odom/map/contacts/drive/model话题也均收到。见[readiness-probe.txt](evidence/readiness-probe.txt)、[readiness-detail.txt](evidence/readiness-detail.txt)。探针没有发布目标、速度或TF，没有干预/放宽门控。

因此不能把故障写成“系统tb1持续没有TF”；已确认的是主监督器Buffer就绪失败。实际安装的`tf2_ros/buffer.py`构造函数中，node仅用于建立FrameGraph服务，**没有自动注册时钟jump/clear回调**；已排除套用其他版本的“首次仿真时钟自动清缓存”解释，未为此假设增加虚构修复或单测。源码原件/摘要见[installed-tf2-buffer.py](evidence/installed-tf2-buffer.py)、[tf-analysis.json](evidence/tf-analysis.json)。原事件sim无倒退，监督日志也没有相应jump清缓存记录。

主Buffer未保存`all_frames_as_yaml`与失败debug tuple，现有证据无法确定它具体缺哪条边，以及初始交付/缓存异常的确切原因。**根因仍未知**。没有在证据不足时改变TF/门控代码或重启Gazebo。

### 停止与退出

三台取消响应均0个目标，导航暂停均成功；UTC13:09:01.288、sim217.0确认真实静止，稳定期仿真推进1.4秒。最终线速度分别约0.0000584/0.0000566/0.0000676 m/s，角速度绝对值约0.000049 rad/s，满足原0.01m/s、0.03rad/s、连续>1.5秒墙钟、仿真推进>0.5秒、12秒观察窗口判据。驱动已消费零值。没有物理暂停，接触事件0，最小观测中心距5.590m。

这只证明本次静置场景收尾，不证明新中央活动目标的取消/停止。BASE-01动态停止验收仍属于原版本既有证据，不移作新版实际运行证明。

顶层launch退出0；部分子进程有SIGINT对应的-2/KeyboardInterrupt，保留完整日志。43个跟踪PID全部退出，当前未发现Gazebo/Nav2/SLAM/Xvfb残留或domain62 daemon。见[process-exit.json](evidence/process-exit.json)、[runtime-process-check.txt](evidence/runtime-process-check.txt)。

## 修改与证据交付

完整源差异为[evidence/base02.patch](evidence/base02.patch)，修改文件清单为[evidence/changed-files.txt](evidence/changed-files.txt)。完整配置/实现见[CONTRACT.md](CONTRACT.md)；关键运行原件集中`evidence/traditional-regression-01/`，保留launch/ROS/Gazebo日志、话题样本、地图NPZ/PGM、驱动CSV、物理轨迹、停止/失败/退出事件。没有截图替代数据，也没有虚构缺失的中央日志。

最终清单为[SHA256SUMS](SHA256SUMS)，核对结果见[evidence/sha256-check.txt](evidence/sha256-check.txt)。本地最终交付commit和报告SHA另见[evidence/delivery-identity.json](evidence/delivery-identity.json)，区别于实际运行候选4a0d528；未远程推送。

根工作区PROJECT/README/AGENTS随当前状态更新。BASE-01的旧FINAL清单曾包含这三个外部动态文档，本轮更新不重签其历史清单；当时版本保存在`12b3665:base01/project-state/`，BASE-01工作树和自身代码/运行证据原件未变。不得声称旧清单对如今变化的根文档仍469项全部通过。

## 最终七项判定

| 项目 | 判定 | 范围和未验证项 |
| --- | --- | --- |
| BASELINE PRESERVED | **PASS** | 冻结源码/配置/历史证据保留，原函数及40组选择对照通过；不声称新版Gazebo行为已证等价 |
| POLICY INTERFACE | **PASS** | traditional/显式外部rl/test共享状态和执行合同，未挂RL则报错；没有训练或伪RL |
| ACTION SAFETY | **PASS** | 离线硬门控、快照/UUID所有权、共同Nav2目标转换通过；新控制器自主运动安全尚未运行验证 |
| TRAINING CONTRACT | **BLOCKED** | 接口和确定性后端测试通过；实际Gazebo训练/reset后端未实现，不可直接开始训练 |
| EVALUATION INTERFACE | **PASS** | 统一事件、指标快照、同区间与真值隔离已测试；真实新中央日志本次未产生 |
| INTEGRATION TEST | **FAIL** | 唯一Gazebo尝试preflight失败；新中央真实执行为NOT RUN。离线确定性集成通过不抵消此失败 |
| OVERALL | **NO-GO** | 当前不能把BASE-02认定为已运行验收，也不进入RL-01 |

## 最小待办与停止边界

1. 后续另行授权后，先增强前置失败的TF Buffer诊断证据：精确debug tuple、各机缓存帧图和接收边/时间，针对真实缺边定位；不能凭晚探针正常直接放行或把其他版本时钟行为当根因。
2. 本轮唯一Gazebo授权已使用，不自动追加回合。定位完成后若需再次真实验证，须在新的明确任务中固定版本、确认安全前提，再验收traditional完整高层闭环。
3. 运行验收通过后，RL-01首先应补真实episode reset/训练后端和可计算奖励口径，验证冻结合同后再选网络/训练。当前不启动该阶段。

本轮接口实现、离线验证、唯一运行尝试和失败归档已执行完毕；工程整体运行验收未通过。保留首失败、未知根因与训练阻断，停止新增检查、修补和运动实验，交回独立复核。

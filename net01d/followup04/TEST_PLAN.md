# sim300 / progress2wall — SOURCE_ONLY 测试与准入计划

Root已在source `c4ad853e7e5e8707a0e5a0be1426bc84b4bd2e1e` 下明确准入并完成唯一真实ROS窗口；native/Gazebo仍 execution_authorized=false。Root另已明确准入并完成下述纯AST/状态确定性单元；该有限范围不授权模型、ROS、native、Gazebo或构建。f03首败和旧wall300配置保持原件；不将新合同通过当旧合同通过。

授权上下文：2026-11-11 本会话用户明确选择“允许新计时配置，先验证”，Root据此准许另建sim300ms业务时效+2wall秒进度watchdog配置与轻量源码/确定性测试准备。本计划不是原wall300ms合同的静默放宽；模型/真实接口执行仍等Root固定源码与明确START。

新合同由用户明确批准：新profile业务health/mask收件时效用模拟时间300ms；另以单调wall时间2秒保护实际推进停滞。原source年龄、源频率、QoS、radio、singlewriter、10sim-ms quantum/20sim-ms credit、UUID/UNKNOWN语义不变。旧profile仍用原wall300ms，默认不切换。

## 最小确定性检查（无Node/ROS/native/模型）

复用 `net01/check_local_guard.py` 的fresh health/bound构造、`net01/followup04/check_time_control_state.py` 的actual纯状态、`check_time_hold.py` 的actual AST方法+controlled Future方法。不复制其整套框架，不在测试里重写Guard/watchdog。待生产接口确定后，唯一薄入口调用实际方法并注入独立sim/monotonic时钟；AST只负责避开ROS import，不能替换方法body。源码AST静态检查可先做，不报语义PASS。

| 检查 | 输入与必需断言 |
| --- | --- |
| 旧默认回归 | sim只前进.1s，wall前进.301s，原health或mask独立过期，仍按wall300 latch |
| 新合同慢速有效 | health/mask已arm；wall前进.6s而sim仅.2s；原source状态仍fresh、watchdog相关进度在2wall内；不因wall>.3误trip |
| 新health超期 | sim前进.301s，mask更新但health不更新，原source仍在.4/.55内；health receipt触发，不能靠另一流保活 |
| 新mask超期 | sim前进.301s，health更新但mask不更新；mask receipt触发 |
| 先tick旧区间 | 在旧health/mask的sim receipt age>.3后送来fresh后继；实际receive_*先检查旧interval并锁存，不能先覆盖再检查；新Goal/ARM不得清fault |
| sim停滞 | sim保持不变、wall超过2s；仅重复stamp/重复ACK不算真实进度；实际watchdog fault |
| native停滞 | 有实际physics/clock活动但native ACK不推进，wall超过2s；实际watchdog fault，不伪造native ACK |
| physics Future悬挂 | actualcontroller已issue唯一token，Future未done；wall超过2s必须fault，不能再issue第二token或把HOLD当成功 |
| HOLD/stop-observe | HOLD等待的原inflight Future与停稳观察都必须有原/新明确deadline，不能等待无界；authority未退出不可进入豁免状态；合法已收尾expected_shutdown不冒充运行中卡死 |
| firstfault/本地停止路由 | 真实生产fault入口必须到LocalStop；只看到TimeController.HOLD不能报安全通过。薄fixture可用实际LocalStop方法+call spies确认owned UUID cancel、zero、PAUSE请求被发出；spies不算DDS响应或physical stop |
| NetworkObserver实际peer_error入口 | 旧profile仍走原super wall300；新profile peer收件用sim300且仍调用原state_fresh。不得伪造peer_received或修改frozen Observer；只Guard单测通过不足以证明此入口已迁移 |
| 未授权wall门不动 | Peer snapshot的odom receipt .2wall与Gateway process-status receipt .3wall仍需分别拒绝旧状态；新sim合同不豁免它们 |
| preflight STOP_OBSERVE不永久撤权 | 原startup在尚未创建authority/未ARM时也会stop_motion→STOP_OBSERVE(True)；此时不能永久撤权后导致业务永不bootstrap |
| 已ARM正常撤权 | 已ARM且可信controller authority_exited之后永久撤权，实际cancel/zero/PAUSE请求；不发guard_fault、不把pending请求伪造terminal，后续RUN/新status不自动恢复权限 |
| 撤权后迟到accepted | 请求pending时正常撤权，随后真实accepted同UUID到达，仍必须发该UUID cancel；只检查guard.fault会漏掉无fault撤权，必须拒绝该回归。未真实终态前C端UNKNOWN |

边界使用.299/.301sim与1.999/2.001wall，避免float等号歧义；门限恰值按生产合同源码另列，不偷加epsilon。缺health/mask bootstrap不arm，不将未armed状态伪装运行中。新旧receipt clock、source clock和progress clock分别记录，避免把source .4/.55门限误当receipt300。

薄脚本入口：`rtk proxy python3 -B net01d/followup04/check_contract.py --output net01d/followup04/evidence/contract-03`。已按Root逐项源码补充执行：contract-01实际35项PASS，A0两override后contract-02为37项PASS；新增首见authority-exited HOLD后contract-03为38项PASS。旧结果均保留。首次启动因测试入口REPO.parents多一级在import阶段退出，尚无断言；`evidence/contract-01-launch-error.json`记录原错，修fixture路径后才执行。实际AST覆盖Guard/LocalStop/A0/Observer及TimeController方法，纯State和controlled asyncio Future；**尚非rclpy Future/真实DDS响应或物理停止证明**。

## 后续真实无运动准入（此时不执行）

首先在新source/profile独审后，复用原Full薄observer/fixture：old0cc serial、同13DSO，32wall normal/60wall hard、原3normal Goal结果4/4/5、第四tb3 accepted且GetResult ACK/pending后原.8wall实际RFoff。所有关键B业务实际走ns3；source epoch/actualmaps/ownedexit沿原门检。不得因新sim时效扩原60wall或重试。

RFoff后以实际native blackout→最后真实reassembly/当前sim为准：新合同在sim receipt age>.3或真实progress watchdog达2wall时锁存；保留首触发原因，不能预HOLD阻止sim时效过期。必须证实exact-owned UUID的实际cancel response/终态5、zero/PAUSE与本地cleanup；中央GetResult断链UNKNOWN原样保留，不能用local5填中央future。此为无运动接口/业务资格，不是机器人停稳证明。

真实progress卡死需Root另准一个独立episode，第一故障即停，不能塞入RFoff后已fault episode冒充第二验证。优先最小受控native ACK停滞或physics Future悬挂之一；具体故障注入位置/source和owned可逆收尾须先审。计龄记录必须来自生产watchdog实际单调时间：last真实进度、deadline、实际fault、LocalStop cancel/zero/PAUSE，不能人工直接trip或仅观察HOLD算通过。保留完整END/异常证据，host/whole界不延长，禁止自动再试另一类故障。

只有确定性合同、真实无运动正常业务与真实断链/进度停止路径获独立有限接受后，Root才决定新共同A0/A1/B/C及Gazebo准入。它是新时效合同/新基准，不能沿用旧wall300的科学对照标签。

## 真实domain95薄fixture（已完成唯一窗口）

`check_progress_ros.py`复用ControlledServer、LocalStop及Gateway.time_control_state实际fanout，不复制原check_local_guard整套测试。整体原30wall界；先做session61的normal-HOLD撤权/迟到真实accept，以及另一LocalStop真实paused ROS clock的2wall停止；再在同一隔离context做独立session62 noGoal TimeController组件。后者原TimeController Node与rclpy Future/真实HOLD RPC等待受控物理Trigger服务；单调2wall到期后实际响应false且inflight保留/0nativeACK/1token。仅观察完成后给受控物理服务一个真实false响应收尾，不伪造成功ACK。session62的native READY/网关发现条件明示为fixture控制输入，0ns3，不冒充真实native进度卡死。

真实Rclock故障读取latched_INVALID保存的**旧**progress_context：last_sim_progress_wall、control_receipt_monotonic、last_sim、receipt_sim及mode/failure；不以事后新快照覆盖计龄。重复admin是真实DDS接收，synthetic health/bound只是受控输入，正常撤权不发guard_fault；两场景均需实际sameUUID取消/本地GetResult5/zero/PAUSE成功。夹具不创建跨网络C端future，故不声称C已收到5；原Full断链仍必须独立报告UNKNOWN。

原check_local_guard默认回归与新fixture各一次，顺序执行，域95必须先空；无机器人/模型/其他timed工作。沿已有rootfs/ROS2 FastRTPS env-i封套及actualowned清理，内部精确入口如下（外层每例35wall，夹具自身30wall；超界真实FAIL，不重试）：

```sh
python3 -B net01/check_local_guard.py --output net01d/followup04/evidence/legacy-ros-01
python3 -B net01d/followup04/check_progress_ros.py --output net01d/followup04/evidence/newprogress-ros-01 --ack-socket /dev/shm/net01d-f04-progress-ros-01.ack
```

新output/ack socket须不存在。Root pin源码/明确START后已实际依次运行两个入口；原件中的实际输出名为legacy-ros-01/newprogress-ros-01（下方结果为准）。该窗口不安装依赖、不build、不启动Full/native/Gazebo；后续资格仍需另准。A1/B Full false准入和薄observer现交pace producer独占维护，不再由本producer修改。

### 实际唯一ROS窗口结果

- 原default `legacy-ros-01`：14checks PASS，exit0，outer2.181373840wall；pausedClock原wall300仍触发，精确ownedUUID实际cancel/GetResult5，原foreignUUID不误取消。
- 新 `newprogress-ros-01`：16checks PASS_CONTROLLED_ROS_ONLY，exit0，outer6.153309443wall；夹具内部4.275773312wall，原30wall尚余25.724222412。tb1真实Rclock固定100sim，按旧progress_context计龄2.002234446wall故障；最后admin receipt只早21.461574ms，故非admin丢失假冒clock卡死。tb2已ARM首见authority-exited HOLD正常撤权不发guardfault，真实accepted迟到后精确UUID取消。两者均actualCancel return0、matchinggoals_canceling、localGetResult5、PAUSEsuccess、接收全零cmd_vel。
- session62实际TimeController/rclpyFuture/HOLD RPC：2wall physicaltimeout后HOLD响应false，原物理Future仍notdone，inflighttrue/nativeACK0/physical_nsnull/仅1服务调用；issue→观察HOLD响应2.003915807wall。记录该证据之后才以受控服务false响应收尾，firstphysics_RPC_wall_timeout保留，没有伪ACK。
- 两例观察到的owned进程最终均gone，无强制信号；ack socket已由原close删除。没有启动native、Gazebo、机器人或NN，controlled PAUSE不等于物理停稳证明；没有跨网络C future，不冒称中央UNKNOWN已恢复。

实际argv、launcher/observed PID+startticks、stdout/stderr、GNUtime、exit保留于 `evidence/{legacy-ros-01,newprogress-ros-01}.*`；原result与TimeController记录在对应目录。小汇总 `evidence/ROS_LOCALSTOP_WINDOW_RESULT.json`。没有重跑或生产源码修改；新profile Full/native/GZ尚未执行。

实际原始来源（原计划名progress-ros-01没有执行/创建；不是测试失败）：

| case | 原result | 原launch/实际完整argv | 原exit/owned | stdout / stderr / time |
| --- | --- | --- | --- | --- |
| legacy-ros-01 | [result](evidence/legacy-ros-01/result.json) | [launch](evidence/legacy-ros-01.launch.json) | [exit](evidence/legacy-ros-01.exit.json) | [stdout](evidence/legacy-ros-01.stdout.txt) / [stderr](evidence/legacy-ros-01.stderr.txt) / [time](evidence/legacy-ros-01.time.txt) |
| newprogress-ros-01 | [result](evidence/newprogress-ros-01/result.json) / [actual TimeController](evidence/newprogress-ros-01/time-controller.json) | [launch](evidence/newprogress-ros-01.launch.json) | [exit](evidence/newprogress-ros-01.exit.json) | [stdout](evidence/newprogress-ros-01.stdout.txt) / [stderr](evidence/newprogress-ros-01.stderr.txt) / [time](evidence/newprogress-ros-01.time.txt) |

外层实际命令为各launch.argv：`/usr/bin/time -v -o <case>.time.txt timeout --signal=TERM --kill-after=2s 35s bash net01/ros-python.sh <上述实际Python入口及参数>`；工作目录为实际repo。原wrapper使用env-i及内部ROS环境，脚本明确rclpy.init domain95覆盖wrapper环境92；未改变wrapper。小汇总：[ROS_LOCALSTOP_WINDOW_RESULT.json](evidence/ROS_LOCALSTOP_WINDOW_RESULT.json)。

## 启动激活边界回归（source2be7；含已完成ROS增量）

GZA1-02暴露global RUN含未ARM启动期。Root固定最小state/controller修补为 `2be7e229492d29817057fa8db166e38f114ca209`：globalclock/native从实际同session任一R Guard ARM开始一次激活，baseline取首次ARM与真实progress的max，重复status/HOLD→RUN不续期、不清fault；physicsRPC2wall所有mode、LocalStop2wall、startup180均不变。

`contract-04`已在生产者最终SOURCE_READY bytes上实际执行一次，**49项PASS**，Rootpin随后报告；[result](evidence/contract-04/result.json)/[source-context](evidence/contract-04/source-context.json)。增量覆盖无ARM clock/native gap>2而RPC<2不误fault、token不伪写实际stamp、actualgateway ANY1ARM一次/max基线、重复状态及HOLD→RUN不延期、late clock/native/physical ACK不洗掉旧故障。不是模型或真实DDS验证，不重复已有case凑数量。

`check_progress_ros.py`仅准备最小新增实际DDS差分：受控Gateway status含真实结构guards，False→**仅tb1 armed=True**，实际TimeController.gateway原方法调用一次后才记fixture观测；再次真实DDS同status必须有接收观测且activation event仍一次、baseline与actualclock/native stamps原样。原LocalStop正常撤权/2wall真实cancel与物理Future2wall/HOLDfalse机制保留。START前该增量仅AST parse/NOT RUN，独占输出/ack拟newprogress-ros-02，原30wall/35wall界；Root固定fixture并START后的实际结果见下一节，未重跑旧例或启动native/GZ。

### 已完成唯一newprogress-ros-02增量

Root固定fixture `82edafe4570a4b98cb5e3d02eaf6f34a11b00fae`、runtime2be7并明确START后，上述待准入项已实际执行一次；**19checks PASS_CONTROLLED_ROS_ONLY，exit0/outer6.060200665wall**，没有重跑legacy。内4.258456364wall，原30wall尚余25.741539472。

实际DDS三次callback为guards全false→仅tb1true→重复tb1true；首次ARM基线605599181087317，重复保持原值。实际clockstamp三次均605599177894681、nativeStamp均None，callback前后原样。LocalStop实际Rclock停滞2.001259230wall后同UUID取消/GetResult5/PAUSE成功；正常HOLD撤权迟到accepted同样正确取消。真实物理Future/HOLD在2wall后失败，1调用/inflighttrue/nativeACK0/physicalnull，未伪ACK或清首故障。

原件：[result](evidence/newprogress-ros-02/result.json)、[小汇总](evidence/newprogress-ros-02-summary.json)、[launch/实际argv](evidence/newprogress-ros-02.launch.json)、[exit/owned](evidence/newprogress-ros-02.exit.json)。观察owned全部gone，ack已清；0native/GZ/robot/NN、无activebag访问。真实C网络Future未创建，不声称中央结果闭合或物理停止。新lifecycle的Full/GZ仍未执行，此有限结果不自动授权后续模型。

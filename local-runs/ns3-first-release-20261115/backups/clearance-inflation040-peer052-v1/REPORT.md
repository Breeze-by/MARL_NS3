# ROS直连导航间距参数试验：两图各三次

2026年11月15日。本批将Nav2两层膨胀半径从0.55m改为0.40m、peer半径从0.55m改为0.52m；机器人半径保持0.25m。**走廊3/3达T95，房间1/3达T95；未呈现普遍加速或稳定改善，因此保留为显式试验配置，不替换旧默认配置。**

## 运行与评价合同

六个预声明任务按走廊b1、房间b1、走廊b2、房间b2、走廊b3、房间b3执行。两图复用各自已有场景与离线reference，physics seed为2026111301–1303；原native seed2026110901/run1–3仅用于共同clock/control，业务为literal A0直连（R92），无Wi-Fi业务、无新增代理延时。固定PPO权重及701维结构、repair-v1候选几何/Goal guard/Nav2 simclock均保留。

每窗G20→G140、120sim；原10sim-ms/40wall-ms节拍、约0.25RTF、23个G25..135预定决策边界，以及source .70/.85sim、receipt .60sim、producer .50sim、原停止/UUID/copy门保持。只使用原质量有效中央应用callback T95；不使用消息header作到达时间。未达保留null，不用120代填T95。

全部六窗四个实际进程的peer_keepout/business_peer半径和producer copied binding均为0.52m；三机六个inflation键均为0.40m，robot_radius=0.25m、cost_scaling_factor=3，前后YAML核对仅发生预定修改。原7工程门、窗口/全工程/clean/stop/UUID/owner/copy资格六窗均通过。首例a01后工程与参数审查不依T95成绩筛选，其后按原序完成。

## 六轮结果与预选历史参考

历史列是上一独立ROS-delay V3中同地图、block和seed的A0结果，预先选定b1–3，没有从旧五次中选择成功样本。它不是同期随机对照，不能将差值认定为参数的因果效果。覆盖是最后实际中央观测样本，不伪称恰好G140的样本；T95是首次质量有效达95%的时间，之后覆盖值可能回落。

|地图/block|新物理例 / 旧例|新T95 / 旧T95（sim-s）|新末覆盖 / 旧末覆盖|新/旧hazard|
|---|---|---:|---:|---|
|Corr6201/b1|a01 / f001|69.17 / 60.51|99.8393% / 99.8200%|均为null|
|Rooms6101/b1|a02 / f010|未达 / 未达|91.1144% / 94.1012%|均为null|
|Corr6201/b2|a03s / f026s|72.76 / 44.24|97.9432% / 99.8907%|均为null|
|Rooms6101/b2|a04 / f021s|85.35 / 116.85|99.8702% / 97.2802%|均为null|
|Corr6201/b3|a05 / f033|75.26 / 85.34|99.8650% / 99.8843%|均为null|
|Rooms6101/b3|a06 / f037|未达 / 85.05|62.4763% / 97.9763%|均为null|

目标计数按原小result的不同UUID状态记录列示：EXECUTING为已实际执行；成功/取消/中止分别是实际Nav2终态4/5/6。取消不等同于任务未达，中止不等同于物理碰撞。

|地图/block|新执行/成功/取消/中止|旧执行/成功/取消/中止|
|---|---:|---:|
|Corr6201/b1|12/12/0/0|12/12/0/0|
|Rooms6101/b1|13/9/4/0|13/10/2/1|
|Corr6201/b2|12/11/1/0|11/11/0/0|
|Rooms6101/b2|15/12/3/0|14/11/3/0|
|Corr6201/b3|12/11/0/1|13/11/2/0|
|Rooms6101/b3|14/8/3/3|15/13/2/0|

## 按地图汇总

均值±样本标准差的单位是独立运行，不是消息样本。只有三次全部达标才给三次T95均值；达成者均值单列并注明n，不能据此给房间方案排序。

|地图|新达标/明确未达/未知|新全三次T95均值±SD（s）|新达成者统计（n）|新实际末覆盖均值±SD|历史同三block达标|
|---|---:|---:|---:|---:|---:|
|Corr6201|3/0/0|72.3967 ± 3.0612|72.40（n=3）|99.2158% ± 1.1022个百分点|3/3|
|Rooms6101|1/2/0|N/A|唯一达成者85.35（n=1）|84.4870% ± 19.5581个百分点|2/3|

走廊新均值72.3967s，历史同三block均值63.3633s；逐对差值为+8.66、+28.52、−10.08s。房间b2从历史116.85s变为85.35s，但b1仍未达、b3从历史85.05s变为未达。总体证据不支持“新配置普遍更快”。

房间两次未达并非仅中央收图滞后：a02的local/C/R三视图T95均null，末覆盖91.2017%/91.1144%/91.1144%（最后观测G139.14/139.15/139.15）；a06亦均null，62.5661%/62.4763%/62.4763%（G139.27/139.28/139.28）。这些末点质量均有效；未追加机制诊断，不能将低覆盖唯一归于peer参数、某次Nav2中止或通信。

## 失败分母与边界

本批实际HOST_STARTED共7次，得到6个完整合格自主窗口：覆盖达标4、明确未达2、未知0；全工程/clean为6/7，不能写7次全PASS。原a03在无RUN/自主/HQ/NN/Goal时发生本地Gazebo spawn响应发送超时；observed_stop=true，但PAUSE、run_integrity及seal资格失败。54个记录actor和host实际退出、495923B原证据完整复制，不会升高其停止资格；原READY/BLOCK/raw/RAM保留。Root通过[AM1](STARTUP_SUCCESSOR_AMENDMENT01.json)仅授权同seed的fresh a03s，原a03计入启动可靠性分母、T95为N/A_NO_AUTONOMY，不当120sim未达。启动缺失不假定随机，也不是通用重试许可。

本批只评估这一组联合参数，无法拆分inflation与peer半径各自贡献。旧同seed参考也受历史执行时机影响。原contact订阅回调数包括空状态消息，不能当作碰撞数；六窗hazard均null只表示已有base_collision接触/中心距离监测未报hazard，不是完整碰撞安全认证。保持旧默认，不训练、不新增试验、不生成新PDF/图表。

## 权威来源

- [预声明计划](PLAN.draft.json)、[共同源码与方法身份](COMMON_BINDING.json)、[26项组件结果](RUNTIME_RESULT.json)。本批81项运行源码身份与9项离线方法固定；旧ELF/13DSO/PPO/world身份继承，未重新构建。组件是纯函数/截断实际Launch入口检查，实际四进程生效证据来自六窗原post-case proof。
- [原自动汇总](SUMMARY.json)、[六条历史参考](HISTORICAL_A0_REFERENCES.json)、[原启动失败登记](STARTUP_FAILURE_REGISTER.json)、[AM1](STARTUP_SUCCESSOR_AMENDMENT01.json)、[最终执行闭合](FINAL_EXECUTION_CHECK.json)。所有旧通信70/40批和原始数据保持独立、不池化。
- [实际Nav2终态与原运动小指标表](NAVIGATION_OUTCOMES.csv)及[对应JSON](NAVIGATION_OUTCOMES.json)保留各例原字段；路程/中心距离为原观察区间统计，不伪装成重新积分的严格120sim指标。
- Root已接受[最终执行闭合](FINAL_EXECUTION_CHECK.json)：7次实际启动、6完整合格窗口、403个已记录PID实际退出、7份copy完整；原a03停止失败资格不升。
- 本报告只复核既有row/proof/result和原T95小JSON；未重算覆盖/传输指标，未读取bag/native大ledger。

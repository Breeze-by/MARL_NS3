# 探索修复基线：单例有界验收

2026-11-13。唯一B例`local-runs/er13/a`，session2026111373。已完成并获根审验收；没有追加案例。

|项目|实际结果|
|---|---|
|中央Gateway主T95|43.17sim秒（绝对G63.17，首次有效样本覆盖97.024%）|
|local最新图并集 / R收件T95|43.15 / 43.18sim秒|
|相对60附近中央实际样本|59.44sim，覆盖98.978%；下一样本60.54同值，无插值|
|末中央/R / local覆盖|99.6529% / 99.7622%（实际末样本，非恰好120秒）|
|评价样本质量|每视图289；local有效289/无效0，C/R有效269/无效20（早期alignment p95警告）；无raw≥95却质量无效，无missing|
|实际运行与停止|120sim / 479.999840wall秒；原simulation_budget停止，非在线T95早停|
|原定节拍资格|RTF0.249999836；12000token，迟到p95=2.575wall-ms，>40ms为10/12000=0.08333%≤1%；最大214.623ms仍保留|
|决策与目标|23槽实际G25..135，sim lateness全0；23次forward/701结构保留，16目标全接受、12成功、1Nav2中止、3预算取消；全部闭合|
|停止、网络、复制与退出|原门通过；已知owner/writer全部退出，native复制6,348,446,912B<8GiB，磁盘raw完整保留|

T95在43.17sim已达，早于原60sim窗口，本次不是延长到120才凑达标。但这是三个变更合并后的单例新行为基线，未做消融或重复统计，不能分摊每项修复的效果，也不能与旧RF组混算收益或称无线因果已证。

三项修复及生效范围：

1. `nav2-simclock-common-v1`仅补实际启用Nav2节点的sim clock。真实installed behavior_server Wait组件已验证暂停/推进语义；本例三机生效YAML七节点均true、其余值保留。未逐节点做运行中GetParameters采样，不冒称该边界已测。
2. `nav2-circular-footprint-v1`把旧7格方形硬膨胀换成圆footprint一致的保守grid-centre几何（R=.25m，R+res/√2=.285355m）。本例实际调用23次，0WAIT、0action_rejected、没有idle且合法候选为0；原权重/701结构和其余peer/任务门保留。新候选语义是显式行为版本，不改写旧结果；连续/动态路径仍由Nav2校验。
3. `navfn-round-active-goal-v1`按实际Goal的map-frame点/原token/UUID与鲜度≤2sim的own-map判断明确100，走原真实取消/终态链；unknown/stale不触发。真实ROS Action组件通过。本例assignment rejection=0、active cancel=0，主动分支未触发，不能声称在ns-3集成运行触发或解释了本例性能。仍有1次Nav2 abort，未证明导航失败彻底消除。

所有业务仍走原d53 ns-3 B Wi-Fi，MCS9/16dBm/指数2；无训练、压缩、理想业务补交或新RF组。固定G20与原5sim cadence，120预算、serial RAM8+2GiB和host1100/Hub1120为独立合同；在线不读bag/ledger/指标。停后只一次三视图T95，原始历史与失败保留。

本task唯一`/dev/shm/er13-a`已依据现有copy/owner证明释放，见[a.RAM-release.json](a.RAM-release.json)；其他RAM未动。

证据：[总小件](RESULT.json)、[T95及60段](a.T95-summary.json)、[原节拍](post-exit/a-pacing/result.json)、[实际修复边界](post-exit/a-runtime-repair/result.json)、[候选/forward](candidate/repair120-actual-candidates.json)、[72路径绑定](COMMON_BINDING.json)。原始运行目录为`../er13/a`及`../er13/a.network`，本机结果不等于随Git完整发布的数据包。

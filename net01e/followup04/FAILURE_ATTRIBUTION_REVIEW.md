# common58 六例：任务失败与 T95 的独立边界审查

**两次真实 raw6 的终态都在本例 T95 后：A1-r2失败Goal从请求起就是post-T95，B-r1失败Goal则跨越T95；缓存首条失败候选文字也均晚于阈值。六例没有任务超时，且“无任务失败”仍可以较慢。因此不能用失败次数单独解释 T95，也不能由这六例认定 RF 或新的 Nav2 bug。**

本审先读六个已关闭 case 的 `metrics.small-result.json`、`uuid-summary.json`，此次只增量读取生产者一次提取的 [TWO_RAW6_HANDOFF.json](event-cache/TWO_RAW6_HANDOFF.json)、[FIRST_OBSERVATIONS_AND_LONG_TAIL.json](event-cache/FIRST_OBSERVATIONS_AND_LONG_TAIL.json)及 [CACHED_GOAL_TIMELINES.json](CACHED_GOAL_TIMELINES.json)。没有重读原journal、bag、Gateway、native/controller ledger、模型，没有新测试/ROS/Gazebo、源码修改、Git或hash。A1-r1采用实际成功的`corr6201-common58-r01-a1-fresh02`；原未执行完整case不替换成成功、不混入以下六例。旧A1-04 timeout详见 [A1_TIMEOUT_REVIEW.md](A1_TIMEOUT_REVIEW.md)，本文不改该历史审查。

## 逐例事实

所有G均为该回合原绝对sim钟；T95elapsed以各自原autonomy start为零点。六例均180sim预算结束、`natural_completion_verified=false`、observed_stop=true；过程PASS不表示每个任务成功。

| case（简称） | 原自主G起点 | T95 elapsed / receipt G | owned UUID | raw4 / raw6 / raw5 | 高层任务超时 | 初始raw覆盖 |
|---|---:|---:|---:|---:|---:|---:|
| r1 A1 fresh02 | 18.73 | 39.46 / 58.19 | 11 | 11 / 0 / 0 | 0 | 11.2868% |
| r1 B | 16.13 | 35.61 / 51.74 | 11 | 10 / 1 / 0 | 0 | 11.0297% |
| r2 A1 | 18.30 | 62.25 / 80.55 | 12 | 11 / 1 / 0 | 0 | 11.0683% |
| r2 B | 16.93 | 40.42 / 57.35 | 10 | 10 / 0 / 0 | 0 | 11.0297% |
| r3 A1 | 18.11 | 72.01 / 90.12 | 11 | 11 / 0 / 0 | 0 | 11.1389% |
| r3 B | 15.40 | 48.68 / 64.08 | 9 | 9 / 0 / 0 | 0 | 10.9911% |

原小件位置为 `gz-analysis/<上述完整case名>/metrics.small-result.json` 和 `uuid-summary.json`。r3B canonical已实际生成，本审采用48.68，不保留“待出”占位。共64 owned UUID、62 rawSUCCEEDED(4)、2 rawABORTED(6)、0 rawCANCELED(5)；各例ownership_closed=true、record_errors为空、各机unterminated_UUIDs为空。canonical各机`timeout_cancel_dispatched`、`timeout_terminal_failures`均为0。没有将status6清洗为成功，也未将总体正常退出改为任务全成功。

## 两个 raw6 的原身份和时序

| case / robot / token | 原 UUID | 原logical terminal | 本例T95 G | terminal−T95 |
|---|---|---|---:|---:|
| r1 B / tb3 / 3 | `478a3297a9a5411db34cdfe71fea106e` | G72.08，aborted；raw history 2→6 | 51.74 | +20.34sim |
| r2 A1 / tb2 / 4 | `c29f5979f42448948a121afe6456b43d` | G117.90，aborted；raw history 2→6 | 80.55 | +37.35sim |

二者均是原Nav2 raw6，不是自身timeout导致的raw5→高层aborted。新增handoff给出以下实际request/response/result时序，不用allocator缓存时刻倒填接受时间：

| Goal | reservation / request G | accepted response G | T95 G | 原raw6 result G | 关系 |
|---|---:|---:|---:|---:|---|
| B-r1 tb3 token3 | 50.00 / 50.00 | 50.46 | 51.74 | 72.08 | T95时实际已接受、仍活动；不能把整个Goal排除在T95前负载之外。 |
| A1-r2 tb2 token4 | 85.00 / 85.00 | 85.53 | 80.55 | 117.90 | 从开始即post-T95，其后失败不能导致此前T95变慢。 |

B-r1这条Goal在G50—51.74的已有世界评价样本中路径约.255m，非仅无活动占位。缓存首条Nav2失败候选是planner potential→plan错误，原logger wall1794490929.754505、按轨迹wall/sim插值约G53.852，**晚于T95**；A1-r2首条候选规划失败约G94.275，也晚于其T95。这里只能说在这些已缓存候选中未见这两Goal的T95前明确失败文字，不能证明更早不存在未记录的内部困难或传递影响。handoff中的UUID字段是提取关联键，原日志仍没有Goal UUID；robot+时间/目的点上下文不能强唯一绑定底层原因。

旧A1-04另有token4自身timeout：T95 G80.50，Goal从G85开始，G180.46原raw5并高层classified aborted，后继token5预算取消。它的**整个Goal从开始即post-T95**，所以不能解释旧例T95差；它不属于本次64 UUID和两次raw6，不混入新六例失败率。

## 无失败仍慢：可排除什么，不能排除什么

- A1-r3所有11 UUID raw4、无任务超时，T95仍为72.01，比A1-r1的39.46慢32.55sim，也比带一次raw6的A1-r2的62.25慢。**“一次任务失败是本组慢的必要条件”已被反例否定**；不能以任务全成功等同效率稳定。
- B-r1有一次raw6，却是本组三例中最快的35.61；B-r2/r3没有失败仍为40.42/48.68。终态失败次数不是T95的充分解释，也不支持“Wi-Fi使失败更少/让探索更快”。
- 没有高层失败不代表每个Nav2内部plan、FollowPath或恢复都没有错误，也不代表到达之前没有绕行、等待、旋转和低平移段。相反，出现raw6也不证明RF、目标帧、地图残影或某一个导航实现独因。当前小件没有这些完整内部阶段。

## 已知输入/计时差异与缺口

原起点G和初始raw覆盖如表所示，数值并不完全相同。此次首观测缓存进一步给出首次实际NN所记录的shared-map metadata、robot状态、候选/条件mask与首Goal；初始quality flag仍不从不存在的小字段补造。相同raw覆盖（例如B-r1/B-r2）不证明相同栅格图、TF、机器人状态或完整701向量；不同覆盖也不能直接解释几十sim差额。

| case | 首NN G / 距T0 sim | 候选数 / conditional options | 原首choices | shared header age / 已知面积m² |
|---|---|---|---|---|
| r1 A1 fresh02 | 25 / 6.27 | 6 / [1,2,1] | [0,4,5] | 1.979s / 5.8850 |
| r1 B | 20 / 3.87 | 7 / [2,2,1] | [0,3,6] | 2.280s / 5.6275 |
| r2 A1 | 25 / 6.70 | 5 / [3,1,1] | [1,3,-2] | 2.300s / 5.6700 |
| r2 B | 25 / 8.07 | 7 / [2,2,1] | [0,3,6] | 2.340s / 5.6450 |
| r3 A1 | 25 / 6.89 | 8 / [2,2,1] | [0,5,7] | 2.486s / 5.7125 |
| r3 B | 20 / 4.60 | 7 / [2,2,1] | [0,3,6] | 1.738s / 5.6075 |

这些是**实际记录的观察/资格和动作差异**，不是“同参数意味着同输入”的假设。例如A1-r2首choices包含原WAIT=-2，tb3的首次dispatched ownership到G35才出现，而首NN是G25；不能把缓存的“首三个请求”（其中可能有另一机器人第二个请求）当成三机同时出发。B三例即使choices索引相同，tb3首目标也从r1/r2的(.875,-1.825)变为r3的(.675,-1.775)；候选索引/进程内map_version不是跨回合同一物理对象。以上没有读取NPZ并逐值比较完整701向量，不能量化哪个特征唯一造成选择差别。header age含建图/融合最旧stamp、发布/排队/传输/取件，不是纯网络延迟或已证过期bug。

原世界评价轨迹缓存的T0→本例T95路径/采样静止估计进一步显示执行不同：

| case | 三机路径m（tb1/2/3） | 三机stationary估计sim s |
|---|---|---|
| r1 A1 | 4.952 / 5.359 / 4.899 | 9.8 / 10.9 / 9.1 |
| r1 B | 5.063 / 5.471 / 4.716 | 5.8 / 5.8 / 6.2 |
| r2 A1 | 6.206 / 10.364 / 3.375 | 21.6 / 11.6 / 29.7 |
| r2 B | 5.063 / 5.028 / 4.483 | 10.7 / 9.8 / 10.8 |
| r3 A1 | 8.138 / 9.881 / 11.921 | 23.6 / 17.4 / 15.0 |
| r3 B | 5.700 / 5.757 / 7.877 | 13.1 / 13.0 / 6.6 |

路线窗口长度随T95而不同；更长路径/更长stationary既可能影响到达，也可能仅因观察得更久，不能将相关表当原因分解。三机区间重叠，不把stationary相加冒充全任务停滞时间。轨迹是已录Gazebo样本、端点最多约.1sim采样误差、不外推；静止估计不是连续无运动证明，GT仅评价，不进入策略。T95后到T98还有另一长尾（例如B-r1为90.97−35.61=55.36sim、A1-r2为112.26−62.25=50.01sim），不能混入T95前损失或用终态截尾掩盖。

已存主窗wall不同：A1约359.98–359.99s，B约408.08–420.46s；在共同sim推进配置下，这意味着wall反馈/应用计时每sim的实际负荷可不同。这里仅披露原观测跨度，不分配为纯RF成本，也不从两组T95差减某个网络p95得到“算法开销”。共同参数/seed不消除ROS调度及动态输入差异。

此次只复用生产者已完成的一次缓存，没有要求第二遍原件扫描。首观测/资格/首目标不同与路线不同均有记录；“哪一个差异导致多少T95”仍未闭合，不因Goal不同认定RL错误。没有因果回归、p值、删去失败后的均值或新测试建议。

**更新后的独立判断：** 两raw6及生命周期真实闭合；A1-r2失败Goal全在T95后，B-r1则跨T95但缓存首失败候选晚于阈值，二者须分开。无失败仍慢、首观察/候选/资格/出发与路线不同有具体反例，足以否定“失败计数单因解释”。这些证据尚不足给各机制的独立T95贡献或签无线/新Nav2Bug唯一根因。保留所有正常但较慢的回合，不追加运行来重证这些已存事实。

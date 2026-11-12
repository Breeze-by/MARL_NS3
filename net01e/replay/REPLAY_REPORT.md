# NET-01E 无运动真实记录回放子报告

**结论：BLOCKED / NO-GO；同源B/C与本轮Gazebo均未运行。** 已完成一次有限真实CDR提取和三次获Root逐项准入的A1尝试；首例新host启动顺序错误，后二例在真实原Gateway/BoundPeer链中因校正源龄越界正确停止。没有已证可直接最小修复的原Gateway源码bug，因此停止新实验，不降源率、刷新header、改安全期限或引入优先级。

生产源、冻结RL/Frontier/SLAM/Nav2/评价/物理与安全参数未改。新sim300与独立2wall沿原实现；旧wall300限制仍保留、未修。本目录是新诊断夹具，不是已验收完整平台；无训练/NET-02/推送。

## 来源与版本

起点Root指定`78bf29c1398efb6df03238a93be17325a65c9652`。真实源为封存B02 `net01d/followup04/runs/gz-simhealth-b1-02/bag/bag_0.db3`的50..60sim原CDR，另取同case C89原`central-map-capture`同窗记录。只连接该DB一次、只取批准话题/初始化记录，不读第二shard/旧GB Gateway/ledger/PCAP，不换窗。

| 项目 | 实际值 |
|---|---:|
| 提取wall | 0.665586098s |
| DB连接 | 1 |
| 原CDR bytes | 6,051,069 |
| 原库存normal/prelude | 15,115 / 12 |
| 原库存总记录 | 15,127 |
| 实际外生源normal/prelude | 7,263 / 9 |
| 实际外生源PLANNED总母数 | 7,272 |

外生源仅原R18流（map/odom/tf/tf_static/local costmap/cmd_vel各三机）及原C89。历史feedback/status/health/filter仍保存库存，**不向新活跃Action同名注入**。原BoundPeer真实计算/发布新mask/health；原ActionWire与ControlledServer及typed ActionClient生成新协议业务，明确不是历史完整双向流复原。

真实片段每机TF1649条：map→odom1255、odom→base_footprint294、双wheel100。每机TF edge+stamp唯一445，重复额外1204（73.01%），并未删重；相同edge+stamp不证明相同body或同一publisher。原bag无writer GID，本source用每机一个TF publisher，不能称精确恢复原多writer拓扑。

原B02自主全phase RTF=.423380（已有costs摘要）；本片段按共同1x目标模拟节拍重播会提高含wall定时源的wall负荷。**原50..60sim片段精确wall RTF未测**，不能用全phase值替代，也不能把新条件下服务不足直接写成旧生产bug。

## 全部实际尝试与母数

| 例 / Root源pin | 实际结果 | 外生源planned / published / 未发 | wire尝试数 / body bytes |
|---|---|---|---|
| collect-01 / 0b471a846bd7f484afa67fbb8320452beab0af58 | host1，4.916700745wall；新host先Hub后coordinator导致step.sock未bind | 业务未启动，源计划文件未创建；不能填零成功 | 未开始采集 |
| collect-02 / a5219a09e11878431111561c25000b6201c45d9c | host1，15.205110866wall；51.73sim原health_original_sources_stale | 7272 / 1293 / 5979 | 1301 / 14,674,456 |
| collect-03 / 271abb817ccffe162026fdf01673e258ef888c9d | host1，14.730952296wall；51.33sim原bound_mask_original_sources_stale（tb3健康同源过期） | 7272 / 977 / 6295 | 973 / 12,436,909 |

collect01只启动域独占probe与Hub/native；Hub1，native按原error-finalize END实际0退出，无强杀。最小修正只恢复原harness依赖：coordinator实际READY/bind后再Hub；原失败原件保留。

collect02/03全部7272原CDR在启动READY之前真实typed deserialize通过，实际publish仍为原bytes、未重写header。域91/92独占门与实际old0cc/native唯一子进程/exe/parent/13DSO maps门通过。两例coordinator1/Gateway1，其余Hub/Peer/servers/source/client/mock clock均0，native实际0，forced=[]；Gateway资源close为clean=true，但整体业务FAIL。

两例固定52sim三个Goal和55sim tb3 Cancel均仅PLANNED、未提交，0accepted Goal/feedback/成功/运动。client退出0只说明资源退出，不能当Action资格PASS。逻辑4条计划独立于7272观测母数；动态Action readiness/Link等与新BoundPeer源也独立计wire尝试。

A1业务通过原Gateway direct适配；Hub的native ingress/delivered均0，仅供原控制时钟推进。实际加载ns-3库不等于这些A1业务经过Wi-Fi。B/C同源全业务、TCP重送/无线交付统计、断链恢复和新Gazebo均NOT RUN。

源发布→wire只做(flow,CDRhash)多重集对账：collect02未匹配868/额外876，collect03未匹配656/额外652。存在相同内容重复、其它cmd_vel零写端、新动态源、pending以及尚未逐条核定的CDR重序列化表示差异；**这些数不构成永久源丢失或无线loss率**。同一source PLANNED/PUBLISHED与独立wire全输入母数保留，未匹配项没有被排除出分母。

## 源龄与本地滞后的直接证据

collect02最后Peer health seq28/generated51.7/readytrue；odom51.68/51.68/51.685，校正51.16/51.161/51.18，R health/mask receipt51.71。51.73时tb1/2校正源龄.570/.569>.55，原保护正确触发；不是300sim-ms收件超期。

首fault mono620765612676904ns之前，外生源已发布原校正stamp51.76/51.761/51.78（原record与本次发布sim51.74，mono约620765611.4ms）。同窗Gateway R最新取件仍51.36/51.36/51.18，C发布与Peer callback迅速处理对应旧值。故片段存在新鲜校正，不是未录到必要校正；滞后主要在源发布→Gateway R取件段，而不是A1无线。

collect02在首fault前TF capture201/200/201，相同key语义配对的source→capture p95下界489.063/494.515/484.839wallms、上界628.220/639.951/624.674ms；重复edge+stamp保留候选区间，不当精确packet身份。odom对应p95仅19.923/23.723/27.606wallms。全保存窗口含fault后尾的TF最终capture210/209/210，不与首fault前cohort混用。

## collect03唯一RMW元数据分解

复用既有`MetadataSingleThreadedExecutor`的同一次native take，无额外take或新SDK补丁。共有441实际take（每机147），441非零、时序有效元数据；以下为**全部保存take，含首fault后有界资源退出尾**，不是全输入loss母数。

| wall ms；每机n=147 | tb1 median / p95 / max | tb2 median / p95 / max | tb3 median / p95 / max |
|---|---:|---:|---:|
| RMW source→reported received | .031808 / .091099 / 2.382663 | .029371 / .088609 / 2.312807 | .031302 / .099399 / 2.413361 |
| reported received→take-before | 255.877829 / 514.588955 / 537.029868 | 256.973292 / 516.065698 / 537.971674 | 258.064441 / 516.769538 / 538.863292 |
| source→take-before | 255.903760 / 514.614980 / 537.060866 | 256.999641 / 516.088241 / 538.000831 | 258.100485 / 516.792593 / 538.926745 |
| take自身wall | .286970 / .376191 / .766614 | .214415 / .325825 / .406489 | .208802 / .304328 / .408481 |

大段等待发生在**RMW报告received时间之后、实际take之前**；不是该次take函数运行数百毫秒，也不是本次A1无线服务。received→take-end p95为514.947115/516.251915/516.952055ms。realtime与mono读取bracket宽度max44.617/25.893/19.697µs，不能将约0.5s差解释成该采样bracket误差。

另按**首次实际fault mono621434652035878ns之前开始take**切分已有pairs，原all-window文件不覆盖：故障前411条（每机137），故障时/后30条（每机10）。[独立故障前摘要](collect-03/take-pre-fault-summary.json)来自同一已保存小JSON，不是新实验。

| 故障前wall ms；每机n=137 | tb1 median / p95 / max | tb2 median / p95 / max | tb3 median / p95 / max |
|---|---:|---:|---:|
| RMW source→reported received | .032145 / .091269 / 2.382663 | .029537 / .096972 / 2.312807 | .031302 / .122689 / 2.413361 |
| reported received→take-before | 243.563357 / 482.319088 / 491.881793 | 245.573149 / 480.617546 / 493.788150 | 247.984333 / 485.179706 / 495.502534 |
| source→take-before | 243.617100 / 482.354312 / 491.915233 | 245.609355 / 480.649450 / 493.817666 | 248.018401 / 485.210641 / 495.596238 |
| take自身wall | .286970 / .380347 / .766614 | .217036 / .338465 / .406489 | .210870 / .303284 / .408481 |

因此故障前的主要等待仍位于reported received→take段；约515–517ms的p95只属于含退出尾的完整窗口，不能写成故障前p95。take低于.4ms仅近似描述p95，max .766614ms必须保留。

限制：RMW received尚未独立证明是最早DDS到达或reader-ready瞬间；该间隔不能再唯一分摊为DDS reader队列、SDK iterator、调度或CPU容量。441条在stable realtime/mono offset假设下各有唯一源发布mono候选，但源没有独立realtime发布bracket，因此不是严格wall源身份校验。重复TF stamp本身不是唯一内容ID，不能用候选匹配断言loss；source/received为系统wall，未与sim header混减。私有SDK同take观察会增加成本，不当纯生产性能基线。

## 已证、未证与停止条件

- **已证新夹具bug**：collect01启动依赖顺序错误，已最小修正；不是原Gateway或Wi-Fi缺陷。
- **已证事实**：固定1x高TF外生记录在A1发生取件滞后；原source已发新校正，过期保护正确。RMW报告收件→take约0.5s占主要段。
- **尚未证原Gateway可修bug**：没有定位错误idle、错误iterator状态或重复take等唯一缺陷；TF原callback/source publish成本短，仍不能由此宣告normal有剩余CPU容量或排除调度/合法服务容量限制。
- **回放条件差异**：原低RTF片段的wall定时重复TF在1x重播负荷更高；新source合并publisher且无历史GID。其影响需限定，不能直接归原生产实现错误。
- **UNRESOLVED**：具体reader/SDK/OS/容量份额，原片段精确wall源率，逐sourceID跨DDS同body消歧，全输入交付/过期/显式drop/右删失终态、完整sim/wall AoI、TCP/MAC重送和恢复。没有为这些缺项填0或PASS。

在没有已证可最小修复源码原因时，本轮停止新实验；不自动collect04、B/C或Gazebo，不改源率/策略/优先级/安全期限。最有证据的后续范围是围绕现有RMW reported-received→take段，在冻结输入与生产语义下定位服务节拍/reader/SDK行为，而不是继续用新无线回合数量代替定位；须Root另行限定/准入。

## 完整证据入口

- [PLAN与准入/预算演变](PLAN.md)、[原body提取manifest](corpus-01/manifest.json)、`corpus-01/records.jsonl`与`bodies.bin`。
- collect01：[host result](collect-01/result.json)、[域发现](collect-01/domain-preflight.json)、[Hub traceback](collect-01/hub.stderr)、[Hub/native END结果](collect-01/hub/result.json)、`commands.json`/`owned.json`；Root另有`net01e/requests/replay-collect-01.json`。实际初次命令没有显式timeout包装，host在4.917wall内失败；不把后续65s外包追写为当次已执行命令。
- collect02：[源pin/实际命令](collect-02/source-command.json)、[host全母数/actual exits](collect-02/result.json)、[首fault](collect-02/FIRST_FAILURE.json)、[typed库存](collect-02/source/typed-corpus.json)、[native maps proof](collect-02/native-load-proof.json)、`native.maps.txt`/`commands.json`/`owned.json`。
- collect03：[源pin/实际命令](collect-03/source-command.json)、[host全母数/actual exits](collect-03/result.json)、[首fault](collect-03/FIRST_FAILURE.json)、[typed库存](collect-03/source/typed-corpus.json)、[native maps proof](collect-03/native-load-proof.json)、`native.maps.txt`/`commands.json`/`owned.json`。
- 两实际业务例的完整新JSON/trace路径：各`source/{planned-inputs.json,result.json}`、`gateway/{network-gateway.json,wire-records.jsonl,wire-bodies.bin,wire-manifest.json,network-gateway-close-phases.jsonl,network-gateway-resources-closed.json}`、`gateway/controller/allocation-events.jsonl`、`peer/{peer-keepout.jsonl,bound-peer-tf-calls.jsonl,bound-mask-publications.jsonl,health-trace.json}`、`time-controller.json`、`mock-clock.json`、`servers.json`、`client/{planned-logical-inputs.json,result.json}`、`hub/{result.json,hub-ingress.json,hub-deliveries.json,hub-clock-control.json,native-control-boundaries.json,native.stderr.txt}`。资源closed marker不替代实际exit。
- 原native新运行文件沿`hub/native/`保留：`native-summary.json`、`transport-config.json`、`configured-lock.json`、`ledger-status.json`、`control-step-trace.jsonl`、`packet-ledger.jsonl`及原4个Wi-Fi PCAP；本子任务只用新小摘要/元数据，没有执行这些ledger/PCAP的完整流分析。
- [collect02语义key/flow成本诊断](collect-02/capture-diagnosis.json)，源码[diagnose_capture.py](diagnose_capture.py)。
- [collect03全部441 pair及边界](collect-03/take-analysis.json)，源码[analyze_take.py](analyze_take.py)。分析只读本次新结果，未重扫历史bag/GB ledger/PCAP。

本报告不进行文件SHA扫描；重要新产物选择/提交/封存由Root统一处理。旧历史失败和冻结版本不改写。

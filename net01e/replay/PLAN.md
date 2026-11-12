# NET-01E 确定性真实业务回放：源码审查与准入前方案

状态：CORPUS EXTRACTED / 新补采集SOURCE ONLY；未启动本目录ROS、模型、native或机器人，不是已验证平台。任务起点由Root指定为`78bf29c1398efb6df03238a93be17325a65c9652`，统一候选尚待Root封定。本文只拥有`net01e/replay/`，不改`net01`生产源、Git或历史证据。

## 1. 先决结论与最小路线

目标是同一份输入记录在A1本地Gateway、B原高质量真实ns-3 Wi-Fi、C原受限真实ns-3 Wi-Fi下回放，固定逻辑ID、完整body、相对模拟时间、源序列和无线节点位置，建立全输入母数。无Gazebo、SLAM、Nav2或RL运行，不产生探索成绩，不训练、不进入NET-02。旧wall300合同仍失败/未修；新sim300与独立2wall合同不改。

**目前不能从已核现成小记录还原完整的原双向真实wire输入。** 原Gateway/Hub/native账本保留长度/hash/身份/时刻，不保存所有body；B02的R域bag没有bound-mask话题和Action服务请求/响应，而且health是原无线交付后的R侧记录。不能把这些条件样本重新包装成原全源输入，更不能以补零、旧模板刷新时间或猜测body补齐。

最小可执行路线分两层；Root已确认先有限提取，再用原组件补采集，不以历史不可恢复缺口停止推进：

1. **可恢复真实记录的固定流回放**：一次有界提取B02原R bag的原始业务CDR及C89独立原捕获。定义新的recorded-input母数，完整记录缺项；三臂只比较这个固定记录的传输结果。它可研究真实大小/节拍业务的Gateway及网络成本，不能声称复原全部历史业务或完整安全系统。
2. **完整wire记录补齐后再做完整合同回放**：若找到原C源bound-mask/Action完整记录，合入并锁定；否则只能另行准入一次无机器人记录采集：使用提取的真实R观测、原BoundPeer/merge生成实际新C业务，原ControlledServer与typed客户端生成新的Action夹具，**在唯一send边界记录完整双向wire bytes**。这份新记录含“历史原CDR”和“本次真实组件生成”两类来源，不称历史原样复原。旧full夹具仅复用进程隔离/原组件，不复用其合成TF/odom来冒充真实业务。

不能以第一层有限流PASS给第二层或四组完整系统签GO。A0仅当Root为定位DDS入口异常另准入，不列首批预算。

## 2. 消息库存、原body来源与缺口

已读：f04最终报告/DELIVERY_IDENTITY、costs-four-arm-01/SUMMARY、costs/NATIVE_PLAN、原wire/Hub/native源码、full_load_source/client/payloads源码、B02的bag/metadata.yaml；未打开任何DB、GB级Gateway/ledger、PCAP或原body。

| 业务 | 原wire/flow | 已确认body来源 | 边界/不能还原项 |
|---|---|---|---|
| 三机map、odom、tf、tf_static、local costmap、cmd_vel | r*20+1..6 | B02 R bag有全部话题；metadata可见原数量；DB未读 | bag recorder接收时刻不是publisher准确发出时刻；TF多publisher顺序只可锁定bag record顺序；cmd含本地writer，不能仅靠话题确定writer |
| peer健康 | 31/51/71 | B02 bag只有公共`/peer_keepout_state`，1958条 | 原R已交付/消费条件流；不代表C发布全源；三路独立原native发送不能从单公共话题反推；只在新回放中显式声明三路复制规则 |
| peer mask | 30/50/70，完整bound envelope+原Grid CDR | 原BoundMaskWire发送`bytes(UInt8MultiArray.data)` | B02 metadata无mask或`/net01/tb*/peer_mask_bound`；Gateway只记binding/hash、不存Grid body；缺原完整包/session/binding时禁止重建假包 |
| filter_info | 32/52/72 | B02 bag各一条 | 在10sim片段之前的transient初始化可按一次prelude提取，独立于normal分母 |
| merge_map | 89 | Gateway `central-map-capture/index.json`与逐条`.cdr`；bag也有R侧276条 | 选C端源捕获，不能混用R交付顺序；source stamp是最老贡献地图戳，不等于生成时间 |
| controller journal | 95 | 原controller journal可有String内容 | 持久行不是准确原Gateway捕获时间；未核原行不得假定可完全还原wire body/节拍 |
| Action | 220..229/240..249/260..269 | bag有feedback/status完整话题；少量journal存Goal/Result字段 | Goal对象CDR不是SendGoal request CDR；RPC/session、service回应的stamp和Cancel list不能猜；readiness/ACK原body未全存。必须真实完整wire记录或新typed夹具 |
| /clock | 控制，不是业务flow | bag有19783条 | 只驱动回放时间；绝不作为业务DDS后门；不伪称来自当前Gazebo |
| /gazebo/model_states | 仅离线候选位置核对 | bag有1978条 | 不送策略；首批固定V3原静态位置，不启动Gazebo、不回放动态位置 |

原`net01d/health/payloads-01/manifest.json`只有六个旧Grid模板，总单条约34.8–52.8KB。来源是另一旧NET-01 B bag的约50.76–51.79sim，旧full明确修改header.stamp/map_load_time、合成静态TF/odom、生成新Action业务；它不是本任务所需全真实记录。不能把该已有资格当新片段资格。

`TopicWire.capture()`只存CDR hash/len；`Gateway.send()`的Action记录同样只存hash/len；`Hub` ingress不存body；native `ipc_ingress`只存身份/长度/admission。native源码明确TX后discard源body、RX从真实网络重组。PCAP可有已TX字节，仍不能覆盖原入队未TX源输入；不提出扫描四份GB级PCAP作为全输入重建捷径。

## 3. 一次提取申请（尚未执行）

候选固定源：`net01d/followup04/runs/gz-simhealth-b1-02/`，原版本AAE，B02原180sim/全主要角色0；不据此推原完整流无损。

申请先仅读`bag/bag_0.db3`：SQLite URI `mode=ro`，连接一次、不PRAGMA/重试/写入，topics表一次；按`(timestamp,id)`固定顺序取`[50e9,60e9)`ns片段。metadata证明该shard覆盖.02..118.49sim；不读bag_1。话题限制：三机`map,odom,tf,tf_static,local_costmap/costmap,cmd_vel,navigate_to_pose/_action/{feedback,status},peer_keepout_filter_info`，公共`/peer_keepout_state`和`/clock`。初始化只为map/tf_static/filter_info各取窗口前最后一条（TF静态是多writer，必须保留能覆盖所需边的原消息，单条不足就报缺失，不能猜合并）；不取scan/plan/link_states/drive diagnostics。只写`net01e/replay/corpus-01/`独占新目录。

另申请只读`.../gz-simhealth-b1-02/central-map-capture/index.json`一次，取capture_node_sim_ns落同窗口的C89原`.cdr`，每文件一次；索引缺失就报告，不改用R片段掩盖。无需读network-gateway.json。提取输出上限64MiB/2万normal记录；触界则整个语料资格FAIL，保留失败原件，不截断后签PASS、不自动换窗。SQL物理页读取量不能由输出上限保证，manifest如实记录wall及返回行/body字节，不伪称只读了64MiB数据库页。

保留原data bytes，不反序列化重写stamp，不重算旧模型/证据hash；已有CDR hash可用于对应匹配。新语料只在需要匹配时计算消息级标识，不做全bag完整性扫描。原bag内重复/相同时间戳全部保留；不能去重降低源率。

这只是**有限真实记录语料**：无bound mask/服务RPC；后续经原组件补采集新业务，不把缺项伪造成旧历史。实际惰性提取源码为`net01e/replay/extract_bag.py`，无ROS/native/model import。Root已接受范围，独立Reviewer审源码后才可执行一次：

```sh
rtk proxy python3 -B net01e/replay/extract_bag.py --output net01e/replay/corpus-01
```

cwd为本workspace。源码固定唯一B02来源、50..60sim、单DB连接、原CDR输出与64MiB/2万normal上界，失败保留manifest且不自动重开/换窗；只准此一次离线提取，不授权新ROS/native。新语料须另经typed语义/anchor审查，EXTRACTED不自动等于回放准入。

## 4. 统一回放时钟、源率、排序与几何

语料每条保存`recording_id,source_file,topic,record_id,original_record_ns,flow,sender,receiver,body_offset,body_bytes,original_source_stamp{available,value},source_kind`。全局按`original_record_ns,固定来源序号,record_id`排序；跨独立源索引相同模拟时刻的先后不可考，选定tie-break并标“新确定性顺序”，不能冒称历史精确顺序。prelude单列，normal不得偷偷补旧样本。

采用绝对原sim区间50..60，body stamp不平移；native sim从0起，以固定anchor50e9映射`admission_ns=original_record_ns-anchor`。完整语料若采用原Gateway capture的sim而非bag record sim，必须另立语料版本，不混用。统一源时钟是明确标记的无Gazebo回放时钟，每10sim-ms一拍、目标10wall-ms一拍。所有当前时刻due输入在STEP前以固定顺序提交，保留各条精确SENDAT admission；STEP返回后观察RX/消费，再推进下一拍。不因为B/C慢而重采样、跳记录、压缩积压或改body时间戳。

若behind wall schedule，只记录late/CPU和实际RTF，不瞬发补偿以改变模拟源率；2wall native/clock进展界保持。禁止伪称实际wall源率完全相同：当模型吞吐不足时相同sim源率和1x wall推进不可同时保证。报告planned/actual sim和wall源率、due→enqueue等待，两种成本独立。

三臂AP/central固定(0,0,1.5)，STA固定V3原静态[(.725,-.15,.15),(.35,-.8,.15),(1.1,-.8,.15)]；不发送动态POSITION。真实记录可描述原运动姿态，但本实验不物理执行该运动、无线位置始终固定；此几何下C未必高丢包，不准事后拉远位置或调RF以制造差异。

只有一个backend选择点。A1复用Gateway原A/direct适配队列语义；B/C复用HubClient→原packet_hub→真实native tcp-mtu-v2→actual RX。消费者仅接收所选backend输出，不可从语料/源缓存恢复目的端body。91/92隔离、原typed QoS、raw反馈/status、BoundMaskWire与ActionWire保持原实现；正常Source与destination同域端点必须按原wire方向，不能在同域同时放同名源/目标造成DDS旁路。A0显式直DDS参考不能混称A1。

需要在`net01e/replay/`实现窄外部入口/记录钩子；原Gateway目前要求actual R clock且有模型位置订阅，直接拿旧GZ runner不能无改动运行该回放。外部回放时钟只能用于此诊断入口，不替换生产actual Gazebo授权语义。任何subclass/monkeypatch若绕过wire receive/guard将无法签Gateway或安全资格，Root须审实际源码后判定。

## 5. 全输入账本、交付/过期/丢弃母数

语料加载时建立全部normal输入ID `recording_id + ordinal + direction + flow`，源due前即入账；body从未出源/排队失败也在母数。不用原R-consumed targets，也不以native ingress作为总源母数。fanout每实际链路为一个delivery-unit，保留父source ID；Action重复attempt另有attempt ID，不增加逻辑RPC母数。

逐层记录计划due、源入队、Gateway捕获/序列化、IPC queued/flushed、Hub ingress/native ID、native admission、TCP首末accepted、actual RX/reassembly、endpoint receive/publish、最终typed sink callback/Guard accept/reject。A1不适用native段为N/A，不能填0代价。所有native/Hub只按真实身份映射，跨层missing/ambiguous是账本失败，不能丢掉难配样本。

每个normal输入最终互斥终态：`NOT_SUBMITTED`（带实际错误）、`EXPLICIT_DROP`（有真实丢弃事件）、`DELIVERED_FRESH`、`DELIVERED_EXPIRED/REJECTED`（真实消费判据）、`PENDING_AT_STOP/CENSORED`。不把deadline过去但可能TCP晚到的输入叫永久丢包；另报deadline-miss（可与late delivered重叠）及缺片/排队原因。总母数=各终态和，另报unique body/bytes、重复传输及duplicate sink回调；原QoS截断/Guard拒绝是消费阶段结果，不归无线丢包。

正常10sim源停止后只drain2sim，结束仍pending均右删失；终止时snapshot native queues/reassembly与Hub出站/Action pending。中途2wall失败照常保留所有未完成母数，不能改源窗口/加跑。

## 6. AoI和成本：两种时钟不能相加

每流/每链路同时报告：sim源生成→完整到达/消费、wall本次due/enqueue→完整到达/消费。body真实header若可用则保留它；TF每edge分开，健康JSON内generation单独解析，mask bound保存原generation；无源戳Action/Twist/String只可报“record-time delivery age”，不称传感信息AoI。C89最老贡献stamp的信息年龄与本次callback生成年龄分列。

AoI_sim(t)=t−最近已接受消息的最大有效generation_sim；晚到旧消息不让generation倒退。未有可用初样本期间UNDEFINED并报时长，不能当0；拒绝/丢失期间AoI继续增。按固定sim网格给time-weighted均值/分位数/max、fresh coverage/300sim-ms超限时长。AoI_wall必须用**本次**记录源发布或due的monotonic，不能减历史wallstamp；旧sim generation到本次wall的映射只是mapped-source-age估计，不能冒称原物理wall AoI。静态TF不适用同一新鲜度判据。

stage wall用同机monotonic、stage CPU用thread/process CPU实际跨度；native admission→TCP accepted→reassembly只用ns3_ns。记录STEP request/return wall和进程CPU、IPC等待、typed反序列化/publish/sink；inclusive parent/child不能相加。native总wall不是纯模型CPU，网络sim服务不是airtime，三臂差值不是序列化CPU。各case统计n/missing/median/p95/p99/max与最差ID。

TCP重送按同一连接/方向TCP数据sequence区间重叠字节计算，允许部分重叠/分段变化；不能只数完全相同(seq,length)，SYN/ACK另报，MAC Retry与TCP重送分开。复用native tcp_tx/rx事件，必要时新短回合PCAP仅一次离线分析，不扫描历史GB PCAP。

**固定双向wire输入与实时Action可靠性不可混成一张因果表。** 严格replay若包括历史ACK/重送，其attempt是记录负载；不能声称是该臂无线诱发重送。实时原ActionWire按ACK再送则attempt/响应时刻自然跨臂不同。第一阶段固定输入仅报告记录内attempt及TCP响应；另行同实现typed资格用固定初始逻辑请求/UUID/源负载与原wall .2/1/最多5attempt，报告由网络实际触发的新attempt。后者显式标注端到端闭环，不能说其全wire序列完全相同。Action幂等继续由原ActionWire负责，纯blob回放不能冒充该资格。

## 7. 统一版本和相对旧四runtime审计

Root封定一个NET-01E候选，不分别拿旧2be A1/AAE B/bd C启动。候选清单必须含完整base/runtime/外部replay源码、corpus index/body来源、session、clock/所有预算、domains/QoS、Gateway/TopicWire/BoundMaskWire/ActionWire/Hub/Guard/TimeController、NETWORK_LOCK_V3、execution profile、native ELF及13DSO绑定和实际maps；只允许backend/RF profile与独占输出路径不同。来源缺项/null保留，不签“全等”。不重hash旧GB原件或冻结模型。

| 旧case | 旧实际runtime | 统一到bd663级外部adapter的已知差异与边界 |
|---|---|---|
| A0 gz-simhealth-a0-01 | aae271f49a8d041285b9a903b3f58d9546985574 | 新197a controller退出完整性门会如实拒绝原controller1；bd663透明异常观察不修消费RuntimeError；A0源码/直DDS机制单列 |
| A1 gz-simhealth-a1-03 | 2be7e229492d29817057fa8db166e38f114ca209 | AAE五个poststop生命周期/证据阶段设置；197a真实controller退出报告；bd663异常观察。不能把历史A1当新统一版本已跑 |
| B gz-simhealth-b1-02 | aae271f49a8d041285b9a903b3f58d9546985574 | 197a报告门与bd663透明观察；源率/业务/RF/策略未改的历史声明继承原绑定，不等同新replay行为等价证明 |
| C gz-simhealth-c1-01 | bd663824d77983cb2b2721e90241ef97bf06461f | 原外部adapter候选基准；新replay source/clock/sink是新增诊断执行条件，必须单列，不能叫零差异 |

此表为既有报告/DELIVERY_IDENTITY/READY来源审计，尚未执行Root的最终逐blob diff；78bf起点是否与bd663生产blob全同由Root审查，本文未访问/更改Git。原12个net01变更路径及PRODUCTION_DIFF.patch保留，不能把新统一版回放取代四旧版本的原失败。

native复用C traced READY绑定：`/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp`，记录ELF前缀0cc771；库目录`.../ns3-lto-portable-followup02/build/lib`，13个ns3.40 wifi/internet/csma/mobility/propagation/spectrum/antenna/energy/network/core/traffic-control/bridge/stats。保持serial logger、tcp-mtu-v2 MSS1448/InitialCwnd10、BE、原queue/reassembly .5sim。B=VhtMcs9/16dBm/LogDistance2，C=VhtMcs3/2dBm/LogDistance3；seed2026110901/run1，V3其它参数不变。不另build替换old0cc，不启RAM ledger候选。

## 8. 有限首批预算及准入材料

本计划授权运行数为0。下一步仅在Root批准数据边界后实现提取器及窄回放入口；审代码、精确命令、配置和源库存后另签START。每项失败保存原件，不自动补跑/改窗口。

拟首批固定流预算：A1/B/C各一次，同一50..60sim真实片段+固定prelude、10sim normal+2sim drain，单case startup≤20wall/active与drain≤60wall/cleanup≤20wall/outer≤100wall；总3case，不计Gazebo，0Policy/SLAM/Nav2。正常native/clock进展2wall界保持；触发即结束并删失，不等outer才停。源片段缺body使资格不能成立时不消耗B/C执行预算。恢复资格在完整body方案获准前为0次；若另准入则独立事前锁定RFoff/on时刻、保持原V3其它参数及原ActionWire上限，不拿合成sleep/drop代替实际RADIO链路切断。

准入必须先有：完整输入库存/缺口结论、确切corpus来源、每flow源率/字节与session/header语义、固定源时钟与排序、唯一backend/no-bypass图、全输入终态账本、实际sink与Guard资格边界、统一源码/库版本、启动和清理argv/owned PID方案。不能用“PLAN完成”代替任何这些实际实现。

NET-01D整体NO-GO、A0 PROCESSFAIL、旧wall300未修、137.93ms历史原因未定均保留。

## 9. Root准入后的实际进展与新补采集源码

独审无阻断、Root START后，唯一`extract_bag.py --output net01e/replay/corpus-01`实际exit0；1次DB连接、0.665586wall，6,051,069B原CDR，15,127条（normal15,115/prelude12），未触上界/重试/换窗。manifest保存每主题库存，正常C89源15条、health100、clock999，三机odom各294/TF各1649。以上不增加历史全流资格；header尚未typed解码。

现有补采集源码（仅AST通过，尚未执行）：

- `recorded_source.py`固定原R的flow r*20+1..6及原C89，完整PLANNED账本在源发布前落盘；raw CDR publish不改header或内容。正常排序按原sim、bag优先/C89其次、原recordID；原历史health/filter/feedback/status不在新活资格同名注入。
- `mock_clock.py`明确无Gazebo，原10×1ms Step/ACK，初值49sim，normal仍50..60sim，留约1sim端点/原观测prelude。**此处具体源码替代第4节最初anchor50提议**：Gateway按原实现首次实际回放clock设置anchor（预期49.01，必须记录实际值）；native与所有source/Guard/health clocks统一沿此固定anchor，不能每臂另取任意偏移。Root已认可49sim prewarm路线。
- `collect_gateway.py`只以原Gateway窄子类在`send`边界被动捕获完整body/flow/RPC/source_sim/anchor及实际send结果，A1原直适配语义；上限128MiB。没有改wire/Guard、没有源缓存补目的body。新原BoundPeer生成bound-mask和health、新原ControlledServer真实typed服务产生RPC/feedback/status；记录含协议动态attempt，运输回放时只能称固定记录负载。
- `action_servers.py`复用原ControlledServer，各实际Goal首次活动后4wall释放tb1/tb2，tb3由原客户端实际Cancel；真实PAUSE服务、原Guard Trigger ARM，0driver/动作执行。
- `run_collection.py`复用原rootfs/bwrap环境、原Peer/TimeController/Hub/native/原typed Full client，client8wall正常、预期4/4/5、0第四negative Goal、0Gazebo。source先READY再启动mock clock；固定旧session2026110912与域91/92。此阶段为新语料采集，不是纯RF对照，也不是物理停稳或完整动态恢复资格。

拟唯一补采集命令（尚未准入/执行）：

```sh
rtk proxy python3 -B net01e/replay/run_collection.py --arm A1 --output net01e/replay/collect-01
```

最多一次；全host60wall，work≤48wall，余量用于原HOLD/实际resource close/owned退出。原source50..60sim发完且client实际normal完成后即进入HOLD；**补采集阶段没有额外2sim drain**，2sim是之后固定运输回放的预算。不得把本补采集收尾称完整固定流全输入排空。发生原Guard/transport fault/角色提前退出立即保留FAIL、源未发条目仍PLANNED；任何强杀或非零实际exit使该次FAIL，不换窗/不自动重跑。

最新源码已加入旧`observe_lto_pair.proc/owned_tree/MODULES`小检查：Hub启动后、任何业务节点之前，查实际唯一native child/exe/parent/maps和13库路径，保存原始maps与JSON；原ELF hash仅继承已封存0cc绑定、不重新扫描旧大原件。启动业务前`domain_preflight.py`各域一次1wall发现要求91/92无其它节点，保存结果，失败不启动业务。此有界发现不代替Root源/身份pin。

Root后续明确主路线为**原Gateway/真实ROS三臂共同外生输入、真实动态协议响应**，不要求固定双向全部wire bytes再次喂给Action。为避免另造A1实现，已停止可选blob回放入口；原Gateway A/direct、B/实际WiFi、C/原受限WiFi都在同一源码`--arm`选项，仅后端/RF变化。`collect_gateway.py --mode`分别A/B/C，source/Peer/Action代码一致。三臂外生原R18+C89 body相同，动态bound/health/ACK/重送/响应的数量与时刻可因交付改变，单列，不宣称全wire负载严格相同。

`action_client.py`代替原旧Full client：事前保存3个52sim Goal完整body/UUID及55sim tb3 Cancel逻辑计划；固定Goal.header.stamp=52，固定pose/behavior_tree与UUID，52sim实际端点未ready就FAIL，不延后换源。GetResult/响应/ACK由原ActionClient/ActionWire真实生成、按动态协议事件列账。原ControlledServer接口不变，非Nav2或真实运动。Root审源后将tb1/tb2 release统一更正为固定54sim（替代早先first-active+4wall方案），从而不同RTF不改变共同受控执行模型。

`recorded_source.py`在READY/启动clock之前，对所选全部原body通过真实generated ROS类各deserialize一次，记录typed-corpus摘要、原header/TF edge戳到新result；未成功就原异常失败、所有PLANNED保留。实际publish仍直接用原body bytes，不重序列化/更新header。此预检只针对本次有限新语料，不重新读旧bag。

新host保存源PLANNED/PUBLISHED及未发布母数，按(flow,CDRhash)多重集与实际Gateway.send采集对账。**相同body重复和其它cmd_vel零写端使逐ID匹配有歧义**，报告重复content组/差额/额外动态源，不能由该多重集给源DDS精确丢包率或完整消费PASS。当前未新增可携带源ID的业务envelope，以免改原body/接口；运输后nativeID/实际wire ID仍可独立全母数对账。

本次先仅申请A1一次，命令如上；B/C主路线同一入口已具参数，但必须A1结果审查后Root分别START，不自动连跑。新增源共8个脚本AST通过，真实ROS/实际native尚未启动；全输入各层终态/AoI分析尚未运行，不能签三臂业务或科学因果PASS。补采集使用同10sim源窗口，原始2sim drain需求将在网络交付统计阶段明确处理，不能以当前host提前HOLD补造drain成立。

### collect-01实际失败（源pin0b471a8）

Root唯一START已执行，host exit1/4.916700745wall，forced=[]。域91/92一次发现无其它节点；新host误将Hub置于coordinator之前，原Hub在native READY立即向尚未bind的`step.sock`发ready，真实FileNotFoundError。Hub1，原error-finalize通过END使实际native0退出；未启动source、Peer、Gateway或Action，typed/Guard/业务分母均未产生，不填0成功。不自动重试/B/C，原stderr/result全部保留。

已提交唯一最小修正：恢复原harness顺序，coordinator实际READY/bind socket后才启动Hub；其它来源/参数/预算不变。该修正仅AST通过、尚未获新执行START。先前owned Hub PID已从/proc消失，Hub原result确认native0；不把失败编排叫业务网络失败。

### collect-02实际失败（源pina5219a0）

Root唯一START、原65s outer/60host/48work/2s kill-grace，实际host exit1/15.205110866wall、forced=[]。源commit/实际命令见`collect-02/source-command.json`。域独占和实际old0cc/13DSO加载门通过；全部7,272所选原CDR真实typed decode通过，raw body/header未改。Gateway anchor实际49.01sim，物理mock49→51.74推进2.74sim、实测ACK RTF1.0004174。

51.73sim三Guard正确触发`health_original_sources_stale`；coordinator HOLD51.74，coordinator1/Gateway1，Hub/native/Peer/source/client/servers/clock0。3个52sim Goal和55sim Cancel尚为PLANNED，0实际Goal/feedback/运动；不得以client0当Action业务成功。源planned7272/published1293/not_published5979，含normal/prelude全母数；新result的868内容单元未匹配/876额外wire仅为多重集差额，相同内容/动态源/pending以及可能的原CDR重序列化差异尚未逐ID消歧，绝不能称永久源或无线丢包。

定点原因证据：最后Peer health seq28/generated51.7/readytrue，odom51.68/51.68/51.685，校正51.16/51.161/51.18。R健康和mask receipt51.71；至首fault51.73，tb1/2校正源龄.57/.569越原.55，而非300sim-ms收件超限。源在首fault mono620765612676904ns之前已发布新map→odom校正stamp51.76/51.761/51.78（原record51.74，发布mono约620765611.4ms）；同期Gateway R最新实际取件仍51.36/51.36/51.18，C publish与Peer callback随后迅速处理这些旧值。每机TF source已发294/294/293而Gateway捕获210/209/210；odom52/52/51全捕获。新鲜校正在**源发布→Gateway R取件之间**落后，当前不能唯一归DDS、SDK iterator、OS，也不是片段缺新校正或Wi-Fi缺片。

本新source把每机原TF话题放在一个publisher，旧full明确有三类独立TF writer；历史真实bag未存writer GID，故本次拓扑不能称精确复原。此夹具差异需先审，不凭它断言唯一底层cause或原生产bug。原源率/内容/header/安全门未调，未自动collect03/B/C。

### collect-03 A1元数据观测提案（SOURCE ONLY）

Root指定用既有`net01d/health/take_trace.MetadataSingleThreadedExecutor`观察R TF的**同一次真实native take**。窄diff只有`collect_gateway.py`新增`--dds-take-trace`并传原Gateway构造参数，以及`run_collection.py`显式转传/记录该布尔值；默认关闭。没有新SDK/private patch、额外take、源率/输入/QoS/安全或profile变化。

```sh
rtk proxy timeout --signal=TERM --kill-after=2s 65s python3 -B net01e/replay/run_collection.py --arm A1 --dds-take-trace --output net01e/replay/collect-03
```

仍只申请一次A1、60host/48work/65outer/2killgrace；原domain/native/typed门保留。用于检验“消息DDS metadata source/received至take驻留”与source发布→Gateway取件总滞后，不是无变化重跑通过率；若原stale再次出现照原保护停止。新观测开销计入，不拿该臂与旧不开观测臂作纯性能改善比较。

分析仅对实际taken且metadata非null/时间戳非0/顺序有效的记录：分别报告RMW source→received、received→take-before、take执行返回wall区间。source/received timestamp为同机wall数值；take保存realtime及mono读取bracket，换算本次source publication mono时保留offset误差界和重复TF edge+stamp候选歧义。不得拿source_sim header与Unix相减；source→received不自动等于网络或最早DDS到达，received的RMW具体语义限制必须保留。元数据为0/无效/不能唯一关联就UNRESOLVED，不猜字段、不新增private hook。

当前两文件AST通过、源码静止，尚未获新执行START。完整证据记录在新输出，不修改collect01/02历史结果。

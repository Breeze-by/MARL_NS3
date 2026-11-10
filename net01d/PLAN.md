# NET-01D 故障因果审计与最小修复计划

状态：STATIC PREPARATION ONLY；尚无 ROS/ns-3/Gazebo/构建准入。起点 `cee0c7024ccf06d88d7ff458a47c39cdf605a7f3`，独立 worktree `/home/zhuyulab/ns3-workspace/net-01d/workspace`、分支 `net-01d/fault-causal-audit`。旧 NET worktree、tag、raw、FAIL、manifest原样保留；不推远程，Git由root协调。

## 目标、所有权与冻结边界

目标是定位旧B health发布→C捕获长等待的实际责任段，审计可靠Action/队列/QoS/时间推进，在有证据时最多两轮最小适配修复及定向回归。不是RL训练或通信调参竞赛。

生产者拥有本 `PLAN.md`、`FAULT_INVENTORY.md`、`RUN_LEDGER.json`、最终 `NET01D_FINAL_REPORT.md`；之后只实现root审定的适配/运行harness。runtime_diagnostic独占 `net01d/health/` 的旧时间线与诊断设计；metric只读审因果与协议。此阶段不改任何现运行源，不重复另一助手的GB级扫描。

冻结 MR3-RL-POLICY-v1.1.0：6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d、701输入、Frontier/candidate/masks/KEEP/WAIT、5sim决策、UUID ownership、Nav2/DWB、SLAM、实体几何/.001ODE均原样。原health/mask .3wall、odom receipt .2wall、odom .4sim/correction .55sim、future bounds、lag .12sim、停止低速/新零/新鲜/实际推进/1.5wall稳定/所有权/三PAUSE全部保持。若修复需要改变冻结核心或安全语义，暂停对应改动并报root。

## 已读依据与P0事实

已读 `docs/PROJECT_STATUS_2026-11-10.md`、发布Manifest的身份/范围与 `docs/BEHAVIOR_CONTRACT.md`、GZ followup-10六例报告、f04 REPORT/账本/A09/A10/B01摘要及原result存在性、f05 REPORT/独审/HEALTH_PATH，以及当前Action/Gateway/Topic/BoundMask/HubClient/PacketHub和执行profile。

- 新HEAD匹配起点；只读git diff对发布tag的 `workspace/config/assets/policy` 与BEHAVIOR合同无差异。复用已发布权重身份，没有重扫全树hash，也没有重新运行模型。
- 六例旧GZ均原600sim/82个UUID闭合、三图各一RL/传统有限配对；不是本轮新120sim配对，也不是自然完成/泛化证明。
- 旧A09/A10/B01 raw实际在 `/home/zhuyulab/ns3-workspace/net-01/workspace/runs/`。三例原result/events/Gateway/袋与native ledger路径存在；A09保存缺项由历史记录保留，存在文件不等于内容完整。新tree只带Git轻证据，缺raw不是删除或丢失。以后按绝对只读旧路径索引，不移动/覆盖/复制GB原件。
- 精确进程executable/Python主脚本只读检查未见Gazebo、Gateway、Hub、native、coordinator、Nav2 actor；不查询DDS图、不启动daemon、不触其它域。宽argv的rtk/rg自匹配不计残留。此快照不代替将来具体入口启动前的owned身份检查。
- 新phase没有build/runtime依赖树；现host入口从本phase相对寻址native/plugin，不能直接使用旧READY启动。需显式只读绑定已知82bc/a49/witness/rootfs及本轮独占输出，不重装ns3、不用同名symlink冒充身份。
- 当前受控入口的120sim符合用户≤180sim上限；本轮统一沿用该合同，不修改旧boot/time_control_runtime或历史READY。新NET01D入口仅显式绑定外部artifact/独占输出。

身份/资源是准备清单，不以文件存在/路径差异列P0故障严重度。P0尚不签完整历史文件内容校验：仅确认Git冻结边界、已有身份和必要raw路径/归属。实际启动artifact只在具体准入前核一次必要SHA与加载路径，不重复全树hash。

## 四臂因果合同（先锁定义，未准运行）

| 臂 | 业务交付 | 可解释差异 |
|---|---|---|
| A0 | 原ROS直接，**无Gateway业务传输** | 冻结原系统参考；只观测诊断与共同外部仿真控制不承载策略业务。不能以旧modeA代替 |
| A1 | 同Gateway、编码、可靠Action确认去重、QoS、ROS端点/记录；有序可靠本地后端 | 当前旧modeA属于此类。A0→A1是适配总开销 |
| B | 同A1适配，通过固定V3 B（VhtMcs9/16dBm/exponent2）/AP/3STA完整RX | A1→B含模型CPU、IPC、同步和无线排队/损失，分段记，不能全叫空口传播 |
| C | 同适配、事前锁定合理受限真实WiFi | 固定原V3 C：VhtMcs3/2dBm/exponent3；无人工drop替代无线、无按成绩找参数 |

所有臂固定同策略/地图/起点/ROI/自主t0规则/决策预算、日志与执行profile；共同墙钟节奏与WallRate影响显式记录。A1/B/C共用可靠层，A0不冒称同适配。是否在A1保留空业务native作控制成本由P2审定，不能静默省去或混成纯无线比较。握手/预热单列在自主t0之前；不为结果后换起点。旧A10 Disk/e224与B RAM/a49差异仍保留，不作为新严格配对。

## P0–P5门禁与实际拟入口

| 门禁 | 最小工作/拟新入口 | 通过依据与停止条件 |
|---|---|---|
| P0 身份/所有权/旧件 | 本文静态审计；后续 `net01d/preflight.py` 仅在设计批准后实现 | 固定源/依赖路径、独占case、无自家残留、不改旧证据；缺必要artifact即未准启动 |
| P1 因果观测 | `net01d/health/PLAN.md` → 经审后最小RAM诊断模块；复用原dispatch/control trace | 单一health seq串联raw publish、binding、C take/capture/serialize/send、socket/Hub、native、R decode/guard；mono/threadCPU、inclusive边界清楚。无profile历史保持UNRESOLVED |
| P2 静态合同 | metric协议/QoS/队列/同步审计，生产者汇总清单 | 匹配源/收QoS、深度/history、缓存/inflight、RPC/session/CDR、ACK与Goal接受分离；无证据不改调度/GC/clock |
| P3 无运动真实规模 | 拟 `net01d/run_replay.py --arm A1|B --case <single-use>`；源与精确argv另送审 | 实际大小完整地图/200²costmap/400²mask、位姿/TF/health、Goal/反馈/Result/Cancel，含真实89/95；真实ROS与B完整WiFi RX。原300ms等逐样本时效、同RPC不二执行、非伪造结果，正常满载不过不得自主GZ |
| P4 故障/停止语义 | 同已审完整负载harness内少量有依据负例，具体注入/预算先报root | 永久失联明确unknown/FAIL、原本机零/PAUSE与Future结果分开；任何注入仅诊断不作C真实无线。真实client收到与真实ownership闭合独立检查 |
| P5 配对准入 | root签新独占READY，拟 `net01d/host_run.py --ready <specific>` | P0–P4成立、统一120sim/固定wall和各阶段账本、所有必需日志/真实控制ACK保存后才逐臂准入 |

以上新入口尚不存在/尚不可执行，不是已批准命令。当前没有新ROS/ns3/build测试准入；下一实际入口须提交源码、参数、总wall、负载合同和停止条件给root审。

无运动负载使用冻结源码时基上限与实际大小交叉约束，不能用中央捕获均值事后降rate；sim源在clock不进时不新发；原wall map→odom重发可以保持同一scanheader，不删原wall流。复用f04 frozen-source-clock依据并补89/95实际全CDR；扫描header holder仅时间近似不冒称SLAM。真实保存body与原clock/headers相配，不用最新缓存替代丢失数据；若旧trace不完整明确NOT VERIFIED。回放用于定位调度/容量，不是物理或策略表现证明。采样开销及供给ticks/skips/实际perWall/perSim必须可见，少供不签满合同。

## 修复与Gazebo上限

先A1/B，后A0/C。最多两轮针对确定缺陷的最小修复+定向回归；每轮登记唯一候选、first failure、scope，不扫描quantum、频率、TTL或无线参数，不把新一次PASS覆盖旧FAIL。若仍缺因果就准确BLOCKED，不为填表耗满。

用户Gazebo上限8次、每臂最多2次、每次≤180sim。本轮事前统一固定四臂120sim，沿已有startup180/autonomy420/outer900/cleanup90wall，原130decision上限保持；本轮当前0/8、各臂0/2。不因结果改长度/延时，120sim/.5目标RTF仍需实际正常负载先验证。任何Gazebo都必须具体READY且原preflight/实际clock/pause/Nav2启动/停止完整。无自动回合、无ROS/仿真进程复用掩盖冷启动。失败如实右删失，T90/T95未达不填0，质量无效raw覆盖不能充有效覆盖。

最终交付仅本轮PLAN/故障表/账本/源diff/必要一次身份/可读最终报告，旧记录不改，root独审与Git本地备份后停止。不push、不训练、不NET02。

## 当前具体实现小步（未执行）

完整P3回放尚未准；先唯一P1入口 `rtk proxy python3 -B net-01d/workspace/net01d/run_replay.py --arm A1 --case health-profile-01`，本轮独占case。当前CLI只支持A1，不自动B。固定16wall源窗口、host总30wall（含启动/排空/证据保存）、Hub29wall；不延时、不自动重试。原生产guard门限不变。源与C侧Peer/merge/journal/Action driver均在独立进程，不在Gateway线程fresh喂入。使用真实Gateway/BoundPeer/ControlledServer/ActionClient；独立MockPhysics+真实nativeACK控制，无实体物理。当前首P1不含89/95/Goal，不签P3/P5完整资格；之后含真实MergeMapNode/Action/journal的完整回放另报设计，不能把本次正例外推。Source直接复用原continuous_dds.source(feedback100,controlled1000,frozen-source-clock)，保持原独立源typed服务/no-request断言。Peer单独进程，真实原10Hzsim mask/health及400² .05m lattice，经A1原完整编码/本地有序接收进入R原guard。guard不arm且不能用无fault签时效PASS，须离线逐样本实际health/mask receipt interval与源龄判原门限。

固定外部依赖为 `/home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload`（原82bc）、`/home/zhuyulab/ns3-workspace/base-01-econ/isolation/rootfs` 与baseline install、原本机Python包目录。新host以明确绝对ro-bind使用，不copy/symlink、不build。独占输出 `net01d/runs/health-profile-01`，其中case runtime-home及原始commands/owned PID/PGID、Hub native child PID、退出/强杀事实均保存。

启动角色：coordinator（真nativeACK/MockStep）、Hub+原native（A1只有控制探针无业务WiFi）、BoundPeer C91、Gateway C91/R92（dispatch/control trace）、MockPhysics R92、独立Source R92。旧f05两域服务器可用性逻辑作为P0参考，本P1不发送任何Goal/非零速度；原source的no_request服务若收到业务请求直接显错。source16wall结束即resource HOLD，实际在途Step完成后STOP source/peer/Gateway/mock/Hub，保coordinator ACK socket到HubEND后再收束；原30wall内任何强杀/异常为工具FAIL，不补跑。

观测新增均RAM且默认opt-in：Peer raw health publish返回与binding后分开；C callback entry、parse后serialize begin/return、send finally；实际Hub queue字节offset/flush与stdinwrite/drain；R真实decode/guard before/after旧seq/receipt/新seq/fault。复用>=10ms wait/handler/pump/journal mono/threadCPU spans。A1无业务Hub health frames是预期，其C→R业务走本地queue，meta.native_id仍可关联。Native Run与上一ACK链按已有trace分开，不把模型计算归作无线或把missing记录当drop。

供给固定：odom30sim与同源TF、双wheel10sim同包212B、scanholder5sim、correction50wall最新scan+.2、costmap200²严格ROS>.5由5wall轮询、map250×220每5wall、feedback100wall、zero20wall；实际发数/每wall每sim/ticks-skips按旧source.json原字段保存。模拟scan仅时基，不是SLAM；额外健康小JSON解析与profile本身有开销，所有profile结论限定诊断执行。任何原限超线原样保留；没有修复行为/额外参数/重试授权。

## P1 B 后续唯一候选（待root具体准入）

首A1运行源为cee0加当次diff，事后同源checkpoint为38e0050cbc5d5dd05073c3ee6c8f7b2f48e906c0，不倒写运行时HEAD。A1供给ticks无skip，实际healthgap<.3，但未证明旧B等待消失。下一仅host允许B和新case、传原RAM后端，角色/源/门限/16wall/总30wall完全相同；0Goal/arm/GZ/NN，仍缺89/95，不签P5。

```sh
rtk proxy python3 -B net-01d/workspace/net01d/run_replay.py \
  --arm B --case health-profile-wifi-01 \
  --native-evidence-ram /dev/shm/net01d-health-profile-wifi-01
```

真实V3 B/82bc原模型不变，所有业务仅完整nativeRX交付，无drop注入/无本地回退。复用现packet_hub独占tmpfs(16GiB可用/24GiBMemAvailable前提)、native退出后原样copy/完整END检查；资源不足/目录已存在/超原30wall/copy不全均首FAIL，保RAM不自动重跑。A1小native控制证据Disk、B实际大负载RAM，I/O条件差异明列，不作纯空口/同硬件科学比较。

## P5完整无运动 SOURCE_READY（未运行，须root逐例准入）

固定正常窗口32wall、host总60wall、Hub59wall；无GZ/实际Nav2/Policy/训练，模拟物理只验证协调机制。当前源码是38e0050后已审Bhost与GZ被动接线、P5薄host/roles/helpers/现status快照缓存；root将统一checkpoint后锁HEAD。原P1全部原件保留。

```sh
# 先A1；此行待root具体准入
rtk proxy python3 -B net-01d/workspace/net01d/run_replay.py \
  --stage full --arm A1 --case full-load-local-01 \
  --payloads /home/zhuyulab/ns3-workspace/net-01d/workspace/net01d/health/payloads-01

# A1审后B另准；不自动执行
rtk proxy python3 -B net-01d/workspace/net01d/run_replay.py \
  --stage full --arm B --case full-load-wifi-01 \
  --payloads /home/zhuyulab/ns3-workspace/net-01d/workspace/net01d/health/payloads-01 \
  --native-evidence-ram /dev/shm/net01d-full-load-wifi-01
```

实际进程：原coordinator、Hub+82bc（A1空业务控制，B真V3）、原BoundPeer、真实Gateway（profile开启）、MockPhysics、三独立R source/ControlledServer、独立C原MergeMapNode、独立C真实ActionClient/journal。新harness与rootfs显式/mnt包根，已有依赖只读绑定；没有重新build。每个case独占目录/socket与完整argv/PID/PGID、原计数/退出；B独占RAM完整copy/END仍计总60wall。

### 载荷与时间合同

- 模板只读准备已由runtime按root准入执行一次：旧B袋50.64sim后六个完整CDR，map三尺寸166×209/204×209/251×210（34800/42740/52816B），costmap三张200²/40104B。不是A10最大尺寸容量上界，不用成绩选模板；原cells/origin/frame/dimensions/resolution保留，仅新fixture header.stamp与map_load_time。纯generated消息检查保持全部字段还原相等，0Node；源不冒称SLAM/真实测量。
- 原mixed时基：odom/同源TF30sim、双wheel10sim同包、scanholder5sim、TF map→odom50wall最新scan+.2、costmap ROS integer严格>.5由5wall检查、原map5wall period、全零cmd20wall、真实受控Goal活动期feedback100wall。feedback正常目标终态后会自然停止；记录实际n/时戳，不说全32wall持续100Hz。原Peer10Hzsim/400²/.05m lattice不改。
- 三R供给从各自真实gateway anchor/clock可用后预热，全部传同SUPPLY_STOP文件并在它出现前持续；B负例继续供给，不能默认32wall提前静默。共同**正常t0由C客户端在已见merge且三个实际Action facade均ready时记录，首Goal之前**；ready含原R guard真arm的既有前提。各R实际arm请求/响应保存，任何一次失败不rearm。正常32wall从该共同t0计，预热供给另列，供给按该mono窗口的emit行/ticks/headers计账，不把累计ticks当纯32wall。
- flow89由原MergeMapNode只融合C实际收到的三map后发布，过原网关下行；flow95由真实测试客户端的请求前日志、真实响应/结果事件写原Gateway journal→原export转发；所有行fixture_origin/Policy_forward=false，不伪造RL决策或成功。R真实订阅消费89/95记录header/内容；本地R同域fanout不算三次无线发送。

### 正常与单一活动负例

正常一次三Goal，原UUID/完整Goal/CDR、反馈/status、GetResult真长等；tb1/tb2原受控server在供给26wall后success，tb3在共同正常t0+25wall由C真实Cancel并收到原UUID列表，结果4/4/5。C正常Done只在该共同t0+32wall且真实结果/反馈/terminalstatus齐备后原子发布。host还等实际Gateway最近原status的RPC/inflight/confirmation计数全0、R owned全空，再只允许第四笔tb3新UUID。原字段按Csource/Raccepted封存后generated解码核一次，不能只凭UUID/退出签通过。

第四Goal必须由C真实接受、GetResult真正pending，且Gateway实际status为唯一C/R pending1、serviceinflight1、确认全0、R原accepted包含该UUID，才允许负例。B发送一次真实native RADIO-off（此诊断显式allow-radio-fault，不是C性能模型），A1只写SUPPLY_STOP停观测；服务仍spin，不关本机清理server。固定负例观察.8wall，原各gate不变，不为凑证据延长。判据为全部原guard真实故障、本机同第四UUID Cancel→GetResult5、三真实PAUSE成功、R owned空与本机Future均done。源的零发布与LocalStop发布可能并存，全零收件不冒称唯一来源或实体物理停机。

本次不额外扩authority退出/FAULT_STOP推进以制造无线恢复；B中央第四GetResult/响应确认可保持未知，按原记录分别保存。coordinator故障exit1及B Gateway未drain exit1可作为预定负例退出原样保留，不改写0；正常段任何真实fault/子进程提前退出则首FAIL即资源HOLD/封存，无重试。原host exit0仅表示已完成事前正负例判据，不替代正常32wall逐样本时效/完整CDR/所有权审计。未验证的恢复交付明确NOT VERIFIED，禁止新Goal的部分证据仅引用f05及现锁存实现。

运行前只做一次精确/proc executable/Python入口确认无真实Gazebo/Nav2机器人actor（不启动graph探针），防同名受控服务竞争。原guard health/mask .3wall、C receipt .2wall、source .4/.55sim、lag .12与全部安全边界不松；P5未过0GZ。

运行前评审纠正（0P5实际运行）：root核native `RADIO` 的enabled=true实际恢复、false实际blackout，因此薄role在RADIO_OFF标记后发送 `radio_fault(False)`。这是新fixture接线纠正，不当旧根因或已运行修复；B封存时需真实native channel_blackout事件确认，不另建测试。

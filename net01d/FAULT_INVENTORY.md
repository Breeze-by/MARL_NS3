# NET-01D 故障清单（停止运行后的事实汇总）

起点cee0c702；含旧证据、静态源码与本轮九次无运动回放。分类：CONFIRMED=事实/缺口已证；UNRESOLVED=责任底层未唯一；REPAIRED-LIMITED=已有有限验证但不能外推。此表不签新运行PASS。旧路径以 `/home/zhuyulab/ns3-workspace/net-01/workspace/` 为基准。

| ID/优先级 | 已有事实、证据与精确边界 | 当前状态/最小处理 |
|---|---|---|
| ID-01/准备 | 发布6d权重/701/76fd行为合同与当前冻结目录git diff为空；Manifest是762文件历史清单，不能声称NET新增层也被原manifest冻结 | 身份沿用；具体新运行只核必要新artifact一次 |
| ENV-01/准备 | 新phase仅workspace，无旧build依赖；host_run从本phase查82bc/plugin，ros-python依赖外部base01 rootfs | 已用新net01d薄入口显式只读绑定旧artifact/rootfs，不copy或symlink，不改旧树 |
| RES-01/准备 | 只读精确executable/Python入口无相关actor；未做DDS图探针。rtk/rg源码文本自匹配已排除 | 仅静态快照，无旧残留证据；未来具体owned启动再核 |
| EVD-01/准备 | A09/A10/B01原result/events/Gateway/袋/native ledger仍在旧workspace/runs；新Git worktree不含大raw | 路径存在≠全内容/捕获完整。只读引用，不覆盖/移动/新全树hash |
| H-01/P1 | B seq1033 composite health return458208.186454543→C capture458208.324384468=137.929925ms；R guard .327175423，新R收件 .330829963；旧receipt至少332.878802ms>.3 | CONFIRMED时效FAIL；底层DDS/wait/handler/pump/CPU仍UNRESOLVED。composite after含binding不是rawDDS ACK。runtime负责时间线/最小埋点 |
| H-02/P1 | 旧B同窗无GW主records，R capture gap194.944751ms；旧B无dispatch profile；物理credit也停，不是独立证明OS冻结 | UNRESOLVED，禁拿全程max/空窗唯一归因或先换SHM |
| Q-01/P2 | HubClient每poll最多recv1MiB，然后处理当前buffer全部完整frame；journal逐行读至当前EOF无固定工作量上界；q4只handler计数，非wall界 | 源码确定可变批量，非已证137ms因果；先观测，未批准截断/优先/丢样 |
| Q-02/P2 | R多writer经C单writer聚合；TF深度100/static transient、health depth1；DDS take/typed转换发生在capture前 | 结构/源合同审计中，不凭数字相同宣称时序等价；不擅改QoS |
| A-01/P2 | 旧B SendGoal IDs12874/23962 ingress+udp_tx却无R完整交付，中央两个Future未知；不是Nav2拒绝或已接受取消失败 | 原FAIL保留。f05加入同RPC ACK/重送；真实满载/运动尚未验 |
| A-02/P2 | f05 core51c：.2wall/1wall/最多5发，requestACK与结果等待分段；GetResult可长等；原body/UUID保持；R缓存幂等；过期不复活 | REPAIRED-LIMITED，0Node16与真实WiFi03 20checks；新增offset9是元数据不是TCP/accepted |
| A-03/P2 | f05原response98与retry102恢复后都RX | 仅延迟/重复处理成立；无线原响应永久丢失恢复未独证，不能随测试名称改解释 |
| A-04/P2 | f05永久分区3发无R RX，ready撤权约.499wall锁存；Cunknown1/retired1/shutdownfalse保留，三PAUSE真 | 诚实FAIL/未知边界成立，不是生产stop所有权认证PASS；不得清表/fake结果 |
| T-01/P2 | 现fixed offset、原/clock、真实World::Step10ms完成ACK、最多20mscredit、.5目标wall节拍；A10和B有限时间对应证据 | 不能把heartbeat FAIL说clock漂移；A1-B需分nativeRun/CPU/IPC/控制等待，A0非旧modeA |
| IO-01/P2 | 26真实D/writev PCAP/ledger页等待；RAM候选降低该阻塞。27 overspec压力仍FAIL，28正确mixed时基有限PASS且缺89/95/99未完整交付 | REPAIRED-LIMITED I/O机制；不能用28当全系统资格或将27改判 |
| SAVE-01/P2 | A09 sidecar/TF保存被SIGINT问题破坏；后修child-only/launch-parent-only、try_shutdown/GCrestore；A10完整TF/witness但gzserver-6 | 旧失败保留。a49寿命修补在B clean exit；不能唯一追认A10根因 |
| SAFE-01/P2 | B observed_stopfalse因两个未知UUID；原CSV新零/低速、618真物理ACK/3PAUSE存在 | 物理低速事实不替代ownership认证，不称实体失控或stopPASS |
| CMP-01/P5 | 旧A09/A10=完整Gateway direct(A1)，非A0。A10 Disk/e224 vsB RAM/a49有执行/记录差异 | 新四臂前瞻配对，不能拿旧99.89vs57.43算纯无线损失 |
| BASE-01/P5 | 六例旧600sim全部停止/82UUID闭合，两图RL T95快、Hard慢；单次且暴露几何 | 有限基座，不是新NET01D 120sim/无线/泛化保证 |

当前责任分工：health明细由 `health/` 汇总；metric协议/QoS只读结论待并入。未确定的新缺陷不得伪装成已修；最多两轮有据修复，任何核心/安全合同改动先停报root。

P0严重度专用于已证安全风险/越权；目前静态初审尚未识别新的P0问题。身份/依赖/残留/文件存在性为准备项，不当成软件故障。

## P1新诊断（非行为修复）

- `health-profile-01` A1：独立源16wall/30总，六角色0，源241/80/40配置ticks无skip；health全段max266ms，原accepted bound5..85共81。未arm，0Goal/无89/95，不当P5资格。没有>100ms单wait/handler/pump，最长外层poll137.874ms/CPU137.561ms含交替短处理；旧B的137ms发布后等待未复现。
- `health-profile-wifi-01` B：同源/原V3/原82bc，六角色0，RAM完整copy292711429B。全段health最大301.355/305.596/312.651ms超限保留；全部是seq7 readyfalse missing_odom→seq8首ready的bootstrap。两端readytrue的72连续间隔另列max278.258/281.131/269.613ms，不追认全段或armed安全PASS。新增路径延迟与源287.010ms发布间隔叠加，不把300ms说单包无线传播。供给active ticksΔ214/71/35无skip，native/耦合降低sim进度，仍保持各wall源原频率。
- P1差别含真实模型CPU/控制、源wall-vs-sim与Disk/RAM证据条件，不做纯无线损失归因。无本轮确定新调度Bug，该P1阶段尚未使用修复轮；后续两轮仅外部生命周期/fixture修正见末节，Gazebo仍未准入。精确分段见runtime独占 `health/summary-01.json`、`summary-wifi-01.json`、`gap-wifi-01.json`；独核见 `review/`。

## 主审追加旧A09原件窄核：来源侧间隔（现象D）

主审只读原Peer3.1MB JSONL，未重算指标/运行：seq1391 entry448235.188505333、snapshot .188586051、healthbefore .250569900、compositeafter .255302901；seq1392 entry .522423292、snapshot .522495902、healthbefore .585151124、compositeafter .590472564。entry间隔333.917959ms、health wrapper return间隔335.169663ms。首guard448235.568498230时新health尚未调用raw publish（before .585151124）。

这是无WiFi A1也出现的真实来源timer/clock消费滞后：原300ms检查合法触发，来源侧等待已经定位，但旧Peer缺clock/profile，不能唯一归GC/ROS/调度。它与B“新health已产生却137.93ms未C捕获”是不同已观测责任段，不能强说同一底层原因。最终矩阵应保现象D、上游执行/clock消费E与来源侧局部B的边界，而不把全部归无线。原A09失败/缺后半TF等保存限制不变。

## 首P5 A1真实失败（502ba02，0自动复验）

`full-load-local-01`正常请求32wall但在6.371wall总时封存FAIL。三真实arm、三正常Goal各1接受、原完整Goal C/R CDR一致；因正常阶段三guard health_original_sources_stale而提前本机取消5/PAUSE，第四活动负例未开始。C客户端仅收tb1/tb2结果5，tb3在其退出快照仍pending；Gateway内部RPC全0不等于端客户端都已接收。89已真过本地完整route0→1并R spy消费；95八条发布中三R spy各收7，未送达/未消费末项不补全。组件原证据见 `review/FULL_LOAD_LOCAL_01_COMPONENTS.json`。

精确首检查为Rsim1.22：持有readytrue seq11/gen1.1的tb1 correction=.66，年龄.56>.55，因此三guard共用同state均合法trip，不是heartbeat。source1已正常发较新1.06/1.26校正；runtime窄链显示首map→odom从源return515750.582214869到R capture515751.607862301约1.025647wall（以source入口算1.025884wall），Rflow23仅39条/last.86而源80条。Rcapture→Cpublish及Peer消费很短，旧值已在Rcapture入口存在；不能归模板/静止pose/CBuffer造旧，source→R订阅回调前的具体发现/缓存/reader/调度责任仍未唯一。不得修改.55、重复等fresh或任意warmup掩盖。此为新无运动夹具/当前接入复现的局部事实，不自动追认旧B同一根因。

## 同观测B完整负载首失败（b043830，非radio-off负例）

`full-load-wifi-audit-01`总10.273wall内正常阶段失败，normal t0=.85sim/mono517268695264451，预定32wall未完成，第四Goal与RADIO-off未开始。三真实arm/三正常Goal接受，首marker为tb1/2 bound_mask_receipt_stale、tb3 health_heartbeat_stale；Gateway failure仍null，具体首段由health独占trace归因，不泛称无线或新Action实现Bug。

原本机三个UUID均Cancel0/status5/PAUSEsuccess、R owned空；tb2本机GetResult仍pending1且无actual_local_GetResult记录，另两机有5，不能写所有本机Future闭合。中央三个GetResult均未知，R三个响应确认仍waiting，executor[false,true]、coor/GW1保留。原89四/95六完整C-R body计数相等，三个R spy各消费4/6，选定journal六条字段相等；route0→1一次无线到R同域fanout不算三STA重复交付。

native0/END与82274649B RAM完整copy只是资源/transport子项，不能覆盖P5 FAIL。截至该stress完整B阶段0Gazebo、0修复轮；后续两轮及actual B结局见末节；该case原FAIL不自动重跑，不改源率/.3wall/credit/V3。机器组件证据 `review/FULL_LOAD_WIFI_AUDIT_01_COMPONENTS.json`。

## 两轮最小外部修补及实际相位最终失败

| ID/优先级 | 已证现场和最小变化 | 实际验证与限制 |
|---|---|---|
| LIFE-01/P2 | 首fault后共享STOP会同时撤R受控server和GW poll；_close不spin本机GetResult。Round1仅停观测并在原hard剩余内≤2wall保服务等本机清理；不等或伪清中央无线unknown | cleanup01确主动停供触发原故障，但Future.done早于done_callback，原marker没有GetResult日志，**总体FAIL保留**；后来结果5不能回填 |
| LIFE-02/P2 | SDK Future.set_result先FINISHED、再排done_callback，Cancel回调可继续创建GetResult Future；Round2要求每stopped UUID真实cancel与GetResult terminal记录均已存在，旧owned/PAUSE/future条件不减 | cleanup02严格3Cancel0/3GetResult5/3PAUSE/owned空/local0，marker早于STOP，58.486ms等待，**有限清理PASS**；不是正常32wall或实体物理停止 |
| FIXTURE-01/合同 | 旧真实A10 14322和B01 10951次WorldACK全部ACK前G=E，旧Mock故意initial5ms/ E=G+5是压力相位，不等于真实Corr6201 | 显式actual-corr6201 initial0；默认stress5/原FAIL不变，Step10ms/credit20ms/pacer20ms/clock100Hz/TTL不变。新actual A1/B同RAM证据后端，仍有Native业务CPU差异 |
| QUAL-01/P5 | actual-phase-local-01正常32wall、3真Goal4/4/5和第4活动任务5完成，正常RPC/确认全0；1740个MockStep全10ms | 有限无运动正常/负例正证，不是旧TF1s已修、不是真实SLAM/ODE或四臂科学比较 |
| QUAL-02/P5 | actual-phase-wifi-01正常首错三guard health_original_sources_stale，Gateway failure=null；正常32/第4/radio-off未达 | **FAIL / NO-GO**。本机94.606ms内LOCAL marker在STOP前、owned/localfuture0/三PAUSE真；中央3GetResult未知、R各1response待ACK、executor[false,true]保留。精确首源龄分段由health独审补入，不先归WiFi/OS |

最终两轮修补已用完。0/8实际Gazebo；A0/A1/B/C均NOT RUN，无新覆盖/T90/T95。所有原FAIL和RAM原件保留，不再第三修补、重跑、训练、NET02或推远程。

### actual B 最终首源龄责任段（81710e6）

最早guard tb1 mono519992.417146585/Rclock4.66：旧seq45的tb2 correction4.10，年龄.56>.55sim；odom .19sim、healthreceipt约218.7ms，非heartbeat/odom首错。新seq46 ready/corr4.30不能擦除旧持有区间失效。三源当时新校正4.67/4.70/4.67、tickskip0。1765TF take全部source timestamp严格匹配、9writer首matched1；source→take中位616.900–638.871ms/max926.126ms，sourceTS→receivedTS≤3.171ms，主要等待在middleware时间戳→Rtake，但该时间戳不能唯一标首入队，executor/中间件具体原因仍E。最大外poll226.947wall/226.103CPU含多handler，无≥10ms单wait/handler；持续输入积压/吞吐不足有证，无唯一可无行为变更修复的SDK逻辑缺陷。466/466ACK G=E、信用≤20ms，相位校准未消除FAIL。详见health/actual-phase-wifi-01/FINDINGS.md；停止，不第三修补。

## 最终原11门禁与分类对照

按用户原11项等级，生产结论为RL FROZEN INTEGRITY PASS；GATEWAY CORRECTNESS BLOCKED；HEALTH TIMELINESS FAIL；ACTION RELIABILITY BLOCKED；ROS MESSAGE INTEGRITY PASS（实收范围）；CLOCK CONSISTENCY有限PASS；NO DDS BYPASS FAIL（全流断链证据未闭合，非已证旁路）；WIFI PACKET EVIDENCE PASS；SAFETY SEMANTICS有限PASS（非实体停稳）；GAZEBO CLOSED LOOP BLOCKED/0of8；CAUSAL ATTRIBUTION PARTIAL。独审另行判定，不由局部正证升级整机。

A=已证harness生命周期Bug、B=观察到的实现/排队调度成本、C=已证WiFi包路径/模型Ndelay、D=合法原保护、E=未解底层。相位5ms压力条件本身不列软件Bug，actual校准不追认旧失败。完整A–E强度表及原始PCAP/路径索引、停止条件/仅建议诊断方向见NET01D_FINAL_REPORT。

actual A1正常32wall的既有原件离线补数不是新实验：3×160health armed无fault、maxgap221.852/221.824/225.383ms；3×160mask全accept、upper max228.158/225.333/225.110ms；1600normalACK G=E/credit≤20ms。其intake源龄抽样不冒充全timer连续max，详见health/actual-phase-local-01/normal-window.json。整体仍actual B FAIL/NO-GO，停止不第三修补。

# NET-01D 故障清单（静态初版）

起点cee0c702；仅旧证据/源码审计。分类：CONFIRMED=事实/缺口已证；UNRESOLVED=责任底层未唯一；REPAIRED-LIMITED=已有有限验证但不能外推。此表不签新运行PASS。旧路径以 `/home/zhuyulab/ns3-workspace/net-01/workspace/` 为基准。

| ID/优先级 | 已有事实、证据与精确边界 | 当前状态/最小处理 |
|---|---|---|
| ID-01/准备 | 发布6d权重/701/76fd行为合同与当前冻结目录git diff为空；Manifest是762文件历史清单，不能声称NET新增层也被原manifest冻结 | 身份沿用；具体新运行只核必要新artifact一次 |
| ENV-01/准备 | 新phase仅workspace，无旧build依赖；host_run从本phase查82bc/plugin，ros-python依赖外部base01 rootfs | CONFIRMED入口迁移缺项；显式只读依赖绑定，未实施，不改旧树 |
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
- P1差别含真实模型CPU/控制、源wall-vs-sim与Disk/RAM证据条件，不做纯无线损失归因。无本轮确定新调度Bug，尚未使用任何行为修复轮；下一完整负载真arm前不得Gazebo。精确分段见runtime独占 `health/summary-01.json`、`summary-wifi-01.json`、`gap-wifi-01.json`；独核见 `review/`。

## 主审追加旧A09原件窄核：来源侧间隔（现象D）

主审只读原Peer3.1MB JSONL，未重算指标/运行：seq1391 entry448235.188505333、snapshot .188586051、healthbefore .250569900、compositeafter .255302901；seq1392 entry .522423292、snapshot .522495902、healthbefore .585151124、compositeafter .590472564。entry间隔333.917959ms、health wrapper return间隔335.169663ms。首guard448235.568498230时新health尚未调用raw publish（before .585151124）。

这是无WiFi A1也出现的真实来源timer/clock消费滞后：原300ms检查合法触发，来源侧等待已经定位，但旧Peer缺clock/profile，不能唯一归GC/ROS/调度。它与B“新health已产生却137.93ms未C捕获”是不同已观测责任段，不能强说同一底层原因。最终矩阵应保现象D、上游执行/clock消费E与来源侧局部B的边界，而不把全部归无线。原A09失败/缺后半TF等保存限制不变。

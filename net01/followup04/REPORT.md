# NET01 followup04 最终生产报告

本报告为生产者交付记录，不代替 root / metric 的独立验收。
最终结论：**OVERALL BLOCKED**。真实 Wi-Fi B01 未完成工程窗，Action 所有权与停止认证未闭合；C 未运行。
本文更新此前 23:14 中间状态，原运行、失败与资格证据均保留，不追认通过。

## 范围与比较边界

- A09 前已前瞻登记 A/B/C 共用 120sim / 420wall 工程窗；不是 180sim 资格通过。
- 原 freshness、heartbeat、TTL、物理停止与所有权闭合门限未改。
- 策略、权重、观察语义、决策规则、Nav2 与无线参数未因本轮结果调整。
- B 使用 RAM native evidence、新 a49 插件及 postpersist 保存流程；这些与 A10 的区别明确披露。
- A10/B 不是严格科学配对，结果不支持通信性能优化或策略效果优越性的结论。
- 本轮实际新 GZ 共 3/3，累计 95；没有第四次。C 为 NOT RUN。

## 实际 A09 / A10 / B01

| 项目 | A09 direct | A10 direct | B01 真实 Wi-Fi |
| --- | --- | --- | --- |
| 自主 sim / wall 秒 | 119.2 / 238.514 | 120 / 239.994 | 87.57 / 186.855 |
| 结束 | heartbeat FAIL | 完成 120sim 工程窗 | heartbeat FAIL |
| T90 / T95 / T98 sim | 63.82 / 71.32 / 71.32 | 74.26 / 76.73 / 91.74 | 均未达到 |
| 最终覆盖 | 98.8559% | 99.8907% | 8935 / 15558 = 57.4303% |
| 三机任务路径 m | 12.3225 / 5.4402 / 11.4642 | 20.1732 / 5.6251 / 17.3798 | .002591 / .251011 / .964417 |
| 导航结果 | 3 / 2 / 3 成功 | 5 / 2 / 5 成功 | tb2 一次 ABORTED；tb3 一次成功；两请求未知 |
| 停止 / 保存限制 | 保存 FAIL | 原 stop、三 PAUSE、UUID/RPC 与 clock/witness 成立；旧 gzserver −6 | 原 observed_stop false / ownership FAIL；新 a49 gzserver clean exit |

A09 的有限运动和覆盖事实不覆盖其 heartbeat 与保存失败。
A10 的任务、停止、RPC、clock/witness 证据成立，但不能写为全部子进程有序零退出。
B01 的自主 t0 = 15.76sim；最终任务表现明显不足，不能用结束后的停机推进增加任务指标。
B 的地图质量有效样本 104/112；p95 = .05m，precision = 98.2383%。
地图质量有效与覆盖完成是不同指标，前者不使 B 的覆盖与闭环通过。

## B01 首个 heartbeat 与通信事实

health seq1033 发布 mono458208.186454543，C 捕获 mono458208.324384468，相隔 137.930ms。
R guard 在 mono458208.327175423 触发，先于 R 收到新 health 的 mono458208.330829963。
旧 heartbeat 年龄至少 332.879ms，超过原 .3wall；现有证据不支持把它写为误报。
该链条尚不能唯一归因为 DDS、CPU 或无线中的某一丢失 / 等待点。

B 有 17 次实际 forward、18 次 attempt、4 次 Goal request、2 次 response。
两个未知 Goal 的 CDR 已进入 native 并 udp_tx，随后未见 R 完整消息交付：

- tb1：native message ID12874，flow220；原 UUID d0f0f07af4ef4822a32bb57afd2096b4。
- tb3：native message ID23962，flow260；原 UUID 5bfac829d999453a8692a5aed7238052。
- [native ledger](../../runs/net01-b-corridor-6201-01.network/native/packet-ledger.jsonl) 行1351869–1351870记录首项 ingress / tx；行2154548、2156177记录第二项 ingress / tx。
- [Hub ingress](../../runs/net01-b-corridor-6201-01.network/hub-ingress.json) 的零基索引12873、23961对应这两项。
- [Hub deliveries](../../runs/net01-b-corridor-6201-01.network/hub-deliveries.json) 与 Gateway 原记录未见这两请求的 R 完整交付或对应响应。

这不能写成 R 已接受 Goal 而 Cancel 没有响应；具体无线丢点仍未唯一定位。
C pending2、retired services2、executor shutdown [false,true]；R pending0不等于 C 原请求已闭合。
真实 B 的 flow89 为138捕获→137整图交付，flow95 journal 为9→8；明确存在丢失。
不能把有限双向链路证据改写为全流无丢、Action 可靠或业务闭环通过。

## B01 停止、进程与封存

原 observed_stop=false，两个未知 UUID 使 ownership 未闭合；三 PAUSE 成功不替代此证书。
原 stop 判据同时要求实际低速、新零、fresh 模型、authority 退出及所有权闭合。
原 CSV 的末段低速 / 新零事实与正式停止证书 FAIL 分列，不泛称机器人失控，也不追认 stop PASS。

- authority PID2274460 实际 exit0 后进入 FAULT_STOP_OBSERVE。
- 618 次真实物理 Step ACK，各10 iterations；103.33→109.51sim，随后 HOLD。
- physics_failed=false，最终无物理 RPC inflight；Native 最终 ACK109.50sim。
- 新 a49 插件实际加载，gzserver 本次 clean exit，未重现 A10 的 −6；不据一次运行宣称唯一崩溃根因已证实。
- Gateway persist 实耗6.62254wall；保存与停止 / Action 成功是不同事实。
- 9个 native 文件合计3.942GB，copy complete 实耗5.11644wall；RAM 原件保留。
- witness R10951 / C10943条，首样本比首 Goal 早48.17wall。
- 两 witness exit0、coordinator exit1；故障与 expected_shutdown=false 保留，无强杀或残留 owned group。

[运行结果](../../runs/net01-b-corridor-6201-01/result.json)、[停止事件](../../runs/net01-b-corridor-6201-01/events.jsonl)、[Gateway保存摘要](../../runs/net01-b-corridor-6201-01/network-gateway-saved.json)为原件。
[coordinator](../../runs/net01-b-corridor-6201-01.time-control/coordinator.json)、[sidecar退出](../../runs/net01-b-corridor-6201-01.time-control/process-exit.json)、[实际插件身份](../../runs/net01-b-corridor-6201-01.time-control/artifact-identity.json)保留实际状态。
[launch.log](../../runs/net01-b-corridor-6201-01/launch.log) 行7243记录 gzserver clean exit；Peer / merge 仍有 SIGINT −2，不能写全 child 零退出。

## 资格与诊断历史

qualification20–27 的原失败全部保留，不用后续候选结果覆盖。
26 定位到具体 PCAP / ledger writev 页等待；此前 strace 扰动与缺失控制 RAM 不支持唯一历史归因。
27 的 RAM 保存改善了该 I/O 路径，但原压力 TTL 仍 FAIL，不能因此准入 B 或宣称时效修复。
28 按实际源码纠正了 sim / wall 夹具口径，16wall 有限范围 PASS；0arm / 0NN。
28 有99条入口消息未完整交付，且缺 flow89 / 95，不能覆盖真实 B 的全业务资格。
B 原89 / 95的实际交付数已在上文披露；真实 B 的失败优先于夹具有限通过。

## NET01 最终矩阵

| 边界 | 状态 |
| --- | --- |
| frozen policy / semantics | PASS |
| NS3 WIFI MODEL | PASS，真实 PHY/MAC/PCAP 与完整 payload 路径 |
| BIDIRECTIONAL TRANSPORT | FAIL：有限双向子测成立，实际关键 Action 请求未交付 |
| NO DDS BYPASS | 已审计业务路径及真实 B 证据范围 PASS |
| TIME SYNCHRONIZATION | 受控 87.57sim 时间对应有限 PASS；120sim 未完成，heartbeat 端到端时效另为 FAIL |
| ACTION AND MESSAGE INTEGRITY | FAIL：两未确认请求 / 所有权未闭合 |
| NETWORK SAFETY | FAIL：原停止所有权认证未闭合；实体低速 / 新零独立成立 |
| GAZEBO NS3 CLOSED LOOP | FAIL：真实 B 未完成 |
| performance | DEVELOPMENT ONLY |
| overall | BLOCKED |

最小退修范围是：有界且保留同 UUID / RPC 的 Action 可靠交付、中央捕获长等待、原停止所有权闭合。
修复必须保留真实未知状态、原安全门限与失败证据；本报告不授权新运行。
未进行训练、改 RL、参数扫描、推送或 NET02；C 未运行，无第四次 GZ。

## 既有源码身份与证据引用

以下保留原中间报告中的源码身份 / 证据引用；历史局部结论以本最终状态为准：
A09质量有效131/145帧，末p95=.05m/precision99.0499%；A10为135/145帧，末p95=.05m/precision98.3192%。均非自然终态、非统计比较，不将A10时效回归成功解读为RL性能提升。A09八UUID均status4成功，并非活动目标cancel验证；A10十二UUID均成功。二者原physicalstop证据与运行/保存失败独立列示。[A09原摘要](A09_EVIDENCE_SUMMARY.json)、[A10原摘要](A10_EVIDENCE_SUMMARY.json)、[A10唯一离线结果](offline-metrics/net01-a-corridor-6201-10/result.json)。
历史中间记录（截至26 / A10时；后续 B / 27 事实见上文）：原180/420资格失败保留；在新A09前主审事前固定全组120sim/420autonomywall工程窗口，startup180/outer900/cleanup90及全部时效/停止gate不变。预算最多3实际启动，本轮已用2（累计94），剩1未准入；slot2在结果前由B改为A10，不因低成绩挑选/补跑，C NOT RUN。[完整账本](RUN_LEDGER.json)、[原前瞻时间方案](CONTROLLED_TIME_PLAN.md)、[A09](A09_PLAN.md)/[A10前瞻](A10_PLAN.md)。
历史中间记录（截至26 / A10时；后续 B / 27 事实见上文）：A10gzserver−6发生在原物理stop/3PAUSE/ExpectedHOLD之后，原错误“Callback group needs to be associated with executor”；一个旧free-run样例干净不能排除历史同类。静态查到新plugin group先于Node析构的真实寿命风险，修补仅成员声明顺序，新a49b已独立build但未加载，不能签实际退出已修复或唯一原因。A10实际仍使用旧e224。Gateway旧194MB证据persist实际21.213秒超原20秒等待；post资源销毁改一次json.dumps后write，同原全文exact，唯一0Node数据验证9.127秒，默认字段/异常不变；测试峰RSS不冒充production界。[新plugin身份](PLUGIN_LIFETIME_IDENTITY.json)。
24窄链：Peer54→55真正health调用间隔283.959ms，Cclock5.50到Peerentry仅1.414ms；nativeH5.52 Run199.061wall/33.831CPU，首大输出前192.099wall/29.183CPU。tb1mask先入Hub，tb2/3约205ms等该STEP后才入，最终RX→accept仅8.34/18.72/3.71ms。额外空隙主要在模型Run及后续Hub接入，不能把全部称无线传播或源Peer独迟。23/24只能定位offCPU，不能唯一归scheduler/文件IO。[24时间链](CONTINUOUS24_SUMMARY.json)。
25实际采到80899writev/15043write，仅1futex，无fsync/fdatasync/sleep/yield；最长非read为PCAPwritev4.787ms、ledger3.803ms，无百毫秒阻塞写。stdin长read为等命令，非Run。完整StepTrace RAM随Hub硬杀丢失，-s0不保存JSONbody；以Run内相邻ledger事件间隔作有限替代，最大10.491ms。不能声称重现/解决24等待或唯一排除未跟踪活动。原16MBtrace保留/dev/shm并已持久复制，旧原件不覆盖。[25证据与限制](CONTINUOUS25_SUMMARY.json)。
历史中间记录（截至26 / A10时；后续 B / 27 事实见上文）：26已完整END，3813样本/proc读取错误0，原wrapper/native精确PID均退出。最大采样间隔7.854ms，四文件非原子跨度最高1.226ms，采样器CPU2.757s/19.632wall（约14%单核，非零扰动）。完整H5.43 Run137.387wall/52.356CPUms，offCPU85.031ms；16个连续样本跨76.945ms恒D/folio_wait_bit_common/writev fd5=wifi-1-0.pcap，running/runqueue/majorfault不变。H5.55 Run61.405wall/7.485CPUms，offCPU53.920ms；10样本跨46.182ms同D/writev fd3=packet-ledger.jsonl，计数亦不变。由此具体识别本26同步记录文件页等待，而不是只猜scheduler/后续stdout；不唯一追认24底层原因或硬件故障，也不据诊断exit0解锁B。[26完整边界与样本](CONTINUOUS26_SUMMARY.json)。目前没有实施记录路径修复或追加实验，待主审下一明确决策。
A10按预定“自主期最大Σceil((完整body+8)/1164)”选最繁忙连续16wall，窗口约50.64–58.63sim。实际Gateway捕获odom14.69wallHz/724B（夹具30）、mixedTF69.63Hz（夹具100；map→odom约50相同，odomTF约14.69，双wheel同包5Hz而夹具单left20）、costmap.81–.875Hz/40104B（夹具2）、feedback99.94Hz/116B（夹具100）。另真实merge89约.75Hz/53284B，夹具缺89/95。因此24为部分上游更保守的混合压力负例，不能直接等同真实任务网络合同必然失败，也不能删原压力失败。捕获不等于独立证明DDS全源发布无漏。[固定选窗与每flow表](A10_OFFER_CONTRACT.json)。

## 可读曲线与最终交付

以下由既有工具一次绘制已提取数据，不新增袋评价或实验：

- [A09 覆盖 / 三轨迹](offline-metrics/net01-a-corridor-6201-09/coverage-and-trajectories.png) · [原 CSV](offline-metrics/net01-a-corridor-6201-09/coverage.csv)
- [A10 覆盖 / 三轨迹](offline-metrics/net01-a-corridor-6201-10/coverage-and-trajectories.png) · [原 CSV](offline-metrics/net01-a-corridor-6201-10/coverage.csv)
- [B01 覆盖 / 三轨迹](offline-metrics/net01-b-corridor-6201-01/coverage-and-trajectories.png) · [原 CSV](offline-metrics/net01-b-corridor-6201-01/coverage.csv)

主审对原 B CSV 的窄核：103.33–109.51sim 停机段每机62姿态、最大速度 .000070/.000076/.000070m/s、最大角速度均小于 .000050rad/s；181/182/182条 stop drive 目标全零且实际消费序号递增。该物理事实不替代两个未知 UUID 的闭合和原停止证书 FAIL。

[B 完整小摘要](B01_EVIDENCE_SUMMARY.json)、[最终账本](RUN_LEDGER.json)、[交付身份](DELIVERY_IDENTITY.json)。已停止运行与修改生产代码，最终独立审查及 Git bundle 由 root 后续单独完成。

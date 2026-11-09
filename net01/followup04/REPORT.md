# NET01 followup04 — 中间报告草稿（截至26，尚未最终交付）

当前已得到一次120仿真秒的**直接适配参考**A10：12个真实Nav2目标全部成功，原时效、物理停稳、3PAUSE、UUID与RPC闭合和独立clock记录成立。但真实WiFi合成压力资格24仍违反原300ms心跳/mask间隔，尚无本轮真实WiFi Gazebo回合，NET01仍BLOCKED。A10收尾gzserver退出−6也未抹去。26定向观察已定位本次native同步文件页等待，但尚未修复；本稿不宣称任务完成或自动开始B。

## 实际机器人结果

下表时间为从自主t0起算的Gazebo仿真秒；覆盖采用原15558cells/38.895m²任务分母和原地图质量gate，各sealedbag只用原评价器离线分析一次。失败回合的有效指标仍报告，不据覆盖高追认运行PASS。

| 实际启动 | 自主sim/wall秒 | T90 / T95 / T98 | 最后有效覆盖 | tb1/tb2/tb3路径m | 真实任务成功/失败 | 结束与限制 |
|---|---:|---|---:|---|---|---|
| A09，累计93 |119.2 /238.514|63.82 /71.32 /71.32|15380/15558=98.8559%|12.3225 /5.4402 /11.4642|3/2/3成功；0高层失败/timeout|首heartbeat故障，120前右删失；三机均stale，不能只按result最后tb1文本认单机；sidecar/TF保存失败|
| A10，累计94 |120 /239.994|74.26 /76.73 /91.74|15541/15558=99.8907%|20.1732 /5.6251 /17.3798|5/2/5成功；0高层失败/timeout|simulation_budget；主要direct闭环成立；poststopgzserver−6，非全child正常退出|
| B/C |NOT RUN|NOT MEASURED|NOT MEASURED|NOT MEASURED|NOT MEASURED|无真实WiFi Gazebo准入；不能用mock或旧600sim补齐|

A09质量有效131/145帧，末p95=.05m/precision99.0499%；A10为135/145帧，末p95=.05m/precision98.3192%。均非自然终态、非统计比较，不将A10时效回归成功解读为RL性能提升。A09八UUID均status4成功，并非活动目标cancel验证；A10十二UUID均成功。二者原physicalstop证据与运行/保存失败独立列示。[A09原摘要](A09_EVIDENCE_SUMMARY.json)、[A10原摘要](A10_EVIDENCE_SUMMARY.json)、[A10唯一离线结果](offline-metrics/net01-a-corridor-6201-10/result.json)。

## 修补边界与实际证据

模型6d、发布a014/原执行76fd、701编码、Frontier/联合mask/目标规则、DWB/shimfalse、SLAM/物理1ms/地图/起点/原V3参数均不动，无训练。轻bootstrap在重依赖import前exclusive创建**本轮真实journal**，一次精确交给原main目录mkdir与原constructor同handle open，未补造旧空journal。C Action已准入RPC在ready撤回后保留原service至真实send_response，保持UUID/session/RPC身份；无运动真实DDS测试证明原中央client收到真实终态，故意未准入unknown回调仍未知且shutdownfalse如实保存。

时间适配仅新增外部World::Step(10)薄plugin与独立owner，postphysics10ms/10iter校验；一物理RPC在途，actualnativeACK+固定20mscredit，真实/clock驱动模型，物理E从不伪充clock。HOLD阻止新token并完成原inflight，再真实pause；正常STOP保native耦合，真实authority退出和原物理/UUID/RPC证据先于ExpectedSeal。固定20mswall token计划共同目标.5RTF，内worldupdate1000/dt.001；实际WallRate/RTF混杂仍须记录，不能宣称逐点等价旧执行或科学通信优势。

原180/420资格失败保留；在新A09前主审事前固定全组120sim/420autonomywall工程窗口，startup180/outer900/cleanup90及全部时效/停止gate不变。预算最多3实际启动，本轮已用2（累计94），剩1未准入；slot2在结果前由B改为A10，不因低成绩挑选/补跑，C NOT RUN。[完整账本](RUN_LEDGER.json)、[原前瞻时间方案](CONTROLLED_TIME_PLAN.md)、[A09](A09_PLAN.md)/[A10前瞻](A10_PLAN.md)。

A09首gap已定位C Peer本身timer迟：clock139.20在mono448235.387739已publish，Peer下一entry晚134.684ms，health下一真正publish发生在首guard之后16.653ms。原Rclock持续约20ms，native21步CPU仅2.358ms；不能归网络下游或唯一GC。其全PG SIGINT先打child，launch再转发，第二KeyboardInterrupt确打断TF落盘；bwrap monitor整PG退出亦丢witness。后续外部parent-only launchSIGINT/innerchild sidecarSIGINT修复保留原等待界。

仅NET BoundPeer有界存活期延期自动循环GC（refcount照常，threshold不改，finally恢复原状态后persist/try_shutdown），作为C实时性可证伪候选，非历史GC唯一归因。A10真实GC运行false→恢复true，PeerRSS135424KiB；完整58923条TF、4296绑定及R/C各14322个clock样本，首样早于首Goal约52秒；14322物理ACK与14321实际nativeACK/固定offset吻合。armed至seal mask最不利gap上界.26804/.27058/.27055wall，health≤.274，原receipt≤.100，无fault。

A10gzserver−6发生在原物理stop/3PAUSE/ExpectedHOLD之后，原错误“Callback group needs to be associated with executor”；一个旧free-run样例干净不能排除历史同类。静态查到新plugin group先于Node析构的真实寿命风险，修补仅成员声明顺序，新a49b已独立build但未加载，不能签实际退出已修复或唯一原因。A10实际仍使用旧e224。Gateway旧194MB证据persist实际21.213秒超原20秒等待；post资源销毁改一次json.dumps后write，同原全文exact，唯一0Node数据验证9.127秒，默认字段/异常不变；测试峰RSS不冒充production界。[新plugin身份](PLUGIN_LIFETIME_IDENTITY.json)。

## 无运动资格与诊断——失败均保留

| case | 结果与范围 |
|---|---|
| clock校准 |20发17收FAIL；仅收到17条DDSsource在真实publish系统时钟括号内，接受限定观察能力，不称BE零丢/arrival层已证|
| 20 free-running |lag .13>.12 FAIL；不改750/TTL凑过|
| 21 controlled |两个bootstrapclock先于Gateway reader构造，未进入16wall业务；实际reader+publisher发现同session条件最小修补，仍原2q|
| 22 controlled |69ready/机；loadedRTF约.425低于原180/420=.4286；旧mask只有entry不足确认真实receipt，NOT VERIFIED，不追认PASS|
| 23 controlled |seq43→44真实maskgap下界.493/.488/.509>.3，FAIL；约183wall/11CPU的Run等待不等于唯一IO/OS根因|
| 24 controlled PeerGC |三机60accepted但seq54→55下界.420/.468/.481，health亦>.3，FAIL；GC已false，不能再归唯一GC|
| 25 strace |原16/30压力不减；29.272wall硬界hub−9，余5角色0；真实native/tracer已精确确认退出。缺完整END/STEP CPU，诊断FAIL，不解锁B|
| 26 proc观察 |六role0/22.906wall；完整Run中观测到PCAP/ledger同步writev页等待，不作资格PASS|

24窄链：Peer54→55真正health调用间隔283.959ms，Cclock5.50到Peerentry仅1.414ms；nativeH5.52 Run199.061wall/33.831CPU，首大输出前192.099wall/29.183CPU。tb1mask先入Hub，tb2/3约205ms等该STEP后才入，最终RX→accept仅8.34/18.72/3.71ms。额外空隙主要在模型Run及后续Hub接入，不能把全部称无线传播或源Peer独迟。23/24只能定位offCPU，不能唯一归scheduler/文件IO。[24时间链](CONTINUOUS24_SUMMARY.json)。

25实际采到80899writev/15043write，仅1futex，无fsync/fdatasync/sleep/yield；最长非read为PCAPwritev4.787ms、ledger3.803ms，无百毫秒阻塞写。stdin长read为等命令，非Run。完整StepTrace RAM随Hub硬杀丢失，-s0不保存JSONbody；以Run内相邻ledger事件间隔作有限替代，最大10.491ms。不能声称重现/解决24等待或唯一排除未跟踪活动。原16MBtrace保留/dev/shm并已持久复制，旧原件不覆盖。[25证据与限制](CONTINUOUS25_SUMMARY.json)。

26已完整END，3813样本/proc读取错误0，原wrapper/native精确PID均退出。最大采样间隔7.854ms，四文件非原子跨度最高1.226ms，采样器CPU2.757s/19.632wall（约14%单核，非零扰动）。完整H5.43 Run137.387wall/52.356CPUms，offCPU85.031ms；16个连续样本跨76.945ms恒D/folio_wait_bit_common/writev fd5=wifi-1-0.pcap，running/runqueue/majorfault不变。H5.55 Run61.405wall/7.485CPUms，offCPU53.920ms；10样本跨46.182ms同D/writev fd3=packet-ledger.jsonl，计数亦不变。由此具体识别本26同步记录文件页等待，而不是只猜scheduler/后续stdout；不唯一追认24底层原因或硬件故障，也不据诊断exit0解锁B。[26完整边界与样本](CONTINUOUS26_SUMMARY.json)。目前没有实施记录路径修复或追加实验，待主审下一明确决策。

A10按预定“自主期最大Σceil((完整body+8)/1164)”选最繁忙连续16wall，窗口约50.64–58.63sim。实际Gateway捕获odom14.69wallHz/724B（夹具30）、mixedTF69.63Hz（夹具100；map→odom约50相同，odomTF约14.69，双wheel同包5Hz而夹具单left20）、costmap.81–.875Hz/40104B（夹具2）、feedback99.94Hz/116B（夹具100）。另真实merge89约.75Hz/53284B，夹具缺89/95。因此24为部分上游更保守的混合压力负例，不能直接等同真实任务网络合同必然失败，也不能删原压力失败。捕获不等于独立证明DDS全源发布无漏。[固定选窗与每flow表](A10_OFFER_CONTRACT.json)。

## 当前验收边界（中间状态）

| 项目 | 当前等级 |
|---|---|
| FROZEN POLICY |PASS：固定模型/算法身份与版本边界不变|
| NS3 WIFI MODEL |PASS限定：实际模型/PCAP/full-byte既有证据，非硬实时承诺|
| BIDIRECTIONAL TRANSPORT |FAIL当前合成满压力时效；有限静态内容/双向子测PASS不覆盖此失败|
| NO DDS BYPASS |LIMITED PASS受控路由证据；A直接明确非WiFi，尚无本轮真实GZ WiFi复核|
| TIME SYNCHRONIZATION |BLOCKED整体验收：A10 actualclock/token/ACK成立；24原wall门限失败、26定位同步记录等待尚未修复|
| ACTION AND MESSAGE INTEGRITY |PARTIAL：真实DDS撤权后原RPC、A10十二真实UUID/RPC闭合成立；真实WiFi Nav2未运行|
| NETWORK SAFETY |BLOCKED：direct原停机有实证；无运动/未arm资格不等于运动中网络失联安全|
| GAZEBO NS3 CLOSED LOOP |BLOCKED：A10是直接参考，B/C NOT RUN，且gzserverpoststop−6未真实回归|
| PERFORMANCE |DEVELOPMENT ONLY / INSUFFICIENT，无统计/泛化/通信优化优势结论|
| OVERALL |BLOCKED，NO-GO NET02；本稿待下一明确诊断决策，未最终封存|

无训练、模型更新、系统网络变更、调TTL/原V3、推送或自动消耗最后Gazebo槽。旧02/03报告/失败、A09原件、A10旧READY和artifact均原样保留。该草稿只整理已发生事实，不授权任何运行。

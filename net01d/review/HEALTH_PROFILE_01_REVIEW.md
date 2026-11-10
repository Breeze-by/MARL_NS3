# A1 health-profile-01 独立原件核对

仅核封存 `net01d/runs/health-profile-01`。先确认文件规模，Gateway JSON为14,365,280字节，单次读取；源和Peer小原件及profile用于核对，未运行节点、网络模型或新测试。关键逐序列派生保存于 `HEALTH_PROFILE_01.json`，不修改生产原件。

## 实际成立的范围

- A1为原完整Gateway的有序本地业务交付，Native只推进空业务网络时钟。独立Source、Peer、Gateway等六角色均退出0，无强杀，总21.967807wall；这些是进程事实，不是完整系统资格。
- 实际供给窗口16.000441wall；受控Mock时钟从.40到8.44sim，共8.04sim，约.50249倍墙钟速度。odom/wheel/scan配置ticks为241/80/40，skips全部0。地图、反馈等仍是已声明合成近似；没有89/95、Goal、Nav2、Gazebo或策略推理。
- Peer共有86个真实health发布序列，seq5..85共81条ready；seq1..4无初始odom、seq86在源结束后stale_odom，原值保留。ready发布时记录的最大odom源龄.0600sim、receipt.113700wall；这只是发布端观测，不能替代目的端时效。
- 三机health均在原guard内更新86次，seq1..86递增，原实际receipt最大间隔分别.266099566、.266139163、.266234786wall，均低于.3。只看ready序列5..85，最大间隔分别.215510674、.215306485、.218396917wall。
- 三机bound各收到86条、实际接受81条；初始化1..4和尾部86被原规则拒绝。相邻接受的真实回调括号所给receipt间隔严格上界分别.217628724、.213385165、.213444548wall，均低于.3。接受在原receive_bound里执行state_fresh，没有放宽门槛。
- 原Gateway failure=null，END已flush、两个executor shutdown=true、RPC/确认/本地清理未决均0；GC从原enabled=true恢复为true，thresholds保持[700,10,10]，记录peakRSS108160KiB。

## 不得外推的结论

guard全程**unarmed**，故无fault及receive_health returned=true不能解释为每条health都通过state_fresh；原receive_health在未armed时仍可保存ready=false输入。当前观测没有记录每个health检查瞬间的R ROSClock值，不补造完整源龄证书。实际bound接受证明其各自检查时刻符合原源龄规则，也不自动覆盖整段health检查或后续运动。

全程最长外层poll间隔.137933wall；相邻C/R累计服务时间不是单回调时长。最高poll span的wall和threadCPU均约137ms，说明本例确有长的同线程批次，但不能据此唯一解释旧B的137.93ms发布→capture等待。源序列与具体handler/pump的因果分析由已分工的runtime审查继续完成，不重复归因。

**结论：本次A1/P1诊断供给、实际收件及profile记录可用于继续定位；未发现此次健康receipt间隔越过300ms。不是P5完整负载、无线容量、真实源龄全程资格或物理停止通过。** 无需因本次进程正常结束增加等价测试；后续具体B或完整负载入口另行限定。

## B/P1 health-profile-wifi-01 的收件阶段补核

随后只读 `health/summary-wifi-01.json`、`health/gap-wifi-01.json` 与B的原Peer JSONL，未重复加载Gateway大原件或扫描native ledger。三路全段最大实际receipt间隔为301.354721、305.595966、312.650892ms，**均超过原300ms，必须保留，不能写全段时效通过**。

三处都对应seq7→8。原Peer seq7为.7sim、三机missing_odom且ready=false；seq8为.8sim、首次ready=true；guard仍unarmed。因此属于初始化向首次ready过渡，不是两端都ready的正常区间，不能描述成运动中故障；但也不能删去此区间补造整体通过。

该间隔的可核算分解为：源raw-publish-return间隔287.010240ms，加上新旧路径耗时之差14.344481/18.585726/25.640652ms。它不是某一条消息无线传播了300ms。两端source-ready的连续区间另列，三路最大278.257979/281.131403/269.613264ms，均无>300ms；这是有明确条件的子集，不替代全段结果、源龄证书或授权安全验证。

故B/P1提供了可用初始化和正常段诊断证据，但不能凭六角色退出0、无arm故无fault、或73条mask被接受就签完整时效/P5。实际同序列profile归因由runtime已分工分析，本核对不重复或扩展实验。

# followup04证据与交付索引

本目录相对仓库根`/home/zhuyulab/ns3-workspace/net-01d/workspace`。完整GB级bag、native ledger/PCAP、Gateway大记录、完整原日志和一次提取的大逐例event-cache均保留本地，不重新散列或纳Git。Git小件白名单见DELIVERY_FILES.json；不是完整rootfs/原始数据备份。Root另做增量Git bundle。

|内容|文件/目录|
|---|---|
|通俗报告/独审|REPORT.md、INDEPENDENT_REVIEW.md、FAILURE_ATTRIBUTION_REVIEW.md|
|全母数/逐例/逐对/描述统计|RUN_LEDGER.json（7host/6物理）、TRIALS.csv、PAIRS.csv、SUMMARY.json|
|协议/共同source/六例准入|PLAN.md、PROTOCOL.json、PROTOCOL_REVIEW.md；gz-requests/COMMON_BINDING_58.json、COMMON58_DELTA.json及各candidate/ready|
|首行政失败/明确修订|ROOT_PRE_GAZEBO_AMENDMENT.md、gz-analysis/corr6201-common58-r01-a1/RESULT.md、failure-and-exit.json；原Hub/host失败及producer-command-after-failure相邻原件；ISOLATION*包含原误判/纠正快照|
|首输入/时序/候选/Goal/两个raw6|MESSAGE_AND_INPUT_OBSERVATIONS.json、INPUT_AND_TAIL_TABLE.csv、CACHED_GOAL_TIMELINES.json、event-cache/FIRST_OBSERVATIONS_AND_LONG_TAIL.json、TWO_RAW6_HANDOFF.json|
|旧bc18单对诊断/旧raw5 timeout|PRIOR_PAIR_DIAGNOSIS.md、A1_TIMEOUT_REVIEW.md、prior-pair/SUMMARY.json、A1-TOKEN4-HANDOFF.json；旧原大件/封存canonical不改、不再分析|
|六覆盖曲线/三对路径图|figures/coverage-six.png/.svg、routes-three-pairs.png/.svg；make_figures.py只读封存CSV/一次event-cache。大逐例cache保留本地，复绘依赖它及原metrics/reference-and-final.npz，不声称单独Git bundle含全部数据|
|两次精确RAM释放|r01-b与r02-b分析目录/ram-cache-release/{ownership-before.json,verified-copy-SHA256.json,result.json}；仅指定owned RAM删除，磁盘native十文件原件仍在|

## 每个真实case的固定小件

所有`gz-analysis/<case>/`含：`pre-analysis-exit-proof.json`（原55+实际daemon56）、`metrics.argv.json`、`.exit.json`、原stdout/stderr、`metrics.small-result.json`、`uuid-summary.json`、`rpc-decomposition.json`、`post-exit-resource.json`、原`metrics/result.json`与`coverage.csv`。各例原canonical仅一次，未读活动bag/SQLite/PRAGMA，均在writer/owned退出后执行。

每个`gz-runs/<case>/`保留原result、launch/control/events、节点/话题/Action、TF、地图/轨迹/bag等；相邻`.host-exit.json/.network-integrity.json/.native-load.json/.owned-runner.json/.producer-command.json`和`.cli-daemon-cleanup/{before.json,result.json}`、`.time-control/`、`.network/`均有原件。自动daemon回收在原host内完成，不是生产者手动补清理；其exitcode未知但实际退出有据。

- slot01 P1 A1: `gz-runs/corr6201-common58-r01-a1-fresh02/`，对应 `gz-analysis/corr6201-common58-r01-a1-fresh02/`。
- slot02 P1 B: `gz-runs/corr6201-common58-r01-b/`，对应 `gz-analysis/corr6201-common58-r01-b/`。
- slot03 P2 B: `gz-runs/corr6201-common58-r02-b/`，对应 `gz-analysis/corr6201-common58-r02-b/`。
- slot04 P2 A1: `gz-runs/corr6201-common58-r02-a1/`，对应 `gz-analysis/corr6201-common58-r02-a1/`。
- slot05 P3 A1: `gz-runs/corr6201-common58-r03-a1/`，对应 `gz-analysis/corr6201-common58-r03-a1/`。
- slot06 P3 B: `gz-runs/corr6201-common58-r03-b/`，对应 `gz-analysis/corr6201-common58-r03-b/`。

## 缓存及校验范围

最后B的`/dev/shm/net01e-f04-p06-b`保留；其完整磁盘复制在`gz-runs/corr6201-common58-r03-b.network/native/`。p02-b/p03-b RAM已获准按内容匹配后释放，其历史source_retained原字段不重写。原行政失败小RAM亦保留，不冒充complete native证据。

FINAL_SHA256SUMS只覆盖报告/统计/小handoff/两图及必要核心小件，不覆盖GB raw或自包含其自身。在仓库根可运行`sha256sum -c net01e/followup04/FINAL_SHA256SUMS`；本次生产者仅生成一次指定小件SHA，没有全历史/大raw重算。原权重/native/13DSO身份沿原封存记录和运行准入，不额外手工重hash。

## 恢复目录时的必要准备

Git不会保存空IPC目录。本轮已实际证明缺父目录会使Hub本地bind失败；在仓库根为未来**另行具体准入**的运行准备目录时，先执行 `rtk proxy mkdir -p net01e/followup04/ipc`。这只创建本项目父目录，不改运行源码、不启动实验；本轮已消费的case/READY不复用。原行政失败及其狭窄例外仍保留，不能以此目录命令获得一般重试或下一阶段授权。

# 2026-11-13项目整理记录

## 整理结果

|项目|结果|
|---|---|
|原日常工作目录|约132GiB|
|整理后日常工作目录|约160MiB，不跟随外置归档链接、不含共享Git对象库|
|外置历史项|211项旧目录、报告、草稿或采集副本；3,774个原已追踪文件不再混入日常索引|
|删除内容|7处可再生成APT/CMake/test缓存，以及一个与已追踪PDF逐字节相同的输出副本；合计逻辑大小3,837,442,061字节，约3.84GB|
|原始研究数据删除|0；失败、慢回合和原始记录均保留归档|
|最新结果|六次Gazebo小指标/报告、中文覆盖率与轨迹、PDF、PPO结构图及选择审计保留；最新缓存补入Git|
|固定版本|v1.1.0标签、PPO权重、机器人/SLAM/Nav2及当前通信执行代码未修改|

外置不等于释放同样数量的磁盘空间。归档在`/home/zhuyulab/ns3-workspace-archive/2026-11-13`，仍占本机存储，目的是将原始历史与日常代码分开。

## 先备份，再清理

完整清理前Git历史先制作自包含bundle、分4片推到[独立备份分支](https://github.com/Breeze-by/MARL_NS3/tree/backup/pre-cleanup-20261113)。随后从GitHub全新取回、重组、校验并fetch恢复，确认原工作提交、实际运行提交和v1.1.0标签都可恢复，之后才开始外置与删除。未跟踪原始数据不在Git备份中，因此只移动保留、不删除。

为避免把历史大日志重新带入日常main，整理后的代码树以原发布/main提交为父提交建立新的当前快照；原开发历史在备份中，原本地分支和Git对象库仍保留。main使用正常快进更新，未强推和改写冻结标签。日常克隆宜使用根README的`--single-branch --branch main`命令，避免额外下载备份大分片。

## 当前入口更新

- 根README聚焦当前工程、中文结果和实际代码目录。
- PROJECT改为当前研究路线与边界，不再滚动堆叠早期过程日志。
- `docs/CURRENT_STATUS.md`包含实际ns-3闭环和最新PPO作用审计；旧日期说明外置保留。
- `docs/SETUP.md`和`LOCAL_ENVIRONMENT.md`说明本机真实环境与新机器重建的边界。
- 外层工作区增加`MARL_NS3`便捷入口，更新README/PROJECT/AGENTS中的过时BASE-only、尚无RL/ns-3状态；通用工程原则保持。

## 必要验证

88项冻结/当前绑定及相关模型文件没有路径缺失、内容差异；现用16个原生运行产物仍存在。`workspace/`、`net01/`、`policy/`、根配置、输入和资产无源码差异。当前文档相对链接可读取。

执行既有CPU三观察重放，编码、合法mask、原logits/value、联合动作和目标记录均保持。只有3次前向，没有梯度、优化器、ROS、Gazebo、Action或环境step。结果见[CPU_REPLAY](CPU_REPLAY.json)。本次不重跑Gazebo，也不产生新的探索性能或实机安全结论。

## 精确范围

- [远端恢复记录](REMOTE_BACKUP_VERIFIED.json)
- [源码来源](CODE_ORIGIN.json)
- [计划与保护集合](PLAN.json)
- [本地归档位置清单](ARCHIVE_MANIFEST.json)
- [实际删除与大小](CLEANUP_RESULT.json)
- [验证范围](VALIDATION.json)
- [恢复方法与本机链接限制](../../archive/README.md)

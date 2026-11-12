# 历史归档与清理前备份

日常工程与现状请从根README开始。此目录只放归档索引，不把旧原始运行日志、失败现场和过时任务计划重新堆进当前工程。

## GitHub完整历史备份

[backup/pre-cleanup-20261113](https://github.com/Breeze-by/MARL_NS3/tree/backup/pre-cleanup-20261113)保存清理前完整、自包含Git历史的4个分片。备份推送后，已从GitHub重新克隆、重组、核验并实际fetch恢复；原清理前提交、实际运行提交和v1.1.0标签均可找回，见[远端恢复记录](../provenance/cleanup-20261113/REMOTE_BACKUP_VERIFIED.json)。

旧历史曾收进单个超过100MB的日志，因此采用分片bundle保存，避免为了清理重写或丢弃原历史。恢复：

```bash
git clone --single-branch --branch backup/pre-cleanup-20261113 \
  git@github.com:Breeze-by/MARL_NS3.git project-backup
cd project-backup
cat complete-history.bundle.part-* > complete-history.bundle
sha256sum -c SHA256SUMS
git bundle verify complete-history.bundle
git clone --branch backup/local-pre-cleanup-20261113 complete-history.bundle restored
```

日常main从保留的原发布提交建立当前代码快照，不携带这些大日志祖先；旧提交历史仍在备份中。原v1.1.0标签未修改，已有远端研究分支未改写，没有强推。

## 本机原始数据

目录：`/home/zhuyulab/ns3-workspace-archive/2026-11-13/research-data`。

归档按原工程相对路径保存，逐项位置见[ARCHIVE_MANIFEST](../provenance/cleanup-20261113/ARCHIVE_MANIFEST.json)。旧目录、文档和额外找到的旧草稿/采集副本经同文件系统重命名移出，原位置留下被Git忽略的本地访问链接。**原始研究数据删除数为0**；这些链接没有被宣称为只读权限。

Git备份覆盖已追踪内容、额外找到的本地源文件和外层入口文档；此前未追踪/忽略的大型原始数据、ROS根环境和外部构建产物未上传。它们仍保留本地。不能把这个Git备份叫作全部工作目录的云端备份。

链接仅保证本机宿主文件系统的读取，不保证新克隆或bwrap容器自动能看到外部归档。隔离容器若需重读旧原件，应明确只读绑定实际归档路径到原容器位置，或先按清单将该目录恢复到原位置；不从缺失文件猜测结果。当前生产启动链不依赖这些旧回合数据。

## 保留和删除的内容

- 保留：全部冻结机器人/PPO源码和配置、当前58项绑定、模型伴随记录、实际运行库/插件、ROS环境、Git公共库、最新六例小证据、中文图表与PPO审计。
- 外置：旧诊断/试验输出、原始Gazebo/网络记录、过时阶段计划/报告和旧日期状态文档。失败原件原样保留，不改写为成功。
- 删除：确认可再生成的APT/CMake/test缓存，以及与已追踪PDF逐字节相同的生成目录副本；用户桌面和文档目录的PDF正本保留。
- 原入口文档旧字节还单独保存在本机归档`entry-documents/`；外层README/PROJECT/AGENTS已改为当前工程入口，原通用工程原则保留。

具体范围与大小见[清理结果](../provenance/cleanup-20261113/CLEANUP_RESULT.json)。不要直接删除`net-01/workspace/.git`、`base-01-econ/upstream/.git`或现用build/install；它们仍被当前工程或其他worktree使用。

后续新输出应放到新任务目录，例如`local-runs/`；不要继续往旧输出链接中写入。需要恢复某项历史时只恢复对应目录，不必把整套历史重新放回日常main。

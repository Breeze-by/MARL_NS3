# 清理前完整Git历史备份

本分支是2026-11-13清理前的可恢复备份，当前工程请看仓库main。

旧历史包含单个超过100MB的研究日志，所以不直接推送原分支，而将完整、自包含Git bundle按80MiB分片存储。它不是新版日常工程，也没有重写v1.1.0标签。

恢复步骤：

```bash
git clone --single-branch --branch backup/pre-cleanup-20261113 git@github.com:Breeze-by/MARL_NS3.git project-backup
cd project-backup
cat complete-history.bundle.part-* > complete-history.bundle
sha256sum -c SHA256SUMS
git bundle verify complete-history.bundle
git clone --branch backup/local-pre-cleanup-20261113 complete-history.bundle restored
```

SHA256SUMS同时核验分片及拼接包。恢复后可访问原模型、源码、报告、全部已追踪历史及v1.1.0标签。清理前HEAD、文件身份及范围见BACKUP_MANIFEST.json。

**范围边界：**原始未追踪/忽略的大型实验数据、bag、rootfs及外部编译环境未上传Git。它们保留在原机器或本地研究归档；不能把本分支称为全部约132GB工作目录的云备份。清理不会据此删除原始研究证据。

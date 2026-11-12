# 项目整理独立小范围复核

**结论：当前记录支持本次文件整理按所审边界完成，未发现现用源码/库被误删或把整理扩大为新的实验结论。** 可交Root封存和发布当前快照；本审不代执行Git提交/远端main更新，不将尚未完成的发布写作已独立验证。

本次只读README、PROJECT、AGENTS、SETUP、CURRENT_STATUS、LOCAL_ENVIRONMENT、archive说明及本目录小记录/归档索引；没有展开旧日志Git差异、重读原始bag/ledger、运行模型/机器人/测试或计算大数据哈希。仅新增本文件。

## 清理边界与证据

- [远端恢复记录](REMOTE_BACKUP_VERIFIED.json)给出GitHub独立备份分支ee1624b、fresh取回四片/重组一致、bundle fetch恢复exit0，以及a768预清理、2c008原HEAD、cec5实际运行和a014发布提交。记录完成于17:32:32UTC，早于[整理结果](CLEANUP_RESULT.json)的17:34:37UTC。支持先备份并实际恢复验证再移动/删除，而非仅声称push成功；本审没有重复网络克隆或bundle校验。
- [归档索引](ARCHIVE_MANIFEST.json)有211项，与结果所列190项加21个旧未跟踪草稿/采集副本一致。原始数据外置与3774个已追踪文件退出日常索引均有说明；未将它们写作从存储销毁。未跟踪原始数据未上传Git备份，也没有被描述成完整云备份。
- 实际删除清单为7处APT/CMake/test缓存和1个PDF重复输出，逻辑大小3,837,442,061字节；PDF正本与桌面副本保留，先前“PDF也是缓存”的混称已纠正。归档外置后日常目录约160MiB是无跟随链接、无公共Git库的口径，文档明确不等于释放约132GiB磁盘。
- 先前精确计划审已核保护集合无祖先路径冲突，现用native ELF/13DSO/Step插件/clock witness解析路径不在删除目标。停后[VALIDATION](VALIDATION.json)记录88保护项无缺失、相对预清理内容差异空，workspace/net01/policy/config/assets/inputs无差异，16运行产物保留。本次不重算这些文件哈希或另做全库Git检查。
- 此前已读的f01生产入口、准入和graceful控制器链直接所需文件均保留，启动不靠旧ram47/资格数据目录读取通过结果。旧数据alias只保证宿主可访问，隔离容器/新clone需恢复或显式绑定；新archive/环境说明准确交代这点，不假称alias只读。
- [CPU_REPLAY](CPU_REPLAY.json)是既有三观察的3次实际前向：编码、mask、slots、动作、logits/value及原目标核对均通过，state unchanged，无梯度/优化器/ROS/Gazebo。这是模型记录重放检查，不是212回放重做、物理闭环或新机器Gazebo重建验证。

## 文档真实性

当前入口正确说明已训练固定PPO、实际ns-3接入与TCP业务适配；没有把全部原生DDS、同R域三机或共同仿真时间写成实机等价。最新六例阈值、64目标中62成功/2中止、PPO54/64多选及性能优势未证明，与此前独审一致。行政启动失败与历史异常原因未完全确定得到保留；没有用新正常例覆盖旧失败。

README区分main当前工程、旧v1.1.0行为标签与原发布Manifest；SETUP明确不是已验证一键新机安装，LOCAL_ENVIRONMENT保护旧编号源码、实际build/install和公共Git库。当前代码快照来源、完整开发历史备份与未跟踪本地原始数据三者不混写。新的CPU入口也没有被宣传成重做Gazebo探索。

仅一处建议作精确措辞：PROJECT中“所有现有完整任务窗口均按预算停止”宜改成“最新六次Gazebo任务窗口均按预算停止”。旧policy审计明确另有二维后端自然完成记录，较宽句子可能被读成否定那些原结果。这是文书范围修正，不是发现新实验错误或要求重测。

本次整理不改变策略、Nav2/SLAM、物理、RF、时钟或保护行为，不授予新实验、训练、NET-02或实机。原运行身份仍为cec5；后续发布快照按[CODE_ORIGIN](CODE_ORIGIN.json)另记，不将新文档提交追认为新增Gazebo资格。除上述措辞外，无需扩大验证或追加清理；Root完成最终发布回执即可收束。

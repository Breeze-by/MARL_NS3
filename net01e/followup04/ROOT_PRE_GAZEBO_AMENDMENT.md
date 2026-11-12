# 首次行政启动失败后的明确修订

Root已直接审查 `corr6201-common58-r01-a1.host-exit.json` 和 Hub 原 traceback：新阶段 `ipc/` 父目录没有准备，`asyncio.start_unix_server` 的 `sock.bind` 抛出 FileNotFoundError。原 host 真实失败、native 已经启动并在错误收尾中退出；ROS主运行器、Gazebo、中央策略和导航任务没有启动，没有探索性能数据。原六sidecar清理及native退出证据由生产者保存。

这是一次事前目录准备遗漏。Root明确授权只补建本轮自己的IPC父目录，不修改运行期源码、策略、导航、网络或安全参数。原失败、原READY与命令回执缺口全部保留，不得改成PASS。

为完成用户批准的三轮配对，允许准备一个新的首A1身份 `corr6201-common58-r01-a1-fresh02`，session `2026111267`，独立socket/RAM/output。它仍需独立隔离检查和Root READY/START；本文件本身不启动实验。原slot1的行政尝试与新的实际实验身份须在账本中明确关联，不能覆盖原记录。

本修订显式例外于原计划“不重试”的行政启动层：上限仍是六个真正Gazebo回合，另保留这一例未启动Gazebo的host失败（最多七次host尝试）。不是在观察覆盖率、机器人行为或无线成绩后补换失败episode。六个真正Gazebo的固定顺序、共同源码、种子、参数、时间预算与统计规则保持；任何实际Gazebo/ROS导航阶段阻断仍按原协议暂停，不自动补跑。

新增准备条件仅是：本轮IPC父目录已经存在且可写；具体socket、RAM和输出路径仍未使用。不得为此新建通用运行框架或放宽原资源/安全门槛。

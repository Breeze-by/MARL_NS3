# slot01首次host尝试：IPC父目录缺失，Gazebo未启动

Root具体READY/session2026111261、源码cec5/common58已准入；实际host UTC2026-11-12T13:23:17.981450+00:00—13:23:21.473943+00:00，exit1/3.491650wall。原Hub start_unix_server sock.bind因followup04/ipc父目录不存在而FileNotFoundError，未到IPC_LISTENING。生产者与Root预检均漏了该必要环境目录；不是冻结策略/导航/无线参数故障，不以改源码/门限掩盖。

事前外围producer-command文件也因尚无gz-runs父目录写入失败，未作为后续工具调用的停止条件；原host命令仍在明确START下执行一次。这个审计缺口与真实Hub环境FAIL分别保留，不伪造事前时间。相邻producer-command-after-failure.json仅事后绑定原host startUTC/命令。

native ELF确已由Hub启动，error-finalize保存native_exit0；但因未到ready/load gate，真实native PID缺测，control trace0bytes、完整性false，不能写native未运行或业务PASS。ROS runner/controller/Gazebo都未启动，physical/iterations/clock null、NN0/Goal0；新物理回合仍0，亦无T90/T95、地图、停止或canonical样本。

六实际sidecar PID均gone、remaininggroups空，原coordinator1、两clock0；coordinator原保护HOLD/native_closed_before_expected_shutdown。自动post-run hook真实执行matches0/signals0/cleanup_pass=true，证明此失败路径无daemon匹配的收尾接线，但不是有daemon或完整机器人整例资格。原error未吞，host仍exit1。

原READY/Hub/host/native不完整输出及新回执保留。序列已暂停，不自动mkdir后重试、不进slot02，不删除或用新case洗掉本次FAIL；等待Root明确裁定环境准备与未启动物理实验边界。

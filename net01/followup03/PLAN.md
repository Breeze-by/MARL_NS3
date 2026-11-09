# NET01 followup03：先测真实STEP/输出背压边界

从15b53完整交付继续，旧02所有原件不改。备份branch与完整bundle由root核验后建立net-01/followup-03。本阶段0新GZ/Goal/Nav2/NN；冻结核心模型、SLAM/Nav2/physics/源龄/guard/V3与原负载，不训练/NET02/push。

首项只改诊断：原controlTrace开关内，native每STEP begin/end及>=16KiB完整payload的stdout输出begin/end，以一次小行write走独立stderr；小消息仅汇总STEP输出条数/bytes/wall/threadCPU，不复制body。父hub独立async reader持续drain stderr，收到即记录native原戳与父接收mono，正常/异常finally都保存，避免只等nativeEND。hub另记大body真实read与owner.write/drain边界，drain不冒充native/ROS ACK。原stdout完整bytes协议/消息顺序/时钟算法不改。

新ELF独立build/followup03-boundaries，旧ELF/ns3/header保持。先给diff与构建身份，由root审唯一完整modeB连续8wall源/20wall总界/100HzFB/controltraceon/CPUprofileoff诊断；尚未运行。任何首fault按原门限锁存，不catchup/重戳/降低负载。fault后Gateway停止业务poll所致后续背压不得倒认为首fault原因。

测量只区分Run整体wall/CPU、其中真实stdout输出、hub读/转发与clock链；trace本身额外少量syscall/解析开销记录为观察扰动，不以未知间隔唯一归因。没有实现同步coordinator/FIFO线程或新调度优化。后续方案据实际证据再审。

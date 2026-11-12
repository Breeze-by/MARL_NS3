# NET01 followup03：先测真实STEP/输出背压边界

从15b53完整交付继续，旧02所有原件不改。备份branch与完整bundle由root核验后建立net-01/followup-03。本阶段0新GZ/Goal/Nav2/NN；冻结核心模型、SLAM/Nav2/physics/源龄/guard/V3与原负载，不训练/NET02/push。

首项只改诊断：原controlTrace开关内，native每STEP begin/end及>=16KiB完整payload的stdout输出begin/end，以一次小行write走独立stderr；小消息仅汇总STEP输出条数/bytes/wall/threadCPU，不复制body。父hub独立async reader持续drain stderr，收到即记录native原戳与父接收mono，正常/异常finally都保存，避免只等nativeEND。hub另记大body真实read与owner.write/drain边界，drain不冒充native/ROS ACK。原stdout完整bytes协议/消息顺序/时钟算法不改。

新ELF独立build/followup03-boundaries，旧ELF/ns3/header保持。先给diff与构建身份，由root审唯一完整modeB连续8wall源/20wall总界/100HzFB/controltraceon/CPUprofileoff诊断；尚未运行。任何首fault按原门限锁存，不catchup/重戳/降低负载。fault后Gateway停止业务poll所致后续背压不得倒认为首fault原因。

测量只区分Run整体wall/CPU、其中真实stdout输出、hub读/转发与clock链；trace本身额外少量syscall/解析开销记录为观察扰动，不以未知间隔唯一归因。没有实现同步coordinator/FIFO线程或新调度优化。后续方案据实际证据再审。

## 唯一实际诊断15结果

c97f830独立ELF按已审modeB/原8源20wall实际执行一次，11.756wall全owned退出，clockFAIL。失败STEP .9真实入口已收到；37.565ms后原lagguard触发；首大payload输出在STEP入口后54.926wall/54.927CPU ms，晚于首fault。主要首段是native真实无线事件处理CPU，不能把故障后hub owner.drain/最终native stdout阻塞倒作第一原因。原始边界已由父进程在异常路径保存，详见MEASUREMENT_15.json及runs/continuous-dds-15-wifi。没有自行重试/修改时间协调/门限/负载/网络，等待根审下一方案。

## 原因分解与独立修补（均不追认首clock故障已修）

fault后IPC排空修补44c2c63保留firstfault、继续读实际ACK/bytes但在Link/Topic/Action副作用前discard，通道IO关闭仅记一次且不再poll；本机R清理继续。根审已读，尚未在后续连续夹具运行验证。

CPU诊断9c44000使用独立followup03-cpu ELF，原V3/ns3库不改。唯一native-cpu-burst-01在18wall native界内0.352wall结束，0ROS/GZ/Goal/NN；3×160611+3×55112B初始burst最后1.0→1.1sim STEP为目标。177.681wall/166.469CPU ms，自有7类exclusive51.501ms/30.94%，余114.968ms/69.06%未归属，不能全叫PHY/PCAP。输出647169B仅.886wall/.681CPU ms。详见CPU_BURST_SUMMARY.json和CPU_NATIVE_IDENTITY.json；inclusive不相加，测量开销未扣除，不称容量PASS。不自动追加运行或改时钟/模型。

# followup04事前计划：同一停后修补版本3对A1/B

用户新批准最多6个新Gazebo回合（每例180sim），先旧日志诊断再重复。基线cec5c5676f8ba156a6cdab05ce8fc94575987df5，分支net01e/followup04-paired-common；实际执行代码含ada4e14停后hook。没有新增算法/运行期改动。旧bc18两例只作动机/诊断，不填新槽、替换失败或混入均值。当前新Gazebo=0，全部START须Root唯一READY。

## 必要输入及已完成诊断

- 已关闭旧canonical/result/coverage_curve、allocation-events、events、trajectories及launch，单次导出prior-pair/A1-extract.json、B-extract.json、SUMMARY.json与约108KB的A1-TOKEN4-HANDOFF.json，后续复用缓存。没有旧bag/PCAP大件或新模型推理。
- PRIOR_PAIR_DIAGNOSIS.md列27.76sim时间账、首次候选/任务分歧及postT95实际控制/恢复异常。缺独立CancelResponse/精确服务发送及recoveries/nav_time就标缺，不追唯一罕见故障。独审A1_TIMEOUT_REVIEW.md/PROTOCOL_REVIEW.md复用。
- 所需执行输入全部继承：冻结6d模型/701/Frontier/KEEP-WAIT/SLAM/Nav2/RF/world/spawns、static-footprint-common-v1、首8Step诊断63e库、pace20。共同源绑定由57继承更新host哈希并加入cleanup模块成为58，使用已封存新源码SHA，不重新散列旧模型/DSO。源码先独立锁，不在回合间改。

## 六槽、顺序与共同身份

事先固定顺序：pair1 A1→B；pair2 B→A1；pair3 A1→B。奇数三对只是部分平衡先后，不宣称完全随机/平衡。具体身份/新session/socket/RAM见PROTOCOL.json；每例独立关闭/退出/清理目录，旧case绝不复用。

A1=原ordered local Gateway业务，direct_reference=false，不是A0；native/profile B仅clock control。B=原真实ns-3 Wi-Fi全业务CDR，不理想旁路/降级。原physics_seed=2026110601、NETWORK_LOCK_V3 rng_seed2026110901/rng_run1全部固定；fresh重复评估ROS进程/观察/执行重复性，不是独立RF种子泛化，相同seed也不保证逐事件随机数消费/输入相同。

## 预算、安全及失败

每例原180sim/130decisions；startup180wall、autonomy720wall、outer900wall、cleanup90wall、host1000wall、physical stop12wall、2wall、one in-flight/10step/10sim-ms/credit等原门槛不变。300sim-ms健康合同及其他TF/source/health/mask/receipt/停止/UUID全部保持，非实机保证。post-run新helper在原资源结束后自动回收精确所属CLI daemon，真实首例重点核实；end_utc/host_wall含其上限12wall管理员清理，不续自主或物理。

每例Root单独READY/START，首启动/关键软件/安全/无法停稳/进程或新hook阻断后暂停余槽，保首次失败，不重试或补槽。任务内合法Nav2超时/取消/aborted与安全保护、进程失败分别报告；不为目标未达调参/换图/改Goal。即便T95已达后发生失败也保T95和后续FAIL事实。是否继续后续槽由Root明确决定，不生产者自动洗PASS。

## 原资源与停后管理

只读初始原公式tmpfs25077174272bytes>=16GiB、MemAvailable72491679744>=24GiB；非资源保留，具体START和producer再次原检查。旧A1 RAM仅约13.93MB，现资源足，不清历史缓存。预计3个B大副本不能无限同时保留；每例原native退出、磁盘copy complete且writer结束后，若下一例原门限不足，提交**该已结束新case**精确RAM/磁盘凭据与释放清单给Root，一次核准后只释放那一份临时副本（必要内容核验只一次）。磁盘原件、别的RAM不动，不降guard，不为资源失败自动重启，不建缓存框架。

## 固定指标与全母数

记录各例真实T0、首次可得观测/初始正确自由覆盖、地图source/receipt与首次NN输入/Frontier/Goal、原主wall/实际RTF/现有CPU/Step记录，不增加热路径监视。主指标原canonical首次质量有效T95及T90、末样本质量/覆盖、180sim完成率、三机参与/路径/重复与任务UUID/高层timeout/原raw状态，物理停稳/PAUSE/退出/新自动daemon cleanup分列。没有测到的CPU/时延项标缺、不双算包含关系。

全部6槽含失败列出，未达T95记录截止与未达，不填180末值；每个预注册pair给B−A1，缺一臂则该pair缺失且失败单列，不用旧bc18替代。n=3描述性展示每例/范围/配对差，不签显著性、纯RF因果或通信优化收益。A1后T95超时单列任务可靠性。

运行期只原append或精确owned liveness，约60wall简报；所有并行分析、bag/SQLite/PRAGMA、重I/O/编译/Git/散列/备份暂停。全部writer及精确case daemon清理完后原canonical每例仅一次，独立小件复核后再审下一例。无A0/C/地图切换/额外资格Gazebo、RL训练、NET02、实机或push。

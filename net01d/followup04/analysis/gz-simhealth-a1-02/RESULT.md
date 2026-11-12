# gz-simhealth-a1-02 — no-active-SQL attempt, startup failure

**FAIL，preflight未通过，未进入自主探索，0NN/0Goal。** 这是Root单独准入的同条件counterfactual一次，runtime C4、activation `b08cc0fa56d4cfae048d1fd7d518e09f90410e74`、session2026111145；01首败原件保持。全程没有打开activebag、SQLite、PRAGMA或新增ROS监控；只读取现有append日志与exact-owned进程存活。未重试/改源/B。

host210.559014wall退出1，Hub/native0，未触发1000wall force。原180sim/130decisions/start180/autonomy720/outer900/cleanup90/stop12与冻结world/spawn/Policy/SLAM/Nav2/物理/source/radio不变。

原coordinator记录给出早于preflight超时的真实首进度错误：

- 最后actual R clock G.02 callback mono604256409043392。
- `independent_progress_wall_failure` mono604258409572291，reason=`actual_clock_progress_wall_timeout`，间隔**2.000528899wall秒**。
- 下一G.03 callback mono604258487954734，故障后**78.382443ms**才到。
- 当时第三physical-token record为604256526737223，到clock故障尚约1.883wall秒；nativeACK.01在604256537029261，也未达到native2wall期限。不能把实际clock故障改称物理RPC超时或RF问题。

coordinator随后HOLD，原Observer仍以原startup界报preflight missing model/odom/drive/scan/maps/TF/peer state/clock，自治0sim/0wall。停止观察阶段稍后推进到G13.50/N13.49、并收到数据，不得反向填补失败的preflight。最终coordinator1/failure保持actual_clock_progress_wall_timeout/expected_shutdown=false；原observed_stop=true，但seal报`Expected seal lacks final physical stop/authority/RPC closure`，run_integrity=false。这些标志不因进程退出或晚数据改写。

实际old0cc/13DSO/exe/Hub父关系门检全true；C4/frozen critical tracked diff前后为空。原END/复制完成、四PCAP与完整native证据保留。无强制组信号，13个registered/observed PID最终gone、91/92空，本次无额外case-owned daemon，69未碰。

所有writer/owned退出后，原R canonical工具依授权只执行一次，exit1：没有启动controller，因此`controller/allocation-events.jsonl`不存在；在读取controller journal时即失败，尚未读取DB shard。此例指标为**NOT_APPLICABLE_NO_AUTONOMY**，没有coverage/T95/路径资格；没有造journal/exploration event、替代地图或改标准。

原件：[small-result.json](small-result.json)、[首coordinator failure/control记录](small-raw/coordinator-failure-control-rows.json)、[原process/stop事件](small-raw/process-stop-events.json)、[canonical argv](metrics.argv.json)、[entry失败](metrics.exit.json)。本例与01失败机制不同：它不能证明或否定01 SQLite锁的唯一owner，也不是可用于探索性能比较的完整no-active-SQL基准。

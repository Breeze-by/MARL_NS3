# gz-simhealth-a1-01 — recording failure retained

**FAIL，不是180sim完成，也不是Guard/Policy失败。** 原Observer在G177.25报 `Controller, launch or bag exited during autonomous interval`；自主G21.05→177.25，共156.2sim/243.233908wall。host317.991070wall退出1，未触及原1000wall界。原件保留，无重试、B或参数修改。

真实runtime为`c4ad853e7e5e8707a0e5a0be1426bc84b4bd2e1e`，activation `a0543d1f65fa9c2a3a9bc7948f446a0491a891f6`；新simhealth合同、冻结6d Policy/原Corr6201/compact3/SLAM/Nav2/物理/source/QoS/radio未改。实际old0cc/13DSO/exe/Hub父关系门检均通过，前后生产/frozen critical diff为空。

## 直接记录器错误与因果边界

bag.log原末尾记录：在Unix1794386463.508784438写remaining cache，1794386463.510448799打开bag_1 READ_WRITE，随后抛出 `rosbag2_storage_plugins::SqliteException` / `SQLite error (5): database is locked`。原退出处理对早已退出进程直接return，未记录bag确切returncode，不能伪填-6。

实际fatal event为UTC08:41:44.959884/Unix1794386504.959917/G177.25，与上述有timestamp的writer日志相差约41秒，不能伪称同时。原process事件证明exploration随后收到SIGINT，在08:41:46.550337退出0；launch也是稍后原SIGINT→0，均不能称自然任务完成。控制器末尾仍有真实Nav2结果，未见import/推理崩溃或Guard fault证据。

本轮运行中按当时获准方式做过live只读SQLite：最后两次读最新Rclock和各三条odom，分别选择bag_0/bag_1，并显式close。只读连接也能持SHARED锁，不能预先排除观测与writer交互；但当时没有记录exact SQL connection/query begin/end或异常mono，**唯一锁owner/严格重叠与唯一监测因果仍UNRESOLVED**。保留原工具调用与已有rounded采样mono，不伪造精确区间；见[live-sql-monitor-evidence.json](live-sql-monitor-evidence.json)。此后停止所有activebag打开/SQL/PRAGMA，未改recorder或busy_timeout。

## 实际闭环与安全保存

31次NN推理，9个实际accepted Goal（3/2/4）；结果tb1成功3、tb2成功2、tb3成功3+abort1。三机原路程9.102/5.590/12.981m，SLAM/merge增长和实际反馈/终态再分配存在，最小pair距离.733755m。这些是失败前实际闭环活动，不补成完整180sim资格或性能PASS。

原observed_stop=true、lifecycle_pause_healthy=true，authority退出、ownershipclosed/0unterminatedUUID。active_cancel_pass=false，本例未演示停止时仍运动的active UUID取消。hazard/Gatewayfailure/coordinatorfailure均null，但recording fatal令run_integrity/network_integrity/engineering_closed_loop=false，原标志不改写。

Hub/native退出0，原END后54583 ledger attempted=captured=written、failed=false；完整原4PCAP和所有native文件12490785B复制完成，tmpfs源保留。coordinator与R/Cwitness退出0，无force/remaininggroup。exactcase-owned R92daemon589012以原标准命令stop0后最终gone，15个registered/observed PID全部gone、91/92空，69未碰。这是实际补清后的闭合，不声称自动daemon登记已修复。

## 原R primary唯一离线评估

全部模型/owned退出后，沿原`workspace/gz01/analyze_recorded.py`、原ROI/质量gate/起点与error终点，**只执行一次**完整多shard入口，命令见[metrics.argv.json](metrics.argv.json)。入口exit1：recorder abort后`bag/metadata.yaml`缺失，`bag_records.records`在读metadata时即失败，尚未读取DB shard。

本例原R canonical指标因此为 **UNAVAILABLE_CANONICAL_ANALYZER_FAILED**，T50/80/90/95/98与最终正确free覆盖没有可验收数值。没有重建metadata、跳坏shard、改标准或用停止后/C89地图替代。原DB、异常/缓存可能缺失的事实全部保留；不是“阈值未达”的同义说法。

小原件索引：[small-result.json](small-result.json)、[process/fatal/stop事件](small-raw/process-stop-events.json)、[bag尾30行](small-raw/bag.log.tail30.txt)、[launch尾](small-raw/launch.log.tail30.txt)、[controller末journal](small-raw/controller-ledger.jsonl.tail30.txt)、[metrics失败](metrics.exit.json)。原Gateway/native巨件没有为此分析读取；不存在新的模型或回放结果。

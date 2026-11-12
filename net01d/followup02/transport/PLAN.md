# Fresh 89/95 严格负例：源审计划，尚未运行

唯一新文件 `check_fresh_89_95.py`，host和ROS worker两角色。只验证新TCP传输下 `/merge_map`（flow89、OccupancyGrid）与 `/net01/controller_records`（flow95、String）的实际新身份交付/断链隔离；不再重复其它业务流，不开始导航或网络优化。

## 复用边界

host复用实际packet_hub、新锁定TCP ELF、原网络B与原RAM证据机制。worker在现rootfs运行，真实C91/R92 Context、原TopicWire capture/receive及QoS、原LinkSession和实际Gateway.send/receive方法。只在本fixture构造两条数据路径：`Gateway.__new__`提供该路径必需字段，短时patch本进程TopicWire的flow工厂仅选择原runtime specs89/95；不改生产文件、消息或QoS。

**这不验证完整Gateway构造/dispatcher/生命周期。** 不调用其正常构造器，避免创建不相干LocalStop、Action、cmd_vel实体或退出动作；没有HQ、Policy、Goal、速度publisher/消息、Nav2、Gazebo或训练。实际Gateway发送/接收逻辑仍原样执行，两条业务只从C91真实typed发布，经真实native完整字节交付，再由R92原TopicWire发布给真实typed消费者。

三条TCP连接与三向应用HELLO/ACK分别核验：IPC READY不代表连接；worker必须收到原LinkSession三STA往返ACK，结束host另核native计数3connect/3accept。

## 固定消息身份与时序

固定session `2026111102`、nonce `net01d-fresh8995-01`，序号1..5。map为250×220/55000cells完整OccupancyGrid，固定merge_map frame、0.05m resolution，map_load_time字段保存session/sequence，合法栅格值还包含固定nonce编码；String保存同session/sequence/nonce。按真实ROS序列化规范化后比全部typed字段，不比较未定义padding。

1. 0→2.50sim推进并完成实际三STA HELLO/ACK。
2. seq1两条消息由C91实际发布/捕获，必须在cut前真实到R92。
3. **原真实RADIO/Range gate在3.00sim切断，3.60sim恢复**。切断后继续真实发布并等待C侧捕获seq2@3.01、seq3@3.11、seq4@3.21，每序号均有map+String。
4. 到恢复前R92不得收到任何这六个新身份，也不得存在切断期native完整收件；旧seq1缓存不算新消息。
5. 恢复后3.61sim发布seq5两条消息，推进固定8sim并要求其真实到达。seq2/3/4恢复后迟到可以发生，逐条保留native接收时间与DDS消费者时间；不把迟到称为丢失，不按旧UDP例假定cut消息永久消失。

worker对原Gateway方法的clock字段由本fixture显式KNOWN/STEP synthetic控制，Hub复用严格admission协议模式；**没有真实Gazebo `/clock`，不签同步、wall时延或AoI通过**。其25wall限为实验进程限，不修改原生产300ms要求。

## 唯一拟执行命令

从 `/home/zhuyulab/ns3-workspace`，待root完成源码审查/身份封存后单独批准：

```sh
rtk proxy timeout --signal=TERM --kill-after=3s 35s python3 -B net-01d/workspace/net01d/followup02/transport/check_fresh_89_95.py --native /home/zhuyulab/ns3-workspace/net-01d/build/followup02-native-tcp/net01-payload-tcp
```

锁定现TCP源码/ELF身份沿用root记录（当前ELF1e8）；执行前不得悄悄换模型/参数，具体完整身份记入独立准入。worker25wall、host30wall、外35wall+3秒kill界限；无自动重试或第二目录。输出独占 `followup02/runs/fresh-8995-01`，RAM独占 `/dev/shm/net01d-f02-fresh8995-01`；旧路径存在直接失败，不覆盖/清理。

必须等当前实验全部结束，并确认没有旧C91/R92生产者/消费者仍参与本域，不能与Gazebo或其它负载同时运行。host只终止本例新建session的process group；强制清理即FAIL，原失败、原Hub状态、PCAP/ledger及RAM保留。没有宿主网卡或namespace更改。

## 交付与判定

worker保存全部源发布、C捕获、native实际抵达身份、原Gateway路径记录、R目的发布、typed消费与恢复后迟到消息；失败时同样保存已获证据。host要求worker/Hub/native成功、完整证据copy及真实3连接/一次cut/恢复，不能只看本地消费者仍收到旧缓存。

结果最多 `PASS_FRESH_89_95_ONLY`。它补这两条TCP数据路径的新身份旁路负例，不替代其余业务、安全时效、完整Gateway或Gazebo验收。当前没有运行、Node初始化或模型调用证据，不写PASS。

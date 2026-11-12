# 四组Gateway成本：一次实际离线导出

activation d5039d0，唯一命令exit0。每组原Gateway各读取/解码一次；A0原direct-safety另一次。没有native ledger、PCAP、bag、ROS/模型或哈希扫描；本摘要只读取新导出结果，没有重读原件。

| 组 | normal健康/accepted masks | 自主RTF | Peer入口→health发布返回p95 wallms（非完整callback/CPU） | tb3健康publish→intake p95 | tb3 mask wrapper→accept p95 |
|---|---|---:|---:|---:|---:|
| A0 | 5400/5400 | 0.633293 | 29.380 | 3.314 | 9.121 |
| A1 | 5400/5400 | 0.617744 | 23.484 | 19.548 | 26.844 |
| B02 | 5399/5400 | 0.423380 | 28.284 | 102.312 | 133.443 |
| C | 5400/5401 | 0.472646 | 26.487 | 125.250 | 165.935 |

表中为每stage原样本分位数，不能相加或把组差直接叫RF/CPU代价。各robot完整n/min/median/p95/p99/max、worst witness、母数与flow/CDR计数在各组JSON；small-summary.json含三机常用stage与窗口。

原自主窗口与actual Rclock mono bracket分别保留，未用Unix时间减mono。A0/A1/B02/C源身份实际为AAE/2be/AAE/bd663；C读取实际traced.ready。所有适用selected matching无missing/ambiguous；A0/A1不适用的业务native/queue阶段不填0延迟。B02的5399健康与C的5401mask是intake窗边界cohort数量，不能当丢包/重复消息结论。

A1健康5400、B02健康5399、C健康5400的producer→C及C→R现有CDR字段/hash比较全等；各组mask publication binding分别5400/5400/5400/5401全等。A0没有直接R健康CDR hash，因此对应检查NOT_MEASURED，不冒PASS。

逐包exact receipt_sim仍UNMEASURED；mask wallgap上界即使超过300ms也不是本profile的失败判据。B02/C tb3 mask wallgap上界max为307.980/310.647ms，仅描述wall成本。whole actual Guard faults及原result/过程结论独立保留；A0依然PROCESSFAIL/controller1，rawhost0/networktrue与任务指标不能覆盖。

B02/C的health socket queue→flush p95(tb3)为.225/.255wallms，endpoint→intake为.086/.090ms；剩余host/native路径还不能称纯模型服务或airtime。native-agent小targets已就绪：B02-native-targets.jsonl 10799行、C-native-targets.jsonl 10801行（各约6.48MB）。仅含normal已由R消费的匹配ID/flow/seq及相关mono/meta，不是全native ingress/loss母数；A0/A1相应文件空。该Gateway脚本没有自动启动native；随后Root独立授权的一次native stream已完成，见[Native摘要](../native-costs-01/SUMMARY.md)。Gateway阶段原JSON的当时未测状态不回写。

原read/decode counts与字节/耗时见read-manifest.json、manifest.json；新summary不覆盖原各组JSON或case原件。没有改判据、补样本、重试加载或资格升级。

Peer该stage固定为publish_masks的timing.entry_monotonic→timing.health_publish_after_monotonic：含snapshot、3grid/build/data/publish及health序列化/发布，不含随后event_lines.append(json.dumps(...))，不是完整callback或CPU。peer_timing=false只禁可选timed_call线程CPU包装，不影响原内联wall记录。数据与导出JSON未改。

后续native实际结果：B02/C10799/10801条件ID全match；scheduled admission→complete p95=17.317561/53.256243simms，p99=19.315920/60.688117，max=23.582208/82.456931。该单位为模拟时间，含TCP/队列/WiFi/重组，不与本表wallms相加，不是airtime/逐包CPU或全输入loss率。原ledger各一次stream，0Gateway/PCAP/bag重读。

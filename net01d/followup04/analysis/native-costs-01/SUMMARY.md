# Native模型服务时间：一次原账本流式导出

唯一独立授权执行exit0，Root声明准入源码commit fde3cdb（完整值见execution-record），模型运行0、自动重试0。B02/C原ledger分别只open1并完整stream；不读Gateway/bag/PCAP/stderr/旧B1，无原件重读。本摘要仅使用新B02/C/manifest/execution-record JSON。

| 条件cohort | 完整匹配ID | scheduled admission→complete p95 simms | p99 simms | max simms | 原ledger行数 / 字节 | 离线stream wall秒 |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| B02 | 10799/10799 | 17.317561 | 19.315920 | 23.582208 | 18,693,385 / 3,123,224,761 | 191.729123 |
| C | 10801/10801 | 53.256243 | 60.688117 | 82.456931 | 18,722,606 / 3,124,389,295 | 187.390982 |

cohort为原normal Rclock bracket内已被R消费的health/mask ID，B02=5399health+5400mask、C=5400health+5401mask。全部具有唯一ipc_ingress、实际Socket::Send接受、tcp_frame_rx与完整message_deliver；无missing/ambiguous/duplicate/wholebody或chunk byte/RX时间不一致。0未完成/重复是这个条件cohort的结果，**不是所有输入的丢包率或全网络无drop**。边界前入网后在窗口内到达的样本保留，完整boundary counts见原新JSON。

admission_ns是SENDAT明确的scheduled application admission；tcp_write在实际正Socket::Send之后记，complete是所有实际接收应用fragment重组完。message_deliver的total是含8B RPC前缀的整body，body_bytes仅末片长度，不混为整ROS消息。模型服务含TCP unsent/connection/send queue、WiFi竞争/重试与重组，**不是PHY airtime或纯RF**。同profile仍有不同路径/负载/输入可用时刻；C服务时间较长与其单回合T95较低可以同时成立，不能声称受限radio提升性能。

离线191.729/187.391wall秒仅账本解析成本，不是模型运行CPU、仿真wall或报文时延。逐报文CPU与wall成本份额未测；simms不与Gateway wallms相加或按平均RTF换算，重叠stage/分位数也不相加。partial-frame Send calls B02=69230/C=70175仅表示该调用后frame尚未完整（含GetTxAvailable限制），不是Send少接收了offered bytes：两组offered−accepted总差0。

全部stage n/min/median/p95/p99/max和最差actual ID/seq/from-to/flow/bytes/三时刻witness见[B02](B02.json)、[C](C.json)；[manifest](manifest.json)保留各open/row/bytes，执行命令/PID/退出与来源见[execution-record](execution-record.json)。原阶段JSON、Gateway产物、模型原件不改。导出完成不升级A0过程FAIL或整体NO-GO，不授权新实验。

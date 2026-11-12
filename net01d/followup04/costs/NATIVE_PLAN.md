# Native costs: SOURCE_ONLY

未执行、未测试，NATIVE_ADMISSION.json 的 execution_authorized=false。当前 C 模型回合不受影响；本阶段只写此计划、禁用准入及 stream_native_costs.py。Root 源码/计划审查和单独 START 后，且全部模型/写进程退出、首阶段 Gateway 导出完成，才可按准入命令运行。不修改生产源、冻结 RL v1.1.0、源率、RF、停止逻辑或历史结论。

命令（cwd `/home/zhuyulab/ns3-workspace/net-01d/workspace`）：

```sh
rtk proxy python3 -B net01d/followup04/costs/stream_native_costs.py --cache-directory net01d/followup04/analysis/costs-four-arm-01 --directory net01d/followup04/analysis/native-costs-01
```

固定 B02=gz-simhealth-b1-02、C=gz-simhealth-c1-01。每 case 原账本位于 case 的 sibling `<case>.network/native/packet-ledger.jsonl`（不是 case 内的 `.network`），恰好一次完整顺序二进制流；不做 stat/hash/预扫描/重读。不读旧 B1、Gateway 原件、bag、stderr 或四份保留 PCAP，不复制完整 ledger/cache。B02 旧小摘要曾记录约 3.1GB（本准备阶段未 stat 或读取原账本）；C 大小未测，不估造。读取量是两份实际完整账本，wall 时间待运行 manifest 实测，不预设吞吐。

只加载首阶段 `B02/C.json` 摘要和各 `*-native-targets.jsonl` 小缓存。内存为目标 native ID 的身份、常数个阶段时间/计数、每目标常数个当前分片前缀，以及每完整匹配目标的统计值；不保留逐行账本、TCP 包或全 Gateway 行。缓存 normal R-consumed cohort 原 kind/robot/sequence/accepted/ID 保留为见证；缓存缺身份、重复 ID、账本缺 ingress/write/RX/deliver、重复 ingress/deliver、身份或字节/分片不一致分别记数并排除完整成本匹配。母数同时报告缓存行、唯一 ID、各阶段存在/缺失、完整匹配及不可用原因。此 cohort 已条件于 R 消费，不能充当全 ingress 或丢包母数。

已只读核对实际源码：

- `net01/native/payload_transport.cc`：event 经 EventLedger 输出 `kind/ns3_ns/monotonic_ns`；ipc_ingress 的 `from/to/flow/message_id/body_bytes/admission_ns` 来自实际 SEND/SENDAT。admission 是计划 native 注入时间，可晚于 ipc_ingress 的当前 ns3_ns；source_stamp_ns 是原 ROS 戳，绝不用作 TX。
- `net01d/followup02/native/tcp_stream_draft.inc`：tcp_write 在 Socket::Send 返回 accepted 后记录，`offset/body_bytes/total` 是原分片；`frame_offset/offered_bytes/accepted_bytes` 是含 36B 头的 TCP 流提交字节。CHUNK=1164。多个 Send 允许分片部分接受，工具按每消息前缀核对；不能叫 PHY TX 或 airtime。
- tcp_frame_rx 来自真实 Socket::Recv 解出的完整分片，message_deliver 在原重组器 `received==total` 后记录。核对总字节、分片数、重复/缺口及 Gateway ns3_rx_ns。
- `net01/tools/packet_hub.py` / `net01/hub_client.py`：Gateway native_meta 用 `sender/receiver/flow/message_id/bytes/ns3_rx_ns`。bytes 含实际 native 消息体中的 RPC 8B，直接匹配 native total，不能拿 CDR bytes 替代。
- `step_begin/end` 的 monotonic/thread_cpu 仅经 NET01_CONTROL 写 stderr；不在 packet-ledger。工具明确 CPU、STEP/Run wall 未测，不额外第三次流读取 stderr。

统计为 admission→首/末 Send accepted、首/末 Send accepted→完整重组、admission→完整重组，单位 sim_ms。报告 n/min/算术 median/nearest-rank ceil(p*n) p95/p99/max/负值数/最差实际身份见证，整体及 robot/kind 分组。保留 early/inside/late native monotonic 事件相对 normal R-clock bracket 的计数，不截断匹配前因或后果。服务时间包含 native/TCP 队列、协议及 Wi-Fi 重试，不能隔离为纯 RF、CPU 或 airtime；各阶段不可重叠加总。

新输出目录必须不存在。manifest 保存每 case ledger opens、读取行数、字节数、耗时与退出状态。首个错误保留当前行号/字节位置及解析失败行的最多 240B 前缀，立即失败，不自动重读。输出仅费用说明，不覆写实际 case 源身份/原失败或资格结论；实际身份直接继承首阶段的逐 case actual_source_identity，不替换成共同计划源。

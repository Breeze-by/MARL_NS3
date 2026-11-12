# A02：源TF新鲜，校正header在转发/接收链上落后

A02已经结束：preflight true、smoke_started false，真实pause .35wall/固定anchor/三Nav2 startup/原停稳及三pause通过。resume后STA1 arm@149.3拒绝，reason=bound_mask_receipt_stale，无latched fault；0HQ/0NN/0goal。最终原停稳/三pause/空UUID闭合健康，但整轮integrity false，B/C暂停，不能只等下一fresh帧重arm。

仅封存bag的145–150sim `/clock` 和三机 `/tf` 共1527条被解码，无第二窗口/Node/重放/实验。原数据见 `TF_CHAIN_145_150.json`。

| robot | C Peer@149.3实际用header | C源龄sim | R原bag已记录的新header | R bag receipt sim |
|---|---:|---:|---:|---:|
| tb1 | 148.419 | .881 | 149.419 | 149.2 |
| tb2 | 148.314 | .986 | 149.514 | 149.3 |
| tb3 | 148.392 | .908 | 149.392 | 149.2 |

同期odom源龄仅.014/.042/.027sim，correction receipt仅.026/.025/.009wall新鲜。相同145–150时段，已捕获同一次TF CDR→C实际publish每flow各313条，wall中位.421/.383/.388ms、最大2.217/2.616/1.834ms；没有秒级捕获后direct传输延迟。哈希只对应同一次captured CDR和其交付body，没有用独立DDS序列化padding负匹配。

这不是R原SLAM当时只生成约1sim旧header的证据。尚不能唯一分段：R订阅队列/捕获前回调延迟，或C发布后Peer订阅队列/执行延迟。R bag receipt不等Peer私有ACK，也缺当时source发布wall，不将逻辑GZ时点对应冒充唯一wall因果。

静态代码：gateway.poll每轮只一次C spin0、一次R spin0；R同节点还承载3×50Hz steady保护、20Hz状态、30Hz Action readiness、clock/model及全部业务订阅。上行TF reader/C publisher和Peer C reader均depth100，原Peer收到map→odom会刷新receipt并调用原project_latest，后者按原Buffer Time0取值，没有重盖stamp或插值修复。这是需要分段的真实耦合边界，不据此断言唯一CPU/队列根因。

最小待审只读观测：在现TopicWire捕获/目标发布时记录原map→odom header、node sim/monotonic及同body身份；BoundPeer外部receive_tf wrapper记录原调用前后原header与实际correction_stamps。只调用原方法一次、无额外lookup/订阅/改QoS/改源值，纯RAM收尾落盘。必要单个无控制顺序检查仅验证字段/调用/异常原样；目前未实施观测、未准新Gazebo，不调SLAM/阈值/网络。

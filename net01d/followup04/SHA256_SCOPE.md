# 交付校验范围

SHA256SUMS覆盖选定的最终报告、独审、身份/预算/差异清单、四组数值结果、匹配目标缓存、绘图、实际准入与分析/回归源码。运行源已有bd663绑定的SHA直接复用；其余选定小交付只计算一次。

没有再次扫描或重hash原始大账本、PCAP、bag、checkpoint或系统库。原件仍按各run路径、字节数量、完整读取manifest、消息身份/CDR SHA和已执行的来源门追溯；该清单不声称为全部raw数据的全文件哈希备份。Git bundle也不含忽略的raw数据。

审查内容固定于DELIVERY_REF.json的audit_content_commit；SHA256SUMS及本包装元数据随后单独提交，不制造自指未来HEAD。原始失败、未知字段和NO-GO不因哈希清单改变。

# full-load-wifi-audit-01 组件独立复核

仅读封存process、first-failure、C客户端、三R源小原件，以及runtime从其已载Gateway提取的 `health/wifi-full-01/component-subset.json`。没有重复Gateway/TF归因、扫描native ledger、执行模型或重算hash。机器可读原事实见 `FULL_LOAD_WIFI_AUDIT_01_COMPONENTS.json`。

**完整负载B仍FAIL，正常32wall、第四目标和预定RADIO_OFF均未完成。** 原总10.273189wall、outer1、coordinator/Gateway各1、其余角色0，无强杀。最早原guard事件是tb3 `health_heartbeat_stale`，mono517272.979286441；tb1/tb2随后为bound_mask_receipt_stale。host的FIRST_FAILURE是稍后观测，不冒充首原始触发时刻。

- 三机实际arm成功；C三Goal都得到真实接受，每台R恰接受一次，完整Goal_CDR与C对应原字节相同，UUID匹配。真实反馈到C为386/389/386次。没有policy或Nav2运动。
- 故障后，三R都有原Cancel返回0及匹配goals_canceling、原status5、PAUSE success，末owned为空；受控服务端执行表也为空。这些是本地受控取消事实，不是物理停车证书。
- R本机额外GetResult只在tb1/tb3记录到5；tb2仍有一个本机清理Future未完，不能写“三机本机所有Future闭合”。
- C客户端没有收到任何终态，三个GetResult保持未决；Gateway清理也保留三个C pending、各R一个响应等待ACK、executor_shutdown=[false,true]。END或资源销毁成立不覆盖这些缺项，也不造未知任务的结果。
- 89共享图实际C捕获/R发布各4份；95实际各6条，C/R原记录CDR身份Counter相同。三个R诊断订阅各消费4图/6journal，journal与C全部六个选中事件逐字典相等（3请求+3接受响应），不是只查文件存在。
- 89/95仍为0→1后共同R域诊断消费，不称三独立STA各自交付一份。其有限接线事实不替代首时效故障或完整负载通过。

Action原数据和本机取消链部分成立，但真实反馈/地图负载下时效资格和退出任务状态没有闭合。源→take、health/mask及Hub/Native责任分解由runtime另报，不由末结果猜唯一原因。本复核不提出重跑或改TTL，旧失败保留。

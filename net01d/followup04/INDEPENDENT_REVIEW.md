# NET-01D followup04 final independent review

**报告事实可作为限定阶段交付；系统结论仍为NO-GO。** 第二轮未发现新增P0或阻止封存的P1汇总矛盾。下列P2措辞建议已交Root最小修订，不需要重算数据、重读原件或新增实验。接受报告不等于接受A0、完整四组平台、旧wall300合同、NET-02或实机部署。

本轮审查对象是待封存的 `NET01D_FINAL_REPORT.md`、`FAULT_INVENTORY.md`、native成本SUMMARY、DELIVERY_IDENTITY、PRODUCTION_DIFF与RUN_BUDGET_LEDGER，结合此前已审各case/组件/费用小输出。最终运行源码为 **bd663824d77983cb2b2721e90241ef97bf06461f**；各历史case保留自己的运行版本，不能统一追记bd663。报告/最终交付提交尚待Root固定，本文件不伪填未来HEAD。未重复原Gateway/A0安全大文件、native ledger、PCAP、bag或模型读取，也未运行测试/模型或新增哈希扫描。

## 汇总一致性

- A0完成180sim/NN35、14accepted/13success与一个最终status5，R质量T95=37.47，但实际controller1，因此 **PROCESS FAIL / NOT ACCEPTED**。原host0/networktrue、真实物理停稳/PAUSE/UUID闭合和有效任务指标被分开保留。197a只修报告门，bd663只加透明观测；两者都未修复历史conversion错误。
- A1-03、B02、C各有有限180sim接受。对应R质量T95为41.48/65.84/37.15，末覆盖99.826456/99.916442/99.890732%；Goal成功3/3/4、5/2/4、4/4/3及各自RTF/路径/来源一致。预算终止不改称自然完成，普通C KeyboardInterrupt/controller0不改称A0根因已复现或修复。
- B1实际GatewayROS−9与nativeleaf0分清。B02真实安全关闭证明、固定总60s/共享绝对界和实际poll exit0获得独立支持；saved/main_return不代替干净退出。01 recorder失败/02初始化watchdog失败/不可用canonical、A0失败与两DDS工具失败或INCONCLUSIVE均被保留。
- Gateway统计明确wall/threadCPU/sim及不同cohort；Peer入口→health返回不含末尾event JSON，非完整callback CPU。CDR匹配不扩为全流PASS，A0health CDR缺测保留。B02/C native条件cohort10799/10801全匹配及服务p95=17.317561/53.256243simms有小见证支持，非全输入loss、airtime或逐包CPU。
- DELIVERY_IDENTITY列出的12个外部生产路径与PRODUCTION_DIFF的12个文件头一致。冻结release a014ef11/76fd行为源/6dcheckpoint身份保持声明边界；没有通过重hash模型或读大证据来扩张本次审查。预算账本七case逐项相加为 **7次GZ、210次policy forward、1056.2自主sim秒**，含失败01的156.2及02的0；训练/optimizer更新0。缺历史字段保留null，不反填退出0。

## Gate判据的有限接受

生产者11门建议在本报告限定语下可接受：冻结完整性、已证Gateway修补、**新profile任务/组件窗口**的health/clock/safety、Action已测接口/正常终态、继承范围NO-DDS-bypass以及WiFi证据存在/匹配范围可记有限PASS。它们不是任意负载、旧wall300、每包精确receipt_sim上界或实机安全证明。

**ROS MESSAGE INTEGRITY / 完整消费=FAIL；GAZEBO CLOSED LOOP=PARTIAL；CAUSAL ATTRIBUTION=PARTIAL；OVERALL=NO-GO** 必须一起保留。C4真实cut证据是继承的未变wire边界，不能写成B02/C新断链实验。未扫描的PCAP存在不能证明目标级RF airtime归因；四组单轨迹和不同负载/位置/可用输入不构成纯RF或CPU因果分解。原137.93ms仍UNRESOLVED，新合同不追改旧失败。

## 最小剩余阻断与文案

**当前系统P1阻断**是A0真实 `_take_subscription/take_message` RuntimeError及controller1。确切消息topic/type、异常创建时刻、SIGINT/转换/生命周期唯一原因仍未定位；报告门正确拒绝未来controller非零不等于此缺陷消失。独立停止/资源闭合只能证明安全收尾，不能抵消进程失败。没有新增P0现场事实。

整体因果解释仍PARTIAL：原137.93窗口、稀有转换机制和逐包CPU/wall/airtime份额未知；exactreceipt_sim分布未存。它们是必须保留的研究限制，不是本交付自动授权补跑/补造数据的清单。没有必要为封存追加验证、扩大流水线或改Policy/系统库/阈值。

三处P2文字可最小澄清：

1. A0的“预算后status5”宜改为“最终status5”；已选记录证明最终2→3→5及shutdown halt，但Cancel caller/response/GetResult5与该状态的精确时间均未捕获，不借叙述补时序。
2. A0 Unix1794394908.4831517是原supervisor **SIGINT请求事件的发送前采样**，随后原helper调用killpg；不能称精确发送完成或信号到达时刻。非零退出的观察在其后已证；原异常形成时刻仍未知。
3. 故障清单“native服务时间即使将来可测”已过时，应为“已测但仍含TCP/队列/WiFi/重组”。统计已完成无需重读。

Root修订上述措辞、固定最终交付SHA及必要小交付清单后，可封存当前事实报告。任何下一实验、参数/合同或A0修复工作仍需单独授权；本审查不放行NET-02、实机、push或历史改写。

最终小修复核：上述三项P2澄清已落实；新增严重程度/CLASS/证据强度表与既有事实及最小遗留一致，Gate状态规范为PASS/FAIL/PARTIAL后原范围限制仍保留，未升级资格，本独审NO-GO结论不变。

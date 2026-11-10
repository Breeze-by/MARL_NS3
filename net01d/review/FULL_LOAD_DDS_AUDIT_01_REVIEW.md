# full-load-dds-audit-01 分项独审

仅读封存process、client、三source、normal/negative小marker；未重复加载31.8MB Gateway/TF原件，TF时基和首窗口由runtime独占分析。机器可读分项在 `FULL_LOAD_DDS_AUDIT_01_COMPONENTS.json`。无新节点、网络模型、测试或hash计算。

## 可直接确认的业务事实

- 原总墙时41.089249、error=null、无强杀；coordinator保留预定故障退出1，其余0。退出码不代替时效或停止条件。
- C正常阶段实际持续32.000098wall，三机真实结果分别4/4/5，正常GetResult未决为空。三机反馈实际到达2515/2517/2452次；这些是受控服务反馈，不是Nav2运动。
- 三源实际arm服务均success。四份Goal（正常三份及后续tb3一份）的C记录完整Goal_CDR与R受控服务端实际接受CDR全部逐字节相等；接受次数为1/1/2，没有将重复传输算重复Goal。
- 第四原UUID `0000000078c3ffc00301000000000000` 在C实际接受；当时GetResult尚未完成。原NEGATIVE_TRANSPORT_READY记录R已接受、C/R pending各1及C service inflight1，确认重送未决0。随后才停止观察供给，未先退出服务制造未知。
- 源保持服务运行，tb3服务端实际取消列表含正常和第四两个精确UUID；末executing为空。第四目标的C客户端最终实际收到终态5、result_pending=false，因此本次A1不应描述成中央仍unknown。
- 三R源均记录本机PAUSE请求。NEGATIVE_DONE由原guard记录判定同UUID本机GetResult5、三个PAUSE成功和本机Future清理完成；其嵌入的central_state是较早timer快照，仍有pending1/local_cleanup2，不能将该旧快照当最终状态，也不能倒过来抹去后来C实际结果5。
- 每个R诊断订阅实际消费共享图19份、journal11条；11条journal与C按原export种类选出的全部11个实际fixture事件逐字典一致，非仅计数相等。89/95仍是0→1后共同R域的诊断消费，不是三独立STA无线交付证明。

## 边界与结论

上述分项支持本次带观测A1完成受控Action正常阶段和停供后本机取消路径，不能称为真实Nav2、SLAM、物理停车或Wi-Fi验证。完整正常段源龄/receipt判定和SDK metadata含义须结合runtime专项证据，不由errornull、normal_done或marker存在替代。

本次只加观测，没有行为修复。上一 `full-load-local-01` 的真实源龄FAIL原样保留；本次未复现不能证明其根因已解决。原始三guard actions及最终Gateway cleanup若由runtime已载数据提供，可补交叉核，不为此重复大扫描或追加运行。

随后已核runtime从其单次已载GW提取的 `health/dds-audit-analysis-01/component-subset.json` 原字段：三个actual_local_pause_response均success；第四精确UUID的原Cancel返回0、goals_canceling匹配、原本机GetResult5，三R owned为空。最终END/两个executor正常、C/R/本机清理与确认未决全0。89/95在C捕获及R发布的原CDR身份Counter相同，数量19/11。上述补证已加入机器可读分项，未重载GW；旧NEGATIVE_DONE内timer快照不被追改成最终状态。

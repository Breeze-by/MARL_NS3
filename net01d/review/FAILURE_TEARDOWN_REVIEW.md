# 正常阶段首故障后的提前收尾：独立窄审

范围：当前harness源码与已封存完整B的tb2清理缺项；只读，没有新测试、节点、网络模型或生产编辑。

## 已证实问题（P2，harness生命周期）

`run_replay.py:124–127` 发现FIRST_FAILURE立即抛出，`:193–200` 在finally完成资源HOLD后直接写共享STOP。这个STOP同时结束三R源/ControlledServer和Gateway轮询。`full_load_source.py:172,230` 随即关闭真实ActionServer；`Gateway._close:523–557` 的前提是上层已尝试停止清理，它只快照未决、flush IPC并remove/destroy执行器，不继续spin本机R Future。

原planned-negative路径`:189–192`却在STOP之前要求NEGATIVE_DONE，而该marker要求实际本机终态、PAUSE响应和Future清理。因此正常阶段首故障分支缺少同样的本机清理机会，存在真实服务/执行器过早撤除窗口。这是可从实际源码确认的收尾缺陷，不是对全部Gateway关闭逻辑的重新设计理由。

完整B实际tb2已Cancel返回0、status5、PAUSE成功，但额外本机GetResult Future仍pending1；这与上述窗口相容。缺少该服务响应及最后处理阶段的完整因果记录，**不能唯一追认tb2就是由提前销毁造成**，更不能把这项收尾缺陷当作更早heartbeat/mask首故障原因。

## 最小修补边界

仅harness在首故障后保留原firsterror，停止观察供给但保持R服务和Gateway原pump；在原60wall硬界内最多给2wall等待真实R owned为空、原PAUSE响应成功及所有本机清理Future完成，然后才STOP。超时仍保存未决和失败，不延长总预算，不伪清Future。

不等待或清除C的无线未知，不为了清理继续推进Native排空业务，不放宽任何guard/停止时限。资源HOLD与数据服务继续处理是不同职责；对本无运动受控服务，本机Cancel/Result/PAUSE可沿原DDS和steady处理完成，不制造物理停稳证书。

## 最小定向回归

复用现有真实Action受控服务与harness，令已真实接受、GetResult仍在等的目标在**正常阶段首故障**分支触发本机清理；不能只重做已成功的planned-negative路径。核原firstfault仍保留、真实精确UUID终态/PAUSE/Future完成先于STOP、源服务退出和Gateway关闭随后发生；若无线中央仍unknown则如实保留。一个有界的失败路径足以验证本修补，不需新故障矩阵或物理机器人/Gazebo。

**意见：允许按此边界准备第一轮最小修补及一个定向回归；不将本意见当已修复、既有失败追认或新运行授权。**

## 固定580610d实际差异补审

已读两个harness文件实际差异：原firsterror保留，SUPPLY_STOP只停观察；HOLD和local drain共用不超过2wall且受原hard界限，原R owned为空、三个真实PAUSE成功和每个本机Future.done后才STOP，超时保存独立缺项，不等或清除C未知。Gateway生产协议、原时限、信用和Native排空规则未改。

20wall定向入口先验证三真实active/已确认的GetResult等待，再停止观察，未创建NEGATIVE_PHASE，确实经过旧正常阶段首故障分支；断言精确三UUID的Cancel0及goals_canceling、GetResult5、清理marker早于STOP。未发现实际阻断。既有源码检查不重跑，实际是否闭合待封存小原件，不从准备代码直接追认修复或P5。

## cleanup-drain-01 的实际反证与第二轮边界

原ACTIVE marker为519024894811490ns，实际停供trigger为519024898117504ns（非None），FIRST_FAILURE为519025152116663ns；故主动触发已发生，不能写成触发前自然TF故障。原整体regression=false保留。

LOCAL_CLEANUP_DRAINED在519025152558029ns生成，早于STOP519025160967404ns。它已有三原UUID的Cancel0、匹配列表、PAUSE成功、status5和Future.done，但三份actions均尚无actual_local_GetResult。最终Gateway小subset才各记录GetResult5，并保留全部本机RPC0/executor正常。这支持后来本机清理完成，不能回填先前marker或追认严格回归通过。

实装SDK `rclpy/task.py:127–131`先把Future设FINISHED，`:157–163`再排done_callback至executor。`delivery_guard.py:116–122`的Cancel回调还会新增GetResult Future；GetResult自己的done_callback又在随后记录结果。因此Future.done不等于回调已排空。上轮静态评审也未识别这个具体窗口，本次原严格oracle正确暴露了它。

第二轮最小方案应仅令marker对g.stopped中每个精确UUID要求已有真实Cancel响应及GetResult终态4/5/6，原owned空、全部Future.done、PAUSE成功条件均保留；定向regression仍严格要求5及Cancel0/匹配UUID，不改判据。cleanup02继续旧stress5ms可隔离这项修补；另增显式actual-phase0仅作后续真实条件校准，不在cleanup02同时变更。无第三轮修补、无新运行授权由本评审产生。

已读随后三文件实际差异：marker确实新增上述每UUID真实响应条件而未删除旧条件；host把cleanup02强制为A1/full/metadata/stress5ms，仍Disk/20wall，原回归严格5/Cancel0/精确列表条件未变。没有发现阻止该定向回归的实际缺陷；不重跑旧检查，仍需封存原件确认。

## cleanup-drain-02 封存独审

只核本case小marker、regression、client及三Source，没有加载Gateway/DDS大记录。原active519603958252491 < trigger519603961664070 < FIRST_FAILURE519604224647993 < LOCAL519604282095023 < STOP519604286712590，次序成立。原首故障仍为三个health_original_sources_stale，保留在process error中；未改成干净正常完成。

LOCAL的三精确原UUID都已有实际Cancel返回0/精确列表、GetResult5、PAUSE success、owned空，本机Future未决0。R受控服务实际cancelled UUID匹配，三个Goal原CDR与C相等，C最终也实际收到三个5。等待58.486393ms低于2wall；无强杀，coordinator原1、其他0。原strict regression=true与证据一致。

**限定接受收尾修补的定向回归**，机器可读事实为 `CLEANUP_DRAIN_02_REVIEW.json`。原cleanup01 FAIL不改，本次仍stress5ms/Disk；outer0只是预期首故障与真实清理满足回归，不是32wall正常满载、P5、物理停车或Gazebo通过。actual-phase后续运行独立准入，不从这次结果外推。

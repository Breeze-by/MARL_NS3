# NET-01 followup02：有界productive refill + 回调边界真实传输进度

本计划在任何新Gazebo成绩前固定。新用户授权最多3次实际启动，历史87→最多90：A05匹配direct参考（actual1/累计88）先单独根审；仅健康完整封存后才分别审B近理想及C基础非理想，各1次，失败含启动都计数、无自动retry/换名/延长。当前0/3，无Gazebo许可，旧A01/A02/A03/A04和337/d4eb报告/身份/失败不改。

## 问题与对应功能修复

- 先纠正比较：封存连续03/04约.3ms是readyfalse的全100分支，readytrue的原mask数学为17–19ms；A04约20ms，同一次0Node原函数测得16.67ms CPU。当前无Python/NumPy线程环境不一致证据，不动Peer数学或线程设置。
- A04独立失败前1sim只解码339条原tf/clock，R原TF明显领先Gateway capture；捕获后到C publish约4ms，不能全部归SLAM或网络无线。
- 已确认代码缺口：本机公开executor Timeout0也是非空ready集合结束；旧drain在此break，即使各reader仍有旧样本，也每个外层仅take一次。修为在原总callback cap内，生产性集合后的Timeout取下一集合；只有完整空集合、原cap或Shutdown返。跨cap保存一个productive flag与原cached cursor，原handler/exception/result语义不变。0Node确切AST8项检查通过，无无限refill/吞异常/改排序。
- 首actual验证06保留FAIL：同8wall/20wall真实连续DDS与100Hz反馈，原source频率不降；R连续消费.6/.7两拍clock时，hub直到整批结束才有机会送首STEP。native只收KNOWN0/.1/.2、horizon仍0，原.12门禁实际触发。该失败不能冒充业务容量通过。
- 合成唯一修补：现有非阻塞hub/native/direct进度主体原样提取，在每个真实handler返回后及外层尾部服务。单线程、同C/R顺序/同callback cap、公开cached iterator；不嵌套spin/drain、不等ACK/过期catchup、不回插过去/重锚/改源戳/过滤/优先。原lag与rollback/source/steadyguard仍立即有效，failure后本机Cancel/GetResult/PAUSE/zero回调继续但正常业务停止。C façade公开create/destroy及epoch/pendingunknown语义保留。

## 唯一组合验证07及限制

同旧真实Gateway A/BoundPeer/native-hub，8.027wall实际源，总11.748wall/四owner0/无Gatewayfault，0GZ/Nav2/arm/goal/NN/C真实Policy。TF401/400/400和odom241/240/240在Rcapture/Cpublish/Peer相应完整到达；TFcapture前重复header下界median7.02/7.57/8.53ms、上界63.07/62.21/66.04ms，非唯一DDS ACK。

反馈真实源801/800/800，R捕获797/795/795，目的端收到全部797/795/795捕获CDR且rpc身份一致；**14条源→capture差额保留：第一capture前只各有2/2/1次source完成，初始头部最多缺1/1/0，至少3/4/5条发生在过程或尾部，重复header不能唯一细分；不称全流零损**，不改原depth10/QoS以凑数。受控源未有真实Nav2/Policy消费者，不能宣称真实完整闭环通过。

实际native首STEP返回.1，81次horizon返回到8.1；Rclock/native事件包络max lag.1sim、无.12fault，不冒称逐Gateway ACK延迟。三guard408–409次、最大58.8–66.4ms；R整批仍可129.7ms/outer157.5ms，而回调间pump让native持续推进。cap不是单回调墙钟硬界，故不签硬实时保证。

## 固定真实回归合同

候选runtime1bb7d55，仅Gateway一文件18+/5−。保留a014/76fd/6d、701/ROI/Frontier/候选/联合mask/生命周期/DWB/SLAMfine.75/原mask数学与3mask→health顺序/物理/三角/分母/V3/.4/.55/.3/原暂停停机，0训练/NET02/push。A05同Corr6201/15558格、180sim/130decisions/startup180/autonomy420/outer900/cleanup90；仍完整CDR direct适配参考，不是WiFi数据。

先真实clock/pause/原Nav2/物理停稳/3arm，才实际NN/accept/反馈/运动；任关键时钟/Action/安全/定位/保存/停止/持续坏图暂停。成功与否均离线用原工具一次量化失败/任务窗口覆盖阈值，未达不填0、不延长窗口或用旧600替代。健康A才可能准B，所有组同候选与独立guard，B/C无directfallback。

实际证据与失败见本目录JSON，源身份DISPATCH_CLOCK_BINDING.json，A05具体draft在requests/。本文件不是运行授权。

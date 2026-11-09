# 前瞻补充：公平ready批次修复与剩余两次Gazebo用途

本补充在新Gazebo成绩产生前登记；原PLAN、A01/A02失败、报告/身份与旧DRAFT/READY全部保留。原续轮上限3次不增加：A02已用1次/累计85，余2次拟固定为修后A03参考（累计86）→B近理想真实WiFi（累计87）。**C本续轮NOT RUN**；不是按探索成绩挑组，目前0NN/0goal。A03具体READY前不执行，有关键失败则B保持未准入，无自动retry/换名或追加。

## 证据与唯一调度修复

A02真实原暂停/固定anchor/三Nav2 startup/原停稳preflight通过，但STA1在149.3因bound_mask_receipt_stale拒arm；原Peer校正源龄约.9–1.0sim而odom新鲜。封存145–150sim bag表明R原TF已新1–1.2sim，不能归原SLAM只生成旧header，也不能放宽.55或等下一fresh帧重arm。

连续DDS03复用实际Gateway A/BoundPeer/native clock模型，8wall实际源，三机各100Hz混合TF/30Hz odom、10Hz合成clock、原mask负载和exactzero旧Observer输入；全owner0，总11.197wall。每机校正TF实际发400，R仅捕获295/309/301；source→capture延迟下界中位954/938/936ms，C publish实际调用约.12ms，主要积压已在R reader捕获前。01 wrapper SIGINT导致RAM丢失、02循环变量覆盖case名均为工具失败，原件保留，不称业务性能失败。

修复仅Gateway公开executor wait_for_ready_callbacks(timeout0)的缓存当前ready批次：每C/R节点按现有实体数cap执行原SingleThreaded handler/exception/result语义，到首Timeout或cap返外层；保留缓存cursor跨cap、C→R→hub轮换、所有timer/guard、原QoS/消息顺序。无TF优先、过滤、压缩、丢旧帧、加wait、改源戳或网络调参。TF只读元数据保留原一次调用和异常，RAM收尾保存。

相同源/窗口连续DDS04全部owner0，总11.641wall，三机仍各发400校正TF/240odom/160wheel/160exactzero；R捕获、C发布、Peer接收均各400。捕获前延迟下界中位降至4.04/4.54/6.75ms；重复header的上界中位43–45ms，不能假作唯一packet ACK。C publish调用中位.08–.13ms；Peer80/83帧ready，仅初始未就绪。R批最大53.7ms、outer gap58.4ms，三guard实际417–418次、最大间隔65–68ms，无Gateway fault。是该受控负载的机制证据，非硬实时/真实GZ/WiFi探索或物理断链停机PASS。

代码固定：`29c7cbba2f2e3775fd3c368eb03d315c258e802f`（Gateway调度及两处只读TF元数据）。原外部recorder路径修复5d5fcd5仍在；发布a014/核心76fd/6d/DWB/Frontier/masks/lifecycle/Nav2/SLAM/physics/地图/共同三角/ROI/时效.4/.55/.3/原停止不变。无进一步接口夹具/训练/NET02/push。

## 两个实际回合的合同

仍Corr6201，原seed/15558格，180sim/130决策/startup180/autonomy420/outer900/cleanup90wall。A03为匹配两域direct适配参考，B为仅真实ns3 Recv交付的原V3近理想配置；两组同新增调度/元数据/guard，B不能fallback direct。A03先实际clock/pause/原Nav2/物理停稳与真实arm，原完整停止/UUID/保存/质量审过后才由root具体签B；本补充不是运行授权。普通低覆盖/Nav失败照实保留，关键时钟/Action/安全/定位/持续坏图/保存/停止问题暂停。

具体A03草稿见requests/net01-a-corridor-6201-03.draft.json；固定新源码身份见READY_BATCH_BINDING.json。原受控证据见CONTINUOUS_DDS_03_ANALYSIS.json和CONTINUOUS_DDS_04_ANALYSIS.json，source实际间隔与stop-file额外开销均保留。stop-file仅无机器人夹具资源控制，不进入生产运行或业务路径。

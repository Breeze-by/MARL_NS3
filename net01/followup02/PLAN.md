# NET-01 followup02：先修正比较口径，定位真实功能瓶颈

从33765d3交付与d4eb指标补充继续，外部runtime a41a；旧报告、3次失败、身份、独审及冻结发布不改。当前0次新GZ，拟本轮最多3次新启动/每180sim与原wall，每次需root具体准入，无自动重试。固定a014/76fd/6d/701/Frontier/掩码数学和源戳/生命周期/DWB/SLAM/物理/源龄.4/.55/心跳.3/停止/V3，不训练/NET02/push。

第一静态发现：必须按实际ready分支比较mask build。旧连续03/04约.3ms属于未就绪全100(np.full)分支；就绪peer_mask真实中位17.21/18.80ms，连续05 18.80ms，A03/A04 19.76/20.13ms。此前用未就绪帧对比真实就绪帧会误判环境差异，分层原数见MASK_BUILD_STRATIFIED.json。当前未见Python入口或OPENBLAS/OMP/MKL=1继承差异，不凭目录猜运行环境。

下一最小验证仅0Node：现有ros-python.sh实际容器导入同冻结Peer与NumPy，读取A04同一sealed ready snapshot，5次原三机mask函数，分别记录mask_poses、peer_mask与原grid数据捕获的wall/threadCPU、实际module路径/版本/线程环境。无ROS初始化/发布/控制/新DDS负载，不改函数或阈值。这仅确认真实数学计算成本与调度分量，不是性能修补PASS。

随后基于现存Gateway/clock/TF路径决定完整接收/转发/clock推进的最小功能修复与可证伪隔离验证，先交root审，不再仅堆重复局部夹具，不通过延后检查、刷stamp或等fresh重arm掩盖过期。正式GZ目前未准入。

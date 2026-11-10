# NET-01D 源差异与版本范围

相对起点 `cee0c7024ccf06d88d7ff458a47c39cdf605a7f3`，最后实际运行源 `81710e6739311a59ed4bef945a0fbd871d274a64`。重要运行源SHA只计算一次，见 DELIVERY_IDENTITY.json；旧ELF/权重身份沿用主审已核原值，不重新全树扫描。Git提交/备份由root统一协调，未推远程。

| 文件范围 | 必要差异 | 不改变的语义 |
|---|---|---|
| bound_peer/topic_wire/gateway/hub_client/packet_hub | opt-in RAM健康分段与已有profile/controltrace关联；R实际接收前后ROSclock/ACK；TF仅诊断executor选项 | 原消息/CDR/QoS/guard tick和更新顺序、原调度、Native模型不变；默认关闭 |
| net_scene_launch/time_control_runtime/BoundPeer main | 实际GZ以后可用的profile flag与/mnt模块路径接线 | 本轮未加载GZ，不以此签实际运行 |
| net01d/health/trace.py、take_trace.py | 原生mono/threadCPU/realtime/DDS实际metadata；TF原take恰一次，保原tuple0/None/异常 | 不安装/修改SDK；无新线程/Node/timer、不伪造缺失GID/seq或首入队时间 |
| run_replay/replay_roles | 独立角色薄host、显式旧artifact、原预算、32wall正常/4真实受控Goal、固定负例；两轮本机清理生命周期修正 | 首fault/error不清，中央UNKNOWN不假闭合；≤2wall排空计原hard内，原安全阈值不变 |
| health/full_load_* | 独立R源、C真实Merge/Action/journal、一次只读实际CDR模板、ticks/skips/headers和匹配数观测 | mixed sim/wall合同、字节/Goal身份、原guard真实arm；不代表真实SLAM/物理或最大尺寸 |
| followup04/mock_physics.py | 新显式actual-corr6201 initial0，仅回放相位校准 | 默认stress5ms原样；Step10×1ms/clock100Hz/credit20ms/pacer20ms不变，无补terminalclock |

未改action_wire可靠协议、Policy/RL/701权重、Frontier、masks/KEEP/WAIT、Nav2/SLAM/物理或网参；未构建/覆写Native82bc、旧rootfs/NS3目录。九次均为无运动ROS/Mock/ns3，实际Gazebo四臂均NOT RUN。

原历史与每次FAIL保留：旧B137ms、首A1约1s未知、stress完整B、cleanup01 oracle不满足、actual B正常源龄FAIL。新相位与本机清理有限正证不能回填历史PASS。原件/所有退出与copy/源供给见RUN_LEDGER及独审小结果。

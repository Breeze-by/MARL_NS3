# NET-01 followup01：修复录包配置后的固定三组续测

用户于2026-11-09明确继续修复测试；从本地交付3c3143b继续，旧A启动失败、REPORT/ledger/identity/READY及冻结发布全部保留。独立分支 `net-01/followup-01`。本轮不把旧A失败改成成功或移作B。

已在实际ros-python.sh/rootfs运行一次无机器人检查：安装RecordVerb对原实际recorder命令parse_args并打开外部原QoS YAML，实际直接启动文件/程序可读，6项通过/native0；没有调用recorder.main、rclpy.init、Node、Gazebo或NN。原tf_static depth100/地图TL保留，见startup-reference-check-01.json；不再重复旧网络/Action/guard夹具。

唯一既有修复是外部recorder QoS路径适配，源5d5fcd5；配置原文来自固定76fd。核心模型/Frontier/mask/联合规则/Nav2/SLAM/物理/源龄/heartbeat/停止和V3网络配置不改，不训练/调参/NET02/push。

| 新顺序 | 组 | case | 实际累计预期 | 准入 |
|---|---|---|---|---|
| 1 | A IDEAL-DIRECT-ADAPTER | net01-a-corridor-6201-02 | 85 | 本轮具体DRAFT经root签署后才执行 |
| 2 | B 近理想真实WiFi | 新独立case，后续具体签署 | 86 | 新A完整/clock/Action/安全/停止/质量/保存原件审过 |
| 3 | C 基础非理想真实WiFi | 新独立case，后续具体签署 | 87 | 新B健康且具体签署 |

本轮最多3次新实际Gazebo启动，旧失败累计84保留，每组最多一次、无自动retry/替换。Corr6201原world/共同三角/yaw0/15558格、固定6d。每组180sim/130决策/startup180/autonomy420/outer900/cleanup90wall。任何关键时钟/Action/安全/记录/停止/定位或持续坏图故障暂停余例供root；普通性能低或Nav失败不删除健康固定比较。当前0/3，B/C未准入。

同C91/R92适配、同guard，A仅完整CDR direct，B/C仅真实ns3接收，无fallback。首真实clock固定anchor、不重锚；原.1量化/.12lag、.35wall无目标pause观察（基线在实际pause成功后）、原wall保护与停稳门槛保持。短启动direct数据或受控接口PASS不冒称完整网络探索/物理断链安全。

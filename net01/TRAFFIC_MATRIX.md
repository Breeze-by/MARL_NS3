# P0 实际业务流与拟隔离边界

实际源码锚点均相对冻结发布仓库的 `workspace/`，不根据目录名推断已运行。现状为同DDS域69/localhost；网络结构尚未实施。`P0_AUDIT.json`记录无Node加载环境检查与真实六例/36配置对应。

| 分类/流 | 实际producer→consumer/源码锚点 | NET-01约束 |
|---|---|---|
| 本机 scan / odom / TF / map / costmap / cmd_vel / joint | Gazebo driver/ray→本机SLAM/RSP/Nav2；scene_launch.py235–355，driver STATE_SYNC=1；Nav2只用本机namespace | R域本地保留，原感知控制闭环不经中央；同一数据若供C则该副本必须过网 |
| 三机map | 每机SLAM→MergeMapNode；merge_map.py地图cache与max融合，scene_launch.py显式.05入口 | R_i→STA_i→AP→C，完整原CDR；C真实原merge，不能读R最新map共享文件 |
| 中央own map/odom/tf/tf_static | ros_policy.py94–101、control.py71–166→HQ per-robot Buffer/Allocator | R_i→C全payload，保留frame/stamp/static history及source-time transform；未到不补 |
| 中央local_costmap/costmap | GZHeadquarters111–114→seed_connection；源/收双1s及source-time TF | R_i→C全payload，不可漏此输入或另用理想local map代替 |
| 中央cmd_vel观测 | ros_policy.py98/control.py robot_status_control当前pass | 不作速度控制旁路；原订阅若保留，其R_i→C副本同样过网，不能偷接R域 |
| peer三机mask | PeerKeepout收到odom/TF后每.1sim→各robot KeepoutFilter；400×400 int8×3×10Hz | C→AP→STA_i→R_i完整bytes，约4.8MB/s裸负载，不用token/本地重新生成原大图；每STA mask实际收件单独记 |
| peer health | C PeerKeepout→C HQ及R Observer；publish_masks先3mask后health | C内消费仍基于已过网R观测；下行独立过网。公共Observer仅明确单路重发不以三副本续龄，三本地watchdog各查自己health/mask |
| NavigateToPose | 原LoggedActionClient→真实Nav2；ros_headquarters.py56–80/control.py196–237 | send_goal/get_result/cancel_goal请求响应及feedback/status全部双向原字节/UUID，不二次生成Goal；远端发现/accept/terminal不伪造 |
| 运行controller_end/journal | run_case.py原incremental cursor→C allocation-events内halt/budget；stop读取requests/UUID | 运行期终止事件经WiFi入R接收副本；原C journal只可停止后离线证据汇集，不能变成共享FS业务旁路 |
| local网络安全 | 原中央Observer cancel/zero/pause有六例stop实证，网络失联本地尚无实证 | 新同源A/B/C安全适配仅停止/撤销权限；服务CancelGoal/生命周期GetState/ManageLifecycle归独立安全白名单，不给policy业务补状态 |
| 参数加载证据 | 现run_case pre-controller各读SLAM fine=.75的GetParameters | 作为部署前无运动管理证据独立读取，不承载新策略状态；不能把其响应当业务送达或代替health |
| 时间/仿真控制 | Gazebo /clock；pause_physics/unpause_physics | 唯一受控/clock白名单独立交付两域及ns3；原source stamp绝不重盖，时间推进/回退明确记epoch |
| truth评价/安全 | /gazebo/model_states→Observer metrics/hazard，不入policy | 独立评价通道保留，禁止重发布为业务odom/TF；只可白名单更新ns3 MobilityModel实际位置，日志标GT_NETWORK_CONTROL |

无线MAC/PHY实际trace、应用分片/重组和ROS消费各有独立identity。Health不是mask ACK，publisher日志不是DDS ACK，完整重组不是Action accepted，最终保存marker也不是网络送达证明。消失的包/未知UUID保持未知，不造默认PASS。

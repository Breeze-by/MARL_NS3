# NET-01 实际组合入口（待审，Gazebo 0/3）

固定冻结发布 a014ef11 / 运行76fd / checkpoint6d；原 DWB、SLAM fine .75、701编码/ROI/候选/最大参与/生命周期/物理/原全部时效与停止阈值不改。这里新增的是外部传输与安全适配，没有更换原源码。A/B/C 各一次 Corr6201，同原三角/yaw0、15558格/38.895m²、180sim/130 decisions。独立 wall：startup180 / autonomy420 / outer900 / cleanup90。启动失败也占该组，无重试；普通任务失败照实保留，安全/时钟/Action/保存等故障暂停余组。

## 进程与域

```
host_run.py (host, no ROS) ─ packet_hub.py ─ native ns3 (host existing3.40 libs)
       └ ros-python.sh (read-only existing rootfs / baseline; no netns/TAP/routes)
           └ boot_network.py ─ run_network_case.py / original Observer [R92]
                              ├ gateway.py [C91 + R92 actual Contexts]
                              ├ original scene launch wrapper
                              │  ├ original merge + BoundPeer [C91]
                              │  └ original gzserver + 3 SLAM/Nav2/sensors [R92]
                              ├ original frozen headquarters [C91]
                              └ original rosbag [R92]
```

Gateway 是独立于 hub/ns3 的 ROS 进程。其 R steady timer 每 .02wall 执行原源龄/独立每机 health 与 mask receipt gate；无同步 IPC 等待。EOF/网络进程故障锁存 INVALID，关闭新目标权限，不切 direct，继续 R executor 处理本机 cancel/result/pause/zero。原独立 Observer 继续做真实三机物理停稳、三Nav2暂停及UUID闭合认证。Gateway 本身失联由 Observer 的 gateway receipt .3wall gate 阻断。只在三个本地源都新鲜时，原导航 resume 后逐机调用真实 arm 服务；故障后不能 re-arm。

ActionWire 真实 R 转发在 SendGoal 前调用 observe_send_goal；真实 accepted 响应先调用 observe_goal_response；迟到 accepted 按同UUID取消。重复 RPC 缓存先于钩子，不重复目标；停止后 Cancel/GetResult 仍按真实本机服务可用性放行。C 五端点 façade 只由实际收到的 R 五端点 readiness 与本地权限创建，不将代理收件当 accepted。

## 唯一业务路径与白名单

| 方向 | 实际完整内容 | 接收与用途 |
|---|---|---|
| 每机 R→C | 原 map、odom、tf、tf_static、local costmap、cmd_vel CDR | 原 merge/HQ/Peer 输入；本机scan、SLAM/Nav2内部不跨域 |
| C→每机 R | filter_info、health、带同批原源戳/seq的完整原160KB mask | 每STA独立 guardian；验证 binding 后发布原 mask |
| C↔每机 R | generated SendGoal/GetResult/Cancel请求响应、feedback/status/readiness | 原 UUID、坐标、frame、stamp、accept/terminal 值，不新建 Action 业务状态机 |
| C→STA1→R | 原 merge 输出（flow89） | 原 Observer/评价使用实际R收到图；C HQ仍用原C融合图 |
| C→STA1→R | 原 request/response/result/halt journal 行（flow95） | R运行期controller_end只看实际收件RAM，停止后原C文件仅独立证据 |

同一进程持有两域，源 callback 只能 capture/send；目标 publish 只能通过 backend receive。A 为 **IDEAL-DIRECT-ADAPTER**：完整CDR本地队列，记录非零开销；不是旧单DDS布局逐时序相同的A，也不称过WiFi。B/C 仅 native SocketRecv CopyData 完整重组后 IPC 可触发接收，没有源blob查表/理想DDS/文件补图/自动 direct fallback。RPC身份真实放入网内正文，独立native id避免双向/跨robot碰撞。

控制白名单只有实际 `/clock` 转发到C、Gazebo model_states 的xy→native MobilityModel（固定天线z=.15）、实验结束与独立安全停止。GT 不发布到 C policy topic，网络位置不回填机器人状态。R运行期不读C controller源日志；其唯一读者是 C 源导出器，四种记录也必须完整过相应 backend。原 stop/final 仅在控制权已结束后读C journal 作取证，不反向喂入主期。

原 Peer 三mask→health发布顺序和值保持。外部观察 hook 在实际同批发布后附原源戳/seq、robot/header/CDR身份；包体及额外绑定字节都走相同链路。R health 公共 topic 仅STA1一路；STA2/3独立topic和guard，任一路新health不续旧mask。每robot一个TL1 bound topic。两端DDS reliable/TL不等于UDP端到端可靠；缺片不发布，不刷新stamp，不自动补丢失静态源。HELLO/ACK实际双向完整过网一次后才建业务订阅，保留首次ARP/关联开销，无预填ARP或隐藏重试。

## 时间与暂停

首条真实 R `/clock` 在任何业务/goal前一次固定 `tGZ=tNS3+offset`，记GZ/ns3/monotonic；以后不重锚、缩放或消漂移。所有ROS header仍为原绝对GZ时间。仅最新已观察 GZ horizon 可经 KNOWN；SENDAT 的 admission 是当前已知映射GZ，不能按旧source stamp回插。native STEP为相对Stop(H−Now)/Run，步长≤.1；同H按UID尚未执行的事件可留下一Run。native不能领先实际clock，映射lag>.12sim或倒退锁存停止，原wall heartbeat不暂停。

A的同一次有预算Gazebo启动中，原 readiness 后/目标前实际调用 pause_physics，持续 .35wall（计startup180）并记录两域clock/ns3 horizon及固定anchor，恢复后在原startup截止前要求原源新鲜。暂停允许至多一个已经观察的 .1sim horizon在途，不将其误称持续推进；旧health/mask不改戳，guard尚未授权。随后原 Nav2 startup、fine参数实读、原零速度/物理稳定/三pause preflight，再resume/逐机arm/原HQ。真实clock与物理停稳是否成立只能由该首A原件判断，合成测试不是 TIME/GZ/NETWORKSAFETY PASS。

暂停基线以实际 pause RPC 成功后新发布的 gateway monotonic 状态确认，才开始固定 .35wall 观察；请求、RPC完成、基线与观察时刻分列记录。发现服务或RPC等待期间的合法物理推进不计入暂停失效；仍不延长原startup截止、不重锚或扩大 .1sim 容差。

ns3延迟为实际同模型Tx/Rx差；外部IPC/ROS调度/量化wall开销分别记录。source没有generation header时保留0与capture元数据，不能虚构sensor AoI或把wall时延当sim时延。

## 启动/停止与证据

具体三份未签draft：`requests/net01-{a,b,c}-corridor-6201-01.draft.json`；root签对应 `.ready.json` 后才执行其中 `requested_command`。当前授权字段全部false。host只启动自己新的native hub/socket/profile，再启动rootfs boot；hub建立Unix监听不等于WiFi链路ready。A native模型只做真实clock探针、不承载业务；B/C正常V3保持，不启用无运动夹具的fault入口。

冻结runner的原loop/ready/source gate/检查顺序/stop/UUID闭合保留。外部层只替换scene launch域放置、HQ进程域、运行期controller_end数据来源和前置clock/arm gate。C/R实际节点图必须记录，不能伪造R图补中央节点。cleanup先原HQ退出、原停稳/UUID/3pause认证、bag和launch退出，再终止gateway/内存落盘，最后END native。外部outer失败只依精确case marker和记录PGID清本轮owner，绝不广域pgrep/清其他环境。

原 `result.json` 不冒充网络完整性；另 `network-integrity.json` 要求原runner成功、hub/native成功、Observer/Peer/BoundPeer/Gateway保存标记有效。保留捕获字段/原时间/顺序；marker只表示保存，不表示DDS ACK。主要输出：原bag、runtime/closure、唯一metric/覆盖轨迹、observer_timing、peer原JSONL、bound发布、gateway全链路/clock/guard、hub ingress/delivery、native PCAP/MAC/PHY ledger。故障同样原样封存。

Gateway资源清理只在监督者原停机/owned清理尝试之后发生；executor.shutdown(timeout_sec=0)不会等待永久unknown的C服务回调。原未决RPC身份/本地cleanup future和逐executor是否完成如实保存，不补accept/reject/terminal。节点/context销毁完成后才写saved marker，另核实际gateway退出码；END未完全送出独立失败，不能因记录保存成功而被覆盖。实际native ELF和生成header首次身份见 `config/NATIVE_IDENTITY.json`；host在启动它之前核两者与具体draft一致，未重扫旧ns3树。

目前已证实：独立网络03、静态ROS04、真实WiFi+受控Action03、bound无Node02、受控本地guard01各自有限范围通过；首次工具/接口/ARP/CDR-padding oracle/长PHY-off故障原件均保留。真实Nav2/实际clock/物理网络安全/有界GZ还未运行，不能据这些夹具签OVERALL PASS。无新增全面回归/压力测试或旧历史重新hash。

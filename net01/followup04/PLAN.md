# NET01 followup04 — clock与Action启动生命周期

从690202b独审继续，新branch net-01/followup-04。03原报告/失败/tag/模型不改。最多3实际Gazebo（旧累计92→不超过95）：A09直接参考，只有健康封存后另审B真实WiFi，条件具备才另审C；无自动retry/用满。当前0新GZ，任何实际入口均需root具体READY。

冻结a014/76fd/6d/701/Frontier/掩码/生命周期/Nav2/SLAM/物理dt与碰撞、V3及.4/.55sim、.2/.3wall、.12lag/停止判据不松。保留5401有界Gateway GC、Release82bc/serialCPUoff，0训练/NET02/系统安装/host网络改动/push。

| 已证问题 | 本次最小边界 | 直接可证伪验证 |
|---|---|---|
| A08真实10条clock累计308.866ms，现两Python观察均无法唯一分清发布/排队 | 独立只读rclcpp单/clock观察，无use_sim_time/业务timer/republish；保存原clock_ns、writerGID、RMWsource/received戳、callback mono/realtime；同clock身份关联Gateway原记录 | 先隔离实际FastDDS已知clock样本核元数据非0/基准；0GZ。共同晚callback不能单凭回调戳判上游晚发 |
| 重依赖导入早于constructor journal open | 轻标准库bootstrap exclusive建本轮run_dir/journal，同Path子类只一次移交精确owned目录mkdir与同一handle的open(x,buffering1)，其他路径原行为；不复制策略main | 0Node受控import中断留下真实空journal/封存；实际原main mkdir和constructor首open语句确认同handle/一次，重复/旧目录原样失败 |
| Cready撤回后，已准入GetResult的真实响应被代际过滤且原service已destroy | 原session/robot/flow/rpc匹配完成真实Future；retired service保留至原send_response成功后释放，未清时不建同名新服务；unready新Goal不转发 | 一次实际DDS受控ActionServer：已接受UUID的GetResult pending→撤ready→原真实终态送回原client；未知RPC/旧session不完成其他Future，恢复无双server；负例unknownTask如实列 |

## 一个前瞻执行候选，不扫描

拟唯一共同profile original1000-clock100-q10ms：外部world只恢复原wall update1000，dt.001/ODE/传感器不改；clock100/q.01保留。500时原10Hzsim health名义200wallms，A08实测309ms越原.3wall；基座旧1000六次600sim历史只作恢复参数依据，不拿旧成绩配对。新Release固定burst35%CPU收益与GC局部修补使重新评估原1000合理，但不预先保证实时性。WallRate关系变化如实披露，A/B同新profile。

先送审唯一无运动modeB/V3真实WiFi资格：source16wall/总30wall，clock .01sim/.01wall，其他每wall源频率不减，Peer仍原10Hzsim，因时基恢复mask实际wall负载回到约4.8MB/s。原guard/lag全保留，失败即留存不扫750/其他频率。成功后才送A09具体DRAFT。当前仅源码，未build/执行任何新诊断。

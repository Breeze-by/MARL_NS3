# BASE-02 TF续作：边界与证据

续作授权：用户明确要求解决问题继续做。起点为首轮NO-GO交付3eef0e177400fa00085caccbde43ebd2cf9d3cd8。旧base-02-central目录、REPORT/SHA及失败原件不写入，独立base-02-tf-fix工作区/分支继续。

已读取实际Humble TransformListener默认static_qos=KEEP_LAST、TRANSIENT_LOCAL、depth100；原Observer/新中央均误将地图depth1用于tf_static，而每机有模型静态链和共同坐标标定两个独立发布者。

真实rmw_fastrtps_cpp诊断使用domain63、独立fixture话题/diag帧，两发布者均可靠ACK。depth1忙等待时只收到最后一条，雷达链缺失；及时处理则两条齐全，depth100在相同忙等待下齐全。该测试没有Gazebo、机器人话题、速度或目标命令。初次诊断因topic token以数字开头报错，原件保留；修正后才取得上述有效证据。

只修改Observer和中央的静态TF订阅为标准depth100，地图QoS保持1；保存真实就绪/失败时的Buffer帧图、debug tuple和消息计数。原ready判据、停止/安全阈值、Frontier/评分、目标生命周期、Nav2/SLAM/world/模型/驱动均不变。不伪造/重发TF，不以晚探针结果替主Buffer放行。

诊断复现了与首轮症状一致的真实队列缺陷；首轮没有主Buffer接收细节，不能声称逐包证明历史唯一原因。修复后定向测试从实际生产代码读取profile验证，固定提交给独立评审，再做一次traditional 180sim/420wall回归。若出现新真实安全问题立即停止留证，不盲目重启。运行继续只读复用BASE-01原产物，仅覆盖中央Python；不编译底座、不训练、不接ns-3、不开展RL-01。

# 唯一前瞻共同执行profile：pace500-clock100-q10ms

在新结果前固定，不扫参数：外部effective world仅real_time_update_rate1000→500；physics dt=.001、ODE/碰撞/感知配置不改。gzserver启动scoped /gazebo参数publish_rate100.0；真实clock以simTime节流，不能运行期set_param假定已生效。Gateway STEP最大.01sim，原native<=.1验证/固定anchor/.12lag/源龄.4/.55/.3wall及所有guard/stop不变。A/B将共享该profile并重建匹配参考，旧成绩不能直接配对。

这不是与旧v1.1逐点等价：Gazebo物理/仿真timer频率可保持，Nav2 BT/Controller WallRate与其他wall-loop相对sim频率会改变。每wall/每sim offered、actual RX/ROS消费和源龄/health间隔分别报告，不称网络输入整体不变或新RL学习。权重、701、5sim决策周期、目标/Frontier/掩码/SLAM/Nav2算法参数不变，V3不变。固定约.5 RTF只提供处理余量，非硬同步保证；.3wall不豁免，若实际health/clock超限照常FAIL。

唯一无运动资格先预定：原连续夹具modeB/V3，CPUprofileoff/controltraceon，真实DDS合成clock增量.01sim/周期.02wall；其余原每wall TF/odom/100Hz FB/costmap等不降低（保守overspec，非真实Nav2发布频率证明）。源连续16wall约8sim，原BoundPeer10Hzsim不改，预定总30wall含收尾，qualification失败不延长。0GZ/Nav2/Goal/arm/NN，未授权机器人运行。根审实际diff/具体入口后仅一次，不重试或改TTL求通过。

预定入口：`rtk proxy python3 -B net-01/workspace/net01/followup01/continuous_dds.py --name continuous-dds-16-paced-wifi --mode B --feedback-hz 100 --execution-profile pace500-clock100-q10ms --control-trace --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-cpu/net01-payload`。采用现成已固定ELF，cpuProfile默认off，不新构建旧库。当前仅实现接线，尚未运行。

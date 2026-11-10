# TF take 元数据观测方案窄审

仅阅读本机实装Humble SDK和已提出方案；未运行测试、节点、网络模型或Gazebo。它是诊断候选，不是对当前TF等待的修复或首故障归因。

## 本机可确认的接口

`base-01-econ/isolation/rootfs/opt/ros/humble/local/lib/python3.10/dist-packages/rclpy/executors.py:398–403` 的 `_take_subscription` 在原 `with sub.handle` 内调用一次 `take_message(sub.msg_type, sub.raw)`；非None返回 `tuple[0]`，否则返回None。继承原SingleThreadedExecutor、仅对选定TF订阅覆写这段以保留 `tuple[1]`，可以维持原take次数、typed/raw方式和回调参数。

当前实际 `_rclpy_pybind11.cpython-310-x86_64-linux-gnu.so` 字符串仅能确认 `source_timestamp`、`received_timestamp` 两个元数据键，未见publisher_gid或publication/reception sequence键。`include/rmw/rmw/types.h:528–608`虽定义这些底层成员，不能据此宣称当前Python返回字典全部暴露。保存实际字典并明确缺字段，比为补身份另建Node更合适。

## 最小实现边界

- 仅TF23/43/63对应的原订阅保留元数据和take前后mono/threadCPU、实际R ROSClock；其他实体沿原SDK。原take/返回msg或None各一次，不先super take再额外take，保留异常与原调度。
- 不新增订阅、线程、timer、DDS配置或SDK安装修改，不调用guard.reason/tick补观测，不改变Message/header或源时间戳。
- 源的原publish前后增加墙钟与mono括号，记录实际匹配订阅数的变化，均仅作RAM诊断；不把匹配数当逐条接收ACK。
- 原TF三writer可从edge种类/header及各源发布ordinal辅助定位。墙钟SLAM重复相同scanheader是合法原行为，不能用最近header或最近时间强认唯一消息；缺少GID/序列的范围诚实保留。
- source_timestamp先与同一源的publish realtime括号对照；不能直接减monotonic或ROS sim。底层头文件明确source/received采点未严格指定，因此received_timestamp不是已证最早DDS入队/网卡到达时刻。只有字段实际可得且时基已辨认，才能把已证等待继续切分。

**意见：上述范围适合继续实现一个薄的被动观测，不需要为此换时钟或修改原源龄规则。具体源码固定后只核take次数、返回及实际字段，不增加框架。** 本方案本身不证明唯一原因、不改变已有完整负载FAIL，也不签新的运行准入。

## c4e95cf固定实现补审

已逐读 `health/take_trace.py` 与本次Gateway、roles、host、Source接线差异，未执行已有六项0Node检查或任何新运行。`take_trace.py:19–45` 保留原handle上下文内一次take、原tuple[0]/None返回，非目标TF走super；没有覆写 `_execute_subscription` 或handler/回调组。异常原样重抛。Gateway仅显式诊断flag才替换R executor，默认及C不变。Source仅flag开启时记录三TF发布ordinal、匹配数、realtime/mono括号，原publish仍一次，payload/QoS不变。

未发现需要阻止这一唯一A1因果诊断的实际缺陷。它仍是观测，不是修复、不是原SDK安全语义变更。真实字段和首错区间待封存后交叉核；source/received元数据不得自动写成最早DDS入队、reader-ready或纯executor延迟。

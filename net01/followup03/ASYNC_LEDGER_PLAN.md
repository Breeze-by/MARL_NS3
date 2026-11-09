# 单一异步ledger候选（测量前固定）

仅显式--asyncLedger=1开启；默认原串行字段格式化/缓冲路径保留。model捕获原ns3/mono和内部seq，队列只存immutable primitive/owned fields字符串，不跨线程传Ptr/模拟对象/业务payload。writer原序格式化全部JSON并写文件；sniff浮点/packet_trace/drop/node字段移到writer，fields(h)仍在model。PCAP与原所有模型/事件/包/RNG/时间/业务不变，不声称26%CPU全可省。

固定pending容量16384 records，captured-written包含writer inflight；另至多1个model正在构建但尚未提交的临时record，字段来自固定数字/短字符串，metadata报peak和实际max record bytes。满/写错显式失败，attempted/captured/written欠账保留，不能drop或无界堆积。STEP在真实Run后，async等该seq written+flush再发原STEP ACK；原serial不添加新逐STEP flush，避免伪造baseline代价。barrier wall单独报告，不以model CPU下降掩盖等待。Destroy后才finish/join/flush并核attempted==captured==written；final simTime在Destroy前捕获primitive。writer从不调用Simulator。

本候选尚未构建/运行。拟独立build/followup03-async-ledger链接原ns3库/原V3 header，不覆盖旧ELF。唯一fixedburst一对均cpuProfile0/controlTrace1：先native-ledger-serial-01，再同输入native-ledger-async-01，后者仅asyncLedger1并与前者比较除mono外全ledger事件、原stdout协议/完整payload和PCAP全部bytes。两次均native18wall，0ROS/GZ/Goal/NN；各自model/writer/总processCPU/wall、STEP barrier、queue峰值都列。通过机制/有实际收益后才另审一次同pace500-clock100-q10ms完整B资格，不自行运行或改数。

预定构建：cmake -S net-01/workspace/net01/native -B net-01/build/followup03-async-ledger -DCMAKE_BUILD_TYPE=Release -DNS3_DIR=/home/zhuyulab/ns3-workspace/ns-allinone-3.40/ns-3.40 -DCONFIG_HEADER_DIR=/home/zhuyulab/ns3-workspace/net-01/build/network-full-payload；cmake --build net-01/build/followup03-async-ledger -j2。

预定两入口（根审实际diff后执行）：
`rtk proxy python3 -B net-01/workspace/net01/followup03/profile_native_burst.py --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-async-ledger/net01-payload --output /home/zhuyulab/ns3-workspace/net-01/workspace/runs/native-ledger-serial-01 --no-cpu-profile`
`rtk proxy python3 -B net-01/workspace/net01/followup03/profile_native_burst.py --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-async-ledger/net01-payload --output /home/zhuyulab/ns3-workspace/net-01/workspace/runs/native-ledger-async-01 --no-cpu-profile --async-ledger --compare /home/zhuyulab/ns3-workspace/net-01/workspace/runs/native-ledger-serial-01`

## 已执行唯一对照

a90d67a独立build/两入口均native0，7883条attempted/captured/written逐条无欠账，ledger除mono/完整stdout及payload/全部PCAP bytes相等。async queue峰37，记录max-owned279B。RunCPU118.963→114.882ms，含barrier wall119.249→115.291ms，但整段modelCPU206.067→205.067ms，总processCPU259.746→306.589ms，总wall265.117→265.371ms。机制等价不等于性能有用；生产者建议不晋升默认/不自动追加fullB资格。详见ASYNC_LEDGER_PAIR_SUMMARY.json与ASYNC_NATIVE_IDENTITY.json。没有扫参数或追加测量。

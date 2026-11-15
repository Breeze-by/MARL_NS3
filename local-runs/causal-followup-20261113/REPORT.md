# 固定启动六例：结果与边界

2026-11-13。本task共7次实际START：原a启动失败永久保留，随后独立共同修复源码g–l六例；旧b–f READY退役未启动。逻辑i实际目录m。已结束，不再追加实验。

|顺序/对|逻辑例/物理目录|Wi-Fi指数|local T95|中央 T95（主）|R T95|末中央覆盖|迟到p95 wall-ms|
|---|---|---:|---:|---:|---:|---:|---:|
|1/对1|g/g|2|null|null|null|89.97%|5.299|
|2/对1|h/h|3|37.23|38.50|38.53|96.79%|7.770|
|3/对2|i/m|3|null|null|null|88.88%|4.924|
|4/对2|j/j|2|null|null|null|87.02%|3.439|
|5/对3|k/k|2|null|null|null|90.37%|2.168|
|6/对3|l/l|3|null|null|null|90.55%|2.197|

T95单位为相对固定G20的sim秒；null为60sim内未达，六例各145采样且无missing。B达到0/3、B-loss3达到1/3，不计算成功者均值或用60补值。末图是窗口末附近实际样本。

六例运行/停止/网络/复制/已知进程退出通过；66个G25..75槽全lateness0，六例各6000token，迟到>40wall-ms均0。原RTF .25±2%、p95≤20ms、>40ms≤1%、对内RTF差≤1%均通过；三对差0.00161953%/0.00155438%/0.00314049%。l的G80显式关闭callback记录在shutdown前未观察到，保持UNOBSERVED；原入口门/组件保证不变，实际无≥80新Goal入口。

a失败由C exporter白名单在入网前过滤初始化marker造成，非RF；最小修复只在新profile准该kind，真实原exporter→DDS→原d53 ns-3 Wi-Fi→R callback组件通过。原a、旧B180时序FAIL及旧b2/l2均保留、不混样本。

固定physics seed2026110601/network seed2026110901/native run1；fresh-process重复不是独立RF种子。只改变路径损耗指数2→3，固定权重/701/Frontier/Nav2/速率/保护/功率/MCS。共同源码67路径，原d53构建源与当前native源码身份分开，原13DSO未重hash。

对内首701分别83/89/73个元素不同、共享grid405/322/244格不同。同臂首701也全部不同（B三组91/80/82；L3三组71/57/67），候选实际记录均不相同。原NPZ逐值比较，无重新编码/推理或hash近似。

66次policy-use链与实际读取/拒绝分支已记录；337839个实际被取到的转发take均有唯一已观测publish bracket候选，4982个C本地派生take另列，unknown/ambiguous/pending均0。它不证明全部源消息送达或无丢失。callback→use为成功更新该state/cache的回调开始→policy-use开始间隔（包含回调处理），不是generation→use AoI；源生成、精确原R publisher、GID和TF插值来源仍未测。未见L3一致更差，工程PASS不等于RF唯一任务因果。

主要小件：[总结果](COHORT_RESULT.json)、[时序](PACING_SUMMARY.json)、[消费者](six-cases.consumer-summary.json)、[同臂输入](same-arm-first-input-comparison.json)、[计划](PLAN.json)、[最终绑定](COMMON_BINDING_POSTFIX.json)。完整审查见[当前项目审查](../../docs/COMMUNICATION_CAUSAL_REVIEW.md)。本机原始结果不是可移植发布包。

所有本task独占native RAM源a/g/h/i/j/k/l已依据既有copy/owner证明定点释放，各RAM-release记录和全部disk raw保留；旧RAM与其他路径未动。

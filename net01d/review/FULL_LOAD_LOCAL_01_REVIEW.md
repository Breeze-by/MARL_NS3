# full-load-local-01 独立小范围原件复核

对象：502ba02 首次完整负载A1，封存目录 `net01d/runs/full-load-local-01`。仅读process/first-failure、C客户端、三R源的小JSON，以及1,038,457字节Gateway JSON中的Action记录和89/95目的发布；没有读bag、运行节点/模型或重复sourcefresh首错归因。该归因由runtime负责。

## 实际结果

原outer退出1，总6.371345wall；coordinator退出1，其余角色0，无强杀。FIRST_FAILURE为三guard `health_original_sources_stale`，不是正常32wall结束；Gateway failure字段本身为null不覆盖guard故障。正常阶段、第四目标及预定停供负例均未完成，不能签P5。

### 真实授权和目标

- 三R实际arm服务均返回success，原guard记录为1.05sim授权。
- C在1.11sim请求三Goal，三台受控服务端各接受一次；原UUID分别为 `0000000078c3ffc00100000000000000`、`...0200000000000000`、`...0300000000000000`。每台R保存的完整Goal_CDR与对应C Goal_CDR逐字节相同，未只从接受结果推断字段一致。
- C实际收到三接受响应，并提出三GetResult；反馈实际到达计数为12/13/13。这里没有RL或Nav2物理执行。
- 首正常guard故障后，三R原记录均包含实际Cancel返回0及精确匹配的UUID、原GetResult终态5、PAUSE success；原R owned为空。
- C客户端只来得及记录tb1/tb2的终态5，tb3的GetResult在客户端退出快照仍pending。Gateway随后保存内部RPC/确认0、END及executor退出正常，不能用其代替末端客户端收件证明。也不能把本次故障取消称为计划的正常4/4/5结果。

### 共享地图与任务记录已实际接线

- 原MergeMapNode的253×211共享图实际在C产生；89的完整CDR为53,495字节，C capture和R目的发布保留相同原记录hash；三R诊断订阅确实消费了该共享图。
- 95实际C捕获并R发布8条；三R诊断订阅各实际消费7条：三请求、三接受响应、tb1的取消结果。尾部tb2结果只证明Gateway目的发布，不能追认三个订阅都消费；tb3结果没有客户端记录。
- 89/95路线均为0→1，再在共同R DDS域上供诊断订阅读取。这里证明业务路径实际接线，不证明三台STA各自传过一份，也不把A1本地交付称为Wi-Fi。

## 独立意见

保留该次完整负载FAIL；已确认真实授权、Goal字段/UUID、原R取消/暂停及89/95接线工作。没有证据将故障归为RL或Nav2，也不能因本机取消成功称物理停稳通过。源内容仍为明确合成观察和旧Grid内容模板，无新SLAM/策略运行。本复核不提出新回合；下一动作由首错因果证据决定。

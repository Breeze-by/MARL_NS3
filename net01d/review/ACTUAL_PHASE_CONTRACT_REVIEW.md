# actual-corr6201 相位条件的独立窄审

仅阅读runtime的 `health/real-gazebo-phase-01.{json,md}`、现Mock及TimeControlState源码，并抽核旧A10/B01原R clock CSV的首两样点与103.33sim样点。未重复全量ACK计数、运行代码、修改源或开展新实验。

## 依据及代表范围

runtime已列旧A10的14322个和B01的10951个连续真实10ms/10iteration物理ACK；全部ACK前coordinator已观察G=E，独立R CSV也含每个E值。原CSV抽核与选中记录相符：B的103.33样点mono458208.158679964，早于coordinator该ACK的458208.160635003。时钟已真实发布，不是把DDS系统时间与mono相减猜测。

这足以支持**所选Corr6201旧实际配置**在ACK边界的相位0，不代表任意未来Gazebo world、启动相位、插件或更改参数。独立witness偶有回调晚一两格，不等于物理采样相位偏移；不能把回调延迟补成新的G。

## 与Mock及信用规则的关系

现 `mock_physics.py:24–32` 初值5ms，每次实际增加10个1ms iteration，仅跨整10ms发布Clock，因而每次完成E=G+5ms。原 `time_control_state.py:63–73` 要求下一物理完成端E+10ms不超过offset+N_ACK+20ms。

Native赶上已观察G后，相位0时原界限允许在没有更新Native ACK前最多再推进两个10ms token；5ms相位只允许一个。这是同一字面20ms界限下的离散相位效果，不能把“两个token”写成两个物理RPC同时inflight。原逻辑仍只有一个物理RPC在途。

## 可接受的最小纠正

另建显式actual-corr6201 fixture模式，以0开始、保留原逐iteration的10ms Clock发布，不补人工末端Clock、不改实际offset。Step10ms、clock100Hz、nativeq10ms、credit20ms、pacer20ms和所有wall/source期限均不变；旧5ms默认继续作为单列stress。

A1/B用同一个新相位模式及原mixed wall/sim源合同。相位校准后sim源随实际clock产生更多perwall业务并不违反同一配置，不能反过来按旧捕获均值降rate制造通过。明确区分本项与先完成的harness清理修补，避免把两者或诊断观测混称唯一性能收益。

**结论：有明确实际依据，可按上述范围准备fixture条件纠正；未发现实际阻断。** 这是P5场景真实性校准，不是加信用、无线调度优化或RL改进。旧压力FAIL、完整B FAIL、旧真实137ms等待均保留；新模式是否通过仍需其实际结果，不能从相位事实预先保证，也不能据新PASS覆盖旧失败。

## 实际差异补审

已读新mock/host/roles工作差异：mock默认stress5ms仍初值5ms；actual-corr6201仅初值0，原循环10个1ms iteration、跨整10ms才发clock和原返回ACK未改，没有人为末端clock。host传显式phase；actual A1/B都要求同类独占RAM记录后端，保持full/metadata与32/60/4Goal范围，减少旧Disk/RAM选择差异，仍不消除模型CPU/IPC/同步差别。cleanup02明确不使用新phase。未见credit/TTL/q/pacer/Policy改动；仅准入准备评价，actual两臂仍由root分别决定，不提前签通过。

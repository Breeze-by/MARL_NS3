# 原版3.40 Release-portable Native显式接线（未构建）

root选择官方Release且NS3_NATIVE_OPTIMIZATIONS=OFF，真实build_profile=release/无库后缀；不是-optimized，不改名/symlink。独立sourceRoot与build由runtimehelper准备、root另准copy/build，旧ns3树/旧ELF不变。Native仅可显式选择匹配build/include、全部精确library suffix和同根RPATH；默认仍原NS3_DIR/build、-default，不改Native其他编译flags。find_library在当前指定lib目录NO_DEFAULT_PATH，每次配置清除旧library cache避免混树。

拟新依赖根：/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03，source=src，include/lib=build/include、build/lib。此目录尚未准备完成，本阶段只CMake接线，不配置/链接/测试。默认asyncLedger=0、cpuProfile=0；暂停前检alignment已单独提交9c9f9ad，原deadline/门限不放宽。后续实际依赖与Native身份由各自新build记录，不根据目录名推断来源。

待根审准新依赖完成后，Native命令：
`rtk proxy cmake -S net-01/workspace/net01/native -B net-01/build/followup03-release-portable-native -DCMAKE_BUILD_TYPE=Release -DNS3_DIR=/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03/src -DNS3_BUILD_DIR=/home/zhuyulab/ns3-workspace/net-01/ns3-release-portable-followup03/build -DNS3_LIBRARY_SUFFIX= -DCONFIG_HEADER_DIR=/home/zhuyulab/ns3-workspace/net-01/build/network-full-payload`
`rtk proxy cmake --build net-01/build/followup03-release-portable-native -j2`

后续唯一同fixedburst Native(0ROS/GZ/Goal/NN)以cpuProfile0/serial对比已封存native-ledger-serial-01：除mono全ledger/stdout完整payload/PCAP bytes/attempted=captured=written均需一致，不能为了优化构建放宽容差；报告真实Run/ACK-barrier/总CPU/wall。原库是-O2非O0，候选O3/ASSERTLOG关闭收益未知。不是网络参数或策略优化，不自动启动benchmark/GZ/NET02。

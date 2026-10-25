# 第五十七批：原双块复数DAT预期的version9兼容验收

本批补齐原自建两块/非零虚部数据的真实MCP读取证据。没有宣称DAT version10写入崩溃已修复，也没有将合成文件当求解输出；P04整体仍deferred，34项状态不变，目标active。

## 先核对已有证据

P04原remaining文字已记录新RC AC非零虚部和OUT/DAT读取成功。engine-dat-mcp、pspice-run-mcp及run-transient-mcp等已有记录，覆盖独立DC/AC/TRAN及正式计划/产物关联；本批没有重跑这些已通过切片，也没有再次将它们当全新功能。本次集中处理ISS-P04-complex-fixture-native-crash的原合成数据预期，原expected.json不改。

## 崩溃位置与对照

对原自写脚本添加Tcl执行enter/leave跟踪，保持原脚本hash：第一块所有header/name/data/closeBlock成功；第二块addBlock及header/name成功，第一条addTimePoint进入后访问违规3221225477，自有进程0。此前只有create=1日志，现已定位到具体调用和block。

本机psptclcmdref的addBlock/closeBlock/setBlock/addTimePoint/create及psptclsample的AC数据示例核对后，保留原两块频率/实部/虚部预期，对照显式setBlock、取消closeBlock、组合、time-point Type1、预创建两块，6例均原生崩溃。再对照重置行数、复用names、组合、version9、直接PIO对象、额外加载引擎、补完整header，共7例；只有version9完整生成并独立读回原预期，其余失败保留。部分变体的崩溃阶段不同，以各自完整trace为准，不统一宣称均第二块同一点。

官方create文档明确支持DAT9和10。使用9作为合成测试夹具的兼容格式，并未降低数值/块数预期；原version10失败与原文件保留。没有在公共MCP中提供DAT写入接口。

## 新固定夹具与真实MCP验收

新增私有fixture_complex_dat_v9.tcl，仅生成固定原合成数据，逐步核对本机native bool返回，最终关闭文件。两次全新目录、两个独立owned进程生成后，使用实际155工具stdio服务读取：

- block0 Frequency=[10,20,30], Gain.real=[10,20,30], Gain.imag=[-1,-2,-3]。
- block1 Frequency=[10,20,30], Gain.real=[110,120,130], Gain.imag=[-2,-3,-4]。
- 每块3行/complex=true；Frequency虚部均0，顺序读取及跨块1→0→1→0交错单行分页准确。
- block分页、缺失trace、越界block/row、末尾空页、关闭后session拒绝通过。
- 第二次全新生成文件由新MCP进程独立读取；仅篡改本次imported.dat副本后target_changed拒绝，原DAT和原oracle hash保持。
- Frequency单位明确为axis_name_convention/Hz；Gain单位unknown，不伪造原生物理单位。两次产物均imported_file，jobAssociationVerified=false、solverSuccessVerified=false、producedByPlan=null，未冒充新求解结果。

完整记录：.local/custom-complex-dat-mcp-20261024/report.json。原数值oracle沿用.local/dat-complex-1fb7500a1b/expected.json，原脚本和原失败DAT未修改。固定夹具代码为原创，没有复制厂家完整示例或手册。原生数据留.local忽略目录。

## 状态与后续

ISS-P04-complex-fixture-native-crash继续open，记录version9兼容通过与version10仍失败两个事实。自建多块非零复数读取缺口已有实证补齐；数字/混合数据、单位/导出及完整P04覆盖仍需完成。Capture3969及其他原门禁继续保留，不能用本批通过替代。

生产MCP逻辑/工具契约与第五十五批hash一致，仍155工具；本批只增加私有探针/夹具和验收工具，沿用373完整回归372通过/1原权限skip，没有无变更重复整套回归。34项仍1 baseline_passed/21 partial/10 deferred/2 planned。下一P04数字/混合与导出能力及剩余错误集中收敛。无GUI、安装或真实设计修改，无提交推送。

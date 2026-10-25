# 第十二批：独立引擎数值与新DAT兼容

2026-10-23。75公开工具；仿真执行仍为内部验证脚本，pspice.run尚未发布。整体34项目标active，P02/P03/P04均未完整验收。

## 官方依据

本机psptclsample/Accessing_PSpice_using_TCL_Scripts.html与psptclcmdref的PSpiceSetLicenseBatchMode、PSpiceSetupAnalysis、PSpiceCommandDo、PSpiceTranEnd、getDataNames、getJSON页面已读取。独立tclsh加载orPSP_ENG64.dll/orpspeng，使用官方PSpiceAD batch mode，不修改许可证配置。分析仅固定dc/ac/transient枚举映射，FINISH用于刷新/解锁OUT/DAT，再清理。独立引擎Tcl与psp_cmd CLI分开记账，后者原60秒timeout仍未解决。

## 原生DC通过与输入失败

`.local/pspice-engine-20261023/report.json`：数字节点DC等值5V分压，新OUT的5V sweep为2.5V，误差≤1e-6V；进程约2.282秒，owned剩余0，新OUT/DAT/hash齐全，源不变。该24.1运行时setup/analysis/finish成功均返回字符串0；官方只写bool，因此不把Tcl catch=0、root exit=0直接视为求解成功。

`.local/engine-analog-20261023/report.json`：IN/OUT节点配具名.PRINT/.PROBE选择出现ORPSIM-15090（PRINT/PROBE device undefined），setup/analysis返回1但Tcl catch与root exit仍为0，未生成DAT，整体失败。保留三个原case及预期，不归因许可、不把无DAT当成功。generic engine adapter后来已在setup/analysis/finish非0时停止并输出失败receipt；还需实际错误分支复测，不宣称已验收。

官方样例裸.PROBE变体在`.local/engine-analog-probeall-20261023`重新独立创建，电路IN/OUT名称保留，物理参数与原数学预期不变；三项均原生求解/FINISH成功并新生成DAT。最初仍被既有DAT元数据decoder拒绝，原失败report不改写。

## DAT修复及独立数值验收

新DAT的getJSON返回旧式对象文本（含尾逗号/路径未转义），不同于官方历史样例的block数组。没有宽松修复JSON。仅识别该旧式结构特征后，另起native worker逐block调用setBlock/getHeaderData/getDataNames 0，生成规范结构，再复用原严格校验（block/index/计数/名称唯一/轴/有限数值）。manifest明确headerSource=native_direct_headers，aliasGroupingSource=not_available_from_direct_names；精确名字可查，但不捏造alias归组。陌生坏JSON仍拒绝，不触发fallback。

`.local/engine-dat-mcp-20261023/report.json`：从保留的求解产物通过实际75工具stdio读取，以原expected.json核验，未重求解/未改oracle：

- DC 1行，输入5V、输出2.5V，≤1e-6V。
- AC 3个复数点，H=1/(1+j*2*pi*f*RC)，逐点实/虚部误差≤1e-6，虚部非0；中点159.15494305Hz，幅值符合1/sqrt(2)。
- Transient 541点，逐点1-exp(-t/tau)最大绝对误差2.8810232710618777e-6V（阈值2e-4V），插值tau=0.001000004061376418s（相对阈值1%）。

这些是明确host fixture的数值证明；导入DAT工具仍正确保持jobAssociationVerified/solverSuccessVerified=false，正式solver job service尚未实现，不能偷偷把导入变成新任务认证。

3项主机测试覆盖旧式识别、独立字段校验、未知trace在native调用前拒绝；任意坏JSON不fallback、count不一致不绕过验证。完整210回归209通过、1原symlink权限skip。`.local/dat-compat-after-direct-20261023/report.json`官方RFAMP 21block/EXAMPLE59点的12例真实MCP回归通过，含分页、alias、缺trace、close和篡改拒绝。最终75工具契约同步该真实tools/list。

## 内部诊断故障与后续

绕过公共trace白名单的临时原生诊断同时请求了不存在的trace，AC进程退出3221225477；没有逐方法日志，不能断言具体是哪次get造成。DC/TRAN同诊断返回0且get未知trace有时返回全0，进一步说明必须保持精确白名单。公共接口/主机测试已拒绝未知trace，不用这些直接native异常充当正常读取结果。该诊断原始进程信息见本地direct-probe-process-audit.json（从工具输出如实登记，非native逐步日志）。

原自写DAT writer多块崩溃仍未修复；非零复数读取要求现有新求解正例，但自建多块与正式新job关联、数字/混合/原生单位仍待验收。完整P02的持久任务/manifest closure、取消/超时/恢复、错误分类和CLI仍待完成；P03测量/通用波形指标未开放。接下来优先持久engine-run闭环与故障验收，随后继续Capture独立项和队尾修复。

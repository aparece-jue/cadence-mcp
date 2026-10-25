# 第六十四批：PSpice原生输入检查任务

2026-10-25。原34项范围保持，整体目标active；本批完善P01，暂不标记完整通过。

## 官方依据与固定入口

已读取安装内PSpiceSetupAnalysis、PSpiceTranEnd文档。固定原生脚本只调用批量许可证模式、PSpiceSetupAnalysis、FINISH及cleanup，不调用任何DC/AC/TRAN/OP执行命令。运行实测返回0表示相应阶段成功，不能仅依文档bool字样猜测。

新增pspice_plan_input_check/apply_input_check/input_check_jobs/cancel_input_check/recover_input_check/inspect_input_check共6工具，实际173；既有失败观察工具kind新增input_check。输入仍由pspice_prepare冻结显式INC/INCLUDE/LIB闭包，检查计划绑定完整准备清单hash、每份原始/准备字节、分析类型、timeout和simulationId。执行前绝对重定位到新的独立任务目录，复用既有所属进程树、幂等、不重放、取消与超时机制。

新检查报告必须有固定入口成功回执及OUT解析无错误、job输入精确符合重定位预期，全部输入/OUT/receipt/若存在的setup.dat都绑定hash。setup.dat只是初始化副产物，不作为已求解波形认证。报告明确nativeParserSetupVerified=true而analysisExecuted/solverSuccessVerified/numericalAcceptanceVerified=false，scope=native_parse_setup_only。模型隐式搜索闭包、全SPICE方言、收敛和电路安全没有因setup成功自动通过。

## 身份与恢复

不能仅凭入口CIR的sourceFingerprint混用结果：相同CIR引用的模型/参数文件可能变化。计划、preview、报告及结果均额外绑定preparedManifestSha256和simulationId；新增测试证明同入口hash但不同依赖内容对应不同清单身份。原输入会话关闭后，冻结文件仍可执行/恢复。

验证阶段中断但成功原生回执保留时，新服务可验证已有文件并生成验证manifest，不再运行原生worker；nativeCompletionVerified=false而nativeReceiptVerified=true。缺失原生回执时，没有独立数值预期可证明setup完成，错误为空的OUT也不足以认证，apply/recover均setup_completion_unverified；保留失败，拒绝重放。

## 原生与MCP验收

- `.local/input-setup-probe-20261025/report.json`：5原生私有电路，合法参数输入成功；缺节点0/未定义参数/DC语句缺参数/缺模型均setup失败，源hash保持。
- `.local/input-checks-mcp-v2-20261025/report.json`：6项真实173工具MCP用例。4文件嵌套INC/INCLUDE/LIB与相对路径参数输入、实际引用模型的OP输入setup通过；其余4反例均OUT错误拒绝，失败观察绑定输入且worker停止，不能作为成功报告读取或重放。计划在关闭输入会话后执行，新服务inspect/apply/recover不重放通过。
- 同一报告另执行独立新DC数值任务：R1=SCALE*RBASE、R2=RBASE、5V源，独立预期5/3V按1e-6绝对误差通过。没有用setup检查代替参数数值求解。
- `.local/input-check-faults-v2-20261025/report.json`：7项故障案例通过。验证中断/完整回执的新服务恢复、缺回执拒绝、启动窗口取消、固定延迟1秒timeout、原生结束后输入字节变化、已验收OUT篡改、冻结准备输入prestart变化。所属进程均确认停止；prestart变更不启动worker；篡改后读取/恢复/复用拒绝。
- 初次相同用例及故障报告保留在不带v2目录；补完整依赖身份后，以v2重新验收，未删除旧证据。新增9 host tests；420完整回归419通过/1原符号链接权限skip，skip不计通过。173实际工具契约重新生成。

## P01剩余与下一步

ground、参数表达式、分析缺参及缺模型已有实际正反例，但原ISS-P01-named-output-selectors仍open，不能用bare PROBE替代其完整验收。已定位官方01commands.html#26898说明方括号强制名称按节点解释，下一步在原IN/OUT选择器电路上对照官方方括号形式，保留原失败与原数值预期。其余显式引用边界、所有原必需条件需完成审计，P01仍implemented_partial。

34项状态保持2 passed、1 baseline_passed、19 implemented_partial、10 deferred、2 planned。此前C01/C02通过状态不被重定义；Allegro排除，PDF延期，无GUI、无安装/真实工程改动、无提交推送。

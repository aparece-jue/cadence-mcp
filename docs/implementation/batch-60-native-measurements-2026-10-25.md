# 第六十批：完整原生分析与MEASURE结果

2026-10-25，目标active。原34项业务验收范围保持；P03仍implemented_partial，P04仍deferred。

## 官方依据与故障定位

安装内`doc/pspcref/01commands.html#measure_command`说明.MEASURE及独立测量文本结果；`doc/psptclcmdref/PSpiceDoAnalysis.html`为完整分析入口。此前分步doDCAN/DoTRAN没有测量文本，AC VM(2)有原生表达式错误。新8例对照保留原电路：doALL的DC/AC/TRAN/修正AC仍无测量文本；PSpiceDoAnalysis四例均生成input_measure.txt，其中原VM(2)为Evaluation Failed，修正V(2)返回0.70711。

PSpiceDoAnalysis已完成并关闭分析，再调用FINISH返回1；生产固定入口不追加该分步FINISH，仅确认完整入口与cleanup返回0、OUT结论/统计、DAT独立可读和测量预期。没有降低旧分步任务的FINISH要求，两种路径使用各自严格的验证钩子。

## 实现

新增6个定型工具：pspice_plan_measure_run/apply_measure_run/measure_run_jobs/cancel_measure_run/recover_measure_run/inspect_run_measurements，实际166。独立pspice_measure_run任务账本复用输入闭包冻结、重定位、所属进程、幂等和不重放机制；固定原生完整分析脚本，不提供任意命令入口。

当前只接受单一DC/AC/TRAN分析类型、至多64个唯一英文标识符测量声明、至多128个独立字段预期。测量来源声明和预期冻结入计划；解析value/at/from/to，有限数值、重复名称/字段、未知输出和失败求值严格处理；结果名称全集须与输入声明一致。原生WHEN输出包含触发阈值value和发生坐标at，时间常数必须检查at，不能把0.632121当成秒。

任务必须有OUT本次完成证据、非空可独立读取的相应DAT和全部声明测量结果；声明字段按独立预期比较。测量文本与输入/OUT/DAT均进入同一hash manifest，后续读取/恢复/幂等复用先核对全部文件。numericalAcceptanceScope为declared_native_measurement_fields_only，designPassed仍null。没有据此认证所有波形、完整测量语法、物理单位或电路安全。

## 验收证据

- `.local/native-measure-modes-20261025/report.json`：8项完整入口/原电路对照，原source未变。
- `.local/native-measure-mcp-v2-20261025/report.json`：3项真实MCP通过。DC最大2.5V、平均1.25V、4V扫值处2V；RC瞬态1ms发生坐标及0.632120558829预期；AC截止点幅值1/sqrt(2)，受原生输出精度约束使用1e-5绝对误差。原VM表达式OUT错误、错误独立预期、待执行取消均拒绝；新服务恢复/读取/幂等不重放通过，source/oracle未变。
- `.local/native-measure-mcp-20261025/report.json`保留首次失败：3正例已通过，验收脚本把原VM负例错误预期为native_measurement_failed；实际更早由OUT错误pspice_output_error拒绝。修正的是负例分类预期，生产未吞错误。
- `.local/native-measure-faults-20261025/report.json`：5项真实故障案例通过。回执丢失后新MCP恢复、数值文件不变且nativeCompletionVerified=false；启动窗口取消与固定延迟timeout确认所属根/观察到的子进程退出；测量数值改变被预期拒绝，恢复/重放拒绝；已验收测量文本被改变后读取/apply/recover均拒绝。
- `.local/transient-after-native-measure-20261025/report.json`：旧分步瞬态完整541点RC响应与时间常数0.001000004061376418通过，保留原预期。
- 新10 host tests；完整401回归400通过/1原符号链接权限skip，未将skip计通过；实际契约同步166工具。

## 数字数据专项与剩余项

`.local/digital-get-forms-20261025/report.json`：官方get与安装QuickView示例getR/长get共8调用。模拟V(ANALOG)正确全1V；DIN与不存在名称得到相同58零值，非5行数字事件；getR与长get两组连模拟对照都未返回值/数组。数字状态不可据此认证，ISS-P04-digital-value-access继续open，失败后移。生产仍拒绝数字数值，不推断“无错误即成功”。

ISS-P03-native-measure-results针对“缺少原生测量结果入口”的复现问题可结案：已有公开完整入口及真实数值/故障链；P03整体仍需更广诊断/单位与完整门禁。TRIG/TARG、PARAM链、其他native语法/失败文本、许可证/非收敛、官方CLI及Capture联动未因本批自动通过。

无GUI操作，不改安装或真实工程，无提交推送。

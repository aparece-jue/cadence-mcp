# 第十三批：持久PSpice引擎任务

2026-10-23。实际81个MCP工具，P02/P03/P04仍partial，整体34项目标active。

## 实现与工具契约

pspice_runs.py复用IsolatedJobs持久plan/digest/幂等/锁、15分钟计划期限、worker启动前started记录及Windows owned进程树。新增pspice_plan_run/apply_run/run_jobs/cancel_run/recover_run/open_run_dat共6工具，capability=experimental_independent_engine_tcl；不调用psp_cmd，不改变原CLI未通过状态。固定dc/ac/transient枚举，不开放任意Tcl/shell。原生接口/官方资料沿用第十二批；仅对本机24.1已验证的返回0成功做严格检查，不把catch=0/exit=0当作成功。

plan绑定pspice_prepare会话的manifest/hash及所有prepared/original副本；不依赖新server还记得输入会话。每个run重新复制到独占job目录，将已登记INC/INCLUDE/LIB重定位到本job闭包，预后核验来源，拒绝未知文件/控制directive和嵌入FILE/PATH等形式。保留全SPICE语法、隐式模型查找/所有文件副作用未完整证明状态，不把该保守预检说成全解析器。高级.step/OP等其他流程仍须专门合同和验收。

写后验证输入闭包未变、receipt各阶段、OUT本次无已识别error且含FINISH/statistics、DAT分析类型/非空analog行、轴全部token有限。调用方可给最多32个独立trace-row real/imag与绝对/相对容差；只认证声明的行/分量，不认证整份波形或设计安全。所有输入及OUT/DAT hash写入run-artifacts.json，缓存结果/新server/open_dat都重新核对每个产物，而不只验证manifest文件。

open_run_dat只从固定verified job映射注册内部只读快照，不扩展公共读根。公共DAT query/samples沿用不可变副本，manifest明确verified_job_snapshot、producedByPlan、runManifestSha256，samples带jobAssociationVerified。普通外部导入仍保持false。恢复缺失receipt保留nativeCompletionVerified=false，不伪造原生回执；数值和输出证据单独核验。

基座新增worker_error hook，Capture默认错误码保持原样，PSpice原生错误分类为本次OUT错误或engine失败。更细的非收敛/许可等分类尚未完成；timeout不推断许可原因。

## 真实MCP验收

`.local/pspice-run-mcp-20261023/report.json`（真实81工具/schema）：

- 带INC电阻依赖的DC新任务2.5V与RC AC中点0.5-j0.5通过；源/依赖hash不变，open_run_dat与分页结果带正确plan关联；公共dat_open直接访问内部job路径仍拒绝。
- 故意期待3.0V，真实求解后simulation_expectation_mismatch，输出不可打开，重复apply拒绝重放。
- 故意具名PRINT/PROBE非法输入真实引擎报错，分类pspice_output_error；不将无DAT或catch成功当作完成。
- pending取消、严格extra字段拒绝、jobs分页通过；timeoutSeconds=1真实超时，owned剩余0。
- 新server相同key复用artifact、无求解重放；向自有DC DAT追加字节后cached apply及open均target_changed拒绝。该DC任务故意保持已篡改的负例状态，不修复或冒充当前仍可用；另一AC正例保持有效。

`.local/pspice-run-faults-20261023/report.json`：真实求解结束后测试host删除仅自有receipt，首次apply失败且process落盘；新stdio MCP recover仅读回原OUT/DAT/声明2.5V，状态verified_recovered、nativeCompletionVerified=false、无重放，open_run_dat通过。OUT/DAT hash前后不变。另一个真实worker创建/绑定后在启动窗口取消，owned剩余0；不是所有求解/保存阶段中断证明。

`.local/run-transient-mcp-20261023/report.json`：公开持久transient任务完成，关联DAT分页后541点符合1-exp(-t/0.001)，最大误差≤2e-4V，插值tau=0.001000004061376418s满足1%。plan自身只声明了首点期望，完整波形是此专项host oracle额外检查，不把首点认证扩大为通用工具已实现RC拟合。

## 主机回归与剩余范围

5项新测试覆盖闭包重定位/源不变、boolean/非有限容差/analysis/timeout、未支持执行引用拒绝、pending取消/陈旧依赖阻止native、缓存返回必须复核每个输出。首次215回归因旧测试仍断言pspice.run=unavailable而失败；原日志保留。依据真实正反例更新为实验性引擎capability，最终215项214通过、1原文件symlink权限skip。最终契约取真实stdio tools/list。

仍需：CLI原timeout、OP/其他分析/复杂模型与隐式查找闭包、更细错误/许可/非收敛分类、所有求解/关闭/写文件中断窗口、资源长期浸泡及历史目录sharing问题、正式OUT结果衔接、通用measure/waveform metrics、Capture生成profile/CIR及参数迭代。原自建多块DAT writer崩溃、层次/总线/DRC/Capture编辑等队列仍完整保留，不能因本批闭环宣布全部Cadence验收结束。

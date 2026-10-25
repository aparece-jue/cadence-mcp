# 第六十一批：原生失败诊断与失败任务检查

2026-10-25，目标active，原34项验收范围保持。

## 原生复现与修正

依据安装内`doc/pspug/B-conver.html`对DC/瞬态非线性收敛与时间步失败的说明，以及`doc/pspcref/00intro.html`关于IF不连续的警告，创建独立无解关系N=IF(N>0,-1,1)，以低ITL1/ITL2执行单点DC。另建缺模型和冲突理想电压源两个独立反例。

原非收敛引擎返回0且所有分步回执返回0，但OUT写`ERROR -- Convergence problem in DC sweep`。原解析器只匹配冒号，漏掉错误，最终由DAT不完整拒绝为unexpected_simulation_data；没有把该任务验收为成功。原始计划、日志和失败状态保留在`.local/solver-diagnostics-probe-20261025/report.json`。

现解析器同时识别冒号和双横线原生错误；仅依据明确error/fatal行作分类，不因时间长或含有license字样作判断。复现确认ORPSIM-15113且Model/undefined为missing_model，ORPSIM-15143且电压源/电感loop为topology_error；明确收敛/时间步失败返回pspice_nonconvergence，其他错误保留pspice_output_error。许可证明确checkout失败模式仅通过host反例测试，尚无本机真实许可证失败验收，不宣称该门禁通过。WARNING不会因为出现失败词而升级为错误。

## 失败任务接口

新增只读pspice_inspect_run_failure(planId,planDigest,kind=engine|measurement)，实际167工具。只检查终末failed/cancelled任务；已启动worker必须能证明stopped，没有worker身份不能假定已退出。固定读取任务目录的OUT/receipt，限长、双hash复核，并比对可用输入闭包。无输出的待执行取消明确workerNotStarted，不能伪造已运行/已停证据。

返回failed_job_observation、文件摘要、原错误、进程记录和结构化诊断；solverSuccessVerified/nativeCompletionVerified/numericalAcceptanceVerified均false，designPassed=null，不能打开成功DAT或重放任务。此为失败产物的当前观察，不是给失败输出签发成功manifest。对输入被改或输出无法识别的情况保留未核实信息，不猜许可证健康状态。

## 验收

- `.local/solver-diagnostics-mcp-20261025/report.json`：3项真实MCP新失败用例通过。非收敛exit0被明确拒绝；缺模型和源环路exit1分类正确；独立源hash和预期未变。失败DAT打开、重放、恢复均拒绝；新服务观察hash保持；原历史非收敛任务不重跑即可读出新分类，其原记录错误仍保留。
- 同一报告验收实际1秒timeout和待执行取消。timeout保持timeout且不推断license_unavailable；待执行取消无worker/无输出时不伪造成功。错误计划digest拒绝。
- `.local/measure-failure-inspect-20261025/report.json`：2个旧原生测量失败只读检查通过，原任务hash未变。原VM表达式属于OUT错误，错误数值预期任务的OUT可无原生错误，两者都保持业务失败，不能将“OUT无error”等同任务成功。
- 新10项host测试覆盖双横线、严格分类、warning、明确license失败与超时反例、待执行/运行/未知worker、只读不执行和读取中篡改拒绝。完整411回归410通过/1原符号链接权限skip，实际167工具契约同步。

## 剩余范围

ISS-P03-uncoded-native-error按该原生双横线复现与公开拒绝链路结案。P02/P03整体不因本批自动通过：真实许可证失败、官方CLI原超时、其余要求仍要逐项核查；完整诊断语法、其他收敛情形也未普遍认证。P04数字值访问、DAT10写失败，Capture原连接/保存/缓存问题及端到端参数迭代继续未完。

下一步按原34项的明确验收条件核对证据与真实缺口，优先关闭可独立完成的必需项，再集中修复原失败；不以新增工具数代替业务完成率。无GUI、无安装/真实工程改动、无提交推送。

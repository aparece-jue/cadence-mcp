# 第80批：层次读取异常完整性

本批修复实际读取器的错误处理，未增加工具，未关闭完整H01门禁。统一MCP仍193个工具。

## 原始缺陷与复现

官方Capture Tcl参考PDF p172分别声明有效属性迭代返回DboState；层次children迭代的返回对象与状态须共同检查。旧inspect_hierarchy.tcl将NextEffectiveProp非OK一概当正常结束，并在NextOccurrence为NULL时不检查终止状态。

使用已有双重复层次、中文/特殊字符/换行覆盖的私有设计副本，冻结修改前读取器与源hash。私有故障代理在真实Dbo迭代的第二次调用返回状态3969：属性故障仍返回24个节点但一处属性被截断；子节点故障仍成功返回14个节点，正常为24。两份旧错误输出和false报告原样保留。3969是明确注入的状态，不宣称该副本自身发生原生损坏，也不将其他3969故障归因为本缺陷。

## 修复与边界

- 有效属性迭代只接受既有正常结束1022，其他非OK状态失败；children迭代NULL之后检查状态，仅成功或既有1022结束被接受。
- 创建迭代器同时检查状态和NULL；所有遍历/属性迭代仍释放迭代器。失败不写JSON，不进入Python会话的已验证层次快照。
- 原生与Python两侧限制路径16384字符、reference/属性名256字符、属性值16384字符，以及原生文本UTF-8总量8MiB；保留64层/10000对象/每对象512属性/总100000属性和32MiB输出边界。超限报错，不截断成功。
- Python对异常编码也返回结构化invalid_worker_result。接口schema、根属性预拒绝和occurrence连接声明不变。

## 验收

同一冻结源与同一故障声明：修正后两种故障均exit1，诊断分别unexpected_effective_end_3969和unexpected_child_end_3969，无结果JSON。正常新进程的24节点完整文档与修改前逐字段相等，源和副本hash均保持。

真实stdio MCP复验重复子模块属性隔离、定义继承分层、重复读取、独立重开、源变更及关闭会话拒绝全部通过。新增5项文本/字节预算边界测试；完整回归500项，499通过、1原文件符号链接权限skip。合同hash与第79批一致。

证据：`.local/hierarchy-iterator-integrity-20261025/`（修改前后冻结adapter/源/错误输出/日志/报告/差异审计）；`.local/hierarchy-integrity-mcp-20261025/report.json`；`.local/regression-500-hierarchy-integrity-20261025.txt`。探针tools/probe_hierarchy_iterator_integrity.py和tools/hierarchy_iterator_fault.tcl接受显式路径；故障代理仅在私有测试入口使用，不加入服务能力或任意Tcl入口。

H01仍deferred：root属性读取访问违规、真实空/循环层次与完整资源/继承来源条件未全部验收。本批只结案“迭代错误被当成成功”的已复现缺陷。34项仍6 passed/1 baseline/9 partial/16 deferred/2 planned，目标active。无GUI，无安装/真实设计修改，无提交推送。

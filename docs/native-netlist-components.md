# 原生网表任务的项目快照与完成回执组件

第105批完成内部组件并通过真实Capture验收；尚未注册新的MCP工具。实际工具数仍204。持久任务账本、宿主互斥/未决调用围栏、取消/恢复和完整业务工具接入仍需按设计08继续实施，原V04/P05不提升为完整通过。

## 项目快照

`capture_pspice_project.py`解析有界OPJ结构与原生SIM的General字段，绑定唯一同目录/同名DSN、唯一活动profile、根schematic、NET/ALS/CIR名称与路径。定义会话中的DSN快照是实际输入；旧OPJ模板所指设计不替代修改后的快照。项目/profile从授权read roots读取，DSN只能来自已注册工作区；每个来源均冻结hash，暂存前后复验。

当前支持范围标为`same_directory_design_single_profile@1`。未知节点/文件角色、额外库/刺激/include资源、歧义、错误profile/root、绝对/UNC/越界/保留名、非法编码和超限均拒绝。该解析器不是完整OPJ校验器，也不认证任意层次设计/模型依赖闭包；这些原范围要求保持未通过。

原OPJ含GlobalState中的绝对旧设计恢复路径。任务副本仅移除这段UI恢复信息，并按UTF8输出；原资源和仿真配置字节保持，原文件不改。GlobalState外出现界面路径/恢复节点也会拒绝，不把未知绝对路径原样带入任务。无现有任务目录合并或覆盖。此项不证明旧工程升级窗口已修复，未为此打开GUI工程。

## 固定原生后端

`adapters/capture_pspice_netlist_job.tcl`只接受可信包装器提供的数据参数：预期PID、活动设计、输入、输出、任务号和固定DLL。PID/活动路径及输出/开始标记检查在原生调用之前。进入标记独占创建；同一任务再次调用明确返回already_dispatched。没有任意Tcl/eval的MCP入口。

原生返回回执包含PID、任务号、是否返回、阶段、原生返回值和四类日志。每类最多1000行，每行4096字符，日志合计最多131072字符；读取失败或超限保留readable=false，不能当成空错误日志。调用失败也生成可诊断回执，不重放。

`capture_pspice_receipt.py`严格核对字段、类型、预期PID/32位十六进制任务号、阶段returned、原生返回字符串1、空error及四类完整日志；错误日志非空或不可读取均拒绝。布尔PID、其他任务回执、缺/重复日志类别和过大内容不能认证成功。返回值只证明这一固定原生调用的受限完成条件；NET/ALS的文件来源、内容和完整任务验证仍由后续任务层承担。转发器退出码不提供完成证明。

## 验收

- 新23项主机/真实Tcl边界测试通过，涵盖解析/暂存/源改变/闭会话、未知恢复路径、错PID、实际同任务拒绝、原生返回0、日志不可读/行超限/总量超限和回执身份。
- 真实Capture PID5256中，任务副本省略GlobalState后仍生成与第104批独立审计完全同字节的NET/ALS，原1kΩ参数、14引脚映射保持。源DSN/OPJ/profile、任务中的暂存输入、活动绑定和源文件保持不变。
- 再次派发同一任务，额外宿主回执明确记录already_dispatched；原网表、别名、进入标记和完成回执全部不变。这与仅观察文件未变化分开记录。
- 三个新目录验证内部/参数化/最终代码；首个版本只证明重复后的文件不变，后续版本补充真实拒绝确认，原记录保留。
- 最终完整回归618项：617通过、1项原文件符号链接权限跳过；现有204个工具/契约保持。alpha.1未改，原34项仍6完整通过17.6%。

复现：`tools/smoke_native_netlist_components.py --help`。参数为全新workspace root、既有私有source root、安装根、已有认证binding、先前独立验收的expected NET和ALS。脚本校验Capture进程/可执行文件指纹，只生成私有工程副本，不切换GUI；原始设计、认证文件和原生输出不提交Git。

下一步把这三个组件接入持久NET/ALS任务，特别处理原生已派发但回执未到的状态：不得杀Capture、不得把转发器结束当作调用结束、不得解除未决围栏后重复派发。之后完成独立profile/CIR任务，再从正式MCP重跑原P05。日志容器所有权/资源释放、任意工程兼容矩阵及原模型/层次等完整范围不由本批窄验收代替。

## 2026-10-27 MCP任务可用范围

已注册五个固定任务工具：`capture_plan_pspice_netlist`、`capture_apply_pspice_netlist`、`capture_pspice_netlist_jobs`、`capture_cancel_pspice_netlist`、`capture_recover_pspice_netlist`。plan显式要求定义sessionId、认证guiSessionId、sourceProject、sourceProfile；只支持same_directory_design_single_profile@1已声明角色。apply生成新副本NET/ALS，结果携带manifest及原生完成/宿主保持证明，不声明模型闭包、DRC或求解成功。

真实原生及MCP验收包括：NET/ALS与写前冻结预期一致；源/活动宿主保持；派发前取消；真实原生完成后注入观察丢失；未决围栏拒绝新计划；新服务仅核验回执/既有产物恢复；新服务幂等。首次MCP产物响应缺字段失败已保留，并在修复后只读恢复旧任务，全部任务文件保持。实际工具数209，契约由真实服务生成。复现工具`tools/smoke_native_netlist_service.py`、`tools/smoke_native_netlist_mcp.py`接受workspace-root/source-root/binding/install-root/expected-netlist/expected-aliases参数；认证binding仅本机保存。

原5256宿主的ORCAP-1356失败没有被重跑或改成功，旧围栏仍在旧绑定目录；经核对专用副本与程序指纹后结束故障进程，新宿主/新绑定/新任务单独验收。内存错误原因未确认。此恢复不能被描述为支持任意正在运行的Capture调用取消。正式profile→CIR任务及完整V04/P05仍未通过；见`docs/implementation/batch-107-evidence.json`。

# 原生仿真输入的库配置与别名链

本批验证的是显式私有配置下的 LowPassFilters RC/RL 流程：之前认证 Capture 生成的 NET/ALS → 原生 profile 生成 CIR → MCP准备引用闭包 → 官方CLI → OUT/DAT与四个独立复数采样点。原默认nom.lib的215文件加密闭包仍被拒绝，未删改原CIR或库引用；本案例不能替代它，也未完成电阻参数迭代P05。

## 两项实际发现

`CorSimSrvr_setIniFile(self, cmdline)`虽然参数名为cmdline，实测接收的是准确INI文件路径。传入`-i <路径>`时会把整串当作文件名，新CIR没有期望库，实验失败。直接写m_iniFile成员则因pathstring类型拒绝。使用准确路径生成的CIR中出现指定的原创模型库，私有INI和全局INI均保持原字节。这里不修改用户全局库配置，不把SDK命令存在等同于已支持业务接口。

原生NET生成还会产生同源ALS。旧诊断链只复制NET，profile仍生成`V(alias(*))`等保存选择，因此CLI返回0、OUT有JOB CONCLUDED，但出现ORPSIM-16527且没有DAT。修复后服务返回`pspice_no_saved_traces`；一般缺DAT返回`incomplete_simulation_output`，不再表现为路径不存在。原生error仍优先，warning本身没有升级成解析器error；已有DAT时继续原本的数据与来源校验。

只把ALS放到工程目录并不会让当前CorSimSrvr生成器自动引用。新的显式私有INI同时列出原创未使用模型库及`.INC "..\LPFilters.als"`，由原生生成器写进新CIR；保持原生PROBE、AC设置和NET数值不变。ALS已与生成前冻结的DSN表逐项比较：7器件14引脚，错误节点、反接电源、漏器件和重复器件负例均拒绝。

长绝对路径INC会被原生格式化为路径字符串加下一物理行的`+ "文件名"`。此前连续单行的预期失败已保留；这类折行引用的通用准备仍未验收。本批正例使用明确的工程相对路径，不声明已修复通用折行解析。

## 验收结果与复现

两套全新私有目录真实MCP均通过：AC LIN100点0.1至200Hz，RC500Ω/1kΩ/7uF及RL2H/1kΩ，两个节点首尾共四个复数值符合求解前计算的原预期和原容差。准备闭包4文件：CIR、NET、ALS、原创库。OUT无error，DAT任务归属及数值核对通过；源DSN/profile/NET/ALS、全局INI保持不变。没有桌面操作。

原无DAT失败任务经新服务器只执行recover和inspect_failure，明确返回未保存信号；原worker已停止，所有已有任务文件字节保持不变，没有重放CLI。三项新增针对性测试及完整595项回归：594通过，1原文件符号链接权限跳过。

可公开复现脚本为：

- `tools/probe_private_lowpass_profile.py`：需要`--install-root --workspace-root --source-root --native-netlist-root --global-ini`。只适用于已审计LowPassFilters本机私有副本，生成独立INI、原创库及原生CIR；不是通用MCP工程创建工具。
- `tools/audit_scalar_native_aliases.py`：需要`--workspace-root --oracle --native-aliases --copied-aliases`，核对冻结表及四类负例。
- `tools/smoke_private_lowpass_ac.py`：需要`--install-root --workspace-root --source-circuit --read-root`，实际MCP/CLI复核四点数值与OUT/DAT归属。

官方依据是本机pspDB/pspice.tcl的profile JSON流程、参考手册ALIASES定义与配置文件说明。setIniFile的字面路径语义由实际生成文件证明，不能直接套用参考手册PSpice进程的`-i`语法。官方文件不上传，只保存指纹。仍需正式化原生输入业务工具、完成DSN参数修改→新NET/ALS→新CIR→新数值、证明旧结果不能复用，并处理原默认模型闭包和折行引用。

## 2026-10-27 固定业务脚本

`src/cadence_mcp/adapters/profile_circuit_job.tcl`封装原已验证的CorSimSrvr序列：加载DLL、构造、绑定私有INI、loadProfile、readSettingsLibinc、updateCirFileI、清理。输入是固定参数，不提供任意Tcl入口。要求三项原生返回0、实际CIR路径与计划相同且非空；已有CIR或回执在构造前拒绝，清理异常不能报告成功。回执含本轮nonce/PID，原子发布；INI选择仍须由生成CIR内容独立核对，opaque getter不作证明。

`tools/probe_private_lowpass_profile.py`现在调用此固定适配器；`tools/prepare_lowpass_iteration_inputs.py`在全新目录完成参数前后两次原生生成。新产物经`tools/smoke_lowpass_parameter_cycle.py`真实MCP/CLI验证原冻结的四点复数预期和旧DAT拒绝；RC低频实部0.6666652337494039→0.4999975819586156，源与全局INI保持。

`tools/smoke_profile_circuit_replay.py --accepted-root <前后原生输入目录> --workspace-root <新的验收目录> --install-root <安装目录>`在原生解释器重新调用固定脚本，要求明确preexisting_profile_output回执及已验收文件树完全保持；不以退出1单独作为拒绝证明。第一轮仅退出码/文件保持证据保留，第二轮补齐原因回执。新增3项Tcl负例检查；最终627项回归626通过、1原权限skip。证据见`docs/implementation/batch-106-evidence.json`。

这是固定脚本的提取与原生验收，尚未注册profile→CIR的持久MCP任务，不代表原默认模型闭包、通用工程生成或完整V04/P05通过。

## 2026-10-27 profile→CIR的MCP入口

第108批已注册并原生/MCP验收以下六个工具，当前开发契约共215工具；前面的“尚未注册”是第106批当时状态。

- `pspice_plan_profile_circuit(netlistPlanId, netlistPlanDigest, libraryPaths, includeAliases, expectedDirectives, inputBudget)`：只消费已验收NET/ALS任务；模型库路径必须属于配置的read roots，调用者显式声明库及别名包含配置。`expectedDirectives`至少包含一条独立声明的OP/DC/AC/TRAN指令，也可约束PROBE/OPTIONS行。`inputBudget`为standard或extended，并保持到输出准备阶段。
- `pspice_apply_profile_circuit(planId, planDigest, idempotencyKey)`：固定CorSimSrvr脚本在新副本生成CIR；核对原生回执、准确路径、配置引用、模型重定位及声明指令。尚未求解。
- `pspice_profile_circuit_jobs`、`pspice_cancel_profile_circuit`、`pspice_recover_profile_circuit`：任务列表、取消自有工作进程、验证既有输出而不重生成。DLL加载后注入等待的取消/超时已验收；不外推为已测updateCirFileI内部取消。
- `pspice_prepare_profile_circuit(planId, planDigest)`：由已验收CIR创建现有CLI流程可用的simulationId，仅授权该任务已验证目录给引用解析器，不开放任意工作区路径。

两层原创模型库已通过实际MCP/CLI的5文件闭包与原冻结复数值。完整500Ω→1kΩ参数场景也已由公开MCP完成属性修改、NET/ALS、CIR、CLI及DAT，旧DAT启动前拒绝、新服务器七个写任务幂等通过。复现脚本为`tools/smoke_profile_circuit_service.py`、`tools/smoke_profile_circuit_mcp.py`、`tools/smoke_profile_circuit_faults.py`及`tools/smoke_full_parameter_mcp.py`，各脚本`--help`列出本机私有输入要求；不发布官方工程文件或认证绑定。

当前配置模式为显式库；未实现继承全局nominal配置的完整来源证明，原加密模型闭包失败保持。未宣称完整profile语义、所有DAT或整体V04/P05通过。验收/失败指纹及最终634项回归见`docs/implementation/batch-108-evidence.json`。

## 2026-10-27 原INI的全局库选择

现有`pspice_plan_profile_circuit`增加可选`configurationIni`。使用时`libraryPaths=[]`，明确选定有读取权限的INI，并将其库目录纳入read roots；`inputBudget="extended"`用于原默认大型闭包。工具数仍215。

这个模式复制完整INI原字节，在专用子进程里调用原生loadProfile、readSettingsLibinc、readSettingsToJSON，核对合并前后ConfigFiles。只支持没有profile/local/include/stimulus覆盖、一个原生解析库搜索目录的global LIB选择。严格核对INI字面库列表与原生启用列表/顺序，不能从空的未合并列表推断没有全局库。无关的`[]`节原样保留；相关PSPICE NETLIST段重复/歧义仍拒绝。

原`nom.lib`的213模型文件、34,548,882字节已完整冻结；实际MCP生成CIR并准备为216文件闭包（模型、CIR、NET、ALS），新服务器apply/recover不重生成且所有任务文件保持。原INI、原模型文件未修改。INI快照、原生合并结果及来源证明绑定最终产物，计划后改INI或篡改证明会拒绝执行。

这证明了原全局库选择与生成来源；不证明全部INI配置、覆盖搜索语义或加密模型可执行。原`unsupported_embedded_reference`仍在CLI计划前拒绝，未启动求解器，也未删库/更换为小库。复现使用`tools/probe_native_profile_configuration.py`、`tools/smoke_inherited_profile_circuit.py`、`tools/smoke_inherited_profile_mcp.py`；详细指纹见`docs/implementation/batch-109-evidence.json`。

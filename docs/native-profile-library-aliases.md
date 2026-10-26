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

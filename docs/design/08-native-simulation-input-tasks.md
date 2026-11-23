# 原生仿真输入任务实施契约

状态：2026-10-27，第108批已注册并原生/MCP验收五个Capture NET/ALS任务、五个PSpice profile→CIR任务及一个已验收CIR准备入口，实际工具数215。当前profile任务支持显式库配置及声明指令验收；继承配置、原始完整V04/P05仍未通过。沿用统一MCP Server、Capture/PSpice内部模块、现有任务账本与来源检查，不开放任意Tcl/eval或外部命令。

## 证据与分层

同一认证Capture宿主可以为不同完整私有项目副本生成NET/ALS，保持活动工程及源文件不变；只有裸DSN时ORNET1165。原生CorSimSrvr可从明确profile/INI和NET/ALS生成CIR。P05实际Value修改、两次原生生成、四文件闭包、两次MCP求解、新电压及旧DAT拒绝已验收，但两段原生生成目前是受控开发脚本。

原生NET/ALS与profile→CIR分别成为持久任务阶段。如此导出发生观察超时但晚到回执有效时，recover只核验原有NET/ALS；随后可创建CIR任务，不必重复导出。不得把Capture.exe转发器返回0或进程已结束当作宿主内业务完成。

## Capture内部模块

拟新增capture_plan_pspice_netlist、capture_apply_pspice_netlist、capture_pspice_netlist_jobs、capture_cancel_pspice_netlist、capture_recover_pspice_netlist。名称需在注册前检查冲突；复用通用结构化结果和任务生命周期。

plan以定义sessionId绑定不可变DSN，以guiSessionId绑定已认证宿主、PID、绑定身份和代次；明确sourceProject、profile及项目中待替换设计入口。OPJ/profile须经read roots授权，解析出唯一匹配的设计/根schematic/profile，拒绝歧义、越界和未支持引用，不从窗口标题推断。将选定DSN快照放到任务中的正确项目文件名，保留原项目/DSN/profile名关系，固定根目录，所有输入hash纳入planDigest。模板OPJ与所用DSN快照是不同角色，来源均记录，不要求已编辑DSN与旧模板DSN字节相同。

apply先取得宿主级互斥，确认无未决GUI写入、活动身份/源hash/干净状态正确，然后用固定、一次性替换数据字面量的PID绑定脚本派发。输出路径只能属于该新任务，派发前无NET/ALS/回执。不得切换/打开真实GUI工程，不得写原项目、安装目录或全局配置。任何开始后异常保留账本并禁止重放。

verify要求真实宿主PID/任务nonce/返回回执、返回值1、错误日志为空、NET/ALS非空且关闭后可读；核对输入、源工程/源DSN/活动绑定保持及输出来源。副产品PRP是否纳入支持须另行明确，不能从本批只使用NET/ALS推断不产生其他文件。输出只公开结构化相对artifact、hash、大小、源revision和范围，不公开认证数据。

cancel只可保证尚未派发时不执行。已在Capture宿主内开始的调用不得通过终止Capture或只杀转发器伪称取消；返回too_late/待观察，并保留真实状态。recover只读核验晚到回执和现有文件，绝不再次派发。若PID/实例/代次已变，不能偷偷重新绑定。

## PSpice内部模块

拟新增pspice_plan_profile_circuit及对应apply/jobs/cancel/recover任务，消费已验证的NET/ALS artifact、明确profile及库/包含配置。所有profile、INI、NET、ALS和模型来源均冻结。CorSimSrvr运行在独立受控进程，构造、loadProfile、readSettingsLibinc、updateCirFileI、delete清理按已验证序列执行，生成目录预先创建且没有旧CIR。

CorSimSrvr_setIniFile传准确路径，不传PSpice进程-i选项。显式配置与继承配置必须区分，不能默默移除nom.lib或改为任意默认库。先实现本批明确配置，继承模式仍需完整来源和原215文件门禁；不据此缩减原V04目标。ALS是否需要引用由保存波形配置明确表达，本批alias(*)实例必须纳入；没有ALS不能报告可用波形链。

verify将CIR分析设置、PROBE选择和所有LIB/INC与源profile/配置/已验收NET及ALS核对。当前原生长路径折行INC未被通用解析接受，继续保留原失败；不得规范化重写后假称原生成CIR通过。明确支持的工程相对引用可先通过，界限在capabilities/结果中公开。

后续提供由验证artifact创建现有pspice_prepare会话的定型入口。内部仅扩展到已验证任务目录的读取，不让用户任意传workspace路径绕过read roots；来源复验通过后再进入现有固定CLI计划/求解与DAT流程。生成成功不等于模型闭包或求解成功。

## 验收顺序

先做项目角色/路径/指纹解析与计划拒绝，再做真实认证宿主NET/ALS任务及生命周期，随后profile/CIR任务，最后用现有property和CLI工具重跑完整P05。必须包含：缺OPJ/错误profile/root、多个同名入口、旧revision、源/输入/输出篡改、预存NET/ALS/CIR、错PID/活动项目、并发写入、派发前取消、转发超时与晚到回执、新服务器恢复/幂等，以及旧DAT拒绝。真实业务没有支持的边界明确未验收，不能用mock替代宿主完成证据。

本设计不把任何原34项提前标为passed。实际工具契约只在功能实现并受影响验收通过后从运行服务生成更新，固定alpha.1不变。

第108批实现/验收详见docs/implementation/batch-108-evidence.json（从仓库根解析）。原文“拟新增”描述保留设计顺序；实际工具以contracts/tools.v0.1.json为准。

第109批：现有profile计划工具可选configurationIni，支持经过原生合并核对的一目录纯global LIB选择，INI字节与配置证明绑定产物。原nom.lib213模型/34,548,882字节和216文件准备闭包通过实际MCP；完整覆盖配置和加密求解仍未通过。见docs/implementation/batch-109-evidence.json。


## 引擎 LIB 引用路径策略（批次164）

新独立引擎计划冻结 `libraryReferenceMode=job_relative_v1`：执行副本内的 `.LIB` 指向生成的 `deps/file-NNN.ext`，受控进程工作目录固定为该任务目录。原生对照确认嵌套 LIB 可按此查找；模型使用证明将相对引用绑定到该目录并核对精确闭包。INC/INCLUDE 的现有绝对规则不变。

旧计划缺少该字段时按 `absolute_v1` 还原原字节，以维持原指纹和只验证恢复。CLI 新计划显式冻结 `absolute_v1`，尚未验收 CLI 的相对策略。所有源输入和准备清单保持不变，仅新执行副本采用计划指定规则。原折行及普通嵌套 LIB 的 2.5V 原预期已通过；较长绝对引用仍可使原生初始化退出，本次未确定精确边界。

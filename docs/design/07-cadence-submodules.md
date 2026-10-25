# Cadence 子模块实施清单

日期：2026-10-23。按用户最新优先级，先开发并验收 Cadence 业务子模块，Skills、规范引擎和交付整合暂缓；已有规范和检查可继续作为开发约束。暂不考虑 Allegro，PDF 自动打印继续延期。正常操作走 MCP/CLI/Tcl/Dbo。

## 资料位置

|用途|已核实的本机位置|
|---|---|
|安装根|`D:/Program Files/Cadence/SPB_24.1`|
|Capture Tcl/Dbo 主参考|`tools/capture/tclscripts/OrCAD_Capture_TclTk_Extensions.pdf`（安装根下）|
|对象模型|`doc/capinfomodel/dboimnew.html`|
|Capture Tcl 解决方案/GUI示例|`doc/orctclcap/`、`doc/orctclsample/`|
|Capture Tcl 官方脚本和样例|`tools/capture/tclscripts/`、`tools/capture/samples/`|
|PSpice 非交互执行说明|`doc/cap_ug/Running_PSpice_in_Batch_Mode.html`|
|PSpice Tcl/数据参考与示例|`doc/psptclcmdref/`、`doc/psptclsample/`、`tools/pspice/tclscripts/`|
|实际解释器/数据库/CLI|`tcltk/bin/tclsh.exe`、`tools/bin/orDb_Dll_Tcl64.dll`、`tools/bin/psp_cmd.exe`|
|参考旧仓库|`D:/workspace/git/cadence-mcp-public`；仅参考任务拆分，许可受限代码不搬入新仓库|
|现开发仓库|`D:/workspace/git/cadence-mcp`|
|早期核查与证据|开发仓库 `docs/design/01-local-findings.md`、`docs/design/evidence/`；原工作目录 `design-plan/evidence/`、`repo-audit/`|
|按类检索接口的辅助索引|`C:/Users/lenovo/.codex/skills/cadence-capture-tcl/references/api-catalog.jsonl`；索引必须回到官方资料和当前运行时核对|

主参考包含第三方版权内容，不复制全文或二进制进公开仓库。文档与索引是依据，不是运行通过证据。

## 子模块与完成条件

|执行顺序|子模块|当前状态与完成条件|
|---|---|---|
|C0|会话与桥接|本机单Capture基础已验收；沿用现有链路，保留双实例未验收和文件符号链接权限待补测边界。|
|C1|Capture查询|已有定义/页面/器件/引脚、快照、导线几何；本批新增按partId读取有效属性。后续补姿态/热点/显示文字与边界，明确定义与occurrence属性区别。|
|C2|属性编辑与位号|先Value等批准字段与PCB Footprint名称，再位号映射。每类执行计划、前置条件、幂等、保存、独立重开与预期连接检查；多单元/已有位号冲突单独验收。已具备受限字段、metadata、显示属性与single-unit位号任务；多unit编号及完整属性显示范围仍待验收。|
|C3|库与缓存|OLB查询、package/device/cell/part/物理引脚模型；用户库副本创建/编辑/保存重开，区分OLB源和DSN缓存，再做缓存更新。已具备库查询、声明创建、引脚编辑、共享脚/替代视图及缓存查询；缓存替换覆盖保持、封装变体与复杂图形仍待完成。|
|C4|放置与布线|器件放置/移动/旋转/镜像，导线/alias/global/NC，保持真实热点和姿态；每个动作有保存重开和独立预期节点表。已有受限放置/布线/标量标签/NC任务，现增加完整同封装共享位号组；单个unit姿态/删除已有受限验证；接线移动仍失败，缺失unit同页缓存补放已有B/P正例及持久任务；跨页、接线移动及完整复杂范围仍待完成。|
|C5|层次与连接|跨页、层次重复实例、总线/Bundle；以occurrence路径和原生网络身份防误合并，配独立预期连接和故障fixture。当前只有定义级读取与局部观察值比对。|
|C6|原生检查与仿真输入|认证接口内执行原生DRC、解析本次报告；生成可追踪的PSpice输入及模型闭包。GUI手工DRC历史结果不等于MCP业务完成。PDF延期。|
|P1|PSpice输入与执行|手工CIR先行，固定任务输出目录、引用闭包、进程树、取消/超时与诊断；DC/瞬态/AC数值和失败样例通过后开放MCP。已有独立引擎及官方非交互CLI的DC/AC/瞬态、持久任务与故障切片验收；真实许可证失败与完整端到端门禁仍未通过。|
|P2|PSpice结果|P03原门禁已通过：OUT错误诊断、原生测量、DC/RC/AC解析数值及可追踪单位推断/unknown，见第78批。DAT数字/格式边界P04与Capture端到端P05仍未通过；不由CLI成功推断高级分析或全测量语法支持。|

先完成各子模块的首个完整可用闭环，再逐项增加复杂能力；不要求一次包装全部Dbo声明。接口明确标记未实现/未验收，不能通过增加空模块宣称完成。模块内部可细分文件，对外仍通过一个MCP Server的定型任务工具。

每个子模块的完成标志是：实际实现 + 工具契约 + 正反/故障样例 + 本机端到端记录 + 范围说明。测试只用自建fixture或明确授权的样例副本，不改安装与真实工程，不自动提交或推送。


2026-10-23 用户授权自主完成开发与验收，计划见docs/implementation/cadence-plan.md（从仓库根解析）；验收失败保留证据并移到队尾，继续独立项，最后集中修复。只有全部必需功能验收通过才结束目标并交用户评审，不自动提交推送。

2026-10-24：原34项详细状态与证据以docs/implementation/cadence-acceptance.json为主档；本表保留完成条件，不用工具数或回归通过率代替业务完成率。

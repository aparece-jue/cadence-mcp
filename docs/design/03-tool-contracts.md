# 工具与数据契约 v0.1

以下为新服务设计。`cadence-mcp-public` 的 TCP 命令没有被当成现有 MCP schema。首批契约使用显式工具名和限定 operation，不提供 execute_tcl、shell 或任意 DLL 加载工具。

## 1. 通用约定

JSON 对象拒绝未声明字段；路径必须在注册的工作区/只读依赖根内，解析 junction、符号链接和最终绝对路径后再检查，输出禁止覆盖已有文件，除非契约明确说明。请求参数中不接受安装根写入目标。`schemaVersion=1.0` 表示本应用契约版本，不代表 MCP 协议版本。

sessionId/workspaceId/planId/jobId/artifactId 是 opaque ID；不要用当前选中对象、窗口标题或位号字符串代替身份。ObjectRef 包含 session generation、设计定义 ID、页面 ID、对象 ID 和可选 occurrencePath；位号/引脚号只作显示和交叉核对。引脚定位同时核对 package、unit 与物理 pin，避免多单元误选。

几何坐标使用 Capture 原生绘图整数单位，并附 units、grid 和页面坐标约定，不能默认为 mm。电气值使用字符串及解析后量纲，避免把 1m、1M、MEG 当成同一值。模拟结果携带单位、分析类型、block、参数值和 x 轴信息。

所有成功/失败都附来源和覆盖范围。`complete=false` 时，未遍历部分不能当成空结果。层次循环、对象上限、超时必须使 complete=false，并列出原因和遗漏范围。

## 2. 工具目录与输入输出

缩写：W=workspaceId，S=sessionId，J=jobId；这里的必填字段之外，公共调用 envelope 见后文。P0 为首版，P1/P2 为后续能力，发布时只声明实际可用项。

|工具|输入必填 / 可选|输出核心|副作用 / 阶段|
|---|---|---|---|
|cadence_get_environment|installRoot?，probeLevel=files/runtime|解释器/EXE/DLL、hash、版本、探测结果|只读；runtime 可创建探测进程，P0|
|cadence_get_capabilities|installId，sessionId?|能力 ID、backend、证据等级、限制及 unavailable 原因|只读，P0|
|cadence_create_workspace|sourceProject，destinationRoot，dependencyPolicy；sourceProject 可为 null 表示新建|W、副本路径、输入 hash、依赖清单、遗漏和只读根|写新目录；不改源，P0|
|capture_open|W，designRelativePath，backend=standalone/gui；gui 需 instanceId|S、generation、设计 fingerprint、dirty、可用能力|打开副本；不自动保存/升级源，P0|
|capture_close|S，disposition=discard/save_verified|状态及输出物；save_verified 需已通过持久化流程|释放自建 session；GUI 不删除 Capture 所有的会话，P0|
|capture_query|S，scope，entity，fields；filter?，cursor?，limit?|items、nextCursor、complete、revision、coverage|只读，P0|
|capture_snapshot|S，scope，include=结构/节点/属性/几何|snapshotId、revision、节点表 artifact、coverage|写快照文件，P0|
|capture_plan_change|S，baseSnapshotId，operations，standardsProfile|planId、digest、目标/前后值、预期网络增删、检查与阻断项|只计算计划，P0 先支持属性/位号，布局布线 P1|
|capture_apply_plan|planId，planDigest，idempotencyKey|J；终态带逐项结果、保存与重开验证|只写计划绑定副本，P0/P1|
|capture_validate|S，checks，expectedConnectivityArtifact?，standardsProfile?|J 或同步报告；各检查 pass/fail/skipped/unavailable|连接比对 P0；原生 DRC、图面 P1|
|capture_export|S，format=pdf/pspice_input，scope，destinationRelativePath，options|J、artifact manifest、来源工程/页 hash|写导出；GUI 能力依赖，P1|
|pspice_prepare|W，source={kind:cir/artifact,cirPath/artifactId}，analyses，parameters，modelRoots|preparedInputId、stage manifest、输入 fingerprint、依赖与诊断|复制/生成 job 输入，不编辑真实 SIM/DSN，P0|
|pspice_run|preparedInputId，backend=cli/engine_tcl，timeoutSeconds，idempotencyKey|J、进程/许可证/运行状态|运行仿真并写 job 文件；CLI P0，引擎 Tcl P2|
|pspice_get_result|J，include=summary/measurements/diagnostics|数值/单位、求解状态、错误、artifacts、完整性|只读结果，P0|
|pspice_export_trace|J，blockId，traceExpressions，xRange?，sampling，destinationRelativePath|CSV/JSON artifact、单位、点数、复数表示和降采样说明|DAT 适配器验证后启用，P1|
|standards_resolve|W，profileId，context|合并后的规则、版本/hash、来源链、冲突|只读，P0|
|standards_check|snapshotId 或 J（二选一），resolvedProfileId，ruleIds?|findings、coverage、人工待审项、豁免项|写检查报告，P0/P1|
|cadence_get_job|J，afterSequence?，maxEvents?|状态、进度事件、结果/错误、输出物|只读，P0|
|cadence_cancel_job|J，reason|cancel_requested 或终态；实际停止情况|仅管理本服务任务；不能保证回滚，P0|

sourceProject 指已明确选择的工程入口，不允许自动扫描全盘并复制。dependencyPolicy 枚举 `strict/allow_readonly_roots`；无法解析的动态依赖必须显式列出。`strict` 下缺依赖不得进入运行。创建副本的 manifest 必须保留重定位映射与原文件 hash。

scope 为判别联合：`{kind:"design"}`、`{kind:"page",schematicId,pageId}`、`{kind:"selection",selectionSnapshotId}`、`{kind:"occurrence",occurrencePath}`。selection 先冻结 ID 和 generation，不能运行时重新取当前选择。entity 枚举 schematic/page/part/pin/wire/net/property/library_part。query 分页游标绑定 revision，变化后返回 stale_cursor。

P0 plan operation：`set_property`、`rename_reference`；P1 增加 `place_part`、`move_part`、`add_wire`、`place_alias`、`place_global`、`place_noconnect`。每种有独立 schema 和 validator；首版不接受任意 method 字符串。删除、缓存刷新、层次重构、复杂库编辑待专用契约完善后启用。

举例：rename_reference 用精确 ObjectRef 和 expectedOldRef/newRef；对 R1/R2 交换先预检全设计唯一性，再分配临时唯一号后赋最终号。不得把操作顺序依赖转嫁给 AI，也不得依据 U1* 选目标。

## 3. 返回 envelope

```json
{
  "schemaVersion": "1.0",
  "requestId": "r-0001",
  "status": "succeeded",
  "data": {"sessionId": "s-1", "generation": 1},
  "diagnostics": [],
  "artifacts": [],
  "evidence": {
    "level": "runtime_probed",
    "backend": "capture_dbo",
    "complete": true,
    "coverage": ["command_registration"],
    "notChecked": ["design_read", "save_reopen"]
  },
  "error": null
}
```

status 枚举 succeeded/accepted/partial/failed/indeterminate。长任务先 accepted，data 为 jobId；最终用 cadence_get_job 获取。业务失败必须设 MCP 工具错误标识并提供结构化 error，不能 HTTP/TCP 成功就报告设计成功；具体 MCP SDK 对应字段在实现时适配。无效协议/未知工具作为协议错误，设计操作失败作为工具执行结果。

partial 意味部分完成且已知哪些项成功；indeterminate 意味无法确定实际执行状态。写入失败默认不自动发布部分输出。查询 partial 必须 complete=false；未执行的检查标记 skipped/unavailable，不能归为 pass。

Artifact：artifactId、kind、workspaceRelativePath、sha256、size、producedByJob、sourceFingerprint、createdAt、validationState。下载/打开路径由服务映射，不能允许 AI 用 artifactId 拼任意绝对路径。日志和诊断默认避免输出许可证地址、token 与完整电路内容。

## 4. Plan 与验证

```json
{
  "sessionId": "s-1",
  "baseSnapshotId": "snap-7",
  "standardsProfile": "project-default@0.1.0",
  "operations": [{
    "type": "rename_reference",
    "target": {"objectId": "obj-42", "generation": 1, "pageId": "page-1"},
    "expectedOldRef": "R1",
    "newRef": "R101"
  }]
}
```

plan 内部保存 base 文件 hash、dirty epoch、对象存在性、原值、规则 hash 和预期网络表 hash。digest 只在 canonical JSON 及固定算法下计算。apply 要求 digest 一致、plan 未过期、会话 generation 和 revision 一致；同一幂等键不同参数返回 conflict。

验证输出分别记录 `appliedInMemory`、`saved`、`reopened`、`connectivityMatched`、`nativeDrc`、`visualReview`。例如布局整理预期网络增删均为空；电气变更须显式提供预期变化。不得从修改后快照重新生成“预期”并自证一致。

保存实现先以 Capture 技能的完整保存链作为候选：MarkModified → SavePage → SaveSchematic → MarkAllLibForSave → SaveDesign；每个实际签名和返回值以当前手册及测试为准。不能假定所有返回值都支持 Failed，也不能假定该链适合所有 DSN/OLB 对象。

## 5. 任务状态、取消和幂等

状态机：queued → running → succeeded/partial/failed/cancelled/indeterminate。cancel_requested 是控制请求的状态，不是已经取消的证据。排队任务可直接 cancelled；运行任务在安全边界停止，Dbo 调用不可中断时先等待；强制终止后需要重开验证，记 indeterminate。

服务端持久化 requestId、operation digest、idempotencyKey、状态和产物映射。重启后未完成写任务不自动重放，先标记需恢复；只读查询允许有限重试，写入和仿真统一依据账本避免重复。客户端停止等待不等于引擎已停止。

每个 job 限定墙钟超时、内存/输出量、进程树及日志大小；PSpice 初始化/许可证等待与求解时长分开记录，初始超时预算由本机测量校准，不能把本次 30 秒当作所有任务的正确上限。

## 6. 错误契约

error = code、message、phase、retryable、details、recoveryAction。details 必须是经过清理的数据，不附任意可执行建议。

|code|含义与恢复|
|---|---|
|installation_not_found / architecture_mismatch|文件未找到或位数不匹配；修正显式安装配置|
|capability_unavailable|当前版本/backend 未验证或缺少命令；列出适用 backend，不盲目降级|
|session_lost / target_changed|会话结束、活动设计或 generation 改变；重新绑定和快照|
|stale_plan / stale_cursor / idempotency_conflict|前置条件或调用身份冲突；重新计划或使用正确游标|
|path_denied / dependency_missing|越界或引用缺失；补依赖清单，不能自动扩大权限|
|object_not_found / ambiguous_target|定位失效或多对象匹配；重新查询精确身份|
|dbo_error / worker_crashed|分别记录 DboState 或进程异常；崩溃不能依赖 Tcl catch 捕获|
|save_failed / reopen_failed / connectivity_mismatch|不发布 validated 输出；保留副本和差异|
|license_unavailable|仅在日志/返回信息明确识别后使用；超时不能直接归此类|
|simulation_input_error / non_convergence|提供 OUT 位置及诊断；不能自动放宽容差掩盖问题|
|timeout / cancelled / state_indeterminate|标明是否已启动、可能写入、是否确认停止及恢复策略|
|rule_conflict / validation_failed|保留规则来源及失败项，不能简单忽略项目覆盖|

## 7. 内部桥接请求

```json
{
  "bridgeVersion": "1.0",
  "requestId": "r-0002",
  "sessionId": "s-1",
  "generation": 1,
  "operation": "capture.query",
  "deadlineUtc": "2026-10-22T10:00:00Z",
  "params": {"entity": "part", "scope": {"kind": "design"}, "limit": 100}
}
```

认证在握手阶段完成，不在每条审计日志重复 token。严格校验长度、UTF-8、JSON 类型、字段、operation 和 deadline。响应保持 requestId；禁止把参数拼进 Tcl source、eval 或 shell 文本。Tcl 使用 list/参数调用和 JSON 编解码器，不手工拼装 JSON。正式实现必须分别测试中文、反斜杠、换行、竖线、花括号、空数组和大结果。

`contracts.schema.json` 仅为公共 envelope、ObjectRef 和 P0 plan 的可运行结构草案，不是此表全部工具的完整 tools/list。P0 实施的第一项交付就是为每个发布工具补齐独立 inputSchema/outputSchema，并用此文档检查一致性。

## PDF 契约修订（2026-10-22）

`capture_export(format=pdf)` 是产物工具名称，不代表使用 Capture Export 菜单。规划默认 `options.pdfBackend=print`，通过 File → Print 与经过兼容性验证的 PDF 打印机生成；实际 GUI 自动化入口尚待 bridge 实现，不新增未核实的 Tcl Print 调用。

产物 manifest 应记录 backend、打印机/驱动、纸型/方向、缩放、实例/发生模式、预期和实际页清单、来源指纹、生成时间、文件指纹、逐页预期文字及查找结果、图面复核状态。仅文件存在或图面可读不能返回交付通过；缺失/乱码文字、页范围错误返回明确验证失败。目标阅读器的全局搜索与选择复制作为交付验收项单独记录，不能由文件落盘推断。

Export → PS → Ghostscript 只保留显式诊断用途，不自动回退。打印机、字体或 Cadence 版本改变后重新验证文本保留。PDF 网络名文字不代替原生网表数据。当前 7 个 MCP 工具不因此增加 PDF 能力。

### 打印机与文件路径参数（规划契约）

沿用 `capture_export` 的 `destinationRelativePath` 表示工作区输出目录与 PDF 文件名，避免再增加互相冲突的目录/名称字段；`options.printerName` 指定已安装且已验证的 PDF 打印机，不依赖系统默认打印机。示例仅表示规划参数，当前服务尚未注册此工具：

```json
{
  "sessionId": "s-1",
  "format": "pdf",
  "scope": {"kind": "design"},
  "destinationRelativePath": "deliverables/review/full-adder-v1.pdf",
  "options": {
    "pdfBackend": "print",
    "printerName": "Microsoft Print to PDF"
  }
}
```

服务将相对路径解析到已绑定工作区的允许输出根内，预检目录可写、扩展名和文件不存在；经校验后可创建工作区内缺失子目录。打印前后核对实际打印机和完整输出路径；打印机不存在或驱动未验证时明确失败，不自动切换到默认或实体打印机。保存对话框与生成文件均需核对，拒绝覆盖已有产物；后续自动实现应采用独立 job 暂存目录并安全发布，以处理并发和意外同名。可在部署配置中注册其他用户指定输出根，不接受未经注册的任意绝对目标路径。

GUI 层具备选择打印机、填写目录和文件名的操作途径；这不代表已有无对话框的 Capture Tcl Print API。全自动调用与窗口恢复仍是 GUI bridge 实施内容。

## 用户指定的 PDF 默认配置（2026-10-22）

- 打印机固定 `Microsoft Print to PDF`，方向固定横向，不隐式换用系统默认或实体打印机。
- 输出目录为工程入口文件所在目录下的 `pdf`，缺失则创建。工程入口优先采用明确绑定的 OPJ；只有单 DSN 时采用 DSN。不能用仓库名、窗口标题、临时重命名的 `design.dsn` 推断原工程名。
- 文件名为 `<工程名>_<版本号>.pdf`；未提供版本号时为 `<工程名>_YYYYMMDD_HHMMSS_ffffff.pdf`，时间戳采用带时区的当前本地时间并在 manifest 中记录时区。版本号不自动从不确定的设计属性推断。
- 拒绝非法文件名、路径越界和覆盖已有文件；输出只能位于已授权工作副本/输出根。初期保持不修改真实工程文件，pdf 子目录的创建和 PDF 写入也不能绕过输出授权。

`cadence_mcp.pdf_output.prepare_pdf_output` 已实现默认值、输出目录创建和命名预检，尚未接入 MCP 或 Capture 打印；最终打印任务仍需 job 暂存目录、安全发布与并发处理。调用层必须在绑定会话/来源 manifest 中确定工程身份，避免现有只读工作区统一命名 `design.dsn` 导致误命名。正式 job manifest 还应记录带时区的时间值；本 helper 的文件名时间戳本身不表达时区。

## 已发布实验工具：capture_check_wiring

输入仅 sessionId，拒绝额外字段；绑定当前只读副本会话，源文件变更时报 target_changed。独立进程读取 Dbo 导线坐标，输出 advisory 几何报告及关联 sourceFingerprint 的 artifact，副本 DSN 不写入。工具会写新报告，因此 readOnlyHint=false；不接收 PDF、GUI、任意脚本或保存参数。

只检查定义级正交线段几何；最大 2000 线段和 10000 finding。交叉/T 点仅为候选，electricalConnection=not_evaluated；designPassed=null。对角线暂不参与相交检查，geometryComplete=false 并返回 partial。报告提供未覆盖检查清单，validationState=unverified。详见 [当前验证记录](../validation/wiring-2026-10-22.md)。当前共 8 个实际工具，机器 schema 以 contracts/tools.v0.1.json 为准。

## 已发布实验工具：capture_gui_status

无参数、拒绝额外字段，只访问主机 --gui-bridge-config 明确指定的绑定。返回实例 ID、PID、活动工程规范路径、Tcl版本、磁盘指纹、bindingVerified、readOnly=true、dirtyState=unknown、capabilities=[gui.status]。不返回令牌或连接配置。失败为 bridge_unavailable 或 target_changed。仅该工具有 GUI bridge 后端，不将已有磁盘副本 session 自动转换成 GUI session。当前实际 tools/list 共9个工具，机器契约已同步。

## GUI RPC会话契约v0.2

新增capture_gui_instances、capture_gui_attach、capture_gui_query、capture_gui_detach；status便捷接口使用协议2和真实dirty状态。总工具13个，机器schema已同步。GUI会话generation独立于磁盘副本session；selectionSnapshotId限定选择条目身份，不返回可写句柄。受限发现根与绑定来自主机配置，不来自工具输入。完整字段与边界见 [GUI桥接](../gui-bridge.md)。


## 已发布实验工具：capture_compare_connections（2026-10-23）

第22个工具。输入 sessionId、expectedRevision（64位小写SHA256）、expectationSource、1–10000条 expectations。每条为 schematicName/pageName/reference/pinNumber/connected/net，拒绝多余字段和重复定位。locator使用精确名称，不能只用位号推断多单元/层次身份。连接需非空net，断开需null。

工具在指纹一致的不可变Dbo快照上比较指定引脚的连接观察值，写新工作区报告，readOnlyHint=false。每项含locator、objectRef、expected、observed、status、reason；缺失为fail、歧义/连接但无网名为unverified。comparisonStatus=pass/fail/unverified，comparisonComplete=false使envelope=partial；已完成且发现差异仍为succeeded，非法输入或过期副本为failed。

只覆盖selected_pin_definitions；未列引脚数量单独记录，designPassed=null、electricalConnectivityVerified=false。expectationSourceIndependentlyVerified=false；工具不生成预期基线，也不证明来源独立。定义网名相等不证明网络等价或完整电气连通。原生DRC、重复层次、junction、总线等仍未覆盖。产物validationState=unverified。机器契约以contracts/tools.v0.1.json为准；完整边界与后续计划见06-business-roadmap.md。


## 已发布实验工具：capture_get_part_properties（2026-10-23）

第23个实际工具。输入sessionId、partId，拒绝额外字段。仅接受当前不可变副本会话内的part定义ID，查询前后核对revision；新进程按照相同遍历ID定位，并核对原理图名/页名/位号。不是GUI会话ID，也不接受任意Tcl或native指针。

返回revision、generation=1、scope=part_definition、partId、原理图/页/位号、items[{name,value}]及count。最多512项、1MiB结果；按name排序。有效属性包含继承值，明确未检查property_origin/editability/occurrence_properties/property_write，不将空字符串解释为不存在。生成临时结果因此readOnlyHint=false，DSN不修改。成功临时文件清理，失败证据保留。数据格式/身份错误为invalid_worker_result；缺失part为object_not_found；陈旧副本为target_changed。验收见../validation/capture-properties-2026-10-23.md。


## 自主实施第一批新增工具（当前31个，2026-10-23）

- capture_library_open(sourceLibrary)、capture_library_query(libraryId,entity,packageName?,cursor?,limit=100)、capture_library_close(libraryId)：复制OLB，读取package/device/cell/part/pin，严格device物理脚映射、指纹/分页绑定；不修改库，不证明外部footprint存在。cell ID是device上下文视图，不宣称全库去重的native身份。
- capture_get_part_geometry(sessionId,partId)：原生位置、rotationCode/mirrorCode与pin热点，校验快照身份；不推断连接或已渲染文字边界。
- capture_get_property_layers(sessionId,partId)：effective/user/display分离，display坐标owner_local；不宣称完整继承链或可写性。
- pspice_prepare(sourceCircuit)、pspice_get_input(simulationId)、pspice_close_input(simulationId)：显式INC/INCLUDE/LIB快照、原始字节和指纹核对；UTF-8/ASCII及有界引用，尚非完整SPICE解析，不执行求解，关闭保留文件。

库query/get_input为readOnlyHint=true；产生临时文件或改变注册状态的工具为false，设计/库内容仍不写入。所有输入拒绝额外字段。H01原生路径身份未通过、P02求解超时，因此capture_get_hierarchy和pspice_run尚未发布。详见../implementation/batch-01-2026-10-23.md及实际机器schema。


## 自主实施第二批：批准属性独立输出编辑（当前36工具）

capture_plan_property(sessionId,partId,propertyName,value)仅接受Value/PCB Footprint，已有有效属性且页内位号唯一；planId/planDigest/旧新值与15分钟期限绑定。capture_apply_property(planId,planDigest,idempotencyKey)生成新输出副本，完成保存/独立重开与定义级基线核对，源不修改；一般多单元/元件型号替换/电气行为/occurrence/DRC不在此通过范围。

capture_property_jobs(offset=0,limit=100)分页读取持久状态，nextOffset非空使envelope=partial；capture_cancel_property(planId,planDigest)取消pending或向当前服务器活动自有进程发请求，最终以jobs状态为准；capture_recover_property(planId,planDigest)在旧worker证明停止后只核验已有输出，绝不重放，nativeCompletionVerified=false。

输出artifact.workspaceRelativePath相对于data.outputWorkspaceRelativePath指定的隔离输出工作区（后者相对主机workspace-root）；不是输入workspaceId。artifact.validationState=validated仅指明确属性/保存重开/定义基线范围，data.designPassed=null。幂等命中验证已有产物hash，不重开修改。字段、路径、数量、状态和完整错误schema以实际tools/list及contracts/tools.v0.1.json为准。完整验收见../implementation/batch-02-property-edits-2026-10-23.md。

## 2026-10-24 基础库vector公共契约

创建spec.symbols[].vectors是严格kind判别数组，支持line/box/ellipse/arc/polygon/polyline/bezier/fill/text。字段及默认值以真实MCP JSON Schema为准；legacy lines先绘制、vectors按声明顺序追加。每view新vector≤256、点≤8192、文字总字符≤16384，整体声明≤32KB。文字location由bounds左上角确定，font为14字段对象。未知字段/类型及任意方法输入拒绝；保存重开必须与完整声明图一致。

capture_query_library_vectors(libraryId,partId,cursor?,limit=100)返回revision绑定的items、total、nextCursor、complete、order=native_draw_order。item含objectId、partId、0起index、kind和descriptor。array定义：line=[kind,start,end,style,width]；box/ellipse=[kind,bounds,style,width,fill,hatch]；arc=[kind,bounds,start,end,style,width]；polygon=[kind,points,style,width,fill,hatch]；polyline/bezier=[kind,points,style,width]；fill=[kind,start,fill,hatch]；text=[kind,text,location,bounds,font14,isFontDefault]。font14顺序为faceName,height,width,escapement,orientation,weight,italic,underline,strikeOut,charSet,outPrecision,clipPrecision,quality,pitchAndFamily；后三个布尔font位以native0/1返回。isFontDefault为SDK派生分类，公开声明不独立指定它。

游标绑定part/limit/revision，同会话缓存命中仍校验副本hash。未支持类型整体拒绝该目标view；不会通过丢弃未知图形形成看似完整结果。readonly表示读取库副本，首次查询会产生自己的快照证据文件。没有渲染、pin-label字体、bitmap、nested symbol、外部封装/电气认证。

已知本机限制：LOGFONT quality0..6创建后可读，但保存重开均为1；quality2声明因此返回library_creation_mismatch且输出不可打开。接口不静默改声明或放宽验证。quality1显式字体字段正例已验收，非1持久化问题保持open。

## 2026-10-24 既有库vector编辑契约

- capture_plan_library_vector_edit(libraryId,partId,vectorId,operation=update|delete,replacement?)：IDs绑定当前库revision与原绘制index/完整descriptor；update必须提供完整同kind声明，delete不得带replacement。预览列明所有同名part的受影响device/package scope；重复符号图形/pin-start不一致拒绝。只改独立副本。
- capture_apply_library_vector_edit(planId,planDigest,idempotencyKey)、capture_library_vector_edit_jobs(offset=0,limit=50)、capture_cancel_library_vector_edit、capture_recover_library_vector_edit：持久任务、取消、超时及恢复只验证不重放；源与冻结before/expected证据hash都不可改变。计划≤48KB，只有该任务族账本读取上限128KB。
- capture_open_edited_library(planId,planDigest,kind=pin|vector)：新增kind，默认pin保持兼容。只有verified/verified_recovered且artifact hash一致才打开，不能扩大公开read roots。

更新保持原生vector对象与draw position；删除只去掉绑定位置。写入前核对全部预览引用上下文，去重真实vector句柄后逐个写入，避免不同加载上下文只有一个被写入。保存后独立比对已建模的所有package/device/cell/part/逻辑与物理引脚、共享/交换信息、模板、pin starts及有序基础vector字段，未知类型拒绝。结果declaredVectorEditVerified/modeledLibraryPreservationVerified不代表任意库属性、未引用native对象、渲染、pin-label字体、bitmap/nested symbol、DSN缓存/电气/DRC或外部footprint已认证。只有明确更新的text不把SDK派生IsFontDefault作为独立声明；所有未目标text的原分类仍严格保留，14项font字段始终比较。quality非1持久化问题保持open。

## 2026-10-24 package属性与退出信号

capture_query_library_package_properties(libraryId,packageId)按revision读取固定字段和显式用户属性的值/原生类型/权限。capture_plan_library_package_edit(libraryId,packageId,changes?,userProperties?)仅固定referenceTemplate/footprint/pcbLibrary；null不变，后两者空串清空。userProperties至多64条name/operation(set|delete)/value，set可为空，delete value必须null，当前set认证editable native string(type0)，拒绝内置影射、重复/别名及无变化。计划冻结全体package属性和已建模库图，≤48KB/账本128KB；不认证外部footprint、实例自定义继承、自动编号、已有缓存、任意类型或其他库对象属性。

配套capture_apply_library_package_edit、capture_library_package_edit_jobs、capture_cancel_library_package_edit、capture_recover_library_package_edit，保存重开，恢复只验不重放；capture_open_edited_library支持kind=package，默认pin兼容。进程结果新增rootExitSignalConfirmed、observedProcessExitSignalsConfirmed、observedOwnedProcessCount：Job排空后还等待根及所观测所属后代句柄退出。预取消仍pid=null/owned0，不声称枚举全部极短寿命进程。

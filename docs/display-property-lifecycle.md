# 显示属性创建与删除

## MCP 支持范围（2026-11-07，第 140 批）

在现有 capture_plan_display_property 中指定 operation=create 或 delete，随后调用 capture_apply_display_property。省略 operation 时仍执行已有显示项布局编辑。此前保存的布局计划及原生回执格式继续有效。

- 创建仅支持本地已放置器件的 PCB Footprint 显示项。已有有效属性值必须非空且显示项尚不存在。调用方显式给出 owner-local location、rotationCode、displayTypeCode。使用固定 Arial-11（quality 1）、原生颜色 0，独立重开核对完整字体描述及默认字体标记。
- 删除同名显示项时仅提供目标和 operation，不传布局字段。底层 PCB Footprint 属性及其他实例的显示项、字体、属性、几何和连接保持。目标同时绑定设计快照、部件 ID、原生 ID、页和位号。
- 计划、执行、取消与恢复沿用现有隔离作业。恢复只对已经保存的字节做独立核验，验证工作进程已停止后才执行。原生产物、日志及独立期望不进入 Git。

用自建 fixture 通过 tools/smoke_display_lifecycle.py 执行真实 SPB 24.1 stdio MCP 验收。需要指定安装目录、fixture、独立输出目录、目标位号及预期的 footprint 字符串。覆盖创建、删除、旧布局、重启后幂等、挂起任务取消、非法输入、模拟保存后中断和终态产物篡改。E02 的字体默认重置、任意字体质量、渲染与 occurrence 仍待验收。

## 第 139 批原生原型（历史记录）

以下是接入 MCP 之前的原型记录。原型脚本依赖当时的原生适配器文本，复现该历史批次请使用 c3558b6；当前版本请使用上述 MCP 验收脚本。

2026-10-29，batch139。现有公开capture_plan_display_property只修改已有显示项布局；创建/删除尚未接入公开计划/任务。依据CAP-REF303页NewDisplayProp及170页DeleteDisplayProp，在用户自建库实例的私有DSN副本上先完成原生完整往返，不宣称MCP生命周期已完成。

独立预期为已有PCB Footprint数据值CUSTOM_00123，新增显示项位置[-40,60]（owner-local）、rotation1、displayType2、color0、Arial-11及完整14字段font quality1。创建前确认该显示项不存在，原生定位仍按partId和schematic/page/reference围栏。只有NULL与状态0或已知1002可视作缺失；其他错误拒绝。按NewDisplayProp及完整保存链保存，新独立会话读取后逐项核对。随后只调用DeleteDisplayProp，保存并新会话重开。

创建阶段所有实例user/effective属性、其他显示项、所有原字体/默认字体标记及定义/引脚网络保持；新增字体完整描述准确。删除后这些已建模状态完整回到原基线，PCB Footprint数据值仍存在。这是语义往返恢复，不是DSN文件字节相同，也不证明实体封装存在。原源及oracle保持，两原生worker均正常退出/owned0，无GUI或真实设计写入。

公开创建/删除计划、持久幂等/恢复/取消、负例及旧计划兼容尚待接入并验收，后续应复用当前任务保护而非暴露任意Tcl。原quality2保存失败、字体默认重置、渲染/occurrence等原E02要求保留；本次固定quality1不能替代它们。E02仍deferred，原34仍8/34。无生产/契约变化，最近732回归沿用，固定研究脚本编译通过。原始DSN/逐实例快照留.local，公开原创复现和hash见batch-139-evidence.json；alpha/release保持固定。

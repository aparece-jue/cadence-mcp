# Capture 元件有效属性读取验收（2026-10-23）

优先级依据与资料索引见 [Cadence子模块清单](../design/07-cadence-submodules.md)。本记录只覆盖C1新增的元件有效属性读取，不代表全部查询或其他子模块完成。

## 实现与契约

新增 `capture_get_part_properties(sessionId, partId)`。partId必须来自当前不可变副本会话；启动新独立Dbo进程前核对DSN指纹，读取后再次核对。按照同一设计遍历生成的定义ID定位，并验证原理图名、页名和位号。ID仅限当前会话，不是跨修订稳定数据库标识。它避免以共用位号选择多单元器件时任意取首个的问题。

独立模块为src/cadence_mcp/capture_properties.py及adapters/inspect_part_properties.tcl。使用官方NewEffectivePropsIter/NextEffectiveProp，读取最多512项有效属性；结果最大1MiB，对象遍历最多100000。有效属性含继承值，但不宣称属性来源、可编辑性或occurrence覆盖；未返回可写指针。值为可包含中文/特殊字符的字符串，空字符串保留，不与不存在混同。未开放任何属性写入入口。

异常worker、错误对象身份、重复属性名、错误结构、数量/大小超限、陈旧会话和未知ID均明确拒绝；失败证据保留，成功的临时属性结果清理。工具需要生成临时本地结果文件，因此readOnlyHint=false，返回readOnly=true表示DSN未修改。

## 资料依据

安装目录tools/capture/tclscripts/OrCAD_Capture_TclTk_Extensions.pdf属性迭代器参考与doc/orctclcap/Listing_Properties_of_the_Selected_Object_in_a_Schematic_Page.html，后者明确展示NewEffectivePropsIter、NextEffectiveProp、CString/ValueType/int输出参数与delete_DboEffectivePropsIter。未复制官方文档全文或旧仓库代码。

## 本机验收

89项自动测试：88通过、1项文件符号链接权限跳过。新增7项覆盖元件ID定位（含共用位号）、Unicode/特殊字符和空值、未知/陈旧/父级不一致、检查期间修改、错误身份/重复/非法worker结果、缺失/超大结果/进程故障、MCP严格输入与临时文件清理。

实际stdio MCP在FULLADD官方样例独立副本上读取全部9个元件的有效属性，每个元件属性项数为[18, 18, 18, 18, 18, 18, 10, 10, 18]；第一元件独立进程重复读取结果一致。可读取Value、PCB Footprint、Part Reference、Source Library/Package/Part、坐标等有效值。输出字段不证明字段对应资源存在或其可写。实际tools/list为23个，输入/输出schema已校验并同步。

副本页/引脚读取、局部连接负例、几何报告、分页、快照、新进程重复读取与关闭会话检查通过；成功属性临时文件无残留。未操作GUI，未写入安装或真实工程。安装样例源SHA256前后均为`27c6d11ffbb8d677954d8e56eba26a4b725c677aa83a08020da682972e1ef104`。

本机忽略目录证据为.local/capture-modules-20261023/native-smoke-report.json、tools-list.json和副本检查结果。第一次直接Dbo探测记录在.local/capture-modules-20261023-probe/property-probe.json。不将这些官方样例数据纳入Git。

后续优先C2：批准字段的修改计划、保存与独立重开，并明确非电气/电气属性的验证边界。其余子模块按实施清单逐项完成。

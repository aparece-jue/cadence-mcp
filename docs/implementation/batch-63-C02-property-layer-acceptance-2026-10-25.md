# 第六十三批：C02属性分层读取完整验收

2026-10-25。按原C02“有效/显式/显示值、空值、重复位号、字符编码与资源释放”要求补齐受控默认/覆盖/删除对照。无生产代码或工具契约变更。

## 官方依据与夹具

已读取本机CAP-PROP官方有效属性遍历示例，以及CAP-REF第165/166/169页：有效/user/display迭代器、DeleteUserProp及NewUserProp(name,value,state)。私有固定脚本创建ROOT/AUX同名页、各页R1/R10，及空页；cache LibPart设MCP_DEFAULT=库默认值，cache package另设MCP_PACKAGE_ONLY作为来源层对照。ROOT/R1有独立MCP_LOCAL中文/特殊字符及Value显示坐标[13,17]，其他实例保持显示坐标[5,15]。

四组独立保存的新设计分别是base无显式覆盖、override显式覆盖、empty显式空串、deleted创建覆盖后删除。探测证实本安装中cache LibPart默认参与实例有效值继承，而测试package自定义属性不出现在实例有效层；不能把任意库/package属性都当成实例继承值。

## 原要求逐项验收

|原要求|真实证据|
|---|---|
|有效/显式/显示分离|四组各4个实例逐一读取三层，并与独立effective接口结果全集比较；Value=1k不出现在显式user层，显示Value及位置单独核对|
|来源与覆盖|默认值存在于effective而非instance user；覆盖后user/effective同显式值；其他同库实例保持默认，不误归因package字段|
|空与删除|显式空串仍存在user且effective为空；删除显式覆盖后user中不存在该项而effective恢复cache默认|
|跨页重复位号|ROOT/AUX同名页中的R1按partId区分，只有目标出现MCP_LOCAL及特殊显示坐标，其他实例不被污染|
|同页重复位号|原已通过的U501双单元私有夹具，两part同页同reference；各有效位置分别匹配原先冻结的1000/700与1200/700声明，不能按reference误读另一单元|
|字符编码|中文、引号、反斜线、方括号、美元号、分号及换行逐字符匹配独立预期；期望用固定字符组合构造，不从实测读取生成|
|资源释放|每组对目标额外3次独立读取相同；property-layers与part-properties成功临时JSON均已清理，close后拒绝读取|
|边界|错误partId、工作副本变更、关闭会话分别拒绝；源设计及预期hash保持|

主要记录`.local/property-layers-mcp-20261025/report.json`四组全部通过；同页单元记录`.local/same-reference-property-layers-20261025/report.json`通过，使用原预期文件hash和原source hash绑定，未重写原预期。

## 公开删除回退补验

`.local/property-fallback-public-20261025/report.json`通过真实MCP plan/apply/open/read：删除MCP_DEFAULT显式覆盖后恢复库默认，MCP_LOCAL原值保持。另建错误“删除后应不存在”预期，原生写入后严格以effective_fallback_mismatch拒绝，不能打开未验收输出或重放。正确任务新服务恢复/幂等不重放通过。此同时补充E02继承回退切片，E02完整编辑/显示范围不随之结案。

## 失败记录与范围

最初两组私有夹具脚本含UTF8中文常量，在本机Tcl脚本默认编码下报missing close-bracket；原失败receipt/源码保留在property-layers-probe-20261025和v2目录。固定脚本改为ASCII加Unicode转义后创建成功。v3仅package属性不进入实例effective的观察保留；v4加入LibPart默认后原生继承对照成立。探测记录不冒充业务验收；规范预期以最终MCP expected.json及独立原声明为准。

C02标记passed，范围为原定义级有效/user/display属性分离及覆盖、空值、回退读取。API原notChecked(full_inheritance_chain/occurrence_properties/rendered_text_bounds/editability)保持：不声称能追踪任意外部库/cache/occurrence全继承路径，不把显示坐标检查等同渲染图面审查。这些限制没有被隐藏，也没有因本批把其他业务门禁标通过。

34项现为2 passed、1 baseline_passed、19 implemented_partial、10 deferred、2 planned；整体目标active，最终A01待办。生产/契约第61批摘要均保持，沿用411回归410通过/1原符号链接权限skip，不因仅新增专项验收脚本而无故重复整套回归；167工具保持。无GUI、无安装/真实工程改动、无提交推送。

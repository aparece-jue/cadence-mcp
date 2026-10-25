# 页面文字写入（develop实验能力）

文字任务工具：capture_plan_graphic_text_add、capture_apply_graphic_text_add、capture_graphic_text_jobs、capture_cancel_graphic_text_add、capture_recover_graphic_text_add。已验证产物可用capture_open_edit_result(kind="graphic_text")打开。当前develop共200工具；已发布alpha.1固定包仍193工具，不会被这次研发自动改变。

## 输入及坐标

指定不可变sessionId及其pageId、文字text、页面锚点location=[x,y]、局部定义框width/height、font、rotation=0..3、mirror=0..1。font={}使用Arial/-11/quality1默认值，也可声明严格VectorFont字段。仅quality1有已验证保存行为，其他quality明确拒绝；原字体质量保留问题没有关闭。

text支持中文、多行LF及字面量[x]$;，不执行其中内容。限制1..4096字符，拒绝NUL、CR、孤立代理字符；使用LF换行。正宽高1..100000，整数坐标及变换后框点均限制±1000000，拒绝布尔值冒充数字。

location是页面文字锚点，不是DboGraphicInstance.GetLocation字段。本机文字实例位置保存为0,0，直接设置实例位置无效；固定写入器逆变换页面锚点，设置DboCommentText定义的Location/BoundingBox，再核对原生页面控制点。四旋转和两镜像已在新副本、保存后新进程读取中验证。此模型与元件定义的宽高补偿不同，不能混用。width/height是声明的局部定义框，既不认证渲染字形范围，也不代表自动换行宽度。

## 写入和验证

plan预览原生定义描述、页面锚点和姿态。apply只写新的隔离DSN副本；完整保存后以新进程重开，验证文字、14字段字体、局部框、页面控制点，以及所有页面支持的图形定义/顺序/几何保持。原实例已建模的姿态/热点、effective/user/display属性和定义/连接基线也需保持。

最多64页、128个已建模实例，沿用每页4096图形/点数/文字预算。任何页出现不支持图形会在计划时拒绝，不省略后当成保留成功。计划最多48KiB，不接受任意Tcl/原生指针；字面量经JSON进入固定adapter。

fresh apply以相同key不会重放。recover只验证已停止任务的现有产物；回执丢失时不伪称已观察native完成。启动取消、DLL加载后的实际超时、无关图形被另一个原生操作改变后拒绝apply/recover均有证据。

## 更新和删除

先通过capture_query_page_vectors取得目标文字的objectId，传入capture_plan_graphic_text_edit(sessionId, graphicId, operation, change)。operation为update或delete。update要求change包含text、location、width、height、font；rotation/mirror默认0，可显式声明。它是完整替换，不把缺省字段当作保留旧值。delete要求change为空；不能选择非文字图形。

预览保留oldGraphic及新声明。执行与恢复仍使用既有capture_apply_graphic_text_add、capture_graphic_text_jobs、capture_cancel_graphic_text_add、capture_recover_graphic_text_add，open结果仍kind=graphic_text；名称中的add是既有任务入口名称，现支持同family的三种计划，不需要另开任务队列。

目标同时绑定不可变源副本、页内原生顺序和nativeId，原生迭代器释放后才修改/删除；不以同名文字猜目标。其他有序图形/实例/定义/连接摘要需保持。delete成功返回graphicRemovalVerified=true、pageAnchorVerified=false；新增/更新相反。无关图形变化会拒绝apply和verify-only恢复。

32混合图形/4段相同文字中，8姿态更新及首/中/末文字删除实际MCP通过；两类操作各4原生故障通过。3既有新增用例复测和3旧199工具时期计划/回执的副本只读核验通过，未重放旧写入。

## 现有限制

已支持新增、完整更新和删除页面文字。页面裁切、实际字体字形渲染、标题栏/嵌套符号、未建模属性、实例显示字体及occurrence/原生DRC不在成功结论中。已有图形描述中的字体字段需保持，但不将其等同视觉验收。D05完整门禁仍未通过。

官方依据为安装内CAP-REF p455–456（NewGraphicCommentTextInst）、p708–709（定义层SetBoundingBox/SetLocation）、p300（原生点转换）；完整来源指纹见参考索引。原实例位置失败预期及首次MCP helper缺失失败都保留，见第88批记录。

# 第四十八批：基础复杂vector的多视图身份校验

2026-10-24。原34项范围保持，无新增MCP工具，仍143。完整325回归324通过/1原文件symlink权限skip；原目录释放间歇issue不关闭。

## 官方依据与真实绑定

本机主参考DboGraphicObject.NewBox/Arc/Ellipse/Polygon/Polyline/Bezier/Fill/CommentText（p285–292），vector读取类p679–709；安装内orPrmDboStreamer.tcl用于核实点iterator.Next使用CPoint输出、按GetCount逐项读取及文字Escapement。未复制官方实现。

只读运行时探测确认8类vector枚举、点iterator和LOGFONT字段getter，字体Name实际签名需要(LOGFONT, CString输出)，其余数字字段返回标量。枚举中SOLID_FILL=0/HOLLOW_FILL=1/HATCHED_FILL=2、hatch0..5等记录为实际元数据，不能把数值凭名字猜义。

## 实现变化

新增dbo_vector_signature.tcl读取box/ellipse边界、arc边界和起止点、polygon/polyline/bezier有序点列、fill种子点，以及stroke/fill/hatch样式；文字含内容、位置、边界、14项LOGFONT字段与default-font标志。不用跨库可重排的fontId代替字体内容。

多视图source/cache选择及保存后实际PlacedInst.GetPart比较复用此描述。含非line对象时保留完整native vector绘制顺序和点序，不用无序集合掩盖顺序变化；原纯line签名保持旧格式/排序兼容。未知bitmap/symbol-vector等类型仍拒绝。每view4096对象、每point集合4096点、全view65536点及262144字符预算、单文字65536字符有界。

sourceVectorGeometryVerified增量标记，旧sourcePinLineViewVerified字段保留；独立视图报告分别给lineCount/vectorCount。既有individual placement只在多视图分支执行此比较，single-view旧路径不因此获得新认证；完整group路径按已有独立视图检查扩展。未声称所有pin-label字体/显示属性、bitmap、嵌套symbol、颜色及其他未建模属性、渲染结果或外部封装已验收。

## 冻结夹具与失败记录

为8类对象各建双view OLB，Normal/Convert的pin及原line完全相同，唯复杂vector字段不同；前置冻结全部几何/样式/font字段。7类首轮保存后新进程全部字段通过；文字首轮因GetLFName真实输出参数签名不符读失败，报告保持false。

修复Name getter后新text-v2：字体内容等字段正确，但fixture随后SetBoundingBox使GetLocation落在边界左上角，原输入location(-5,0)与bounds(-5,-10,35,4)不一致，完整字段oracle失败，旧期望不改。新v3独立声明location(0,0)/bounds(0,0,40,14)，两视图字体/旋转/weight明确，保存重开全部字段通过。这不是把原失败观察值写回原期望，也不宣称任意文字锚点约定已解决。

## 实际MCP与故障验收

- 三组真实143工具stdio共16次Normal A/Convert B放置，覆盖8类图形；source、cached候选及保存后实际instance的有序字段匹配，新进程open/fresh apply/recover/open不重放通过。每view3pins/4lines/5vectors。每组错误热点oracle实际保存后拒绝/open拒绝/不重放，源DSN/OLB和冻结oracle hash保持。
- 两个纯图形破坏负例：实际native放置保存后，仅改私有输出中的ellipse bounds或文字font weight。原pin/net/pose/value及连接对象检查仍能通过，但视图比较matches=false/placement_view_mismatch，输出不可打开、重复写入拒绝；原来源和OLB hash保持，自有worker0。
- 旋转文字Convert专门回执丢失：真实保存后删回执，fresh MCP只验证恢复/nativeCompletionVerified=false/mutationReplayed=false/sourceVectorGeometryVerified=true/hash保持/open通过；真实启动取消、受控延迟对1s timeout，owned0通过。
- 原同pin仅line4/5不同的2例真实MCP兼容回归通过，证明旧line-only行为保持。最后加总预算后完成325项全回归324通过/1原权限skip，contract实际143同步。

## 尚未完成

本批扩展的是已有库符号的多view放置校验，不是公共复杂vector创建或查询接口。公开OLB声明创建仍只有line；复杂vector声明式创建、公开图形读取、pin-label/default显示字体、bitmap和nested symbol、Unicode/多行/任意字体与渲染完整矩阵仍待实现或验收。原缓存任意命名异构导入、封装变体/替换覆盖保持、D02共享电源接线移动失败、flat/总线/DRC/仿真闭环等完整34项保持。

下一推进声明式复杂符号创建/读取，并继续原失败后移策略。无GUI、安装或真实设计修改，无提交/推送。报告与实现文件SHA256见batch-48-evidence.json。

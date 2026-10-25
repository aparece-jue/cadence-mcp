# 第四十九批：公共库图形创建与查询

日期：2026-10-24。范围是库符号的基础vector字段，不等同于页面图形实例、标题栏、渲染效果或全部库业务验收。工具由143增至144；原34项门禁保留，目标仍active。

## 官方依据与实现

本机 `tools/capture/tclscripts/OrCAD_Capture_TclTk_Extensions.pdf` p285–292的固定创建接口及p679–709的类型读取接口。文字GetFont/IsFontDefault见p707，库字体注册SetFont见p204；实际调用参数继续由本机独立Tcl验证。没有复制官方实现或手册全文。

`LibrarySymbolDefinition.vectors` 支持line、box、ellipse、arc、polygon、polyline、bezier、fill、text。字段通过判别式严格模型校验，不提供任意Tcl或方法调用。每view最多256项新vector，8192个声明点、16384个文字字符；整个创建声明仍受32KB预算、原引脚和物理映射约束限制。legacy lines先创建，vectors随后按声明顺序创建。

保存后独立进程读取全部声明字段、每view完整native draw order，以及原package/device/cell/part/引脚/物理映射等图。新式line同时属于全部线段子集与有序vector序列；任何view使用vectors时，所有view都记录顺序，避免空view被漏验。原无vectors字段的持久计划不插入新默认值，原line-only图摘要形状保持；未声明的复杂图形仍会导致验证拒绝。

文字声明提供bounds和14项LOGFONT字段，location固定为bounds左上角，避免SetBoundingBox重设锚点引起矛盾。14个声明字段逐一比较；SDK派生的IsFontDefault作为读取字段暴露，不猜测默认字体继承。位图、嵌套symbol、pin-label字体/显示属性、颜色和渲染效果尚未覆盖。

新工具 `capture_query_library_vectors(libraryId, partId, cursor?, limit=100)` 绑定复制库的revision和part，按package/device/part精确定位后读取，避免扫描其他view的未知vector。返回带稳定快照索引的descriptor数组，顺序为native_draw_order。游标绑定part/limit/revision；缓存命中仍核对副本hash，关闭或篡改会话拒绝。未知类型/异常输出拒绝，不声称图面视觉合格。

## 原生与实际MCP验收

- 首轮 `.local/public-library-vectors-20261024/report.json` 保持false：新式line实际保存正确，但expected_graph的全部线段子集漏计此line，独立校验正确拒绝；修复后增加针对此错误的host测试。
- 新独立 `.local/public-library-vectors-v2-20261024/report.json` 三组通过：混合9类、仅新式line、旧声明。每组4个device-scoped view逐字段查询/分页；错误游标参数、无效part、关闭session拒绝；错误homogeneous预期实际保存后拒绝/open拒绝/不重放；fresh apply/recover/open不重放，源声明和冻结预期hash保持。
- `.local/public-vector-faults-20261024/report.json`：混合图形真实保存后丢回执，fresh MCP verify-only恢复/nativeCompletionVerified=false/hash保持/open通过；真实启动取消、独立延迟worker的1秒timeout、自有进程退出；保存后追加未声明ellipse被完整图校验拒绝且不可打开。
- `.local/public-vector-legacy-faults-20261024/report.json`：同一故障矩阵用不含vectors字段的旧格式持久计划通过，证明新验证器未破坏旧摘要与恢复；旧计划出现非声明图形仍拒绝。
- `.local/public-vector-placement-20261024/report.json`：公共接口创建的混合库进入真实MCP Normal/Convert放置，每view3pins/5lines/13vectors，source/cache/实际instance几何/样式/文字字体/顺序匹配，保存重开、错误热点拒绝/fresh lifecycle/来源hash保持通过。脚本准备阶段曾误读不存在的outputWorkspaceRelativePath；未启动业务写入，已按planId定位实际产物后运行。
- `.local/public-vector-fields-20261024/report.json` 保持整体false：默认style5/width3通过，中文/Ω/特殊字符/多行文字通过，显式font quality2保存重开成1而失败。原声明和预期没有改写。
- 构造器quality0..6都保持原值；独立完整package/cell/device对照，创建后和SetBoundingBox后仍0..6，保存重开全部变为1：`.local/logfont-quality-20261024.json`、`.local/comment-font-trace-v2-20261024.json`、`.local/comment-font-reopen-v2-20261024.json`。即使预注册库字体也如此。首孤立part对照无法按名重开，不作为持久化证明。新增ISS-L02-comment-font-quality-persistence保持open；不放宽字段比对，不宣称任意font quality可持久化。
- 另立明确quality1的独立用例 `.local/public-vector-font-quality1-20261024/report.json` 通过，覆盖height8、width1、weight500、strikeOut、charSet、out/clip precision及pitch/family等显式字段；这不关闭quality2原失败。
- 新增8项host测试，完整333项回归332通过、1原文件符号链接权限skip：`.local/regression-333-public-vectors-20261024.txt`。144实际工具契约同步。历史间歇目录释放问题保持open。

## 保留的完整范围

本批没有关闭完整L02/L03/L04/D01门禁。任意字体quality、bitmap/nested symbol、图形属性编辑与渲染、页面复杂图形/标题栏、缓存替换覆盖、封装变体、共享电源接线移动、flat/global/总线、原生DRC/网表与完整PSpice闭环等原任务仍需实现或验收。1 baseline_passed、21 implemented_partial、10 deferred、2 planned，不以工具数或回归数代替功能门禁。

下一推进用户库既有基础vector的明确修改/删除与保存重开，保持冻结期望、未目标对象及连接身份；本批字体失败保留后移。无GUI、安装或真实设计修改，无提交推送。机器记录见batch-49-evidence.json。

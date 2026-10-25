# 第七十五批：显示属性字体与默认字体状态

2026-10-25。原34必需门禁不变。新增6个MCP工具：capture_get_display_font、capture_plan_display_font、capture_apply_display_font、capture_display_font_jobs、capture_cancel_display_font、capture_recover_display_font，verified打开增加kind=display_font；实际工具191。其他旧显示位置接口不变。

## 实现与官方依据

本机Tcl参考616–619/622页：DboDisplayProp.GetFont需要dbFontType及LOGFONT输出参数；本实现使用明确的DboDisplayProp_sGetFont(obj,status)返回完整字体。IsFontDefault及GetDefaultFontType分别记录是否继承默认字体及默认类型，SetFont写显式字体。原型首轮误用了其他图形类GetFont(status)形式，读取被拒，诊断原样保留后改正。

固定读适配器单进程覆盖全部实例及已有display字体，128实例、每实例512字段、完整14字段LOGFONT、默认标记和默认类型；独立unit identity核对完整覆盖并拒绝重复/外来/异常字段。新字体采用已有严格VectorFont schema，全量替换，未给字段取schema默认，不是局部patch。字面名称通过JSON及固定方法传递，无eval。nativeId+schematic/page/reference绑定单实例，允许共享基础位号和drawn层次实例；不存在display不自动创建。

计划冻结源hash、全部字体及默认状态、全部实例已建模geometry/effective/user/display状态、units、定义和连接对象。目标期望由声明新字体及显式fontDefault=0生成，其余保持。固定Tcl工作器写独立DSN、校验旧字体/继承状态、完整保存；新进程重开逐字段检查全部预期。异常不重放，恢复只验证现有输出。没有把字体是否安装、真实渲染边界、occurrence覆盖、缓存装饰图形或DRC算通过。

## 原生与实际MCP证据

- 多单元Part Reference：字号-17、weight700、italic/underline、quality1原生及真实MCP通过；R101.Value的Times New Roman、height-15、weight500、strikeOut、quality1真实MCP通过。此Value原本为显式字体，不能计作继承转换。
- 单独预先确认halfadd_A.Reference原fontDefault=true；MCP关闭输入后应用height-19/weight600/quality1，重开fontDefault=false且完整字体等于声明，全部其他字体、已建模状态和连接保持。默认状态不是由font数组相同推断。
- 六故障全部通过：保存后回执丢失由fresh服务verify-only恢复；启动取消；真实1秒执行超时；真实不相关实例字体误改被全字体检查拒绝；启动前源副本篡改；启动前冻结预期篡改。执行后确认owned进程退出，未验证输出拒绝、写入不重放。原输入hash保持。
- pending cancel、新服务重复apply不重放/recover通过。首MCP正例输出完成验证后先保存完整备份，再作终末篡改；open/recover/apply均target_changed，原始正例与失败报告不回填，原生正例和默认转换正例仍有完整输出。

## 未通过的quality与后移

独立声明MCP_NOTE height-16/quality2，本次保存成功但完整字体检查拒绝。新进程只读审计确认唯一差异是quality2→1，其余13字体字段、default标记/类型保持。整体真实MCP报告保留passed=false；未把实际1改成期望，不将正确拒绝当作quality2持久化通过。原报告、计划账本、冻结expected文件和失败输出hash均保持。ISS-E02-display-font-quality-persistence open，完整E02由partial转deferred并移队尾。与库comment字体的旧quality问题有相似现象，但根因未证实，未关闭旧issue或声称SDK不可实现。

## 回归与状态

新增7host测试覆盖严格完整字段/顺序/布尔编码、字面名称、完整实例覆盖、重复/异常字体/默认状态、精确display名。首新增服务两个register漏readonly导致服务启动失败及14回归错误，修正为readonly=True后在新目录复验，原失败日志保留。首不完整Getter原型同样保留。

最终完整473回归：472通过、1原符号链接权限skip，无失败；真实191契约同步。34现5 passed、1 baseline、13 partial、13 deferred、2 planned，整体active。未使用GUI、不改安装/真实设计、不提交推送。后续先推进其他独立功能，再集中处理quality和其他后移问题。证据hash见batch-75-evidence.json。

# 第五十批：既有库图形更新、删除与保留校验

日期：2026-10-24。新增5个任务工具，实际MCP工具149。原34项完整门禁保持，整体目标未完成。

## 官方依据和公共行为

本机OrCAD_Capture_TclTk_Extensions.pdf p285的DeleteVector，p682–705各基础图形的几何/样式/点列setter，p708–709的文字SetText/SetBoundingBox/SetFont。仅通过固定Tcl方法调用，没有任意eval、shell或native指针入口。

新增plan/apply/jobs/cancel/recover_library_vector_edit，复用持久IsolatedJobs。既有capture_open_edited_library增加kind=pin|vector，默认pin保持兼容。更新提供完整、同kind的replacement声明，直接修改原生对象，保持draw position；删除移除明确的原顺序位置，不重建全部库符号。

计划绑定library会话revision、partId、vectorId、原index与完整旧descriptor。独立进程先读取完整已建模库图：package/device/cell/part/逻辑与物理引脚、共享/交换元数据、模板、pin starts，以及所有view的有序基础vector字段。源副本与冻结before/expected证据都记录hash；apply/recover不能静默改期望。未知vector、缺失/歧义scope、相同符号名但图形或pin-start不一致等情况在持久写入前拒绝。

预览列出全部同名原生part的引用scope。写入器遍历并验证所有预览上下文，在任何修改之前核对原vector；对同一原生vector句柄去重，更新每个不同的已验证对象，避免只取一次GetPart写入后不能满足多上下文期望。整个已建模库保存重开后按预先声明比较，不把返回成功或文件落盘当作验收。

未目标文字的IsFontDefault及14项font字段严格保留；只有明确被更新的text，其SDK派生default分类不独立作为声明值，其余字段仍逐项比较。此前font quality非1保存后变1的问题保持open，本批没有放宽quality或其他字体字段比对。

计划payload仍≤48KB；仅library_vector任务的账本读取上限为128KB，以容纳终末结果重复的affected scopes和进程/恢复信息。新增大记录测试证明一个合法48KB以内的计划，终末记录超过原64KB时仍可读；没有扩大其他任务上限或声称该合成记录做过原生写入。

## 原生与MCP证据

- 初版两组18例通过：`.local/library-vector-edits-lines-20261024/report.json`（8例）、`.local/library-vector-edits-path-text-20261024/report.json`（10例）。每例全新输出，更新/删除line、box、ellipse、arc、polygon、polyline、bezier、fill、text；四个device/view逐字段对照独立冻结预期。更新包括点数、点序、style/width/fill/hatch、Unicode多行文字及字体。A/B Normal两scope同步，Convert保持，所有已建模定义/模板/引脚保持。
- 最终全引用写入器重新验收同一18例：`.local/library-vector-edits-lines-v2-20261024/report.json`和`.local/library-vector-edits-path-text-v2-20261024/report.json`。invalid owner/kind-change/delete-with-replacement拒绝且不生成durable jobs；fresh apply/recover/open不重放；源库和冻结oracle hash保持。账本扩容后另有`.local/library-vector-edits-final-text-20261024/report.json`两例通过。
- `.local/library-vector-edit-faults-v2-20261024/report.json`：实际保存后丢回执，fresh MCP verify-only恢复/nativeCompletionVerified=false/hash保持；真实启动取消和延迟worker对1秒timeout，自有进程退出；仅额外改动未目标Convert视图，主任务library_vector_mismatch/open拒绝/不重放；独立终末输出保留精确backup后篡改，open/recover/apply全部拒绝。初版故障报告也保留。
- `.local/edited-vector-placement-20261024/report.json`：已验收text-update库及bezier-delete库分别做Normal/Convert真实MCP放置，共4例；3pins/5lines、13vectors或删除后的12vectors，source/cache/实际instance视图匹配，保存重开、错误热点拒绝和fresh lifecycle通过，来源保持。没有把图面渲染或flat电气认证加入结论。
- 双package扩展首轮`.local/library-vector-multipackage-20261024/report.json`保持false：四个预期变化scope保存重开后仍是旧polygon，定义字段保持，严格验证拒绝；未改原预期或重放失败任务。修正为逐一写入全部预览原生上下文后，独立v2 `.local/library-vector-multipackage-v2-20261024/report.json`通过，四个目标scope、八个总view、两个不同封装名称属性/模板保留，并完成fresh lifecycle。另立双package删除用例`.local/library-vector-multipackage-delete-20261024/report.json`也通过，四个Normal删除polygon、其余Convert保留，八个view/fresh lifecycle/来源hash符合冻结预期。该证据说明修正覆盖这个实际多上下文fixture，不宣称任意商业库关系、封装变体或外部封装实体已验收。

## 回归与未通过项

新增9项host测试。首次341项完整回归触发旧ISS-P02-process-directory-release-152：test_cancel_and_precancel的临时目录清理WinError32/5，原始失败保留为`.local/regression-341-library-vector-edits-20261024.txt`；独立341复测通过340/1原权限skip，但不据此关闭间歇问题。最终342项完整回归341通过、1原符号链接权限skip，见`.local/regression-342-library-vector-edits-20261024.txt`。实际149工具契约已同步。

完整L04/D01仍partial：没有认证未建模的任意库属性、未引用native对象、bitmap/nested symbol、pin-label显示/字体、渲染、DSN缓存替换或外部footprint。字体quality持久化、目录释放、原共享电源接线移动、非中心旋转、层次/总线/flat、原生DRC/网表与PSpice闭环等原范围保持。34项仍1 baseline_passed、21 implemented_partial、10 deferred、2 planned。

下一继续库package属性、reference template及封装名称编辑/保留，继而推进其余复杂范围和队尾问题。无GUI、安装或真实设计修改，无提交推送。字段契约见docs/design/03-tool-contracts.md，机器证据见batch-50-evidence.json。

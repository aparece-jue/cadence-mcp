# 第88批：页面文字新增与定义坐标保存

2026-10-26，D05/C05；新增5个文字任务工具，实际199。完整原34项范围及状态不变，目标active。

## 原理与范围

按官方CAP-REF p455–456和p708–709，使用NewGraphicCommentTextInst及其DboCommentText定义层SetBoundingBox/SetLocation。实例位置字段仍为0,0，原构造/SetLocation失败预期保留；通过逆姿态设置局部定义点，再按p300原生GetOffsetGraphicPoint验证页面锚点。它与元件的宽高补偿不同。

固定独立声明中文、多行LF、字面量[x]$;、300/450目标点及180×40局部框，四旋转×两镜像8native副本全部保存/新进程重开通过；完整定义/连接基线保持，source和expected SHA保持。没有以实例零位置当页面位置，也没有放宽原失败预期。

## 实现及验证范围

新capture_graphic_text.py与固定write_graphic_text.tcl公开plan/apply/jobs/cancel/recover，capture_open_edit_result新增graphic_text。沿用不可变绑定、持久计划、new-copy执行、完整保存、独立核验和不重放恢复。预览页面锚点、局部描述/字体/姿态，最多4096文字、64页/128实例和48KiB计划；严格字体/整数/字面量验证，质量仅1，其他quality仍拒绝。

冻结每个页面支持的完整有序图形描述/几何摘要、既有实例已建模姿态/热点/effective/user/display，以及定义和连接基线。未知图形不省略而拒绝。保存后任一摘要变化拒绝verified输出。实际glyph/render、clipping、titleblock/nested、实例display字体和未建模属性明确未检查，编辑删除尚未实现。

## 真实MCP与故障

- 3实际MCP任务全部通过：默认中文多行、r1/m1 Arial粗体斜体下划线、r3/m0 Courier New删除线。独立重开页面锚点、姿态、全14字体字段及完整保留通过；非法quality/布尔坐标/外来page/NUL/零宽度拒绝，pending取消与fresh apply/recover不重放通过，源/声明SHA保持。
- 首MCP因固定qualified-page helper所需cmcp::str遗漏而exit1；持久ledger terminalfailed、owned0，无transport成功误判。原adapter/报告/计划/回执保留，补齐helper后用全新计划复测，没有重放旧作业。
- 回执丢失：真实native完成后移除receipt，fresh只核验恢复，nativeCompletionVerified=false。
- 启动取消：原测试错将既有operation_cancelled预期为cancelled，原4例报告false保留；修正harness后仅用新计划复测该项通过。不是生产取消功能修复。
- 超时：固定私有adapter在DLL加载后写marker再延迟，3秒真实owned超时，marker保持、owned0，不重放。
- 无关图形：文字成功后用另一固定native操作额外加线；apply及fresh recover均报graphic_text_mismatch，证明不是仅核对新增文字。

四种故障分类结合原3正例及新取消正例验收，原报告不改写，审计见.local/graphic-text-faults-20261026/audit.json。

## 回归、进度与下一步

新增5host测试，实际199工具合同同步。531完整回归530通过/1原权限skip，无失败；首次目标测试因测试文件编码处理未更新工具数而失败，修正后18目标测试通过（当时Tcl环境未设置多1skip），最终完整回归只1原skip。不是把目标skip当全验收。

34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，完整验收17.6%；D05完整门禁仍deferred，C05仍partial。说明见docs/graphic-text.md。后续继续文字/图形编辑删除、页面边界与视觉检查及其他原门禁，不改安装/真实设计，正常流程无GUI。

第87批已在本地35ee78b，先前GitHub连接失败；本批完成后一起同步develop，alpha.1固定不变。

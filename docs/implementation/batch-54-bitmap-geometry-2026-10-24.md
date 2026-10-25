# 第五十四批：既有位图几何修改

原34项必需门禁及目标保持：1 baseline_passed、21 implemented_partial、10 deferred、2 planned。以下是既有位图几何编辑的已验证切片，不是完整位图生命周期或库/放置门禁验收完成。

## 官方依据与实现

本机CAP-REF PDF712再次核实DboBitMap.SetLocation(CPoint)、SetBoundingBox(CRect)、SetBitmapDimension(width,height)的返回DboState。当前几何编辑只设置位置和图形边界，保持原DIB字节、DIB长度及原像素尺寸；不以修改尺寸字段冒充像素重采样。该类文档未提供SetDib，公共像素替换仍未开放。

现有`capture_plan_library_vector_edit`新增可选`bitmapGeometry={bounds,location,expectedDibSha256}`。operation=update且目标为bitmap时必须仅提供此声明，拒绝普通replacement；非bitmap目标或delete不接受bitmapGeometry。坐标为严格整数±1000000，bounds必须有序非空，SHA256为64位小写hex且必须等于快照位图完整DIB摘要。错误图片预期、无变化及矛盾参数在计划阶段拒绝。

内部冻结声明只含bitmap kind、bounds/location；expected graph保留原dimensions、dibSize、dibSha256，以及全部未目标vector/模板/引脚定义/位置。原生遍历并验证预览的全部同名引用上下文，再去重设置位置和边界。修改不改变draw position，不删除重建对象。原生保存后的独立完整图校验、新会话恢复、产物指纹及不重放机制沿用。

原纯基础vector计划/更新/删除和bitmap删除接口兼容；LibraryVector创建union仍不接受bitmap，不会暴露一个尚不能执行的创建声明。工具仍155个，真实stdio契约同步新增可选参数及说明。

## 验收证据

- `.local/bitmap-geometry-20261024/report.json`：两项真实MCP修改分别为移动缩放`bounds=[30,40,70,90], location=[30,40]`，独立锚点`bounds=[-40,12,20,42], location=[7,9]`。Native允许边界与位置独立保存，两组在两引用view均完整符合冻结预期，原像素尺寸2×2/DIB56字节/摘要保持；错误expectedDibSha256被bitmap_content_mismatch拒绝；新会话apply/recover/open不重放及source/oracle hash保持。
- `.local/bitmap-geometry-faults-20261024/report.json`：几何修改真实保存后丢回执，fresh MCP verify-only恢复/nativeCompletionVerified=false/hash保持；启动取消及1秒timeout均owned0；未目标Convert变化和终末产物篡改拒绝。
- `.local/bitmap-geometry-placement-20261024/report.json`：独立锚点修改后的OLB进入真实MCP Normal和Convert放置，source/cache/实际placed view完整DIB与几何签名一致；引脚全局热点、网络定义、保存重开、错误热点预期拒绝和新会话恢复不重放通过。fixture manifest绑定已验证编辑计划和独立未变的引脚声明来源。
- 新5项主机测试覆盖全部引用更新而不改变像素/尺寸、错误内容摘要、参数/对象类型冲突、no-op、严格坐标与bounds校验以及不误开放创建union。完整366回归365通过、1原符号链接权限skip：`.local/regression-366-bitmap-geometry-20261024.txt`。

## 未完成

位图公共创建/资产声明与像素替换、更多BMP格式和大图边界验证尚未完成；ISS-L02-bitmap-pixel-identity继续open并保留原IsEquivalent忽略像素失败证据。原字体quality持久化、复杂缓存/变体、共享电源接线移动、3969、层次/总线/flat、原生DRC/网表与完整PSpice闭环等仍需处理，门禁未提升。

下一推进受控BMP资产校验、冻结复制与创建声明，再接入原生创建和新进程完整DIB预期比对。无GUI、安装或真实设计修改，无提交推送。

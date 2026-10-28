# C03 完整验收审计（2026-10-28）

结论：原34项中的C03“位置/旋转/镜像/实际引脚热点”按原范围通过；总进度7/34（20.6%），完整目标仍active。只关闭这一查询门禁，不改变分母、后续写操作、电气、层次、图形渲染标准或已发布版本。

## 原要求与当前证据

原cadence-plan.md/C03要求四方向与镜像人工fixture、热点核对原生数据；依赖C01已passed。实际入口capture_get_part_geometry直接读取GetLocation/GetRotation/GetMirror和每个物理引脚GetOffsetHotSpot。返回设计定义级partId/实际pinId、脚号/名、revision，独立工作进程读取；生产代码不使用任何假设仿射公式来代替原生热点。

1. 原始失败对象的同一源DSN、真实R101电阻、公开创建并导入的混合GATE符号各8姿态，共24。写副本前冻结源定义框尺寸和defining local pins，仅用此前独立验证的width/height补偿模型生成新预期；没有用目标的observed/converted点生成预期。每个原生保存后新进程重开，24/24位置/姿态/脚号/名/热点准确，GetOffsetGraphicPoint额外与原生热点一致。定义框尺寸分别40x40、20x20、0x0，未强制改成居中的小样本。
2. 24/24实际stdio MCP公开几何读取与冻结预期相同，所有pinId在partId下，读出的revision与打开的副本一致。原文件重复U3两实例按partId分别定位，热点不混淆。错误对象、owned副本改动、关闭会话、新服务复用旧session均拒绝；源和旧oracle hash保持。
3. 当前MCP额外复验同构2单元/6逻辑pin行（5个物理脚号）和异构3单元/8行（6个物理脚号）的共享引脚几何，与原冻结单位/热点表一致；源SHA与早期原生样本一致。原手工BLOCK_A400,300及IN400,320/OUT500,320也在当前接口直接通过。层次块连通未由此接受。
4. 原100x60偏置非方形holdout已有8原生/8公开MCP通过，报告仍有效；原80x40 center假设失败保留。5项专属geometry测试本批全部通过，无skip，覆盖未知/外来目标、父级不一致、非法worker shape/重复或错pin身份/类型、读取期间源改动、worker错误和严格MCP参数。最近完整721项720通过/1全局symlink权限skip沿用上批，当前无生产代码变化；该skip属于仍未完整验收的环境边界，不冒称消除。

## 原失败为什么现在可以结案

ISS-C03-pose-matrix-1fc81bf46d原r1/m0实际值并未改变。审计将旧observedPins按旧位置归一化，与本批同原对象的新MCP热点归一化逐一比较，完全相同；旧expectedPins仍不等于observedPins。问题是早期测试假设围绕local零点转动，遗漏定义框width/height补偿，产生固定40单位偏移。此前尺寸/偏置holdout已区分错误center模型；本批进一步在原失败源和不同实际源上独立冻结并完成全姿态/native/public集成，因此可关闭“坐标模型/广泛来源尚未验收”的旧问题。旧报告、旧oracle、原失败范围原封不动留存，不把它们的passed改true。

此前C03证据中混有多单元复制/隐藏电源连线失败；这些电气写入条件仍留在L03/L05/D02/D04/H02相关门禁。当前共享脚“查询”复验已通过。早期shared-pin-read第一次失败还包含旧测试错误工具名capture_query_part_geometry；后续正确capture_get_part_geometry及本批当前接口已通过，其原失败日志也保留。

本轮新测试首次按U3位号选择遇到合法重复，在任何姿态写入前拒绝；新v2目录明确绑定原失败partId。该准备错误单独保留，未篡改源/原预期。单项研究探针中fullC03Accepted=false只表示探针本身不签完整门禁；本文件与c03-completion-audit/audit.json汇总原要求、所有当前矩阵和边界后签署C03。

## 范围与遗留

C03仍是原定义级读取范围。这里没有认证D02姿态写操作的全部电气保持、多单元放置/缓存替换、H02 occurrence/跨层网络、H03端口方向/连接或C05/V02字形/笔宽边界；这些原要求和失败均继续保留。本轮未新增工具、未修改生产读写实现，仍223开发工具；alpha/release和固定发布包保持，研发资料同步develop。机器证据见batch-126-evidence.json，包含逐要求audit、源/结果hash、原失败说明与之前remaining全文。

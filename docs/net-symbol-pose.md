# 已连接网符号位姿

`capture_plan_net_symbol_edit(operation="set_pose")` 接受绑定的 `symbolId`、`wireId`，以及完整 `location`、`rotation`、`mirror` 和独立 `expectedHotSpot`。只支持 scalar global/offpage 和一个两点、非空、正交的终端引线；计划预览列出原/新端点。另一端点固定，别的脚、连接对象或 alias 依赖移动端点时拒绝。几何重合不作为电气连通证明。

apply 在新 DSN 副本中同次修改符号和原引线。独立重开检查全部原生页内 pin/wire 成员、网络名、已建模连接对象、目标页器件位姿，以及符号的有效/用户/显示属性和14项字体字段。错误热点或节点预期的产物不开放，开始后的任务不重放；取消、恢复和幂等沿用原任务族。

## offpage 的明确重绑定策略

offpage 的旋转/镜像 setter 在本机返回 Failed1，不能据内存字段变化直接接受。方向变化使用官方构造接口和原 typed 缓存定义重建符号，复制用户/显示属性及字体。必须显式提供 `allowSourceCacheRebind=true`，且原 Source Library 是 DSN 缓存来源。该字段只允许绑定本次任务的输出 `design.dsn`；未授权或外部 OLB 来源拒绝。其他有效字段只允许声明的坐标变化。

预览中 `pose.recreate` / `pose.sourceCacheRebind` 明示此行为。结果的 `nativeSymbolRecreated`、`nativeSymbolId` 和 `sourceCacheReboundToOutput` 表明原生身份与缓存来源变化；输出会话中的查询 ID 属于新 revision。global 位姿和 offpage 纯平移保留原生实例。

原始脱离连接的移动、复杂/分支引线、跨页全局合并、occurrence 属性、未建模扩展、渲染、DRC 和 PSpice 地零语义不在本切片的通过范围。原失败报告和预期保留。16姿态、中文属性/字体、错误预期、取消、旧编辑和新服务无重放恢复见 [批次168](implementation/batch-168-evidence.json)。

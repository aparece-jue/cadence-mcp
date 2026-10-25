# 第四十七批：已有DSN缓存中的缺失单元补放

2026-10-24。原34项范围保持。新增1个计划工具capture_plan_cached_unit_add，复用现有multiunit placement的apply/jobs/cancel/recover/open，实际143工具。

## 原生机制与冻结预期

先在两个独立私有副本中验证：从已删除B的同构组和已删除P的接线异构组，按现有U501A的native identity取得同一DboPackage；GetDevice/GetCell及精确cached partName取得缺失单元，NewPlacedInst放入原base reference。只操作DSN已有缓存，不加载外部OLB、不创建新cache、不新增导线。明确设置组内继承的Value和PCB Footprint字符串字段，不认证实体封装。

原生prototype两例保存/新进程读取全部通过：独立源symbol spec冻结物理pin/name/hotspot/net，补回B.Convert与P.Normal；全定义、连接对象、新单元归属/几何/属性、旧单元native identity/geometry/Value/FP、cache逻辑元数据与源/产物hash保持。P.VCC8/GND7恢复到已声明网络。

## 公共任务实现

计划绑定session/ownerPartId/cachePartId，cachePartId来自capture_query_cache的同revision快照；同名view须按device区分。owner必须是内部multiunit placed definition、有稳定参考号；拒绝空号/U?、外来cache/package、已放device/full reference、来源组重复device或所有权冲突。组内Value/Footprint须存在且一致，供新单元继承；非默认覆盖一致性尚未做完整原生矩阵，L05仍partial。

调用者声明新单元pose、全部物理pin/name/global hotspot/net，以及所有旧page pinId连接；共享physical pad预期必须一致。仅同owner页面补放，不隐式编号、跨页移动或导线修改。现有持久kind增加operation=add_cached_unit，来源hash/计划digest/禁止重放等边界不变，group ledger仍256KB、payload160KB，固定JSON worker200KB。没有任意Tcl/eval接口。

保存后独立重开验证完整定义/连接对象、新单元完整位号/device/package及旧实例身份、全页原geometry/Value/FP、cache pin/shared/swap元数据、实际PlacedInst.GetPart缓存view名称、全页pin/wire同一原生网络对象及不同net隔离。此路径不声称完整矢量图形缓存或外部闭包认证；complete-package路径仍保留此前source pin/line比对。

## 实际MCP与故障验收

- 首MCP脚本只按view name挑选，误选已存在A.Convert，服务正确unit_already_placed拒绝，0写入；失败report保留。修正按device+part作用域定位，新v2真实143工具B/P两例均通过，不重写旧报告或重放旧账本。
- 错误热点oracle实际保存后cached_unit_hotspot_mismatch，open拒绝、重复apply不重放。来源外cache、漏旧pin、已放目标device、pending cancel及fresh apply/recover/open全部通过；来源/冻结oracle hash保持。
- 独立供电P补放：native实际保存后删receipt，首apply失败留账本；fresh MCP verify-only恢复、nativeCompletionVerified=false/mutationReplayed=false/cachedViewVerified/nativePageNetworksVerified通过，原产物hash保持。真实启动cancel、故意2s延迟对1s timeout都确认owned0并拒绝重放。
- 新7项host边界测试覆盖缺失设备、重复放置、完整位号与其他base冲突、外来cache、external owner、来源重复device和U?。完整325项324通过/1原symlink权限skip；早324绿色也保留。实际143工具契约同步。

## 未完成范围

本批不解决D02接线单元移动导致共享8/VCC page binding丢失，原失败/deferred继续。缺失unit跨页分配、非默认组属性覆盖矩阵、完整图形/任意命名异构cache导入、封装变体/缓存替换覆盖保持、flat/occurrence/总线/DRC/仿真闭环等原34项仍未完成。L03/D01整体partial，没有用工具数或测试通过率代替功能完成率。

下一独立推进复杂库/cache与图形身份，失败项保留队尾。无GUI、安装目录或真实设计修改，无提交或推送。证据路径与SHA256见batch-47-evidence.json。

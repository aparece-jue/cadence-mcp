# 第四十五批：同封装共享位号的完整组持久放置

2026-10-24。原34项范围保持，新增5个MCP工具，总142。完整310回归309通过、1原文件符号链接权限skip；间歇目录释放历史issue仍open。

## 工具契约与实现

capture_plan_multiunit_placement声明同一来源OLB package全部2..16个device，每个device只选一个part视图，明确base reference、公共Value、各单元pose/完整物理pin/name/hotspot/net。每组最多512逻辑pin rows、每单元最多500，源package/device/cell/part身份绑定，不能跨package或漏掉供电单元。期望旧页面连接用revision-bound pinId覆盖每条pin，保留共享位号及共享脚号的单元差异；不使用(reference,pinNumber)合并。

新增apply/jobs/cancel/recover，open_edit_result kind=multiunit_placement；取消路由进入独立控制线程。CaptureMultiunitPlacements复用既有持久任务的来源hash、计划digest、幂等与禁止重放。新固定Tcl adapter复制一份新cache，在同页放入所有单元，逐项检查状态后完成SavePage/SaveSchematic/SaveDesign。不新建导线，不改既有缓存。

保存后独立重开核对完整定义/连接对象、每单元完整位号和device/package ownership、单元作用域物理pin/net/实际热点、Value/footprint，逐个新原生进程比较实际PlacedInst.GetPart与来源pin/line视图；按nativeId核对原有页面全部实例geometry。原生pin/wire对象检查要求声明的同一网络成员属同一非空对象，两个不同声明网络不能共享对象。范围仍page-definition，非完整flat/occurrence。

同一physical number跨unit必须有一致的(connected,net)声明；两不同电源网和未解决的local/flat混合状态在创建账本前拒绝。源/副本/产物hash前后保持。payload160KB、group请求200KB和该类ledger256KB有界，其他任务原64KB记录限制保持；新增测试实际载入超过64KB的group记录并确认其他任务仍拒绝。

## 官方依据与运行问题

沿用本机主参考DboPartInst/DboPlacedInst、DboLib.CopyPackageAll、NewPlacedInst、DboPackage/DboDevice，以及共享脚显式迭代和已验证的pin/line对象方法；实例GetPart第529页，NewPinsIter第522页。来源文档hash见机器矩阵，未复制官方全文。

首次直接GetSchematic/GetPage定位在原生load阶段3969，失败账本/report保留；改用已验证的有界qualified-page native iterators，后续真实用例通过。没有声称解决历史跨页/port/新建DSN的全部3969问题。初307回归因旧工具数断言137而失败；更新为实际142后最终310项通过，原失败日志保留。ledger新增测试最初临时安装夹具缺tclsh文件，修复仅临时测试设置，没有修改真实安装。

## 真实验收

- v2真实142工具MCP同构A/B未连线、异构A/B/P未连线、异构A/B/P接入预先声明的VCC/GND底图共3主用例通过；每个输出保存重开、各单元源视图、单位网络/物理脚、原页geometry与hash通过。底图自身在写入组前按冻结全定义/连接对象单独通过。
- 同一页面在已有U501A/B组旁再放U502A/B通过，原共享位号/8号脚的各旧pinId得到独立覆盖；旧组nativeId/geometry保持。重复device、已有base/full reference冲突拒绝；错误热点oracle实际保存后group_hotspot_mismatch/open拒绝/重复apply不重放。pending取消及fresh apply/recover/open不重放通过。
- 独立接线异构组：保存完成后删native receipt，首次apply失败留存；fresh MCP仅验证恢复，nativeCompletionVerified=false、mutationReplayed=false，单位来源视图与原生网络仍通过且产物hash保持。启动cancel和延迟worker1s timeout均owned0。
- 最新真实MCP6个前置拒绝：共享physical8矛盾VCC/GND、混合connected/unbound、重复device、漏旧pin、已有位号、额外字段，均在建账本前拒绝；合法组仍可计划并取消，源hash保持。
- 终末第二组产物先保存逐字节同hash备份，再受控篡改；open/recover/apply全部target_changed，前三主输出、原主report和备份hash保持。原主report记录的是篡改前成功，第二组ledger产物当前故意不可用；备份位于.local/multiunit-artifact-tamper-20261024/retained-before-tamper.dsn。
- 完整310回归309通过/1权限skip；actual142契约同步。10项新host测试覆盖device/物理脚/旧pin identity及大记录边界。

## 原范围仍未完成

增量增加/删除/编辑单个unit、跨页分配、非line图形身份、任意命名异构cache导入、隐藏脚实例设置、封装变体、flat/occurrence/总线、真实DRC和Capture→PSpice闭环等仍待完成；原34门禁不提升为全部通过。L03/D01/D04整体partial。GUI/simmgr待授权未变。

下一继续group生命周期与复杂库/cache来源，不把atomic完整组替代原范围。无GUI、安装或真实设计修改，无提交/推送。报告路径/hash见batch-45-evidence.json。

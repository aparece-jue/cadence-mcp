# 第六十二批：C01定义查询完整验收

2026-10-25。依据原cadence-plan.md中C01要求“人工计数、空结果、重复名、精确筛选、分页、源hash一致”及标题中的不可变快照，补齐真实验收。此次无生产代码修改，无新工具，不修改原验收标准。

## 独立夹具与预期

执行前冻结expected.json。empty：1 schematic/1空page/0 part/0 pin。duplicate：ROOT、AUX两个schematic，两个同名SAME_PAGE及ROOT下EMPTY_PAGE；各非空页显式放R1和R10，共4part/8pin，每只原生R引脚1/2且不连线。私有固定脚本使用官方CreateDesign/NewSchematic/NewPage/CopyPackageAll/NewPlacedInst及完整保存链，仅创建新文件，不改源库或真实工程。没有以读取观察值生成预期。

## 原要求逐项证据

|原要求|实际验证|
|---|---|
|人工计数|两组固定预期与新进程重开查询一致；全部父子ID关系核对，每页R1/R10各一只、每只引脚1/2，空页无器件|
|空结果|空工程part/pin均0、duplicate的空页和不存在位号返回空|
|重复名|同名页位于不同schematic，pageId及父归属不同；R1跨页重复，各页精确选择互不混淆|
|精确筛选|R1不匹配R10，R和R100不误匹配；投影字段集合精确|
|分页|四类实体limit1遍历，全集计数、唯一ID、revision、终末complete；修改limit或跨会话使用cursor拒绝|
|不可变快照|对象全集和revision匹配快照及其摘要；新读取同对象一致；私有副本改变后原快照字节/摘要保持|
|陈旧与关闭|活动query/cursor/snapshot/reopen遇到副本变化全部target_changed；关闭会话后session_lost；陈旧会话可正常close|
|源hash|原夹具及三个官方样例源hash均保持，破坏仅针对MCP工作副本|
|释放与重复读取|两组各12次额外原生打开/关闭及重开，均完成；此为有界重复验收，不外推所有操作的资源无泄漏|

`.local/query-closure-20261025/report.json`两组实际167工具MCP验收通过；`.local/query-stale-final-20261025/report.json`补充活动陈旧/游标/快照和关闭验收通过；`.local/definition-query-final-20261025/report.json`当前代码重验FULLADD/CMOSCPU/TUTOR2，沿用原断言全部通过，确认未连接引脚的原兼容修复保持。

## 状态与范围

C01原4个issue均有既有resolved证据，当前官方原例再次通过。C01标记passed，范围仍为原计划的设计定义查询；occurrence和平坦层次连接分别归H01/H02，未因此通过。旧remaining中混入的共享电源接线、异构库复制和任意源放置问题属于D01/L03等写入/连接门禁，原失败记录完整保留，不能用这些问题永远阻止独立查询项结案，也不能因查询通过把写入问题结案。

34项状态现为1 passed、1 baseline_passed、20 implemented_partial、10 deferred、2 planned；整体目标active，A01最终整体验收继续待办。无生产更改，沿用并核对第61批所有代码/契约摘要与411回归410通过/1原权限skip，不无故重复全套；新专项均真实执行。167工具保持。

下一步继续按原明确条件核对其余门禁及实际缺口，优先完善属性来源、输入校验，再集中修复Capture原连接/保存和完整仿真联动。无GUI操作、无安装/真实工程改动、无提交推送。

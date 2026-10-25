# 第十六批：声明式库创建、多单元及放置闭环

2026-10-23。公开88工具，完整228回归227通过/1原symlink权限skip。L02/L03/D01/L05仍partial，整体34项必需范围active。

## 实现与契约

library_create.py/固定create_library.tcl实现一个新package的OLB声明，输入区分symbols(cell/part/逻辑pin/line)与devices(designator/位置/物理number共享swap映射)，不把设备级pin查询行数当作封装物理脚数。支持重复使用同一symbol的同构单元、不同symbol的异构/供电单元、shared物理pad与隐藏脚。要求每个device恰好覆盖该symbol的logical positions；共享物理号必须全部显式shared且name/type/swap一致；device positions连续，禁止重复/未用symbol和歧义cell/part名。图形线条保留重复数量，端点方向按无向line语义归一。pinType0..7、line style0..4/width0..2有本机原生正例。

固定factory在新job目录CreateLib，显式NewPinNumber position后建SymbolPin与line，完整保存；不覆盖既有OLB。spec≤32KiB及对象/坐标/字符串均有界，plan/digest/幂等/取消与不重放恢复沿用IsolatedJobs。新独立inspect_library_create.tcl读回完整device-scoped图、template、pin start/hotspot/type/visible/shared/swap、line几何/style/width；不按跨进程ordinal比较。

新增capture_plan_library_create/apply_library_create/library_create_jobs/cancel_library_create/recover_library_create/open_created_library六工具；open仅将verified且hash一致的新OLB导入普通library query/placement会话，不扩展公共读根。产物sourceFingerprint为spec digest，sourceKind=new_library_spec，区别于已有文件指纹；通用Artifact新增可选受限sourceKind字段，旧artifact字段仍兼容，未知字段继续禁止。

## 先失败后修复，证据保留

`.local/library-creates-20261023/report.json`四个原生worker均保存成功，但扩充metadata reader失败。只读诊断未改库，定位到向量迭代NULL结束后1022状态污染NewLPinsIter。隔离vectorState，并仅在NULL结束时允许0/1022，其他失败仍拒绝；不删除底层DboState对象。`.local/library-creates-recover-20261023/report.json`对原四份OLB仅recover/新进程核验，artifact hash未变、无创建重放，nativeCompletionVerified=false。

首次真实MCP `.local/library-create-mcp-20261023/report.json`后端已验证新库，但Envelope尚未允许artifact.sourceKind，响应序列化失败。补齐严格可选来源标记并加入旧/新/未知字段的契约测试。验收脚本另有未运行到的查询工具名拼写已改为现有capture_library_query。首次记录保留，最终新任务正反例见final目录。没有把之前响应失败假称通过。

## 真实MCP正反例

`.local/library-create-mcp-final-20261023/report.json`（88工具及全部schema）：

|声明|逻辑查询行|唯一物理pad|验证重点|
|---|---:|---:|---|
|电阻|2|2|完整outline、template、pin起点/热点、footprint|
|同构A/B|6|5|同cell复用、共享VCC、隐藏power pin|
|异构A/B/P|8|6|三cell、供电单元、跨unit共享pad、不同局部几何|
|全部pin types|8|8|type0..7、混合可见性、line style0..4/width0..2|
|中文/特殊字符|2|2|中文package及`A $[x];中文`作为数据保存，不执行Tcl|

每例原生保存、独立模板/图/几何检查、open/query通过。缺mapping、extra字段拒绝；故意错误homogeneous预期在真实保存后library_creation_mismatch，输出不可打开、失败不重放。pending取消、jobs分页、新server同key复用/再开通过。最后Unicode产物被故意追加字节作篡改负例，后续cached apply/open均拒绝；该负例保持已损坏，不冒充当前仍有效artifact。

`.local/library-create-faults-20261023/report.json`：真实保存后host删仅自有receipt，首次apply失败；新stdio MCP recover只核验原OLB并打开2pin，nativeCompletionVerified=false、hash保持、无重放。真实worker启动窗口cancel与1秒timeout均owned剩余0；不是全部保存中断窗口覆盖。

## 新库实际放置

首次联动脚本读取UTF8报告使用Windows默认GBK，在任何native操作前失败，记录于`.local/created-library-placement-20261023/report.json`；显式UTF8后用新独占目录验证。

`.local/created-library-placement-v2-20261023/report.json`：新server从verified resistor OLB开library session，复制第十五批自有空页DSN，R401放到(700,300)，physical1/A热点(680,300)、2/B(720,300)，参数4k7与MCP_RES_FP；保存/new-process/open_output与整份定义连接基线通过，源DSN hash保持。仍embeddedCacheClosureVerified=false；未把本例扩大为多unit共享reference放置或所有缓存更新已通过。

## 回归及剩余

6项新增主机测试覆盖完整pin map/position、shared metadata一致性、重复cell与未用symbol、语义排序、计划取消/篡改阻止native，以及严格Artifact来源契约。完整228回归227通过/1原symlink权限skip，契约同步final实际tools/list。

仍必需：其他symbol vector/font/渲染、alternate part与封装变体、正向交换组与复杂共享边界、全部native中断窗口/长期资源、库属性/引脚/图形编辑、cache替换/覆盖、同reference追加unit、编号/页CRUD/层次/总线/DRC、PSpice CLI等原清单。不因本批基本创建与三unit正例宣布整个库/多单元模块完成。

# 第81批：同一OLB内的封装家族

依据Capture Tcl官方参考DboLib.NewPackage（PDF p215）以及DboPackage独立device/template/footprint模型，扩展既有capture_plan_library_create的spec声明：原单封装对象继续兼容，也接受{packages: [单封装声明, ...]}。沿用同一apply/jobs/cancel/recover/open任务链，无新工具，实际193。

## 实现与契约

- 同一新OLB内声明2..8个独立package，每个保持自己的footprint名称、reference template、设备与物理脚映射，以及Normal/Convert等符号视图。跨封装package/cell/part名称大小写冲突拒绝；同一封装内既有共享cell/alternate-view规则保留。不隐式共享不同封装的native cell/part。
- 家族总上限16个symbol声明、16个device、512个逻辑pin、2048个物理映射；声明预算31000字节，最多32个位图、重复device读取所需DIB总量64MiB。各单封装原有边界仍执行。新建后任何包失败，整份输出不发布。
- 物理脚数按package分别去重再相加，避免把两个封装的同号脚合并。独立新进程读取全库，逐package核对完整已建模属性、pin映射/起点/热点/可见性/共享/交换组、矢量/字体/位图DIB摘要及顺序；全库采用ordered读取时，纯legacy-line的包也纳入有序期望。
- 位图按每个封装冻结与复验，同时实施家族总预算；图形与plain包混合可验证，不将原图片路径当作输出内容身份。沿用原任务digest、幂等、所属进程、停止后恢复和终末artifact hash保护。
- server联合输入schema/能力说明与实际193工具合同已同步。旧单封装payload和expectedGraph形状保持，未升级旧账本或自动重放。

## 原生与MCP验收

新建四组实际stdio MCP：两种footprint及不同物理脚号/中文名称；同构共享双单元与异构A/B/P组合；旧单封装；一个包含ellipse/32位位图、另一个包仅legacy线。所有组完整保存、新进程重开、包级footprint与人工声明pin表、物理脚计数通过。位图源在apply前移走，仍正确使用冻结字节，查询DIB摘要/顺序一致。第二包错误homogeneous期望被严格拒绝，不开放未验证输出。

新服务重开与幂等不重放、pending取消、输出篡改后的open/apply/recover拒绝通过。首输出故意附加篡改测试字节前保存valid-first-output.olb，其SHA256与原verified artifact一致；其他三组输出hash核对通过。保留原MCP报告而非将篡改输出称作当前有效文件。

四类原生故障通过：丢回执后由新MCP恢复且只执行一次；所属进程启动窗口取消；真实1秒超时；独立原生修改第二包footprint后apply及recover均拒绝library_creation_mismatch。取消/超时剩余所属进程均0。

另用原已验空页快照（先核对历史SHA256与零器件/零引脚），从同一有效新库分别放置两种封装到独立副本；手工声明的1/2与A1/A2脚号、中文pin名、[680,300]/[720,300]热点及各自实例footprint经保存重开通过。源DSN/OLB保持hash。首次放置harness误用了历史报告中的result字段，KeyError发生在建工作副本前；已改为该报告实际opened.workspaceId并检查原hash，原空失败目录保留，不记为产品原生失败。

8项新增host测试；完整回归508项，507通过、1原符号链接权限skip。描述/能力文案同步后不改运行逻辑。真实MCP与合同一致。

证据：.local/library-family-mcp-20261025/、.local/library-family-mcp-v2-20261025/、.local/library-family-faults-20261025/、.local/library-family-placement-v2-20261025/及regression-508-library-family-20261025.txt。工具为tools/smoke_library_family.py、smoke_library_family_faults.py、smoke_library_family_placement.py和私有故障worker fault_library_family_footprint.tcl。

## 未通过范围

本批只补上同OLB多封装变体的声明/持久创建/查询及两种单单元变体放置，不认证跨封装共享原生cell、任意外部库归并、实体PCB封装存在、物理pin swap执行、渲染效果或全种类字体持久化，也不代替层次/flat/隐藏电源/接线移动/缓存替换等原门禁。L02/L03完整功能仍partial，原问题与未通过条件保留，34项仍6 passed/1 baseline/9 partial/16 deferred/2 planned。目标active；无GUI、安装/真实工程修改或提交推送。

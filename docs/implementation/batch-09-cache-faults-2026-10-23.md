# 第九批：放置故障与DSN缓存查询

2026-10-23。新增一个只读MCP工具，现65工具；34项required与最终门禁不变，目标active。没有GUI、安装目录或真实设计写入，不提交推送。

## 放置专属原生故障验收

原创tools/smoke_placement_faults.py在独立job输出中完成：

- 原生真实保存后，仅删除该测试自有job的receipt，apply未误报成功。新stdio MCP进程调用capture_recover_placement，只核验已有DSN、库指纹、pin-net/热点/值/封装，返回verified_recovered/nativeCompletionVerified=false/mutationReplayed=false；随后通过MCP打开输出。修改执行计数仍1、目标hash不变。
- 另一个计划在真实worker挂起创建并放入私有Job Object的启动窗口取消，job=cancelled，remainingOwnedProcesses=0。
- 测试专用adapter先恢复合法生产argv，再刻意延迟2秒；1秒deadline触发timeout，job=failed、owned残留0。这里验证的是**刻意延迟worker的超时控制**，不是正常放置性能，也不是保存中断的原子性证明。生产接口没有延迟/eval参数。
- 源设计、官方OLB及输入工作副本hash保持不变。故障测试未改动真实工程。证据`.local/placement-faults-final-20261023/report.json`；初版故障记录在`.local/placement-faults-20261023/report.json`。

尚未覆盖任意native保存阶段的MCP并发取消、全部中断窗口或所有损坏输出恢复；不能仅因复用任务基座而认为这些分支通过。

## 缓存读取及有界离线案例

只对第八批自有两份OLB输入（job/library.olb、原library session的工作副本）暂时改名，源/目标绝对路径先解析并检查都位于该测试batch/work内，finally恢复原路径及hash。没有锁住、移动或改写安装内ANALOG.OLB。新Tcl进程从另一个只含DSN的工作副本重开，完整定义摘要与R103物理引脚/热点预期保持，读取期间两条已知路径确实不存在。

`.local/cache-offline-4383bfd6a9/report.json`记录此案例通过且两文件准确恢复。**未追踪所有native文件访问，安装库仍可访问，不能据此证明所有可能fallback均不存在。** fullCacheClosureProven仍false，正式placement结果embeddedCacheClosureVerified仍false，不缩减L05完整闭包/同步要求。

## 新增capture_query_cache

独立模块capture_cache.py及固定inspect_cache.tcl，从绑定的不可变DSN通过GetDesignAndSchematics遍历cache package/device/cell/part/pin。该adapter由本仓库原创OLB遍历代码复用，未复制官方实现。

- 以scope=dsn_cache_device_definitions返回，明确不等同于外部OLB。source session/当前DSN hash绑定，支持entity、准确packageName、分页及签名绑定cursor。
- 复用严格库图模型校验；≤100000对象和32MiB native文档，成功后缓存到该session，失败文档不进入cache。陈旧或关闭session拒绝，未知额外参数拒绝。
- 结果externalSourceLibraryVerified=false、cacheSynchronizationVerified=false；不提供cache替换或库编辑入口，缓存对象ID不应跨保存/新session持久复用。

真实stdio `.local/cache-query-mcp-20261023/report.json`通过：在R103已保存DSN中按预期的host生成cacheName查询，package/device/cell/part各1、物理pin2（1/1、2/2），pinType4且visible、Footprint AXRC05。limit=1分页、空过滤、额外参数及关闭session拒绝均通过；源DSN hash不变，实际65工具清单已导出。

3项新增主机测试通过：缓存scope/分页/查询签名与重复读取缓存、准确过滤/陈旧snapshot，以及畸形native文档拒绝并不缓存。完整回归195项：194通过、1项原有Windows文件symlink权限跳过，跳过不是通过。P02历史目录清理issue不因本次未复现而结案。

## 资料、复现与剩余工作

读取依据沿用Capture官方设计/库对象模型及已核实的GetDesignAndSchematics、NewPackagesIter、Device/Cell/Part/Pin API；DboDesign继承的库遍历接口经本次真实运行确认。原生过程控制沿用已有Windows Job Object框架。官方文件不提交入仓库。

tools/smoke_placement_faults.py接受install-root/workspace-root/source/library；使用第六批原创新双电阻MCP_PLACE设计和官方ANALOG源，只写自有副本。tools/smoke_cache_query.py接受install-root/workspace-root/source/cache-name，读取已知放置结果；输出目录必须不存在。离线改名探测为一次性本地证据，不是生产API流程，不能在活跃共享工作区中照搬。

证据hash见batch-09-evidence.json；`.local/regression-195-cache-20261023.txt`是完整回归日志。L05仅只读查询切片通过，导入/替换/更新、实例覆盖/引脚映射与通用依赖闭包仍待完成。D01复杂unit/variant和全部姿态也保留。后续继续D03修改删除/连接矩阵、D05图形及V03等独立项，再按队列集中修复遗留。

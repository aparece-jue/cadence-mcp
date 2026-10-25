# 第五十一批：package属性与进程退出确认

2026-10-24。实际155工具，整体目标active，原34项范围保持。

## package业务

依据本机OrCAD_Capture_TclTk_Extensions.pdf p595–598的package模板/PCB库名/封装名getter/setter，p165–169和p186–188的用户属性iterator、创建/删除、类型/权限与字符串setter。

新增capture_query_library_package_properties和plan/apply/jobs/cancel/recover_library_package_edit共6工具，open_edited_library增加kind=package，默认pin兼容。明确区分模板与device A/B标识、显式空属性与删除；只认证原生editable string(type0)设置，拒绝保留字段影射、重复/大小写别名、无变化、锁定/类型冲突。模板与原生package designator getter语义不一致时拒绝推测修改。

计划绑定源和冻结before/expected文件hash；独立读取全体package属性及已建模定义、模板、引脚起点/映射和有序基础vector。仅写新OLB副本，保存后独立重开逐项比较。每批≤64用户操作、写值≤4096字符，计划≤48KB/账本128KB；每package读取≤1024属性/值≤16384字符，总字符预算4Mi，属性JSON≤16MiB。

首轮library-package-edits报告整体false：前三步通过，清空footprint时实际字段正确，但expected定义行未按新值重新排序，严格校验拒绝。修正规范化排序并保留原失败后，v2独立5步创建/改字段→更新/空值→删除→清空字段/最后属性→还原全部通过，24pin/全部已建模图形、另一package属性保持。保留字段/重复/缺失删除/noop不生成durable job；缓存命中后的副本篡改和关闭后查询拒绝；fresh生命周期不重放。

实际故障矩阵通过回执丢失fresh verify-only恢复/nativeCompletionVerified=false/hash保持、启动取消、受控timeout；额外修改另一package或Convert vector时拒绝/open拒绝/不重放；终末输出先备份再篡改，open/recover/apply拒绝。两次真实DSN放置验证非空PKG_51和显式空footprint均正确继承，原连接/图形身份保持。

初始package-property-probe的Tcl源码中文literal受默认脚本编码影响，不作为Unicode验收；正式MCP以UTF-8 JSON传值，中文、多行、特殊字符均按独立字面预期验证。没有认证外部footprint实体、已有DSN缓存更新、自定义用户属性实例继承、原生自动编号、任意类型属性或所有库对象属性。

## 已复现目录释放问题

原352回归再次在timeout后TemporaryDirectory清理发生WinError32/5，原日志保留。微软说明TerminateProcess是异步操作，需要进程句柄的退出信号确认；TerminateJobObject相当于对所属进程终止：

- https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess
- https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list

独立诊断在Job ActiveProcesses=0之后观察到两组各60次根/子句柄仍未signaled；工作盘49/60、系统临时盘14/60不能立即删除自己的空目录。修正为持有所观测Job后代句柄并核验成员身份，Job排空后等待根/保留进程signaled再返回；异常回调也终止并等待后才释放句柄，等待总界限5秒。没有固定sleep替代退出确认，没有忽略清理错误。

结果新增rootExitSignalConfirmed、observedProcessExitSignalsConfirmed、observedOwnedProcessCount，明确是根与已观测成员，不宣称枚举每个极短寿命进程；Job活动数仍确认进程树排空。修正后两盘各60次均0即时删除失败/0根子未退出。新增即时目录删除和三代早退wrapper测试，原异常回调测试收紧到返回后0等待已退出；原后代、非目标存活、退出码和句柄泄漏测试通过。ISS-P02-process-directory-release-152按这个已复现的归属进程退出时序问题结案，不等于完整P02/所有资源门禁通过。

修正后真实Cadence package故障链再次通过；独立新CIR、OUT/DAT的PSpice DC分压2.5V数值预期通过，源hash保持，没有复用旧求解输出。

## 基线与剩余

新10项package和2项进程测试；两次完整354均353通过/1原符号链接权限skip，实际155工具契约同步。原始352失败及所有业务失败、修复前后诊断均保留，路径和hash见batch-51-evidence.json。

34项仍1 baseline_passed/21 implemented_partial/10 deferred/2 planned。字体quality、其他图形/库属性、bitmap/nested symbol、缓存/变体、接线移动、层次/总线/flat、原生DRC/网表与PSpice闭环等原范围未完。下一按冻结预期复核原保存/读取3969，再推进独立剩余功能。无GUI、安装或真实设计修改，无提交推送。

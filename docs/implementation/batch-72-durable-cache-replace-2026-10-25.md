# 第72批：持久缓存替换任务与严格独立验收

日期：2026-10-25。新增5个实际MCP任务工具，总数184。L05没有完整通过；一项异构未接线组出现非预期GND连接，失败保留后移。全部操作仅作用于独立副本，无GUI操作、安装/真实设计修改或提交推送。

## 公开工具与受支持操作

新增capture_plan_cache_replace、capture_apply_cache_replace、capture_cache_replace_jobs、capture_cancel_cache_replace、capture_recover_cache_replace；原capture_open_edit_result新增kind=cache_replace。

计划按第71批已验证的源库+包名绑定选择整个实际缓存组。必须为每个受影响partId声明替换libraryPartId和完整物理引脚/名称/热点/连接表，不能只改传入实例。当前兼容替换保持package size、device designator、物理脚号集合、端子热点及既有网络；改变封装结构、脚号/热点/网络或外部设计依赖需单独验证的映射/重布线流程。typed或source-binding用户覆盖拒绝，原类型持久化缺口不被隐式绕过。

冻结DSN、OLB、期望证据及摘要。新owned目录独占复制输入；固定worker先核对实际完整受影响组，再执行ReplaceCache(1,1)。原生preserveRefDes本身不足以保持状态，worker显式按nativeId恢复位号、Value/PCB Footprint和确证的string用户覆盖；全保存链后独立重开。

独立验证包括：全定义引脚/网络和连接对象、所有实例身份、所有实例已建模几何、有效/显式用户属性（含nativeType/可编辑/可删除标记）、显示值/位置/旋转/类型/颜色、来源明确的全部缓存逻辑图，以及每个实际放置视图与冻结源符号比较。仅四个明确Source/Graphic字段按新绑定改变，其余未声明状态必须保持。完整继承来源、显示字体/渲染、未目标缓存vector内容、occurrence连接、实体封装、DRC和电气行为仍未认证。

任务复用持久幂等账本和owned进程树。开始后的写入不重放；取消/超时确认进程退出，恢复只验证现有字节。只有verified输出可打开，终末复用同时检查DSN及私有OLB摘要。关闭输入查询会话不取消已经冻结的计划。

## 一次扫描全部实例状态

新固定只读扫描器在一个原生进程中读取全部实例几何及属性层，避免为每实例重复启动解释器。最多128实例、每层512属性、每实例500引脚、8MiB属性文字、32MiB结果；超限拒绝，无静默截断。独立实例清单核对完整覆盖和nativeId。

首内部探测在drawn层次端口GetPinNumber处遇到1021，尚未执行替换，原失败和调用栈保留。drawn端口没有placed物理焊盘编号；现在显式记录physicalPinNumbersApplicable=false及numberState=1021/空编号，同时保留其名称/热点。该状态仅在drawn及空编号组合接受；placed或其他错误仍拒绝，不把无物理脚号描述为成功读取。修正后全实例扫描及内部替换任务通过。

## 实际通过证据

- `.local/cache-layer-preservation-20261025/report.json`：原两目标显式user属性、已建模display属性和预期几何只读对照通过。
- `.local/cache-replacement-task-probe-v2-20261025/report.json`：原接线夹具全实例状态读取、内部持久计划/实际替换/独立重开通过；首v1失败保持。
- `.local/cache-replace-mcp-20261025/report.json`：原接线夹具及新增中文/特殊字符MCP_TAG、非默认Value显示位置[17,23]/旋转2的自建副本，两组真实MCP全部通过。完整组/网络/热点错误预期拒绝；关闭输入会话后执行、verified打开、任务列表、待执行取消、新服务恢复/幂等和DSN/OLB分别篡改后拒绝通过。两个终末输出按反例故意篡改，不作后续正例源；原输入保持。
- `.local/cache-replace-faults-20261025/report.json`：7项全部通过：丢回执后fresh verify-only、通过cancel方法在启动窗口取消、真实1秒写入超时、第二个固定native worker实际破坏未目标实例Value后拒绝，以及源DSN/源OLB/冻结期望分别改变时启动前拒绝。进程退出信号及remainingOwnedProcesses=0核对，未验证输出拒绝打开、不重放。
- 原多单元预期不变：`.local/multiunit-cache-replace-20261025/report.json`中同构双单元（含Normal/Convert）和已接线异构A/B/P供电组通过。完整3组原DSN/OLB与计划摘要保持在source-unchanged-audit.json逐项核对。

## 异构未接线GND失败，未验收通过

同一多单元报告的hetero-unbound失败，整体report保持false。新worker保存后，严格验证发现原声明未接线的U501物理7号GND脚变成connected=true、net=GND。连接对象图本身不变，不能因此忽略原生引脚网络变化。

`.local/hetero-cache-replace-failure-audit-v2-20261025/report.json`只读复核独立冻结预期：唯一pin差异为上述GND连接；未重放，源/输出和读取前后原失败账本摘要不变。首诊断的账本哈希比较写法缺少独立前值，未采用其账本保持结论；v2已以真实前后摘要修正，原记录保留。

登记ISS-L05-heterogeneous-unbound-gnd-replace，根因未证明，不改原unbound预期、不将错误副本开放。该项后移，L05完整门禁状态改deferred，已有通过切片保留。原ISS-L05-native-replace-preservation也继续open，不能用本批部分成功代替全部覆盖/继承/多单元要求。

## 回归与下一步

新增8项host覆盖完整影响组、声明源device/view、物理脚/网络/热点保持、typed/source覆盖拒绝、完整状态身份/flags、drawn不适用状态和同名cache/local来源。与第71批5项针对性共13通过；最终456完整回归455通过、1原文件符号链接权限skip。实际stdio契约184同步。

34项现在5 passed、1 baseline_passed、15 implemented_partial、11 deferred、2 planned，整体active。优先继续其余独立编号/库/原理图验收，最后集中处理本次GND及其他原生连接/保存遗留；没有将未通过项计为完成。

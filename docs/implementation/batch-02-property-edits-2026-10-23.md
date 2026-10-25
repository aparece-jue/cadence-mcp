# 自主开发第二批：独立副本属性编辑（2026-10-23）

总目标仍为active，34项必需功能尚未全部实现/验收；不提交集中评审。前批失败的L02/P02/H01仍在后移队列，未被改成通过。本批推进与其独立的E01。

## 实现

- 新增capture_plan_property / capture_apply_property / capture_property_jobs / capture_cancel_property / capture_recover_property，共36个实际MCP工具。
- 当前批准字段为已有Value和PCB Footprint，目标必须是当前不可变会话内、页面范围位号唯一的定义。共享位号/多单元明确拒绝，交专门操作。Value字符串修改不等于替换元件型号/引脚模型；footprint字符串不证明实体封装存在。
- 每次apply创建新的自有输出DSN，不写源工作区或Capture GUI当前工程。计划包含源hash、明确旧新值、目标定位和定义级基线摘要；15分钟有效、按摘要和幂等键持久绑定。Win32私有Job Object在恢复线程前保存worker PID，超时/取消/宿主崩溃关闭句柄时终止自有进程树。
- 完成官方page/schematic/design完整保存链，再以独立新Dbo进程读取磁盘设计和属性，验证明确新值及修改前的定义/引脚网名多重集合。它是保留现状的前后比对，不是从修改后数据生成预期，也不是occurrence/原生DRC/仿真验收。
- 已started/failed/cancelled操作不重放。恢复仅在旧worker可证明停止后读取已有输出并验证；恢复产物可通过，但nativeCompletionVerified=false。用户数据源与输入副本始终保持不变。失败/部分输出留在隔离job中，不自动回滚或覆盖。
- 成功输出附artifact指纹、输出工作区相对位置、验证范围；designPassed=null、electricalBehaviorVerified=false。同一幂等键的已验证结果在新服务器内也只读取旧结果/核对文件hash，不重做修改。取消为尽力请求，最终状态通过jobs查询；已完成结果不会被描述成回滚。

## 实际验收

标准stdio MCP在FULLADD官方样例的副本中定位FULLADD/FULLADD/U1，分别修改PCB Footprint、Value及含中文/引号/反斜杠/换行/花括号/美元符的footprint字面值。三个输出均保存、新进程重开、准确读回且定义基线保持；源安装样例与输入工作副本hash均不变。

MCP同时拒绝未批准Implementation字段与共享位号目标；待执行取消后apply拒绝重放；持久jobs分页返回partial。退出服务后启动新的stdio服务，以相同计划/幂等键得到相同产物，plan记录hash保持不变。

另以真实Dbo工作进程注入：保存成功后删除回执，首次结果明确失败；新服务只核验已保存副本并结案为verified_recovered，未重放、文件hash不变、nativeCompletionVerified=false。另一次在原生进程已分配Job Object但尚未恢复线程的窗口发送取消，结果cancelled，remainingOwnedProcesses=0。两项故障验收也保持源文件和输入工作区hash不变。

完整自动测试134项：133通过，1项原有文件符号链接权限跳过。新增10项验证持久幂等/新服务、幂等冲突、过期/摘要/路径、预检、待执行与活动取消、仅核验恢复、分页、批准字段/歧义目标、定义基线。此前通用进程树真实测试仍覆盖无关进程保护、子进程、超时、取消、挂起回调失败和句柄释放。此次无桌面操作。

证据：.local/property-stdio-20261023/property-edits-report.json和tools-list.json；.local/property-faults-20261023/property-faults-report.json；最初直接API正例.local/property-write-f42c3bc890/report.json。副本/官方原始输出在忽略目录，不进入公开源码。

E01仍标implemented_partial：更多批准参数/型号字段和最终联合门禁待后续。接下来继续C04连接对象、C05文字图形与E02属性新增/删除等独立工作；最后集中处理后移故障。

# 原生总线成员与入口查询

开发版新增 `capture_query_bus`，开发版共221个工具。先通过普通工作副本接口打开 DSN，传入其 `sessionId`；`entity` 可选 `bus`、`scalar`、`entry`，可选精确 `pageId`、不透明 `cursor` 和1..1000的 `limit`。

- bus 返回原生计算网络名、几何分段、位宽、成员的原生顺序，以及 Bundle 标志。数组位置和名称都保留，不自动排序或把字符串相似视为同一网络。
- scalar 返回原生分支网络名和几何。
- entry 返回两个端点及原生 `GetEntryWire`/`GetEndWire` 所引用的线段身份。空引用保留为 null；引用绑定本页，不将几何相交推断为连接。

读取基于不可变工作副本。每次查询都复核源指纹；游标绑定会话、类别、页面及页长。原生扫描与Python解码均限制数量/类型/文本/引用范围。返回的 wireId/entryId 是快照内身份，不能拿到新会话中作原生句柄。

本机官方依据：Capture Tcl/Tk Extensions 的 PlaceBus/PlaceBusEntry（PDF117页）、BusEntry端点与引用（581–584页）、DboNet.GetNetName（730页）和Bus成员（738–740页）。原读取草稿使用 GetName，实际命名总线返回状态1037；独立只读对照证明 GetNetName 正确读取计算网络名，现生产读取器采用后者，每次仍严格检查状态，没有忽略错误的回退逻辑。

原生编辑命令已构造并保存八位 `DATA[7..0]` 样例，独立进程可重开。预先冻结的原几何保持：竖直总线(600,200)→(600,700)，8个入口(600,220+50i)→(620,240+50i)，8个分支DATA0..DATA7。入口插入把总线自然拆为9段；真实MCP查询验证全部分段、每段位宽/7..0成员顺序、8个入口的两端原生引用和对应分支名，包含逐条分页、空页、会话/页面/页长游标隔离、3次额外开关及缓存防陈旧检查。

开发版另有5个受限总线写工具：`capture_plan_bus_create`、`capture_apply_bus_create`、`capture_bus_create_jobs`、`capture_cancel_bus_create`、`capture_recover_bus_create`。通过显式guiSessionId/hostProject绑定当前干净宿主，只在任务副本中执行固定编辑命令，保存关闭后恢复宿主。总线限竖直普通总线、2..128个连续成员；每个声明分支包含index、entryPoint、endPoint、wireEnd、expectedBusAttached。目标页所有物理引脚须明确声明expectedConnections，其他页保持。

分支可明确不完整，但不会自动补齐。原降序、升序、缺分支、脱离入口四例已通过MCP创建及独立重开；后两例的`localEntryRoutingComplete=false`。已有DATA总线旁新增ADDR后，原命名几何/成员顺序/入口引用保持，共16入口。真实R501.1接PIN0且原MCP_LINK保持；错误pin预期在实际保存后拒绝，产物不作为verified结果开放，禁止重放。pending可取消；已开始宿主任务不通过终止Capture取消。真实完成后观察丢失保留围栏，新服务仅核验恢复，不重发写操作。

结果的`routingScope=local_bus_entry_structure`，`designPassed=null`；完整八个物理引脚成员、重复层次、嵌套Bundle及原生DRC仍未通过。一个真实引脚切片不能证明全部总线电气语义。原H04完整门禁没有通过，旧独立构造3969失败保留。

验收汇总见 [batch114](implementation/batch-114-evidence.json)。完整回归668项，667通过、1项原文件符号链接权限跳过；本轮不修改安装/真实设计，不自动提交推送。

公开写任务及故障/引脚验收见 [batch115](implementation/batch-115-evidence.json)。本批完整回归676项，675通过、1项原权限跳过。

## 八物理引脚的原生成员查询

`capture_query_bus(entity="pin_member")`返回同页定义pinId、busGroupId、HasMember、GetPosition与GetMember原生指针一致性（不公开句柄），包含非成员行。成员次序不排序；预算/完整配对覆盖/原定义保持和源指纹严格检查，分页游标绑定会话/页长。四电阻八引脚升序、降序、缺分支、脱离入口均原生及MCP通过。脱离入口可能仍因显式命名网络而属于总线；成员查询不证明入口布线完整，也不证明occurrence/Bundle/DRC。alpha.2独立安装复测通过，详见batch116。

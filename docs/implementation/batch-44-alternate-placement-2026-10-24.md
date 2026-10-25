# 第四十四批：公共放置的来源绑定替代视图

2026-10-24。原34项保留；公共工具仍137，契约由真实stdio同步。完整300回归299通过、1原符号链接权限skip，间歇目录释放issue仍open。

## 公共业务变化

既有capture_plan/apply_placement继续绑定同一DSN/OLB不可变来源、页面、device、part ID及人工声明的pins/hotspots/nets。此前复制多part cell后只按旧partName定位，无法处理重命名的Normal/Convert。edit_place.tcl现在检查复制前后part计数，源part唯一；对于多视图，优先绑定可核实的源名或cell前缀替换后的缓存名，同时比较pin/line signature；无名称身份时必须恰有一个完整signature匹配，禁止用迭代顺序选视图。

新增dbo_part_signature.tcl核对逻辑position/name/electrical type/visibility/start/hotspot以及全部线条start/end/style/width，有计数上限。遇非line图形类型明确拒绝，不忽略。单视图沿用原行为，并不声称增加该分支的完整图形认证。首次引脚迭代器末尾1022被当错误，保留失败输出；按本机正常NULL结束状态处理1022，其余错误仍拒绝。

capture_place.verify对多视图新增固定inspect_placed_view.tcl，在保存后的独立原生进程比较源库选中part和DSN实际PlacedInst.GetPart的pin/line signature。前后同时核对输出与私有源OLB hash，并继续原定义、连接对象、热点、pose、Value/footprint与原来源hash门禁。返回sourcePinLineViewVerified明确是否执行该检查。它不是所有图形属性、文字/圆弧/多边形、外部缓存依赖或occurrence认证。

## 实际验收

- 最终v3真实137工具MCP：canonical及arbitrary source names各Normal A/Convert B，4次创建新cache/保存重开/输出打开成功；错误另一视图热点期望实际保存后拒绝，输出不可打开，重试不重放；新MCP进程apply/recover/open不重放。四次sourcePinLineViewVerified均true。
- 独立新库：两个视图的pin表完全相同，仅line图形4条/5条不同；源OLB完整声明图保存重开通过。真实MCP两次放置均选中正确图形，独立读取实际实例分别4/5lines，错误热点负例、fresh lifecycle及来源/oracle hash保持通过。证明选择不是只比较pin热点。
- 回执丢失：Convert5line真实原生保存完成后删回执，首次apply失败保留账本；fresh MCP只验证恢复，nativeCompletionVerified=false、mutationReplayed=false、sourcePinLineViewVerified=true，产物hash保持。真实启动取消和延迟worker1s超时均确认owned0。
- 最终完整回归300项299通过/1权限skip。工具契约实际137同步，工具说明和capabilities标记实验pin/line身份范围。同步辅助脚本的缺少read-root及相对路径启动错误已修正，仅影响元数据读取，未改设计。

## 未完成范围

完整同包多单元共享reference持久任务还未实现；源cache命名非标准的异构多cell复制、其他图形类别/全部显示字段、隐藏电源实例设置、封装变体和原34项其他门禁仍待完成。L03/D01等整体保持partial。下一实现共享reference的package-aware计划/执行/保存验证与恢复，沿用前两批独立电源网络和短/开故障oracle。

无GUI操作、安装目录或真实设计修改，无提交或推送。证据与保存后视图计数见batch-44-evidence.json。

# 第七批：持久连线业务工具

2026-10-23。实际MCP工具由54增加到59，统一Server与既有隔离任务框架不变。34项required保持原范围，目标active。本批未操作GUI、安装目录或真实工程，未提交推送。

## 新增接口及保存闭环

- `capture_plan_wire_add`：给定不可变session/page、两端点、scalar alias名，及目标页**所有既有引脚**的明确连接预期；可指定alias锚点、保存后的完整导线路径、alias所属导线的原生canonical net预期。
- `capture_apply_wire_add`：只写新DSN副本，固定native命令，完整保存page/schematic/design，新进程独立打开并核验后才返回verified artifact。
- `capture_wire_add_jobs`、`capture_cancel_wire_add`、`capture_recover_wire_add`：沿用持久计划/digest/15min期限、幂等、不重放、分页、pending或自有worker取消、原worker已停止后的只核验恢复。
- `capture_open_edit_result(kind="wire_add")`：只允许已verified/verified_recovered、hash仍一致的结果进入新不可变session；不扩大任意文件读取根。

新增源码为`capture_wire.py`、`adapters/edit_wire_add.tcl`。native用schematic/page准确名称遍历定位，唯一匹配后释放iterator，再创建线和alias。没有跨进程复用ordinal对象ID，也没有开放Tcl/eval/方法名参数。错误回执包含具体phase。

## 修改前预期与修改后核验

1. 引脚预期必须恰好覆盖目标页现有全部引脚；未知/重复/共享歧义、错误页名、空net与connected矛盾均拒绝。其他页面定义/引脚网络保持修改前基线，不能从读回数据替换期望。
2. 默认保存几何为原page所有wire path加一个新segment。调用方也可提前声明分段/合并后的paths，但其整数直线/投影区间并集必须**恰好**等于旧几何加新段，不能夹带漏删或新增段。几何并集不代表电气junction。
3. 保存后按稳定schematic/page语义定位，核对整份定义pin-net摘要、完整wire paths、alias名称/锚点以及global/port/offpage/NC等其他连接对象字段。wire路径方向可反转，结构路径仍按提前声明的完整多重集合核对。
4. 每个alias锚点必须落在其实际owner wire上；新增alias唯一定位后，进一步核对owner wire的原生net名。默认期望为输入netName；遇到已有网络的canonical name需明确传expectedWireNet，不能由observed补写。
5. 源工作副本hash在计划、复制、核验阶段检查，输出hash在独立重开前后核对。≤1e6整数坐标、≤500个page pin预期、≤500 paths/10000 points及48000-byte计划上限均在host检查，超限明确拒绝。

结果明确保留`wireOnlyNetIdentityVerified=false`：新增alias owner的net名通过不等于所有无引脚线段的网络身份或occurrence连通均已通过。还未核验完整junction语义、native DRC、字体/渲染避让以及其他器件属性；不得将artifact validated当作全设计通过。

## 验收

### 主机逻辑与协议

新增10项测试全部通过：完整pin表/共享身份/非法范围、非scalar alias与离线锚点拒绝；任意整数斜线/正交线段分段并集、平行偏移/缺口/额外段负例；明确分段预期；源不变/陈旧拒绝；独立读回错误net、错误wire几何及错误alias-owner net拒绝；跨序号的语义inventory摘要；严格MCP额外字段、pending取消与jobs状态。这些mock测试不代替原生行为。

最终完整回归188项：187通过，1项原有Windows文件symlink权限跳过；跳过不计通过。P02历史目录清理问题本次未复现，仍不结案。

### 真实stdio MCP

`.local/wire-add-stdio-owner-20261023/report.json`全部通过，实际59工具schema已导出并校验：

- 在既有双电阻测试副本，按提前声明四脚表计划/执行MCP_MIDDLE线和alias，保存、新进程完整核验及`capture_open_edit_result`衔接通过；新增alias owner实际net=MCP_MIDDLE。
- 同一四脚表经已有MCP compare工具4条通过；它仍是selected definitions，41个其他脚不在人工表内，不宣称全设计连通。
- 把独立预期故意改成4脚全无绑定：native真实保存后被`unexpected_connectivity_change`拒绝，未开放未验收输出，重复apply返回write_not_replayed。失败不是自动修正期望或重复修改的理由。
- pending取消后不能apply；jobs以limit=1完整分页，状态包括verified/failed/cancelled。未知额外参数被协议拒绝。
- 关闭并启动新Server后，同一幂等键返回既有artifact且mutationReplayed=false；已verified输出可再次打开。

### 真实进程故障

`.local/wire-add-faults-mcp-20261023/report.json`通过：

- 自有worker真实保存完成后，测试host删除其native receipt；apply未静默当成功，job保留failed和已保存artifact。
- **新启动的stdio MCP进程**执行`capture_recover_wire_add`，仅核验既有文件，返回verified_recovered/nativeCompletionVerified=false/mutationReplayed=false，并通过MCP打开输出；修改执行计数仍1、目标hash不变。
- 另一个新计划在真实worker已挂起创建并归入私有Job Object的启动窗口取消，结果cancelled、自有残留进程0；源及输入工作副本hash未变。这是native-start取消专项；不伪称覆盖了任意保存阶段的MCP并发取消。

## 证据与复现

原生依据沿用Capture主PDF432/434页NewWireScalar、495–496页NewAlias及已核实的完整保存链；字体参数使用此前已探测的固定LOGFONT helper。测试不依赖PDF或桌面。

- `.local/typed-wire-174a550d24/report.json`：首个内部typed plan/apply/save/reopen/idempotence通过。
- `.local/wire-add-stdio-20261023/report.json`及`wire-add-faults-20261023/report.json`：初版工具实际验收。
- `.local/wire-add-stdio-owner-20261023/{report.json,tools-list.json}`：新增owner-net断言后的最终MCP协议与正反例。
- `.local/wire-add-faults-owner-20261023/report.json`：owner-net版本的native故障/直接API核验恢复。
- `.local/wire-add-faults-mcp-20261023/report.json`：最终新stdio MCP恢复及native-start取消。
- `.local/regression-188-wire-owner-20261023.txt`：最终完整回归。hash见batch-07-evidence.json，contracts/tools.v0.1.json同步最终59项真实清单。

公开原创`tools/smoke_wire_add.py`和`tools/smoke_wire_faults.py`均接受install-root/workspace-root/source；source须为第六批构建的MCP_PLACE双电阻副本，输出目录须不存在。fault脚本删除的是**自己新建job目录**的receipt，绝不删除源设计或其他任务回执。

## 未完成范围与下一步

D03整体仍implemented_partial：本批是add segment+alias，修改/删除、交叉无连接/T结点/重叠/断点等原生矩阵仍须完成。expectedWirePaths支持预先声明分段并不等于所有native分段行为已经验收。D04的global/power/ground/NC、独立alias编辑仍未完成，C03姿态参考帧和V01短接fixture失败仍后移。

接下来将已验证的库到实例放置接入typed工具，并推进图形及原生检查。放置不能依赖已失败的简单仿射C03模型推算热点；应绑定库package/device/cell/part的稳定语义身份、明确expected pin/姿态/全局热点及碰撞/缓存策略。多单元和缓存生命周期、所有原定功能及最终门禁不缩减。

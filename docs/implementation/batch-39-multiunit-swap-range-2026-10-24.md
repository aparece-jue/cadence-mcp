# 多单元共享脚、交换组元数据及本机范围修复

本批独立于待授权Simulation Manager窗口，不做桌面操作。原34项完整scope及L03剩余范围保留。

## 原生与MCP结果

在创建前写入expected.json。同构A/B单元共享一个4pin符号，逻辑position为0/3/7/12，隐藏VCC映射物理8，两unit各自输入交换组为7/11；8条逻辑记录对应7个物理焊盘。已有真实137工具MCP完整声明图、保存重开、query通过。

异构原始A/B/P用例使用101/202，创建物理映射阶段NewPinNumber返回1110，未保存。`.local/multiunit-swap-maps-20261024/report.json`整体false，保持原报告和账本，不按后来成功覆盖。

按官方Tcl手册p724、726–727 GetPinSwapId/NewPinNumber/SetPinSwapId，在新简单2pin库中校准。-1/0/31/32/63/64/99/100/101均保存并独立验证完整图；127/128/202/4095均失败1110。补测125/126保存重开通过，明确本机126/127边界。共11个合法测试值通过、4个超界值拒绝，自有进程均0。不泛称所有版本范围相同。

当前公开创建契约原允许4095过宽；现host validate_spec和PinMapping.swapId schema同时改为[-1,126]，逻辑position范围未改，现有库读取元数据不因本次写范围收紧而丢弃。旧校准report发生在修复前；修复后再次运行高值会先被host拒绝，不得冒充重测native边界。

## 单独completion

`.local/multiunit-swap-completion-20261024/report.json`通过，保持原失败report hash。

- 同构复用原成功job，在新server apply/recover/open不重放，8logical/7physical保持；没有重复其native写入。
- 新异构声明使用A101/B102合法组，A/B5pins各自隐藏VCC/GND、P2pins可见电源，12logical/8physical。物理8/7三unit共享且元数据一致，源符号几何、设备映射、共享/visible与swap IDs均由独立native graph核对；真实MCP query与fresh apply/recover/open通过。
- 127/202/4095由schema在计划前拒绝；范围内共享VCC的swapId不一致也拒绝。未执行实际物理脚交换，不证明多单元DSN实例集成。

## 证据与限制

- `.local/pin-swap-range-20261024/report.json`及`.local/pin-swap-boundary-20261024/report.json`：修复前真实原生校准。
- `.local/multiunit-swap-maps-20261024/report.json`：原同构成功/异构失败，整体仍false。
- `.local/multiunit-swap-completion-20261024/report.json`：新合法异构及既有同构生命周期补验，passed。
- `.local/regression-297-swap-bound-20261024.txt`：新增边界测试后完整297项296通过、1原文件符号链接权限skip。历史间歇目录句柄issue保持open。

contracts/tools.v0.1.json同步实际137工具输入schema。L03仍partial，alternate part/footprint variants及多单元DSN unit/package集成、原复杂边界仍待完成。原34项不缩减，全目标active，不修改安装/真实设计，不提交推送。

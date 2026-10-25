# 符号改名/删除持久MCP任务

新增CaptureNetSymbolEdits，5个固定任务工具：capture_plan_net_symbol_edit、capture_apply_net_symbol_edit、capture_net_symbol_edit_jobs、capture_cancel_net_symbol_edit、capture_recover_net_symbol_edit。capture_open_edit_result支持kind=net_symbol_edit；真实工具137，契约来自stdio实际列表。

## 输入和不变量

计划输入sessionId、symbolId、wireId、operation(set_name/delete)，改名另给name，可选expectedWireNet。只接受已通过原生专项的scalar attached global/offpage，拒绝port/bus/pose、no-op、非法标量名和已检测名称冲突。完整生命周期的其他范围仍在原34项清单中，未因本工具切片而移除。

绑定私有DSN hash、qualified page、native ID、原name/location/hotspot/rotation/mirror；要求热点位于明确wire且native GetNet对象一致，不能按坐标或同名推断连接。写入固定JSON-only adapter，对新副本操作；name/delete-only adapter无姿态分支。

沿用持久账本和Windows自有进程树机制，启动过的写入不重放。保存重开核对完整definition结构、精确连接对象、所选页全部part姿态/热点，以及native page pin-wire成员分区和所有非目标网络名。仅目标组可自动改名；指定expectedWireNet时须完全匹配。改名后另开原生读取核对symbol与wire仍同一非空net。输出SHA在验证阶段之间和完成时保持，source重新核对。scope明确为页定义；跨页/global-flat/occurrence、其他页几何、其他器件属性、渲染和DRC尚未认证。

## 真实验收

- `.local/net-symbol-edits-mcp-20261024/report.json`：初harness查询entity=all被已有schema拒绝，修改前失败，保留。
- `.local/net-symbol-edits-mcp-v2-20261024/report.json`：global/offpage改名/删除四个真实MCP任务均verified，schema与非法输入拒绝。global错误owner预期保存后验证拒绝/open拒绝/禁止重放和pendingcancel通过；offpage第二次错误预期任务复用wrong幂等键，被正确拒绝，harness错误期待write_not_replayed，整体report仍false。原报告不改为成功。
- `.local/net-symbol-edits-mcp-completion-20261024/report.json`：复用上述四个已验证任务，在新server核对apply/recover/open/hash保持及mutationReplayed=false；不重新执行四次写入。另用唯一键新建offpage错误预期任务，保存后拒绝/open拒绝/禁止重放和pendingcancel/jobs通过。最终仅offpage-delete成功输出故意追加bytes并确认target_changed，保持拒绝；前三输出和原输入完整。completion通过，原失败报告hash保持。
- `.local/net-symbol-edit-faults-20261024/report.json`：真实native完成后受控删回执，fresh仅核验恢复/nativeCompletionVerified=false/输出hash保持/open；启动cancel、真实1s timeout、自有进程0和禁止重放通过。不是所有保存窗口/浸泡故障已通过。

原smoke脚本已修正查询类别及按kind区分幂等键，但未无必要重跑四个成功写入；完整链由保留的写入证据与单独completion共同证明。脚本最终版本hash在batch-34-evidence.json。

## 回归与下一步

新增3项测试，覆盖原快照和wire/pose保持、未通过姿态/bus/非法删除与标量名拒绝、只删除选定实例。完整294项：293通过、1原文件符号链接权限skip，见`.local/regression-294-net-symbol-edit-20261024.txt`。历史取消后目录句柄问题仍open，不因绿色回归关闭。

batch33的残留网络、热点模型、offpage-state1问题保持open并后移。下一推进跨页原生语义和官方PortSymbol来源fixture；D04仍partial，原34项完整范围、全目标active。不使用GUI、不修改安装或真实工程、不提交推送。

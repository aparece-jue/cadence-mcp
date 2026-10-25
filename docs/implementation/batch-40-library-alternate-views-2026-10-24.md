# 同cell替代符号视图

本批补L02/L03的alternate part变体。沿用单package创建工具，无新增工具族，不进行GUI或真实工程操作。

## 实现与不变量

symbols允许多行具有相同精确cellName和不同partName，代表同cell的Normal/Convert等替代视图。全局partName大小写唯一；同cell的casefold别名拒绝。各view逻辑position/name/pinType必须一致，几何/visibility可分别声明，device物理映射依然完整且shared pads功能/swapId一致。

原生只创建一次cell，分别AddPart；part对象按partName定位，避免按cell字典覆盖导致旧图形丢失。expected/actual图以package/device/cell/part语义身份比较每view的pins、hotspots、pin-starts、lines及meta；package.size仍是真实device数，physical pad count不按额外view重复计数。旧单view声明的图结构与digest保持兼容。单package单footprint字段和外部实体封装认证范围未扩展。

## 验收

原生fixture在执行前冻结spec/expected，Convert视图翻转x坐标而保留function mapping，3类保存重开图精确通过：

|case|units|part-view rows|pin-view rows|physical pads|
|---|---:|---:|---:|---:|
|single|1|2|4|2|
|shared_dual|2|4|12|5|
|heterogeneous_power|3|5|14|6|

这些view行数不称为额外逻辑单元或物理脚。shared_dual保留hidden shared VCC，异构A/B/P保留供电映射。

真实137工具MCP对3类创建、保存、独立重开、open/query均通过。新server幂等apply、recover、open无重放；不兼容function视图在计划前拒绝；错误homogeneous声明实际保存后以library_creation_mismatch拒绝、禁止open与重放。末尾仅heterogeneous_power MCP成功OLB故意追加bytes作为篡改负例，保持target_changed拒绝；原生3份和其他2份MCP产物完整。

独立多view异构故障链：native完成后受控删除回执，fresh MCP仅核验恢复，nativeCompletionVerified=false、hash保持、open通过且只有一次native写入；启动取消、真实1秒超时、自有进程0通过。未宣称所有保存阶段/长时间资源浸泡已通过，历史目录句柄问题保持open。

## 证据

- `.local/library-part-variants-20261024/report.json`：3类原生fixture通过。
- `.local/library-part-variants-mcp-20261024/report.json`：3类实际MCP及负例/重启/篡改通过。
- `.local/library-variant-faults-20261024/report.json`：多view故障验收通过。
- `.local/regression-300-library-variants-20261024.txt`：新3项host测试后完整300项299通过、1原文件符号链接权限skip。

contracts/tools.v0.1.json同步真实说明，工具仍137。L02/L03仍partial：footprint变体及DSN多单元实例/同package归属等原范围待完成，未把OLB图验收当作DSN连接或渲染认证。Simulation Manager应用授权步骤仍待处理；原34完整门禁不缩减，目标active，无安装/真实工程修改、提交推送。

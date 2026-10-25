# 第84批：原生引脚标志与派生global语义

官方依据为Capture Tcl主参考p603–604读取标志、p608–609的固定setter。新只读capture_get_library_pin_style及既有pin edit可选style(long/clock/dot)，实际194工具；未开放任意Tcl/指针。十一原生标志按package/device/cell/part/逻辑position绑定，读取原样返回，完整覆盖/严格bool/8192行和32MiB边界；source revision前后核对。新样式计划冻结全库标志与完整已建模图，旧任务保留原范围；最大64个重复scope及原48KB计划预算。

## 原生行为与模型修复

首实际MCP四例中long、shared dot、power clock通过，组合clock+dot+隐藏+start失败。只读审计定位唯一global字段：旧模型期望false而实际true。该原报告保持false，原OLB/请求/失败账本不变。初版把global误作独立存储标志；新16转换矩阵预先声明按类型/visibility的派生规则并严格核对其余九标志，确认当前标量引脚global=(pinType==7 or hidden)。计划现在在visible/type变化时明确预览这个字段；未改变值的setter在新style计划中跳过，读取和未改动字段不强行归一化。

前四探针保持未接受：短名称GetPart查找1021；迭代结束1022被带入下阶段检查；只取反visibility的初始假设在power类型失败（构造状态、转换后各一）。输入/原生输出/诊断和hash见私有history；没有把原假设改写成通过。v5的完整type-aware规则通过16例。symbol global标志不证明DSN/flat电气连接。

新五组实际MCP通过完整保存重开、11标志及其他已建模数据：单单元long，Convert clock+dot/visibility/start，共享双单元dot，异构POWER clock，样式与pinType7组合；shared scope数量、no-change/外来pin/关闭拒绝和fresh apply/recover/open不重放通过。原先错误global摘要仍被当前verify拒绝，原失败账本/输出/请求hash不变，不自动迁移旧计划。

## 故障与边界

四类真实原生故障通过：完成后丢回执，新实例verify-only恢复；启动窗口取消；加载库并完成样式定位后的2秒注入延迟触发1秒超时（补测有阶段marker）；独立原生setter修改未目标Convert.1的dot，执行及恢复均由新全库style摘要拒绝。所有所属进程剩余0。新查询工作副本篡改在输出生成前拒绝，关闭后session_lost，源OLB不变。

8项新host覆盖共享scope、其他view/pin保持、派生global/power例外、严格输入、覆盖/语义ID/源图变更拒绝及no-change。完整526回归525通过/1原权限skip，实际194工具合同同步。初测试安装脚本缩进anchor失败在只读断言更新前停止，已按实际缩进修复；未影响原生结果。

L04仍partial，typed user property等原问题保留；不认证新增glyph渲染/DSN缓存同步/实例电气。34项仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%不变。alpha.1及main/tag保持固定，仅同步develop。无GUI、安装目录/真实设计修改。

证据：library-pin-style-mcp(-v2)-20261026、pin-visibility-global-matrix-v5-20261026、library-pin-style-faults-20261026、library-pin-style-timeout-marker-20261026、pin-style-read-guards-20261026、pin-style-old-oracle-audit-20261026及regression-526-pin-style-final-20261026.txt（均在.local）。原始失败/探针历史仅保留私有原件，公开原创复现脚本和脱敏结论/摘要。

# 第五十九批：绑定DAT的CSV/JSON数值导出

2026-10-25。当前目标继续active，原34项范围不变，P04保持deferred；本批只验收其模拟数值导出切片。

## 实现与契约

新增pspice_plan_dat_export、pspice_apply_dat_export、pspice_dat_export_jobs、pspice_cancel_dat_export、pspice_recover_dat_export，实际160工具。输入为已打开DAT、block、精确trace或已核实alias、CSV/JSON、非空采样范围；计划冻结来源DAT与manifest摘要、数值声明及来源身份，关闭原会话后仍可执行。

固定Python序列化worker只读取冻结表和复制DAT，不开放任意代码、DAT写入或shell入口。CSV固定index/axisReal/axisImaginary/real/imaginary列，metadata及单位保存在导出manifest；JSON保留metadata和samples。单位只使用已有trace名称约定，未知单位明确保留unknown。数字逻辑值继续拒绝，禁止把混合文件中的模拟网格零向量当成数字状态。

完成后新建原生DAT读取会话，逐行核对独立重读数值、轴和声明，再比较序列化完整字节及来源摘要。验收记录绑定source.dat、samples文件、export-manifest.json三个摘要。此证明是已有采样身份一致，exportedRowsNumericalOracleVerified保持false，不代表新增电气预期通过。来源为导入或已核实求解任务的区别保留。

## 实际验收

- `.local/dat-exports-mcp-20261025/report.json`：4项真实160工具MCP用例通过。DAT9两块复数的CSV及范围JSON、带新求解任务关联的混合模拟电流CSV及范围JSON；原会话关闭后执行、新服务恢复/幂等不重放、数字与非法范围拒绝、原source/oracle不变均通过。
- `.local/dat-export-faults-20261025/report.json`：7项故障案例通过。成功worker丢回执后新MCP服务恢复，workerCompletionVerified=false且数值文件hash不变；可补建验证manifest但不重建数值文件。启动窗口取消、1秒超时所属进程退出信号确认；完成后数值追加导致原生重读字节比对失败，恢复/重放拒绝；三个终末文件分别篡改后复用与恢复均拒绝。负例保留在独立任务目录。
- 新8个host测试覆盖数字/范围拒绝、有限浮点与精度、Unicode、固定CSV头、冻结来源/manifest/table篡改、固定worker拒绝覆盖和待执行取消。完整391回归390通过/1原符号链接权限skip，日志`.local/regression-391-dat-exports-20261025.txt`。skip不算验收通过。
- 契约由实际stdio tools/list重新生成，160项。

## 未通过项与下一步

P04仍需可靠数字状态/强度/时间访问及剩余单位/格式边界；DAT10第二块写入崩溃保留，DAT9是已核实替代夹具，不代表DAT10修复。Capture连接与保存、完整CLI/诊断边界、Capture到PSpice参数迭代和最终验收继续未完。34项状态仍为1 baseline_passed、21 implemented_partial、10 deferred、2 planned。

本批不使用GUI、不修改Cadence安装或真实工程、不提交推送。安装脚本首次错误匹配readonly装饰器在修改server前中止，已修正后安装；最早审批额度阻止的写入未执行，恢复后重新检查再执行。没有以失败尝试计为通过。

# 第七十八批：PSpice测量单位与P03原门禁验收

2026-10-25。原34必需范围不变，工具仍192。本批依据cadence-plan.md及cadence-acceptance.json原P03条件逐项核对，并补齐测量单位来源信息。P03标passed；P02许可证失败、P04数字/格式边界、V04/P05 Capture生成输入及端到端仍未通过，不随P03结案。

## 单位注释实现与依据

本机官方doc/pspcref/01commands.html的measure_command锚点说明DC/AC/TRAN、TRIG/TARG、FIND/WHEN及统计表达式。原生测量文本只含数字，没有独立原生单位字段；本接口新增的是保守推断，明确nativeUnitMetadataAvailable=false。

pspice_inspect_run_measurements在验证全部输入/输出hash后，从冻结声明、实际原生表达式及已执行的输入文件生成fieldUnits与measurementUnits。简单V/I及MIN/MAX/AVG/RMS/PP包装的value使用V/A；at/from/to按TRAN时间s、AC频率Hz、唯一简单DC电压/电流源扫描V/A。TRIG/TARG的无表达式差值使用独立轴单位。WHEN的value可能是触发电压，at才是时间，不能由变量名tau推断。复杂表达式、PARAM、dB、MIN_AT/MAX_AT等未验证维度保持unit=null并说明原因；不将数字同名误作量纲证明，不声称覆盖全部原生测量语法。

只在只读inspection返回副本增加元数据，原nativeMeasurements/OUT/MEASURE文本、run-artifacts及任务账本不变；输入逐文件按manifest hash检查，结束再次核验所有产物。新旧任务均可读取。源文件32MiB/单文件8MiB预算及固定任务执行限制沿用原输入体系，未新增任意脚本入口。

## 全新真实MCP原条件验收

创建前冻结原5V/1k+1k分压、RC=1ms及其解析数学预期；新任务求解，不复用旧OUT/DAT。三类原生MEASURE及两个后端各三类完整运行通过。native complete-analysis不是CLI的隐式替代，后端与产物身份单独核对。

|原条件|实际证据|
|---|---|
|DC绝对误差≤1e-6V|引擎与官方CLI均2.5V，最大误差0|
|RC时间常数误差≤1%|两后端541点均通过1-exp(-t/1ms)，最大电压误差2.8811e-6V；tau=1.000004061ms，相对误差约0.0004062%|
|AC截止频率误差≤1%|两后端301点、1Hz至100kHz，实/虚部与解析H(jw)最大误差2.964e-8；截止159.16087Hz，相对误差约0.003724%|
|退出码与输出共同判断|原生exit0的非收敛、exit1缺模型及电压源环路均按OUT分类拒绝，失败DAT不开为成功|
|测量与独立预期|DC max/avg/find及at、瞬态when/find、AC幅值均按冻结字段验收；故意3V错误预期拒绝|
|单位与来源|电压/电流、时间/频率/DC轴、触发延迟均原生正例；PARAM常数表达式返回3但维度未验证，明确unknown|
|来源和恢复|6运行的当前全部artifact hash、CLI原始/规范OUT/DAT逐字节身份；fresh不重放；3原旧任务的原数值/raw及账本hash保持|

补充真实测量：电源平均电流-1.25mA标A，DC扫描的from/to标V；触发20%到80%的RC延迟与1ms*ln4吻合，value/from/to均s。常数PARAM输出未知维度不猜单位。与原source/declaration/native expression对应，8host测试覆盖组合表达式、歧义/嵌套DC、WHEN/延迟字段及副本隔离。

原5项native-measure故障、8项CLI故障及原native-MEASURE正反矩阵报告保持通过并纳入闭环证据；原AC VM不支持的失败仍保留，不把替换为V表达式称为全语法支持。P03原唯一issue缺测量入口已在第60批按其范围解决，本批记录原P03门禁关闭审计，不更写历史失败原因。

## 边界与最终状态

P03通过指原计划规定的受限显式CIR、DC/RC/AC、OUT诊断及已验测量结果闭环，不是完整SPICE方言/测量表达式、原生单位元数据库、数字状态、隐式模型查找或电路安全认证。输出仍保留notChecked与单位来源/unknown。P02、P04、V04/P05及其他原34项仍按各自完整条件验收，未缩减整体目标。

488完整回归487通过/1原文件符号链接权限skip，无失败；192实际stdio契约说明同步。34现6 passed、1 baseline、10 partial、15 deferred、2 planned，目标active。无GUI、安装/真实设计修改或提交推送。主报告.local/pspice-result-acceptance-20261025/report.json，单位边界.local/measurement-dimensions-mcp-20261025/report.json；逐项证明见batch-78-evidence.json。

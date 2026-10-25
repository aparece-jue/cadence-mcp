# 第六十五批：命名节点输出选择器与P01完整验收

2026-10-25。原34项范围不变，本批无生产逻辑/契约修改。P01按原明确标准完成验收；其他门禁及全目标不自动通过。

## 原选择器问题的根因与实际修正方式

已读取本机`doc/pspcref/01commands.html#26898`的PRINT节点/器件语义与方括号强制节点说明。原IN/OUT电路中的V(IN)/V(OUT)被当前原生引擎解释为器件选择，报ORPSIM-15090设备未定义。不是没有节点，也不是数值求解正确就能忽略该错误。

保留原DC/AC/瞬态电路及expected.json字节/hash，对照三种形式：原括号形式，以及官方强制节点的V([IN])/V([OUT])与V[IN]/V[OUT]。仅改变PRINT/PROBE选择器字符，电源、节点名、元件、分析配置、误差和数值预期全部保持；没有用裸PROBE获取全部波形绕开需求，也没有重命名IN/OUT节点。

`.local/named-selectors-mcp-20261025/report.json`真实173工具MCP共9项通过：3原形式重新确认错误拒绝，6明确节点形式新求解通过。DC OUT/DAT均2.5V并检查本次PRINT表；AC全部3行实部/非零虚部符合原1/(1+j2πfRC)，截止频点及幅值符合原误差；瞬态完整响应及插值1ms时间常数符合原预期。新服务apply/recover不重放，原始失败source和原oracle均未改。

ISS-P01-named-output-selectors按“支持官方命名节点选择语义”的范围结案；原未消歧形式继续作为错误反例，不声称更改了Cadence对其的解释，也未自动改写用户CIR。

## P01原要求逐项审计

|原要求|实际证据|
|---|---|
|嵌套INCLUDE/LIB|第64批4文件INC/INCLUDE/LIB输入及独立参数求解；本批4文件INC→LIB→LIB和INCLUDE相对引用，原生Setup成功|
|相对路径与空格|本批models folder/level.lib再引用deep/model.lib、../values.inc，原始和准备字节、完整清单身份绑定，native读取成功|
|缺模型|第64批真实缺模型反例被原生拒绝，正确显式模型的OP输入Setup通过；失败任务OUT可结构化检查|
|节点0|第64批无0节点浮空电路被原生Setup拒绝，含0节点正例通过；没有用文本“出现0”代替原生检查|
|参数与分析语法|第64批未定义参数、DC缺参数均被原生拒绝；独立参数分压新求解5/3V按1e-6通过；本批命名DC/AC/TRAN沿原数值预期通过|
|诊断与来源|原错误不吞掉，失败不能读取为成功或重放；原生Setup结果明确analysisExecuted=false，不冒充求解结果；计划绑定preparedManifestSha256，避免相同入口hash下依赖变化混用|
|拒绝越界/动态执行引用|本批14反例：缺引用/环/绝对越界/Windows目录junction逃逸/多root歧义/通配符/动态名/不支持的LIB section/二进制/写文件指令/缺END/缺分析/控制块/嵌入式LIBPATH。均在native检查worker启动前拒绝|
|原字节与清单/故障|既有InputTests和第64批冻结/篡改/取消/timeout/恢复7例通过；原输入关闭后持久计划仍可用，缺Setup回执保持未认证；关闭输入后查询拒绝；全部source/oracle hash保持|

引用边界详情`.local/input-boundaries-mcp-20261025/report.json`：14负例后检查任务总数仍0，再执行合法嵌套正例。目录junction仅指向本批私有outside文件夹，不触及安装或真实设计，保留作为证据。

## 支持范围与未完成项

P01标记passed，仍是原计划中的受限手工CIR/显式单文件INC/INCLUDE/LIB准备与原生输入检查；没有扩大为所有SPICE输入格式。隐式模型搜索闭包、嵌入/动态文件、LIB section语法、非UTF8、任意SPICE方言仍明确不认证/拒绝，保持原API限制。Setup通过不表示收敛、数值结果或电路安全通过；最终全局A01仍需处理原文件符号链接权限skip及所有未完成项。

本批核对第64批全部生产/契约摘要保持，沿用420完整回归419通过/1原权限skip；仅新增真实专项验收，不无故重复整套。173工具保持。34项现3 passed、1 baseline_passed、18 implemented_partial、10 deferred、2 planned，全目标active。

下一步处理官方CLI/许可证失败等P02缺口，再推进剩余库缓存、Capture连接/保存和完整参数联动。无GUI、无安装/真实设计改动、无提交推送。

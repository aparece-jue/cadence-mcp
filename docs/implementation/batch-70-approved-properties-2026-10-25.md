# 第70批：批准参数与模型引用修改，E01验收

日期：2026-10-25。E01按原条件审计，批准字段明确为Value、PCB Footprint、Implementation、TC1、TC2；这是既有有效属性修改，不是替换符号/库缓存或任意属性写入。单个目标定义必须在其页内位号唯一；多单元成组修改继续归E03/L03。无GUI、安装/真实设计修改、提交推送。

## 官方依据及实现

安装文档`doc/pspug/003_model_Changing_the_model_reference_to_an_existing_model_definition.html`和`004_part_Attaching_models_to_parts.html`明确Implementation关联PSpice模型名；它不同于Value标签和Implementation Type。现有官方二极管定义实际读取为Implementation=D1N4001、Implementation Type=PSpice Model。官方ANALOG电阻实际具有TC1/TC2，其PSpiceTemplate通过TC参数引用两者。

既有capture_plan_property增加三个批准字段，工具总数仍178。Implementation仅接受最多128字符的字面模型标识符，要求目标已有PSpice Model类型；不隐式改变view type、解析外部模型或替换符号。TC1/TC2接受最多64字符、有限十进制数字字符串；不冒充支持表达式或所有PSpice后缀语法。原Value/PCB Footprint语义保持。

所有新计划现在冻结全设计有效属性多重集的期望摘要，按schematic/page/reference scope及完整属性名值集合比较，保留重复scope的多重性；原定义引脚网络基线检查继续执行。目标仍要求唯一，setter前核对原值/对象身份及Implementation Type。保存后独立新进程重开，准确修改声明字段、拒绝不相关有效属性改变。旧计划保留其原验证范围，不追溯提高旧认证。

新增固定只读扫描器单次遍历所有页和器件；最多1024器件、每器件512属性、总16384属性、8MiB原始属性文字及16MiB结果。属性名256字符、值16384字符，未知/重复结构拒绝。原生属性迭代结束明确核对1022，异常结束拒绝；禁止截断后认证完整图。完整属性多重集不等于完整显式/继承来源/显示图或全部unit身份认证。

## 原生与MCP验收

原创fixture从已有自建四电阻设计副本中加入官方二极管库副本，先写期望：7实例/14脚，ROOT同页D1/D10及AUX同名D1。安装和原源不变。`.local/model-property-fixture-20261025/report.json`记录创建与读取。

- `.local/model-properties-mcp-v3-20261025/report.json`：五个批准字段各一组真实MCP，执行前写入完整期望图，保存重开后逐项核对全部有效属性；原始v1/v2成功记录保留。严格模型名/有限数字、未批准字段、非PSpice Model目标拒绝，待执行取消、打开已验证输出、新服务幂等/恢复不重放及源hash保持通过。
- `.local/property-official-final-20261025/property-edits-report.json`：官方FULLADD有线样例副本上的Value/Footprint、中文及特殊字符等3例重新通过；全定义pin-net保持、原字段新计划的全有效属性保护、共享位号拒绝、取消、任务分页及新服务无账本改写/不重放通过。
- `.local/model-property-faults-20261025/report.json`：丢回执新服务只验证恢复、启动取消、真实1秒执行超时、源副本改变启动前拒绝，以及第二个固定原生worker实际修改不相关R10.TC2后拒绝认证，共5项通过。未验证输出拒绝打开，不重放写入，所属进程均确认停止。
- `.local/model-fault-reverify-final-20261025/report.json`：最终严格扫描器只读重验原丢回执输出和不相关属性篡改输出，前者可验证、后者仍拒绝；产物及原账本hash不变。

## 电气语义独立验证及范围

`.local/model-property-numerics-v2-20261025/report.json`通过五个真实官方CLI求解：温度127°C下电阻分压基线2.5V、TC1=0.001对应5/2.1V、TC2=-2e-6对应5/1.98V；另两份DSN副本分别写入MCP_D_A/MCP_D_B模型名，重开后显式转录到独立原创二极管电路，结果符合预先声明的Shockley公式（不同IS、同温度/电压）预期。

每份转录绑定DSN输出hash、目标scope、实际属性值和本次求解任务/输出，期望文件执行前写入且不变。此处是明确的手工参数转录，不是Capture原生生成网表；不认证原有原理图整体电气行为。属性工具仍返回electricalBehaviorVerified=false、modelDefinitionResolved=false、simulationInputRegenerated=false。V04/P05、模型引脚兼容、occurrence连接、外部实体封装与DRC均不因本批通过。

## 失败保留及修复

- 首次数值夹具只有PRINT没有PROBE，CLI生成本次OUT而没有DAT，任务正确未认证；首次`.local/model-property-numerics-20261025/report.json`保持false。补PROBE后使用全新目录，原数学预期完全不变，五例全部通过。
- 完整属性扫描器收紧文字预算时引入属性文字变量与页序号变量冲突，私有诊断记录`expected integer but got COMPONENT`。`.local/property-snapshot-end-state-20261025/diagnostic-process.json`保留，重命名后v2报告7实例/180属性及1022正常结束通过，最终MCP/官方样例和回归均复验；未放宽结束状态或截断数据。

新增5项host测试，修改原计划测试以核对新全属性冻结；15项针对性通过。最终`.local/regression-443-model-properties-20261025.txt`为443项、442通过、1原文件符号链接权限skip，无失败。实际stdio契约重新同步178工具。

## E01原条件审计结论

原acceptance文字保持：before/after预期、计划hash、幂等、保存、新进程重开；net不变不代表仿真语义不变。五个批准字段的完整实际正例、既有网络样例复验、持久任务/故障反例与独立电气语义观察共同满足E01本身；E01标passed。未将Value字符串变更当作换型号，未将属性保持当作模型存在/整图求解证明。

34项现5 passed、1 baseline_passed、16 implemented_partial、10 deferred、2 planned。整体仍active，库缓存替换、连接保存、层次/总线、DRC、V04/P05及其他原遗留继续推进。

# 第69批：库引脚起点编辑与用户属性类型核实

日期：2026-10-25。L04继续implemented_partial，原34项要求保持。只操作自建库副本；无GUI、无安装/真实设计修改、无提交推送。

## 引脚起点编辑

CAP-REF第609页的DboSymbolPin.SetStartPoint(CPoint)返回DboState。既有capture_plan_library_pin_edit新增可选startPoint；它表示符号内部引脚起点，hotSpot仍为连接端热点，两个坐标分别声明。严格两整数、±1000000边界，不允许bool/float替代整数。

支持起点单独修改或与name/number/pinType/hotSpot/visible组合。起点只沿cell/part/logical pin position匹配的原生符号视图传播；所有引用上下文必须有唯一且一致的旧起点。预览单独列出affectedStartPoints、每个scope、oldStartPoint和expectedStartPoint，不把符号起点变化冒充物理脚号变化。拒绝超过64个受影响视图、缺失/重复引脚和旧起点不一致。

原生设置前校验旧起点，检查setter的DboState。保存后独立新进程读取完整已建模图，准确比较声明起点及其他定义/热点/可见性/模板/有序vectors；旧计划兼容其原验证范围。

`.local/pin-start-mcp-20261025/report.json`四组真实MCP全部通过：单单元Normal起点单独修改、Convert起点+可见性、共享双单元Normal起点+热点+可见性、异构POWER起点单独修改。预先写入声明与完整期望图，再执行并独立重开比对；另有旧字段组合、新字段严格schema反例、no_change、待执行取消、新服务幂等恢复和输出篡改拒绝。最后输出按反例被故意篡改，不能作下一正例输入。所有原库hash保持。

`.local/pin-start-faults-20261025/report.json`丢回执后的fresh verify-only恢复、启动取消、1秒真实执行超时三项全部通过，均核对所属进程退出；已开始写入不重放。起点变化由完整图验证，不只检查回执或文件存在。

新增5项host测试：共享视图及未目标字段保持、引用旧值/缺失/重复拒绝、严格坐标/未知scope、无变化、64行预算；23项针对性回归通过。实际stdio契约仍178工具，已同步。最终`.local/regression-438-pin-start-20261025.txt`为438项、437通过、1原文件符号链接权限skip，无失败。

## 类型属性未通过，失败保留后移

官方CAP-REF148/151/153/169/188/759分别提供DboValue读取/设置、NewUserProp两个重载、DboUserProp.SetValue及DboTclHelper_sMakeDboValue。安装自带的类型映射区分STRING0、LONG1、INT2、BOOL3、TIME6等。以下探测不代表公开功能通过：

- 首轮脚本依赖相对路径错误，没有native.json，保留`.local/typed-package-probe-20261025`及runner错误记录。
- v2/v3以严格DboState检查在值setter处遇到code1/Failed1，停止该行；它们没有完成类型写入。
- 只读值对象诊断发现setter虽报告Failed1，随后读取仍能得到相应值。这是待解释的返回码行为，未据此放宽生产检查。
- v4/v5/v6仅作观测：记录异常值setter状态，再分别对照NewUserProp带初始字符串/不带字符串，以及SetValue默认/显式bFromProp=1。六个声明中，值对象类型分别为INT2、LONG1、BOOL3、TIME6、FILEPATH16、STRING0，但对应用户属性GetType均为0；保存重开仍均为0。属性SetValue本身返回0，不能据此认证类型保持。

三个完整原生观测报告是`.local/typed-package-probe-v4-20261025/report.json`、v5和v6；源hash不变。诊断脚本不接入MCP，无公开任意Tcl或指针入口。不能把文本内容等价当作类型保持，也尚未证明这是产品限制或SDK缺陷。

登记ISS-L04-typed-user-property-persistence，要求按独立类型预期修复/证明支持范围并重验；相关失败工作后移。原公开package edit继续明确只允许字符串set，不将本探测包装为typed编辑实现。L04整体不通过，其他引脚属性/typed/变体和原要求仍未完成。

34状态仍为4 passed、1 baseline_passed、17 implemented_partial、10 deferred、2 planned；整体active。继续推进独立库/缓存与原理图业务项，最后回到类型持久化及原Capture连接/保存等遗留。

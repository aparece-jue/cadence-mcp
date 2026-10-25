# 库引脚标志查询与编辑（develop）

新增`capture_get_library_pin_style(libraryId,pinId)`读取11项原生标志及语义scope/共享视图scope。通过`capture_library_open`和`capture_library_query(entity="pin")`获取绑定revision的ID；不接收原生指针或Tcl命令。

读取字段：long、clock、dot、leftPointing、rightPointing、netStyle、noConnect、visible、global、numberVisible、userDefinedShape。当前只允许通过既有`capture_plan_library_pin_edit`的style对象编辑long/clock/dot；其余字段保留并在新样式任务中核对。style必须有至少一个严格布尔字段。

```json
{"libraryId":"lib-...","pinId":"package-.../pin-...","style":{"clock":true,"dot":true}}
```

沿用apply/cancel/recover/open任务链，作用于新OLB副本。计划预览包含oldStyle和affectedStyles的完整旧/预期标志；共享symbol的多个device引用一起预览。保存后新进程核对全库标志、定义、起点、已建模图形与模板。最多8192个标志行、64个受影响视图、32MiB读取及既有48KB计划预算。

本机24.1标量引脚矩阵确认：global是派生属性，电源类型(pinType7)为true，其他类型隐藏后为true。在指定style的新计划中，修改类型或可见性时会展示相应派生变化；原生读取不改写、不归一化已有值。新样式计划跳过未改变值的类型/可见性setter，避免无意副作用。这个symbol标志不等于实例已经连接到某个全局网络，不提供flat/occurrence连通性认证。

5组真实MCP覆盖单单元、替代视图、共享双单元、异构供电、样式与类型/可见性/起点组合；16个原生可见性转换覆盖8类型双方向。恢复、取消、原生阶段超时和未目标flag篡改拒绝通过。字形渲染、DSN缓存/实例及完整L04仍未认证。alpha.1不包含本轮新增功能；它继续使用已发布固定包。

未指定style的编辑及原有任务仍使用其原验证范围；请查看结果nativePinStylesVerified，不能把未覆盖的标志视为已经通过。

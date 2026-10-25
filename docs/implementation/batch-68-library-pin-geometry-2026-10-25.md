# 第68批：库引脚热点与可见性编辑

日期：2026-10-25。范围：L04独立功能补齐，整体门禁保持implemented_partial，不改变原34项条件。无GUI、无安装或真实设计修改，无提交推送。

## 官方依据与实现

本机CAP-REF第609页确认DboSymbolPin.SetHotSpot(CPoint)、SetIsVisible(int)均返回DboState。在既有capture_plan_library_pin_edit添加可选hotSpot和visible，不增加工具；实际仍178个。坐标必须为两个严格整数且各在±1000000内，可见性必须为严格布尔值。原name/number/pinType参数兼容。

热点和可见性按cell/part/logical position标识的符号传播到受影响device视图；物理脚号仍按原device范围处理，不开放共享脚重编号。预览明确列出全部受影响行。原生worker在设置前额外核对旧热点和可见性，并检查两个setter的DboState。

含新增字段的计划，除原完整定义图外，还冻结已建模的reference template、引脚起点和有序vector图摘要。独立新进程重开，要求声明字段变化准确、其他已建模数据完全保持。旧计划继续原语义定义图验证范围；不会追溯升级旧结果的图形认证。完整图不支持的原生对象会拒绝计划，不放宽为部分读取。

## 实际验收

- `.local/pin-geometry-mcp-20261025/report.json`：4组实际MCP正例全部通过，分别为单单元Normal热点、Convert可见性、共享双单元Normal两条关联行、异构POWER单元。另通过name/number/type/hotSpot/visible组合修改。预先写入声明及期望图，独立重开核对完整图，原库hash保持。
- 同报告覆盖严格schema反例、no_change、待执行取消、新服务恢复/幂等不重放，以及已验证输出被篡改后拒绝打开。最后一份输出特意篡改，仅作为反例保留，不能作为后续正例库。
- `.local/pin-geometry-faults-20261025/report.json`：丢失原生回执后新服务只验证恢复、启动取消两项通过；首次短超时测试发生在新增的计划只读扫描阶段，因此该报告整体false，原记录保留，不能冒充写入超时验收。
- `.local/pin-geometry-timeout-v2-20261025/report.json`：计划使用正常预算，执行阶段单独配置1秒；真实写入进程timeout、所属进程全部退出、重复执行拒绝通过。测试驱动新增可选mode，未改生产超时语义。
- `.local/pin-preservation-negatives-20261025/report.json`：在正确引脚预期之外预先声明错误起点保持图，保存后拒绝认证；未验证输出拒绝打开、写入不重放。计划后源副本改变在启动前拒绝，未生成输出。原源库hash均不变。

新增4项有实际逻辑覆盖的host测试，18项针对性回归通过。首次全回归未配置原生Tcl测试环境，433项中15项skip，仅作准备记录。补配置后最终`.local/regression-433-pin-geometry-native-20261025.txt`为433项、432通过、1原文件符号链接权限skip，无失败。实际stdio工具契约重新同步，178工具。

## 剩余范围

本批只认证新输出OLB的声明字段及完整已建模图保持，不认证渲染外观、未建模库属性、未引用原生对象、DSN缓存或实例连接、外部实体封装、原生DRC。L04尚有typed用户属性、其他符号/引脚属性和变体等原要求，字体质量及位图像素替换等原问题也未关闭。库到DSN放置及缓存同步仍分别归属D01/L05，不由本批通过代替。

34项仍为4 passed、1 baseline_passed、17 implemented_partial、10 deferred、2 planned；目标保持active。下一优先核实typed库属性和其他未覆盖引脚属性的官方接口与原生读写保存范围，独立项推进后再集中处理Capture导线/层次保存等遗留。

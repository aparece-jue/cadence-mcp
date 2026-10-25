# 第七十三批：整组位号映射与交换

2026-10-25。原34项范围不变，E03保持implemented_partial，整体目标active。

新增capture_plan_package_reference_map，复用既有reference apply/jobs/cancel/recover及verified输出打开入口，实际工具185。每个代表实例扩展同schematic内同基础位号的全部已放单元；要求实际缓存来源、包和唯一device归属一致。保留前缀、显式编号，最终基础/完整单元名冲突检查，组内共享临时位号支持交换；最多64实例。拒绝外部设计、未编号和未验证归属。跨页分组已做host验证，跨页原生矩阵尚未验收。

计划冻结旧新完整单元引脚/节点表、全部实例已建模geometry/effective/user/display状态、来源限定缓存逻辑图、定义和连接对象及NC物理归属。Reference/Part Reference字段仅做精确token更新；自由文字保留。固定Tcl工作器校验旧nativeId/完整位号/device/cache/source及全部组成员，写独立副本、完整保存；新进程重开检查上述全部范围。未认证字体渲染和缓存装饰图形。

## 实际验收

- 真实MCP四组：同构未接线、异构未接线、异构显式VCC/GND接线、两组U501/U502整组互换，全部通过。计划旧新节点表与原先独立声明的expectedPins比较，原报告与DSN hash保持。关闭输入后apply、verified打开、新服务重复apply不重放与recover通过。首启动脚本使用相对路径被Config拒绝，修正路径规范化后在v2新目录执行，未覆盖首目录。
- 原有共享脚NC夹具新副本：U501→U601后单条NC仍属于原单元8/VCC，热点(1000,680)保持，独立重开与源hash通过。此项为原生服务验收，不宣称公共共享NC创建功能已完成。
- 六故障：保存后回执丢失由fresh服务只验证恢复；启动取消；真实1秒执行超时；原生误改不相关实例Value被完整状态检查拒绝；启动前源副本篡改；启动前冻结预期篡改。停止进程退出确认、未验证输出拒绝和不重放通过。原始输入未变。
- 新增10host测试覆盖U1/U10精确选择、整组交换/临时别名、冲突/重复代表、缓存归属、共享物理脚矛盾、跨页/跨schematic边界、精确属性字段与自由文字、NC owner和旧新节点表。首fixture缺少extra对应part记录，修正测试夹具后10通过。
- 完整回归466项：465通过，1原文件符号链接权限skip；无失败。真实stdio契约185同步。没有GUI操作、安装目录/真实设计修改、提交或推送。

## 保持未完成

E03的occurrence位号、自动编号/未编号分配、跨页原生与非默认显示完整矩阵仍未验收。本批没有关闭原issue，也没有用host跨页测试代替原生验收。缓存替换GND原失败属于L05，本批改号通过不代表该失败修复。其他原34门禁及权限skip保持未完成。

证据摘要见batch-73-evidence.json；本机报告在.local/package-reference-mcp-v2-20261025、package-reference-faults-20261025、package-reference-nc-20261025。

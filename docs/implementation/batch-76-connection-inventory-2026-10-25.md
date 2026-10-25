# 第七十六批：连接对象查询补验与矩阵夹具重开失败

2026-10-25。原34项范围不变。本批不改生产代码/契约，191工具保持。原C04条件“对象计数、坐标、名称、空页及同名局部对象隔离”与H02平坦/occurrence网络、D03写入/junction等分别处理，没有把任何读取正例视为完整电气连接通过。

## 原有独立夹具读取通过

在此前shared-unit-nc-guard独立DSN上，预先声明HALFADD页端口CARRY/SUM/X/Y四个、FULLADD页CARRY_IN/CARRY_OUT/SUM/X/Y五个、MCP_PLACE无端口。实际MCP逐条分页、全部计数/名称/分页全集/精确pageId筛选与同名SUM/X/Y页面隔离通过。对象opaque objectId保持九个唯一；原生数字ID在不同页复用，不用于全设计唯一定位。

端口坐标与原有导线段或明确的直接器件连接核对：CARRY_OUT与FULLADD.U1物理3/O热点(560,320)直接重合，无中间导线。其余端口在本页导线段上。此项为已有样例几何一致性，不声称由重合推断电气连通、通用junction或任意姿态公式。

共享脚NC精确单条U501.8、热点(1000,680)及partId/pinId/number归属通过。不同查询页长/外来会话cursor、外来pageId拒绝；6次额外open/read/close通过。已有缓存查询遇工作副本变更仍target_changed，关闭后session_lost，源原件及冻结expected hash保持。

测试脚本首轮把nativeId假定全局唯一，与现有组合身份契约不符；v2改为页面/nativeId组合并保留旧记录。随后脚本强制每端口位于导线顶点、再强制位于导线段，均未覆盖原样例CARRY_OUT直连U1.3结构；v4在启动前声明该确切直接连接并用独立part geometry验证，没有改动生产读取结果或旧报告。原v1/v2/v3全部保留，v4通过。未将这些脚本假设失败伪装成生产修复。

## 新完整矩阵未能重开，C04后移

创建前冻结两页各8个global、8个offpage、2条wire及2个alias、另一个空页，总40个对象，含四方向/两镜像/跨页同名；源VCC/OFFPAGELEFT-L取私有capsym拷贝。热点变换只是显式标注的预先假设，尚未获得验证，不从待测读数改写该表。

首夹具漏NewAlias字体/方向/颜色参数，按官方495–496页完整签名修正后新v2报告保存成功。但真实MCP capture_open失败。只读诊断定位inspect.tcl对应NewPagesIter.NextPage返回非NULL后状态3969，即页面载入检查失败；没有放宽该检查，也没有把SaveDesign成功算作可重开。尚未进入40对象与姿态预期比较。原失败MCP报告、DSN和expected文件保持hash，旧构造参数失败亦保留。

记录ISS-C04-inventory-matrix-reopen-3969为open，C04完整门禁由partial转deferred并移队尾。与既有D03/其他3969同码，不据此断言根因相同或桥接不支持。四方向/镜像完整查询和原C04全部条件仍未通过；后续先推进其他独立功能，再集中修复该原生保存/重开问题。

## 证据与基线

复现工具：tools/prepare_connection_inventory.py及fixture_connection_inventory.tcl生成新矩阵（workspace-root必须新目录）；tools/smoke_connection_inventory.py作完整MCP检查；tools/smoke_reference_connections.py对原共享NC夹具作独立读取验收。参数均明确绑定安装/输出/输入路径。所有实际文件在.local，不修改安装目录/真实设计，无GUI/提交/推送。

第75批生产实现、测试与191契约hash保持，沿用473回归472通过/1原权限skip；本批未重跑完整回归。34现5 passed、1 baseline、12 partial、14 deferred、2 planned，目标active。hash摘要见batch-76-evidence.json。

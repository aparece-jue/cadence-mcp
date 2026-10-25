# 第七十四批：跨页编号映射、显示保持与原生增量编号实验

2026-10-25。完整34项范围不变。依据本机官方Tcl参考PDF页259（GetRefDesMgr）、303（NewDisplayProp）、426（实例跨页复制）、461–462（删除）、522（SetReference）及823–825（manager/query/annotation）。不改安装和真实设计，无GUI、提交或推送。

## 已通过的补充验收

用原同构双单元独立副本，通过NewPlacedInst(pSource,status)将B复制到同schematic的HALFADD页，再删除MCP_PLACE原B；A仍在MCP_PLACE。增加Part Reference/Reference/MCP_NOTE三类非默认display：位置(17,23)/(19,31)/(29,37)、rotation2/1/3、type1/2/1、color3，以及每单元中文备注“位号 U501 / U501A或B / U5010 [x]$;”。夹具先重开按原始多单元expectedPins验证每脚名称/网络，并核对上述文字和显示字段，之后冻结改号预期。

原生服务跨页U501→U601通过全实例已建模状态、单位归属、缓存、连接及旧新节点表独立重开检查。实际stdio MCP再分别从两页代表发起U601/U701整组改号，两例通过；输出的有效完整位号A/B、中文自由文字和display字段独立查询通过。重复组代表、已有目标冲突、pending cancel、fresh apply不重放与终末输出篡改open/recover拒绝通过。篡改只作用于第二例输出，事先另存完整备份。源DSN、原始预期报告与夹具均保持hash。字体渲染仍不属于这些检查。

## 原生自动编号未通过并后移

读取实际GetRefDesMgr、实例/occurrence映射成功。运行时确认DboRefDesQueryHandler/RefDesQueryOptions零参及new_DboRefDesAnnotate(pQueryHandler)签名，读取编号策略；独立解释器无capBatchAnnotate。首选项探测因不存在delete_RefDesQueryOptions失败，后改为owned进程退出释放；原报告保留。首编号实验使用shadow构造入口被拒绝，尚未编号；新v2改为实际new_入口后执行AnnotateIncremental并成功保存。

实验预先冻结R?→R1及其他实例保持，fill-holes/preserve-designator/match-common-pins开启、include-nonprimitive关闭。实际R?仍未编号，非目标层次块halfadd_A/halfadd_B变为halfadd_A1/halfadd_B1。定义、全部已建模状态及unit identity不符，连接对象图与缓存逻辑图相同，整体false。没有把实际结果覆盖为预期，也没有发布自动编号工具。具体参数/primitive/occurrence语义根因仍待调查，不能据此断言SDK不支持。

只读新进程审计复现这三个差异，原失败report、expected.json与annotated.dsn的前后hash保持。ISS-E03-native-incremental-target-scope记录open，完整E03门禁由partial转deferred并移至队尾；显式single-unit/whole-package映射已验能力保持可用。后续先推进其他独立功能。

## 基线与复现

生产代码及185工具契约与第73批hash保持；未更改生产代码/测试，沿用此前466回归465通过/1原权限skip，本批没有伪称新跑完整回归。34现5 passed、1 baseline、14 partial、12 deferred、2 planned，整体active。

原创跨页夹具工具：tools/prepare_crosspage_reference_fixture.py、fixture_crosspage_references.tcl；实际MCP：tools/smoke_crosspage_reference_mcp.py。三个路径参数均为--install-root/--workspace-root/--fixture-root；workspace-root为不存在的新目录，夹具输入为第45批multiunit-placement原始报告根，MCP输入为通过的跨页夹具根。编号实验脚本及运行输出本机保留于.local，证据hash见batch-74-evidence.json。

# 第十五批：库创建逻辑位置修复与页面重命名复测

2026-10-23。公开工具仍82，无新增未验收库/页写工具；L02/E04均仍partial，整体34项必需范围保持active。

## 库创建故障定位与修复

旧`.local/library-create-f6355f7ec1`只有dbo_error，不知道失败方法。本批保留旧脚本，在create_library_probe.tcl加入固定阶段与native code；`.local/library-create-traced-20261023/report.json`复现到第二个NewSymbolPinScalar，code1106。CreateLib/package/cell/part/device/首脚均已走过，并非CreateLib接口不可用；不把裸错误码猜成许可失败。

已读取本机官方主参考p178 CreateLib/SaveLib、p215 NewPackage/NewCell/NewPart、p586 AddPart、p598-599 package属性/NewDevice、p726 NewPinNumber，以及官方MdlANDSymbolCreate.tcl的generatePinNum/makePin相关段。后者按i显式初始化DboTclHelper_sMakeInt i；旧夹具每次默认0，随后把返回logical position用于symbol pin，导致两个脚没有预先独立的位置。

原失败脚本保留。新create_library_positions.tcl预声明logical positions 0、1，physical numbers 1、2，并核对GetPinPosition等于所声明位置；不从失败后的实测倒写预期。`.local/library-create-positions-20261023/expected.json`在native调用前保存完整独立脚表。

新原生流程保存成功，独立LibraryService新进程重开：package/device/cell/part各1、pin2；A/1/position0热点(-20,0)、B/2/position1热点(20,0)，type4、visible=true，单元A position0、cell MCP_R_CELL、part MCP_R_PART、size1/homogeneous及MCP_TEST_FOOTPRINT均符合预期。新OLB hash保留，未覆盖任何已有OLB。reference template持久性尚未由独立query读取，未把setter返回成功扩大为此项已验证。两个引脚之间尚无已验收图形body，不能据此称完整符号绘图已完成。

原库创建issue仅在“原单单元夹具创建/保存/独立重开”的范围结案；typed MCP create plan/apply、生命周期故障、更多pin类型/隐藏脚、符号图形、编辑、多unit/共享/variant等仍需要完成。

## 页创建与重命名

此前Page.SetName失败，本实现已按官方p362 DboSchematic.Rename(pPage,newName)修正。本批`.local/page-rename-retest-20261023/report.json`完成3例：FULLADD副本.HALFADD新增空页、该空页再重命名、从独立原副本重命名原有元件页。每例均完整保存/独立重开/expected definition+pin-net比较及open_output衔接通过，官方源DSN hash前后不变。CapturePages.verify补充来源postcondition，避免验证期间source改变仍发布。

原page rename issue按此范围结案。尚未核验occurrence、hierarchy依赖、完整连接/图形对象、全项目OPJ重命名引用等；新设计/schematic CRUD、页删除及依赖拒绝也未完成。当前页编辑类未注册公开MCP，不把内部原生正例当作完整E04可用。

## 回归与下一步

当前最终222回归221通过、1原文件symlink权限skip（`.local/regression-222-library-page-final-20261023.txt`）；第十四批82工具契约保持。不存在新的真实Cadence GUI操作，均独立Tcl/Dbo副本。

下一优先将已可原生实现的库创建和页操作接成定型MCP，并补ref模板/完整图形及依赖/生命周期保护；随后推进多单元/缓存/编号/层次及DRC，PSpice CLI等遗留仍原范围必需。不自动提交推送。

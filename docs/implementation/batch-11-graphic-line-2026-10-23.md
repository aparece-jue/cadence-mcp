# 第十一批：装饰直线新增

2026-10-23，D05保持partial，整体目标active，34项必需范围不变。

## 依据与实现

已读取本机Capture Tcl/Tk Extensions PDF p450 NewGraphicLineInst、p309 GetDboLine、p686 GetStart/GetEnd、p300 GetOffsetGraphicPoint。使用图形instance，不用电气wire画装饰线。capture_graphic_line.py与固定graphic_line_probe.tcl提供新增和只读核验；后者命名probe但已由定型工具调用，无任意Tcl/eval入口。

新增plan/apply/jobs/cancel/recover五个MCP工具，实际75；capture_open_edit_result新增固定graphic_line kind。只支持零旋转、零镜像的新直线；局部(0,0)到(end-start)，instance位置=start，全局端点必须等于输入。坐标、名称、数量、输出与持久plan大小有界，bool坐标拒绝。页名/schematic名唯一，源hash/revision锁定；不修改源。

保存后新Capture进程核对整份定义/pin-net、连接对象，以及目标页所有graphic line的局部/全局端点与pose多重集。保留重复线数量，不按ordinal跨进程比对。图形线与电气线重合仍必须保持原电气连接，不从交点推断电气含义。只有验证成功和artifact hash一致的输出可继续编辑。

## 证据

- `.local/graphic-line-20261023/expected.json`在调用前定义(330,310)-(490,310)装饰线与全设计连接不变。report.json证明native新增、保存、新进程读取局部/全局端点正确，源hash不变。
- `.local/graphic-line-mcp-20261023/report.json`真实stdio75工具：schema校验、degenerate/extra参数拒绝、原生保存/独立重开/输出衔接、pending cancel、jobs分页、新服务幂等与已成功artifact复核通过。recover案例是成功artifact再校验，不是receipt丢失或native中断故障证明。
- 4项主机测试：重复几何多重集、不合法坐标/溢出/外页、陈旧source/取消阻止原生调用、畸形native文档拒绝。初次测试夹具缺mock Tcl路径，已修正；4项最终通过。
- 完整207回归206通过、1原文件symlink权限skip，见原始输出。未把skip计为通过。

## 仍需实现与验收

D05的文字、字体、装饰框/弧/多边形/其他图形、编辑删除和标题栏仍待完成；当前工具不核验line style/width/color、其他图形类型、页面裁切、其他器件属性、occurrence或原生DRC。缺失receipt、保存中断/真实取消/超时/故意损坏输出的graphic-line专属矩阵仍需补；不能借用其他writer证据宣称完成。

V03原生DRC仍未执行。本机capRunDRCConfigData只关闭配置框，capTrueRunDrc只返回true，均不是成功报告。继续查实际执行上下文和本次报告来源后才能注册业务工具。

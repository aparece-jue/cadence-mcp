# 第六批：未绑定引脚读取、放置与原生连线

2026-10-23。目标active，34项required和最终门禁不变，实际MCP工具仍54个；新增写入仅为内部验收fixture，尚未开放通用放置/布线工具。无GUI、真实工程/安装写入或提交推送。

## 已通过的工作

### C01共同依赖修复

新测试页导入ANALOG.R两只电阻后，库复制/创建实例/设置位号/保存均成功，但基础Capture.open失败。只读诊断定位为R101.2的GetNet：返回NULL，DboState.Code=1021、Severity=2、Failed=true，消息为Object Not Found。原读取器把无网络绑定当作致命读取错误，之前CMOSCPU/TUTOR2及移走导线热点的姿态fixture也受此类问题影响。

修复仅接受GetNet的**NULL+1021**，或无错误的NULL，表示无原生net绑定；非NULL+失败、其他NULL错误码、GetNetName失败均仍拒绝。为GetNet/GetNetName分别使用新状态对象，避免复用失败状态。`connected`字段继续仅表示原生net绑定，不能由此单独推出完整电气连通、junction或层次语义。

候选修复曾显式调用delete_DboState：Tcl mock通过，但真实DLL发生读取失败/3221226356退出。该候选立即撤回，生产读取器恢复基线后，再在独立适配器目录测试替代版本。最终采用现有读取器的worker生命周期方式，不原始删除构造器返回的状态代理；状态数量受对象上限约束，进程退出后回收。不能据mock测试声称已证明 native 对象所有权，也未做峰值内存/长期浸泡验收。

独立候选4案例全部通过后才合入生产，再经真实stdio MCP4案例复验：

|样例|schematic/page/part/pin观察数|无绑定引脚观察数|核验|
|---|---|---|---|
|FULLADD|2/2/9/41|0|与既有独立计数一致，分页完整|
|CMOSCPU|3/3/27/155|32|先前失败的打开和分页现在通过|
|TUTOR2|1/1/38/221|37|先前失败的打开和分页现在通过|
|原创新双电阻页|2/3/11/45|4|原9件/41脚加2件/4脚；四脚身份与无绑定预期一致|

CMOSCPU/TUTOR2的总数为本次观察，未将其当作独立人工计数oracle。所有源前后hash一致。5项Tcl状态组合回归通过，包括未知错误拒绝及禁止重新引入失败的raw delete方式；它们不证明真实内存生命周期。完整回归178项：177通过、1项原有文件symlink权限跳过。

### D01放置首个原生闭环

在HALFADD的新MCP_PLACE测试页中，从只读官方ANALOG.OLB副本CopyPackageAll到设计缓存，选择cached device/part并NewPlacedInst放置R101/R102。官方库与FULLADD源hash未变。修改前已写expected.json：两个中心位置(300,300)/(500,300)，旋转/镜像为0，各物理脚1/2的位置分别(290,310)/(330,310)、(490,310)/(530,310)，四脚均无绑定。

最初保存成功后因C01失败而未验收；修复C01后，**只读重验同一已保存artifact**通过上述预期，剔除新增两件/四脚后，原设计定义基线保持一致。没有重放原写入。仅证明该两实例、单device、未旋转/镜像的fixture；通用放置工具、复杂device/缓存冲突/引用身份与其他姿态仍未完成，不关闭D01。

### D03/D04实际导线与alias

从已验证的双电阻artifact再制作新副本，NewWireScalar连接(330,310)到(490,310)，在线端创建MCP_MIDDLE alias，完整保存并独立重开。事先固定四脚节点表：R101.2/R102.1绑定MCP_MIDDLE，R101.1/R102.2无绑定。四脚比对通过，整份修改前定义仅按这两脚的明确预期改变，其他定义保持；新页恰好1条线、1个alias，端点和alias→wire关系核对通过。

这是直线与alias的一个正例，不代表编辑/删除、交叉、T结点、重叠、global/NC、bus或全局/局部隔离均通过，也未验收字体/图面效果。

### V01实际MCP正例和断线负例

同一份提前声明的四脚表经真实MCP `capture_compare_connections`：正确串联fixture通过4条，未连线fixture准确报告中间两脚2条mismatch。两份原始fixture均未改动。比对范围仍为selected definitions，41个其他引脚未被这份人工表覆盖，designPassed=null；不将其称为全设计或DRC通过。

## 保留的失败

- C03重新运行**未改变的**八姿态oracle：r0/m0通过；r1/m0时原生实际热点相对简单仿射预期出现统一Y+40偏移，检查后停止。报告有2个attempt记录，仅1个通过。之前基础open阻塞已解除，但定义局部坐标/实例原点/旋转参考的关系仍需官方依据和独立oracle核实，不从实测倒写预期。新issue保留C03 deferred。
- 故意短接fixture在opening阶段失败，未执行短接，原始日志不足以确定GetDesign/GetSchematic/GetPage哪一步失败。首次组合脚本因此没有进入任何MCP comparison。此失败后移；随后用独立只读比较脚本完成了已有正确/断线两项，**短接仍未验收**。不得把脚本失败当成检测器成功识别短接。
- 先前L02/P02/H01/L04/E03/E04/P04及symlink问题仍按机器矩阵保留；本批未替代其完成标准。

## 依据与证据

本机Capture主PDF147–148页：DboState.Code/Message/Failed；542页：PortInst.GetNet；218/226页：CopyPart/CopyCell/CopyPackageAll；424–425页：NewPlacedInst；432/434页：NewWireScalar；495–496页：NewAlias。Object Not Found状态组合由本机24.1真实运行核实，不宣称其他版本自动兼容。官方capDB/capExportDesignCache.tcl等显示CopyPackageAll实际使用；不复制其源码。

- `.local/placement-521716d26a/`：提前预期、已保存native receipt/phase、最初读失败及未变源hash。
- `.local/definition-diagnostic-0c36a4d608/`及`definition-diagnostic-b0a9a2ce36/`：只读故障定位、NULL/1021原生消息。
- `.local/definition-fix-8ab816a3e4/report.json`：错误状态释放候选的4案例失败记录。
- `.local/reader-candidate-fe7a4d9cad/`、`.local/definition-fix-1712d44e3c/report.json`：独立候选4案例通过及双电阻热点/引脚验证。
- `.local/definition-stdio-20261023/report.json`：生产真实MCP4案例通过。
- `.local/pose-matrix-1fc81bf46d/report.json`：C03新坐标oracle失败。
- `.local/wire-alias-0666b70746/`：提前节点表、native保存、独立重读、正确连接及线/alias几何。
- `.local/connections-positive-negative-20261023/`：短接fixture在打开阶段失败，0项MCP比对执行。
- `.local/connections-read-20261023/report.json`：独立MCP正确/断线2案例通过。
- `.local/regression-178-reader-20261023.txt`：完整回归原始输出。文件hash见batch-06-evidence.json。

公开原创fixture脚本为tools/fixture_place_resistors.tcl、fixture_connect_resistors.tcl、fixture_short_resistors.tcl；它们要求host-created copied设计及固定测试页，并非对外业务API。复现读取用tools/smoke_definition_reads.py的install-root/workspace-root/可选placed-design；节点正反例用tools/smoke_connection_reads.py的install-root/workspace-root/placed-design/connected-design及可选shorted-design。旧组合脚本保留用于复现原失败，不将其当可用创建短接入口。

下一步把放置/直线alias流程接入持久typed业务工具，补故障/取消/幂等和全部原定绘图条件，推进图形/原生检查；C03和短接fixture失败后移。最终仍需34项逐项全部验收。

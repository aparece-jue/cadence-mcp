# Capture到PSpice原生网表路径调查

本批以安装内资料和实际DLL为依据，新增内部诊断，不开放未经验证的生成工具。

## 运行时与接口

官方`capPSpiceServerClientOperation.tcl`中的createPSpiceNetList仅打印消息和常量返回，是占位实现。没有调用它冒充成功。官方OrPSpiceServerClientOperation指向orPspNetlist64；实际加载该DLL及orTclNetlist64成功。递归namespace前后差异修正后分别新增205/10命令；这不是MCP工具数。初报告因只记录根namespace基线混入旧Tcl命令，保留原记录，以v2为有效delta。

固定100个错误参数的调用只获取wrapper拒绝诊断，不打开设计。安装DLL字符串提供运行时类型签名：OrTclNetlist_sCreatePSpiceNetList的design/output、DRC-marker/legacy/subcircuit/hierarchical/descend/name-preference六个bool及license参数。日志vector使用官方DboTclHelper_sMakeStdVector/sGetVectorSize/sGetConstCharPtrFromVector（Tcl手册p757–764），不是读取旧session日志。

## 实际生成失败

仅将官方LOWPASSFILTERS.DSN复制到新私有目录，预先确认target不存在，不复制历史NET。缺失DSN负例也原生return0但无文件；有效副本调用return0却生成0bytes NET。故返回0、进程exit0、文件出现均不构成成功。

独立legacy模式采集到原生error vector：ORNET-1165 Unable to initialize pspice explorer while creating netlist file；session仅显示Writing PSpice Flat Netlist，netlist vector为空。2参数最小调用被重载拒绝，不能据此猜默认值可用。

COM初始化假说采用同一安装Tcl嵌入独立Python进程，在承载原生Tcl的同一线程分别none/STA/MTA，三种均同样ORNET1165/0bytes。只初始化COM不能修复；没有证据认定许可证缺失、DSN本身非法或接口必须依赖桌面点击。首版宿主误用不存在的tcl86t.dll，3case启动失败保留；改本机实际tcl86.dll后v2才是有效对照。未使用安装目录旧NET替换新产物。

## 证据与状态

- `.local/netlist-runtime-20261024/report.json`：初命令盘点；`.local/netlist-runtime-v2-20261024/report.json`：正确递归delta。
- `.local/netlist-signatures-20261024/report.json`：固定错误arity拒绝信息。
- `.local/capture-pspice-netlist-20261024/report.json`：真实缺输入/官方副本调用。
- `.local/netlist-modes-20261024/report.json`：原生模式及日志。
- `.local/netlist-com-20261024/report.json`：初宿主DLL名错误；`.local/netlist-com-v2-20261024/report.json`：none/STA/MTA有效对照。

batch-36-evidence.json核对5份有效输入副本hash仍等于官方源、NET均0bytes、所有自有进程0及最终脚本hash。仅完整性确认，不接受网表。V04新增ISS-V04-pspice-explorer-initialization后移，仍需正确宿主初始化、profile/依赖闭包、真实NET/CIR及节点预期、持久任务和原完整门禁。

下一通过已有authenticated bridge核对私有Capture/PSpice宿主上下文；不提供任意Tcl/eval公开入口。原34完整范围保留，全目标active，工具137，最新全回归仍294项293通过/1权限skip。本批无公开生产Python/schema变化，不重复无修改回归。无GUI、安装目录/真实设计修改、提交推送。

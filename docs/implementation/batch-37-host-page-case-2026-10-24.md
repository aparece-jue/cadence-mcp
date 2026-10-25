# 宿主启动、页加载对照及网络名大小写检查修复

## 已修复的业务问题

本机官方`doc/cap_ug/Assigning_Net_Aliases.html`明确Capture保留名称大小写，但比较电气连接名称时忽略大小写。公开符号改名工具原先仅精确比较已存在wire/alias/global/offpage/port名称，可能漏掉大小写不同的冲突。现统一casefold比较这五种已知连接定义，排除选中符号自身和caller声明wire。不放宽原生保存回读门禁，也不把前置名称判断当连接证明。

`.local/net-symbol-case-guard-20261024/report.json`真实137工具MCP：既有MCP_MIDDLE，对mcp_middle、McP_MiDdLe、MCP_MIDDLE三种改名都以net_symbol_merge_unsupported在创建写计划前拒绝；durable plan文件为0，源和私有副本hash保持。不是新增原生写入通过证据。

新增2项测试覆盖所有五类已知连接名的大小写冲突及自身/owner wire不误拒。完整回归296项295通过、1原文件符号链接权限skip，`.local/regression-296-net-symbol-case-20261024.txt`。历史间歇目录句柄问题仍open，不凭本次绿色关闭。工具仍137，schema未变。

## Capture宿主启动未通过

当前没有Capture可复用会话；旧绑定PID不可复用。独立netlist API已报ORNET1165，故按用户授权的必要宿主例外启动一次受控Capture，使用官方`Capture.exe command-file.tcl`，脚本第一条即写私有PID回执，之后才做命令inventory，不打开设计或调用业务。

`.local/capture-host-bootstrap-20261024/report.json`：45秒超时，bootstrapReached/inventoryAvailable均false，剩余自有进程0。此次实际启动应用，但无桌面点击；没有证据说明许可、模态或具体启动原因。未建立可认证会话，未进行网表或DRC验收。附到V03/V04既有issue，不反复重启。

## 页加载对照未通过

按Tcl手册p343 ReadAllPages、p354 Expand，对已冻结的cross-page和copied-port两份失败DSN，只在读取进程内初始化，不save。`.local/schematic-expansion-20261024/report.json`共4case失败：read_all分支报3969；expand分支也在其前置ReadAllPages就失败。Expand本身未执行，不能声称Expand无效。源hash保持、自有进程0，不改原期望/失败报告、不忽略状态。

下一推进新建设计的初次保存顺序专项及多单元剩余验收，已失败宿主/页/flat网络继续保留并后移。原34项完整范围未缩减，目标active。未修改安装目录或真实工程，无提交推送。

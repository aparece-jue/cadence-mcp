# 本机核查与证据

## 1. 方法与范围

仅检查 `D:/Program Files/Cadence/SPB_24.1`、`D:/workspace/git/cadence-mcp-public` 和当前工作目录。没有安装插件、启动其网络服务、运行其 EXE、打开真实设计或调用设计保存。使用本机官方 HTML 文档作为主要依据；PDF 仅检查存在、长度和指纹，没有声称通读其方法签名。没有联网获取其他版本资料。

读取前序聊天后，只取得用户问题和助手正文引用标记，无法恢复助手完整方案。当前设计以本次明确要求为准。工作目录已有仓库审查报告及解码副本；本轮重新解码原仓库的 19 个 `.enc` 到内存并逐一比较，全部匹配，再核对相关源码。没有将旧报告中的运行结论冒充本轮测试。

Git 命令访问目标目录返回 Permission denied；通过只读 `.git/HEAD` 和其指向的 `refs/heads/master` 取得当前提交。没有据此声称工作树干净，也没有 fetch 或核查远端最新状态。

## 2. 安装与文档索引

以下路径以安装根目录为前缀。完整 SHA-256 见 `evidence/inventory.json`。

|证据 ID|文件/目录|实际意义|
|---|---|---|
|C01|`tcltk/bin/tclsh.exe`、`tcl86.dll`、`wish.exe`、`tk86.dll`|独立解释器和 Tk 文件存在；本轮只运行 tclsh，未验证 Tk 窗口|
|C02|`tools/bin/Capture.exe`|文件版本 24.1-2024；未启动 GUI|
|C03|`tools/bin/orDb_Dll_Tcl64.dll`|文件版本 24.1.0 d001；加载入口 DboTclWriteBasic 本轮已探测|
|C04|`tools/capture/tclscripts/OrCAD_Capture_TclTk_Extensions.pdf`|Capture Tcl/Tk 扩展详细参考存在；后续按类/方法查签名|
|C05|`doc/orcadtclgsg/Introduction_to_the_OrCAD_TCL_Environment.html`|官方说明 Capture 集成 Tcl 同时提供 UI 与数据库交互命令|
|C06|`doc/capinfomodel/dboimnew.html`|对象、容器、迭代器、层次与状态模型；它本身明确不是最终接口定义|
|C07|`doc/orctclcap/`|属性、库引脚、occurrence、网络选择等具体 Tcl 解决方案|
|C08|`doc/orctclsample/TCL_Programmimg_with_OrCAD_Capture_GUI_Interface.html`|GUI 菜单、会话与延迟加载示例，不能在独立 Tcl 中直接假定可用|
|P01|`tools/bin/psp_cmd.exe`、`pspice.exe`|后台 CLI 与交互程序实际位置为 tools/bin|
|P02|`doc/cap_ug/Running_PSpice_in_Batch_Mode.html`|明确区分交互和非交互模式；CLI 参数为 `/r <cir文件>`|
|P03|`doc/psptclcmdref/PSpiceSetupAnalysis.html`|四个参数 cir/out/dat/libpath；返回 bool；不是 Dbo API|
|P04|`doc/psptclsample/Accessing_PSpice_using_TCL_Scripts.html`、`Modifying_Parameters_in_PSpice_using_TCL_Scripts.html`|引擎 Tcl、参数、温度、瞬态等示例；内部仍有旧 17.2 绝对路径|
|P05|`tools/pspice/tclscripts/pspDB/pkgIndex.tcl`|登记 orPspEng、PspCtrlTcl 等包；包标签 16.6.0 不等于安装版本|
|P06|`tools/bin/orPSP_ENG64.dll`、`oradvctrlr64.dll`|引擎与高级分析 DLL 实际存在；本轮未加载或申请对应许可证|
|P07|`doc/psptclcmdref/Accessing_PSpice_Data_Files_using_TCL_Commands.html`|loadFile、getDataNames、getJSON、分块数据等读取命令目录|
|P08|`tools/pspice/tclscripts/pspQuickView/orpspExtractTraceFromDat.tcl`|使用 orPIOData64.dll 与 orPIOObject 读取/抽取 DAT；不能把 DAT 当 CSV|

文档中的 `tools/pspice/psp_cmd.exe` 示例路径与本机不一致，应查找实际文件，不能机械拼接。24.1 文档保留旧版本路径和先决条件，因此文档版本、文件版本、包版本、运行时能力分别记录。

官方实例还包括 `tools/pspice/tutorial/capture/pspiceaa/Snubber/.../transient.cir`、`share/orcad/tutorial/tutorial-PSpiceFiles/SCHEMATIC1/TRAN/TRAN.cir` 等。后续测试需复制工程和引用闭包，不能原地执行安装内示例。仅复制 CIR 不保证其 INCLUDE、LIB、STIMULUS 等依赖齐全。

## 3. 本轮运行结果

### Capture 独立 Dbo 探测

执行自写 `runtime_probe.tcl`；仅加载 DLL、枚举命令，不创建 session，不打开 DSN/OLB。

- Tcl 8.6.5；pointerSize=8；Dbo 会话创建命令加载前为 0，加载后为 1。
- `load ... DboTclWriteBasic` 的 catch 返回 0；结果字符串却为 `can't read "lBuild": no such variable`。这不是 Tcl 异常返回；命令注册已确认，但不能据此保证所有功能正常。
- `DboTclHelper_sCreateSession`、`DboState`、`DboSession` 可见。
- `GetActivePage`、`GetSelectedObjects`、`orExecuteDrc`、`orExecutePst` 在这个独立进程中不可见。结论限于本次环境、加载顺序和这些名称，不表示所有非 GUI 导出方式都不存在。

证据：`evidence/runtime-results.json`。技能已有的 DSN 写入经验只是后续实现参考，不是本轮兼容性通过记录。

### PSpice CLI 探测

在工作目录内新建一次性分压电路，没有使用真实工程。

|运行|结果|可证明与不可证明|
|---|---|---|
|首次，字符串节点 IN/OUT|约 26.11 秒，exit=1，生成 OUT；ORPSIM-15090，PRINT/PROBE device OUT undefined|CLI 能启动并完成输入检查及错误报告；尚不能确认此表达式失败的根因|
|第二次，改为数字节点 1/2，V(2)|30 秒超时，捕获输出为空；没有新 OUT/DAT|启动过程/许可证/进程等待等原因未定位；不能宣称仿真成功或确认许可证失败|

第二次进程被 Python 的 timeout 机制终止，状态为 `timeout_indeterminate`。scratch 中残留的 `divider.out` 是首次运行的旧文件，内容仍为 IN/OUT，**不是第二次结果**。因此契约必须使用每个 job 独立目录、运行前后文件指纹与时间检查，不能用“OUT 存在”作为成功条件。

首次材料为 `evidence/divider-first.cir`、`divider-first.out`、`runtime-results-first.json`；第二次输入位于 `evidence/scratch/divider.cir`。本轮没有有效 2.5 V 数值，没有波形解析通过记录。超时机制只保证所启动的直接子进程结束，未实现 Windows Job Object 的完整子进程树管理，必须在实施时补齐。

## 4. 仓库实现与采用判断

快照提交：`1cbe53f3b915f996215e869253625ce445068b4e`。EXE SHA-256：`897402159f2393c6a7e20da620f520fb9a10862aef2f7162d68e0eaecae7a662`。

有 13 个 CadenceMCPTool Tcl 模块和 6 个 CaptureCoreKit 模块，以 Base64 `.enc` 存放；加载器自己解码后执行。Base64 不是密码学加密。未发现 MCP EXE 的明文源码、可核对的工具 schema、构建清单和测试套件；不能将 TCP 命令当成已核实的 MCP tools/list。

以下行号对应工作目录已有的 `repo-audit/decoded/capture-tcl-crypt/CadenceMCPTool/` 可读副本，本轮比较确认与原仓库对应。

|实现证据|后续设计要求|
|---|---|
|server_core.tcl:11–12 声明 127.0.0.1:8888；343、346 实际固定 19984，socket 未指定 -myaddr|配置和实际监听统一，显式回环地址，按实例分配端口并握手核对 PID|
|server_core.tcl:210–220 未知命令分支 eval 输入|只接受已注册 typed operation；不设任意 Tcl 执行工具|
|server_core.tcl:312–327 无认证接入；字符串按换行/竖线分隔|增加本地会话令牌、版本、请求 ID、帧长度上限、正规的 JSON 编解码|
|circuit_query.tcl:183、204、212 依赖选择并有手写 JSON|selection/page/design/occurrence 查询范围明确，所有结果统一编码|
|draw_pins.tcl:56、place_netalias_db.tcl:18 使用 U1* 式前缀|稳定对象定位，精确匹配，不能把 U10 或 U1A 当成同一器件|
|place_netalias_db.tcl:24 等复位旋转，其他电源脚本也有类似操作|保持姿态，读取实际引脚热点，修改前后比对连接|
|rename_refdes_by_page.tcl:93、409 从 root schematic 遍历|区分设计定义与 occurrence，重复层次独立定位|
|主要写脚本缺完整保存/重开闭环|内存完成、保存完成、独立重开验证分别报告|
|install.bat 覆盖加载配置并清理旧目录；初始化 after 5000 自动启动|首版外置手动加载，不改 capinit、不运行原安装器|

仓库可以帮助理解 Capture 任务拆解，不适合直接作为新系统的可信运行基础。建议独立实现统一服务和薄桥接；能否复用具体代码还取决于 README 的内部/授权许可，不将其复制进待发布的新项目。原 EXE 的行为、真实 MCP schema、连接端口和兼容性仍未知。

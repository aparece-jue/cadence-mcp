# 无对话框 Print 可行性验证

日期：2026-10-22。用户要求 Microsoft Print to PDF、横向、工程目录/pdf、工程名加版本号或时间戳。测试仅使用自建文字 fixture；没有打开/修改真实设计或 Cadence 安装文件，也未改变全局打印机默认值。

## 实测结论

|层次|结果|证据与边界|
|---|---|---|
|目录与命名规则|已实现 helper，独立测试|创建 pdf，使用 OPJ/DSN 名称、显式版本或本地时间戳，拒绝非法名称与同名覆盖；不执行打印|
|Windows 无对话框打印|已实际通过|固定 PDF 队列，按任务 DEVMODE 设置横向，DOCINFO.lpszOutput 指定完整新路径，GDI 输出测试文字；没有点击任何窗口|
|PDF 文本和方向|通过测试文字 fixture|pypdf 读取到 CARRY_OUT/U1A/X_BAR，页面 841.92004 × 595.32001 pt；渲染已视觉检查|
|Capture 原理图 → 无界面 Print|尚未证实可行|没有找到并验证受支持的原理图打印调用；Windows 成功不证明 DSN 能直接打印|
|Capture GUI Print|此前已验证|实际原理图两页，用户确认搜索/复制；仍需 GUI 运行上下文和打印入口|

## 本机核查

- Tcl API 索引 5,699 项中仅检出通用打印相关 PrintGrid 和 CapPdfPrint，Dbo 边框/网格/标题栏打印属性不提供完整页面渲染入口。
- 安装内 `tools/capture/tclscripts/capPDFExport/tcl/capPdfUtil.tcl` 显示 printPdfEx 调用 CapPdfPrint，使用 PostscriptDriver 选项及后续 PS 转 PDF；这属于此前被否决为默认交付路径的 Export 流程，未尝试将其伪装为新 Print。
- `capTCLMenu.tcl` 出现 FilePrint/FilePrintSetup 菜单标识；菜单名称与回调过滤配置不能证明对应 Tcl 可执行入口或无对话框参数。
- 本机官方 `doc/cap_ug/Launching_OrCAD_X_Capture.html` 的启动参数说明列出 version/viewer/product/ini，未列出可指定 PDF 路径的打印参数；不能据此推断所有未文档化参数都不存在。
- 官方 Printing and Plotting / Print dialog box 描述的是 Windows 对话框工作流。旧参考仓库中未检出可复用的受支持原理图静默打印实现。

上述核查有范围限制，结论为“尚未找到并验证”，不是证明 Capture 绝对不能实现。全无窗口与“Capture 进程运行但无需点击/弹框”是两种不同能力，应分别登记。

## Windows 探针

`tools/native_print_probe.py` 是独立手动诊断工具，不是 MCP 工具，不接受打印机名称或可执行脚本。只打印明示的自建文字，不读取 DSN，不渲染设计。传入新的 PDF 完整路径后，OpenPrinterW → DocumentPropertiesW（仅任务内 DEVMODE）→ CreateDCW → StartDocW（指定输出）→ TextOutW → EndDoc。没有设置 DM_IN_PROMPT，没有修改队列端口或调用 SetPrinter。

原始文件留在本次任务工作区 `tmp/native-print-probe/pdf/`，不提交。原型只支持单操作者手动测试：同名预检不是跨进程原子保留，不能直接开放为并发生产工具。生产任务还需执行超时、job 状态确认、隔离暂存及拒绝覆盖发布。

Windows API 参考：

- [DOCINFOW / lpszOutput](https://learn.microsoft.com/windows/win32/api/wingdi/ns-wingdi-docinfow)
- [DocumentProperties 修改单次打印设置](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/main/support/windows/win32/modify-printer-settings-documentproperties.md)
- [DEVMODEW](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-devmodew)

## 后续判定门槛

优先核对一次原生 Print 的官方 Tcl 命令日志，确认打印动作是否记录了可重放入口和设置。记录日志时允许一次有人监督的 GUI 操作，但重放验收必须不点击对话框。若记录仅是 UI 动作或仍需弹框，保持 capability unavailable，进一步向 Cadence 官方核实 SDK/打印接口；不把隐藏窗口、自动按键、默认打印机或注册表端口改写包装成无 GUI 接口。

只有真实测试原理图通过正确工程绑定、两页范围、Microsoft PDF 队列、横向、指定新路径、文字提取与查找、图面复核，才发布对应能力。当前 MCP 仍只有原有 7 个只读工具。

## 本轮补充：实际尝试官方命令日志

通过 computer-use 在测试副本开启 Journaling / DisplayCommands，开启前两项均为 0，并设置 180 秒恢复定时器。选择测试设计根节点后实际完成一次原生 Print 和 PDF 保存。Capture 输出 PRINT_LOG_RESTORED，设置恢复为原值。日志目录 Thu_Oct_22_17_42_59_2026 已创建，但 OrCaptureLogFile.captcl 在检查时为 0 字节，没有得到可重放调用或打印设置 XML。

这次日志探测没有提供可用入口；因未取得其他动作的正向记录作为对照，不将空日志解释为“所有 Print 行为绝对不支持 Tcl”。未尝试用假设的 Menu/FilePrint 命令盲目重放，也未声称无窗口验证通过。

按本轮规则的 helper 明确绑定测试工程 GUI_FULLADD.opj，创建工程旁 pdf 子目录，并输出 GUI_FULLADD_print-log-check.pdf（显式诊断版本标记）。该原理图文件通过 GUI 打印生成；两页均横向，CARRY_OUT / X_BAR 文本提取正常，两页渲染已复核。SHA-256：b9d192c1425b470831d7e84867b9c48e557df8f46310f2ede8dce38d00494af0。测试副本、安装示例与已有真实 DSN 的 hash 均未改变。

当前测试 22 项：21 通过，1 项因符号链接权限跳过；新增 6 项覆盖指定默认值、中文工程名、目录创建、时间戳、同名保护、非法版本与越界目标。没有增加对外 MCP 工具。

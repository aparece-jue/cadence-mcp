# 复现 GUI 验证

仅在临时工程/副本上运行。原生 DRC 可能自动保存设计并创建 marker、DBK 和 OPJ；不要在真实工程上试验。详细结果与边界见 [本轮记录](validation/gui-2026-10-22.md)。

1. 将测试 DSN 复制到新的本地输出目录，记录原文件 hash；启动 Capture 并确认没有在真实工程上执行操作。
2. 在 Capture Command Window 加载仓库中的 `tools/gui_probe.tcl`。
3. 调用 `::cadenceGuiProbe::run <副本DSN绝对路径> <输出目录>`；它打开副本，校验活动设计路径，生成带时间的探测 JSON。手工处理新 DSN 的项目类型窗口，并复核结果。
4. 用 Capture 原生 Design Rules Check 对话框复核范围、规则、模式及报告路径，然后 Run；等待当前报告完成，保留错误和警告，不为测试通过关闭规则。
5. 使用 `tools/summarize_drc.py --report <本次报告> --output <新的摘要JSON>` 读取诊断。摘要不证明执行完成，需要与 GUI 操作、时间和工程路径证据一起核对。
6. 在项目树选择测试设计根节点，打开 File → Print。Setup 中选择已验证的 Microsoft Print to PDF；本次采用 A4 横向、Scale to paper size、600 dpi、Inst. Mode。范围和纸型必须按目标工程复核，不将本次设置硬编码为通用配置。
7. 打印到新的 PDF 路径，检查文件新生成、预期两页 FULLADD/HALFADD、页清单与渲染图面。
8. 用独立 PDF 解析器检查逐页文字：第一页 CARRY_IN、CARRY_OUT、halfadd_A、U1A；第二页 X_BAR、U2A、U3A。再执行文字层关键词查找并提取命中范围；不得用 OCR 补字冒充原生文字通过。正式交付还需在目标阅读器复核全局查找和选择复制。中文、特殊字符、不同字体/驱动另设 fixture。
9. 复查安装示例和真实设计 hash。打印可能更新用户的打印首选项，不修改安装目录或真实设计。

`tools/gui_export_pdf.tcl` 属于历史 Export → PS → Ghostscript 验证，其 `run` 入口现已停止默认执行；显式 `legacyDiagnosticExport` 仅保留诊断用途。本机旧输出虽可显示图面，但文字提取失败，不满足交付标准。不要根据 `printPdfEx` 函数名误判为 File → Print。

Tcl 工具没有远程调用接口，路径检查不构成隔离恶意本机调用者的沙箱。GUI Print 仍是有人监督的验证流程，尚未接入 MCP。

默认打印机、横向和工程目录/pdf 命名约定，以及无对话框验证边界，见 [Print 可行性记录](validation/print-without-dialogs-2026-10-22.md)。

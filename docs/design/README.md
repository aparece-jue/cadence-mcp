> 当前实现进度：此目录保留初始设计和历史探测状态。第一阶段已实现只读原型，实际功能与验证边界见 [运行说明](../phase1.md) 和 [验证记录](../validation/phase1-2026-10-22.md)。

# Capture / PSpice 统一 MCP 设计包

日期：2026-10-22，Windows 本机，设计稿 v0.1。范围：Capture、OLB、原理图与 PSpice；暂不纳入 Allegro。

> 迁入说明：本设计包从先前工作目录整理而来。文中“本轮”“当前工作目录”和 repo-audit 路径描述的是 2026-10-22 原始核查现场；探测脚本、官方文档提取文本和第三方解码副本仍保留在原工作目录，未纳入本仓库。仓库中只保留原创方案、自建电路和选定探测记录，详见 evidence/README.md。

建议采用一个 stdio MCP Server，内部划分 Capture 和 PSpice 模块，共用环境发现、任务、文件副本、审计及规范引擎。Capture 再区分独立 Dbo 工作进程与 Capture 内 Tcl 桥接；PSpice 先用 CLI，后加引擎 Tcl 与波形读取。

这是一份可实施的设计基线，尚未创建或安装 MCP 服务。所有新增文件位于本目录；没有运行仓库安装器或 EXE，没有改动 Cadence 安装、原仓库和真实 DSN/OLB。

## 阅读顺序

1. [本机核查与证据](01-local-findings.md)：安装、文档、源码、实测与未知项。
2. [架构与模块边界](02-architecture.md)：执行链、模块、生命周期、Skills 拆分。
3. [工具与数据契约](03-tool-contracts.md)：工具清单、输入输出、错误、任务与桥接协议。
4. [兼容验证与实施阶段](04-validation-roadmap.md)：验证矩阵、测试工程、准入条件和交付物。
5. [独立设计规范体系](05-design-standards.md)：规则分层、覆盖、检查与豁免。
6. [核心契约 JSON Schema](contracts.schema.json) 与 [规则示例](standards.example.json)：供后续实现对齐的机器可读草案。

## 已确认与尚未确认

|事项|本轮结论|
|---|---|
|Capture Tcl/Dbo|64 位 Tcl 8.6.5；扩展加载 catch=0，Dbo 命令注册可见；没有打开设计|
|Capture GUI 能力|独立 Tcl 中未见已探测的页面选择、DRC、网表执行命令；GUI 内另验|
|PSpice CLI|`tools/bin/psp_cmd.exe /r` 可启动并报告电路错误；修正电路后的第二次运行 30 秒超时，未取得有效数值结果|
|仓库|提交 `1cbe53f3b915f996215e869253625ce445068b4e`；19 个 Base64 Tcl 模块与已有审查副本一致；MCP EXE 源码缺失|
|写入、保存、重开、DRC、波形|本轮未验证通过，列入后续分阶段验收|

关键决策：内部 API 目录可完整覆盖模块职责，逐项登记文档与验证状态；对 AI 暴露有边界的任务工具。Skills 写操作流程和验收方法，规范另行版本化。Dbo 仍由 Cadence Tcl 扩展调用，MCP 和 Skill 均不替代解释器。

`evidence/inventory.json` 固定文档、二进制及插件模块指纹；`runtime-results*.json`、`divider-first.*` 和 `scratch/` 保存本轮探测材料。文档提取文本仅供本机研究，不应随新项目公开发布。探测脚本可以复查环境，但运行 `run_probes.py` 会重写该脚本自己的 scratch 测试输入、结果和日志；需要保留本轮证据时先复制整个目录。




2026-10-23 桥接后当前业务阶段与验收条件见 [业务开发计划](06-business-roadmap.md)。历史初始状态不代表当前能力。

最新执行优先级及资料索引：[Cadence子模块实施清单](07-cadence-submodules.md)。先完成Cadence子模块，暂缓Skills/规范引擎与交付整合。

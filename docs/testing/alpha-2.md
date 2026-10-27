# v0.1.0-alpha.2 安装与试用

需要 Windows x64、Python 3.12+ x64、本机 Cadence 24.1 及对应可用许可证。此测试版含221个 MCP 工具；完整34项业务中6项全部通过，其余仍有未完成范围。

## 安装到新目录

解压到新的目录，例如 `D:\cadence-mcp-alpha2`。不要覆盖旧 alpha.1 环境。进入解压目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-deps -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps .\cadence_mcp-0.1.0a2-py3-none-any.whl
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import cadence_mcp; print(cadence_mcp.__version__)"
```

应显示 `0.1.0a2`。安装使用固定 wheel；后续研发源码变化不会改变此环境。依赖安装需要网络。输入放入新建 `inputs`，输出使用全新 `workspaces`。

## 客户端配置

修改 `mcp-client.example.json` 中 Python、Cadence 安装、输入/输出的绝对路径，将配置合并到所用 MCP 客户端；本包不自动修改客户端全局设置。服务使用 stdio，单独启动后等待客户端协议，不提供交互命令行。连接后先查询环境/能力和工具列表，预期221个工具。

## Capture 桥接功能

普通 DSN/OLB 查询和独立 CIR 仿真无需 Capture GUI。原生编辑布线/总线、原生网表任务需要一个已打开且干净的 Capture 工程以及显式宿主绑定；按包内 `GUI-BRIDGE.md` 使用随包固定管理脚本。请用测试工程副本，不用真实设计。不能把发现的进程直接当作认证绑定，也不要复制他人的 binding.json。绑定可能含认证信息，应只保留本地。

`capture_gui_instances`→`capture_gui_attach`取得 guiSessionId 后，原生布线需要同时给出 hostProject。多实例子页必须明确 editorOccurrence。任务写入自己的新副本，完成后恢复宿主并使旧 GUI 会话失效；下一任务重新 attach。独立只读会话与 GUI 会话是不同对象。

## 推荐新功能测试

1. 先调用 `cadence_get_environment`、`cadence_get_capabilities`，再对输入 DSN 创建工作副本并读取页面/引脚/属性。
2. 验证 `capture_query_bus` 的 bus/scalar/entry/pin_member。pin_member读取同页定义级原生网络成员及位置；入口接线和成员关系分开检查，不代表重复层次或 DRC 全通过。
3. 在测试副本中计划原生 wire_add/delete；声明页面全部引脚结果。确认 plan 后执行，再用 `capture_open_edit_result` 及独立查询复核。旧独立 Dbo 新导线路径仍有3969失败，新增布线应显式选择已验证的编辑宿主后端。
4. 计划普通竖直总线：2..128个连续成员，显式 branches 和完整页 expectedConnections。缺分支/脱离入口会标记 localEntryRoutingComplete=false，不能算完整设计通过。嵌套 Bundle 尚未验收。
5. 用随包 divider.cir 做独立 CLI DC，V(OUT)预期2.5V。参数 LIST 扫描显式用 CLI。Capture→PSpice另需对应 OPJ/profile 和明确库闭包，不把一个 DSN 副本当完整仿真工程。

接口参数与工具名请查包内 `tools-contract.json`。写入失败不要反复提交；保留 planId/jobId 和错误码，用对应 recover 仅验证恢复。已开始宿主任务不通过杀 Capture 取消；GUI异常时可能仍需人工恢复。

## 已知未完成与反馈

见 RELEASE-NOTES.md。特别是完整层次/嵌套 Bundle/DRC自动闭环、跨页供电与部分缓存字体、数字/混合 DAT、真实许可证失败仍有缺口。完整门禁6/34并不因工具数增加而改变。PDF延期，Allegro排除。

反馈请注明 alpha.2、Cadence版本、操作、工具参数中不敏感部分、预期/实际、错误码及任务号。真实 DSN/OLB、模型、许可证和私有绑定留在本地。

## 本版安装复测注意事项

本次安装复测：官方 CLI 三个独立任务均超时；只读窗口列表确认 psp_cmd 正在 Cadence Product Choices 等待本机产品选择。没有修改许可配置，没有把超时认定为许可证失败。此版 CLI 安装复测未通过；已有此前专项通过记录不替代当前结果。请先在本机正常完成 Cadence 产品选择，再单独测试 CLI。独立 Tcl 引擎本次新 DC=2.5V 与 DAT 已通过；两后端不会自动切换。

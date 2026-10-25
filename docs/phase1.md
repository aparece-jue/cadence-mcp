# 第一阶段：只读 MCP 原型

本版启动真实的标准 stdio MCP Server，发布 7 个工具。所有 Cadence Dbo 调用在独立 Tcl 子进程中执行；没有运行旧仓库 EXE、安装插件或修改 Cadence 安装目录。

## 安装

Windows、Python 3.12+，以及显式选择的 x64 Cadence 安装。生产依赖固定为 MCP SDK 2.3.0 和 Pydantic 2.14.1；构建依赖固定为 setuptools 82.0.1。`requirements.lock.txt` 固定本轮 Windows/Python 3.12 环境的传递依赖，不是跨平台通用锁文件。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

MCP SDK 的 stdio 传输、工具 schema、协议协商和工具错误由官方 SDK 处理；本版通过其底层 Tool 元数据固定未知字段拒绝策略，并配套契约测试。升级 SDK 必须重跑这些测试。接口依据：[官方 SDK 文档](https://py.sdk.modelcontextprotocol.io/)，本轮还直接核对了已安装的 2.3.0 源码与签名。

## 启动

以下路径是示例，需替换为实际安装、工作区与允许读取的工程目录；程序不写死本机路径。工作区不得与安装根目录重叠。

```powershell
.\.venv\Scripts\python.exe -m cadence_mcp.server `
  --install-root 'D:\Program Files\Cadence\SPB_24.1' `
  --workspace-root 'D:\workspace\git\cadence-mcp\.local\workspaces' `
  --read-root 'D:\MyDesigns' `
  --timeout-seconds 30
```

`--read-root` 可重复。输入文件必须使用绝对路径，解析后的路径需位于允许读取的根目录内。`--workspace-root` 是唯一输出根目录，由宿主启动配置指定，AI 不能在工具参数里扩大它。MCP 客户端配置可参考 `examples/mcp-client.example.json`，其中占位路径必须替换；这不是 Codex 客户端专用配置，也没有自动注册到用户客户端。

## 实际发布工具

完整 inputSchema/outputSchema 在 [工具契约快照](../contracts/tools.v0.1.json)，来自本版真实 tools/list。

|工具|参数|效果|
|---|---|---|
|cadence_get_environment|probeLevel=files/runtime|读取显式安装的文件指纹；runtime 启动命令注册探测，不创建 Dbo 设计会话|
|cadence_get_capabilities|无|报告已实现、实验性、不可用能力；不把当前环境自动标成已验证|
|cadence_create_workspace|sourceDesign|仅复制一个 DSN，并生成 manifest；不复制 OPJ/OLB/模型或声称依赖完整|
|capture_open|workspaceId|在新 Tcl 进程读取副本的原理图定义、页、器件、引脚及定义级网名，缓存不可变结果|
|capture_query|sessionId/entity/scope；fields/reference/cursor/limit 可选|按设计定义或指定页面查询；位号严格等值匹配；分页绑定查询与会话|
|capture_snapshot|sessionId|写入 JSON 快照及 SHA-256；快照仍标为 unverified，不能充当独立预期节点表|
|capture_close|sessionId|释放当前服务的缓存；不保存，不触碰 GUI 会话，不删除工作区|

示例顺序：

```json
{"tool":"cadence_get_environment","arguments":{"probeLevel":"runtime"}}
{"tool":"cadence_create_workspace","arguments":{"sourceDesign":"D:/MyDesigns/example.dsn"}}
{"tool":"capture_open","arguments":{"workspaceId":"<返回的workspaceId>"}}
{"tool":"capture_query","arguments":{"sessionId":"<返回的sessionId>","entity":"pin","scope":{"kind":"design"},"limit":100}}
```

这里是调用示意，不是可直接写入 stdio 的 JSON-RPC 帧。客户端按 MCP 协议发起调用。`nextCursor` 非空时继续相同查询；修改 entity、scope、fields、reference 或 limit 后不能沿用旧游标。page scope 使用返回的页面 objectId，而非页面名称。字段和实体枚举由 schema 与运行时共同校验。

工具失败返回 `is_error=true`，同时提供结构化 error；无效输入由 SDK 拒绝。分页结果 status=partial、complete=false，未实现的 occurrence 查询不回传假空结果。所有响应附覆盖范围与 notChecked。

## 与设计草案的刻意收缩

- 本阶段 workspace 只支持 `single_design_file`，manifest 的 `dependencyClosureVerified=false`。正式项目依赖闭包仍待实现。
- session 是经过一次独立 native worker 读取后的不可变缓存，不是持久 Tcl/Dbo 会话；每次查询检查副本 hash，改变后拒绝旧会话，关闭仍可释放。
- ID 只在当前缓存会话内有效，不是跨进程/修改后稳定的数据库身份。generation=1。禁止据此实现写入。
- definition 级引脚网名不等于 occurrence 展开后的完整工程连接。外部层次、隐藏电源脚语义等还未独立验证。
- worker 不接收 Tcl/JSON 脚本，只接收宿主生成的路径和数量限制；Tcl JSON 输出使用独立、受测的定型编码函数，无请求求值入口。
- timeout 终止独立 Tcl 直接子进程；本阶段不运行 PSpice，也未实现 Windows Job Object 子进程树、任务账本、取消工具和持久恢复。
- stdout 仅用于 MCP；native 日志由宿主捕获。单次输入 DSN 最大 128 MiB，结果最大 32 MiB，最多 100000 个对象。日志大小在进程结束后检查；当前不提供对恶意本机进程的沙箱隔离承诺。
- 服务内锁保证自身请求串行一致性，不能防止其他本机程序在检查后恶意替换路径；配置根目录应由当前用户独占管理。

原始架构文档作为目标设计保留，本文件和真实 tools/list 描述本版可用能力。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

.\.venv\Scripts\python.exe tools/smoke_capture.py `
  --install-root 'D:\Program Files\Cadence\SPB_24.1' `
  --workspace-root 'D:\workspace\git\cadence-mcp\.local\validation' `
  --source 'D:\Program Files\Cadence\SPB_24.1\tools\capture\samples\Schematic\FULLADD\FULLADD.DSN'
```

原生测试需要用户显式选择样例路径；仅在独立副本上操作。native-smoke-report.json、工具清单和快照均写入传入工作区。Cadence 示例 DSN、官方资料及其原始输出不进入 Git。普通单元测试通过自建 mock 设计结构验证失败路径，不依赖 Cadence 许可证或安装。


2026-10-23新增第22个工具 `capture_compare_connections`。使用只读副本会话与expectedRevision、人工预期引脚表和来源，输出选定定义的观察差异报告；完整参数见当前tools/list及[业务计划](design/06-business-roadmap.md)，验收见[B1记录](validation/business-b1-2026-10-23.md)。不代表全工程电气连通验证。

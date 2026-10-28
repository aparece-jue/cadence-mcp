# v0.1.1-alpha.1 安装与试用

需要Windows x64、Python3.12+ x64、本机Cadence24.1及可用许可。解压至新目录，例如D:/cadence-mcp-0.1.1-alpha.1，不覆盖旧环境。依赖下载需要网络。

在解压目录打开PowerShell：

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
.venv/Scripts/python.exe -m pip install --no-deps cadence_mcp-0.1.1a1-py3-none-any.whl
.venv/Scripts/python.exe -m pip check
New-Item -ItemType Directory -Force inputs,workspaces
```

复制mcp-client.example.json到客户端配置，修改Python、Cadence安装、workspaces和inputs的绝对路径；输入只读目录需显式列出。默认模块cadence_mcp.server是224工具扩展入口。先运行cadence_get_environment，再创建DSN工作副本并打开查询，真实设计不作测试写入目标。

本版可优先测试capture_query_part_vectors、capture_check_symbol_contacts和capture_query_titleblock_vectors。标题栏ID从capture_query_graphics(entity=titleblock)取得，partId从capture_query取得。所有分页ID/cursor绑定当前会话及revision；错误来源或关闭会话须重新创建副本。接触候选不等同电气连接或完整渲染避让结论。

库属性使用capture_query_library_package_properties和既有package编辑计划/执行链；值需明确字符串，空文本与删除不同。按计划预览核对再执行，失败留planId与错误证据，不重复派发未知结果。需要写宿主的功能见GUI-BRIDGE.md，绑定必须重新建立，不能复制他人的私有绑定文件。

随包divider.cir可用pspice_prepare/pspice_plan_run/pspice_apply_run测试独立引擎DC=2.5V，再读取本次关联DAT。CLI未作为本版安装通过项，见RELEASE-NOTES.md。反馈请附版本、Cadence版本、操作/预期/实际、错误码与任务号；私有设计、模型、许可证保留本地。

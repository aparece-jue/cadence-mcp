# v0.1.0-alpha.1 安装与试用

这是首次公开测试版，供边用边反馈；完整原理图创作、层次/总线、原生DRC及Capture→PSpice联动仍未完成。默认通过独立Tcl/Dbo工作进程操作副本，普通查询及独立PSpice仿真无需启动Capture GUI。GUI桥接单实例功能需单独配置，不作为首次试用前置条件。

## 安装固定测试版

需要Windows x64、Python 3.12+ x64、已有可用的Cadence 24.1安装及对应许可证；本测试包不包含Cadence。依赖安装需要网络。下载Release中的Windows测试包ZIP并解压，在解压目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-deps -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps .\cadence_mcp-0.1.0a1-py3-none-any.whl
```

固定版安装在独立环境，不使用研发仓库的editable安装；后续源码变更不会改变这份已安装测试版。源码安装也可在对应tag检出后执行同样依赖安装，再用`pip install --no-deps .`。

## MCP客户端配置

修改ZIP中的`mcp-client.example.json`：command指向刚创建的`.venv/Scripts/python.exe`；install-root为实际Cadence安装；workspace-root使用全新测试输出目录；read-root仅填写准备试用的输入目录，可重复指定。工作区和输入目录应分别设置，避免将历史生成文件混入输入。所有路径使用绝对路径。

```json
{"mcpServers":{"cadence-alpha":{"command":"D:/cadence-mcp-alpha/.venv/Scripts/python.exe","args":["-m","cadence_mcp.server","--install-root","D:/Program Files/Cadence/SPB_24.1","--workspace-root","D:/cadence-mcp-alpha/workspaces","--read-root","D:/cadence-mcp-alpha/inputs","--timeout-seconds","60"]}}}
```

将此条目加入所用MCP客户端；不同客户端的配置文件位置不同。本仓库不隐式修改用户全局客户端设置。直接运行服务会等待stdio协议输入，没有交互式命令提示符；需由MCP客户端连接。

## 推荐测试顺序

1. 环境：让客户端调用`cadence_get_environment(probeLevel="runtime")`及`cadence_get_capabilities`，检查显式安装和当前能力。
2. 只读Capture：把一个DSN副本放入read-root，调用`cadence_create_workspace`、`capture_open`，再查询page/part/pin、属性和几何。记录源文件不变及对象/分页结果。它只复制DSN，不宣称自动收齐OPJ、外部库和仿真依赖。
3. 库：先查询OLB，再试声明式创建/引脚编辑/独立封装变体；修改通过plan/apply产生新OLB，并重新打开。封装名称验证不等于实体PCB封装存在验证。
4. 独立PSpice：ZIP附原创`divider.cir`。准备后使用引擎或CLI的plan/apply执行DC，预期V(OUT)在输入5V时为2.5V；这是独立CIR仿真，不是从Capture自动生成输入。
5. 受控写入：优先测试批准属性、位号映射及已验证范围的器件放置。写入需明确预期引脚/连接；不确定时先停在plan预览。失败输出不能作为verified成果继续编辑。

可以给AI的首轮任务：“连接cadence-alpha，检查环境和能力；将inputs里的DSN复制到MCP工作区，只读取并汇总页面、器件、引脚和属性，最后报告未支持项。”

## 已知未完成与反馈

完整布线保存重开、接线器件移动、部分缓存替换/字体/文字坐标、层次flat网络和总线、原生DRC、Capture仿真输入及端到端参数循环仍未完整通过。数字/混合DAT、真实许可证失败场景仍有缺口。普通缺失B单元同schematic跨页补放有通过证据；供电P单元跨页出现VCC未连接，会拒绝验收。PDF自动打印延期，Allegro排除。

反馈请注明版本、安装版本、想完成的操作、调用的工具、预期/实际结果、错误码和job/planId。可使用仓库Issue模板；真实DSN/OLB、模型和许可证信息保留本地，优先提供可公开的最小复现。工具及全部参数以`contracts/tools.v0.1.json`为准，不能把历史README中的工具数当成当前版本数。

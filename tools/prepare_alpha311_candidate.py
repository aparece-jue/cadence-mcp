import io,json,subprocess,zipfile
from pathlib import Path
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/alpha311';root.mkdir(exist_ok=False);stage=root/'source';stage.mkdir();dist=r/'dist/alpha311';dist.mkdir(exist_ok=False)
g=['git','-c','safe.directory='+r.as_posix()];assert not subprocess.check_output([*g,'status','--porcelain'],cwd=r).strip()
base=subprocess.check_output([*g,'rev-parse','HEAD'],cwd=r,text=True).strip();assert base=='975001db63c392dc9019fbf462d35bb06cdfc858'
raw=subprocess.check_output([*g,'archive','--format=zip','HEAD'],cwd=r)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 for name in z.namelist():assert (stage/name).resolve().is_relative_to(stage.resolve())
 z.extractall(stage)
for rel in ['pyproject.toml','src/cadence_mcp/__init__.py']:
 p=stage/rel;s=p.read_text(encoding='utf-8');assert s.count('0.1.1.dev0')==1;p.write_text(s.replace('0.1.1.dev0','0.1.1a1'),encoding='utf-8')
notes='''# v0.1.1-alpha.1

Windows x64 / Cadence24.1，Python包版本0.1.1a1，224个开发/扩展MCP工具。此版更新已专项验收的功能；原34项完整业务门禁仍8/34（23.5%），不是全部功能完成或新版正式发行。

相对v0.1.0-alpha.2：新增元件定义图形、线性元件/导线接触候选与标题栏定义图形读取；修复仅新增库用户属性时可能未保存的问题。元件姿态/热点和原40连接对象读取门禁已完整验收。标题栏line/box/text、中文多行及八姿态通过；查询控制点不代表字形/笔宽渲染边界或电气DRC。用户属性按官方StringT模型保留原字符串，数字、布尔输入不隐式转换。

独立安装验收及SHA256见release-manifest.json和SHA256SUMS.txt。安装包不含Python、Cadence、许可证、手册、DSN/OLB或模型。旧alpha.2和v0.1.0保持固定，请使用新环境和新工作目录。

未完成项保留：完整层次/flat/occurrence/隐藏脚、嵌套Bundle、部分缓存/变体/字体渲染、原生DRC闭环、数字/混合DAT及原始剩余门禁。独立NewWireScalar及部分构造顺序仍可能产生3969，旧失败产物拒绝且不自动重放。需要原生编辑的功能须显式配置Capture桥接和干净私有宿主。PDF延期，Allegro排除。

本版基础求解安装验证显式使用独立PSpice引擎，不自动切换后端。CLI本版未重新验收；alpha.2安装复测曾被Cadence Product Choices产品选择阻塞，此限制继续保留，不能宣称已修复或诊断为许可证失败。224工具包含部分实现/研究能力，以各工具契约、证据和未检查项为准；正式支持范围仍见v0.1.0。
'''
guide='''# v0.1.1-alpha.1 安装与试用

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
'''
for rel,content in [('docs/releases/v0.1.1-alpha.1.md',notes),('docs/testing/alpha-3.md',guide)]:
 (r/rel).write_text(content,encoding='utf-8');(stage/rel).write_text(content,encoding='utf-8')
config={'mcpServers':{'cadence-alpha-0-1-1':{'command':'D:/cadence-mcp-0.1.1-alpha.1/.venv/Scripts/python.exe','args':['-m','cadence_mcp.server','--install-root','D:/Program Files/Cadence/SPB_24.1','--workspace-root','D:/cadence-mcp-0.1.1-alpha.1/workspaces','--read-root','D:/cadence-mcp-0.1.1-alpha.1/inputs','--timeout-seconds','60']}}}
for folder in [r,stage]:(folder/'examples/mcp-client-alpha3.example.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
(root/'preparation.json').write_text(json.dumps({'baseCommit':base,'version':'0.1.1a1','tag':'v0.1.1-alpha.1','sourceStage':str(stage),'privateSourceOnly':True,'oldEnvironmentsUntouched':True},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'stage':str(stage),'dist':str(dist),'version':'0.1.1a1'}))

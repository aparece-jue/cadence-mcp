# 第95批：页面编辑器初始化与新导线对照

2026-10-26，C00/D03。对应原新建DSN导线重开门禁，原固定坐标及失败保持。

独立创建新的MCP_VIEW_WIRE私有空DSN，ROOT/MAIN及无元件/引脚读取通过。首次切换在发Open前因上一轮保存后旧绑定指纹变化而拒绝target_changed；这是正确保护，空诊断目录不代表业务已派发。为当前私有旧设计重新绑定后，新诊断目录只派发一次Open。最小OPJ仍触发旧工程提示，必要GUI选None/Finish，未改Do-not-ask、未转换项目；晚到回执单独审计，旧未确认报告保持，未重放。

通过观察到的私有工程树展开设计和ROOT，双击MAIN以验证真实页面编辑器初始化。Capture自动将新空页标记dirty。固定save_private_editor_initialization.py仅允许已知私有空夹具、活动页面/视图身份及0导线条件，保存后独立读取ROOT/MAIN、0parts/0pins/0objects通过。保存生成的新指纹重新绑定；probe_editor_session_wire.py在实际应用会话再次核对GetActivePage等于目标page且GetActiveView存在，才构造(100,100)→(300,100)单导线并完整保存。

宿主记录entered/editor_verified/new_wire/save/saved，回执saved=true。但独立重开open/root/iterator均0，NextPage3969。审计证明导线前before.dsn字节正是上一阶段独立读取通过的初始化空页；两个oracle指纹相同、未改预期。因此页面编辑器初始化本身通过，不能将其当作导线验收通过；“先打开并保存编辑器即可修复”的假说被否定。原控制DSN指纹和新失败文件均保留；无需重跑原写入。

新增4固定开发诊断脚本，Python语法/原生调用/独立读取和字节衔接审计执行。脚本构造阶段发现未执行Tcl代码中的字面换行并在调用前修正，实际阶段标记确认身份检查已运行。无公开工具/生产合同变化，正式202工具；沿用第93批完整554项553通过/1原权限skip，本轮未宣称重新完整回归。

34项仍6完整通过（17.6%），目标active，D03不提升。第94批1173fcc补推再遇GitHub443连接失败，本批本地记录继续；后续补推develop，alpha.1固定。下一步继续新导线构造/序列化所需初始化与实际DRC规则和模型外部依赖。官方程序/资料全文、私有工程和认证不上传；无安装/真实设计修改。

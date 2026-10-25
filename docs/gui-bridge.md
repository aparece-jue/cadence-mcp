# Capture 桥接 v0.5：部署、契约与验收边界

本机单个 Capture 24.1 的桥接基础链路已经完成实测：认证、会话、读取、受限写入、持久任务、取消、结果核验恢复、停止与重载。尚不能把两份真实 Capture 的并行运行或任意 Capture 编辑能力标为完成。

## 对外工具

当前 MCP 总计 21 个工具，其中桥接相关 13 个：

|工具|契约|
|---|---|
|capture_gui_instances|只扫描主机注册配置；验证令牌、实例、PID、可执行文件和设计指纹，不自动换工程|
|capture_gui_attach|默认 read；write 仅允许显式准备的隔离副本；绑定 generation，600 秒闲置租约|
|capture_gui_query|只接受 status/pages/selection；选择标识只对本次快照有效|
|capture_gui_detach|释放会话；断线时释放本地状态并报告远端未确认|
|capture_gui_status|恰好一个有效实例时的便捷查询|
|capture_gui_plan_note|固定 MCP_NOTE 属性计划；包含目标、旧值、文件指纹、连接基线摘要和有效期|
|capture_gui_apply_note|应用一次、保存、独立重读、定义级连接比对，并复核原生保存代次|
|capture_gui_jobs|从主机注册的私有绑定目录读取持久任务，不依赖旧服务器内存；最多 256 项|
|capture_gui_cancel_note|只取消尚未开始的计划；取消与应用共用排他锁，并在锁内复核状态|
|capture_gui_recover_note|仅核验已开始任务；需要原生保存回执、未变化的 generation、clean 状态及独立重读结果；不重发修改|

输入输出完整 Schema 见 `contracts/tools.v0.1.json`。不开放任意 Tcl、eval、shell 或客户端指定的监听地址。

## 部署

1. 用 `tools/prepare_write_fixture.py --source <允许读取的DSN> --output-root <测试目录>` 新建副本。外部库、模型和依赖闭包不自动复制或验证。
2. 在 Capture 中打开副本，记录该进程 PID。首次打开单 DSN 可能需要确认工程类型。
3. 用 `tools/prepare_gui_bridge.py --private-root <注册根> --copied-design <副本DSN> --capture-pid <PID>` 准备只读绑定；需要固定备注写入时显式加 `--allow-property-write`。私有目录在写令牌前限制 ACL。令牌不能写进日志或提交仓库。
4. 在 Capture 命令窗口执行 `source {<仓库>/src/cadence_mcp/adapters/bridge.tcl}`，然后 `::cmcpBridge::start {<私有目录>/binding.json}`。不改安装目录、capinit 或真实设计。
5. MCP 启动配置设置安装根、输出根、读取根，并用 `--gui-bridge-config` 或 `--gui-bridge-root` 注册绑定。参见 `examples/mcp-gui-client.example.json`。原生 Dbo 工作进程需继承本机合法许可环境；禁止将许可证配置提交仓库。
6. 通过 instances → attach → query/plan/apply → detach 使用。每次失去会话后显式重新附加。首次加载后，正常 RPC 不需要桌面点击。

停止：在 Capture 执行 `::cmcpBridge::stop`。只清理自身监听与端点描述，保留绑定、任务及设计。相同进程、相同目标下可重新 source/start 同一绑定，旧会话必定失效。Capture 进程重启或目标工程改变时，需要新绑定；不自动启动、杀死或重新绑定 Capture。

## 故障与恢复

- 回环地址、每次认证、16 KiB 帧、最多 4 个客户端、3 秒接收超时；RPC 读取约 4 秒、应用约 8 秒，带请求截止时间。请求发出后不自动重试。
- 嵌套事件产生重入请求时返回 bridge_busy；不在一次保存中插入另一次业务操作。
- 写前用只读 Win32 状态检查确认主窗口存在且启用；有模态窗口时拒绝写入。该检查不会点击、关闭窗口或替用户作决定。窗口状态在主机侧预检，不能声称从机制上消除了预检之后的全部人工交互竞争；设计 clean、旧值和 generation 也会复核。
- 写入前持久记录 started 和排他锁。发生断线、保存或验证失败时保留记录，避免重复写入。独立验证使用 SHA-256 校验副本，并确认验证期间原文件未变。
- 服务器重启后先调用 jobs。pending 可取消；started 只能调用 recover 核验。若 Capture 回执仍在且上下文未变化，可核验后释放锁；如果 Capture 已崩溃、重载、切换工程或发生后续编辑，保留锁和状态，人工调查。没有自动回滚、自动删除锁或盲目重放。
- 取消不等于中断已经执行的 Dbo 保存；正在写入的任务不能安全强制取消。运行期间跨进程 OS 锁阻止另一核验进程抢先发布结果。
- 74 项自动测试：73 通过，1 项因 Windows 符号链接权限跳过。原生协议组必须设置 CADENCE_TEST_TCLSH；模拟 Capture 上下文的测试不能当作真实 GUI 验收。

## 本轮真实验收

|场景|结果|
|---|---|
|计划取消后再次应用|拒绝，文件未变|
|真实保存成功，主机故意丢弃回执|保留 started 和锁|
|新 stdio MCP 进程恢复上述任务|独立核验属性和定义级连接后解除锁，没有再次写入|
|打开工程类型对话框期间读状态|仍可响应，本次约 0.031 秒|
|打开文件对话框期间写前检查|bridge_busy，文件未变|
|停止桥接|端点被清理、旧监听不可达|
|同进程重新加载|旧会话被拒绝，generation 从 18 增至 20，新会话读到两页，文件未变|
|最终代码正常备注写入闭环|保存、独立重读、定义级连接一致、原生代次复核和幂等重放通过|

本地证据在 `.local/bridge-recovery-20261022/` 和 `.local/bridge-final-20261022/`。这些私有配置、DSN 和原始日志不纳入 Git；历史首次写入记录见 [写入验收](validation/gui-write-2026-10-22.md)。

## 支持边界及收尾验收

普通启动及官方文档中的独立 INI 目录启动均未留下第二个 Capture 进程；普通启动还将测试 DSN 的打开请求转交给现有实例，已取消该弹窗。不能据此判断是单实例策略、许可还是其他启动条件；两份真实 Capture 并行仍未验收。协议测试已验证两个独立 Tcl 进程的会话隔离，不能替代此项。

真实事件线程阻塞12秒、调用方8.047秒退出、迟到修改拒绝、受控进程终止与新进程工作恢复均已完成实测。缺失回执的旧任务保持不确定并保留锁，不自动回滚或重放。新增 tools/load_gui_bridge.py 使用官方命令行入口及单行source包装，正常加载/重载不需要桌面操作；崩溃后的Capture恢复弹窗仍可能需要人工处理。

专项结论及完整支持范围见 [本机桥接最终验收](validation/bridge-final-2026-10-22.md)。双Capture并行未通过，只将本机单进程模式列为已验收，不把其他模式默认为可用。

元件、导线、一般参数编辑、原生 DRC 和 PSpice 是后续业务模块。当前固定备注证明写入基础链路，但不代表这些业务已实现；occurrence 层次连接也未验证。PDF 自动交付继续延期。

## 运维加固更新

新增 capture_gui_diagnose、capture_gui_review_note 和 capture_gui_resolve_note。原生恢复仍优先；进程确已停止时，可独立核验后明确结案，解除对应锁，不补造原生回执。诊断有独立线程，业务线程固定为两个。已完成连续读写及重载测试，详见 [运维加固验收](validation/bridge-operations-2026-10-23.md)。

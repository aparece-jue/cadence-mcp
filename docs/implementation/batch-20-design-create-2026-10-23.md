# 第二十批范围与验收

## 第二十批新设计创建、文档元数据与页面保留校验

- 新capture_design_create.py/create_design.tcl，公开capture_plan_design_create/apply_design_create/design_create_jobs/cancel_design_create/recover_design_create；open_edit_result新增kind=design_create，实际99工具。每次在全新job目录创建一份design.dsn、一个声明root schematic和page；不需要模板/OPJ/GUI，不覆盖已有设计。Artifact.kind=capture_created_design，sourceKind=new_design_spec限定枚举，sourceFingerprint是声明digest。OPJ、SaveAs/design-delete、页/原理图CRUD完整范围仍未完成。
- 本机官方Tcl手册p179/255与page NewPage/save链；独立inspect_document_meta.tcl读取root、schematic rawRefCount、page 10类计数（part/wire/busEntry/port/global/offpage/graphic/titleblock/ERC/bookmark）。schema、计数非负与上限、bool、root归属、同名/重复页检查。仅 recognized categories；custom plugin objects等未认证，不能据此开放全通用删除。
- `.local/design-create-ascii-20261023/report.json`ROOT/PAGE_ONE、POWER_CORE/POWER_PAGE两个新设计/save/new-process/root/count/重启幂等通过，ROOT继续内部NewPage链通过。原FULLADD源hash保持；metadata的HALFADD rawRefCount=0，而既有H01证据明确有halfadd_A/B两个Implementation=HALFADD引用，因此GetRefCount不是可用的incoming依赖计数证明。没有用0作为删除安全条件。
- `.local/design-create-20261023/report.json`与v2均保留Unicode失败：native保存后独立inspect输出schematic/page/part/pin全空，未按声明通过。改用UTF-8 JSON传入名称仍失败，先前argv编码假设未证明根因。公开plan提前拒绝non-ASCII，ISS-E04-unicode-design-reopen open后移；未篡改期望或将Unicode从完整后续验收中删除。
- CapturePages增加可扩展的plan_payload/verify_content；内部CapturePageEdits对connection、graphic/part/display与root/page counts做稳定语义基线，图形owner保留reference，qualified page重命名随预期更新。不变更现有内部旧页计划语义。`.local/page-content-20261023/report.json`create与rename populated均graphic baseline mismatch；定义/已检查连接阶段通过不足以声称内容全保持。原因未定位，页工具不发布，ISS-E04-page-content-baseline open后移。delete保护、非空/引用/外部依赖仍待完成。
- `.local/design-create-mcp-20261023/report.json`新设计真实MCP创建、两次R501/R502放置分别保存/重开均成功；下游wire链失败。native add_wire receipt saved=true、exit0、自有0，账本state=failed/error=dbo_error；失败在保存后读取验证，不是已证明MCP通信故障。导线未计通过、未重放，ISS-D03-new-design-wire-reopen open后移。
- `.local/design-create-lifecycle-20261023/report.json`单独真实99工具stdio验证创建链本身：严格schema、声明digest/root页名、fresh server原plan无重放/open、错误key、已验证结果recover、非法路径/Unicode/extra、pending cancel/jobs、tamper拒绝全部通过。原CORE创建产物仍完整，独立新TAMPER产物故意追加bytes，保持拒绝；不覆盖首次下游失败报告，不把单独生命周期通过当作wire通过。
- `.local/design-create-faults-20261023/report.json`实际native完成后删除receipt→fresh只核验恢复/nativeCompletionVerified=false/hash保持并open；启动窗口cancel与真实1s timeout各自有进程0/禁止重放。不是所有保存阶段/资源浸泡验收。
- 5项新增主机测试，完整238回归237通过/1原symlink权限skip。E04和D03保留已验证切片，同时deferred后移；34项原范围及其余问题均保留，目标active。源码未改后又回跑无必要回归；无GUI、安装/真实工程修改、提交推送。下一H04/V03等独立项。


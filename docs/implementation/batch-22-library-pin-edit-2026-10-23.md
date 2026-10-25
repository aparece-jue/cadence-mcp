# 第二十二批范围与验收

## 第二十二批元件库引脚编辑与语义重开校验

- library_semantics.py规范化完整现有基础OLB图：package字段、device designator/position/cell、part variants、pin逻辑position/物理number/name/type/visible/shared/swapId/hotspot逐项保留；只排除快照ordinal IDs和遍历顺序。重复语义身份拒绝，不能按脚名/脚号简单合并多单元/变体。5项新主机测试证明改变任一映射/几何等字段会改变图，ID/顺序变化不改变，变体不塌缩，共享功能冲突拒绝。
- LibraryPinEdits原生目标定位从pin ordinal改为package/device designator+position/cell/part/logical pin position，唯一匹配且old fields必须相符。UTF-8固定pin-edit.json传参，不执行名称中的Tcl字符；释放所有iterator后才SetPinName/SetPinType/Device.SetPinNumber与SaveLib。依据本机官方Tcl参考p608/726。verify新进程重开、完整基础语义摘要、源前后hash；旧ordinal计划明确拒绝自动迁移/重放。
- 物理pad重号/共享pad重编拒绝；异构共享pad只改一单元导致name/type功能不一致时拒绝，需后续package-wide业务。符号name/type修改影响同cell/part/逻辑位置的全部视图，device pad号只改所选device。同构/异构区别不靠logical pin总数推断物理脚数。
- 新6个MCP工具：capture_plan_library_pin_edit/apply_library_pin_edit/library_pin_edit_jobs/cancel_library_pin_edit/recover_library_pin_edit/open_edited_library，实际105。verified/hash一致产物才能开为新只读library session，不扩大公共读根。verificationScope=library_device_definitions、symbolGraphicsVerified=false、designCacheUpdated=false；没有认证vector graphics/reference template/其他属性或DSN同步。
- 初版验收脚本漏写官方analog路径的pspice子目录，在原生开始前FileNotFoundError；`.local/library-pin-semantic-20261023/harness-error.json`保留，修正到真实且sha7065...一致的pspice/analog.olb，新目录验收，未修改安装。
- `.local/library-pin-semantic-v2-20261023/report.json`5原生用例全过：官方库副本组合name/number/type；自建resistor Unicode与literal `A $[x];中文`；同构name影响2行、pad renumber只所选device；异构A输入name影响1行。独立重开、fresh writer不重放/open、源hash保持。
- `.local/library-pin-mcp-20261023/report.json`真实105工具stdio：3类库编辑、schema、Unicode、影响范围、pad/异构共享功能冲突、bool/extra拒绝、pending cancel/jobs、新server幂等/recover/open、tamper拒绝通过。末尾异构OLB故意追加bytes保持拒绝；first resistor产物仍完整。
- `.local/library-pin-faults-20261023/report.json`真实native完成后受控丢receipt→fresh只核验恢复/nativeCompletionVerified=false/hash不变并open；启动窗口cancel和1s timeout各自有进程0/不重放。不是所有故障阶段或文件句柄释放的完备证明。
- `.local/edited-library-placement-20261023/report.json`新MCP用first编辑OLB放置R601到空白CORE/MAIN DSN，物理101+2、中文literal脚名、(280,300)/(320,300)热点与独立定义预期通过；DSN和OLB源hash保持。这是新私有cache放置，不是原DSN缓存替换/实例覆盖同步。
- `.local/legacy-library-edit-audit-20261023/report.json`只读审计最初L04失败产物：验证旧plan自身digest、旧source fingerprint、冻结inspection与beforeLibraryDigest、严格重建与原expectedLibraryDigest完全相同的原期望；其语义图与旧保存OLB一致，rawOrdinalDigestEqual=false。ledger/source/target前后hash相同，mutationReplayed=false，legacyLedgerState仍failed/nativeCompletionReaccepted=false。仅原身份/顺序误判issue结案，未改旧账本为成功、未降低原期望；完整L04继续partial。
- 最新250完整回归249通过/1原file-symlink权限skip。上批245取消后目录占用错误保留，ISS-P02-process-directory-release-152仍open；本次绿色不证明其间歇资源问题已解决。原34功能完整范围与其他failed/deferred均保留，目标active。无GUI/安装目录或真实设计修改/提交推送。下一E03/L05/P03等。


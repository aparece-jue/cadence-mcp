# 第四十六批：单个多单元实例的姿态与删除

2026-10-24。原34项完整范围保持。复用既有part_edit计划/apply/jobs/cancel/recover/open，不新增工具族，仍142个实际MCP工具。

## 实现和官方依据

capture_plan_part_edit新增可选expectedUnitConnections，以remaining-page pinId逐条声明网络；选择该分支时expectedConnections必须为空。旧single-unit调用不变。新CaptureUnitEdit实现使用nativeId、base/full reference、device designator、cache package/size及原pose绑定单个内部placed unit，拒绝external、attached NC及歧义。姿态仍由调用者声明全局热点，不从本次观察反推oracle。

固定edit_unit_part.tcl在新副本中使用官方DboGraphicInstance.SetLocation/SetRotation（主参考p301）、SetMirror（p302）和DboPage.DeletePartInst（p461），迭代器释放后才修改，删除后不再解引用指针，完整SavePage/SaveSchematic/SaveDesign链逐项检查。未实现missing unit补放或跨页分配。

保存后新进程核对全部定义/网络、连接对象、全设计剩余单元native identity/full reference、同页全部pose/hotspot、Value/PCB Footprint、语义cache package/device/view/pin共享/交换元数据及原生页pin-wire网络对象。cache ordinal ID重排不算逻辑变化；不声称完整图形缓存、外部依赖或flat/occurrence认证。共享physical pad的矛盾网络声明在计划前拒绝，不允许把各单元当作不同物理封装脚。

Part edit账本扩展为有界256KB，unit payload160KB，旧single-unit payload48KB限制保持。其NC和net-symbol-create子类明确保留原64KB记录上限。

## 验收结果与未通过项

- 首7例真实MCP：A移动、B旋转、B镜像、删除B、删除接线P共5正例通过；错误热点负例保存后unit_edit_geometry_mismatch/open拒绝/不重放；接线A移动失败，原总report保持false。所有成功输出fresh apply/recover/open不重放，原来源及冻结oracle hash保持。
- 接线A移动只读差异审计：原U501A.8/VCC connected=true/net=VCC，移动后connected=false/net空；其他期望引脚无差异。原账本、失败输出、source和oracle未变。不能把网络期望改成观察值提升通过，也未推断实际flat/physical continuity；D02完整门禁deferred并排队后移。
- 首故障脚本相对来源路径被guard拒绝，3失败report保留。修正harness绝对路径后：真实保存完成删除receipt、fresh MCP verify-only恢复/nativeCompletionVerified=false/不重放/hash保持/open通过；启动cancel和故意延迟1s timeout owned0通过。
- 修复inspect_page_objects共享NC遗漏：NewPinsIter显式IterDefs_ALL/bReturnShared=1，与definition pinId一致。私有U501A共享8/VCC设置NC后，新进程+真实MCP只读返回准确单条NC、owner pinId/partId、热点(1000,680)，完整definition与源hash保持；删除带NC单元在建账本前attached_nc_unsupported拒绝，0durable plans。未扩大公开NC写入范围。
- 后续物理脚一致性/错误phase=verify/共享NC保护改动后，最终targeted3例move-A、delete-power-P、wrong-hotspot重新执行通过；早先接线移动失败继续保留。验证错误阶段由代码修正，旧report的preflight字段不回填。
- 8项新增host回归覆盖同base不同unit identity、单删不误删同base伙伴、ordinal重排、cache shared/physical number/swap/visibility、互斥期望、矛盾共享脚。最终完整318项317通过、1原symlink权限skip。原317回归是早期版本记录；最终record-guards回归涵盖最后的子类记录上限保持。
- 最终复测曾被自动审批服务额度耗尽拒绝启动，未产生结果文件；用户回复继续后服务恢复，现已实际完成，不把先前拒绝算执行。

## 后续与原范围

完整unit生命周期未完成：缺失unit新增、跨页分配及接线单元移动的共享/flat语义仍待处理。非line图形、任意命名异构导入、封装变体、缓存替换覆盖保持、原DRC/总线/仿真闭环等原34项继续。D02失败排队后移，其余独立项推进。无GUI、安装目录或真实设计修改，无提交/推送。详细路径与SHA256见batch-46-evidence.json。

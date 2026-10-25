# 第五批：库引脚、编号身份及页面操作

2026-10-23。目标仍active，34项required不变。本批新增的是**内部实现和原生验收证据**，未发布新的MCP工具，实际契约仍54项。不能把内部代码、9项主机测试或一个新增页正例合计为L04/E03/E04全部通过。无GUI、真实工程/安装写入或提交推送。

## 已实施与实际结果

### L04：隔离库引脚编辑

内部`LibraryPinEdits`复用持久计划、幂等、取消和不重放恢复基座；只生成新OLB输出。支持规划符号脚名、电气类型码和device物理脚号，显式列出共享symbol的受影响记录；冲突脚号和共享脚的单点改号拒绝，未把逻辑脚数当物理脚数。脚名/类型预期按cell/part/逻辑position传播；device脚号预期只对选定device/position传播。

首个真实ANALOG.R引脚名修改完成原生保存，但新进程重开后严格snapshot摘要不同，整体失败，后续脚号和类型修改未运行。已有证据显示库保存前后package枚举顺序改变，序号objectId随之变化，不能按跨进程序号做持久身份或比较。保存后的R目标名称确已观察到改变，但这不证明全部库定义和其他属性保持正确，也不证明其余两个字段成功。

已从原始前后JSON生成verification-diff.json；未调整期望或忽略差异来宣布通过。内部native目标预检已补package/device/cell/part名称和逻辑位置，避免仅凭ordinal+相似脚名/脚号碰巧定位其他对象。该加固尚未重新做原生验收；最终须以稳定语义身份定位及验证，并加重复/共享/变体正反例，不能简单删除objectId字段后假定没有误改。

库user属性/符号图形、复杂共享/变体重编号、DSN缓存更新仍未完成。L04保持deferred、工具未注册。

### E03：多单元编号身份

固定只读`inspect_reference_units.tcl`尝试读取PlacedInst的package/device designator、source library/part及原生reference。FULLADD副本探测失败，原始错误证据只到unit_identity阶段，无法断言具体API或对象类别。没有执行编号修改，没有发布编号工具。

已补每个关键方法前的phase及本地bounded错误回执，未盲目重跑。尾部应先区分DrawnInst/PlacedInst、GetReference的有效状态、GetPackage/GetId/设计器方法，不能按共享可见位号合并不同实体，更不能在身份未确认前开放SetReference。E03保持deferred。

### E04：新增页面与重命名

内部`CapturePages`实现create/rename计划、同schematic大小写冲突拒绝、范围绑定及新输出DSN；通过固定native操作、完整page/schematic/design保存和新进程Capture读取进行验证。预期先从修改前定义构造，仅添加页面或改指定页面名；其他部件与pin-net不应改变，不能从读回值覆盖预期。

FULLADD副本中向HALFADD新增MCP_EMPTY页**通过**保存、独立重开、完整定义预期和输出再次打开；原文件hash一致。随后空页重命名在rename_page阶段返回dbo_error，未完成保存；第三个带元件页面重命名案例未执行。该次native使用继承的Page.SetName，官方PDF362页提供专用`Schematic.Rename(page,newName)`；已替换调用但尚未原生复测，不能认为修复已验收。

新设计、新schematic、删除及依赖检查均保留未实现；页面图形布局与occurrence连通性仍未验证。E04保持deferred、工具未注册。

## 测试与边界

新增9项主机层测试通过：显式共享symbol影响/单device脚号映射、脚号冲突/共享脚拒绝、noop/控制字符/非法枚举、其他cell保持、创建/重命名定义预期、错网络负例、重复页面/越界目标、路径/删除拒绝和陈旧源拒绝。这些mock数据测试不证明原生全流程成功。

完整回归173项：172通过、1项原有Windows文件符号链接权限跳过，不将跳过算通过。P02历史目录清理故障仍open，本次未复现不构成根因修复证据。

## 官方依据与证据

本机Capture主PDF515/522、529–530页是reference/PlacedInst方法，608页是SymbolPin.SetPinName/SetPinType，726页是Device.SetPinNumber，166/362–363页是SetName及专用Rename/NewPage/SavePage/DeletePage。电气类型模型的八种类别来自`doc/capinfomodel/dboimnew.html`，原生码及所有类型语义仍需专项验证，不能把一次pinType读取当全部类型写入验收。

- `.local/reference-units-2c21c1eba1/{report.json,units.json}`：E03身份探测失败，源hash未变。
- `.local/library-pin-4536efce3f/report.json`、`verification-diff.json`及isolated-jobs/library_pin下的native-result/verification/plan：L04已保存但未通过重开比对，源hash未变。旧计划原样保留，不重放。
- `.local/page-edit-fd681cbf5c/report.json`及isolated-jobs/capture_page：新增页一个通过案例、rename_page失败回执，源hash未变。旧失败任务不重放；后续修正须新计划。
- `.local/regression-173-editors-20261023.txt`：完整回归输出。摘要hash见batch-05-evidence.json。

失败项均新增issue并移队尾。下一批推进已有库/页面可支撑的放置、导线、图形等独立业务，再集中修复编号身份、库持久身份、页面Rename等遗留。不因本批失败而缩小34项或提前向用户交全部完成评审。

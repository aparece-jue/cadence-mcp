# cadence-mcp

[研发分支 develop](https://github.com/aparece-jue/cadence-mcp/tree/develop) · [测试分支 alpha](https://github.com/aparece-jue/cadence-mcp/tree/alpha) · [发行分支 release](https://github.com/aparece-jue/cadence-mcp/tree/release) · [分支与晋级规则](docs/BRANCHES.md)

<!-- progress:start -->

[![完整验收进度](docs/progress.svg)](docs/PROGRESS.md)

[当前进度：8/34（23.5%）](docs/PROGRESS.md) · [研发同步规则](docs/DEVELOPMENT.md) · [参考资料](docs/references/INDEX.md)

<!-- progress:end -->

> **发行版 v0.1.0（已验证能力）**：[下载](https://github.com/aparece-jue/cadence-mcp/releases/tag/v0.1.0) · [安装](docs/testing/v0.1.0.md) · [65工具支持范围](docs/releases/v0.1.0-supported.md)。发行安装包默认使用validated_server；当前develop入口224工具，当前完整研发8/34，不将本发行声明为全部功能完成。

> **测试版 v0.1.0-alpha.2**（Python 包版本 `0.1.0a2`）：[下载预发布版](https://github.com/aparece-jue/cadence-mcp/releases/tag/v0.1.0-alpha.2) · [安装与试用指南](docs/testing/alpha-2.md) · [版本说明](docs/releases/v0.1.0-alpha.2.md)。Windows x64 / 本机验证 Cadence 24.1，221个工具；原34项门禁仍6项完整通过。新增原生编辑布线、普通总线/物理成员查询及受限PSpice联动。未完成范围见指南。[旧alpha.1](https://github.com/aparece-jue/cadence-mcp/releases/tag/v0.1.0-alpha.1)保留。


面向 Windows 本机 Cadence OrCAD Capture 与 PSpice 的统一 MCP 服务。

当前为持续开发中的实验性统一 MCP 服务：已开放设计/库查询、属性与显示编辑、明确预期的连线/alias新增、库绑定放置，以及PSpice输入准备和OUT/DAT读取。修改默认生成新副本并独立重开核验。完整绘图/层次/缓存生命周期、MCP原生DRC和PSpice求解仍未全部完成；PDF自动交付延期。当前状态以docs/implementation/CURRENT-STATE.md及机器验收矩阵为准。

GUI 验证已在测试副本上实际运行原生 DRC 并通过 File → Print 生成保留文字层的两页 PDF（已检查文字提取、关键词查找和图面；用户已确认阅读器搜索和复制可用）；本次 DRC 报告有 19 条错误，电路未通过检查。这些流程尚未接入 MCP，详见 [GUI 验证记录](docs/validation/gui-2026-10-22.md) 和 [复现说明](docs/gui-validation.md)。

## 架构方向

- 一个 MCP Server，共用环境发现、工作区、任务、输出物和审计能力。
- Capture 内部模块：独立 Tcl/Dbo 工作进程，以及 Capture GUI 内 Tcl 桥接。
- PSpice 内部模块：优先验证 CLI，再扩展引擎 Tcl 和波形数据访问。
- 小型、按需加载的 Skills；独立、版本化的设计规范体系。
- 当前范围不包含 Allegro。

## 设计基线

从 [设计包总览](docs/design/README.md) 开始阅读，其中包含本机核查、架构、工具契约、兼容性验证、实施阶段和规范体系。

接线坐标及旋转参考点见 [符号定义坐标与页面热点](docs/coordinate-frames.md)，包含本机正反例及已验证范围。 页面文字操作见 [文字写入说明](docs/graphic-text.md)，尺寸与声明框检查见 [页面边界说明](docs/page-bounds.md)。

运行与安装见 [第一阶段说明](docs/phase1.md)，验证范围见 [本机验证记录](docs/validation/phase1-2026-10-22.md)。本机 24.1 已通过标准 stdio MCP 在 FULLADD 示例副本上读取 2 个原理图定义、2 页、9 个器件、41 个引脚，并用新 Tcl 进程重复读取核对；源文件指纹不变。此结果不证明重复层次的 occurrence 网络、独立预期节点表、保存重开已通过。后续已完成独立引擎DC/AC/瞬态求解，原始CLI路径仍未验收；见下方实施记录。

首批实现目标：

1. 补齐自建 fixture 的独立预期节点表及 occurrence 专项验证。
2. Capture 副本最小修改、保存、新进程重开及连接核对。
3. PSpice 自建分压电路完成求解并验证 2.5 V 结果。

## 开发原则

设计文件默认在工作区副本中操作，不修改 Cadence 安装目录。兼容性结论区分文档描述、文件存在、运行时探测和完整流程验证。

本仓库只收录独立实现的代码、原创文档及可再分发的测试材料。Cadence 安装文件、官方手册全文、第三方受限插件源码和真实设计文件不纳入仓库。

## 许可证

本项目采用 [Apache-2.0](LICENSE)。该许可证不覆盖本机 Cadence 软件、官方资料或其他第三方受限材料。

导线几何检查现提供第 8 个工具 `capture_check_wiring`：已通过原生 stdio MCP 从示例读取 28 条导线并报告 2 处交叉候选，尚未验证连接点与电气语义。[几何验证记录](docs/validation/wiring-2026-10-22.md)。PDF 自动交付已延期；后续 5 阶段顺序见 [实施路线图](docs/design/04-validation-roadmap.md)。

Capture 单实例桥接基础链路已在本机实际验收，当前共132个 MCP 工具：认证、会话、状态/页面/选择、受限备注写入、持久任务查询、待执行取消、无重放结果核验恢复、停止及重载。真实双 Capture 并行尚未验收；一般电路编辑和原生 DRC 业务仍待实现。见 [桥接部署与验收边界](docs/gui-bridge.md)。

此前134项自动测试：133通过、1项Windows符号链接权限跳过；当前测试与遗留问题见CURRENT-STATE及第三批记录。实际Capture已验证保存回执丢失后由新MCP进程核验恢复、模态期间拒写、重载旧会话失效及正常保存闭环。默认会话只读，仅显式准备的副本允许固定 MCP_NOTE 属性写入。

桥接专项已完成本机单Capture模式验收，包括12秒事件线程阻塞、迟到修改拒绝、受控进程终止及新进程工作恢复。正常操作走MCP；新增命令行加载/重载工具，无需手工操作命令窗口。崩溃恢复弹窗仍可能需要桌面处理；双Capture并行不在已支持范围。[最终验收与GUI使用约定](docs/validation/bridge-final-2026-10-22.md)。

桥接加固已补充故障任务独立核验与明确结案、统一诊断、固定线程池和缓存/临时文件清理。实际连续运行通过120轮读会话、26次验证写入及6次CLI重载，全程无桌面点击。[加固结果及首次失败记录](docs/validation/bridge-operations-2026-10-23.md)。

业务开发已开始：[五阶段业务计划](docs/design/06-business-roadmap.md)。首批新增 `capture_compare_connections`，将明确预期节点表与只读Dbo定义快照中的指定引脚观察值比对，输出差异、歧义和未覆盖数量；不等于完整电气/层次连通验收。

[B1首批验收记录](docs/validation/business-b1-2026-10-23.md)：82项自动测试中81通过、1项权限跳过；实际stdio MCP与Dbo副本读取、明确缺失引脚负例已通过，完整人工正向节点表仍待专项验证。

当前按用户要求优先[Cadence子模块开发](docs/design/07-cadence-submodules.md)，暂缓Skills/规范引擎和交付整合。本批新增 `capture_get_part_properties`，通过实际stdio MCP逐个读取样例副本9个元件的有效属性，并完成独立进程重复读取与临时文件清理。[属性模块验收](docs/validation/capture-properties-2026-10-23.md)。

已按用户要求启动[Cadence子模块自主实施与验收计划](docs/implementation/cadence-plan.md)，包含34项必需功能、官方来源指纹、依赖、正反/故障验收和失败后移规则。[第一批进度及未通过项](docs/implementation/batch-01-2026-10-23.md)。目标仍在执行，当前未宣称全部完成。

自主第二批已通过批准属性在新DSN副本中的plan/apply/save/reopen，以及真实回执丢失恢复和启动窗口取消；当前总目标仍在执行。[实现与验收范围](docs/implementation/batch-02-property-edits-2026-10-23.md)。

自主第三批新增连接/图形对象查询、自定义属性生命周期、显示属性布局、已验证输出继续编辑及导入OUT诊断/偏置电压读取；50个工具契约已同步。[第三批范围与未通过项](docs/implementation/batch-03-objects-metadata-output-2026-10-23.md)。这些切片通过不代表整个业务模块或求解闭环通过。

自主第四批新增DAT导入会话、块/轨迹查询、实数/复数采样分页与关闭，54个实际工具契约已同步；官方样例12案例读取通过，自建复数多块fixture写入仍失败。[第四批验收与限制](docs/implementation/batch-04-dat-2026-10-23.md)。

自主第五批完成内部库引脚/页面编辑基座及编号身份探测；新增页面一个原生闭环通过，库重开身份和页面重命名等失败已后移，尚未开放新增工具。完整回归173项中172通过、1项权限跳过。[第五批证据与未通过项](docs/implementation/batch-05-editors-2026-10-23.md)。

自主第六批修复未绑定引脚NULL/1021读取，真实MCP四样例通过；首次库到实例放置、直线alias及独立四脚正确/断线反例通过。姿态参考帧与短接fixture仍有失败，工具总数仍54。[第六批范围与证据](docs/implementation/batch-06-reader-placement-wire-2026-10-23.md)。完整回归178项：177通过、1项既有权限跳过。

自主第七批开放5个持久wire_add工具，新增连线/alias的明确引脚与几何预期、独立重开、重启幂等、失败不重放和实际MCP恢复通过；现59工具，完整188项回归187通过、1项权限跳过。修改/删除与复杂连线及其余子模块仍待完成。[第七批范围与验收](docs/implementation/batch-07-wire-tools-2026-10-23.md)。

自主第八批接入5个库绑定放置工具，现64工具；原生MCP保存重开、明确全局热点和物理脚表、错误热点拒绝、重启幂等通过。完整192项回归191通过、1项权限跳过；cache闭包和多单元/其他姿态及故障矩阵仍待完成。[第八批范围与验收](docs/implementation/batch-08-placement-2026-10-23.md)。

自主第九批新增DSN缓存只读查询，放置专属MCP恢复/native-start取消/延迟超时通过；65工具，195回归194通过、1项权限跳过。自有OLB路径不可访问的单案例读回通过，通用缓存闭包仍未证明。[第九批范围与验收](docs/implementation/batch-09-cache-faults-2026-10-23.md)。

自主第十批新增两端点scalar导线移动/删除及alias显式处理；真实MCP闭环通过，70工具，203回归202通过/1原权限skip。中间引脚短接反例仍失败并后移，完整布线未验收。[第十批验收范围](docs/implementation/batch-10-wire-edits-2026-10-23.md)。

自主第十一批新增装饰直线受控新增及独立全局端点/连接不变核验，真实75工具MCP通过；207回归206通过/1原权限skip。D05完整图形范围仍未完成。[第十一批验收范围](docs/implementation/batch-11-graphic-line-2026-10-23.md)。

自主第十二批验证独立PSpice引擎的新DC/AC/瞬态数值，并修复新DAT元数据兼容；75工具，210回归209通过/1原权限skip，官方DAT12例回归通过。正式求解任务工具与CLI验收尚未完成。[第十二批范围](docs/implementation/batch-12-engine-dat-2026-10-23.md)。

自主第十三批开放独立PSpice引擎持久任务和关联DAT快照：DC/AC/瞬态、声明值正反例、取消/超时/回执丢失恢复及新服务幂等通过。81工具，215回归214通过/1原权限skip；CLI与完整仿真范围仍未验收。[第十三批范围](docs/implementation/batch-13-persistent-engine-runs-2026-10-23.md)。

自主第十四批新增DAT采样摘要、插值和阈值交越测量，DC/复数AC/瞬态真实MCP验收通过；82工具，222回归221通过/1原权限skip。原生MEAS及完整模块仍未完成。[第十四批范围](docs/implementation/batch-14-waveform-measures-2026-10-23.md)。

自主第十五批修复两脚库创建的位置映射，空页/带元件页重命名原生复测通过；相关公开MCP写工具尚未注册，完整L02/E04仍partial。82工具，222回归221通过/1原权限skip。[第十五批范围](docs/implementation/batch-15-library-page-2026-10-23.md)。

自主第十六批开放声明式新OLB创建，支持已验收的同构/异构共享脚、线图形和全部有效pin类型，并完成新库到DSN放置闭环。88工具，228回归227通过/1原权限skip；完整库/缓存/多unit范围仍partial。[第十六批范围](docs/implementation/batch-16-library-create-2026-10-23.md)。

自主第十七批开放 `capture_get_hierarchy`，官方FULLADD 16实例的单元身份、重复原始路径、分页及隔离验收通过；不代表完整层次网络连通性验收。89工具，230回归229通过/1权限skip。[第十七批范围](docs/implementation/batch-17-hierarchy-2026-10-23.md)。

自主第十九批开放器件姿态/删除的计划、执行、任务、取消与恢复，明确page pin-net与global hotspot预期、独立保存重开、8种居中符号姿态、原生故障与真实MCP验收通过。94工具，233回归232通过/1权限skip；完整D02仍partial。[第十九批范围](docs/implementation/batch-19-part-edit-2026-10-23.md)。

自主第二十批开放ASCII名称的新空白DSN创建及其持久任务生命周期，声明来源、原生root/空page计数、真实MCP与故障验收通过。99工具，238回归237通过/1权限skip；Unicode创建、页面图形保留与新设计下游wire仍未通过，E04/D03后移。[第二十批范围](docs/implementation/batch-20-design-create-2026-10-23.md)。

自主第二十一批增强任意方向导线精确交点/重叠及显式栅格检查，真实MCP专项通过；修复桥接端点半写入发布。总线读取及DRC运行时探测失败后移。仍99工具；最新245完整回归243通过/1进程清理error/1权限skip，当前回归未通过。[第二十一批范围](docs/implementation/batch-21-bus-drc-geometry-2026-10-23.md)。

自主第二十二批开放库引脚name/type与device pad号编辑，完整基础语义图代替ordinal比较；原生/实际MCP/故障及编辑库到新DSN放置通过。105工具，250回归249通过/1权限skip；历史进程清理问题仍open，完整L04仍partial。[第二十二批范围](docs/implementation/batch-22-library-pin-edit-2026-10-23.md)。

自主第二十三批开放single-unit definition位号映射/交换及冲突预检，真实pin-net/位置热点不变、原生/MCP/故障验收通过；多unit/occurrence和自动编号仍待完成。110工具，257回归256通过/1权限skip；历史资源问题保持open。[第二十三批范围](docs/implementation/batch-23-reference-map-2026-10-23.md)。

最新任务关联OUT与原生测量探测：[batch24](docs/implementation/batch-24-run-output-2026-10-23.md)。原生MEASURE未验收，完整P03仍partial。

缓存读取已修正为cached+local package枚举；缓存替换仍为内部专项，见[batch25](docs/implementation/batch-25-cache-2026-10-23.md)。

层次复用块与私有网络隔离专项通过，尚无通用层次写接口，见[batch26](docs/implementation/batch-26-hierarchy-clone-2026-10-23.md)。

新增5个顶层内部块复用任务工具，实际116工具；完整层次编辑仍未完成：[batch27](docs/implementation/batch-27-hierarchy-write-2026-10-23.md)。

NC增删原生专项和MCP读取通过，新建层次端口失败已留证后移：[batch28](docs/implementation/batch-28-ports-nc-2026-10-23.md)。

NC增删已接入5个持久任务工具，实际121工具；完整连接对象模块仍未完成：[batch29](docs/implementation/batch-29-nc-write-2026-10-23.md)。

独立scalar网络标签改名/移动/删除新增5个持久工具，实际126工具；全范围仍未完成：[batch30](docs/implementation/batch-30-alias-edit-2026-10-23.md)。

新增net-symbol库查询，实际127工具；global/offpage短引线原生专项通过，尚无通用写接口：[batch31](docs/implementation/batch-31-net-symbols-2026-10-23.md)。

来源绑定global/offpage创建新增5个持久工具，actual132；跨页/global-flat语义仍未完整验收：[batch32](docs/implementation/batch-32-net-symbol-create-2026-10-24.md)。


2026-10-24最新：同封装共享位号完整组放置新增5个持久工具，实际142；同构/异构/已有电源线路/同页第二组、独立源视图与原生网络、故障恢复及篡改拒绝通过。完整310回归309通过/1原权限skip；34项整体仍未全部通过，见[最新状态](docs/implementation/CURRENT-STATE.md)和[batch45](docs/implementation/batch-45-multiunit-placement-2026-10-24.md)。


单unit姿态/删除现复用part_edit的pinId期望分支，5正例与故障/共享NC保护通过；接线共享电源移动仍失败并后移。实际142工具，318回归317通过/1权限skip；完整目标未完成，见[batch46](docs/implementation/batch-46-unit-edit-2026-10-24.md)。


已有DSN缓存的缺失B/P单元补放新增1个计划工具，复用多单元持久任务族；实际143工具，325回归324通过/1权限skip。原生/MCP/恢复/取消/超时验收通过，完整目标及接线移动等遗留未完：[batch47](docs/implementation/batch-47-cached-unit-add-2026-10-24.md)。


已有库多视图放置现比较8类基础vector字段/点序/font/native顺序，16真实MCP用例、纯图形篡改拒绝、旋转文字恢复和line兼容通过；工具143，325回归324通过/1原权限skip。公共复杂图形创建与完整目标仍未完：[batch48](docs/implementation/batch-48-basic-vector-identity-2026-10-24.md)。

公共库声明创建支持9类基础vector，并新增按part读取图形的工具；混合创建/查询/放置、旧计划恢复及故障拒绝验收通过，实际144工具，333回归332通过/1权限skip。font quality非1持久化失败等完整范围继续跟踪：[batch49](docs/implementation/batch-49-public-library-vectors-2026-10-24.md)。

既有库9类基础vector可明确更新/删除，独立比对全部已建模定义与未目标图形；18实际MCP用例、双package引用更新/删除、故障拒绝和编辑后放置通过。149工具，342回归341通过/1权限skip；目录释放旧问题复现仍open，完整目标未完成：[batch50](docs/implementation/batch-50-library-vector-edits-2026-10-24.md)。

package模板、PCB名称及显式string用户属性生命周期与放置/故障验收通过；补齐所属进程退出信号等待并验收所复现目录释放时序。155工具，两次354回归353通过/1权限skip，完整目标未完：[batch51](docs/implementation/batch-51-package-properties-exit-signals-2026-10-24.md)。

私有位图DIB字节读取通过正反例及源BMP缺失重开；原生IsEquivalent忽略像素差异，公共位图能力尚未开放。3969保存失败在进程修正后仍复现，继续后移；公共基线155工具/354回归：[batch52](docs/implementation/batch-52-bitmap-bytes-save-recheck-2026-10-24.md)。


绑定DAT的CSV/JSON模拟数值导出新增5个持久任务工具，实际160；4项真实MCP与7项故障案例通过，391回归390通过/1原权限skip。完整34项仍未通过，数字逻辑访问与Capture联动等继续开发：[batch59](docs/implementation/batch-59-dat-exports-2026-10-25.md)。


原生完整分析MEASURE新增6工具，实际166；DC/TRAN/AC真实字段预期、故障恢复与旧瞬态兼容通过，401回归400通过/1原权限skip。缺测量入口问题按复现范围结案，P03整体及完整目标仍未完成：[batch60](docs/implementation/batch-60-native-measurements-2026-10-25.md)。


原生ERROR双横线非收敛漏诊已修复，新1个失败任务只读检查工具，实际167；真实非收敛/缺模型/源环路与超时分类通过，411回归410通过/1原权限skip。真实许可证失败及完整业务门禁仍未通过：[batch61](docs/implementation/batch-61-solver-diagnostics-2026-10-25.md)。


C01定义查询按原计数/空结果/重复名/精确筛选/分页/源hash与快照要求完整验收通过；空工程、同名页/重复位号、活动陈旧边界及3原官方样例复测通过。工具167、生产未改，整体仍有32项未完整通过（包含partial/deferred/planned）：[batch62](docs/implementation/batch-62-C01-query-acceptance-2026-10-25.md)。


C02定义级有效/user/display属性分层按原标准完整验收：默认/覆盖/空值/删除回退、同页及跨页重复位号、Unicode与临时清理通过。公开删除回退补验通过，E02完整范围仍未结案。整体还有31项partial/deferred/planned，167工具保持：[batch63](docs/implementation/batch-63-C02-property-layer-acceptance-2026-10-25.md)。


原生输入Setup检查新增6工具，实际173；嵌套引用/参数/模型输入与4类原生错误、7故障边界通过，独立参数分压5/3V求解通过。420回归419通过/1原权限skip；P01原命名选择器问题未结案，整体继续开发：[batch64](docs/implementation/batch-64-native-input-checks-2026-10-25.md)。


P01受限手工CIR输入按原条件完整验收：官方方括号命名节点的DC/AC/瞬态原数值预期通过，14引用边界拒绝及嵌套LIB空格路径原生检查通过。173工具、整体仍有30项partial/deferred/planned；原全局权限skip仍待最终处理：[batch65](docs/implementation/batch-65-P01-input-acceptance-2026-10-25.md)。


官方非交互psp_cmd/r新增5工具，实际178；原分压2.5V/AC/全RC及8故障边界通过，原生MEASURE兼容复验通过。429回归428通过/1原权限skip；历史CLI超时原因未证实，真实许可证失败未验收，P02仍partial：[batch66](docs/implementation/batch-66-official-cli-2026-10-25.md)。


L01库查询按原标准完整验收：官方及原单单元/共享脚/异构库4组原声明映射、分页/陈旧/重复及7边界通过。许可证子进程覆盖未复现真实不可用，仍open后移。178工具、整体仍有29项partial/deferred/planned：[batch67](docs/implementation/batch-67-L01-library-query-acceptance-2026-10-25.md)。

# 当前自主执行状态

2026-10-26。目标active：34项必需Capture/OLB/原理图/PSpice业务全部实现并原生验收后集中交用户评审。Allegro排除，PDF自动输出延期，Skills/规范引擎整合暂缓；不改安装或真实设计；按最新授权完成批次提交并推送develop，发布版保持固定。每项失败留证据后移，其余独立项继续。AGENTS.md、cadence-plan.md及cadence-acceptance.json是约束/计划/机器状态主档。

## 第一百零三批私有库配置、ALS与原生AC闭环（2026-10-26）

- CorSimSrvr_setIniFile实际接受准确文件路径。pathstring成员赋值拒绝、误传-i后无库两次失败保留；准确路径时CIR包含指定原创库，全局INI/源工程未改。没有放宽加密库策略或删除原nom库引用，默认215文件案例仍未通过。
- 旧NET链遗漏同次产生的ALS，原生PROBE alias(*)没有信号，CLI退出0/OUT完成但ORPSIM16527且无DAT。新增专门pspice_no_saved_traces和一般incomplete_simulation_output诊断，原错误优先；已有DAT继续原核验。原失败任务只recover/observe，旧文件全不变且未重跑。
- 只放入ALS不会自动引用；显式私有INI引用同源ALS后，原生CIR到真实MCP/CLI/DAT四个RC/RL复数值原预期通过，两套新目录复测成功。ALS对生成前冻结的DSN7器件14脚及4类故障审计通过。长绝对INC被原生折行，原单行预期失败留证，新增V04待验证项；工程相对引用成功不代替其修复。
- 204工具不变，595完整回归594通过/1原权限skip。原34项仍6完整通过17.6%，V04仍deferred、P05仍planned；参数修改→新原生NET/ALS→新数值和正式MCP原生生成业务未完成。说明docs/native-profile-library-aliases.md，证据batch-103-evidence.json。
- 上一批5ff0de4本地提交后GitHub连接重置，远端最后核实f6d2d9c，保持待同步。下一步围绕P05电阻参数迭代推进，不重复离线DRC菜单。alpha.1固定，安装与真实设计未改。

## 第一百零二批原生数字瞬态变更记录（2026-10-26）

- 新增只读pspice_dat_digital_samples，准确目录/别名绑定并在独立原生进程二次验证canonical。六状态、时间、原生强度码、压缩记录分页实际MCP通过；7090头行不再当作INIT/RUN各4条记录的长度。源DAT不变，无GUI。
- 合法激励0→R→1→F→0→X→Z及末尾Z共8条，独立时间/状态和相对驱动强度通过。原混合DIN5条也通过。Time/缺失名称拒绝，未知状态字26即使请求首条也整条拒绝，不猜测标志；未解释尾字不公开。
- 原Time/DIN组合读取独立进程异常、非法R→F原生hazard、DAT10写入失败全部保留。P04完整验收不提升，后移继续原始业务项。源代码、接口、原创激励/预期、资料指纹和测试见docs/pspice-digital-records.md与batch-102-evidence.json。
- 204实际工具/契约，592完整回归591通过/1原权限skip。原34项仍6完整通过17.6%，目标active，alpha.1保持固定。上一批82c885e已本地提交，但GitHub443连接两次失败，远端最后核实f6d2d9c；本批开始修正gitSyncPending=true，最终同步结果以Git实际回执为准。

## 第一百零一批原生项目与DRC计数键（2026-10-26）

- 直接DSN打开进入24.1原生Select Project Type，用户确认后生成新OPJ；其ProjectVersion仍19981106，证明不能据该字段判断17.4。新原生项目的副本两次认证打开成功、无升级窗口。PSpice资源目录不等于已创建profile，联合仿真仍待验收；官方明确既有项目可后续配置仿真。
- Tcl内部附加MessageBox、另发提示宏、项目ShowDRCOutput0均未自动结束离线菜单末尾ORCAP1805；用户关闭后原回执确认/回调恢复，无DRC重放。活动工程曾变为其他同名副本，loader拒绝错绑定，固定PID只读确认后恢复；后续使用唯一工程名。
- 新私有OPJ七个准确在线字段全部TRUE，读回7/7；直接接口无菜单弹窗。立即规范化路径计数仍0，延后以GetName原始键读到2电气错误，同文件规范化键仍0；晚到日志2电气+5物理，原14引脚连接/类型独立保持。不能由初始0排除故障，也不能以2条记录证明原四引脚全部覆盖或执行完成。
- 新增既有capture_gui_query的drc_counts：保留原生GetName键，4个计数严格校验，明确runRequested/completionVerified/coverageVerified/atomicCrossCategorySnapshotVerified均false。实际MCP重复稳定、7项配置及detach拒绝通过。首次人工把物理5误数4的reader失败保留；依据先前独立原生日志精确计数修正，未改变四引脚覆盖预期。
- 新4解析+1原生缺能力测试，580完整回归579通过/1原权限skip，203工具/扩展契约同步。V03仍deferred并后移，34仍6完整通过17.6%，目标active。下一步推进原P04数字DAT/格式门禁，菜单提示与完整DRC任务留待集中处理。详见docs/drc-counts.md、batch-101-evidence.json；安装/真实设计未改，alpha.1固定。

## 第一百批原生离线DRC检出原冲突（2026-10-26）

- 根据24.1官方指南修正为选择DSN、PCB菜单DRC；旧Tools路径在回调前拒绝，原失败保留。固定临时配置返回回调实际调用1次；原四输出冲突全部检出，新报告13errors/7ORCAP-1628。末尾查看日志问题由用户处理后晚到回执确认，回调完整恢复、配置不变。
- 原生DRC自动保存私有DSN/OPJ，原“源字节不变”预期失败及超时报告保留；独立审计另行接受冲突检出范围：新报告来源/mtime/hash成立，原始14个定义引脚连接与类型完整保持，原fixture未改。不是不保存的只读操作，不能套用到真实设计。
- 报告解析新增逐条诊断及行号、页和打印坐标，13条错误均可定位；坐标单位不猜测。byPhase只表示最近明确章节，不能当作已验证原生分类（界面与报告章节存在差异）。新增3测试；575完整回归574通过/1原权限skip，正式203工具不变。
- 运行程序版本核实24.1-2024；OPJ来自24.1随附旧模板，ProjectVersion历史字段并非17.4运行证据。再次复制保存后的OPJ仍触发升级，用户指出None无法选择；当前请求取消，不再重复。仅24.1已保存DSN的新副本已准备，尚未打开；末尾MessageBox宏尚未运行验收。
- V03仍deferred并后移，原在线规则0/漏检失败保留；干净fixture、结构化MCP原生DRC任务及完整自动闭环未完成。34仍6完整通过17.6%，目标active。详见docs/native-drc-offline.md、batch-100-evidence.json。安装/真实设计未改，alpha.1固定。

## 第九十九批原生DRC配置只读查询（2026-10-26）

- 扩展既有capture_gui_query：drc_configuration。认证实例/会话/代次与原生DesignPath绑定，受限读取配置，不调用保存/启用/执行；返回配置开关、7在线电气规则计数及16×16 ERC矩阵。字段/布尔值/矩阵形状严格校验，原16KiB协议上限不变，原始路径/配置正文不向MCP公开。
- 实际Capture PID5256/MCP重复查询一致，detach后拒绝；当前flow/master=1但7在线电气规则全0，OUT/OUT矩阵E。首次传输超长失败保留；紧凑的已检查字段后通过。GetDRCSettings查询准确配置字段仍返回unknown，不能据此推断规则ID或启用成功。
- 新5解析测试+1原生Tcl缺能力拒绝，572完整回归571通过/1原权限skip；实际203工具、扩展契约已同步。未运行本批DRC，原冲突未检出的失败保持，V03仍deferred；34项仍6完整通过17.6%，目标active。说明docs/drc-configuration.md，证据batch-99-evidence.json。
- 下一步核实按设计规则标识及真正原生执行器；未获证据则后移并推进其他原始子目标。无桌面操作/安装/真实设计修改，固定alpha.1不变。

## 第九十八批未使用模型库预检（2026-10-26）

- 依据官方LIB按需读取与INC全文读取区别，新增严格限定的平坦字面量R/C/L/V/I电路证明。引用图/物理行绑定、未知语法拒绝，proof写入不可变plan，执行前及路径重定位后重新计算；不删库、不改模型正文。仅完全未被请求的可读子电路中的数字FILE模板可豁免，非一般模型解析器。
- 自建私有分压器经实际MCP/psp_cmd /r/OUT/DAT核对2.5V及来源通过；原生输出选择器错误和DC误要求虚部的两轮失败保留，数值/容差未放宽。新增6host测试，566完整回归565通过/1原权限skip，正式工具仍203。
- 原生AC默认215文件完整闭包重新准备，plan拒绝；诊断定位deps/file-033.lib第2775行$CDNENCSTART。加密内容无法检查，未豁免或启动该案例求解器，原AC数值预期不变。V04仍deferred，34项仍6完整通过17.6%，目标active。下一步按计划转向V03准确DRC配置读回，模型闭包问题留待集中修复。
- 说明见docs/pspice-model-use.md，证据batch-98-evidence.json；无GUI/安装/真实设计修改，alpha.1固定。

## 第九十七批原生模型库元数据（2026-10-26）

- 新只读pspice_inspect_library，正式203；本地固定parseLib读取私有快照，返回顶层模型/AKO名、子电路形式端口、局部定义计数和分页。引用库/二进制/非法作用域结构拒绝，源/快照指纹及完整顶层声明核对；无模型正文发布/求解/远端调用。
- 自编4定义及AKO、2/3端口筛选标记、分页/参数拒绝真实MCP通过；官方breakout副本75顶层+32未返回局部定义核对。首次全作用域预期导致拒绝保留，明确顶层契约后新目录验收；不是模型依赖闭环通过。
- 新6host，203契约同步；560完整回归559通过/1原权限skip。原34项仍6完整通过17.6%，V04仍deferred、D03仍队尾。使用见docs/pspice-library-metadata.md，证据batch-97-evidence.json及批次说明。下一步显式模型/AKO/子电路使用与外部文件依赖，及DRC准确规则配置。

## 第九十六批导线名称与活动页更新（2026-10-26）

- 默认线仍重开3969，SetName空/显式名均在保存前1021。3例原预期/失败保留，名称初始化不是已验证修复。
- 新初始化空页在真实活动编辑器创建线后UpdatePageState未返回，最后标记before_update_page_state；实际Capture异常退出提示已观察，关闭后获准查询确认原20696退出。无保存，磁盘源仍原空页且独立0对象，未重放。具体异常码未记录，不冒称已定位底层根因。
- 重启一次原Capture，取消自动恢复旧项目，固定接口打开干净私有控制DSN并绑定新PID5256；bridgeReady/sourceUnchanged通过。必要GUI只处理升级、打开私有页和异常恢复，不绘线、不上传工程。
- D03失败后移队尾，转向模型库依赖接口和明确DRC规则配置。正式202工具/生产不变，本批语法/原生/独立审计；沿用554回归553通过/1原权限skip。原34项仍6完整通过17.6%，目标active，详见batch-96-evidence.json和批次说明。

## 第九十五批页面编辑器初始化对照（2026-10-26）

- 新私有空页先独立读取成功，旧绑定在前次保存后因指纹变化正确拒绝；重新认证后只派发一次Open，升级弹窗None/Finish后晚到回执单独审计，未重放。
- MAIN编辑器打开即dirty，专用固定脚本只保存空页初始化并独立核对0对象；同一初始化字节、相同原导线预期，再经GetActivePage/GetActiveView身份检查创建/保存导线，独立NextPage仍3969。初始化空页通过，导线未通过；不把两者混为成功。
- 原失败、空页初始化及导线结果分别留证；无GUI绘线/真实设计/安装修改。正式202工具/生产合同不变，本批语法/原生及独立审计，沿用第93批554回归553通过/1原权限skip。
- 原34项仍6完整通过17.6%，目标active。第94批1173fcc和本批042af82已成功推送develop，网络中断记录保留。下一步导线构造/序列化前置条件及DRC、模型依赖原门禁，详见batch-95-evidence.json和批次说明。

## 第九十四批应用会话导线与私有DRC启用（2026-10-26）

- 按设计EnableDRC候选键返回1，配置读回仍0；未执行DRC，finally恢复，完整配置和DSN/OPJ不变。原冲突未检出问题保持，不能凭返回值宣称规则启用。
- 新空DSN先独立重开通过，再在Capture真正应用会话DboSession_s_pDboSession创建/完整保存固定导线，确认回执；独立NextPage仍3969，原坐标预期保持。排除仅因另建Dbo会话的解释，编辑器/页面视图初始化尚待验证。
- 最小OPJ触发旧工程升级弹窗；初受限进程查询误判退出，UI和获准查询证明原20696仍运行。None选择跳过转换，误选提示复选框已恢复，原Open晚到回执单独审计无重放，认证绑定恢复。无宿主崩溃证据。
- 正式202工具/生产契约不变，本批诊断语法、原生调用/独立重开及来源审计；沿用第93批554完整回归553通过/1原权限skip。原34项仍6完整通过17.6%，目标active。详见batch-94-evidence.json及批次说明；安装/真实设计未改。

## 第九十三批模型原始字节与扩展预算（2026-10-26）

- 定位opamp.lib非UTF8字节含实际模型行；显式preserve-bytes保持原字节，不猜编码。standard预算64文件/32MiB保留，extended256文件/64MiB可选；两者单文件8MiB/深度32，策略纳入manifest/持久plan及任务重定位。
- 原生默认库215文件/34549814字节闭包实际MCP准备及逐文件来源/字节审计通过，1649 opaque字节保持。PROBE64及CORE数值PATH兼容修复；ROM/PAL外部FILE模板仍导致执行拒绝（4库），原生AC未运行验收。完整V04不提升。
- 分压器首轮插注释导致原标题移入正文，原失败留证；新副本CLI完成但OUT注释未定义字节阻断核验。显式模式仅转义完整注释行显示，其他行严格；原任务MCP只恢复核对2.5V/OUT/DAT，原生hash不变，无重跑。
- 正式202工具新增参数契约已同步，554完整回归553通过/1原权限skip。原34项仍6完整通过17.6%，目标active。使用见docs/pspice-input-options.md；证据batch-93-evidence.json。下一步模型使用/外部依赖闭环与明确DRC规则覆盖；安装/真实设计未改。

## 第九十二批原生CIR与DRC配置（2026-10-26）

- 认证只读取得DRC配置：flow1、在线电气各规则0，ERC输出对输出E；内部候选GetDRCSettings键返回unknown，未猜测启用或写全局配置。原冲突零错误负例保持失败。
- 本地独立CorSimSrvr实际profile→CIR：缺profile子目录首轮update=-1；遵循官方mkdir前置条件的新副本update0生成638字节CIR，原AC100点/0.1–200及NET引用独立核对，4负例拒绝。未执行远端/求解器。
- 修复官方nom.lib分号行尾注释引用解析，新增2测试；相同CIR闭包由unsupported_reference推进到unsupported_encoding，未悄悄转码或移除库。正式202工具不变，546完整回归545通过/1原权限skip。
- 原34项仍6完整通过（17.6%），V03/V04及模型闭环未通过。详见batch-92-local-profile-cir-drc-config-2026-10-26.md和batch-92-evidence.json；下一步明确库编码/依赖来源与按设计规则配置，安装/真实设计未改。

## 第九十一批宿主恢复、本地NET与在线DRC（2026-10-26）

- 一次必要的PSpice A/D启动产品弹窗确认后，Capture20696响应恢复；认证只读桥接重建成功。旧wire派发随后确认，未重放；独立重开仍NextPage3969，原失败报告不改。
- 固定本地NET接口实际生成294字节新NET；导出前冻结原DSN，7元件14引脚及参数/电源极性一致，错接/漏件/错值/反极性4负例拒绝。尚无原生CIR/profile/模型依赖闭环和公开生成任务，V04不通过。
- 在线DRC运行/转储成功；新报告来源/时间/hash核对成立。但预先声明并保存重开的4输出引脚冲突仍报0错误0警告，负例失败。不能把干净样例的0错误称为规则有效；V03仍未通过。实例类型设置无效及枚举前置拒绝均留证。
- 开发诊断工具变化，正式MCP202/生产契约不变；沿用第90批544完整回归543通过/1原权限skip，本批进行语法、真实原生调用和独立审计。34仍6完整通过（17.6%），目标active。
- 详见batch-91-host-local-netlist-drc-2026-10-26.md与batch-91-evidence.json。下一步核查明确的电气规则配置/覆盖及本地profile到CIR生成；不调远端ASP，不改安装/真实设计，alpha.1固定。

## 第九十批页面尺寸与声明边界（2026-10-26）

- 新2只读工具，实际202；原生physical/doc尺寸、比例/标志及声明comment控制点边界，零尺寸明确未知。英制/公制、9对象27点/0与10留白、其他/空/零页、非法/关闭及缓存变更拒绝真实MCP通过；迭代边界故障拒绝且不发布结果。
- 先前fixture语法错误在DB入口前退出，源/report保留，Tcl完整性修正后新副本验收。零尺寸3969假说经6组新设计尺寸初始化仍失败，且既有成功wire页同样0×0，未作为修复；原失败和预期保持。
- 新8host、202合同同步，544完整回归543通过/1原权限skip。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active；C05/D05/V02完整范围保留。
- 说明见docs/page-bounds.md，证据见batch-90-page-dimensions-bounds-2026-10-26.md及batch-90-evidence.json。无GUI、安装/真实设计修改；第87–89批已同步develop 2800f75，alpha.1固定。

## 第八十九批文字更新删除（2026-10-26）

- 新1个edit planner复用文字任务family，实际200工具；不可变页图形index/nativeId定位，update完整替换/delete拒绝change，其他有序图形、原实例已建模状态及定义/连接保持。
- 32混合图形/4同名文字中8姿态更新及首/中/末删除11真实MCP通过；update/delete各4原生故障通过，3新增兼容复测和3旧plan/receipt只读副本核验通过，均不重放。故障扩展脚本首次语法错误在执行前退出，未启动native。
- 新5host，200合同同步，536完整回归535通过/1原权限skip。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active；完整C05/D05仍未通过。
- 使用见docs/graphic-text.md；证据见batch-89-page-text-edit-delete-2026-10-26.md及batch-89-evidence.json。后续页面边界/视觉及其他原门禁；无GUI、安装/真实设计修改。前批提交待网络恢复一起补推develop，alpha.1固定。

## 第八十八批页面文字写入（2026-10-26）

- 定义层Location/BoundingBox及逆姿态保留页面锚点，8native姿态通过；原实例位置仍0，旧失败保留。新5任务及open-result kind，实际199工具，冻结所有支持页图形顺序/几何、原实例已建模状态及定义/连接。
- 3真实MCP中文/多行/旋转镜像/字体、非法输入/取消/fresh不重放通过；回执丢失只核验、启动取消、DLL加载后marker超时、无关原生额外图形apply/recover拒绝通过。首次helper缺失及取消harness错误期望失败均保持，独立审计分类。
- 新5host，199合同同步；531完整回归530通过/1原权限skip。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active；完整D05/C05不提升。
- 说明见docs/graphic-text.md及batch-88-page-text-add-2026-10-26.md。后续文字/图形编辑删除及页面/视觉/其他原门禁；无GUI，安装/真实设计不改。同步develop，alpha.1保持固定。

## 第八十七批非居中坐标框架（2026-10-26）

- 原40×40符号中心候选8姿态匹配；80×40偏移边界否定中心假设（2/8），失败保留。新100×60偏移边界在写入前声明宽高补偿模型，8native保存重开及8真实MCP/关闭拒绝通过；独立原生点转换与pin热点相同。
- 原origin失败与新中心失败均保持，补充只读审计解释24已存结果，未重写旧oracle；首次报告更新脚本中断目录也保留。新docs/coordinate-frames.md明确有限验证范围及实际热点使用方法，完整C03仍未通过。
- 正式194工具/生产/合同不变；沿用第84批526完整回归525通过/1原权限skip，本轮语法/native/MCP/进度检查。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active。
- 宿主旧派发仍无boot/receipt，不重发、无桌面输入。详见batch-87-noncentered-coordinate-frames-2026-10-26.md及batch-87-evidence.json。第85/86批已推送develop c12aa71。

## 第八十六批导线逐点构造与宿主对照（2026-10-26）

- 空构造+NewPoint旧版本仍3969，新版本0页内导线/重开objects空，两个SetPoint返回1003；五例均失败，原报告与独立分类审计保持，未放宽预期。
- 宿主转发绑定原私有PID20696/设计及独立Dbo会话，但无boot/receipt；保留dispatch_unacknowledged_no_replay。窗口只读观察有未响应Capture及产品选择窗口，未获得可操作产品控件，无桌面输入；不重发，不冒称宿主保存失败/成功。
- 正式194工具/生产代码/合同不变；沿用第84批526回归525通过/1原权限skip。本轮语法、证据断言、进度检查。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active。
- 详见batch-86-wire-points-host-2026-10-26.md及batch-86-evidence.json。下步先观察同一宿主派发是否确认，再处理宿主依赖；安装/真实设计未改。GitHub网络故障，上批c665385尚待补推。

## 第八十五批导线页面初始化对照（2026-10-26）

- 默认、实际先建网络、InitUndoRedoData三例仍NextPage3969；UpdatePageState前/后/撤销初始化后三例原生3221225477，第二轮调用前后落盘标记确认停在该调用，所有owned进程归零。
- 两轮各六例全部失败，原预期与失败证据保留；未将这些API接入正式写入，生产读取仍严格。此结论限当前独立解释器夹具，不宣称GUI/整个SDK不可行。
- 正式工具仍194，无生产实现变化，沿用第84批526完整回归525通过/1原权限skip。本轮诊断语法、证据断言及进度检查；34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active。
- 详见batch-85-wire-page-state-2026-10-26.md及batch-85-evidence.json。下一步比较成功已有页与新建页原生状态及序列化；不改安装/真实设计，无GUI。

## 第八十四批引脚标志（2026-10-26）

- 新只读capture_get_library_pin_style，既有pin edit新增long/clock/dot；完整11标志/共享scope及定义/图形/起点/模板保持，实际194工具。
- 首组合误将global当独立字段，失败及唯一差异审计保留；16原生转换确认power或hidden派生规则，新计划明确预览，原失败摘要仍拒绝。5新MCP、4原生故障及marker超时/陈旧副本读取拒绝通过。
- 新8host；526完整回归525通过/1原权限skip，合同同步。L04仍partial；34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%不变，目标active。
- 说明见docs/library-pin-style.md和batch-84-library-pin-style-2026-10-26.md；仅同步develop，alpha.1/main/tag保持固定。无GUI、安装/真实设计修改。

## 第八十三批单单元引脚边界（2026-10-25）

- 两组0..4095稀疏/独立乱序12脚、全部type/visibility/swap边界、第三组非空Unicode/128字符/重复名真实MCP保存重开/完整图/逐条分页/fresh不重放通过。
- 原空名矩阵保存重开变$PIN0，三种官方setter探针仍不符；唯一字段差异及原oracle/输出hash审计保持。创建schema/Python现提前拒绝空名，显式非空矩阵与原失败分开，未认证精确空名。
- ISS-L02-empty-pin-name-canonicalization open，完整L02 deferred后移；193合同同步。新2host，518完整回归517通过/1原权限skip；34现6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%不变，目标active。
- 无GUI、安装/真实设计修改；只同步develop，alpha.1固定不变。详见batch-83-library-pin-boundaries-2026-10-25.md。

## 第八十二批跨页缺失单元及alpha.1（2026-10-25）

- 既有缺失单元补放新增显式targetPageId，同schematic跨页冻结全部原实例已建模状态，并校验共享pad原生身份；原同页/旧计划兼容。普通B跨页原生与真实MCP、原B同页通过；供电P.8跨页VCC变unbound，严格拒绝，原引脚保持，失败与只读差异审计保留。
- ISS-D01-crosspage-shared-vcc-unbound open，完整D01 deferred后移。34现6 passed/1 baseline/8 partial/17 deferred/2 planned，目标active；不将跨页普通单元当成完整供电/flat验收。
- 用户授权首次预发布v0.1.0-alpha.1（包0.1.0a1）。193合同同步，516完整回归515通过/1权限skip；wheel独立安装、pip check、实际193合同/Capture查询/官方CLI新DC2.5V/DAT读取通过。首次CIR命名节点PROBE语法失败保留，修复示例后数值预期不变。
- 安装/试用/反馈与已知问题见docs/testing/alpha-1.md；无GUI、安装/真实设计修改。本次Git发布按用户明确授权执行，完整业务开发继续。

## 第八十一批同OLB封装家族（2026-10-25）

- 既有建库spec新增packages联合声明，同OLB 2..8独立封装，名称/原生cell/part隔离与家族资源预算；物理pad按包分别计数，完整图与混合vector/native顺序、位图冻结字节独立重开比对，旧单包兼容，实际仍193。
- 四组真实MCP及错误期望/冲突/取消/fresh不重放/终末篡改拒绝通过；位图原件在apply前移走仍正确创建。四类原生故障含第二包footprint真实篡改拒绝通过；两个封装分别放置原空页副本后脚号/热点/实例footprint通过，源hash保持。
- 新8host；508完整回归507通过/1原权限skip，合同同步。首次放置harness历史report字段错误未进入业务调用，修正来源并校验旧hash后重测通过，原空失败目录保留。
- L02/L03完整门禁仍partial；34仍6 passed/1 baseline/9 partial/16 deferred/2 planned，目标active。无GUI、安装/真实工程修改或提交；详见batch-81-library-package-families-2026-10-25.md。

## 第八十批层次迭代错误完整性（2026-10-25）

- 复现旧读取器将原生迭代错误当正常结束：显式3969故障下仍返回缺属性的24节点或14/24节点树。修改前源/adapter/错误输出/false报告保留。
- 有效属性严格1022结束，children NULL后检查状态及缺失iterator；原生/Python文本与UTF-8总预算显式拒绝。修正后同故障exit1且无JSON，正常24节点全量文档逐字段不变，源/副本hash保持。
- 真实MCP重复层次覆盖隔离/重开/变更/关闭拒绝通过；新5host，500完整回归499通过/1原权限skip，193合同hash不变。仅结案迭代错误漏报，H01/root原问题仍deferred。
- 34仍6 passed/1 baseline/9 partial/16 deferred/2 planned，目标active。无GUI、安装/真实设计修改或提交；详见batch-80-hierarchy-iterator-integrity-2026-10-25.md。

## 第七十九批occurrence属性层（2026-10-25）

- 新只读capture_get_occurrence_properties，实际193。完整unit路径选组件occurrence，分开读取effective/direct-user与即时定义层，区分定义base/full/device身份；不由同值推断全继承来源。
- 两重复子模块共用定义但中文/特殊字符/换行标记独立，一侧Value覆盖不污染另一侧及定义，定义标记两侧继承；完整保存重开与真实MCP重复读取/重开/源变更/关闭拒绝通过，源/expected hash保持。
- 原root属性读取导致隔离Tcl3221225477，原请求/报告/源保留、精确方法未定位；Python及Tcl现双重预拒绝root，不伪造空值成功。ISS-H01-root-property-native-access-violation open，完整H01 deferred后移，根/递归/资源等原条件未通过。
- 新7host；495完整回归494通过/1原权限skip，193契约同步。34现6 passed/1 baseline/9 partial/16 deferred/2 planned，目标active。无GUI、安装/真实设计修改或提交；详见batch-79-occurrence-property-layers-2026-10-25.md。

## 第七十八批P03结果门禁通过（2026-10-25）

- 已验证测量inspection新增保守fieldUnits/measurementUnits，V/I及分析/唯一DC源扫描轴维度，WHEN值与at、TRIG延迟分开；复杂/未知表达式为null，nativeUnitMetadataAvailable=false。仅返回投影，不改旧数值/raw、任务或manifest；输入/产物hash再次核对。
- 全新3原生测量+引擎/CLI各3 DC/RC/AC通过，541点tau相对误差约0.0004062%、301点截止约0.003724%；exit0非收敛/缺模型/环路拒绝及错误3V预期通过。电流/延迟/unknown PARAM原生边界与3旧任务只读兼容通过，当前6任务全部产物hash及CLI原始规范身份审计通过。
- P03按原明确条件passed；原全语法/数字/许可证/Capture输入及联动边界保留，不替代P02/P04/V04/P05。新8host；488完整回归487通过/1原权限skip，192契约说明同步。34现6 passed/1 baseline/10 partial/15 deferred/2 planned，目标active。详见batch-78-P03-results-acceptance-2026-10-25.md。

## 第七十七批页面图形明细（2026-10-25）

- 新只读capture_query_page_vectors，实际192。八类图形定义/样式/文字及14字体字段、实例姿态和原生页面控制点，native顺序/分页/完整unsupported行；复用固定embedded Tcl/DIB回调，局部文字矩形不认证渲染边界。
- 32声明矩阵中28非文字的全部定义/姿态及独立手算页面控制点通过；4文字实例位置在构造及显式SetLocation成功保存后仍0,0，原预期/失败/输出保持。复用ISS-D05-comment-text-coordinate-frame补证，D05完整门禁deferred后移，未发布文字写入。
- 实际MCP32读取、旧清单身份/坐标对应、逐条分页、空页、cursor/scope、6次额外开关、缓存源变更/关闭拒绝通过；readContractPassed=true，文字位置及完整矩阵passed=false保留，C05仍partial。
- 新7host；480完整回归479通过/1原权限skip，192契约同步。34现5 passed/1 baseline/11 partial/15 deferred/2 planned，目标active。无GUI、安装/真实设计修改或提交；详见batch-77-page-vector-query-2026-10-25.md。

## 第七十六批连接对象补验（2026-10-25）

- 原已有样例9端口的计数/名称、逐条分页、跨页同名隔离、空端口页、明确CARRY_OUT直连U1.3与其他端口在线段上的几何一致性、共享NC owner/热点通过；cursor/scope/关闭/缓存变更拒绝及6次额外开关会话通过，原输入/预期hash保持。
- 新40对象四方向/镜像/跨页同名/空页矩阵保存receipt成功，但MCP重开失败，诊断为NextPage载入3969；原DSN/expected/report保留，姿态假设尚未进入比较。ISS-C04-inventory-matrix-reopen-3969 open，完整C04 deferred后移，不将保存当验收。
- 生产/191契约与第75批hash保持；沿用473回归472通过/1原权限skip，本批未新跑。34现5 passed/1 baseline/12 partial/14 deferred/2 planned，目标active。原测试脚本全局nativeId及强制有线假设修正记录保留，无生产读取放宽。详见batch-76-connection-inventory-2026-10-25.md。

## 第七十五批显示字体（2026-10-25）

- 新6字体查询/plan/apply/jobs/cancel/recover，verified打开kind=display_font，实际191。nativeId单元绑定、完整14字体字段及默认标记/类型、所有实例已建模状态/定义/连接冻结与独立重开检查；不改旧显示布局计划。
- 两真实MCP字号/粗斜体/下划线/字体名及独立drawn默认字体true→false通过；六故障、pending cancel/fresh不重放及终末篡改open/recover/apply拒绝通过。原Value并非默认字体，未冒充继承转换。
- quality2保存为1，唯一字段差异审计及原失败report/账本/期望/输出hash保持；总体MCP报告false保留。ISS-E02-display-font-quality-persistence open，E02完整门禁deferred并后移。首getter原型及register标记缺失失败保留后修正。
- 新7host；最终473完整回归472通过/1原权限skip，191实际契约同步。34现5 passed/1 baseline/13 partial/13 deferred/2 planned，目标active。无GUI、安装/真实设计修改或提交；详见batch-75-display-fonts-2026-10-25.md。

## 第七十四批跨页映射与原生编号实验（2026-10-25）

- 原生跨页A/B夹具及中文/三类非默认display保持通过；实际MCP分别从两页代表发起两例整组改号、重复/冲突/pending cancel/fresh不重放/终末篡改拒绝通过，原独立pin预期/源/夹具hash保持。
- GetRefDesMgr实际入口核实；官方AnnotateIncremental执行保存，但R?未变且两个非目标层次块追加数字，定义/状态/unit严格不符，连接对象/缓存不变。失败原预期/输出/report及只读三差异审计保留；ISS-E03-native-incremental-target-scope open，E03完整门禁deferred并后移，自动编号未发布。
- 无生产更改，185契约及第73批生产hash保持；沿用466回归465通过/1原权限skip，不伪称本批新跑。34现5 passed/1 baseline/14 partial/12 deferred/2 planned，目标active。先推进其他独立项；详见batch-74-crosspage-and-native-annotation-2026-10-25.md。

## 第七十三批整组位号映射（2026-10-25）

- 新1个capture_plan_package_reference_map，复用既有reference任务链，实际185。来源缓存/完整unit组/共享脚一致性、基础与完整位号冲突、整组临时位号交换，冻结旧新节点全集；精确Reference字段更新，完整已建模实例状态/缓存/NC归属独立重开验证。
- 同构/异构未接线、异构电源及双组互换4真实MCP通过，原独立expectedPins及源hash保持；fresh不重放/recover、共享脚真实NC保持及6故障通过。跨页仅host已验，occurrence/自动编号/未编号及非默认显示完整矩阵仍未验，E03保持partial。
- 新10host；466完整回归465通过/1原权限skip，185实际契约同步。34仍5 passed/1 baseline/15 partial/11 deferred/2 planned，目标active。L05原GND失败未关闭；无GUI、安装/真实设计修改或提交。详见batch-73-package-references-2026-10-25.md。

## 第七十二批持久兼容缓存替换（2026-10-25）

- 新5个plan/apply/jobs/cancel/recover缓存替换工具，verified打开kind=cache_replace，实际184。源限定完整组、独立DSN/OLB、位号/string覆盖恢复、全实例已建模几何/有效/user/display层及来源缓存逻辑图/连接/实际源视图严格重开验证；不重放，终末DSN与私有OLB均验hash。单进程全实例扫描显式记录drawn无物理号1021为不适用，placed/其他错误仍拒绝。
- 原接线与中文/特殊字符/非默认display两组MCP、七故障、同构双单元及接线异构组通过；异构未接线组失败：U501物理7 GND由unbound变GND，连接对象图未变，严格拒绝输出。原预期/源/输出及失败账本保留，ISS-L05-heterogeneous-unbound-gnd-replace open并后移，L05完整门禁deferred。
- 新8host及13针对性通过；456完整回归455通过/1原权限skip，184实际契约同步。34现5 passed/1 baseline/15 partial/11 deferred/2 planned，整体active；继续其他独立编号/库/原理图项，最后回到GND及其他原生遗留。详见batch-72-durable-cache-replace-2026-10-25.md。

## 第七十一批缓存来源限定（2026-10-25）

- 新增只读capture_query_cache_binding，实际179；同进程完整缓存定义/来源/实例原生绑定关联，独立清单核对全部placed覆盖和nativeId/device/view，确认GetCachedPackage源键命中实际placed包，区别同名本地定义，不打开外部源库。
- 原prepared及replace0/1三组MCP、共享位号A/B、旧查询ID、重复/关闭/陈旧/外来/drawn拒绝通过。两原替换输出只读审计的源限定缓存逻辑图、未目标缓存逻辑元数据、全部有效属性与覆盖及4实际符号视图通过；不重放/不更新原失败账本，L05/原issue仍未结案。
- 新5host；首448因旧178工具数断言失败保留，改179并加只读/参数检查后最终448回归447通过/1原权限skip，179实际契约同步。34状态不变，整体active；下一源限定持久替换及覆盖来源保持，详见batch-71-cache-source-identity-2026-10-25.md。

## 第七十批批准参数/模型引用与E01门禁（2026-10-25）

- 原property工具新增Implementation/TC1/TC2，已有PSpice Model类型、字面模型标识和有限十进制系数检查；所有新批准字段计划冻结/重开比较完整有效属性多重集，并保留原pin-net基线。严格1022结束、器件/属性/文字预算，旧计划不追溯升级。
- 五字段真实MCP及官方FULLADD有线样例3例通过；五故障含真实不相关R10.TC2改变拒绝、最终只读复验通过。独立参数转录的3个温度分压及2个模型二极管数值通过，明确不是原生Capture网表/P05验收。初缺PROBE无DAT与新增扫描器变量冲突保留并修复复验。
- 新5host，443完整回归442通过/1原权限skip，178实际契约同步。E01原条件审计passed；34现5 passed/1 baseline/16 partial/10 deferred/2 planned，整体active。详见batch-70-approved-properties-2026-10-25.md；继续库缓存/编号及原理图剩余门禁。

## 第六十九批库引脚起点及类型属性核实（2026-10-25）

- 既有pin edit新增startPoint，起点与hotSpot分开声明，预览完整受影响视图及旧/新起点；共享旧值一致性、64行和严格坐标限制，原生旧值检查与独立完整已建模图重开验证。
- 单单元Normal/Convert、共享双单元及异构POWER4组真实MCP、组合字段/schema/no-change/fresh不重放/篡改拒绝通过；丢回执/启动取消/真实1秒执行超时3项通过，原源不变。5新host，438完整回归437通过/1原权限skip，178契约同步。
- typed package user property在两种NewUserProp及显式SetValue重载的3组观测中，值类型2/1/3/6/16均成为属性字符串0，重开仍0；值setter还报告Code1/Failed1，未放宽生产检查。首脚本路径/早期严格检查失败保留，ISS-L04-typed-user-property-persistence open并后移，未证明产品限制。34状态不变，目标active；详见batch-69-library-pin-start-2026-10-25.md。

## 第六十八批库引脚热点与可见性（2026-10-25）

- 既有pin edit工具新增可选hotSpot/visible，实际仍178；严格坐标/布尔、旧值核对、共享符号影响预览，并冻结/重开比较完整已建模定义/模板/pin-start/vector图。旧计划保持原验证范围。
- 单单元Normal/Convert、共享双单元及异构POWER4组真实MCP、组合旧字段、schema/no-change、取消、fresh不重放、输出篡改拒绝通过。丢回执/启动取消通过；原短超时落在计划扫描、保留false报告，单独apply-only timeout补测通过。错误保持图与计划后源变更反例通过。
- 4新host；补配置原生Tcl后433完整回归432通过/1原符号链接权限skip，178实际契约同步。34状态不变，L04仍partial、目标active。下一typed库属性及其他引脚字段；详见batch-68-library-pin-geometry-2026-10-25.md。

## 第六十七批L01库查询门禁通过（2026-10-25）

- child-only CDS_LIC_FILE不可用端口对照中CLI/Setup仍成功，未建立真实license失败条件；父环境/源不变，P02缺口open后移，不改全局配置。
- 官方库与原单单元/共享双单元/异构库4组MCP查询按原独立device/part/pin映射声明全部通过；分页/归属/视图与物理脚区分、游标/陈旧/关闭及重复打开通过，7实际边界含junction越界拒绝通过。
- L01按原条件passed，其他glyph/嵌入/放置与封装几何门禁不替代通过。34项现4 passed/1 baseline/17 partial/10 deferred/2 planned，目标active；178工具及429回归428通过/1原权限skip生产基线摘要保持。详见batch-67-L01-library-query-acceptance-2026-10-25.md。

## 第六十六批官方CLI任务（2026-10-25）

- 原电路官方psp_cmd/r本次2.171秒生成OUT/DAT，附加/e/o/d/l组合返回2；固定/r新增5工具，实际178。单分析计划、原始/规范身份、独立DAT与声明数值验证，旧产物执行前拒绝。
- DC/AC/全RC3真实MCP正例、非法输入/待执行取消及fresh lifecycle通过；8故障含真实1秒CLI timeout/主动取消/丢回执恢复/原始规范篡改/旧输出/错误预期通过，原生MEASURE复验保持。
- 新9host，429完整回归428通过/1原权限skip，178契约同步。CLI原失败按当前功能验收结案，历史60秒原因未证实；真实license失败仍open，P02整体不通过。34状态保持3 passed/1 baseline/18 partial/10 deferred/2 planned。详见batch-66-official-cli-2026-10-25.md。

## 第六十五批P01输入门禁通过（2026-10-25）

- 原IN/OUT选择器歧义按官方方括号强制节点语义处理，3原错误重现、6正确DC/AC/瞬态命名选择求解通过；原源/数值oracle不变，DC本次PRINT表、AC复数/截止、全瞬态/tau均通过。
- 14引用/执行边界在native worker前拒绝，包括实际Windows junction越界；含空格的嵌套LIB/INCLUDE原生正例通过。结合64批模型/地/参数/分析反例与故障闭环，P01按原受限显式引用范围标passed，命名选择issue结案。
- 34项现3 passed/1 baseline/18 partial/10 deferred/2 planned，整体active；173工具与420回归419通过/1原权限skip基线摘要保持，无生产更改。全方言/隐式文件等原限制及其他门禁不自动通过。详见batch-65-P01-input-acceptance-2026-10-25.md。

## 第六十四批P01原生输入检查（2026-10-25）

- 新6定型输入检查工具，实际173；固定Setup/FINISH/cleanup，不执行数值分析，严格完整准备清单hash/冻结输入/OUT/receipt身份，setup.dat不认证为波形。
- 嵌套参数与模型OP两正例及缺地/缺参数/分析缺参/缺模型4反例MCP通过；单独新DC求解5/3V预期通过。7故障边界通过，缺回执不因OUT无错而认证；补依赖清单身份后v2全复验通过。
- 新9host，420完整回归419通过/1原权限skip，实际173契约同步。P01仍partial，原命名输出选择器问题未结案，下一官方方括号节点形式对照；34门禁状态保持2 passed/1 baseline/19 partial/10 deferred/2 planned。详见batch-64-native-input-checks-2026-10-25.md。

## 第六十三批C02属性分层门禁通过（2026-10-25）

- 缓存LibPart默认/显式覆盖/显式空/删除回退4组各4实例真实MCP分层读取通过；effective接口全集一致，中文及特殊字符逐字、显示位置隔离、重复读取/临时清理、错误目标/陈旧/关闭拒绝通过。
- 原同页U501双单元按原独立位置声明属性读取通过；公开删除默认恢复及错误缺失预期拒绝/不重放、新服务恢复通过，E02仍partial。
- C02按原条件标passed，完整外部继承链/occurrence/渲染边界仍未认证。34项现2 passed/1 baseline_passed/19 partial/10 deferred/2 planned；167工具、生产无改，第61批411回归410通过/1原权限skip基线摘要核对保持。私有脚本编码失败与package非继承对照保留。详见batch-63-C02-property-layer-acceptance-2026-10-25.md。

## 第六十二批C01查询门禁通过（2026-10-25）

- 原验收条件下新增空工程及同名页/跨页重复R1/R10原创夹具：计数/引脚/归属、逐条分页/精确筛选/字段投影、游标隔离和快照通过；两组各12次额外打开关闭通过。
- 活动query/cursor/snapshot/reopen遇到工作副本变更拒绝、陈旧关闭/关闭后拒绝通过；原快照/源hash不变。当前代码重验3原官方样例原断言通过。
- C01原4 issue均resolved，C01完整验收标passed；写入/层次连接原问题不随之结案。34项现1 passed/1 baseline_passed/20 partial/10 deferred/2 planned，整体仍active。无生产变更，167工具与411回归410通过/1原权限skip基线摘要核对保持。详见batch-62-C01-query-acceptance-2026-10-25.md。

## 第六十一批原生失败诊断（2026-10-25）

- 原生非收敛exit0的ERROR --形式原先漏解析、由DAT不完整拒绝；补双横线识别及明确分类。真实非收敛/缺模型/源环路3项MCP失败链通过，原历史记录保留。
- 新1工具检查stopped失败任务，实际167；真实超时不推断许可证、待执行取消不伪造worker、新服务观察/错误digest及2项旧原生测量失败只读检查通过。新10host，411完整回归410通过/1原权限skip。
- 原双横线诊断问题按复现结案；真实license失败未验收，P02/P03完整门禁不变。目标active，下一按原明确验收条件核对缺口与官方CLI/Capture遗留。详见batch-61-solver-diagnostics-2026-10-25.md。

## 第六十批原生MEASURE完整入口（2026-10-25）

- 官方完整入口PSpiceDoAnalysis在8例对照中生成独立测量文本，旧分步/DoALL不生成；原AC VM失败保留。新6工具、独立measure账本与严格原生value/at/from/to预期，实际166。
- DC/TRAN/AC真实MCP3正例、错误求值/错误预期/待执行取消、新服务幂等恢复通过；5项回执丢失/主动取消/超时/数值及终末篡改故障通过。旧分步瞬态541点RC与tau通过，10新host，401完整回归400通过/1原权限skip。
- 缺测量入口ISS-P03-native-measure-results按复现范围结案，P03整体仍partial。数字8调用DIN与缺失名同58零值，数字访问仍open并后移。34门禁不变、目标active。详见batch-60-native-measurements-2026-10-25.md。

## 第五十九批绑定DAT数值导出（2026-10-25）

- 新5个CSV/JSON plan/apply/jobs/cancel/recover工具，实际160；关闭原DAT会话仍可执行，来源/单位/范围声明冻结，新原生读回逐行及完整字节验证，数字状态仍明确拒绝。
- 4项真实MCP复数/混合模拟导出、新服务恢复与幂等通过；7项回执丢失、启动取消、超时、数值篡改及三个终末文件篡改案例通过。恢复不重建数值，可在验证后补建manifest。
- 新8 host，完整391回归390通过/1原权限skip，实际契约同步160。34门禁不变、P04仍deferred；数字访问、DAT10原失败、Capture连接/保存及完整联动待完。详见batch-59-dat-exports-2026-10-25.md。

## 第五十八批数字目录与混合模拟分区（2026-10-25）

- 原生单/双close对照确认数字reader重复close可3221226505；生产补失败close不重试。严格数字/混合行列、aliases和role目录接入，数字值/测量在numeric worker前拒绝。
- 官方数字7090行/212列MCP目录通过；原创新mixed58模拟行/5数字行，公开新求解的1V/5V/1mA、全行/测量、任务关联、错误预期和fresh恢复通过。native get DIN错误返回模拟网格58零向量，明确拒绝，不认证数字状态。
- 原双块复数与官方21块/瞬态兼容通过；新10tests，最终383完整回归382通过/1原权限skip，155契约同步。34门禁不变、P04仍deferred，新增数字值accessor open；下一可靠采样和单位导出。详见batch-58-digital-catalog-mixed-analog-2026-10-25.md。

## 第五十七批双块复数DAT兼容验收（2026-10-24）

- 原DAT10崩溃定位到第二块首addTimePoint；6生命周期与7格式/对象/header对照，仅官方支持DAT9完整通过原双块预期。原DAT10失败保留，未宣称修复。
- 新固定私有DAT9夹具两次全新生成，真实155工具MCP核对两块实部/非零虚部、交错分页、block/row/trace边界、关闭与副本篡改拒绝；原source/oracle hash保持。明确合成import，不冒充solver/job结果；Gain单位unknown。
- 生产与55批hash保持，373回归372通过/1原权限skip基线沿用，34门禁不变。P04/ISS-P04继续未完整通过，下一数字/混合与单位导出。详见batch-57-complex-dat-v9-acceptance-2026-10-24.md。

## 第五十六批3969集中诊断（2026-10-24）

- 故障定位为首次NextPage3969且非NULL，空新设计/既有导线对照code0；native消息文本为空。20个构造/初始化/Expand/根创建对照仍无完整拓扑通过，数据库版本字段一致。
- bNewVersion1虽消除3969但创建时page-owned wires=0、重开丢导线，严格拒绝；未吞状态、未改预期。初诊断GetId1002及catch字段问题保留并单列。
- 无生产逻辑/契约变更，155工具及373回归372通过/1原权限skip基线保持。34门禁不变，ISS-D03继续open；失败后移，下一独立PSpice新AC/非零复数DAT验收。详见batch-56-new-wire-3969-diagnostics-2026-10-24.md。

## 第五十五批位图资产与公共创建（2026-10-24）

- 创建专用bitmap声明绑定授权BMP路径、文件/DIB摘要、尺寸/长度，严格RGB24/RGB32/大小与完整图预算；计划前冻结副本、去重并复核。旧创建与编辑union兼容，像素替换未开放。
- RGB24/RGB32/旧声明3组及独立锚点创建、原图移除后执行、fresh恢复、冻结资产篡改/回执丢失/取消/timeout/未声明图形矩阵、像素单独改变反例、4次新建库Normal/Convert放置均通过。首alias测试失败与修复证据保留。
- 新7host，373完整回归372通过/1原权限skip，155真实工具契约同步。34项仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。详见batch-55-bitmap-assets-create-2026-10-24.md。

## 第五十四批既有位图几何修改（2026-10-24）

- 既有vector edit新增可选bitmapGeometry，严格bounds/location及expectedDibSha256；仅改位置边界，原dimensions/DIB长度/完整字节摘要保持。创建与像素替换仍未实现，旧basic-vector接口兼容。
- 两组移动缩放/独立锚点真实MCP编辑、错误图片预期拒绝、fresh恢复、完整故障矩阵、修改后Normal/Convert放置保存重开通过；来源和预期hash保持。
- 新5host，366完整回归365通过/1原权限skip；155契约同步。34门禁仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。详见batch-54-bitmap-geometry-2026-10-24.md；下一BMP资产声明与受控创建。

## 第五十三批受控位图worker与业务接入（2026-10-24）

- 固定安装Tcl同进程读取完整DIB摘要，严格HGLOBAL ABI/内存预算，不开放脚本或指针。公共query、完整图保留、bitmap删除、source/cache/实际view放置均接入；创建/几何更新/像素替换仍未实现。
- 三组bitmap/旧混合查询、两种编辑、两次Normal/Convert放置、双单元及第二组、像素单独变化反例、回执丢失/取消/timeout/篡改矩阵均通过；首次命名空间检查/准备缺声明失败保留。
- 361完整回归360通过/1原权限skip，实际工具仍155并同步契约。34项仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。详见batch-53-bitmap-worker-2026-10-24.md；下一bitmap受控创建与几何编辑，原遗留门禁保持。

## 第五十二批位图字节原型与3969复核（2026-10-24）

- 进程信号修正后的新6例保存顺序仍empty通过/5wire失败；私有诊断副本确认全为3969，源hash与生产读取器保持。原D03问题继续open后移。
- 私有bitmap工厂/新进程字段3组通过，实际BITMAP_VECT47；原生IsEquivalent忽略不同像素，不能作内容认证。初枚举错误、GetId1002及DIB ABI尝试失败保留。
- 固定同进程安装Tcl/GetDib/GlobalSize/GlobalLock原型已逐字节匹配两张BMP的独立DIB预期，错误图预期拒绝、移走源BMP后新进程仍读出并恢复/hash保持通过；尚未接入公共MCP。
- 公共仍155、基线354回归353通过/1权限skip，无生产变更不重复整套回归；34项仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。下一受控字节worker及bitmap全链路；详见batch-52-bitmap-bytes-save-recheck-2026-10-24.md。

## 第五十一批package属性及退出信号（2026-10-24）

- 实际155工具，新query+5个package编辑任务及open kind=package；模板/PCB名称、string用户属性创建/更新/空/删除/还原5步MCP、故障拒绝和两次编辑后放置通过。首footprint期望排序错误保留并修正。
- 原352目录清理错误复现，诊断Job0但根/子未signaled；等待所属进程句柄信号后，双盘各60次全部0目录释放失败/0未退出，三代/回调/句柄测试及真实Cadence/PSpice DC回归通过。已复现的ISS-P02-process-directory-release-152结案，完整P02未完。
- 两次354完整回归均353通过/1原权限skip，契约155。34项仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。下一原3969保存重开复核，再推进库缓存等剩余范围。详见batch-51-package-properties-exit-signals-2026-10-24.md。

## 第五十批既有库图形更新/删除（2026-10-24）

- 新5工具plan/apply/jobs/cancel/recover_library_vector_edit，open_edited_library kind=vector；实际149。9类基础vector完整同kind更新/删除，冻结源与before/expected图，全部已建模定义/模板/pin-start/vector顺序保留；原生所有预览引用上下文验证后去重写入。
- 最终18实际MCP用例、恢复/取消/timeout/未目标Convert篡改拒绝及终末hash保护通过；编辑后的OLB4次真实放置通过。双package首失败保留；新更新/删除两例各8view及4受影响scope通过。
- 新9host，最终342完整回归341通过/1原权限skip，contract149。首341目录释放WinError32/5及后续341绿色均保留；ISS-P02仍open，不宣称修复。图形任务账本独立128KB，旧任务上限不变。
- 34门禁仍1 baseline_passed/21 partial/10 deferred/2 planned，目标active。未建模属性/bitmap/嵌套图形/渲染、缓存/变体及原DRC/仿真等未完，下一库package属性/模板/封装名称编辑。详见batch-50-library-vector-edits-2026-10-24.md。

## 第四十九批公共库图形创建/查询（2026-10-24）

- 实际工具144，新增capture_query_library_vectors；创建声明接入9类基础vector，有序几何/样式/font保存重开全图比对，旧计划摘要兼容。混合/typed-line/legacy三组MCP创建查询及fresh lifecycle、两套故障矩阵、混合13vectors两视图放置通过。
- 默认枚举与中文多行文字通过；font quality2保存变1，严格验证拒绝。独立0..6对照定位保存重开统一为1，新quality1显式其他字段正例通过；原失败保留，ISS-L02-comment-font-quality-persistence open。
- 333完整回归332通过/1原权限skip，contract144同步。34门禁仍1 baseline_passed/21 partial/10 deferred/2 planned；目标active。下一既有库基础图形编辑。详见batch-49-public-library-vectors-2026-10-24.md。

## 恢复后的最终复测（2026-10-24）

- 全新执行325项回归：324通过、1原符号链接权限skip，无失败；实际stdio工具143，与正式契约逐字段一致。
- 全新私有输出复验fill/text Normal/Convert共4例：保存重开、错误hotspot预期拒绝、fresh恢复不重放、源DSN/OLB及冻结预期hash保持通过。batch48原证据与实现hash全部保持。
- 本次仅完成该批复测，不是全部业务最终验收；34项仍1 baseline_passed/21 implemented_partial/10 deferred/2 planned。间歇目录释放问题保持open，公共复杂vector创建/查询尚未接入。
- 机器记录：resume-final-verification-2026-10-24.json；无GUI、安装或真实设计修改，无提交推送。

## 本批可靠基线

- 155个实际MCP工具，契约同步真实stdio；最新383完整回归382通过/1原权限skip，见`.local/regression-383-mixed-dat-analog-20261024.txt`；前批两次354绿色证据保留。历史目录释放失败保留，本批对所复现时序补齐退出信号并用双盘120次修复后对照验收，详见batch51。
以下早期基线条目保留历史限制，不能当作当前完整能力表；后续实现状态以最新批次和cadence-acceptance.json为准。

## 早期基线记录

- 第三批对象读取、metadata生命周期、显示布局、已验证输出继续编辑链通过；49工具原生链在`.local/objects-display-stdio-20261023/objects-metadata-report.json`；OUT新增后50工具真实stdio在`.local/out-reader-20261023-b/report.json`。详细范围/未通过项见batch-03-objects-metadata-output-2026-10-23.md。
- Capture定义、属性层、姿态/热点、OLB查询、批准Value/PCB Footprint编辑及CIR引用准备已有切片；不代表完整C01/C02/C03/L01/E01/P01通过。C01未绑定引脚读取问题已修复，整体仍partial；C03矩阵仍deferred。
- C04 connections(wire/alias/global/port/offpage/nc)与C05 graphics(part_bounds/display_property/graphic/titleblock)已注册，session-bound分页。FULLADD/BCD非空对象已读；global/offpage/NC正向fixture未验收。Native cached display bounds坐标/有效性未验证，不可当避让结论。
- E02 user metadata set/empty/delete、display property location/rotation/type及source unchanged/save/reopen通过；真实继承回退正例、字体和完整显示生命周期待完成。capture_open_edit_result只打开verified输出、核对artifact hash，固定kind映射，不允许任意读根扩张。
- P03新增导入OUT诊断与bias voltage读取；2官方历史OUT解析通过，jobAssociationVerified/solverSuccessVerified均false。测量、波形/容差及新求解关联仍未实现。pspice.run仍unavailable。
- P04现有4个MCP工具pspice_dat_open/query/samples/close，固定orPIOData64读取器，headers全块数组按Number校验，canonical/alias精确定位，实数/成对复数解码和分页，源/副本不可变hash，文件close+owned进程退出确认。数字/混合采样未开放；单位为明确name convention或unknown，未声称native unit。
- `.local/dat-stdio-real-complex-20261023/report.json`真实54工具stdio12案例通过：官方RFAMP21块/99trace/61行，0/10/20块Frequency/V(IN)/V(0)符合独立数学预期；官方EXAMPLE59点Time及±12V/0.1sin(2π5MHz t)实数源预期通过。缺trace、close后session和故意更改副本被拒。7项针对性主机测试通过。batch-04-dat-2026-10-23.md有范围/命令/证据。
- DAT完整P04仍deferred：原创新2block非零复数fixture create=1后native访问违规3221225477，具体方法未定位。`.local/dat-complex-1fb7500a1b/{expected.json,fixture.log,process.json}`，issue ISS-P04-complex-fixture-native-crash移队尾。现有复数正例虚部为0；非零虚部独立oracle、自建多块及新求解关联必须补，不能计已完成。


## 第四十八批基础复杂vector多视图身份（2026-10-24）

- 多view校验扩展box/ellipse/arc/polygon/polyline/bezier/fill/comment-text，比较边界/点序/style/fill/hatch/文字14font字段，保留混合native draw order；纯line旧签名兼容，unknown bitmap/symbol-vector拒绝。增加sourceVectorGeometryVerified和准确vector/line计数；未扩大single-view旧路径的认证范围。
- 原生7类首轮通过；文字先getter输出参数错误、再bounds/anchor矛盾两失败保留，新独立一致声明v3全部字段通过。3组16真实MCP Normal/Convert通过及错误hotspot拒绝/fresh不重放；纯ellipse/font篡改在pin/net检查通过后视图检查拒绝；旋转text回执丢失fresh verify-only/hash保持/取消/timeout owned0通过，旧line2例兼容通过。
- 325完整回归324通过/1原权限skip，工具仍143/contract同步。公共复杂vector创建/读取、完整图形属性、原缓存/变体/D02/flat/DRC/仿真等未完，34范围保持，目标active。详见batch-48-basic-vector-identity-2026-10-24.md，无GUI/安装或真实设计修改/提交推送。

## 第四十七批已有缓存缺失unit补放（2026-10-24）

- 1个新plan_cached_unit_add复用multiunit apply/jobs/cancel/recover/open，实际143。绑定owner native identity及revision cachePartId，同封装/原base补缺失device，继承一致Value/FP，不引入OLB/新cache/wire；拒绝U?/重复device/fullref/外来cache/组冲突。完整pinId与新pin/hotspot/net oracle，保存后实际cached view名、cache逻辑元数据、原实例identity/geometry/属性及native page网络验证。
- 原生两例B.Convert/P.Normal通过；MCP首误选同名A视图被正确拒绝，修正device scope后v2两例通过。错误热点保存后拒绝/open拒绝/不重放、缺pin/外来cache/已放device、pendingcancel/fresh lifecycle通过。回执丢失fresh MCP verify-only/nativeCompletionVerified=false/hash保持、启动cancel/受控timeout owned0通过。
- 7host新增，325完整回归324通过/1原权限skip；143真实工具契约同步。跨页/非默认覆盖矩阵/完整图形/复杂导入/变体等未完，D02原接线移动失败保持deferred，34范围未缩减，目标active。详见batch-47-cached-unit-add-2026-10-24.md，无GUI/安装或真实设计修改/提交推送。

## 第四十六批单unit姿态/删除与共享NC保护（2026-10-24）

- 既有part_edit新增expectedUnitConnections/pinId分支，nativeId/fullref/device/cache/old pose绑定单unit；保存后全定义/连接对象、剩余全设计unit身份、同页geometry/Value/FP、cache逻辑pin元数据和native page nets验证。5正例移动/旋转/镜像/删除通过，wrong hotspot保存后拒绝；接线A移动unit8/VCC变unbound未通过，原report false、ledger/hash/oracle保持，D02deferred后移。
- 首故障harness相对路径失败保留，v2回执丢失fresh MCP verify-only/nativeCompletionVerified=false/hash保持、启动cancel/延迟timeout owned0通过。共享NC reader显式ALL/shared1；原生私有共享8 NC/fresh MCP读取owner及hotspot正确，带NC delete建计划前拒绝。
- 最新targeted3在最终guards后实际通过；318完整回归317通过/1原权限skip。Part edit记录256KB，NC/net-symbol-create子类原64KB保持。工具142、contracts同步，未增加工具族。审批额度导致的未启动已在用户继续后实际复测，不伪作执行。原34范围/其他失败保持，目标active。详见batch-46-unit-edit-2026-10-24.md；无GUI/安装或真实设计修改/提交推送。

## 第四十五批完整多单元组持久写入（2026-10-24）

- 新5工具plan/apply/jobs/cancel/recover与open kind=multiunit_placement，实际142。完整2..16 source devices一次放置同base reference/新cache，现有pinId逐条覆盖；共享physical pad矛盾bindings拒绝。完整定义/连接对象、各单元ownership/physical pins/nets/pose/hotspots、Value/footprint、源pin/line视图与原页nativeId geometry保存后独立验证；原生页net对象同组/隔离检查。
- 3真实MCP主用例同构/异构/接线通过，同页第二共享位号组通过；wrong hotspot保存后拒绝/open拒绝/不重放、pendingcancel/fresh lifecycle通过。回执丢失fresh verify-only/nativeCompletionVerified=false/hash保持、启动cancel/timeout owned0通过。6项preflight拒绝0durable plans；终末第二组先备份再tamper，open/recover/apply拒绝，前三输出/原报告/备份完整。
- group账本256KB有界，其他任务64KB不变；10host新增，完整310回归309通过/1原权限skip。首直接页定位3969、原307工具数断言失败记录保留；不关闭其他3969或目录释放issue。原34范围未缩减，增量unit/跨页/非line/变体/flat/DRC/仿真等仍未完，目标active。详见batch-45-multiunit-placement-2026-10-24.md，无GUI/安装或真实设计修改/提交推送。

## 第四十四批公共替代视图放置（2026-10-24）

- 既有placement支持来源绑定多part Normal/Convert：源名/缓存前缀名+pin/line形状，或唯一完整pin/line signature；不按顺序选。多视图保存后新进程核对PlacedInst.GetPart与源、私有OLB/输出hash；sourcePinLineViewVerified标识。非line vector拒绝，其他图形属性未认证，单视图原行为保留。
- 最终v3四canonical/arbitrary Normal/Convert真实MCP通过；额外同pin仅line4/5不同两视图通过，独立保存后计数4/5。错误hotspot保存后拒绝/open拒绝/不重放，fresh apply/recover/open通过。回执丢失fresh verify-only/nativeCompletionVerified=false/hash保持、启动cancel/timeout owned0通过。
- 完整300回归299通过/1原权限skip，contracts实际137同步。首1022正常迭代结束误判失败保留，固定处理其他错误不忽略。原34范围保持，package-aware共享reference持久写入等仍未完，目标active。详见batch-44-alternate-placement-2026-10-24.md，无GUI/安装或真实设计修改/提交推送。

## 第四十三批显式异构电源网络与故障反例（2026-10-24）

- 固定fixture支持wireAliases，独立冻结全定义/连接对象/单位身份/热点/原页geometry；新A/B/P显式VCC三引线+trunk和独立GND原生网络通过，两个非空组互异。短接/断开反例保存后definition和native-object检查均拒绝，完整性及oracle hash保持，owned0。
- 真实137工具MCP3units/8pins/6physical numbers/3VCC与全部net/connected/hotspots通过。首脚本错误null空网假设失败保留，修正为已有empty-string契约后v2通过。未改旧failed oracle/ledger。
- 原34范围及整体partial/deferred不变，隐藏/flat/occurrence、通用cache/view及公共组写入未完。没有公开业务Python/schema变更，最新完整回归沿用300/299/1。详见batch-43-multiunit-power-2026-10-24.md。目标active，无GUI/安装或真实设计修改/提交推送。

## 第四十二批多单元命名/电源可见性对照（2026-10-24）

- 4份新OLB完整图通过；package前缀cell/cell前缀part构造复制不再1025，缓存Normal/Convert保持，异构A/B/P未连线集成通过。仅是当前命名构造的证据，任意用户库导入/全图来源认证仍未实现；未静默收紧公开创建契约。
- 可见同构共享VCC接线全检查通过；隐藏两类接线仍失败。可见异构VCC同一原生net通过，但未连线GND意外出现原生连接，与冻结预期不符，整体false。未修改旧预期，下一新增显式分离VCC/GND线路。
- 真实137工具MCP异构3units/8pins/6physical numbers/3shared VCC与全冻结热点通过；原hash保持。无新生产变更，全回归沿用batch41。L03/D01/D04完整scope未完，目标active。详见batch-42-multiunit-naming-2026-10-24.md，无GUI/安装或真实设计修改/提交推送。

## 第四十一批共享脚读取与多单元DSN集成（2026-10-24）

- 四个只读adapter显式NewPinsIter/IterDefs_ALL/bReturnShared=1，修复共享脚遗漏。真实137工具MCP六pin/五physical numbers/两VCC8及冻结热点通过；初错误tool name失败保留。完整300回归299通过/1原权限skip，历史目录释放issue仍open。
- 新副本同构U501A/B未连线实例集成通过定义/连接对象/身份/各单元热点；接线VCC原生网络验证失败，异构A/B/P CopyPackageAll1025两例失败，原报告及旧失败全部保留。内部pin-signature候选选择不含装饰图形，不发布通用多单元写接口。
- 官方隐藏电源脚可见性规则需进一步原生验证；page-definition不能替代flat/global。原34范围和整体partial/deferred不变，目标active。详见batch-41-shared-pin-reads-2026-10-24.md及batch-41-evidence.json。无GUI/安装或真实设计修改/提交推送。

## 第四十批同cell替代符号视图与持久创建（2026-10-24）

- 先独立fixture复用cell并创建distinct partName Normal/Convert，3类全新OLB按冻结expected图保存/新进程读取全部通过：single1unit/2part rows/4pin views/2pads；shared_dual2units/4part rows/12pin views/5pads；hetero A/B/P3units/5part rows/14pin views/6pads。视图翻转x坐标，逻辑position/name/type与physical mapping保持，footprint仅每package一个声明值，不认证外部封装。
- 接入既有LibraryCreates，无新增工具族。symbols允许重复exact cellName与distinct partName；cell大小写别名、重复partName、不一致position/name/pinType拒绝。cell只创建一次、part对象分别定位，不用cellName字典覆盖早先图形；完整expected/actual图按device+cell+part scope保留每view geometry/visibility/physical map，package.size按真实devices计，physical pad按number去重。旧单view期望保持兼容，不降低保存后完整digest门禁。
- 实际137工具MCP3类创建/open/query/fresh idempotent apply/recover/open通过；不兼容view preflight拒绝；错误homogeneous oracle实际saved后library_creation_mismatch/open拒绝/不重放通过。末hetero MCP成功产物仅在最后故意篡改并保持拒绝，前三native产物和前两MCP输出完整。独立异构多view receipt-loss fresh verify-only恢复/nativeCompletionVerified=false/hash保持/open、启动cancel、1s timeout及owned0全部通过。
- 新3host测试，完整300项299通过/1原symlink权限skip；contracts同步真实tool说明，工具仍137。L02/L03仍partial，footprint variants、DSN unit/package实例集成及其他原门禁未完；历史目录占用及GUI/simmgr待授权保持，目标active。下一实例集成。无新GUI动作/安装或真实设计修改/提交推送。

## 第三十九批多单元共享脚/正交换组与本机范围修复（2026-10-24）

- 在等待simmgr桌面访问期间推进独立OLB验收。真实137工具MCP同构A/B：稀疏逻辑position0/3/7/12、8logical rows/7physical pads、hidden shared VCC8、swapId7/11保存重开完整声明图通过。原异构A/B/P101/202在create_physical_mapping失败1110，保留原report整体false及failed ledger，不改旧期望/重放。
- 独立简单库原生范围校准：-1/0/31/32/63/64/99/100/101及追加125/126共11个值经保存/新进程完整图验证；127/128/202/4095共4值NewPinNumber1110失败，owned0。收紧library_create.validate_spec及公开PinMapping.swapId schema上限4095→126（仅本机24.1写范围，逻辑position上限不变）；普通读取不删除旧库元数据。新增范围host测试和actual contract同步，原native失败仍是失败。
- 独立completion保持原失败report hash，复用已成功同构job做fresh apply/recover/open不重放；新异构合法101/102：A/B/P12logical/8physical，hidden gate VCC/GND与visible power unit共用8/7，完整symbol geometry/device physical mapping/swap metadata新进程及MCP通过，fresh再次apply/recover/open无重放。127/202/4095 schema拒绝、范围内共享脚swap冲突拒绝通过。不是实际物理pin交换/多单元DSN放置认证。
- 完整297项296通过/1原symlink权限skip，工具仍137；目录句柄历史issue保持open。L03仍partial，alternate part/footprint variants及DSN unit/package集成未完成。原34完整scope、Capture/simmgr待访问和所有其他失败保持，目标active，无GUI新动作/安装或真实设计修改/提交推送。下一变体/实例集成。

## 第三十八批保存顺序对照与真实桌面宿主诊断（2026-10-24）

- 官方CreateDesign/SavePage/SaveSchematic/SaveDesign/SaveAs构造6个独立新DSN，预先声明ROOT/MAIN与单wire(100,100)→(300,100)。empty控制通过定义/对象新进程读取；direct、initial_design、initial_page、save_as、no_page_save五种wire用例全部读取失败，保存receipt成功/owned0/hash保持。不能宣称调整保存顺序解决持久化问题；原失败保持，仍需排查初始wire存储/上下文。
- 更新后的computer-use技能及桌面工具可用，通过@oai/sky实际launch_app启动Capture20696，观察Ready Start Page，未见启动modal；不据此重写此前hidden owned CLI启动失败原因。桌面Open文件框索引不可用且literal typing未填入，已Escape取消，没有误开真实工程。
- 固定PID-bound CLI inventory转发到现有20696成功，原runtime.json真实产出；helper结束自己创建的secondary forwarder而非20696。原report字段unacknowledgedLauncherTerminated命名欠准确（inventoryAvailable=true已确认回执），不把它误解成已观察Capture被终止。
- 仅准备官方LOWPASSFILTERS.DSN/OPJ/AC.sim私有副本，不复制旧NET/CIR/DAT/OUT。官方Open私有OPJ后实际观察Read Only及独立simmgr.exe Simulation Manager Product Choices默认PSpice A/D。通过Capture窗口点击被正确拒绝为非目标进程，未执行；取得真实simmgr窗口985800后get_window_state报Computer Use app approval timed out。没有绕过访问审批，没有选择产品/改变default，没有private project认证bridge或网表验收。Capture及产品窗口当前留在此状态待应用访问授权/用户确认产品；私有DSN hash保持，安装源/真实工程未修改。
- 本批无公开生产Python/schema变化，工具仍137，未重复全回归；最新296项295通过/1原symlink skip及原目录句柄issue不变。原34完整门禁及所有失败保留，目标active。下一独立多单元验收，宿主在simmgr访问可用后续接。桌面观察摘要为observation.json，非native接受凭据；未提交推送。

## 第三十七批宿主启动、页加载对照与名称大小写冲突修复（2026-10-24）

- 无运行中的Capture，旧PID绑定不能复用。因独立网表明确ORNET1165，按已授权例外启动一次受控Capture，使用官方CLI脚本形式、首条即写PID回执，不开设计或调用业务；45s超时、boot/inventory均未出现、owned0。此次确实启动Capture应用但无桌面点击；不猜许可证/模态/具体启动原因，V03/V04既有issue附证据。
- 官方p343 ReadAllPages/p354 Expand对冻结cross-page和copied-port DSN做内存初始化对照。4case均失败；Expand两个分支在前置ReadAllPages就3969，Expand本身未执行，不能声称Expand无效。两份DSN hash保持、owned0，旧报告不改，不忽略状态；继续后移。
- 官方Assigning_Net_Aliases明确连接名称忽略大小写；发现公开net-symbol rename preflight仅exact比较。新增symbol_name_conflicts统一casefold已知wire/alias/global/offpage/port名称，排除目标自身和声明wire；不改保存/回读或跨页认证范围。真实137工具MCP对mcp_middle/McP_MiDdLe/MCP_MIDDLE都在create_plan前以net_symbol_merge_unsupported拒绝，0durable plans、输入/副本hash保持。
- 新2host测试覆盖5类名称冲突及自身wire不误拒；完整296项295通过/1原symlink权限skip。公开工具/schema仍137，历史间歇目录占用issue不因绿色关闭。原34完整门禁、所有native失败保留，目标active。下一新建设计保存顺序专项及多单元剩余验收；无安装/真实工程修改/提交推送。

## 第三十六批Capture→PSpice原生网表生成路径（2026-10-24）

- 本机官方Capture Tcl包createPSpiceNetList有仅puts/常量返回的占位实现，不能算生成路径。实际orPspNetlist64和orTclNetlist64均可独立load；修正递归namespace baseline后真实delta205/10命令（非MCP工具数）。初盘点混入既有namespaced Tcl命令的原报告保留；固定100错误参数只获取C binding拒绝信息，不执行有效网表调用；DLL内运行时类型签名核实OrTclNetlist_sCreatePSpiceNetList为9参数design/output/6bool/license。
- 私有官方LOWPASSFILTERS.DSN真实调用：缺输入负例也return0但无输出；有效副本return0/NET出现却0bytes。独立legacy/log-vector诊断报告ORNET-1165 Unable to initialize pspice explorer；2参数最小重载被拒绝，不忽略。没有新可用NET/CIR，没有用安装中的历史NET替代。
- COM线程初始化假说做独立嵌入同一已安装Tcl的none/STA/MTA对照，三者相同ORNET1165/空NET，不能视为修复或猜许可证。首宿主误用tcl86t.dll导致启动失败的3case保留，改实际tcl86.dll后新目录重新诊断；未冒充有效业务验收。私有副本/安装源hash保持，所有自有进程0。V04新增open issue并deferred，原完整scope仍在。
- 本批仅内部诊断/证据/文档，无公开生产Python/schema变化，仍137工具，未重复全回归；最新294项293通过/1原symlink权限skip及历史目录句柄问题不变。目标active，34项未缩减；下一核对现有authenticated bridge的owned Capture/PSpice host上下文，必要时按已授权例外验证宿主而非桌面点击。无GUI/安装或真实工程修改/提交推送。

## 第三十五批跨页原生网络与官方PortSymbol对照（2026-10-24）

- 按本机Placing_Off-Page_Connectors及Assigning_Net_Aliases官方规则预先声明TOP/PAGE_A+PAGE_B八wire：同名offpage/忽略大小写offpage/同名global各共享一flat组，异名offpage分两组，总5组。全新fixture完整保存，但root直接wire→GetSchematicNet为空，plain与官方UpdateNetAndPorts内存初始化均失败；页对象绑定读取另报3969。未完成任何跨页连接接受，不按名称推断。
- 独立端口初始化替代：私有capsym PORTLEFT-L type34→CopySymbol→typed getter→两个NewPort/SetPinType→CHILD wire/parent BLOCK_A与implementation/边界pin→完整save，原进程exit0/owned0且tree reader成功。此路径越过原空NewPortSymbol崩溃阶段，但完整definition/objects/bindings失败，热点/方向/子图连接未接受，原H03 issue保持open；不把已保存或tree通过当全功能成功。
- 分阶段只读trace将两份新graph的3969均定位NextPage。各做一次官方GetRootSchematic预初始化对照仍失败；不忽略状态、不改旧期望/报告、不重放。与历史H04同症状，尚未证明同根因。H02/H04/H03既有issue附新证据，失败项继续后移。
- 所有6reports整体false，新增integrity审计确认两份DSN当前hash=保存hash，source OLB/private copy保持，所有自有进程0；仅完整性成功，不提升失败。没有新增公开工具/Python生产行为/schema，仍137工具，未无修改重复全回归；最新294项293通过/1原symlink skip，目录句柄issue保持。目标active，原34完整门禁不变，无GUI/安装或真实工程修改/提交推送。下一独立V04官方仿真输入生成路径调查，后续集中修复fresh-page读取/网络初始化及端口完整验收。

## 第三十四批符号改名/删除持久MCP任务（2026-10-24）

- 新CaptureNetSymbolEdits及name/delete-only固定adapter，5工具plan/apply/jobs/cancel/recover与open kind=net_symbol_edit，实际137。绑定immutable source、qualified page/native ID/old name/origin/hotspot/pose与caller指定wire；原生symbol/wire同组且hotspot在wire上才接受。bus/port/pose/冲突名/noop/非法字段拒绝；仅scalar attached page scope。完整save/reopen核对definition结构/连接对象、所有所选页part pose/hotspot、原生pin-wire分区及非目标名；改名后独立检查symbol-wire同组。删除允许目标auto net name或显式expectedWireNet；不改wire成员关系。
- 初MCP harness entity=all错误在修改前被schema拒绝，保留report。v2四个真实写任务均verified，但第二种kind误复用wrong幂等键，正确拒绝后harness断言失败，整体report仍false。独立completion使用四个既有job进行fresh apply/recover/open/hash不变/不重放，另建offpage错误oracle及pendingcancel，用唯一键补齐；最后仅offpage-delete输出故意篡改并确认open拒绝。completion passed，不改旧report/ledger，不重做四次写入。原source与前三输出完整。
- receipt loss在native保存完成后受控删回执→fresh verify-only recovered/nativeCompletionVerified=false/hash保持/open、启动cancel和真实1s timeout自有0/不重放全部通过。faults报告passed；历史间歇目录句柄issue仍open。
- 新3host测试，完整294项293通过/1原symlink权限skip，contracts同步实际137stdio。上批3姿态issue及原34完整范围保留，D04仍partial，目标active。下一跨页原生语义/官方port-symbol来源fixture；无GUI/安装或真实设计修改/提交推送。

## 第三十三批global/offpage生命周期原生验收（2026-10-24）

- 新内部固定edit_net_symbol.tcl及Disconnect对照adapter、原生probe和只读完整性audit；未增加公开MCP工具，仍132。依据本机官方p463/572/576–578，绑定qualified page/native ID/old name/origin/hotspot/pose，先释放iterator再修改，完整save链后新进程读取。
- 初验收脚本work root配置使10例在原生修改前被路径guard拒绝，失败report保留。修正harness后全新v2副本10例：global/offpage改名及删除共4通过；全definition结构、精确连接对象、页内全部part pose/hotspot及native pin-wire分区保持。删除允许目标native group自动命名但不允许成员关系变化，非目标名称保持。无跨页/flat/occurrence/DRC认证，无持久公开edit task验收。
- global移动坐标/热点正确但保存重开仍绑定原wire/pin网络，不能按坐标判断线；rotation/mirror热点模型未通过。offpage3姿态用例mutate_symbol返回DboState1未保存，具体setter未定位。新增3个issue open后移。独立Disconnect→move两例仍失败，返回1不代表电气验收通过；不重放旧ledger/改旧期望。
- `.local/net-symbol-edits-v2-20261024/report.json`原生4/10通过、整体false；`.local/net-symbol-disconnect-20261024/report.json`0/2通过。只读integrity-audit验证12例source hash、已保存产物hash、未保存副本字节保持、自有进程0及原失败report未变；完整性通过不提升原失败。旧harness进程exit0不代表report passed；脚本已增加最终非通过exit1和adapter hash供以后运行，未声称旧运行具有新字段。
- 本批仅内部诊断及文档/矩阵，无现有公开production Python/schema变化，不重复无修改全回归；最新基线仍291项290通过/1原symlink权限skip，历史目录句柄问题保持open。D04 partial，原34范围不缩减，目标active。下一独立改名/删除持久MCP集成及跨页fixture，姿态失败后移。无GUI/安装或真实设计修改/提交推送。

## 第三十二批来源绑定net-symbol创建任务（2026-10-24 checkpoint）

- 新5工具plan/apply/jobs/cancel/recover与open kind=net_symbol_create，actual132。绑定DSN/OLB双snapshot hash、symbol ID/name/type、qualified page、独立origin/hotspot和全page pin oracle。可选正交lead只接明确unbound internal single-unit pin；端口kind另属H03，拒绝替用。完整save/reopen核对definition/连接对象/页内geometry及有lead时symbol/wire/pin同非空native net对象。scope仍page_definition，非cross-page/flat-global/DRC。
- 初40char cacheName使CopySymbol1099，原MCP及receipt-loss失败保留。独立24/31成功、32/40失败，确认本机31边界；改24char随机名+冲突guard与31char preflight。新任务验收不改旧payload/ledger、不重放。
- `.local/net-symbol-create-mcp-v2-20261023/report.json`真实132工具4source/pose/name/lead用例、错误origin oracle拒绝、schema/输入guard、pendingcancel/jobs/fresh idempotency/recover/open/tamper拒绝通过。仅末offpage产物故意篡改，前三及原输入完整。faults-v2真实receipt loss只核验恢复/nativeCompletionVerified=false/hash保持/open、startcancel及1s timeout owned0/不重放通过。
- 4host新增，完整291项290通过/1原symlink权限skip；历史目录句柄问题保持open。D04 partial，symbol edit/delete/cross-page及原34完整范围仍未完，H03端口崩溃等保留。目标active，无GUI/安装或真实工程修改/提交推送；下一global/offpage独立编辑删除和cross-page fixture。

## 第三十一批官方net-symbol来源、短引线连接与公开查询

- 本机capsym原始/复制hash dbfe...保持，仅Cadence打开私有OLB。40 symbols中21个net symbols：11global/8port/2offpage，实际native type33/34/35。新增capture_query_net_symbols按library session/revision绑定kind/name metadata与分页，actual127工具；geometry/hotspot/embedding/electrical不认证。
- 内部fixed CopySymbol+typed getter→NewGlobal/NewOffPageConnector保存重开4例成功但初次仅原点定位，不是连接验收。热点对齐引脚的4例仍unbound，原失败保留；不能用坐标重合认定连通。
- 显式新增(240,310)→(290,310)短导线后，VCC/offpage、GND与offpage的rotation1/mirror1共4例全definition pin-net/对象oracle通过。独立同进程GetNet分组8正反例证明symbol/lead/pin同非空native对象及coincident无pin连接，非按同名推断；不证明跨页/global flat语义。`.local/net-symbol-wire-lead-20261023/report.json`及`net-symbol-native-bindings-20261023/report.json`通过。
- 4例实际126-tool MCP读取/pose/hotspot/明确四pin预期通过；新增查询后127-tool metadata21项/游标kind-limit-session绑定/严格输入/关闭/篡改拒绝通过。仅第二私有OLB副本故意篡改，其他source/保存设计完整。全287回归286通过/1原symlink权限skip，历史issue保持。D04仍partial，无公开net-symbol写任务；原34范围不变、目标active。下一source-bound创建任务。无GUI/安装或真实工程修改/提交推送。

## 第三十批独立scalar alias任务与原生页网络分组

- CaptureAliasEdits/固定JSON adapter公开5工具plan/apply/jobs/cancel/recover及open kind=alias，实际126。支持同wire scalar alias改名/锚点移动/删除；指纹/qualified page/native wire ID/path/old name/anchor绑定，拒绝off-wire/noop/bus/歧义及已检测的直接跨网名称合并。
- 原生删除唯一alias后网络仍连通但自动改名N02664；不固定未来编号。新只读reader按GetNet对象分组pins+wires（非按名字），page scoped。GetName1037定位留证，按官方p730改GetNetName后3原生保存产物的分区/结构/连接对象不变量通过：`.local/alias-partition-accept-v3-20261023/report.json`。原失败及配置不全的直接诊断不混为根因。
- 真实126工具stdio rename/move/delete、output open、错误owner oracle native saved仍拒绝/no replay、pending cancel/jobs、fresh recover/idempotent/tamper拒绝通过：`.local/alias-edits-mcp-20261023/report.json`。末尾delete产物故意篡改，rename/move/source完整。`.local/alias-faults-20261023/report.json`真实receipt loss只核验恢复/nativeCompletionVerified=false/hash保持/open、startcancel/1s timeout owned0/不重放通过。
- 8host新测，完整284项283通过/1原symlink权限skip，历史目录句柄问题仍open。scope仅保持page definition native memberships，非H02/跨页global/occurrence/DRC认证；D04仍partial，原34项不变、目标active。无GUI/安装或真实工程修改/提交推送；下一global/offpage生命周期。

## 第二十九批持久NC增删任务

- 新CaptureNcEdits/JSON固定adapter公开5工具plan/apply/jobs/cancel/recover，open_edit_result kind=nc，实际121。scope=single_unit_unbound_scalar_pin；绑定session pin/native part/qualified page/ref/physical number/name/hotspot/oldflag/source fingerprint，拒绝connected/多unit/external/缺失或重复脚号/noop/extra/非bool。native标量type16仅本机24.1实测guard，不泛称跨版本。
- 新输出save/reopen核对完整definition pin-net、全部连接语义含NC目标热点、所选页所有器件pose/hotspot；其他scope/属性/render/DRC未声称。R101.1(290,310)与自建库R401.1/A(680,300)两真实121工具stdio增→重开→删链、pending cancel/jobs、fresh不重放/recover/open/tamper拒绝通过。两final remove产物末尾故意篡改，保持拒绝；两source/add产物完整。
- `.local/nc-faults-20261023/report.json`真实保存后receipt loss→fresh只核验恢复/nativeCompletionVerified=false/hash保持/open，startcancel及1s timeout/owned0/不重放通过。历史process-directory占用issue仍open，不代表所有故障窗口通过。
- 4host新增测试，完整276回归275通过/1原symlink权限skip；D04仍partial，原34项完整范围及H03端口崩溃不变，目标active。无GUI/安装或真实工程修改/提交推送；下一独立alias edit/delete。

## 第二十八批新建层次端口失败与NC专项

- 新建TOP/CHILD及真实PortSymbol的fixture在create_child_ports阶段native3221225477，owned0，无保存DSN。V1/V2及逐阶段日志保留；该阶段含多个NewPort/SetPinType，具体方法及symbol初始化根因未证实。新ISS-H03-fresh-port-native-crash open后移，不开放接口。
- 独立D04 NC固定fixture4原生用例通过：R101.1 unbound添加/另副本删除，R101.2 connected与错误oldflag在修改前拒绝/字节保持。独立重开全definition pin-net与其他连接语义保持，NC目标/脚号/热点(290,310)准确。`.local/nc-lifecycle-20261023/report.json`通过。
- `.local/nc-read-mcp-v2-20261023/report.json`真实116工具stdio add/remove两例查询NC与明确四pin连接预期、schema/非法limit/关闭拒绝通过；初版漏expectedRevision仅harness失败，原记录保留。源及两输出完整未篡改。尚无NC公开write task，D04/C04/H03仍partial。
- 本批仅内部fixture/scripts与证据，未改公开production业务实现；未重复完整回归，最新仍batch27的272项271通过/1原权限skip。历史问题均保留，完整34项不变，目标active；无GUI/安装或真实工程修改/提交推送。下一D04 NC任务集成。

## 第二十七批持久层次复用MCP

- 实际116工具，新增hierarchy clone plan/apply/jobs/cancel/recover及verified output opening。仅顶层内部同页块复用；原source hash/native ID/qualified page/内部实现及caller完整热点绑定，保存后核对definition/原连接/页内geometry/tree与原occurrence属性/native flat分区及隔离。
- C(2000,2000)、D(1800,1600)真实stdio、fresh server不重放、pendingcancel/jobs/recover/open/tamper拒绝通过。两MCP产物末尾故意篡改并保持拒绝。receipt loss只核验恢复/nativeCompletionVerified=false、启动cancel和1s timeout/owned0通过。错误热点native saved仍被verify/fresh apply/open/recover拒绝，不改期望或重放。
- 证据与完整范围见batch-27-hierarchy-write-2026-10-23.md。272回归271通过/1原symlink权限skip，历史目录句柄问题仍open。H03仍partial，fresh block/child/port CRUD及原矩阵未完，H02原NULL schematic net仍deferred。目标active，无GUI/安装或真实工程修改/提交推送。

## 第二十六批层次复用块与原生网络隔离

- 内部固定probe用官方NewDrawnInst(source,state)复制halfadd_A为halfadd_C到(2000,2000)，复用内部HALFADD定义；释放iterator后修改并完整保存。定义/pin-net及原连接语义保持，新四个边界pin未连接、位姿热点预期通过；新进程23occurrence=16+新块+6child。`.local/hierarchy-clone-20261023/report.json`通过，源与保存产物完整。
- 原生flat对象分区验证28新child pins复制原A内部关系，private对象与原域隔离，仅VCC/GND global共享；原域分区/名称/global metadata保持。V1错误声明30pin，按2×4+4×5=28修正只读重验，原失败保留。typed边界显式转换GetIsGlobal整数0/1，其他整数拒绝；原strict bool失败stdout另存。V2原生+typed audit通过，不修改或重放设计。H02原NULL schematic net问题未修复，仍deferred。
- 真实111工具stdio对生成设计23node树/单位身份/分页/重开/cursor/关闭/篡改拒绝通过：`.local/hierarchy-clone-mcp-20261023/report.json`。仅其query副本故意篡改，原clone完整。这不是public write验收。
- 6项新host分区测试；完整269回归268通过/1原symlink权限skip。H03由planned→implemented_partial，仅内部fixture，未开放通用层次写；新建子图/端口CRUD/方向错配/闭包/循环/无关属性几何/持久写故障及原完整矩阵均未完成。目标active，34项不缩减；无GUI/安装或真实工程修改/提交推送。下一H03通用写集成或失败后D04。

## 第二十五批缓存真实枚举与替换保留专项

- inspect_cache原先只NewPackagesIter，漏原生cached packages。现按官方cache iterator/casts枚举cached+local package objects，保留同名不同对象；source-qualified identity仍false。4原生只读fixture及真实111工具stdio分页/重命名pin/TTL/错误/关闭检查通过，源hash保持。见`.local/cache-enumeration-v3-20261023/report.json`、`.local/cache-enumeration-mcp-20261023/report.json`。原早期cache-query证据仅local slice，不代表完整cache覆盖。
- 原生ReplaceCache以package名成功，sourcePart名1021；preserveRefDes1仍使R101/R102都R?，独立footprint/value覆盖也被重置。显式native-ID ref+两项effective值恢复后，两种updateflag的已连接两电阻definition/pin-net/geometry/hotspot/全部effective属性及原连接语义通过。V5旧报告仍failed；单独只读combined audit链接冻结期望、哈希、新reader，证明property顺序及alias native ID变化不是语义变化，不改旧报告或设计、不重放：`.local/cache-replace-v5-20261023/combined-audit.json`。
- 此为内部probe，未开放cache写工具；L05仍partial。继承来源、source-qualified identity、多单元/occurrence/无关几何属性、closure、持久计划/故障未完。新native-preserve issue open后移；初次相对路径、1022 iterator EOF、V2–V5失败记录全部保留。完整263回归262通过/1权限skip，历史process-directory问题不因此关闭。目标active；无GUI/安装/真实工程修改/提交推送。下一H03/D04。

## 第二十四批任务关联OUT读取与原生MEASURE探测

- 新pspice_inspect_run_output绑定verified任务；计划digest/state及全部input/OUT/DAT哈希前后核对，OUT实际字节也核对manifest。只读不求解、不扩张读根。native recovered不宣称原生完成，测量明确未查；designPassed=null，数值验收只继承原声明行。
- 实际stdio DC/TRAN求解及OUT读取、fresh server不重放、错误digest/extra/AC失败拒绝及DAT篡改拒绝通过：`.local/run-output-mcp-20261023/report.json`。该新DC DAT末尾故意篡改，保持拒绝，TRAN完整。源hash保持。
- 原生MEASURE三例进程exit0/owned0，但DC/TRAN在owned目录没有测量值文件；AC VM明确ORPSIM-16646/16634，未计测量成功。`.local/native-measure-20261023/report.json`及预先期望保留，新ISS-P03-native-measure-results open后移，P03仍partial。
- 最终260回归259通过/1权限skip；初次270因继承/import重复收集测试而偏多，修复收集后重跑。历史目录占用issue仍open。111实际工具/契约同步；全34项未缩减，目标active，无GUI/安装或真实工程修改/提交推送。下一L05/H03/D04。

## 第二十三批位号映射、交换与冲突预检

- inspect_reference_units.tcl按真实object type区分placed/drawn，避免无条件cast；去掉DboPackage缺少官方签名的GetId请求，用packageName/size/deviceDesignator/source part等语义身份。V2仍报package_get_id，因一次字符串替换漏掉旧调用；精确删除后`.local/reference-identity-v3-20261023/report.json`同官方FULLADD全部definition partId/ref对应通过，源hash保持。原最早错误仅写unit_identity，不能追溯断言其一定在某个具体方法。新增external-design flag供plan拒绝外部依赖，未把definition单位当成occurrence覆盖单位。
- 新capture_references.py/edit_references.tcl，固定JSON声明与两个阶段SetReference：全部选中对象先到临时号，再全部到最终号，释放iterator后才修改，完整page/schematic/design保存。依据官方Tcl p515/522/529–530，修改真实Reference，不是仅改显示文本。临时号沿用prefix、避开全部已有与最终ref，失败保留副本/账本，不自动回滚重放。
- 公开5工具capture_plan_reference_map/apply_reference_map/reference_jobs/cancel_reference_map/recover_reference_map，open_edit_result新增kind=reference，实际110。1..64显式映射、原prefix/编号语法、part唯一、final casefold重号与未映射对象占用检查；可做循环/交换。当前仅唯一ref的single-unit placed definitions。重复ref/多unit/drawn/external/目标NC/未编号分配等提前拒绝或未提供；不假称原生自动Annotate。
- plan绑定native part ID +语义page/ref/package，post核对所有definition part/pin/net摘要、wire/alias/其他connection objects基线、所选页每个器件位置/旋转/镜像/实际pin hotspots、新单单元package及GetReferenceDesignator完整位号。scope=single_unit_part_definitions，designPassed=null，occurrenceConnectivityVerified=false；多单元/occurrence/渲染/其他属性/DRC原要求继续pending。
- `.local/reference-maps-20261023/report.json`4原生用例通过：未连接rename/swap、已连接rename/swap，新进程重开与fresh writer不重放/open、源hash保持。交换后原R101.2→新R102.2、原R102.1→新R101.1仍接MCP_MIDDLE；另两外端仍未接，位置/热点跟随原器件，wire/alias保持。
- `.local/reference-map-mcp-20261023/report.json`真实110工具stdio：已连接交换、明确pin-net与位置期望、schema、未映射冲突/重复单位/extra拒绝、pending cancel/jobs、fresh server原key不重放/recover/open、篡改拒绝均通过。末尾该MCP swap产物被故意追加bytes，保持拒绝；4原生用例产物未篡改。
- `.local/reference-map-faults-20261023/report.json`实际native完成后受控丢receipt→fresh只核验恢复/nativeCompletionVerified=false/hash保持并open；启动窗口cancel和真实1s timeout均自有进程0/不重放。不代表临时号/最终号/每个save窗口均已覆盖，也不证明历史目录句柄问题修复。
- 7项新主机测试：交换保留物理pin绑定且不改输入、casefold冲突/重复映射、prefix/控制符/未编号边界、临时号碰撞、重复ref、unknown/noop/extra、multiunit/drawn/external在创建plan前拒绝。最新257完整回归256通过/1原file-symlink权限skip；ISS-P02-process-directory-release-152等历史问题仍open，不因本次通过关闭。E03 partial，原34项完整范围未缩减，目标active。无GUI、安装/真实设计修改、提交推送；下一L05/P03/H03/D04等独立项。

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

## 第二十一批总线/DRC探测、精确几何与桥接发布修复

- H04：依据官方Bus_Connectivity.html及Tcl手册p435–443/498–499/581–583/739–740，新增内部fixture_bus.tcl、inspect_bus.tcl及probe_bus_fixtures.py。预先声明DATA[7..0]/DATA[0..7]、8scalar aliases/入口两端，另造缺成员与脱离入口。4项native创建保存均exit0，但独立读取全部失败；0项bus成员/正反例通过。`.local/bus-fixtures-20261023/descending/phase.json.error.json`定位page iterator NextPage/state3969；只读诊断hash保持，自有进程0。容器名改用DboNetBus.GetName而非scalar net名也未解决此前page阶段错误。H04 deferred后移，不发布MCP，不忽略3969。
- V03：再次核对官方capRunDRCConfigData仅设置/返回配置并关框，不能执行DRC。无现存Capture进程时，一次PID绑定的Capture.exe官方脚本命令行探测只列命令/proc参数、不主动开设计/调用DRC，45.047s超时，无runtime.json，自有进程0。没有桌面操作；该次确实启动了Capture应用，不能称全程未启动GUI。原因未观察到，不猜许可/模态/启动策略。V03 deferred后移，未获得真实DRC命令/报告，未开放接口。
- 独立V02推进：capture_check_wiring增加可选gridSize/gridOrigin，未提供时明确grid未检查；wire-geometry-advisory@0.2.0用精确Fraction求任意方向直线交叉、T接触、共线重叠，包括斜线；整数点保持point，非整数点用point=null/pointExact分子分母，不舍入后假落栅格。共享端点不加交叉罚，跨页隔离，非正交仍警告。2000segments/10000vertices/findings、native32bit坐标上限；零长度/grid也受限，不截断后宣称完整。geometryComplete仅指bounded_linear_wire_intersections，designPassed=null，未判断任何电气连接/DRC/文字避让。
- 新6数学/边界测试：6/5斜交点、反向斜重叠/T/共享端点、负坐标/平移grid原点、bool与非法范围、退化线/输出上限、大native整数精确交叉。`.local/wiring-exact-mcp-20261023/report.json`真实99工具stdio读取既有两电阻wire/alias副本：MCP_PLACE(330,310)-(490,310)，grid10 origin(0,0)离栅格0顶点、origin(5,5)离栅格2顶点，artifact hash、非法参数与副本篡改拒绝通过，源hash保持。这不是native斜线fixture或symbol/text渲染验收；V02 partial，其他原要求未删。
- 首次244回归失败于旧的“斜线未覆盖”测试断言。更新该契约测试为新线性覆盖succeeded，同时增加geometryCoverage、electricalConnectivityVerified=false、designPassed=null和未给grid仍notChecked断言；没有放宽电气结论。
- 第二次244回归发现既有桥接endpoint.json半写入竞态，认证测试在空文件上JSONDecodeError。bridge.tcl改成同目录排他临时文件、完整写入/close、无覆盖rename后才发布endpoint并登记owner；失败清理自己的temp。新增确定性native观察测试，在真正payload写入边界检查最终endpoint尚不存在。`.local/bridge-atomic-native-20261023.txt`23项全部通过，未用readiness延时/重试掩盖生产竞态；这是真Tcl协议夹具，不是重新验收Capture GUI加载。
- 最新完整245回归仍失败：243通过、1error、1原file-symlink权限skip。失败为test_cancel_and_precancel结束后临时cwd清理WinError32/5；与原ISS-P02-process-directory-release-152同类，现有完整原始堆栈保存，根因/持有句柄未确定，保持open。不能用早前绿色回归或专项通过称当前全回归通过；不再无修改重复跑去碰绿色。前三份失败报告都保留。
- 实际工具仍99，contracts同步新grid输入Schema。原34项和失败门禁保持，目标active。除一次无设计Capture脚本运行时探测外均独立Tcl/MCP；没有桌面点击、安装目录/真实设计修改、提交推送。下一L04/E03/L05/P03等独立项，最终集中修复后移问题。

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

## 第十九批器件姿态与删除业务

- 新capture_part_edit.py/edit_part.tcl；公开capture_plan_part_edit/apply_part_edit/part_edit_jobs/cancel_part_edit/recover_part_edit，capture_open_edit_result新增kind=part_edit，实际94工具。set_pose要求完整目标pin热点与所有保留page pin-net预期；delete不接受新pose/pins，只声明删除后存留pins。源hash/独立输出/持久计划/幂等/只核验恢复沿用隔离任务。调用者须声明预期，后端不会按观察值替换oracle。
- 检查同页引用唯一、目标NC拒绝、页面语义名称唯一、数据量/坐标/枚举/字段；核对完整definition/pin-net、connection objects以及所选页所有器件位置/姿态/热点。几何稳定键用ref+number/name，不依赖保存前后ordinal ID。非所选页几何、其他属性、occurrence、多单元封装生命周期、NC生命周期、渲染及DRC明确未核验。
- 根据本机官方手册p301–302/461–462/524使用SetMirror/SetRotation/SetLocation、Page.DeletePartInst及完整save链。选取对象后先释放iterator再修改/删除，不访问已删除指针。首次connected两个用例在编辑前失败；`.local/part-edit-opening-phase-20261023/native-result.json`定位Schematic.GetPage(name)/3969。改为已有reader所用NewPagesIter/NextPage/唯一exact name，未忽略3969。修复仅限本adapter；H02 NULL schematic net仍open。
- `.local/part-edits-v2-20261023/report.json`5项原生验收全通过：未连接move/delete、已连接move/delete、错误hotspot拒绝+禁止重放。move_connected明确R101移走后两个pin未连，R102.1仍连MCP_MIDDLE；delete_connected明确删除R101并保留R102与原wire/alias。新进程重开、其他page pin基线和所选page其他器件几何保持，源hash不变。
- `.local/part-edit-mcp-20261023/report.json`真实94工具stdio：move/delete、schema与非法bool/extra/漏pin拒绝、pending cancel/jobs/recover、新server相同key不重放并重开产物通过。末尾delete产物刻意追加bytes作为篡改负例，现应保持拒绝；不是全部MCP输出仍为有效产物。
- `.local/part-pose-centered-20261023/report.json`自建居中R401符号完整8姿态通过，期望先固定local pins±20、mirror-x、顺时针quarter turns，保存后新进程核对所有global hotspots和明确unbound网络。它不替代原C03非居中符号90度偏移反例，原issue保持open/deferred。
- `.local/part-edit-faults-20261023/report.json`真实native完成后受控删除receipt，fresh writer只核验恢复、artifact hash保持、nativeCompletionVerified=false；native启动窗口cancel和实际1s timeout均自有进程0、不重放。只覆盖这些窗口，不能代表所有保存阶段故障/资源浸泡已验收。
- 3项新主机测试覆盖声明热点不被自动重算/修改、缺失未知重复与bool拒绝、保存后ordinal变化不改变几何语义。完整233回归232通过/1原file-symlink权限skip。D02 partial；原34项完整范围不变，目标active。无GUI、安装/真实工程修改、提交推送。下一E04、H04、V03等独立项。

## 第十八批层次网络探测与单元物理脚专项

- 新增内部inspect_occurrence_nets.tcl与原生探测脚本，不开放MCP。按本机手册p273/529–530/545/596/626/628/642/651及官方capShortedDiscretePart.tcl、capPhysicalShortedPackShort.tcl，读取port occurrence -> port instance -> page net -> schematic net -> parent net occurrence -> flat net。原生对象指针仅在worker内部映射为临时ID，不按名称合并网络，不修改/保存DSN。
- FULLADD读取16occurrence、69port记录、18flat对象，包含层次块端口和隐藏电源。这是runtime探测计数，不是全连接表的独立验收。初次GetPinNumber在halfadd_A报1021；细分phase后确认是层次端口无物理脚号，不是GetNet的未连接状态。内部探测保留numberStatusCode，不能泛化所有1021。
- 发现U1C occurrence通过GetPortInst/GetPinNumber仍得到definition B单元4/5/6；GetPathNameNumber同样不能替代occurrence物理映射。采用occurrence.GetDesignator + placed package.GetDevice(designator) + pin logical position -> device.GetPinNumber，得到C单元9/10/8及共享14/7。
- `tools/verify_occurrence_pinmap.py`读取已保存的FULLADD原生证据，与TI SN74LS32官方14pin脚表独立核对A/B/C。将U1C强行换回definition脚号的负例被拒。`.local/occurrence-map-accept-20261023/pinmap-verification.json`通过，范围仅selected_ls32_occurrence_physical_pin_map；不能代表全H02、heterogeneous cell对应或全封装共享冲突已验收。外部依据：https://www.ti.com/document-viewer/SN7432/datasheet 。
- 联合专项`.local/occurrence-map-accept-20261023/report.json`仍失败：既有电阻连线副本GetNet非NULL而GetSchematicNet为NULL，错误阶段schematic_net；原生退出1、自有进程0、源和副本hash均保持。没有跳过该节点/按netName拼接/强制声称未连接。ISS-H02-null-schematic-net新增open，H02 deferred后移；FULLADD API探测通过不能覆盖此失败。原生网络初始化/新页生命周期原因未查明。
- 本批只新增内部适配器/探测及验收资料，公开工具仍89；最近完整回归仍230项229通过/1原symlink权限skip（第十七批报告，不冒充本批新运行）。无GUI、安装/真实设计修改、提交推送。34原始大项及全部验收要求保留。下一独立D02器件姿态/删除、E04文档生命周期、H04及V03。

## 第十七批层次实例身份与文档操作原生验证

- capture_get_hierarchy正式开放：身份仅限session/revision，occurrenceId为遍历身份，instancePathSegments由父上下文及完整单元位号构成；path/hierarchicalPath为原生字段，允许重复，不推断完整电气连接。
- `.local/hierarchy-identity-v2-20261023/report.json`、`.local/hierarchy-mcp-20261023/report.json`原生及真实stdio均通过：FULLADD 16项=1根+3顶层器件/块+12子单元；两个halfadd实例，U3A/U3B等共享raw path但单元身份独立。分页、重复、新session重新读取、游标绑定、非法参数、关闭及副本篡改拒绝通过；安装源hash不变。
- 初次验收脚本误预期关闭错误为stale_session，实际已有契约session_lost；`.local/hierarchy-identity-20261023/report.json`失败证据保留，未更改生产错误语义。历史raw path issue仅在身份误判范围结案。H01仍partial：根属性、原生空/循环夹具、覆盖属性来源、资源浸泡及原要求待验收；H02完整层次pin-net未实现。
- `.local/document-lifecycle-v2-20261023/report.json`5原生用例通过：新设计、schematic创建/重命名/删除、page删除；均自有副本、完整保存、新进程重开、源hash保持。仍为内部probe，未开放文档CRUD；依赖/非空/根对象删除保护、SaveAs及原完整范围未完成。首轮工作区路径拒绝报告仍保留。
- 实际89工具；230回归229通过、1原文件symlink权限skip。Allegro/PDF范围不变；本批无GUI、安装/真实设计修改、提交或推送。完整34项未结项。

## 第十六批声明式库创建与多单元/放置闭环

- library_create.py/create_library.tcl/inspect_library_create.tcl新增单package spec：symbols、devices、完整scalar pin物理映射和line body，显式position、shared/swap一致性；6个MCP工具，实际88。普通library query/placement可开verified/hash匹配产物，公共读根不扩张。Artifact可选sourceKind限定file_fingerprint/new_library_spec，明确创建输入为声明digest。
- 首轮4份OLB保存成功但metadata reader受vector EOF1022污染；独立vectorState修复后`.local/library-creates-recover-20261023/report.json`只读恢复原4份/hash不变。首次MCP sourceKind未同步Envelope而失败；完整失败记录均保留，见batch-16-library-create-2026-10-23.md。
- `.local/library-create-mcp-final-20261023/report.json`真实88工具5例：resistor、同构A/B shared VCC(6logic/5pad)、异构A/B/P(8logic/6pad)、type0..7/line样式宽度、中文及Tcl特殊字符全部通过。缺map/strict/错误native预期拒绝/不重放/pending cancel/jobs/新server幂等/篡改拒绝通过；最后Unicode OLB为已追加字节的负例，保持拒绝状态。
- `.local/library-create-faults-20261023/report.json`真实receipt-loss新MCP只核验恢复并打开，nativeCompletionVerified=false；native启动窗口cancel/1秒timeout owned0。不是所有保存阶段中断覆盖。
- `.local/created-library-placement-v2-20261023/report.json`新建resistor OLB→自有空页R401(700,300)，物理1/A(680,300)、2/B(720,300)、4k7与MCP_RES_FP、源不变/save/new-process通过；embeddedCacheClosureVerified仍false。首次联动脚本GBK读UTF8失败发生在native之前，报告保留。
- 228回归227通过/1原symlink权限skip；L02/L03/D01/L05保持partial。原其他vector/font/variants/swap边界/库编辑/cache/编号/页CRUD/层次/总线/DRC/CLI全要求未删。下一E04、L04、L03/E03/H01等继续。证据hash见batch-16-evidence.json。

## 第十五批库创建与页重命名故障结案（限定范围）

- create_library_probe.tcl逐阶段定位旧库创建失败到第2个NewSymbolPinScalar/code1106；官方MdlANDSymbolCreate明确NewPinNumber位置指针应初始化i，原夹具两次默认0。原失败保留，ISS-L02队尾诊断后用新explicit position0/1版本完成保存/独立重开。
- `.local/library-create-positions-20261023/report.json`：1package/device/cell/part/2pin，A/1/pos0(-20,0)、B/2/pos1(20,0)、type4/visible、cell/part名、deviceA/0、homogeneous/size1/footprint均通过。referenceTemplate独立读取、图形body、typed MCP create、其他pin/生命周期/多unit仍待验收。L02 partial，不把fixture当完整业务工具。
- `.local/page-rename-retest-20261023/report.json`3例create/rename_empty/rename_populated全通过，官方Schematic.Rename替代原错误Page.SetName；完整definition/pin-net/new-process/open_output及源hash保持。CapturePages.verify新增source postcondition。occurrence/hierarchy/连接/图形和其他CRUD未完成，页工具未注册。
- 两个旧issue只在上述原故障范围resolved；L02/E04仍partial。222当前回归221通过/1原symlink权限skip，82工具不变。见batch-15-library-page-2026-10-23.md与batch-15-evidence.json。下一typed库创建/页操作，再多unit/缓存/编号/层次/DRC及P02遗留。

## 第十四批采样波形通用测量

- 新pspice_dat_measure：summary、value_at、first_crossing；严格有限/单调实轴，拒绝重复/不连续/外推，real/imaginary/magnitude分量，明确样本mean/RMS与区间piecewise-linear mean/RMS，平台/未找到有独立结果。保留job/import来源，不等于原生.MEAS或设计安全。
- `.local/dat-measures-mcp-20261023/report.json`真实82工具：DC2.5V、AC cutoff幅值/虚部/下降交越、TR541点mean/RMS解析积分及tau上升交越1.000004061ms通过；复用原已验证job，没有重求解/改oracle。布尔axis、未知trace、非法组合和extra字段拒绝。
- 7项主机新测试，222回归221通过/1原symlink权限skip。见batch-14-waveform-measures-2026-10-23.md与batch-14-evidence.json。P03原生MEAS/OUT/相位/其他诊断等仍partial；下一回到L02/E04/V03核心Capture遗留项及P02 CLI。

## 第十三批持久引擎任务

- pspice_runs.py新增plan/apply/jobs/cancel/recover/open_run_dat共6工具，实际81；capability实验性independent engine Tcl，CLI仍未通过。闭包文件重新复制并重定位INC/INCLUDE/LIB，本次OUT/非空DAT/声明样本与输入hash验证，缓存/new server也复核全部artifact。
- `.local/pspice-run-mcp-20261023/report.json`真实MCP：嵌套DC2.5V、AC0.5-j0.5、关联DAT、错误数值拒绝/不重放、原生输入错误分类、pending取消、真实1s timeout/owned0、strict/jobs/新服务幂等通过。DC输出为篡改负例已追加字节，保持拒绝状态；AC正例完整。普通dat_open仍不能访问private job根。
- `.local/pspice-run-faults-20261023/report.json`真实receipt-loss→新MCP只核验恢复→关联DAT通过，nativeCompletionVerified=false，无重放/原OUTDAT hash保持；真实native启动窗口cancel owned0。不是所有求解/保存阶段故障证明。
- `.local/run-transient-mcp-20261023/report.json`公开transient job关联541点，完整host RC oracle/tau=1.000004061ms通过。通用工具仅验证声明行，完整波形数学比对是专项host验收。
- 215最终回归214通过/1原symlink权限skip；首次旧capability断言失败日志保留。见batch-13-persistent-engine-runs-2026-10-23.md与batch-13-evidence.json。后续P03通用指标、原生错误细分/CLI与其余Capture项，全部34项仍必需。

## 第十二批独立引擎与DAT格式修复

- 独立tclsh/orPSP_ENG64.dll + 官方PSpiceAD batch mode已原生DC通过；数字节点5V分压2.5V。CLI原timeout仍open，未发布solver工具。
- IN/OUT配具名PRINT/PROBE选择触发ORPSIM-15090，无DAT，ISS-P01-named-output-selectors后移；裸.PROBE官方变体同物理参数三项原生求解通过，但旧DATdecoder失败，原报告保留。
- 新DAT旧式getJSON文本不宽松解析；识别特征后另起worker逐block读取官方getHeaderData/getDataNames，复用严格decode。headerSource/aliasGroupingSource明确数据来源，未知trace仍主机拒绝。
- `.local/engine-dat-mcp-20261023/report.json`真实75工具核验已有新solve产物：DC2.5V、AC3点非零虚部/159.15494305Hz截止、TRAN541点/1.000004061ms tau（最大2.881e-6V误差）通过。导入API仍不认证正式job。详见batch-12-engine-dat-2026-10-23.md。
- 210回归209通过/1原权限skip；官方21block/59点12例真实MCP兼容通过，`.local/dat-compat-after-direct-20261023/report.json`。正式持久solver jobs、错误/取消/timeout/recover、多块writer旧故障、CLI等仍需推进。
- 临时绕过trace白名单的直接native诊断AC退出3221225477，具体方法缺日志；已记录direct-probe-process-audit.json，不归因某个get。公共精确白名单不可放宽。

## 最新内部文字失败与DRC调查

- `.local/graphic-text-20261023/report.json`：中文/Ω/换行和Arial完整字体已保存，新进程定义/连接保持；实例位置读到0,0，不满足300,450原oracle。ISS-D05-comment-text-coordinate-frame后移；未开放文字writer，D05仍partial。详见text-drc-investigation-2026-10-23.md及text-drc-evidence.json。
- DRC官方CustomDRC.pdf与framework源码已读并登记hash；主执行入口仍待核实。capProcessSelection依赖活动PM，日志为append；true/config回调不是检查通过。当前Capture不在运行，独立Dbo DLL未暴露ExecuteDrc命令，不推断GUI运行时能力。

## 第十一批装饰线

- capture_graphic_line.py/graphic_line_probe.tcl新增零旋转装饰线与独立局部/全局端点复核，真实MCP75工具闭环通过；全部定义/pin-net及连接对象不变，已有line几何/pose多重集保持。207回归206通过/1原symlink权限skip。
- `.local/graphic-line-20261023/report.json`及`.local/graphic-line-mcp-20261023/report.json`是当前证据；成功artifact recovery只是再核验，不是丢失receipt/native中断证明。D05文字/其他形状/编辑删除/标题栏/字体/样式/页面边界及完整故障矩阵仍待完成。
- 第十一批范围见batch-11-graphic-line-2026-10-23.md、batch-11-evidence.json。V03仍未执行；配置框Run/true回调均不当作原生DRC已通过。

## 第十批导线编辑

- capture_wire_edit.py/edit_wire.tcl新增受控两端点scalar移动/删除与显式alias处理，70工具契约同步；真实原生两例及MCP生命周期通过，203回归202通过/1原symlink权限skip。见batch-10-wire-edits-2026-10-23.md和batch-10-evidence.json。
- 故意四脚短接的SetPoint跨度保存成功，但独立重开中间pin未绑定，wire_edit_net_mismatch拒绝。`.local/short-via-edit-20261023/report.json`和对应plan.json保留；ISS-D03-interior-pin-topology后移。原V01短路fixture问题仍open，不称短路反例验收成功。
- D03/D04仍partial；junction/T/交叉/重叠/断点、occurrence、wire-only网身份、完整故障矩阵、DRC均待完成。优先继续D05/V03独立项。

## 第九批放置故障与cache只读查询

- 新capture_query_cache，capture_cache.py/inspect_cache.tcl；通过DSN而非外部OLB返回package/device/cell/part/pin，scope=dsn_cache_device_definitions，session/hash/查询签名绑定cursor，严格validate_library及文档/对象上限。externalSourceLibraryVerified/cacheSynchronizationVerified=false，不提供cache修改。实际65工具、195回归194通过/1原symlink权限skip。
- `.local/cache-query-mcp-20261023/report.json`真实MCP查询已放置cacheName：package/device/cell/part各1，pin1/2、电气类型4、visible及AXRC05正确；分页/空过滤/额外字段/closed session拒绝通过。3项主机缓存边界测试通过。
- `.local/placement-faults-final-20261023/report.json`：真实保存后删自有receipt，新stdio MCP recover只核验、nativeCompletionVerified=false、无重放并打开输出；真实native-start取消和合法argv的刻意2秒延迟/1秒timeout均owned残留0。不是正常放置性能或所有保存阶段中断证明。
- `.local/cache-offline-4383bfd6a9/report.json`：仅暂时改名该批自有job/library.olb和lib-session/library.olb，独立DSN重开与R103脚/热点/定义符合预期；finally两路径/hash恢复。安装库仍可访问，未跟踪所有native文件访问，fullCacheClosureProven=false，不能把该单案例当通用闭包已证明；production placement仍embeddedCacheClosureVerified=false。
- 见batch-09-cache-faults-2026-10-23.md、batch-09-evidence.json。后续推进D03修改删除/矩阵、D05图形/V03检查，再按后移队列修复；L05更新/替换/实例覆盖、多unit及完整closure仍原范围必需。

## 第八批已开放的typed placement

- CapturePlacements在capture_place.py，native edit_place.tcl；新增plan/apply/jobs/cancel/recover placement共5工具，实际64；open_edit_result新增固定placement kind。library service之后创建placements，cancel接诊断线程池。
- 输入绑定source DSN/OLB不可变副本及package/device designator+position/cell/part语义；source variant数核验，随机新cache名原生冲突拒绝，不替换旧缓存。新reference全设计忽略大小写唯一；同号追加单元不走此普通接口，需package-aware实现。
- 调用方声明每个新physical pin的number/name/global hotspot/connected/net，及目标页全部既有pin预期。不能用失败C03仿射公式推断热点；读实际GetOffsetHotSpot核对raw pose与全局坐标。保存重开核对全部定义/连接对象保持、Value、继承PCB Footprint。
- `.local/placement-mcp-20261023/report.json`真实64工具MCP：ANALOG.R→R103(700,300)，脚1=(690,310)、2=(730,310)、Value2k/Footprint正确，12part/47pin；故意错热点真实保存后拒绝、pending cancel/jobs/extra参数、新server幂等/输出再开通过，源DSN/OLB hash未变。
- 独立打开时job/library.olb仍在，因此embeddedCacheClosureVerified=false。多device/shared单位/variant/cache复用更新及其他pose/器件未全验收；这些placement专属真实故障切片已在第九批补验；所有保存阶段中断与完整closure仍需补。
- 4项主机测试+完整192项回归（191通过、1既有symlink权限skip）。见batch-08-placement-2026-10-23.md和batch-08-evidence.json。D01保持partial，总目标active。

## 第七批已开放的typed wire_add

- 新增capture_plan_wire_add/apply/jobs/cancel/recover共5工具，实际59；capture_open_edit_result新增固定wire_add kind，只允许已verified/verified_recovered且artifact hash一致的输出。新类CaptureWireAdds在capture_wire.py，native固定edit_wire_add.tcl，不允许eval/任意方法。
- 计划要求目标页全部既有引脚的明确expectedConnections，其他页定义不变；端点/alias锚点整数、scalar名、大小/数量有界。预声明expectedWirePaths可分段/合并，但整数线/投影并集只能等于原几何+新段；独立读回还须路径多重集相同，不能拿并集代替native junction。
- 独立重开核对整份pin-net/几何/alias/其他连接对象；新增alias owner原生net默认期望netName，可传expectedWireNet表达既有canonical名。wire-only其他网身份/occurrence/DRC/布局字体/器件其他属性仍未核验。结果明确wireOnlyNetIdentityVerified=false。
- `.local/wire-add-stdio-owner-20261023/report.json`真实MCP保存/重开/输出衔接、owner net、错误topology真实保存后拒绝且不重放、pending取消、jobs分页/严格额外字段、新server幂等/输出再开均通过。最后tools-list.json为最终59工具契约。
- `.local/wire-add-faults-mcp-20261023/report.json`：真实保存后host删除自有receipt，apply失败；新stdio MCP recover仅核验artifact、nativeCompletionVerified=false、不重放，随后MCP打开输出；另一个真实worker启动窗口取消owned剩余0，源不变。不要说成已覆盖所有保存阶段的并发取消。
- 10项主机新增测试通过；最终完整188项187通过/1既有symlink权限skip。历史P02资源清理issue仍open。见batch-07-wire-tools-2026-10-23.md与batch-07-evidence.json。
- D03仅add segment+alias的typed闭环，修改/删除/所有交叉T重叠断点矩阵待完成；D04其余功能同样未完成。D01在第八批已接入typed placement，完整范围仍partial。所有required功能和后移issue保留，目标active。

## 第六批重要修复与原生正反例

- C01 GetNet未绑定返回NULL/1021(Object Not Found)，现仅允许这对或无错误NULL；非NULL错误/其他失败仍拒绝，新状态避免污染outer iterator。精确错误回归5项通过。显式delete_DboState候选曾导致真实DLL失败，已撤回；最终worker-scoped状态生命周期通过独立候选4例及生产MCP4例。资源数量受对象上限约束，峰值内存/长期浸泡仍待最终门禁，不能称已证明所有对象析构语义。
- `.local/definition-stdio-20261023/report.json`真实MCP FULLADD/CMOSCPU/TUTOR2/已保存双电阻4例通过，原两个C01 open issue已resolved。CMOSCPU3/3/27/155(32未绑定)，TUTOR2 1/1/38/221(37未绑定)为观察计数，非独立人工oracle。
- `.local/placement-521716d26a`原生CopyPackageAll/NewPlacedInst/save本就成功；在C01修复后只读重验同一artifact的R101/R102位置、源R脚号/热点、4脚无绑定、原设计定义不变均通过，见`.local/definition-fix-1712d44e3c/report.json`。D01仍无通用typed工具。
- `.local/wire-alias-0666b70746/report.json`：两电阻端点330,310→490,310直线、MCP_MIDDLE alias、新页1wire/1alias、独立四脚表和其他定义保持通过。D03/D04仅原生fixture切片，未注册新写工具。
- `.local/connections-read-20261023/report.json`真实MCP正确四脚表pass、断线中间两脚2mismatch通过；41个其他脚未列入人工表，designPassed=null。故意短接生成在opening失败，尚无短接比对，issue ISS-V01-short-fixture-open队尾，证据`.local/connections-positive-negative-20261023`。
- C03 `.local/pose-matrix-1fc81bf46d/report.json`：GetNet修复使r0/m0通过，r1/m0与不变仿射oracle有Y+40偏移，报告2attempt仅1通过，停止且新issue deferred。原基本open issue已解决，不等于姿态矩阵通过。要核实原生符号局部/实例原点/旋转参考，不从观察值倒写期望。
- 详细范围和证据hash见batch-06-reader-placement-wire-2026-10-23.md、batch-06-evidence.json。178完整回归177通过/1原symlink权限skip，实际工具仍54。

## 第五批内部实现（未注册MCP）

- LibraryPinEdits/library_edit.py + edit_library_pin.tcl实现隔离OLB脚名/类型/device脚号计划与保存重开；首个脚名native保存后ordinal snapshot摘要失败，后续number/type未跑。原生枚举顺序变化已在前后JSON确认，旧计划不改/不重放。后续需跨进程稳定语义身份定位与全图比对，不能只按ordinal持久化。已补package/device/cell/part身份预检和48000byte计划限制，尚未复测。库属性/图形/复杂共享与缓存仍待完成。
- inspect_reference_units.tcl原生多单元身份探测失败，仅unit_identity阶段，未做编号。已补更细phase/错误文本，尚未重跑。需区分drawn/placed以及GetReference状态，不能把同名位号直接合并物理器件。
- CapturePages/capture_pages.py + edit_page.tcl：FULLADD.HALFADD新增MCP_EMPTY页保存、独立重开、expected definitions与open_output通过；随后Page.SetName失败，带元件页rename未执行。已改官方Schematic.Rename，原生复测待尾部。新设计/schematic/删除与依赖检查仍待完成。
- 9项主机规划/保护测试通过，真实业务仍失败，不能据此开放工具。实际工具仍54。证据与范围见batch-05-editors-2026-10-23.md；ANALOG库（实际hash见report）与FULLADD源前后均一致。

## 遗留失败队列

- L02 `.local/library-create-f6355f7ec1/report.json`：单单元CreateLib/package/cell/part/device/pin创建或保存Dbo错误，缺phase；后续补阶段诊断。官方方法CreateLib，不是NewLib。
- H01 `.local/hierarchy-probe-20261023/failure-report.json`：16occurrences/4重复GetPathName；host错误唯一性假设。capture_get_hierarchy未注册；需核对GetHierPathName/GetRefPathName及多单元身份，不能按raw path合并。
- C01原CMOSCPU/TUTOR2基础open失败已按第六批解决；历史失败证据不删除，C01完整功能仍partial。
- C03原pose-matrix-ee5基础open阻塞已解决；新pose-matrix-1fc81bf46d的90度参考帧oracle仍失败，详见第六批。
- P02 `.local/pspice-owned-7797dd67a5/report.json`：DC分压60秒超时，无有效数值，2自有进程已终止；不得无证据归因许可证。新增issue ISS-P02-process-directory-release-152：152项回归一次临时目录sharing/access清理失败，157项回归未复现但未查明，不结案；ActiveProcesses=0不等于所有资源释放。原trace未落盘，仅batch03有诚实摘要。
- 文件symlink权限skip仍未补测；junction逃逸测试不能替代，不修改系统开发者模式/安全设置。

- 新增E03 `.local/reference-units-2c21c1eba1/report.json`、L04 `.local/library-pin-4536efce3f/report.json`、E04 `.local/page-edit-fd681cbf5c/report.json`失败后移。详见第五批；未发布对应MCP工具。

## 下一步与依赖

下一批优先D03修改/删除/矩阵、D05图形、V03原生检查，并保留D01复杂中断/多unit/cache闭包矩阵。现有库/页可支撑独立项；不要把未验收rename/library edit当稳定公共能力。放置需source OLB不可变副本、package/device/cell/part稳定语义身份、明确new reference/expected pin-map与全局热点、实例和缓存策略。不要套用已失败C03简单仿射公式；可用明确调用方全局热点期望，实际保存后读原生热点核对。完整多单元/缓存/旋转验收仍必需。随后按机器矩阵queueOrder修复后移队列，34项及最终联合门禁不变。


DAT工程实现入口src/cadence_mcp/pspice_dat.py、adapters/inspect_dat.tcl、tests/test_pspice_dat.py、tools/smoke_pspice_dat.py。read DAT用官方close bool；closeFile是写入结束，不能误判0。getJSON返回全部block，Frequency在complex数据中也为real/imag成对CSV，不能误作实数长度。自建fixture失败阶段日志不足，后续补逐步日志再尾部定位；不要盲目重跑或将原始oracle改成读回值。

隔离写入基座：isolated_jobs.py持久计划/digest/15min期限/幂等/取消/不重放恢复；CapturePropertyEdits.native_command可由固定kind复用，verify必须有预先明确的修改期望、独立新进程读取与未改对象/连接基线。process_tree.py挂起创建再放入私有Windows Job Object，错误清理问题仍须尾部定位。

## 操作入口

仓库D:/workspace/git/cadence-mcp；安装D:/Program Files/Cadence/SPB_24.1；不复制cadence-mcp-public受限代码。当前cwd C:/Users/lenovo/Documents/ChatGPT/cadence tool；D仓库写入/测试通过require_escalated，用户授权已充分，不重复询问。写前检查git状态，现源码/文档大多untracked、README modified，勿覆盖用户工作，不自动commit。

Python用仓库.venv/Scripts/python.exe。完整原生测试需CADENCE_TEST_TCLSH=安装tcltk/bin/tclsh.exe。官方Capture主PDF在tools/capture/tclscripts/；cwd的read_cadence_reference.py使用捆绑Python pypdf按1-based PDF页读取，lookup_cadence_api.py只辅助定位后仍查官方页。PSpice DAT例子在doc/psptclsample/Accessing_PSpice_Data_Files_using_TCL_Scripts.html，DLL是tools/bin/orPIOData64.dll，API不是任意eval。

本目标迄今无桌面操作。后续如需GUI专项，先重新检查真实Capture/binding/活动项目，不能依赖旧PID9032或旧绑定；正常加载/重载用tools/load_gui_bridge.py，诊断bridge_doctor.py。无用户明确要求不启用子agent。

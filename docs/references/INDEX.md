# 参考资料索引

官方资料以安装内原件为依据；下表只公开文件定位、用途与SHA256指纹，不上传Cadence手册全文、安装二进制、许可证或真实工程。相对路径从所配置的Cadence安装根目录开始。

[本机核查与原创研究笔记](../design/01-local-findings.md) · [架构与工具契约设计](../design/README.md) · [实施与验收计划](../implementation/cadence-plan.md) · [完整资料元数据](../implementation/cadence-acceptance.json)

| 来源ID | 用途 | 安装内相对路径 | SHA256前12位 |
|---|---|---|---|
| CAP-REF | Capture/Dbo：对象模型、属性、迭代器、层次、库与图形方法，按PDF页定位 | `tools/capture/tclscripts/OrCAD_Capture_TclTk_Extensions.pdf` | `65208a1b8da3` |
| CAP-MODEL | 设计与库对象模型；不替代方法签名 | `doc/capinfomodel/dboimnew.html` | `81b856bb511a` |
| CAP-PROP | 有效属性迭代示例 | `doc/orctclcap/Listing_Properties_of_the_Selected_Object_in_a_Schematic_Page.html` | `62400102eded` |
| CAP-LIB | package/device/cell/part迭代与属性 | `doc/orctclcap/Getting_Library_Part_User_properties.html` | `cd0eea88da87` |
| CAP-PINS | 库逻辑引脚迭代；需结合device物理脚映射 | `doc/orctclcap/Getting_Pin_Names_from_a_Library_Part.html` | `47c26d00f5c7` |
| SIM-CLI | psp_cmd /r 非交互模式 | `doc/cap_ug/Running_PSpice_in_Batch_Mode.html` | `2956bdd1da51` |
| SIM-ENGINE | PSpice引擎接口与输入/输出/库路径 | `doc/psptclcmdref/PSpiceSetupAnalysis.html` | `6b6aef24df87` |
| SIM-EXAMPLE | 引擎初始化/分析/退出示例 | `doc/psptclsample/Accessing_PSpice_using_TCL_Scripts.html` | `3e5b7b72760b` |
| SIM-DATA | DAT块、trace和结构化数据访问 | `doc/psptclcmdref/Accessing_PSpice_Data_Files_using_TCL_Commands.html` | `a859bf04160c` |
| CAP-DRC | DRC配置实现；关闭对话框不代表执行DRC | `tools/capture/tclscripts/capDRCConfig/tcl/OrHandlerDRCConfig.tcl` | `9c4dc66335bd` |
| SIM-OUT | OUT类型及与DAT/CIR的区别；格式另核对官方样例 | `doc/pspug/007_set_sim_PSpice_A_D_Simulation_Window.html` | `390d66b3f0f1` |
| SIM-DAT-EXAMPLE | Direct Access API、complex标志、AC写入/多块读取示例，实际运行上下文需另验收 | `doc/psptclsample/Accessing_PSpice_Data_Files_using_TCL_Scripts.html` | `e9dd3b74e0ca` |
| CAP-CUSTOM-DRC | Official custom DRC framework; not evidence of main native DRC execution | `tools/capture/tclscripts/capDRCFramework/tcl/CustomDRC.pdf` | `cd76ee8a0767` |
| CAP-DRC-TRAVERSAL | Official custom DRC framework; not evidence of main native DRC execution | `tools/capture/tclscripts/capDRCFramework/tcl/capProcessDRC.tcl` | `8b5b751ce6be` |
| CAP-DRC-LOG | Official custom DRC framework; not evidence of main native DRC execution | `tools/capture/tclscripts/capDRCFramework/tcl/capCustomDRC.tcl` | `0cdd006e8b20` |
| SIM-BATCH-LICENSE | Official engine/direct-data command signature and example, not execution proof | `doc/psptclcmdref/PSpiceSetLicenseBatchMode.html` | `66fed9325630` |
| SIM-DO | Official engine/direct-data command signature and example, not execution proof | `doc/psptclcmdref/PSpiceCommandDo.html` | `099d6f0d2bfe` |
| SIM-END | Official engine/direct-data command signature and example, not execution proof | `doc/psptclcmdref/PSpiceTranEnd.html` | `f609722be742` |
| SIM-DATA-NAMES | Official engine/direct-data command signature and example, not execution proof | `doc/psptclcmdref/getDataNames.html` | `f054864e9dc9` |
| SIM-DATA-JSON | Official engine/direct-data command signature and example, not execution proof | `doc/psptclcmdref/getJSON.html` | `1c26d3eb896a` |
| CAP-SYMBOL-CREATE | Official makePin uses explicit logical position; generatePinNum initializes int pointer with loop position, not default0 | `tools/capture/tclscripts/capPSpiceModelApp/Digital/Gates/AND/tcl/MdlANDSymbolCreate.tcl` | `e1bacccf92aa` |
| SIM-COMPLETE-ANALYSIS | Run all analyses using fixed complete native entry point | `doc/psptclcmdref/PSpiceDoAnalysis.html` | `8340346f1b49` |
| SIM-MEASURE | Native MEASURE syntax and measurement text result; measure_command anchor | `doc/pspcref/01commands.html` | `0b4842419e91` |
| SIM-CONVERGENCE | Nonlinear DC/transient convergence and time-step diagnostics | `doc/pspug/B-conver.html` | `b72b27c62ca6` |
| SIM-ABM-CONDITIONAL | IF expression discontinuity and convergence warning | `doc/pspcref/00intro.html` | `6725e8a86e01` |
| SIM-OUTPUT-SELECTORS | PRINT/PROBE output variable disambiguation; anchors26898/42747, brackets force node names | `doc/pspcref/01commands.html` | `0b4842419e91` |
| SIM-CLI-OPTIONS | Command-line option table; actual psp_cmd only/r accepted in this batch, extra flag combination rejects | `doc/pspcref/00intro.html` | `6725e8a86e01` |
| SIM-LICENSE-ENV | CDS_LIC_FILE port@host syntax; child-only override did not prove license-unavailable behavior | `doc/pcbInstall/chap8.html` | `7faf1449d520` |
| CAP-PAGE-ALIGN | 官方页面排列示例：GetDocUnits(1)边界及PhysicalGranularity用户单位转换 | `tools/capture/tclscripts/capAlignObject/capObjectAlignment.tcl` | `bccb4b118379` |
| CAP-PAGE-CUSTOM | 官方自定义页面示例：原始PageWidth/PageHeight与用户单位的区别 | `tools/capture/tclscripts/capCustomSamples/capCustomizePage.tcl` | `0ccc2e04e608` |
| CAP-LOCAL-PSPICE-NET | 本地PSpice NET生成调用和日志读取示例 | `share/orTclscripts/tclscripts/orPrmDesigner/orPrmHandlerSimulation.tcl` | `a2323ca28204` |
| CAP-ASP-DISPATCH | 区分远端ASP分发与本地NET接口，远端接口未调用 | `share/orTclscripts/tclscripts/orPrmDesigner/orPrmDesigner.tcl` | `59b10cfa1a35` |
| CAP-ONLINE-DRC | 在线DRC设计事件/订阅机制；不证明全部规则开启 | `tools/capture/tclscripts/capOnlineDRC/tcl/capDRCImpl.tcl` | `38d6393f6b9e` |
| CAP-DRC-NATIVE | 本机DRC包装签名核查，仅元数据不分发二进制 | `tools/bin/orDRC64.dll` | `4b0571b7a8c2` |
| SIM-LOCAL-CIR | 本地profile读取、目录前置条件及updateCirFileI调用示例；未source整体服务 | `share/orTclscripts/tclscripts/orPSpiceSrvrEnv/orPSpiceSrvrEnv.tcl` | `7df7230cc471` |
| SIM-REFERENCE-COMMENTS | PSpice官方分号行尾注释规则，本批只扩展显式依赖引用解析 | `doc/pspcref/01commands.html` | `0b4842419e91` |
| SIM-PROBE64 | 官方.PROBE64输出指令示例 | `doc/psphlp/01_chap01.html` | `ed9f232bca08` |
| SIM-CORE-PATH | CORE磁芯模型PATH数值参数，区分外部文件路径 | `doc/pspcref/02analog.html` | `98d22e318d5e` |
| SIM-LIB-PARSER | 本地parseLib元数据入口；只记录指纹，不分发二进制 | `tools/bin/orPSpiceLibParser64.dll` | `f3c3139288a9` |
| SIM-LIB-PARSER-CALLER | 官方getLibJson使用parseLib的依据；未source整体服务或调用上传函数 | `share/orTclscripts/tclscripts/orPSpiceSrvrEnv/orPSpiceSrvr.tcl` | `16dcb21a325d` |
| SIM-LIB-BREAKOUT | 官方库私有副本75顶层/32局部定义核验，原始模型不上传 | `tools/pspice/library/breakout.lib` | `987c7563ecfc` |
| SIM-LIB-READ-SCOPE | LIB按需读取定义与INC全文读取的区别；不证明未知/加密库语义 | `doc/pspug/003_model_Configuring_Model_Libraries.html` | `5a70a565ae59` |
| CAP-DRC-UI-FIELDS | DRC普通/在线字段及ERC行列；Run提交配置、Apply保存配置，不证明实际规则执行 | `tools/capture/tclscripts/capDRCConfig/hybrid/nativeJS/DRCConfig.js` | `c0d1ed48526a` |
| CAP-DRC-RUN24 | 24.1原生DRC由PCB菜单启动，需选择DSN；运行可保存设计/设置 | `doc/cap_ug/Running_Design_Rules_Check_-_Physical_Rules.html` | `e50aa4214504` |
| CAP-TCL-MENU-MACRO | SelectPMItem、Menu及MessageBox宏示例；末尾日志提示宏尚未验收 | `doc/orctclcap/Common_Tips_and_Tricks.html` | `0791f43fb27b` |
| CAP-DRC-ACTION | 原生DRC菜单到配置返回回调的调用链 | `tools/capture/tclscripts/capAutoLoad/capAutoDRCConfigInit.tcl` | `3dab4431557c` |
| CAP-LOWPASS-OPJ | 24.1随附模板仍含历史项目字段，不能据此认定运行版本17.4 | `tools/capture/templates/pspice/LowPassFilters.opj` | `1cbe75c241c8` |
| CAP-PROJECT24 | 24.1原生项目创建、启用PSpice及既有工程后续仿真配置 | `doc/cap_ug/Creating_a_Project.html` | `fc0b1ef3b6e7` |
| CAP-DRC-NATIVE-KEY | 只读参考GetName原始字符串再MakeStdStr查询DRC计数；不调用PCB创建 | `tools/capture/tclscripts/capNewPcbEditorBoard/tcl/OrHandlerNewPcbEditorBoard.tcl` | `d67121d51d01` |
| CAP-DRC-OUTPUT-OPTIONS | Show DRC Outputs选项；实际0仍出现末尾日志询问，不作为自动结束保证 | `tools/capture/tclscripts/capDRCConfig/hybrid/DRCConfig.html` | `75ffe613816b` |
| SIM-DIG-ENUM | 本机SDK六状态枚举；不证明getDigital标志或尾字段格式 | `tools/pspice/api/include/PSpiceDigApiDefs.h` | `a71b3a54f902` |
| SIM-DIG-CONCEPTS | 数字六状态与64强度概念 | `doc/pspug/14digsim_Concepts_of_Digital_Simulation.html` | `e2a0b012233e` |
| SIM-DIG-STIM | STIM状态字符与数字器件语法 | `doc/pspcref/03digita.html` | `37de227ee448` |
| SIM-PROFILE-NATIVE-JSON | 官方profile创建/读写JSON流程；不证明CorSimSrvr全部语义 | `tools/pspice/tclscripts/pspDB/pspice.tcl` | `1e75aa2a194b` |
| SIM-ALIASES | ALIASES映射及INC/LIB定义 | `doc/pspcref/01commands.html` | `0b4842419e91` |
| SIM-CONFIGURATION | profile/design/global库与包含文件配置 | `doc/pspug/007_set_sim_Configuration_Files.html` | `3324abb736c8` |
| SIM-ALT-INI | PSpice进程-i参数；不能直接视为CorSimSrvr_setIniFile语义 | `doc/pspcref/00intro.html` | `6725e8a86e01` |

完整SHA256与文件大小见原始验收清单。原创最小复现与可再分发材料可随源码提交；第三方资料有明确再分发许可后才纳入。私有原生输出留在`.local`，公开其脱敏结论、复现步骤及摘要。

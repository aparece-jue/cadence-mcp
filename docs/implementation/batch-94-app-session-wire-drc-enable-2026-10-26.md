# 第94批：应用会话导线保存与按设计DRC启用对照

2026-10-26，C00/D03/V03。正式工具202/生产契约不变，原34项及独立预期保持。

认证私有错误夹具中，固定EnableDRC候选标识DRC_Check_Unconnected_Nets_Online返回1，capGetDRCConfigData相应在线规则却仍0，全部配置读回没有变化。脚本未调用CleanAndRun或转储，finally恢复false；恢复后的完整配置与原配置相同，DSN及OPJ指纹不变。现有日志mtime/hash原样且fresh=false，不将旧日志算作本次DRC。该结果不能证明规则真正启用，也不能宣称修复了冲突检测。

另建空DSN/ROOT/MAIN，独立解释器读取通过。最小OPJ经已认证的私有工程切换接口派发一次Open，被Update Old Project模态阻塞。受限命令查询未列出进程，曾错误地判断为宿主退出；随后computer-use窗口观察及获准进程查询确认同一PID20696仍运行，必须纠正，不归因为崩溃。旧原报告保留未确认状态，晚到Open回执及独立审计另存。

必要GUI恢复只处理此私有工程弹窗：选择None跳过转换，未改“Do not ask”最终设置。第一次元素输入缺几何失败；随后元素索引点击实际误中了Do not ask，截图确认后立即取消，再按已观察坐标选择None/完成。没有转换工程、没有选择不再提示。原Open随后返回并核对活动DSN，新认证绑定建立；没有重发Open或启动第二Capture。UI选择与误选恢复摘要留本地审计，不把截图/原生私有数据提交。

本次导线操作使用实际Capture应用的DboSession_s_pDboSession，而非此前宿主内另建的独立会话。依据官方capCustomizePage.tcl示例绑定全局session且不销毁。固定原预期无元件/引脚、ROOT/MAIN、唯一导线(100,100)→(300,100)，构造及完整保存链返回成功，实际宿主回执saved=true。但独立重开open/root/iterator为0，NextPage仍3969；独立审计owned0，设计原预期不改，失败保留。原两个私有控制DSN指纹均保持。由此否定“只要使用Capture应用会话就能修复”的假说；编辑器页面视图初始化尚未验证，不声称整个SDK不可用。

新增固定开发诊断/复现工具：probe_private_drc_rule.py、prepare_blank_capture_wire.py、fixture_blank_capture_wire.tcl、probe_app_session_wire.py、audit_app_session_wire.py。它们仅用于受控私有夹具，没有公开任意Tcl接口。Tcl完整性与Python语法检查、实际调用和独立状态审计执行；生产未变，沿用第93批554完整回归553通过/1原权限skip，本轮未冒称重跑完整回归。

完整验收仍6/34（17.6%），D03/V03不提升。下一步新夹具在真实页面编辑器初始化后再验证导线，继续准确DRC规则标识和模型使用/外部依赖解析。安装及真实设计未改，alpha.1固定，源码/结论/进度按授权同步develop。

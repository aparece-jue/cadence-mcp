# 原生DRC配置查询

`capture_gui_query(sessionId, entity="drc_configuration")`通过已有认证Capture会话读取配置。先发现实例并以read方式attach，结束后detach。开发版桥接需经可信loader重载一次才能具备新能力；旧桥接未提供此查询时会拒绝，不能当作规则关闭。工具总数仍203，alpha.1固定版本不含本扩展。

返回包括在线/flow主开关、配置中Run字段、7个在线电气规则的启用数量、ERC矩阵及明确列顺序。`configurationSha256`是本次检查并返回的开关/矩阵的紧凑JSON指纹，不是完整全局配置或设计文件指纹。原生DesignPath必须与绑定活动设计一致；路径和未检查的其他配置不会进入返回结果。缺字段、非法布尔值、矩阵行列/严重性异常会拒绝，不能默认为关闭。矩阵严重性为“-”（未声明检查）、“W”、“E”。

`rulesExecuted=false`及`coverageVerified=false`始终明确表示此次只读查询没有运行规则。主开关开启不代表各规则开启；矩阵中的E也不能证明某个真实故障已经被检测。第99批样例7个在线电气规则全关闭；第101批新私有项目已明确配置并读回7/7，仍不证明原四引脚冲突完整覆盖。原始失败保留。

官方资料索引CAP-DRC、CAP-ONLINE-DRC及CAP-DRC-UI-FIELDS分别定位窗口处理、在线事件与UI字段。官方Run回调只返回配置，Apply会保存配置；本工具不调用两者，也不启用规则、修改ERC或创建DRC报告。GetDRCSettings对配置字段返回unknown，配置字段不能自动当作该接口的规则ID。

真实验收脚本为`tools/smoke_drc_configuration.py`，要求显式binding和全新私有workspace-root。它在干净设计且无属性计划时重载可信桥接，旧读会话随代次变化失效；然后验证实际MCP查询、重复稳定性及detach后拒绝。首轮响应超长已保留，紧凑响应不改变原16KiB传输限制。完整原V03仍需按设计规则配置、真实运行、干净/故障样例、报告来源及分类定位。

原生计数读取与键身份、晚到结果限制见[drc-counts.md](drc-counts.md)。

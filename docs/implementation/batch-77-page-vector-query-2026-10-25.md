# 第七十七批：原理图页图形明细查询

2026-10-25。新增只读capture_query_page_vectors，实际192工具。C05完整门禁保持partial；已有D05文字坐标问题补证并后移。原34项和其他失败范围不变，无GUI/安装/真实设计修改或提交推送。

## 官方接口与实现

本机Tcl参考300–302页：DboGraphicInstance的位置/旋转/镜像及GetOffsetGraphicPoint；304–327页各图形实例GetDboLine/Box/Ellipse/Arc/Polygon/Polyline/Bezier/CommentText/BitMap；414页NewCommentGraphicsIter；448–456页对应固定构造签名。复用已验证的library vector原生描述符及定型embedded Tcl/DIB摘要回调，仅把新的固定只读脚本加入allowlist，不开放任意脚本或原生handle。

以session/page/revision绑定读取，native comment draw order，4096对象、65536控制点、262144文字字符、32MiB输出预算。返回localDescriptor（原生定义内坐标、样式、文字/14字体字段）、实例位置/姿态、GetOffsetGraphicPoint转换后的页面控制点；bitmap若类型命中则使用同进程有界DIB摘要。未建模OLE/嵌套图形保留unsupported行，报告unsupportedCount/supportedGeometryComplete，不静默遗漏。仅comment graphics，不把库实例或titleblock的内部vectors混入。文字矩形和控制点不是实际字形渲染边界，不能直接认证避让或电气连接。

## 原生声明矩阵与遗留文字问题

在此前可重开的工程独立副本MCP_PLACE页创建8类×4方向共32图形，奇数方向mirror1，偶数mirror0；显式非中心控制点、stroke style2/width1、fill1/hatch0，文字“中文 [x]$;\nR1 / R10”、Arial/height-11/weight700/italic/quality1。创建前expected.json冻结，原DSN/连接定义保持。

线、框、椭圆、圆弧、多边形、折线及贝塞尔28对象的local descriptor/样式/实例位置/姿态全部符合声明。新独立读取审计还从冻结局部点手算X镜像后屏幕顺时针旋转与平移，28组页面控制点均精确相符。不是以读取结果生成自己的预期。

4文字的文字/字体/原生局部框及方向/镜像符合声明，但实例位置始终(0,0)，并非声明的非零位置。v1构造后失败；v2按301页显式SetLocation返回成功、保存重开仍(0,0)，也未通过。原预期、两个失败报告、输出与只读审计hash保持。首脚本按期望位置寻找行导致StopIteration，审计改为完整native顺序逐条比较，确认只有4文字位置及其页面控制点不符；没有把实际零位置覆盖为期望。可复现工具改进了失败列表报告方式，旧报告保留。

复用原ISS-D05-comment-text-coordinate-frame，增加本次四方向/显式setter保存不符证据。根因仍未知，不声称Dbo不支持文字位置，也没有发布文字创建工具。D05完整门禁由partial转deferred并移到队尾。C05本批是读取能力增量，仍缺全字体/渲染边界、完整图框/符号与bitmap/嵌入等原条件，未标完整通过。

## 真实MCP与回归

32对象真实stdio逐条分页，全部local descriptor、文字/字体/方向/镜像与冻结声明相符；28非文字位置匹配，4文字位置不匹配明确记录。与原capture_query_graphics的objectId/nativeId/位置/姿态逐条对应。空页、跨页/页长/外来会话cursor、错误pageId、6次额外open/read/close、缓存后源工作副本变更拒绝、关闭后拒绝均通过，原DSN及expected hash保持。readContractPassed=true，但passed=false/textPlacementAccepted=false，不用读取契约通过代替写入位置验收。

新增7host验证严格类型、descriptor/control覆盖、显式unsupported、native顺序/数量预算和拷贝隔离。首安装脚本锚点假定旧geometry工具readonly=True而实际为False，assert在生产修改前拒绝；按实际锚点安装，不改变旧工具标记。最终完整480回归479通过/1原文件符号链接权限skip，192实际stdio契约同步。页bitmap byte路径复用已验证基础设施，但本批没有新增页bitmap原生夹具，不扩张验收结论。

## 复现与状态

tools/prepare_page_vector_fixture.py --install-root/--workspace-root/--source调用原创fixture_page_vectors.tcl，新输出目录、稳定输入DSN副本；当前会完整报告文字失败而不以其退出成功冒充完整夹具验收。tools/smoke_page_vectors.py --install-root/--workspace-root/--fixture-root验收读取工作流，输出同时保留完整矩阵未通过。原生审计脚本保留.local/batch77-probe-sources。

34现5 passed、1 baseline、11 partial、15 deferred、2 planned，目标active；先推进其他独立项，再回到所有原生遗留。hash摘要见batch-77-evidence.json。

# 标题栏定义图形查询

2026-10-28，batch130。新增开发接口`capture_query_titleblock_vectors(sessionId, titleblockId, cursor?, limit=100)`。先从`capture_query_graphics(entity="titleblock")`选择当前session/revision内的实例ID，再查询其符号定义的原生有序向量。工具224，发行65工具白名单保持，未晋级alpha/release。

结果含局部typed descriptor、文字/字体、实例位置/旋转/镜像、原生`GetOffsetGraphicPoint`计算的页面控制点、sourceSymbol、pageId及分页。向量ID只在revision/标题栏/原生顺序内有效；缺少稳定原生ID时明确null。unsupported向量保留，不能因部分支持就推断完整渲染。

固定worker按唯一schematic/page、标题栏nativeId定位，不接受Tcl/eval。4096标题栏与4096向量上限、65536控制点、262144文字及32MiB输出界限，状态和迭代结束检查保持。cursor绑定session、revision、实例及页大小；每次含缓存调用仍复核来源，任务不修改DSN或使用GUI。

## 实际验收

私有设计中MAIN放8姿态标题栏，OTHER放同名另一个，EMPTY为空。定义含line、box和中文/Omega/多行text，使用不同于首次失败的负偏移框[-30,10,140,90]。预期在构造前冻结，页面线端点通过独立旋转/镜像+location计算，未使用输出改写预期。9实例共27向量经公开MCP逐项查询，原生顺序/1项分页、sourceSymbol、局部几何、线端点、文字及Arial字号通过。跨目标/页大小/会话cursor、错误目标、缓存后源tamper及关闭会话拒绝通过；原DSN和oracle指纹保持。

首轮失败完整保留：UTF8 Tcl源由系统编码读取造成文字损坏，换行实际正确；旧框归一化公式也与标题栏转换不一致。新的fixture用Unicode转义消除源编码因素，生产接口直接调用原生转换，不把元件公式套到标题栏。原报告因先遇文字断言而未记录全部坐标差异，另只读审计补列差异，不更改原报告/oracle，不追认为成功。首次源未记录重开前hash，不补造保留证明。

新增6单元测试覆盖目标/pose类型、索引、控制点、未知几何及空定义。第一次完整回归两个固定工具数断言仍223失败，记录保留；核对旧223契约逐项完全保持、唯一新增本工具后更新为224。最终完整729项：728通过，1原符号链接权限skip；收紧header类型后再次实际MCP复验通过。

## 证据范围

本批实际原生覆盖line/box/text，字体仅核对族与字号，完整字体质量/字形边界不在通过范围。其他typed类别虽共用已有描述器，未据本样例宣称标题栏曲线/位图等原生验收。动态标题栏字段、effective occurrence文字、display property、嵌套/OLE、字形/笔宽/打印边界及标题栏编辑等原要求仍待验收。C05仍partial，原34项仍8/34（23.5%），目标active。

本机CAP-REF依据：285–291页图形定义/创建、300–302页坐标转换及姿态、443页NewTitleBlock、668–669页GetSymbol及source name。只公开原创总结与源码，不上传手册/原生设计；批次证据和SHA256见[batch130](implementation/batch-130-evidence.json)。复现为`tools/probe_titleblock_vectors_v2.py`、`tools/smoke_titleblock_vectors.py`，数据目录必须全新且位于私有.local。

## 2026-10-29：椭圆与圆弧补验（batch132）

以CAP-REF287–289页NewArc/NewEllipse签名在全新私有fixture中加入椭圆[0,20,80,70]与圆弧框[-20,20,100,80]、起点[-20,50]、终点[40,20]；原line/box/text保持。预期在构造前冻结，未从读回重写。九个标题栏共45向量，八姿态及另一页同名实例的原局部曲线数据、四角控制点和圆弧端点逐项符合独立旋转/镜像+location预期；1项分页/原生顺序、空页、非法目标、跨目标/页大小/会话cursor、缓存后来源改变及关闭后拒绝通过公开MCP。源/预期和旧失败证据hash保持。

新增18个曲线实例原生验收，不是曲线实际渲染边界、填充/笔宽或字体/动态字段验收。C05仍partial，原34仍8/34；生产代码和契约未改变，最近完整729/728+1权限skip沿用batch131，未重跑完整回归。两份固定研究脚本编译通过。测试版/发行版及旧tag保持固定，研究资料同步develop。证据见batch-132-evidence.json。

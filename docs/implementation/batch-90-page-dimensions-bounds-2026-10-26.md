# 第90批：原生页面尺寸与声明控制点边界

2026-10-26，C05/D05/V02；新增两个只读工具，实际202。原始完整门禁未提升。

## 实现和官方依据

CAP-REF p400–402提供Page.GetDocUnits、GetPageWidth/Height、GetSize、比例及图框标志，p416提供原生尺寸设置，仅用于私有fixture。官方capAlignObject使用doc units作页面边界并按PhysicalGranularity转换用户单位，capCustomizePage区分原始页参数与用户单位；资料索引新增两个路径/指纹，不上传源码。

固定只读reader以fresh DboState遍历视图及页面，任何异常迭代结束都拒绝，不将已找到1目标后的错误当完整成功。Python严格验证字段、类型、范围及有限正比例，16KiB原生输出预算；revision-bound缓存校验前后源。零文档尺寸返回未知，checker不生成界内结论。

checker按fullPageBounds与显式margin核对全部支持comment graphic声明控制点，精确边缘界内、界外侧别分别记录，所有对象和顺序来自原生page reader。4096对象/65536点/1000finding上限、不支持对象及超限均失败，不截断为成功。结果designPassed=null，明确排除glyph/曲线/arc真实裁切、物理可打印原点、元件导线、标题栏/嵌套、连接与DRC。

## 原生与真实MCP验收

- 私有新增英制9700×7200页（doc970×720）、公制12700×10160页（pin254，doc500×400）、已设尺寸空页和未设尺寸零页。
- 主页面6条线/3段文字，共9对象27控制点；预先固定精确边缘、四侧越界、声明框及锚点，margin0的10发现、margin10的16发现逐项坐标/序号/侧别一致。其他公制页仅自身1线2点，空页0对象；零页checker page_dimensions_unknown。非法scope/bool margin/过大margin及关闭session拒绝。
- 真实遍历正常结果通过；私有reader副本在找到目标后注入page/view结束3969，两次均非0退出、无JSON、owned0。它是边界状态注入，不声称Dbo原本主动报该错误。生产reader及源hash保持。
- 实际MCP重复读取缓存一致，修改独立workspace副本后尺寸和图形checker均target_changed，原fixture/源不改。
- 前两次fixture源代码少一处闭合花括号：第一次harness未保存process，因缺receipt退出；第二次保存exit1/owned0且未进入首个DB标记。保留原脚本/目录/report；原Tcl info complete=0，新脚本=1，修正后全新副本MCP通过。未改失败预期。

## 导线3969反证

观察到新页0×0后做六组独立原DSN线段预期对照：默认、SetPageSizeInfo、SetSize、两者、独立width/height/pin/metric、画线后设尺寸。后5组保存前getWidth/Height均9700/7200，但所有新进程NextPage仍3969；保存receipt成功不算通过。原预期/hash保持，owned0。已通过wire-alias产物的实际MCP_PLACE也为0×0；首次路径指错产物根目录导致missing_design，定位output/design.dsn后结果保留。只初始化尺寸的修复假说被否定，D03问题仍open。

## 回归和进度

新增8host，202实际合同同步；544完整回归543通过/1原权限skip。34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active。说明见docs/page-bounds.md。未通过范围保持，安装/真实设计未改，无GUI或旧宿主派发重放。

第87–89批已推送develop至2800f75；本批完成后同步develop，main/alpha.1固定。后续继续图形CRUD/视觉及原34项完整门禁，不用边界控制点结果替代实际字形验收。

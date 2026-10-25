# 页面尺寸与声明图形边界

新增只读capture_get_page_dimensions(sessionId,pageId)及capture_check_page_graphic_bounds(sessionId,pageId,margin=0)，当前develop202工具；alpha.1固定包仍193。

## 原生尺寸

get_page_dimensions返回原生物理参数、GetSize、GetDocUnits(0/1)、单位比例、图框/网格/标题栏显示打印标志及边距。它们的坐标系不能混用：本机英制9700×7200的原始页参数对应970×720文档单位，公制12700×10160（pinToPin254）对应500×400文档单位。fullPageBounds以原生文档单位表示[0,0,width,height]，与本工具读取的图形页面控制点配套；不把PageWidth直接当页面图形坐标。

页面文档尺寸0×0时返回dimensionsKnown=false、fullPageBounds=null。checker明确报page_dimensions_unknown，不给空finding伪装成检查通过，也不自动修改或补造页尺寸。GetDocUnits(1)仅作为原始可绘制尺寸返回，不由它猜测实际打印原点。

## 检查含义

checker检查当前页支持的comment graphic声明控制点。默认全页矩形，margin为调用者明确声明的原生整数留白；边缘相等计入界内。输出每个界外控制点的objectId、kind、控制点序号、坐标和left/top/right/bottom侧别。同一坐标的文字锚点及声明框角仍按各自序号记录，finding数不是实际被裁切对象数。

它不读取渲染字形范围。文字声明框、椭圆/圆弧声明范围、Bezier控制点超界只产生候选发现；控制点在界内也不等同真实字形/曲线/打印裁切验收。完整对象/点数、跨页隔离和错误拒绝属于本工具验证范围。designPassed固定null；原生DRC、电气连接、元件/导线/标题栏/嵌套符号及实际打印区域另行验收。

最多4096图形、65536控制点、1000发现；超过预算或存在不支持图形明确失败，不返回部分成功。margin不能是布尔值，必须小于页面两个维度的一半。尺寸及图形缓存每次调用都校验不可变副本revision，源被改动或session关闭则拒绝。

## 已验证与未解决项

新fixture含英制/公制页面、精确边缘线、四侧越界线和文字声明框，共9对象/27控制点；无留白10条发现，留白10时16条，与写入前声明一致。其他页、空页、零尺寸页及非法/关闭拒绝均通过实际MCP。独立私有reader副本在已找到目标后注入页/视图迭代3969状态，均无结果发布，生产reader与源SHA保持；私有副本改动后缓存读取拒绝。

零尺寸不是导线3969的已证原因。六组尺寸初始化对照全部仍失败，且一个已通过导线页面同样为0×0，失败与原预期保留。该检查能力不代表该导线故障已修复。

官方依据CAP-REF p400–402和p416，另有安装内capAlignObject及capCustomizePage示例佐证单位区分。参考索引只公开路径/指纹与原创结论，不上传官方源码全文。D05/C05/V02完整门禁仍未通过。

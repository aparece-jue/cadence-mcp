# 原生新端口与层次图研发（2026-10-27）

对应原H03的fresh TOP/BLOCK_A/CHILD，原预期文件32f349f0..未改。不是完整H03通过或新公开写工具。官方本机Tcl/Tk Extensions PDF119页PlacePort、570–571页NetSymbolInstance、578–579页Port类型、273–274页PortOccurrence.GetFlatNet为依据。

## 端口创建和读取

固定认证宿主中的PlacePort导入官方CAPSYM.PORTLEFT-L，再明确SetPinType0/1与PlaceWire。前两次错误把NULL迭代后的1022当失败，故在加导线前停止；未保存的私有输出按围栏保留，后续只保存为取证、关闭并恢复宿主，原失败回执不改、输出仍未认证。第一次恢复脚本使用不存在GetActiveSchematic在保存前失败，改用原ROOT/MAIN数据库定位与逐步保存链的新恢复成功，失败证据保留。

独立对照：正常空白、四电阻及两份失败副本均在空NextWire后返回NULL/Failed/1022；DboState.Message明确At normal end of iteration。四类NextView/Page/Wire/Port真实终止一致。共享dbo_iterator.tcl只接受NULL/1022；非NULL1022或其他NULL错误仍拒绝。7项纯Tcl注入测试验证边界，不把它说成修复原NextPage3969。

PlacePort参数是符号放置基点，原端口热点100,100/300,100未改。独立读取OLB边界[0,0,30,20]及单pin[0,10]，由源几何计算放置点100,90/300,90，保存独立重开得到原热点。只验证零旋转/镜像，不外推任意符号/姿态。早期未补偿产生100,110等失败保留。

声明名和合并后的网名分开读取。GetName保留IN/OUT，DboNetSymbolInstance.sGetNetName在两者连线后均返回canonical IN。早期混用computed名称作为declared名称导致OUT丢失的诊断报告保留，不能回填oracle。最终两个端口及导线的原生DboNet对象身份相同，类型0/1正确；新服务MCP后续读取不依赖PDF或几何交点推断。

## 完整骨架已读回，跨层尚未闭环

从原固定fixture去掉会崩溃的空符号NewPort与独立导线构造，创建TOP/MAIN和CHILD/CHILD_PAGE、BLOCK_A、两边界引脚；C01重开2schematics/2pages/1part/2pins。固定编辑命令在子页新建端口/导线并保存，独立公开MCP核对父块位置400,300、IN400,320/OUT500,320、子端口100,100/300,100及根→BLOCK_A/Implementation CHILD结构，均通过；原图预期仍同一hash。

但父块引脚定义本地无导线，旧definition-net→net-occurrence路径及官方直接PortOccurrence.GetFlatNet都给NULL，原规则“父边界通过子电路连通”仍未通过。没有按同名或子页局部网合并父网，也未把层次树当作连接证明。新增ISS-H03-native-graph-parent-flat-null后移；完整public端口写任务、方向/缺失/同名/重复层次/嵌套及故障矩阵仍需要。旧NewPort构造器访问异常不宣称修复。

本批698回归697通过/1原权限skip；221个开发工具不变，alpha/release和已发布包不变。私有设计/日志留.local，公开摘要与hash见batch119。

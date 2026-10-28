# 元件线条与导线接触检查（2026-10-28）

开发工具capture_check_symbol_contacts(sessionId, partId)只读检查一个实际元件的线性定义边界与同页导线。复用经过本机验证的capture_query_part_vectors与原生wire inventory，不用缓存的元件包围框代替真实线条，也不依赖PDF。

当前profile symbol-wire-linear-contacts@0.2.0支持line、polyline、polygon、box的精确线段交叉、T接触和共线重叠候选，并检查简单闭合box/polygon内部的严格整段包含。非整数交点用numerator/denominator保留精确值。每项包含pageId/partId/vectorId/vectorSegmentIndex/wireId/wireSegmentIndex/contactKind和交点或重叠范围。曲线、文字、位图、Fill等保留skippedVectors；存在跳过项时linearBoundaryCoverageComplete=false。2000元件边界段、2000导线段、1000000配对、10000finding上限超限即失败，不返回截断成功。重复身份、外来part/page、非法坐标拒绝。

这不是完整避让或DRC结论。共享端点、自交/退化轮廓内部包含、实际笔宽/字形/显示属性/引脚图形/曲线填充/嵌套/occurrence均未验收；designPassed始终null、renderedClearanceVerified=false、electricalConnectivityVerified=false。正常引脚接线也需电气语义解释，不能因几何接触直接判短路或违规。输出是可追踪候选报告，产物hash绑定源revision；缓存命中仍复核不可变源。

## 实际原生/MCP验收

沿用原HALFADD三线三角形局部(0,0)-(40,20)-(0,40)-(0,0)。原位置600,400不接触；固定副本SetLocation至330,300之前冻结手工预期：350,310两次crossing、350,330两次T、330,310一次crossing。原生保存独立重开后，所有原28条导线的完整几何/原生net信息均与源完全相同；MCP准确0/5候选，同页仅15条导线段。另一页在同样区域有导线，未误计入，所有finding的wireId确属目标页。原本源文件保持。

混合13-vector元件明确保留5条非线性/文字/Fill跳过项，无空结果冒充避让通过。错误partId、缓存后owned副本改动、关闭会话拒绝，报告产物hash均通过。新增8项单元测试验证精确分数、T/重叠/共同端点策略、跨页、空与跳过、闭合边界、身份/坐标、退化段与配对预算。完整712项711通过/1原symlink权限skip；旧65工具发行白名单保持。

## 文字边界依据与遗留

本机官方capAlignObject/capObjectAlignment.tcl的GetDisPlayPropAbsCoord（367行）对元件display property把缓存框与owner location相加；该转换不能证明缓存框按字体重新计算。阅读原生索引与对齐脚本尚未得到已验收的独立字体重测/真实笔宽覆盖流程。本批只归档文件定位/hash和原创解释，不复制官方脚本。ISS-V02-clearance-bound-coordinate-qualification仍open，不将本新检查替代完整文字器件避让原范围。

开发223工具契约从实际stdio生成；alpha/release和现有版本保持，研发同步develop。证据implementation/batch-124-evidence.json，私有fixture/日志留.local；原34完整通过数仍6。

## 简单封闭轮廓包含增强（batch125）

对简单box/polygon闭合轮廓检查非退化导线段是否严格全部位于内部。两端都必须在内部，且整段不能与任何轮廓边接触/穿出；精确整数绕数与线段相交计算避免浮点误差。不能只检查端点，否则穿过凹缺口会误报。顺/逆时针一致，边上或退化段不计为严格包含。重复首尾/连续重合点归一化；自交、自触、折返、零面积轮廓不猜填充规则，skippedContainmentOutlines明确列出。simpleClosedContainmentCoverageComplete仅描述该项，不能覆盖skippedVectors中的文字/曲线等。轮廓简单性全局配对预算1000000，与原导线配对/finding预算分别限制。

包含候选ruleId=SYMBOL-WIRE-CONTAINMENT-CANDIDATE，contactKind=contained_segment，记录wireStart/End；vectorSegmentIndex=null，因为属于整个轮廓，不伪造接触某条边。该策略描述封闭轮廓内部位置，无论填充属性，不声称像素被涂满、实际笔宽覆盖或电气违规，设计通过值仍null。

真实私有副本新增100x100原生box，600,350时原导线640,380..660,380全部在内部、无边界交叉，准确1包含；移700,350对照0。另一个8顶点凹轮廓在600,350时，该导线两端各在左右内部，中途穿过645..655缺口，只报告645,380与655,380两次交叉、0包含；移700,350对照0。原28线完整几何/网名均保持，MCP页面控制点先核对冻结形状，再核对候选和artifact hash。

首次凹轮廓测试模板残留未使用的全局boundaryContacts=0，与预先约定两次交叉的场景矛盾。原报告虽passed，不作为完整验收：额外oracle-audit记录失败、原预期/报告hash和字节保留。新v2目录按每个场景逐项0/2交叉、零包含检查，几何/源预期不回填观察值。原0/5接触及混合5skip会话/改动保护另在新目录重新通过。

新增9测试覆盖严格内外/边界/顺逆序、凹缺口、非简单拒绝、归一化、32位大坐标、报告/跳过/预算。完整721项720通过/1原symlink权限skip。工具数仍223，契约仅增强已有检查说明，alpha/release不动。完整文字/笔宽/显示/引脚/曲线填充/嵌套/occurrence及原V02尚未通过。证据implementation/batch-125-evidence.json。

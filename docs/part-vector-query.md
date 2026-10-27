# 元件实际定义图形查询（2026-10-27）

新开发工具capture_query_part_vectors(sessionId, partId, cursor?, limit=100)是固定只读查询。数据绑定不可变DSN版本及已有partId，独立worker遍历GetDefiningPart.NewVectorsIter/NextVector，用既有typed descriptor读取局部定义，GetOffsetGraphicPoint转换实际控制点到页面。4096图形、65536控制点、262144文字字符、32MiB输出、10000游标边界沿用；分页1..1000，副本hash在读取前后和缓存命中时均复核。

每行包括objectId、partId、pageId、nativeTypeCode、kind、localDescriptor、实例位置/姿态和pageControlPoints。objectId为<partId>/vector-N，只在该revision/part内有效。nativeId明确null：本次原生GetId在定义向量返回1002，失败日志保留，最终不再调用该方法，不把1002当正常终止，也不捏造ID。首次遗漏shapePoint辅助函数的失败亦留证，补齐后独立读取通过。未建模的fill/嵌套等以unsupported行保留，不静默丢掉；已知描述器错误仍失败。

实际MCP八种姿态测试使用已有非中心定义框副本，调用前冻结三角形三线(0,0)-(40,20)-(0,40)-(0,0)及width80/height40、先镜像再四分之一转的源坐标模型；24条实际页面线段均匹配。人工定义框、缓存框和实际三条边分别保留，不用框替代实际图形。单项分页、分页大小不匹配/跨会话cursor、错误partId、缓存后源变更、关闭会话拒绝，以及全源/原oracle hash通过。

查询具备既有描述器的text/font和bitmap读取路径，但本批原生验收只覆盖三条line的八姿态；其他图形/位图/文本的本新入口矩阵尚未验收。controlPoints是几何控制点，不是实际曲线、笔宽或字形渲染边界。显示属性、引脚图形、嵌套/OLE、occurrence、完整文字器件避让和DRC仍未认证，不会自动返回避让通过。ISS-V02-clearance-bound-coordinate-qualification仍open，接下来需验证其他实际图形及显示/字体边界。

新增6个有效身份/归属/姿态/控制点/unsupported测试。完整704项703通过/1原symlink权限skip。开发222工具契约来自真实stdio，发行65白名单保持；alpha/release及已有包/tag未动。仅develop研发，不改安装或真实设计；原34仍6/34=17.6%。

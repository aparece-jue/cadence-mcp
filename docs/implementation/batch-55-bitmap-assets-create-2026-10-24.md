# 第五十五批：位图资产与公共创建

原34项必需验收保持1 baseline_passed、21 implemented_partial、10 deferred、2 planned，目标active。当前155个真实MCP工具；373完整回归372通过、1原文件符号链接权限skip，不将工具/测试数量当业务完成率。

## 创建实现

LibraryCreationVector单独增加bitmap声明，LibraryVector编辑replacement union不接受bitmap；已有位图几何更新继续使用bitmapGeometry。声明包含bounds/location、已授权sourceBmp绝对路径，以及独立expectedBmpSha256、expectedDibSha256、expectedDimensions和expectedDibSize。

bitmap_assets严格校验BITMAPINFOHEADER40、bottom-up BI_RGB24/32、planes、像素偏移/行对齐/长度、保留位、调色板及尾部数据；单BMP16MiB、宽高各4096以内，最多32声明，并按device引用估算完整图DIB累计64MiB预算。不支持的压缩、palette、top-down、其他header格式明确拒绝，未声称所有BMP格式可用。

计划前校验输入根与独立摘要，冻结复制到私有工作区，按文件摘要去重并记录来源manifest；计划绑定冻结路径及完整预期图，执行/验证重查冻结资产。最终规范化spec重新检查32KB限制；旧无位图计划形状保持。原生创建使用已在24.1私有探针核实的sMakeBitMapData/sMakeBitmap，保存后新进程读取完整DIB及定义/几何/样式/顺序图比较。原始BMP不再是执行时依赖；不提供任意路径写入、指针或脚本入口。工具契约已从实际stdio同步，工具数仍155。

## 原生与MCP证据

- bitmap-public-creation-20261024：RGB24/RGB32及旧9类基础图形三组实际MCP创建，各4个device-scoped view。创建期间移走本轮原BMP、随后恢复，独立重开摘要/尺寸/长度符合冻结预期，fresh apply/recover/open不重放，源和oracle hash保持。
- bitmap-independent-create-20261024：location=[7,9]与两view不同bounds独立声明原生持久化通过，证明没有暗中将锚点限制为边界左上角。
- bitmap-create-faults-20261024：冻结资产同长度像素篡改在native启动前拒绝，任务保持planned且无OLB；真实保存后丢回执fresh verify-only恢复/nativeCompletionVerified=false；启动取消/1秒timeout owned0；未声明ellipse保存后被完整图校验拒绝，open拒绝。
- bitmap-create-pixel-fault-20261024：创建后仅替换私有OLB内等长DIB像素，4view仍可原生重开、尺寸/位置/边界不变且读出替换后摘要；正式创建校验报library_creation_mismatch，fresh恢复、open和重放均拒绝，读取不改变产物hash。
- created-bitmap-placement-20261024：新建RGB24/RGB32库Normal/Convert共4次真实MCP放置，source/cache/实际view完整DIB和几何签名、引脚/热点/网络预期、保存重开、错误热点拒绝和fresh恢复不重放通过。

各目录均位于.local，完整report.json路径和hash见batch-55-evidence.json。

新增7项主机测试：24/32独立字节/头、格式/长度负例、重复资产与原图移除、错误独立预期、路径越界与冻结像素篡改、创建专用union和descriptor、持久计划资产保护。首轮重复aliased dict改写导致path_denied已保留test-bitmap-assets-initial-20261024.json；修复为改写前捕获全部已授权原路径，随后7 targeted与373完整回归通过。

## 保留范围与后续

位图创建/查询/保留/几何/删除/新放置已有公共证据，像素替换、更多格式及大图覆盖仍未完成。ISS-L02-bitmap-pixel-identity及完整L02/L04/D01未提升为整体通过。34项仍包括复杂缓存/变体、姿态与共享脚接线移动、3969、层次/总线/flat、原生DRC/仿真输入、PSpice完整求解/结果与端到端迭代、最终权限补测和统一回归。不能由本批绿色替代这些门禁。

后续收敛按Capture遗留、PSpice独立闭环、Capture→PSpice联调、最终完整验收四段组织，前两可交错推进。Allegro排除、PDF延期，Skills/规范引擎整合暂缓。无GUI、安装或真实设计修改，无提交推送。

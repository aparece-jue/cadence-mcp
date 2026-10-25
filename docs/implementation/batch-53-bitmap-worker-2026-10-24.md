# 第五十三批：受控位图字节读取、保留与放置

目标仍active。原34项必需门禁不变：1 baseline_passed、21 implemented_partial、10 deferred、2 planned。本批完成的是位图业务切片，不代表L02/L04/D01或整个Cadence业务完成。

## 实现与契约

新增内部`embedded_tcl`进程，加载配置安装中的tcl86.dll及固定仓库adapter。仅允许3个固定读取器及3个固定写入器，不向MCP提供脚本、eval、DLL路径或指针参数。参数使用Tcl对象列表传递，原有任务复制、指纹、Job管理、取消和恢复机制保持。其他业务继续原tclsh路径。

`bitmap_dib`依据24.1实际GetDib绑定，在同一进程读取HGLOBAL值包装和DIB块；严格检查64位SWIG本机字节编码、类型、包装长度、GlobalSize和GlobalLock，完成复制后解锁。只返回完整DIB的SHA256。单次16MiB、worker累计64MiB，包含重复视图读取；超限或不兼容ABI拒绝。该实现没有其他进程内存读取或原生地址输出。

`capture_query_library_vectors`增加六项bitmap descriptor：`["bitmap", bounds4, location2, dimensions2, dibSize, dibSha256]`，保留快照身份、draw order和游标契约。完整已建模库图、source/cache/实际placed view的签名均纳入位图像素摘要；不再依赖已证明忽略像素的IsEquivalent。纯line旧签名保持。

既有vector编辑可以删除bitmap；更新其他基础vector时验证未目标位图保留。公共位图创建、几何修改、像素替换和任意页面位图编辑仍未实现，不接受对应创建/更新声明。155个工具数量不变；真实stdio重新同步`contracts/tools.v0.1.json`中的准确说明。

## 实际验收

- `.local/bitmap-public-query-20261024/report.json`：A/B两图几何、尺寸及DIB长度相同而像素不同，查询摘要各与独立BMP DIB预期一致；shifted相同图仍一致；旧13vector库兼容。分页、错误游标、关闭会话拒绝，独立owned进程读取全库图及来源/预期hash保持通过。
- `.local/bitmap-public-edits-20261024/report.json`：改line保留bitmap、删除bitmap两项实际MCP任务；同名view的两引用均核对，保存新进程重开、fresh apply/recover/open不重放通过。
- `.local/bitmap-pixel-only-fault-20261024/report.json`：只在本次私有产物中将唯一56字节DIB替换为独立B图同长度数据。新Dbo进程确实能正常读出相同几何和B像素；正式完整图校验报library_vector_mismatch，open及重放拒绝。不是把打不开的文件当像素校验成功。
- `.local/bitmap-public-placement-v2-20261024/report.json`：含bitmap的Normal及原Convert两次真实MCP放置；原引脚/网络预期、source/cache/实际view完整签名、保存重开、错误热点预期拒绝、fresh恢复不重放通过。
- `.local/bitmap-public-group-20261024/report.json`：A.Normal含bitmap、B.Convert为旧图形，完整双单元同封装放置；错误预期拒绝、第二组保持原实例几何、pending取消及fresh恢复通过。
- `.local/bitmap-edit-faults-20261024/report.json`：真实保存后丢回执，fresh MCP只校验恢复且nativeCompletionVerified=false；真实启动取消、延迟worker超时均owned0；未目标Convert变化和终末产物篡改拒绝。延迟wrapper按新Python worker参数组织，不复用旧tclsh位置假设。
- 新7项主机测试覆盖实际字节复制/解锁、ABI拒绝、内存大小和累计预算、锁/复制失败、descriptor类型和固定adapter allowlist。完整361回归360通过、1原文件符号链接权限skip，无失败：`.local/regression-361-bitmap-reader-20261024.txt`。工具契约155项。

首固定读取尝试因命名空间内info commands相对名称检查而拒绝，已显式使用::cmcp::bitmapDigest；原错误记录在bitmap-reader-first-20261024.failure.json。首次放置准备缺spec.json，无写入启动；原preparation-error.json保留。补独立引脚声明fixture后使用全新v2输出验收，来源hash在fixture manifest记录。

## 未完成与下一步

ISS-L02-bitmap-pixel-identity继续open：字节读取/查询/保留/删除/新放置已验证，公共创建声明、几何编辑、像素替换和更广bitmap格式矩阵仍需完成。嵌套图形、字体quality持久化、缓存替换/变体、接线共享电源移动、3969、层次/总线/flat、原生DRC/网表、完整PSpice闭环等原遗留范围均保留，不以本批回归或工具数量代替门禁验收。

下一推进位图资产声明与受控创建、明确几何修改，再集中处理已有失败项。无GUI、安装目录或真实设计修改，无提交推送。

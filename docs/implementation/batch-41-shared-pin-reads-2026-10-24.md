# 第四十一批：共享脚读取与多单元DSN集成

2026-10-24。范围保持原34项；没有新增公开工具，仍137项。完整验收未完成。

## 已验证修复

官方 OrCAD_Capture_TclTk_Extensions.pdf 第522页的 DboPartInst.NewPinsIter 默认 bReturnShared=0。四个只读适配器 inspect、part geometry、page partition、net-symbol bindings 显式传入 IterDefs_ALL 与 bReturnShared=1，保留各单元的共享引脚记录。NC对象枚举、occurrence与其他写入适配器不在本次修复范围。

真实MCP shared-pin-reads-mcp-v2：同一缓存和U501基础位号的A/B单元，6条引脚定义、5个不同物理脚号，VCC8每单元各一条；两组热点与修改前冻结声明全部相符，源DSN hash保持。首轮脚本错用工具名 capture_query_part_geometry，失败报告保留；修正为已有 capture_get_part_geometry 后在新目录运行成功。

完整回归300项，299通过，1项原符号链接权限跳过。历史进程目录释放间歇问题仍未关闭。

## 实例集成与未通过项

独立修复后新运行 multiunit-group-shared-reads：同构A/B未连线用例通过定义全集、原有对象、U501A/B归属、缓存/包大小与各单元热点核对。不能据此声称已验证全部原有器件几何、occurrence或板级封装。

同构共享VCC接线用例保存成功，但原生pin-net及同一原生网络对象检查失败；异构A/B/P两用例均在CopyPackageAll返回Dbo1025，未保存。保留全部原失败报告，未重放账本或改变旧期望。此前忽略共享脚的报告仍为失败，不回填通过。

CopyPackageAll会把源GATE.Normal/Convert改成MCP_GROUPal/ert，源GetSuffix不能在缓存中直接保持。内部诊断采用唯一完整pin signature选择候选，包含position/name/type/visibility/start/hotspot；未比较装饰图形，因此不能作为任意复杂符号的通用来源认证，也未发布多单元写工具。

官方cap_ug/Making_Power_Pins_Visible.html说明隐藏电源脚的全局性质、实例级Power Pins Visible与设计级仅显示选项不同，多单元重复电源脚应全部设为可见再布线。本轮尚未验证按该实例设置处理后的实际连接，不能把现有坐标重合当作成功，也不能把page-definition的无net结论外推为完整flat/global语义。

## 后续

查明多cell复制的命名/来源规则；在新副本对照规范命名与显式电源脚可见性，逐项核验源/输出hash、定义/热点/原生网络。失败后移。L03、D01、D04及C01/C03整体状态不提升；原跨页/总线/DRC/网表/PSpice闭环及GUI产品确认问题保留。

所有输入来自私有夹具。未修改安装目录或真实设计，未进行GUI操作，未提交或推送。详细报告路径与SHA256见同目录batch-41-evidence.json。

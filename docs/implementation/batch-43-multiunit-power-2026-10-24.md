# 第四十三批：异构多单元显式电源网络与反例

2026-10-24。原34项范围保持；没有新增公开MCP工具，仍137。修改仅内部fixture和验收工具，未改公开业务Python/schema，沿用batch41完整300回归299通过/1原权限skip。

## 实现与独立预期

fixture_multiunit_group.tcl支持固定JSON wireAliases索引，显式给两组wire分别添加VCC/GND标量alias；无此字段保留原首wire VCC行为。无任意Tcl执行入口。probe_multiunit_power.py在修改前冻结全部原始定义/连接对象、三个新单元的物理脚表与热点、VCC三端引线+分段trunk、GND独立引线、两网名称和原有页器件几何。

3个新DSN副本共用该冻结oracle，只有请求分别设置正常、故意短接两网、将首VCC引线起点移开热点的断路；不根据输出生成或重写oracle。原source/OLB以及每个保存产物hash保持，owned进程0。

## 原生结果

- separate：全部定义、连接对象、A/B/P身份/同缓存包大小3、各单元实际热点、原有页器件geometry保持通过。三个VCC与5条wire同一非空原生net；GND与独立wire另一非空原生net，VCC/GND两组不同。
- short：保存成功，但definition和原生网络预期均失败，VCC/GND实际落入同一原生对象；反例被发现。单元身份/热点、原器件geometry、输入输出hash和冻结oracle保持。
- open：保存成功，但definition和原生网络预期均失败，首VCC断开；反例被发现。其他完整性同上。报告passed表示反例正确拒绝，electricalAcceptance明确false。

## 真实MCP读取

以separate输出创建新MCP工作副本，读到3units/8pin rows/6physical numbers/3shared VCC，完整name/number、多单元实际热点、显式power-net名和connected标志符合冻结预期。首验证脚本误假定公共未连接net为null，接口实际为empty string，保留失败报告；修正脚本与接口契约一致后在v2目录重测通过，不改变生产结果或冻结oracle。原生对象身份由独立native report证明，MCP名字读取不单独替代它。

## 范围与后续

这修复了batch42对无外接线GND的验证缺口，提供新的显式GND独立正例；batch42的原错误期望/失败不改，不将其重写为成功。不证明无外接线GND的完整全局语义或隐藏脚实例级可见性。L03/D01/D04/H02等整体仍未完成，仍需公共多单元持久写入、任意来源cache/view身份、封装变体、跨页/occurrence和完整DRC等原范围。

下步优先将库alternate view的来源选择接入现有公共放置业务，随后实现同包多单元持久任务，保持计划/幂等/恢复及独立保存重开门禁。GUI/simmgr待授权未变。没有GUI动作、安装/真实设计修改或提交推送。证据路径/hash见batch-43-evidence.json。

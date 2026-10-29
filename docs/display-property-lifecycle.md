# 显示属性创建/删除原生原型

2026-10-29，batch139。现有公开capture_plan_display_property只修改已有显示项布局；创建/删除尚未接入公开计划/任务。依据CAP-REF303页NewDisplayProp及170页DeleteDisplayProp，在用户自建库实例的私有DSN副本上先完成原生完整往返，不宣称MCP生命周期已完成。

独立预期为已有PCB Footprint数据值CUSTOM_00123，新增显示项位置[-40,60]（owner-local）、rotation1、displayType2、color0、Arial-11及完整14字段font quality1。创建前确认该显示项不存在，原生定位仍按partId和schematic/page/reference围栏。只有NULL与状态0或已知1002可视作缺失；其他错误拒绝。按NewDisplayProp及完整保存链保存，新独立会话读取后逐项核对。随后只调用DeleteDisplayProp，保存并新会话重开。

创建阶段所有实例user/effective属性、其他显示项、所有原字体/默认字体标记及定义/引脚网络保持；新增字体完整描述准确。删除后这些已建模状态完整回到原基线，PCB Footprint数据值仍存在。这是语义往返恢复，不是DSN文件字节相同，也不证明实体封装存在。原源及oracle保持，两原生worker均正常退出/owned0，无GUI或真实设计写入。

公开创建/删除计划、持久幂等/恢复/取消、负例及旧计划兼容尚待接入并验收，后续应复用当前任务保护而非暴露任意Tcl。原quality2保存失败、字体默认重置、渲染/occurrence等原E02要求保留；本次固定quality1不能替代它们。E02仍deferred，原34仍8/34。无生产/契约变化，最近732回归沿用，固定研究脚本编译通过。原始DSN/逐实例快照留.local，公开原创复现和hash见batch-139-evidence.json；alpha/release保持固定。

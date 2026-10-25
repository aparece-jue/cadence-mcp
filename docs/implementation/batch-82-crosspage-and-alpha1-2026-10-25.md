# 第82批：跨页缺失单元与首次alpha交付

capture_plan_cached_unit_add新增可选targetPageId，同schematic内从既有owner缓存补放缺失单元；省略时沿用原同页计划。原生writer分开定位owner页与目标页。跨页计划冻结全部原实例的已建模几何、有效/user/display属性，保存重开后独立比较；旧计划不追溯升级。共享物理pad进一步按同进程native网络对象身份核对，拒绝同名但不同对象的伪连接；不声称完整flat/occurrence验证。字体及未建模图形另列未检查。原生/主机资源上限保持，跨页全状态最多127个原实例。

普通B.Convert跨页与旧B同页原生验证通过；真实MCP跨页、跨schematic/陈旧页/不完整目标预期拒绝、新服务不重放/recover/open及终末篡改拒绝通过。新8host纳入完整516回归，515通过、1原符号链接权限skip。

供电P跨页原生保存成功但节点不符，失败输出/账本/原预期保留；只读审计确认所有原引脚不变，新P.8 VCC预期connected/VCC却实际unbound，新P.7 GND符合unbound预期。原失败保持拒绝，不将新观察写回oracle。第一次审计混入hotSpot键导致多列差异，只作诊断保留；v2仅比较连接字段，定位唯一8脚差异。新ISS-D01-crosspage-shared-vcc-unbound open，完整D01后移为deferred。

用户明确授权首次Git测试版提交/推送/发布，版本0.1.0a1/tag v0.1.0-alpha.1。193工具合同同步；隔离环境按固定依赖清单安装wheel，pip check通过；安装后的实际工具合同逐字段一致，Capture独立DLL查询、官方CLI新DC 2.5V及原生DAT读取通过。首次原创CIR示例.PROBE V(OUT)被原生拒绝（ORPSIM-15090）；改用已核实命名节点语法V([OUT])后，保持同一个2.5V/1e-6V oracle重测通过；原失败报告及输入保留。这是样例修复，不是求解器阈值放宽。

源码不含Cadence程序/官方手册/真实设计或私有验收数据。README仅增加测试版入口并保留历史正文；新增独立安装/客户端配置/推荐测试/反馈指南。wheel在独立环境安装，后续研发不影响固定alpha安装。测试版发布不等于完整34项验收通过；现6 passed/1 baseline/8 partial/17 deferred/2 planned，目标active。未改安装或真实设计，无GUI。本次提交推送仅依据用户此次明确发布授权。

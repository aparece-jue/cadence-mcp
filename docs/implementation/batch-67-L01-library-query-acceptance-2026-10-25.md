# 第六十七批：L01库查询完整验收与许可证复现边界

2026-10-25。目标active，原34项范围保持；本批无生产代码或契约修改。

## 许可证测试先行及后移

先读取安装内pcbInstall/chap8.html对CDS_LIC_FILE的端口@主机说明。固定私有测试仅对子进程环境副本把该变量设为本机绑定但未监听的随机端口，分别调用非交互CLI和固定原生Setup，再执行未覆盖变量的CLI对照。没有更改父进程环境、系统变量、安装文件或实际许可证服务器，也不读取/输出用户实际许可证地址。

`.local/license-child-probe-20261025/report.json`三项都正常退出并输出本次文件；父环境和原source保持。测试未能建立“真实许可证不可用”条件，没有明确原生许可证失败诊断，所以不能认证license_unavailable；也不能认定一定忽略变量或一定使用了缓存/其他服务器。该项保持open并按用户要求后移，未改全局配置强迫故障，继续独立L01验收。P02整体不通过。

## L01官方依据与原要求

原标准：“官方库副本与自建库正例；多单元、引脚映射、分页、陈旧/越界与重复读取”。已核对CAP-REF第591页DboLibPart.NewLPinsIter、第724页DboDevice.GetPinNumber(position,...)及shared/swap映射；逻辑位置必须按对应device解析物理脚号，不能直接当物理脚号。

采用官方ANALOG.OLB和原先自建单单元、共享脚双单元、异构A/B/电源单元三个OLB。自建库来自`.local/library-part-variants-20261024`，沿用创建前声明生成的原expected.json及其hash，不从当前查询构造期望。

## 实际完整验收

`.local/library-query-closure-20261025/report.json`四组真实178工具MCP全部通过：

- package/device/cell/part/pin五类实体全部limit3分页，计数/唯一ID及父归属一致；官方26package/26device/26cell/26part/81pin维持原基线，R物理脚独立预期为1/2。
- 三个原创库的package名称/size/homogeneous/footprint与原声明一致；每个device/part视图范围及全部pin的position→physical number、name/type/visible/shared/swapId/hotSpot逐项匹配原预期。
- 明确分别记录视图pin行数和uniquePhysicalPins，Normal/Convert及共享脚的重复行不冒充新增物理焊盘；device-scoped cell视图不冒充全局去重对象。
- package精确筛选/缺失与前缀空结果、改变limit或跨libraryId复用cursor拒绝；独立新worker打开后全实体结果相同，另两轮打开/关闭计数保持。
- 仅破坏MCP私有library.olb副本后查询target_changed，陈旧会话仍可close，关闭后查询session_lost；所有官方/原自建源及原oracle hash保持。

`.local/library-boundaries-20261025/report.json`另7项真实反例通过：直接越过read-root、Windows目录junction逃逸、非OLB扩展名、未知会话、limit0/1001及不支持entity均拒绝。目录联接只指向本批私有outside文件夹；合法源及复制源字节保持。

## 状态与范围

L01按原条件标记passed。旧remaining中“待L02/L03自建/异构正例”已由既有原始声明库当前重读补齐；全glyph绘制、全局/跨页符号嵌入、外部PCB封装几何和原DSN放置连接问题归各自门禁，本批不替它们结案。查询返回readOnly=true、externalFootprintVerified=false仍保留。

34项现4 passed、1 baseline_passed、17 implemented_partial、10 deferred、2 planned；整体仍active。生产/契约第66批摘要保持，沿用429完整回归428通过/1原文件符号链接权限skip，未把skip计通过；本批仅新增真实专项，不重复无变更的整套回归，178工具保持。无GUI、无安装/真实设计改动、无提交推送。

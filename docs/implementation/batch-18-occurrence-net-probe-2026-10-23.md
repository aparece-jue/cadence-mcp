# 第十八批记录

## 第十八批层次网络探测与单元物理脚专项

- 新增内部inspect_occurrence_nets.tcl与原生探测脚本，不开放MCP。按本机手册p273/529–530/545/596/626/628/642/651及官方capShortedDiscretePart.tcl、capPhysicalShortedPackShort.tcl，读取port occurrence -> port instance -> page net -> schematic net -> parent net occurrence -> flat net。原生对象指针仅在worker内部映射为临时ID，不按名称合并网络，不修改/保存DSN。
- FULLADD读取16occurrence、69port记录、18flat对象，包含层次块端口和隐藏电源。这是runtime探测计数，不是全连接表的独立验收。初次GetPinNumber在halfadd_A报1021；细分phase后确认是层次端口无物理脚号，不是GetNet的未连接状态。内部探测保留numberStatusCode，不能泛化所有1021。
- 发现U1C occurrence通过GetPortInst/GetPinNumber仍得到definition B单元4/5/6；GetPathNameNumber同样不能替代occurrence物理映射。采用occurrence.GetDesignator + placed package.GetDevice(designator) + pin logical position -> device.GetPinNumber，得到C单元9/10/8及共享14/7。
- `tools/verify_occurrence_pinmap.py`读取已保存的FULLADD原生证据，与TI SN74LS32官方14pin脚表独立核对A/B/C。将U1C强行换回definition脚号的负例被拒。`.local/occurrence-map-accept-20261023/pinmap-verification.json`通过，范围仅selected_ls32_occurrence_physical_pin_map；不能代表全H02、heterogeneous cell对应或全封装共享冲突已验收。外部依据：https://www.ti.com/document-viewer/SN7432/datasheet 。
- 联合专项`.local/occurrence-map-accept-20261023/report.json`仍失败：既有电阻连线副本GetNet非NULL而GetSchematicNet为NULL，错误阶段schematic_net；原生退出1、自有进程0、源和副本hash均保持。没有跳过该节点/按netName拼接/强制声称未连接。ISS-H02-null-schematic-net新增open，H02 deferred后移；FULLADD API探测通过不能覆盖此失败。原生网络初始化/新页生命周期原因未查明。
- 本批只新增内部适配器/探测及验收资料，公开工具仍89；最近完整回归仍230项229通过/1原symlink权限skip（第十七批报告，不冒充本批新运行）。无GUI、安装/真实设计修改、提交推送。34原始大项及全部验收要求保留。下一独立D02器件姿态/删除、E04文档生命周期、H04及V03。


# 第四十二批：多单元库命名与电源可见性对照

2026-10-24。不改变原34项范围；无公开业务生产代码/schema变化，仍137工具；最新全回归仍batch41的300项299通过/1权限skip。

## 独立对照

新工具probe_multiunit_naming.py从batch40冻结spec读取，构建同构/异构各hidden/visible两份新库。cellName包含packageName前缀，partName使用完整cellName加.Normal/Convert；visible组只将VCC/GND的声明可见性改为true。全部4份OLB通过完整声明图、新进程读取、源spec与产物hash保持、owned进程0。首轮报告误用exclusive write_json，第二例后写report失败，原不完整报告保留；v2完整运行成功。

两组分别以新私有DSN执行未连线/显式VCC布线4例。hidden组同构/异构未连线通过，两个布线失败。visible组同构未连线、同构布线、异构未连线通过，异构布线整体失败。所有失败保持原报告false。

命名前缀对照中CopyPackageAll不再返回1025，缓存保留MCP_GROUP[_CELL].Normal/Convert且异构A/B/P单元身份、全部热点通过。该证据证明当前命名构造可以复制，不证明任意用户库命名可直接复制，也不证明本机内部实现或唯一根因。公共库创建仍接受此前任意合法名称，未静默改名/限制用户输入；通用来源绑定和完整装饰图形认证未完成，仍无公开多单元组写工具。

可见同构VCC8的两单元与3条wire同一非空原生网络，定义全集/连接对象/身份/热点/保存重开全部通过。hidden版本相同坐标仍失败，符合官方Making_Power_Pins_Visible说明的可见性与连接区别；本轮未验证原隐藏库的实例级Power Pins Visible设置。

visible异构布线的三个VCC与5条wire已属于同一非空原生网络，连接对象、身份、热点通过，但未布线GND7由原生读取报告connected/GND而冻结预期为unbound，故definitionMatches=false、整体false。不能从观察值回填旧预期为通过。下一步新增显式独立GND线路和事先声明的完整电源/信号网络，验证VCC/GND隔离与原有网络保持，再研究无外接线电源脚/flat语义。

真实MCP额外读取异构未连线副本：3单元、8条pin定义、6个物理脚号、VCC8三条及全部冻结热点通过，源hash保持。smoke_shared_pin_reads.py按输入冻结expected支持不同单元/脚数，未用实测生成期望。

L03/D01/D04等整体仍partial，原34项与历史失败不变。无GUI操作、安装/真实设计修改、提交或推送。证据路径/hash见batch-42-evidence.json。

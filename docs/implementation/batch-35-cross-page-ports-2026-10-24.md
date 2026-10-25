# 跨页网络与官方PortSymbol初始化对照

本批内部原生fixture与诊断，不新增公开MCP工具。原34项完整范围不变，未通过项不计完成。

## 官方依据及预期

本机`doc/cap_ug/Placing_Off-Page_Connectors.html`规定同一schematic folder内同名offpage连接，不同folder同名不连接；`Assigning_Net_Aliases.html`规定连接名称比较忽略大小写。Tcl/Tk手册p194/222为typed PortSymbol getter/save，p463及既有创建接口支撑页对象，p569–572支撑热点/网络，p637 UpdateNetAndPorts用于显式独立内存初始化对照。

新建TOP/PAGE_A、PAGE_B，每页4个独立短导线及符号，expected.json在原生写入前固定：同名offpage共享flat net、异名offpage独立、同名global共享且isGlobal=true、大小写不同offpage共享，总8wire/5flat groups。按root page wire→native page net→schematic net→root net occurrence→flat对象分组，禁止按名称合并来证明预期。

## 结果

跨页fixture完整save成功、原进程exit0/owned0，但plain与UpdateNetAndPorts两次独立读取均在GetSchematicNet得到NULL而失败。该初始化仅在读取进程内，无save，源DSN hash保持。原生页绑定读取另失败3969。没有证明任何跨页连接成功；保存文件不等于连接验收。

独立端口对照用私有capsym.olb的PORTLEFT-L(type34)，CopySymbol到新设计后typed getter创建IN/OUT，逐调用记录NewPort及SetPinType，再建立CHILD wire、parent BLOCK_A/Implementation和两个边界pin，完成save。此路径越过原空NewPortSymbol访问违规阶段，tree reader成功看到BLOCK_A及CHILD implementation；但definition、objects、bindings失败，子图连接/热点/方向均未验收。原始空符号崩溃尚未定位修复，H03不能关闭。

在两份已经保存的DSN上追加只读trace，都定位NextPage/status3969；各一次GetRootSchematic预初始化仍失败。不忽略3969，不按观察值修正原热点/网络期望。与历史bus症状相同，未证明共享根因。按授权失败后移，推进独立V04仿真输入生成调查。

## 证据

- `.local/cross-page-20261024/report.json`：新建跨页fixture/两种flat读取均失败及原库/private hash。
- `.local/hierarchy-copied-ports-20261024/report.json`：官方符号复制/完整save成功，tree成功，其余读取失败。
- `.local/cross-page-read-trace-20261024/report.json`、`.local/copied-port-read-trace-20261024/report.json`：NextPage3969只读定位。
- `.local/cross-page-root-init-20261024/report.json`、`.local/copied-port-root-init-20261024/report.json`：root预初始化未解决，源hash保持。

上述6份报告整体均false。batch-35-evidence.json另核对两份当前DSN hash等于保存时hash、所有自有进程0、最终原创脚本hash；完整性不提升失败验收。旧报告、原设计和预期不改，不重放。

本批未改变公开Python实现/schema，未重复已有全回归；工具仍137，最新294项293通过/1文件符号链接权限skip，历史目录句柄问题仍open。H02/H03/H04既有问题附新证据，D04仍partial，全目标active。无GUI、安装目录/真实设计修改或提交推送。

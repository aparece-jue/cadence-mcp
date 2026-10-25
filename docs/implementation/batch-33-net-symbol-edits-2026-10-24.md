# Global/offpage编辑删除：原生专项

本批推进D04完整生命周期，不改变原34项最终退出条件。公开工具仍132；这里只增加内部固定JSON诊断，无任意Tcl/eval入口，无GUI、安装目录或真实设计修改、提交推送。

## 官方依据与输入

本机24.1 Tcl/Tk Extensions PDF：p463 Page.DeleteGlobal/DeleteOffPageConnector，p572 NetSymbolInstance.SetLocation/Disconnect，p576 Global.SetName/Rotation/Mirror，p577–578 OffPageConnector.SetName/Rotation/Mirror；p570 GetNet/GetOffsetHotSpot。接口声明不等于工作流通过。

输入是batch31已有带短引线的global/offpage两份私有DSN。每次复制到全新case目录，绑定qualified schematic/page、native ID、oldName/origin/hotspot/rotation/mirror；释放iterator后修改并执行page/schematic/design完整保存链。读取均为独立原生进程。

## 验收与结果

预先写入expected.json：全definition结构、精确连接对象语义、所选页全部器件姿态/热点及native pin-wire分区。仅目标wire group允许自动网络名，非目标网络名和所有pin-wire成员关系必须保持；改名有明确新网络名。浮动符号不能继续共享wire/pin net。没有跨页flat-net或DRC认证。

|操作|Global|Offpage|
|---|---|---|
|改名|通过|通过|
|删除|通过|通过|
|移动|失败：位置正确但残留原网络绑定|失败：修改阶段DboState1|
|旋转|失败：热点不符合声明模型|失败：修改阶段DboState1|
|镜像|失败：热点不符合声明模型|失败：修改阶段DboState1|

原始10例中4通过、6失败，report整体false。改名/删除是内部原生证据，未通过公开MCP持久计划、幂等、取消、恢复、篡改等任务生命周期验收，故不宣称公开编辑功能完成。

移动Global热点从(240,310)到(240,410)，保存重开后仍与旧短引线和R101.1同一native net。独立Disconnect返回1后再移动的试验依然残留绑定；Offpage对照依然DboState1。两次Disconnect用例整体0/2。不能忽略状态、用名称或几何关系代替native连接证明。旋转/镜像模型与更新机制尚未校准，不据此断言某原生函数缺陷。Offpage阶段含多个setter，尚不能归因到具体方法。

## 证据与保留

- `.local/net-symbol-edits-20261024/report.json`：首次harness把case放到配置workspace外，10例在写入前由路径guard拒绝；原失败保留。
- `.local/net-symbol-edits-v2-20261024/report.json`：全新副本原生10例，4通过。
- `.local/net-symbol-disconnect-20261024/report.json`：独立断开对照2例，均未通过。
- `.local/net-symbol-edits-v2-20261024/integrity-audit.json`：只读核验12例输入不变、已保存输出hash相符、未保存副本保持、自有进程0、原失败reports不变。此审计不重新接纳失败。

最初两个执行版本的harness以exit0结束，但以report.passed=false为验收依据。之后脚本补上非通过exit1及adapterSha256，并加强浮动符号不共享任何page pin/wire group的检查；未重跑、未改旧report，不把后续脚本字段冒充旧执行证据。batch-33-evidence.json冻结本批最终脚本hash。

新增3个open issue：ISS-D04-symbol-pose-retained-net、ISS-D04-offpage-pose-state1、ISS-D04-symbol-pose-hotspot-model，按授权移队尾。下一推进独立改名/删除的持久MCP集成和跨页原生fixture，最终仍须修复全部遗留。

本批未修改已有公开Python/schema，故未重复全回归；最新仍291项290通过、1原文件符号链接权限skip，历史目录句柄问题保持open。D04仍partial，全目标active。

# 第五十六批：新设计导线3969集中诊断

本批没有修复3969，也没有提升任何业务门禁。只增加私有定型诊断adapter/工具及证据，生产读取器、写入器和155工具契约保持第五十五批hash；因此沿用373回归372通过/1原权限skip，没有无变更重跑整套测试。34项仍1 baseline_passed、21 partial、10 deferred、2 planned，目标active。

## 定位结果

native-page-status-text-20261024对空新设计、失败新导线设计及成功既有导线设计逐步检查。三组GetDesignAndSchematics、GetRootSchematic、NewPagesIter均code0；只有失败组首次NextPage为3969/Failed1/Severity2，同时返回非NULL。Message和GetExtendedText在独立基础解释器均为空，不能据此推断错误含义。生产check没有忽略任何错误。

首诊断probeError误承接catch成功返回值的列表，之后修正仅在rc非0时记录；初源码保留。该字段不影响原native状态记录。原source哈希均保持。

## 同一冻结预期的对照

所有构造对照预期固定ROOT/MAIN、0parts/0pins以及唯一导线[[100,100],[300,100]]。不能仅因不报错而删掉导线预期。

1. new-wire-constructor-matrix首轮在保存前被诊断性page.GetId的1002中断；原报告和源码保留。后续只将这个不受支持的诊断字段单列，并保持所有生产错误检查。
2. new-wire-constructor-matrix-v2六组：默认、完整显式bNewVersion0、显式color/style/width0都保存成功，但重开仍3969；bNewVersion1的三个分支NextPage变code0，却没有持久导线，严格拓扑预期全部拒绝。
3. new-wire-initialization-matrix七组：ConnectInitialization、ClearCreatedByDB、CleanupQuad和额外NewNetScalar均未解决；显式NewConnection在初始化时报1041。bNewVersion1创建时GetWireCount即0，bNewVersion0为1。这解释了前者为何不能当修复，但不声称已定位3969根因。
4. design-serialization-versions：空新设计、失败设计和成功既有设计的session data/design/interface分别2/4/10，design data/save-as均2、formatVersion均3.2；这些是数据库字段而非产品版本，未发现对照差异。
5. new-wire-expansion-matrix四组：保存前/创建导线前执行官方DboSchematic.Expand均返回成功，保存后仍3969；GetRootOccurrence成功且非NULL，也未解决。
6. new-design-constructor-matrix三组：默认CreateDesign、显式SCHEMATIC rootType、CreateDesign(name,state)+NewSchematic+SetRoot均保存成功且创建时1wire，重开仍3969。

上述default状态、构造参数、创建时导线字段/网络为空、进程退出信号、自有进程0、独立读取结果及不可变expected.json均保留。构造/初始化/展开/设计创建共20个有效对照（含每组重复baseline），无符合全部预期的通过项；首轮6个因诊断字段提前停止另列。各目录完整路径和hash见batch-56-evidence.json。

## 结论与后续

官方依据为本机CAP-REF147-148(DboState)、179(CreateDesign)、223(NewSchematic)、258(SetRoot)、354(Expand)、431-435(NewWireScalar)、494-496(连接初始化/清理)及对应已核实runtime binding。外部检索未取得可解释该错误的有效资料，没有将无关结果作为原因证据。

ISS-D03-new-design-wire-reopen继续open，相关E04/D03/H04/V04等完整门禁不能借本批提升。不能使用bNewVersion1丢弃对象或吞3969来制造通过。当前只排除了一批候选初始化/样式/版本路径；原失败DSN、账本、预期全部保留。

按用户失败后移的顺序，将3969保留队尾，下一推进独立PSpice AC/非零复数DAT与新求解关联验收，再回头集中处理设计序列化/网络数据初始化。无GUI、安装或真实设计修改，无提交推送。

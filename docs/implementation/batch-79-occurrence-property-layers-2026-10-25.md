# 第七十九批：component occurrence属性层与根访问异常

2026-10-25。新增只读capture_get_occurrence_properties，实际193工具。原H01范围不变，完整门禁deferred并移队尾；不以组件属性切片代替根/递归/资源验收。无GUI、安装/真实设计修改、提交推送。

## 依据与实现

本机Tcl参考165页DboBaseObject.NewEffectivePropsIter/NewUserPropsIter；625页DboInstOccurrence.GetPartInst及children/reference路径；位号按实际类型区分DboPartInst.GetReference基础位号与DboPlacedInst.GetReferenceDesignator/DeviceDesignator完整单元。根是design context，不能当placed component处理。

从现有session/revision层次快照选occurrenceId，再用完整instancePathSegments逐层找唯一子单元，不用会折叠共享位号的raw path选对象；原生raw/hierarchical路径同时核对。固定JSON请求和固定Tcl调用，无eval/任意脚本。深度64/访问10000/每层512属性、值16384字符、合计8MiB及输出16MiB限制；effective/user迭代的非1022异常不作为正常结束。

返回occurrence effective/direct-user与对应即时definition effective/direct-user分开列表，以及definition nativeId/base/full/device/kind。没有根据值相等自动判定完整继承来源，propertySourceResolutionVerified=false；外部库全链、typed用户值、显示层及occurrence pin-net仍不认证。旧capture_get_hierarchy保持接口和根属性未认证边界。

## 原生覆盖/隔离验收

原副本的halfadd_A/U3A和halfadd_B/U3C对应同一实际definition，放置单元为U3A；occurrence位号不同，不用定义位号错误合并它们。创建前冻结独立期望：定义MCP_DEF_TAG=DEF_SHARED；两occurrence的MCP_SCOPE_TAG分别为A/B开头的中文、[x]$;及换行文字；只有A侧Value覆盖OCC_A_VALUE，B侧保持源定义原Value。

定型私有fixture NewUserProp后完整保存page/schematic/design，独立重开按上述逐字验证。两个occurrence的直接user和effective分别保留各自标记，definition不含该标记；定义DEF_SHARED被两occurrence有效读取；A的Value覆盖没有污染B或definition。相同definition nativeId/full unit身份与原定义/引脚网络基线保持，源原DSN与冻结expected hash保持。没有发布occurrence写入工具。

实际MCP两路径、完整schema/readOnlyHint、中文特殊字符/空值模型、3次重复读取、独立再次打开、源工作副本变更拒绝及关闭后拒绝通过。根及未知occurrence在生成原生属性request前拒绝；7host测试亦验证根路径不会调用worker。

## 原根访问失败与后移

首只读原型对root effective/user属性层读取时，独立Tcl进程返回3221225477（访问异常），没有属性输出；相同原型之后读取两个组件路径成功，源hash保持。尚未定位是哪一个根原生操作出错，也未证明SDK不支持。原失败报告、原DSN及原始root请求保留。现Python入口和固定Tcl双重拒绝root，不返回空列表伪装成功，也不反复启动已知异常绑定。

记录ISS-H01-root-property-native-access-violation为open，完整H01由partial转deferred并移到队尾。根正确对象/属性入口、空/递归native夹具及完整资源/继承来源边界仍待完成。原ISS-H01-native-path-identity已解决的历史范围不重写；组件属性读取通过不关闭根问题。

## 基线与复现

新7host；495完整回归494通过/1原文件符号链接权限skip，无失败；193实际stdio契约同步。34现6 passed、1 baseline、9 partial、16 deferred、2 planned，目标active。工具prepare_occurrence_override_fixture.py --install-root/--workspace-root/--source生成私有覆盖夹具（输入为原共享NC/完整FULLADD样例副本），smoke_occurrence_properties.py --install-root/--workspace-root/--fixture-root验收读取；workspace-root均需新目录。原生及MCP报告在.local/occurrence-overrides-20261025与occurrence-properties-mcp-20261025，摘要见batch-79-evidence.json。

# 原生用户属性模型与独立属性保存

2026-10-28，batch128。L04保持部分实现，原34项仍7/34（20.6%）；没有把平台限制或局部测试算作整项通过。

## 官方模型

安装内`doc/capinfomodel/dboimnew.html`（CAP-MODEL，指纹见批次证据）在`pgfId-1000517`区分多类型DBProp；`pgfId-1000520`说明UserProp为用户添加的Name/Value对，并明确：“The Value is limited to a string.” `pgfId-1000640`的Value字段为StringT。内置有类型属性与用户字符串属性是两套模型。

因此用户属性接口保留严格字符串输入，不自动转换数字、布尔或空值；空字符串与删除不同。查询新增userPropertyValueContract说明。过去DboValue类型2/1/3/6/16写入后变成type0的失败记录保留，不追认为类型持久化成功；临时值setter的Code1/Failed1也不改判。关闭的是未知平台约束调查，未实现非字符串UserProp或通用有类型DBProp写入。

## 保存缺陷与修复

第一份固定预期要求仅新增五项用户属性，不修改固定字段。原生返回saved=true，但独立重开仍只有六项旧属性，严格图比较以library_package_mismatch拒绝。失败plan `af3a2c52e88a4048a36a41dac0b228c9`、原预期和输出保留，未重放。

修复在保存前显式标记package修改、调用library/package的void重载，再标记library修改，继续原MarkAllLibForSave/SaveLib链。DboBaseObject.MarkModified及DboLib.MarkModified的状态检查保留；void重载不调用Failed。依据Tcl扩展手册165/200页，不放宽保存后的严格比较。

新目录新计划中，`00123`、`1e3`、`False`、空字符串及中文均按原文本/type0保存重开；六项原属性保持。实际MCP另行通过纯修改、纯删除、幂等、跨服务只验证恢复及原生输出指纹不变。数字/布尔/浮点输入在建计划前拒绝。所有操作限私有OLB副本，无GUI、安装或真实设计写入。

新增两项测试覆盖文本不被解析和非字符串拒绝；专属12项通过。修复后完整回归723项，722通过、1原符号链接权限跳过。第一次测试准备错误在原生派发前失败并留证。工具仍223，契约仅两处描述更新，输入输出schema未改。

原始运行数据留`.local`，不上传Cadence手册或OLB。复现脚本、来源索引与SHA256见[batch128](implementation/batch-128-evidence.json)。后续仍需按原L04要求审计其他属性、变体、缓存、渲染等缺口；本轮不晋级alpha/release。

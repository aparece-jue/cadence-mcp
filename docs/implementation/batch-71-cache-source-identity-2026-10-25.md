# 第71批：缓存来源限定与替换前置验证

日期：2026-10-25。L05保持implemented_partial，原34项验收条件不变。本批补齐替换之前必须成立的缓存身份定位，并只读复验原替换输出；没有公开缓存替换写入工具。无GUI、安装/真实设计修改，无提交推送。

## 官方依据与原生确认

CAP-REF第198/199页定义GetCachedPackage(SourceLibName, SourcePackageName)及DboLib.GetSourceLibName；第283页定义DboLibObject.GetSourceLibName/IsCachedCopy；第529/530页定义PlacedInst.GetPackage和来源字段。第206页ReplaceCache参数仍需在后续写入中结合实际实例保持验证，不能仅因参数名preserveRefDes就相信它能保持位号。

`.local/cache-binding-probe-20261025/report.json`在原自建夹具副本确认：按源库+包名查询的缓存包与PlacedInst实际包是同一原生对象；只按包名GetPackage取得的同名本地包则不是。两个来源读取方法都返回预期来源且状态0，源和副本hash均保持。

## 公开读取契约与实现

新增只读capture_query_cache_binding(sessionId, partId)，实际179个MCP工具。固定新扫描器在同一原生进程内耦合完整缓存定义、来源及实例绑定，内部比较对象身份；不把原生指针暴露给客户端。再用独立实例清单交叉核对全部placed实例覆盖、nativeId、scope、来源和device/view，拒绝缺失/重复/错配数据。

返回revision绑定的实际cachePackageId、源库/包/part/device字段、精确被绑定包的定义子图，以及同名本地/缓存条目的区别。源路径作为DSN内部存储的身份键使用，不据此访问文件系统或打开外部库。sourceQualifiedPackageIdentityVerified=true仅认证内部绑定；externalSourceLibraryVerified=false和cacheSynchronizationVerified=false明确保持。

新读取器与旧capture_query_cache共享同一session内的定义ID。若已有快照与新扫描的遍历身份不一致，拒绝混用并要求新会话，不静默替换旧ID。每次读取包括已缓存读取仍检查源revision。drawn/hierarchical实例没有placed包绑定，明确拒绝，不能误归同名库包。

## 实际验收

`.local/cache-bindings-mcp-20261025/report.json`：原prepared夹具及原replace0/replace1两份输出全部通过。每份检查R101/R102精确来源和共享同一缓存包、源pin名称、完整定义子图、先旧查询后新查询的ID一致性、重复读取稳定性。同名本地/缓存各一条的歧义被正确区分；同页U3A/U3B共享位号但nativeId/device不同，均独立定位。drawn、外来对象/会话、关闭和实际篡改工作副本后的陈旧读取均拒绝。三个原源文件及预写期望hash保持。

`.local/cache-source-qualified-audit-20261025/report.json`：只读复验两份原替换输出，不重放、不更新原失败账本。先从原source-with-overrides和原request构造期望，再核对：

- 只替换精确来源的旧缓存条目，新绑定包完整逻辑元数据与选定源OLB包一致；未目标缓存条目的已建模逻辑元数据保持，同名本地条目保留。
- 所有实例有效属性多重集保持，仅两目标的四个明确来源/Graphic字段按原声明改变；R101封装覆盖、R102 Value覆盖保持。
- 两个输出各R101/R102共4次实际放置视图与源符号比较通过，每个2脚/8条线。
- 原源DSN、源OLB、两份输出及本次期望摘要保持，原历史report仍false，未追溯改判其执行回执或原始失败。

本审计尚未认证全部显式属性来源/继承规则、显示层和未目标图形内容，也未认证多单元替换或公开持久写入流程。ISS-L05-native-replace-preservation继续open。

新增5项host测试覆盖重复包名、外来源/本地误选、scope/nativeId/device/view错配、缺失/重复来源及实例、严格flags与分离快照。首448回归仅因旧工具总数断言178未更新而失败，保留`.local/regression-448-cache-bindings-20261025.txt`。更新为实际179并新增新工具readOnlyHint/required参数检查后，最终`.local/regression-448-cache-bindings-final-20261025.txt`为448项、447通过、1原符号链接权限skip。实际契约同步179。

## 后续写入工作

按本批源限定绑定展开完整受影响组，而非只改传入实例。冻结原DSN/新OLB/旧新完整引脚声明、所有实例属性和身份/几何/连接及来源明确的缓存图；先核实显式覆盖与继承来源的读取和恢复方式。采用固定worker在新副本内替换、恢复确证的位号/覆盖，保存后独立重开比较，接入plan/apply/jobs/cancel/recover及verified-only打开，严格不重放已开始写入。

完整L05仍要求多单元/变体、属性来源/覆盖、不相关状态、旧新引脚和必要故障等原条件；本批身份查询和历史只读审计不能代替这些。34状态保持5 passed、1 baseline_passed、16 partial、10 deferred、2 planned，整体active。

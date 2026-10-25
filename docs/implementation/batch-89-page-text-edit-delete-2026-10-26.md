# 第89批：页面文字完整更新与删除

2026-10-26，对应D05/C05；新增capture_plan_graphic_text_edit，实际200工具。既有graphic_text持久任务family和apply/jobs/cancel/recover/open入口复用；旧新增计划缺operation按add处理，旧receipt匹配仍兼容。

## 实现与官方依据

CAP-REF p708–709的定义层SetText/SetFont/SetLocation/SetBoundingBox，p464的Page.DeleteCommentGraphic。plan绑定不可变session、图形objectId、页内index及nativeId；只接受text类型。update要求完整替换文字/页面锚点/局部框/font，严格rotation/mirror；delete不接受change。预览旧图形和新声明。原生读取迭代器释放后再更新或删除，不访问已删除对象。原生操作固定，无任意方法/脚本/指针入口。

更新在原定义对象上修改文字、全字体和坐标/姿态；删除只移除选中comment graphic。冻结所有支持页的完整有序图形及原已建模实例/定义/连接摘要，结果只允许选中行替换或移除，其他行顺序/重复数/几何保持。回执operation按实际add/update/delete精确匹配，删除结果单独标记graphicRemovalVerified。

## 真实MCP与独立检查

- 私有原fixture有32混合图形，其中4段相同文字。8种旋转镜像更新第二段文字，以及首/中/末文字3删除，11实际MCP写/重开/读取全部通过；其他行的完整规范描述顺序逐条核对。
- 非文字/外来ID/缺少update change/delete带change/布尔mirror拒绝，pending delete取消及关闭session拒绝；fresh update/delete相同key无重放，recover正常。
- update和delete各4原生故障：真实完成后丢receipt仅核验恢复、启动取消、DLL加载后marker+真实3秒超时、另一个native操作额外加线后apply及recover拒绝。8例全部通过，owned0，源保持。
- 既有新增3字体姿态/生命周期复测通过；旧199工具时期3份已验证plan/receipt/DSN复制到新审计目录，当前verifier直接核验通过，原SHA保持，没有调用execute或重放原写入。
- 初次故障测试扩展脚本出现语法错误，在解释阶段退出，未创建任务或启动native；语法修正后才执行上述故障。旧第88批所有失败记录仍保留，没有修改其结论。

输入预先冻结，源/expected SHA保持。完整536回归535通过/1原权限skip，无失败；200实际工具合同同步，新增5host覆盖精确目标/严格替换/非文字外来大ID拒绝/重复顺序及删除。

## 范围与下一步

文字新增/更新/删除已在上述范围验收；不等于完整D05通过。页面裁切、渲染字形/字体质量、其他图形CRUD、titleblock/nested、未建模属性、实例显示字体与occurrence/原生DRC仍不认证。C05仍partial、D05仍deferred；34仍6 passed/1 baseline/7 partial/18 deferred/2 planned，17.6%，目标active。

第88批与跳过原因修正已本地提交e965b01/353f069，之前GitHub网络重置导致尚待补推；本批将一起同步develop，alpha.1固定。安装/真实设计未改，无GUI或宿主旧派发重放。下一步继续页面边界与其他原始门禁。

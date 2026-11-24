# 已有装饰线的更新与删除

先用 `capture_query_page_vectors` 取得当前会话的装饰线 `graphicId`，再调用 `capture_plan_graphic_line_edit`。电气导线和其他图形类型不能作为目标。对象ID限制256字符，页内图形索引1..4096；页的语义定位必须唯一。

`operation="update"` 必须提供完整 `change`：`localStart`、`localEnd`、`location`、`rotation`、`mirror`、`lineStyle`、`lineWidth`、`lineColor`。局部端点需不同；先在 mirror=1 时将局部X坐标取反，再按原生旋转码0..3变换为 (x,y)、(y,-x)、(-x,-y)、(-y,x)，最后加实例位置。所有输入及变换后端点受坐标界限约束。线型0..5、宽度0..3、原生调色板码1..48；48是对象默认色，不承诺具体RGB或打印效果。`operation="delete"` 不得提供 change。

计划预览显示原生身份和完整旧字段。执行沿用 `capture_apply_graphic_line_add`，取消与恢复同样沿用该任务族；通过后用 `capture_open_edit_result(kind="graphic_line")` 打开结果。名称中的 add 是历史任务族名称，不会把更新/删除改为新增操作。

写入只发生在新副本。固定工作器先核对页、迭代顺序、原生ID、类型、原位置/端点/姿态/线型/宽度及两层颜色。更新保留目标原生ID；删除只移除选定实例。保存后新进程核对所有已支持页的有序图形、已建模实例和定义连接，并逐页比较有序线条身份与实例/定义颜色。最多64页，每页4096图形，整体最多4096线条记录，计划上限48KiB；存在不能完整建模的图形时拒绝计划。

通过结果包含 `modeledGraphicsAndInstancesPreserved`、`lineIdentitiesAndColorsPreserved`。更新还核对新颜色；删除的 `graphicRemovalVerified` 为 true。原生退出或保存成功都不足以通过：故障验收中，工作器已保存错误新颜色，仍被独立读取拒绝；失败产物不能开放、恢复为成功或重放。

实际 MCP 已通过八种旧姿态到新姿态的更新、首/中/末删除、取消/来源改变/终态篡改拒绝及新服务恢复。补充原生服务测试在四条完全重合线中只改指定ID的颜色，再精确删除同色双胞胎之一，其余身份和颜色保持。四个原生错误身份/旧字段例均在保存前拒绝且副本字节未变。见 [批次173](implementation/batch-173-evidence.json)。

此验收不证明实际字形/笔宽占用、页面裁切、标题栏/嵌套符号、实例显示字体、未建模属性、occurrence连通或原生DRC。原34项D05的其余条件仍保留；alpha/release及既有发行65工具契约未晋级或改写。

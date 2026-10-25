# 第86批：空导线逐点构造与Capture宿主对照

2026-10-26，D03及ISS-D03-new-design-wire-reopen继续未通过。正式194工具/生产读取写入/合同未改。

## 官方依据与预期

CAP-REF p434的空NewWireScalar(status,bNewVersion)，p492的NewPoint及SetPoint。原件路径与指纹见参考索引，不上传手册。固定独立预期仍ROOT/MAIN、零元件/引脚、一根[(100,100),(300,100)]导线。所有独立解释器实验新建私有DSN，完整保存并新进程读取，原oracle保持。

| 条件 | 实际结果 |
|---|---|
| 默认带坐标构造 | 保存成功，NextPage3969 |
| 空构造version0 + NewPoint两点 | 保存成功，仍3969 |
| 空构造version1 + NewPoint两点 | 对象自身有2点，但pageWireCount=0；新进程objects=[]，失败 |
| 空构造version0 + SetPoint | 点设置返回dbo_1003，进程exit1，saved=false |
| 空构造version1 + SetPoint | 同样dbo_1003，进程exit1，saved=false |

五例均未通过，owned进程归零。version1能重开但没有导线，不能当修复。原始report中assert错误文本为空、setter错误被harness表述为native_process_exit；另存audit.json读取原回执并明确分类，原report/回执不覆盖。

## 宿主上下文与未确认派发

首次准备冷启动前发现已有Capture，工具按保护规则拒绝，没有新实例启动。随后明确检查PID20696、进程路径及原私有lowpassfilters.dsn，固定command-file要求PID和活动私有设计路径一致后才执行；使用单独Dbo会话、独立命名空间，不Open/Save活动工程、不退出原Capture。生成脚本中去除重复DLL加载与失败exit，完整预期不变。

转发器exit0，但20秒内没有boot或receipt；稍后只读检查仍无两文件。它只证明未收到执行确认，不能判定命令一定没有排队，也不能判定Dbo保存失败。禁止重放此命令。原私有活动DSN磁盘SHA保持，不能据此声称其内存会话已完成检查。

computer-use只读窗口列表显示同一私有Capture工程、一个未响应窗口，以及Simulation Manager Product Choices窗口。文本未返回可操作控件，截图未显示可操作产品按钮，未点击/输入/关闭窗口。没有绕过应用访问权限，也没有将标题当成已知根因。宿主结果保持dispatch_unacknowledged_no_replay，后续先观察同一派发的boot/receipt，不重新发写。

## 验证、进度与下一步

原始数据留.local/wire-point-construction-20261026及.local/wire-capture-context-v2-20261026。公开脱敏摘要和SHA见batch-86-evidence.json。新增诊断的Python语法、原生输出断言与进度一致性检查；生产未改，沿用第84批526完整回归525通过/1权限skip，不声称本轮重跑。

34门禁仍6 passed/1 baseline/7 partial/18 deferred/2 planned，完整验收17.6%。本轮不证明宿主方案成功/失败，不修改安装或真实设计。后续先核实宿主是否恢复及本次命令是否得到确认，再推进宿主依赖的DRC/网表；同时保留新建导线和interior-pin原失败及完整验收要求。

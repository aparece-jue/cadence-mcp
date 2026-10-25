# 保存顺序对照与桌面宿主诊断

## 新设计保存顺序

依据本机Tcl手册p179–180及p362–363构造6个全新DSN，expected.json预先固定ROOT/MAIN、零part/pin，wire为(100,100)到(300,100)。empty控制成功被两个新进程读取；direct、initial_design、initial_page、save_as、no_page_save五个wire用例均保存成功但定义和对象读取失败。保存顺序假说未验证成立；不改变原失败产物/预期，不忽略3969，不宣称新DSN布线可用。

`.local/design-save-order-20261024/report.json`整体false，1/6通过；各自owned0，当前文件hash保持。只证明该有限对照，不能以empty通过替代含导线设计验收。

## 桌面工具与现有进程

更新后的computer-use技能和@oai/sky可用，实际launch_app后Capture PID20696达到Ready Start Page，未看到启动modal。此前hidden owned CLI冷启动仍是失败，不能由本次成功推断其原因或改写原报告。

一次桌面Open文件选择尝试：set_value报element1942不可用；重新观察后literal路径输入未填到文件名，Escape已取消。未误开Recent Projects或真实工程。后续回到固定CLI/native路径。

`.local/live-capture-inventory-20261024/report.json`记录PID绑定的固定command-file在现有20696执行，产出runtime.json；没有设计open或native write。终止的是自建secondary forwarder，非20696。旧字段unacknowledgedLauncherTerminated命名不佳，inventoryAvailable=true表明已收到回执，不等于终止已观察Capture。

## 私有工程与待审批状态

仅复制官方LOWPASSFILTERS.DSN、OPJ和AC.sim到`.local/capture-host-design-20261024`，未复制旧NET/CIR/DAT/OUT。官方Open接口对该私有OPJ调用后，桌面实际显示Read Only和独立simmgr.exe的Simulation Manager Product Choices；默认选中PSpice A/D，未勾选default。

通过Capture目标窗口点击OK被工具正确拒绝（控件属于simmgr.exe），没有执行。随后list_windows返回真实simmgr窗口985800；get_window_state因Computer Use app approval timed out失败。没有绕过应用授权、改注册表或盲点其他窗口，也没有产品选择成功证据。

`.local/owned-capture-host-20261024/report.json`bridgeReady=false，Open完成回执未收到；当前不能用此private project建立认证bridge或声称网表已生成。Capture及产品窗口留待访问授权或用户手动确认本次PSpice A/D，私有DSN hash保持。

`.local/desktop-capture-host-20261024/observation.json`是上述桌面工具观察的摘要，不是native验收回执。授权恢复后须重新观察窗口/工程/PID，不能沿用过期UI索引或盲目重放Open。

本批工具仍137，无公开生产Python/schema变化；最新全回归仍296项295通过/1原权限skip，历史目录句柄问题保持open。原34完整范围及失败均保留，目标active；下一独立多单元验收，simmgr可访问后续接宿主。无安装目录/真实工程修改、提交推送。

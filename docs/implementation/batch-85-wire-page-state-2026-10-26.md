# 第85批：新设计导线保存故障的页面初始化对照

2026-10-26，对应D03及ISS-D03-new-design-wire-reopen。目标仍未完成，未新增通过门禁。

## 官方依据与独立预期

CAP-REF第421页声明DboPage.NewNetScalar、UpdatePageState、InitUndoRedoData；NewWireScalar最小重载见第432页。这里只公开定位及原创结论，安装原件指纹见参考索引。手册声明不证明这些方法在独立解释器上下文中适用。

固定预期为ROOT/MAIN、一根[(100,100),(300,100)]标量导线、零元件及零引脚。每个实验新建私有设计并完整保存，再由独立进程严格读取；未修改生产读取器或容忍3969。此前net_before实际在导线之后创建网络，本轮net_first在导线之前创建，二者明确区分。

## 实际结果

| 条件 | 结果 |
|---|---|
| 默认构造 | 保存exit0，但新进程NextPage返回3969，失败 |
| 先NewNetScalar后画线 | 保存exit0，仍3969，失败 |
| InitUndoRedoData后画线 | 保存exit0，仍3969，失败 |
| 画线前UpdatePageState | 原生进程3221225477，无保存回执 |
| 画线后UpdatePageState | 原生进程3221225477，无保存回执 |
| InitUndoRedoData后画线，再UpdatePageState | 原生进程3221225477，无保存回执 |

第一轮六例结果保存在.local/wire-page-state-20261026，原adapter/probe副本保留。第二轮在新目录添加UpdatePageState调用前后即时关闭文件的标记，三例均只留下before_update_page_state。它们是明确原生异常退出，不是缺少回执导致的普通文件错误；本轮没有重放原失败作业。其余三例设计SHA在读取前后保持，预期文件SHA保持；全部子进程终止，remainingOwnedProcesses=0。两个报告allCasesPassed均为false。

这排除了本轮三个初始化方案作为当前独立解释器修复的可行性，不证明GUI上下文同样失败，也不证明官方SDK无法完成。正式业务流程不加入UpdatePageState。导线/跨页/层次/网表原门禁继续保留。

## 复现与证据

新增tools/probe_wire_page_state.py和固定adapters/fixture_wire_page_state.tcl；传入安装根及不存在的私有workspace-root，通过仓库虚拟环境执行。原始DSN/回执/报告留在.local，公开摘要与SHA256见batch-85-evidence.json，不上传第三方设计或手册全文。

仅新增诊断与管理文件，正式工具/合同仍194，生产实现未改。本轮沿用第84批完整回归526项（525通过、1权限跳过）；不声称本轮重新跑过完整回归。执行诊断Python语法检查、证据断言及进度一致性检查。

原34项仍6 passed、1 baseline、7 partial、18 deferred、2 planned；完整验收6/34=17.6%。下一步比较可成功写线的已有页面与新建页面的原生初始化/序列化差异，保留原失败；若需Capture上下文实验，单独绑定私有设计，不隐式切换真实工程。

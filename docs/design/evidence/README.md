# 历史本机探测记录

这些文件来自 2026-10-22 的设计阶段探测，不是本仓库实现的验收结果。

- inventory.json：本机文件与原仓库模块指纹，以及与已有审查副本比较的结果；其中 text 字段指向原工作目录保留的官方文档提取文本，这些文本未纳入本仓库。
- file-versions.json：本机主要可执行文件与 DLL 的版本信息。
- runtime-results-first.json、divider-first.cir、divider-first.out：首次一次性电路的失败记录。
- runtime-results.json：第二次运行记录，Capture 仅做命令可见性探测，PSpice 修正输入后超时。
- scratch/divider.cir：第二次运行的输入。未收录 scratch 中残留的首次 OUT，以免误认为第二次结果。

原始路径保留用于证据追溯，不是程序配置或跨机器默认路径。官方文档全文、第三方源码及其解码副本均未纳入本目录。完整原始材料继续保留在先前工作目录的 design-plan/evidence。

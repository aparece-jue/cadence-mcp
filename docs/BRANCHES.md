# 分支、版本与验收晋级

2026-10-27，依据用户最新要求实施。开发目录继续使用D:/workspace/git/cadence-mcp，当前工作分支develop。

| 分支 | 内容与用途 | 初始化基线 | 默认入口 |
|---|---|---|---|
| develop | 源码、原创研发资料、计划/进度、问题、复现和验收摘要；按完成批次持续提交推送 | 已有研发历史继续推进，版本0.1.1.dev0 | cadence-mcp / cadence_mcp.server，224个开发工具 |
| alpha | 已完成该次测试验收的固定测试版本源码 | v0.1.1-alpha.1 / eebb8ca6bd5aaea5a2aebf99a025e036578a66ae | 该tag的开发/扩展入口，224工具 |
| release | 已完成明确支持范围验收的固定发行源码 | v0.1.0 / e59f888607bdc647c3dbcec1a235663fc3b3eeb4 | cadence_mcp.validated_server，65工具 |
| main | 现有默认分支暂保留 | 0a31dda | 历史alpha.1基线，当前发行请选release/tag |

alpha/release初次创建直接指向既有已发布标签提交，未改写历史或重新打包旧版本。分支本身是可晋级的渠道，tag才是不可变版本身份。分支不同不意味着从历史中删除共同的研发文档；最新研发记录只随develop继续增长。

## 完成一个研发批次

1. 对应原34项中的具体要求，先固定独立预期与官方依据。
2. 实现和验收，保留失败后移；主机测试、真实原生/MCP与未执行项分开记录。
3. 同步CURRENT-STATE、cadence-acceptance、批次证据与进度；检查可公开内容。
4. 运行适当检查和update_progress.py --check，然后提交并推送develop。网络失败保留回执，先核对远端，再处理未同步批次。

## 测试与发行晋级

仅在某个候选版本完成其明确范围验收、独立wheel安装与实际MCP工具契约检查后，准备新版本号、新tag、ZIP/校验值、版本说明及支持矩阵，再将alpha或release前移到该候选提交。不直接合并develop全部实验能力到发行入口；发行白名单/Schema/旧任务guard需同时审计。

常规研发提交不改用户已安装的固定环境，不重打包或覆盖旧Release资产。这里没有配置或宣称GitHub服务器端分支保护、自动CI晋级；目前由明确检查与非强制引用更新执行。main默认分支暂不变。

Git smart-HTTP连接重置时，可用官方Git Data API同步本地相同Git对象，必须逐一核对tree/commit/annotated tag SHA，分支仅非强制前移；不能以重新生成不同内容/不同身份的提交冒充原推送。

## 可公开资料

原创源码、架构/研究总结、合法最小复现、计划与验收摘要、官方资料定位及hash放develop。官方手册全文、Cadence二进制、真实DSN/OLB、外部模型、许可证、认证绑定及原生输出留本地.local，禁止因分支管理而上传。PDF延期，Allegro排除，原34项仍完整保留。

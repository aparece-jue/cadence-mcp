# 第八批：库绑定的器件放置

2026-10-23。新增5个实际MCP工具，总数64。34项required、失败后移及最终门禁保持不变。D01仍implemented_partial，目标active。本批无GUI、真实工程/安装写入、提交推送。

## 接口与实现

新增capture_plan_placement、capture_apply_placement、capture_placement_jobs、capture_cancel_placement、capture_recover_placement。capture_open_edit_result增加固定placement kind。沿用持久计划、digest、15min有效期、幂等、不重放及自有进程控制；新增取消方法进入独立诊断线程池。

计划绑定不可变设计session/page与OLB libraryId/libraryPartId，从快照确定package/device designator/position/cell/part名称。native重新按稳定语义校验这些身份及variant数，不能把跨进程序号当持久身份。设计和OLB均复制到新job，原副本hash再核对。新缓存名由host生成并在原生缓存列表中检查冲突；不替换已有缓存。

调用方必须明确提供reference/location/raw rotation+mirror/value，以及每个新physical pin的number/name/全局hotSpot/connected/net和目标页所有既有pin预期。引脚名称/脚号多重集合必须与选定库part/device完全一致，有重复歧义则拒绝。已有reference（忽略大小写）不允许作为普通放置追加单元，需未来package-aware操作。

不使用C03失败的简单仿射模型计算热点；实际保存后读取原生GetOffsetHotSpot，与调用方预声明的全局坐标逐脚比较。raw旋转/镜像和location单独比较。已有wire几何默认保持；可预声明分段结构，但并集不得增加或丢失旧几何。其他连接对象、其他页及整份定义pin-net基线均核对。

完整保存链后独立进程重开，验证唯一new reference、物理脚表/net、全局热点、pose、Value及继承的PCB Footprint。artifact只有这些断言通过才verified。源码capture_place.py、adapters/edit_place.tcl；native各阶段保留bounded错误回执，模糊variant选择拒绝。只有source cell本来一个part且cached cell也唯一时，才接受copy导致名称变化的唯一对应。

## 原生与真实MCP验收

内部首例`.local/placement-typed-7aa3ff38ca/report.json`：从ANALOG.R放置R103，位置(700,300)、rotation=mirror=0、Value=2k，预声明脚1=(690,310)、脚2=(730,310)，两脚均未绑定；既有R101/R102四脚保持未绑定。源DSN和官方OLB hash不变，Value/Footprint及全基线保存重开通过，verified输出再次打开通过。

真实stdio `.local/placement-mcp-20261023/report.json`导出并验收64工具契约，以下全部通过：

- 通过已有库查询工具选择R的part/device，计划/apply/独立核验及MCP输出衔接；读回整份12个part、47个pin（原11/45加一件两脚）。
- 给R104故意声明错误全局热点(0,0)：真实保存后独立核验以placement_hotspot_mismatch拒绝，未验证输出不能打开。没有把观察值改写到期望。
- 新pending计划取消后apply拒绝，jobs包含verified/failed/cancelled，额外eval参数被协议拒绝。
- 关闭Server再启动新进程，同一幂等键返回原结果、mutationReplayed=false，verified输出仍可打开。无需重新注册原设计/库session来重放修改。

4项主机测试通过：物理脚映射精确匹配、脚名/号错误、非法热点/绑定预期、重复共享物理脚不静默合并及既有页pin预期完整性。这些主机断言不代替原生行为。

完整回归192项：191通过、1项原有Windows文件symlink权限跳过。历史P02目录释放问题本次未复现，仍保留，跳过仍不是通过。

## 仍需完成

- 本批真实成功例是ANALOG.R单device、零旋转/镜像。其他器件/姿态、复杂/共享单元、variant迁移、缓存复用/更新/冲突矩阵仍须验收；不能因为接口接受raw codes就认为C03或全部pose通过。
- 独立重开时job内输入OLB仍存在，**未证明外部OLB不可用时的cache闭包**，结果embeddedCacheClosureVerified=false。不能将保存重开等同于已完成L05缓存生命周期。
- 引脚电气类型/可见性、occurrence网络、字体/图形布局和native DRC未核验。
- placement专属真实receipt-loss恢复、native启动/执行中取消及timeout故障矩阵仍待补。继承已验证任务基座不单独构成这些业务的原生验收。
- D03后续修改/删除/交叉/T/重叠与D05/V03等继续推进；其余历史失败按队列保留。

## 官方依据与复现

Capture主PDF226页CopyPackageAll、424–425页NewPlacedInst、522页SetReference、530页SetPartValue及已核实保存链；新part几何/属性读取复用既有已验证适配器。本次不复制官方库、手册或受限源码进公开仓库。

公开原创tools/smoke_placement.py使用install-root/workspace-root/source/library四参数；source应为第六批MCP_PLACE双电阻测试副本，library为安装内ANALOG.OLB，只读导入，workspace-root须不存在。本地原生资料均在.local忽略目录。

证据：`.local/placement-typed-7aa3ff38ca/report.json`、`.local/placement-mcp-20261023/{report.json,tools-list.json}`、`.local/regression-192-placement-20261023.txt`。摘要hash见batch-08-evidence.json，正式工具契约同步真实64项清单。

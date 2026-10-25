# 第二十三批范围与验收

## 第二十三批位号映射、交换与冲突预检

- inspect_reference_units.tcl按真实object type区分placed/drawn，避免无条件cast；去掉DboPackage缺少官方签名的GetId请求，用packageName/size/deviceDesignator/source part等语义身份。V2仍报package_get_id，因一次字符串替换漏掉旧调用；精确删除后`.local/reference-identity-v3-20261023/report.json`同官方FULLADD全部definition partId/ref对应通过，源hash保持。原最早错误仅写unit_identity，不能追溯断言其一定在某个具体方法。新增external-design flag供plan拒绝外部依赖，未把definition单位当成occurrence覆盖单位。
- 新capture_references.py/edit_references.tcl，固定JSON声明与两个阶段SetReference：全部选中对象先到临时号，再全部到最终号，释放iterator后才修改，完整page/schematic/design保存。依据官方Tcl p515/522/529–530，修改真实Reference，不是仅改显示文本。临时号沿用prefix、避开全部已有与最终ref，失败保留副本/账本，不自动回滚重放。
- 公开5工具capture_plan_reference_map/apply_reference_map/reference_jobs/cancel_reference_map/recover_reference_map，open_edit_result新增kind=reference，实际110。1..64显式映射、原prefix/编号语法、part唯一、final casefold重号与未映射对象占用检查；可做循环/交换。当前仅唯一ref的single-unit placed definitions。重复ref/多unit/drawn/external/目标NC/未编号分配等提前拒绝或未提供；不假称原生自动Annotate。
- plan绑定native part ID +语义page/ref/package，post核对所有definition part/pin/net摘要、wire/alias/其他connection objects基线、所选页每个器件位置/旋转/镜像/实际pin hotspots、新单单元package及GetReferenceDesignator完整位号。scope=single_unit_part_definitions，designPassed=null，occurrenceConnectivityVerified=false；多单元/occurrence/渲染/其他属性/DRC原要求继续pending。
- `.local/reference-maps-20261023/report.json`4原生用例通过：未连接rename/swap、已连接rename/swap，新进程重开与fresh writer不重放/open、源hash保持。交换后原R101.2→新R102.2、原R102.1→新R101.1仍接MCP_MIDDLE；另两外端仍未接，位置/热点跟随原器件，wire/alias保持。
- `.local/reference-map-mcp-20261023/report.json`真实110工具stdio：已连接交换、明确pin-net与位置期望、schema、未映射冲突/重复单位/extra拒绝、pending cancel/jobs、fresh server原key不重放/recover/open、篡改拒绝均通过。末尾该MCP swap产物被故意追加bytes，保持拒绝；4原生用例产物未篡改。
- `.local/reference-map-faults-20261023/report.json`实际native完成后受控丢receipt→fresh只核验恢复/nativeCompletionVerified=false/hash保持并open；启动窗口cancel和真实1s timeout均自有进程0/不重放。不代表临时号/最终号/每个save窗口均已覆盖，也不证明历史目录句柄问题修复。
- 7项新主机测试：交换保留物理pin绑定且不改输入、casefold冲突/重复映射、prefix/控制符/未编号边界、临时号碰撞、重复ref、unknown/noop/extra、multiunit/drawn/external在创建plan前拒绝。最新257完整回归256通过/1原file-symlink权限skip；ISS-P02-process-directory-release-152等历史问题仍open，不因本次通过关闭。E03 partial，原34项完整范围未缩减，目标active。无GUI、安装/真实设计修改、提交推送；下一L05/P03/H03/D04等独立项。


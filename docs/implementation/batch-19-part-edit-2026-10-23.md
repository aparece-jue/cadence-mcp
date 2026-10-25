# 第十九批范围与验收

## 第十九批器件姿态与删除业务

- 新capture_part_edit.py/edit_part.tcl；公开capture_plan_part_edit/apply_part_edit/part_edit_jobs/cancel_part_edit/recover_part_edit，capture_open_edit_result新增kind=part_edit，实际94工具。set_pose要求完整目标pin热点与所有保留page pin-net预期；delete不接受新pose/pins，只声明删除后存留pins。源hash/独立输出/持久计划/幂等/只核验恢复沿用隔离任务。调用者须声明预期，后端不会按观察值替换oracle。
- 检查同页引用唯一、目标NC拒绝、页面语义名称唯一、数据量/坐标/枚举/字段；核对完整definition/pin-net、connection objects以及所选页所有器件位置/姿态/热点。几何稳定键用ref+number/name，不依赖保存前后ordinal ID。非所选页几何、其他属性、occurrence、多单元封装生命周期、NC生命周期、渲染及DRC明确未核验。
- 根据本机官方手册p301–302/461–462/524使用SetMirror/SetRotation/SetLocation、Page.DeletePartInst及完整save链。选取对象后先释放iterator再修改/删除，不访问已删除指针。首次connected两个用例在编辑前失败；`.local/part-edit-opening-phase-20261023/native-result.json`定位Schematic.GetPage(name)/3969。改为已有reader所用NewPagesIter/NextPage/唯一exact name，未忽略3969。修复仅限本adapter；H02 NULL schematic net仍open。
- `.local/part-edits-v2-20261023/report.json`5项原生验收全通过：未连接move/delete、已连接move/delete、错误hotspot拒绝+禁止重放。move_connected明确R101移走后两个pin未连，R102.1仍连MCP_MIDDLE；delete_connected明确删除R101并保留R102与原wire/alias。新进程重开、其他page pin基线和所选page其他器件几何保持，源hash不变。
- `.local/part-edit-mcp-20261023/report.json`真实94工具stdio：move/delete、schema与非法bool/extra/漏pin拒绝、pending cancel/jobs/recover、新server相同key不重放并重开产物通过。末尾delete产物刻意追加bytes作为篡改负例，现应保持拒绝；不是全部MCP输出仍为有效产物。
- `.local/part-pose-centered-20261023/report.json`自建居中R401符号完整8姿态通过，期望先固定local pins±20、mirror-x、顺时针quarter turns，保存后新进程核对所有global hotspots和明确unbound网络。它不替代原C03非居中符号90度偏移反例，原issue保持open/deferred。
- `.local/part-edit-faults-20261023/report.json`真实native完成后受控删除receipt，fresh writer只核验恢复、artifact hash保持、nativeCompletionVerified=false；native启动窗口cancel和实际1s timeout均自有进程0、不重放。只覆盖这些窗口，不能代表所有保存阶段故障/资源浸泡已验收。
- 3项新主机测试覆盖声明热点不被自动重算/修改、缺失未知重复与bool拒绝、保存后ordinal变化不改变几何语义。完整233回归232通过/1原file-symlink权限skip。D02 partial；原34项完整范围不变，目标active。无GUI、安装/真实工程修改、提交推送。下一E04、H04、V03等独立项。


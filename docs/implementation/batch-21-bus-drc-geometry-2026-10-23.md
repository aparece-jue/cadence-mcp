# 第二十一批范围与验收

## 第二十一批总线/DRC探测、精确几何与桥接发布修复

- H04：依据官方Bus_Connectivity.html及Tcl手册p435–443/498–499/581–583/739–740，新增内部fixture_bus.tcl、inspect_bus.tcl及probe_bus_fixtures.py。预先声明DATA[7..0]/DATA[0..7]、8scalar aliases/入口两端，另造缺成员与脱离入口。4项native创建保存均exit0，但独立读取全部失败；0项bus成员/正反例通过。`.local/bus-fixtures-20261023/descending/phase.json.error.json`定位page iterator NextPage/state3969；只读诊断hash保持，自有进程0。容器名改用DboNetBus.GetName而非scalar net名也未解决此前page阶段错误。H04 deferred后移，不发布MCP，不忽略3969。
- V03：再次核对官方capRunDRCConfigData仅设置/返回配置并关框，不能执行DRC。无现存Capture进程时，一次PID绑定的Capture.exe官方脚本命令行探测只列命令/proc参数、不主动开设计/调用DRC，45.047s超时，无runtime.json，自有进程0。没有桌面操作；该次确实启动了Capture应用，不能称全程未启动GUI。原因未观察到，不猜许可/模态/启动策略。V03 deferred后移，未获得真实DRC命令/报告，未开放接口。
- 独立V02推进：capture_check_wiring增加可选gridSize/gridOrigin，未提供时明确grid未检查；wire-geometry-advisory@0.2.0用精确Fraction求任意方向直线交叉、T接触、共线重叠，包括斜线；整数点保持point，非整数点用point=null/pointExact分子分母，不舍入后假落栅格。共享端点不加交叉罚，跨页隔离，非正交仍警告。2000segments/10000vertices/findings、native32bit坐标上限；零长度/grid也受限，不截断后宣称完整。geometryComplete仅指bounded_linear_wire_intersections，designPassed=null，未判断任何电气连接/DRC/文字避让。
- 新6数学/边界测试：6/5斜交点、反向斜重叠/T/共享端点、负坐标/平移grid原点、bool与非法范围、退化线/输出上限、大native整数精确交叉。`.local/wiring-exact-mcp-20261023/report.json`真实99工具stdio读取既有两电阻wire/alias副本：MCP_PLACE(330,310)-(490,310)，grid10 origin(0,0)离栅格0顶点、origin(5,5)离栅格2顶点，artifact hash、非法参数与副本篡改拒绝通过，源hash保持。这不是native斜线fixture或symbol/text渲染验收；V02 partial，其他原要求未删。
- 首次244回归失败于旧的“斜线未覆盖”测试断言。更新该契约测试为新线性覆盖succeeded，同时增加geometryCoverage、electricalConnectivityVerified=false、designPassed=null和未给grid仍notChecked断言；没有放宽电气结论。
- 第二次244回归发现既有桥接endpoint.json半写入竞态，认证测试在空文件上JSONDecodeError。bridge.tcl改成同目录排他临时文件、完整写入/close、无覆盖rename后才发布endpoint并登记owner；失败清理自己的temp。新增确定性native观察测试，在真正payload写入边界检查最终endpoint尚不存在。`.local/bridge-atomic-native-20261023.txt`23项全部通过，未用readiness延时/重试掩盖生产竞态；这是真Tcl协议夹具，不是重新验收Capture GUI加载。
- 最新完整245回归仍失败：243通过、1error、1原file-symlink权限skip。失败为test_cancel_and_precancel结束后临时cwd清理WinError32/5；与原ISS-P02-process-directory-release-152同类，现有完整原始堆栈保存，根因/持有句柄未确定，保持open。不能用早前绿色回归或专项通过称当前全回归通过；不再无修改重复跑去碰绿色。前三份失败报告都保留。
- 实际工具仍99，contracts同步新grid输入Schema。原34项和失败门禁保持，目标active。除一次无设计Capture脚本运行时探测外均独立Tcl/MCP；没有桌面点击、安装目录/真实设计修改、提交推送。下一L04/E03/L05/P03等独立项，最终集中修复后移问题。


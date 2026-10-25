# 第六十六批：官方非交互CLI任务

2026-10-25。目标active；原34项范围保持，P02整体仍implemented_partial。

## 官方入口与原超时复测

读取cap_ug/Running_PSpice_in_Batch_Mode.html：非交互入口为psp_cmd.exe /r；GUI pspice.exe不是本批实现。读取pspcref/00intro.html的命令选项表后实测：psp_cmd附加/e /o /d /l组合返回2、无OUT/DAT；单独/r在原分压电路的新副本中2.171秒正常退出，生成本次input.out/input.dat，打印2.5V。原60秒timeout记录和原source保留。本次未复现原超时，不把环境/许可证猜测当成历史根因证明。

公开接口固定安装内psp_cmd.exe、/r及owned input.cir，不开放任意exe/参数。/r运行文件内所有分析，因此计划要求恰好一个选中的DC/AC/TRAN类型，拒绝含额外分析类型，避免执行未请求分析。

## 实现与契约

新增pspice_plan_cli_run/apply_cli_run/cli_run_jobs/cancel_cli_run/recover_cli_run共5工具，实际178；pspice_open_run_dat和pspice_inspect_run_output新增backend=engine|cli（默认engine兼容旧调用），失败观察kind新增cli。CLI账本独立，后端标记official_psp_cmd_r，不隐式回退Tcl引擎。

复用固定输入闭包冻结/重定位、幂等与所属进程树。执行前若任务已有原始/规范OUT/DAT、CLI回执或manifest，拒绝启动、覆盖或复用旧文件。CLI结束后等待所属根和观察到的子进程退出信号，原始input.out/input.dat逐字节复制为规范result.out/result.dat；两组文件和CLI完成回执都进入同一hash manifest。运行未退出/timeout/取消不签发完成回执。

验收同时要求退出/进程身份、原生OUT完成且无错误、DAT独立原生读取、分析类型及声明数值预期；exit0不足以证明成功。CLI验证使用JOB CONCLUDED/统计标记，不误套Tcl的FINISH命令回显。共用验证逻辑新增后端和extra-scope钩子，CLI仍为declared_trace_rows_only；原生MEASURE维持declared_native_measurement_fields_only，不能混淆。

## 验收证据

- `.local/cli-runs-mcp-20261025/report.json`：3真实MCP正例通过，原分压2.5V、AC0.5-0.5i、全RC瞬态及1ms时间常数；原始与规范文件hash一致，后端/作用域准确。非法模型OUT错误拒绝，失败DAT不开放；待执行取消、新服务apply/recover/open不重放，source/oracle保持。
- `.local/cli-faults-20261025/report.json`：8故障案例通过。丢CLI回执后新服务独立数值/原始副本身份验证恢复，不重跑且nativeCompletionVerified=false；启动窗口主动取消；真实psp_cmd1秒timeout，所属进程退出；原始DAT改变、终末规范DAT改变、错误3V预期均拒绝；preexisting旧OUT不启动/不覆盖/不重放；冻结输入变化在preflight拒绝。负例保留。
- `.local/native-measure-after-cli-20261025/report.json`：复验原生DC/瞬态/AC测量、错误预期/错误求值及fresh lifecycle通过，确认共用作用域钩子兼容。
- 新9 host tests覆盖固定/r命令、单分析限制、原始/规范身份、完成回执、未知退出码不猜license、旧产物保护与后端作用域。429完整回归428通过/1原符号链接权限skip；178实际工具契约同步。

## 状态与尚未通过项

ISS-P02-pspice-owned-7797dd67a5按当前官方/r运行功能及不变原分压输入的真实验收结案；rootCauseProven=false，未证明2026-10-22那次60秒等待的历史原因。现官方CLI不再只靠Tcl替代实现，但真实license不可用的原生分类仍未验收，单元测试中的license文字反例不能替代真实故障。新增独立跟踪项保留该缺口；P02整体不通过。

34项仍3 passed、1 baseline_passed、18 implemented_partial、10 deferred、2 planned。下一继续真实许可证失败证据及剩余P02原要求，再推进库/缓存、Capture连接/保存和端到端参数迭代。无GUI操作、无安装/真实设计改动、无提交推送。

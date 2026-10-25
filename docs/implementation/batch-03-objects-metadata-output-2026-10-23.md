# 第三批：对象查询、属性生命周期与OUT读取

日期：2026-10-23。目标未完成，34项required功能及最终门禁均保留。本批无桌面操作，不修改安装或真实工程，不提交/推送。

## 已通过的实际切片

- 实际stdio清单49工具：FULLADD副本中连接/图形对象分页及空分类读取；自定义metadata新增→空值→删除，每步plan/apply/save、新进程重读，并通过MCP打开已验证输出继续修改。重启服务后幂等及输出重开通过。源hash不变。
- 已有显示属性的位置、旋转和显示模式修改通过：独立核对有效/user值、其他显示属性和定义引脚网络基线。字体及native cached bounding box的渲染有效性未验收。
- FULLADD计数：wire28、alias1、port9、part_bounds9、display_property18、titleblock2。BCD另有wire122、alias42、port5、part_bounds20、display_property36、graphic1、titleblock1。零global/offpage/NC仅证明空分类，正向fixture仍必需。
- E01批准Value/PCB Footprint及中文/Tcl特殊字符修改在基座抽取后实际回归通过。metadata不开放内部identity/model/source/connectivity字段；删除显式user层与有效值继承回退明确分开。
- 新增第50个工具`pspice_inspect_output`：复制并读取配置read-root内OUT，记录来源hash/编码和报告。官方tutorial与DRV8837 OUT通过真实stdio。tutorial的初始偏置电压人工样例值5V=4.050e-12V、3V3/OUT1=751.3e-6V、OUT2=0V核对通过；DRV8837没有偏置表，返回空数据。数字状态不当作模拟电压。
- OUT工具只解析coded diagnostics和偏置电压表，保留重复section及无法完整解析的行。错误诊断不会被JOB CONCLUDED覆盖；从不据此宣称新求解成功或归属本次job。测量、波形、数值容差和求解关联保持P03未完成。
- DAT只完成内部原生探测：官方orPIOData64.dll在独立tclsh可读取隔离DAT副本，1块、49模拟列、59行、Time数据及alias header；未接入MCP、未验收复数/多块/单位/分页。源与副本hash未变。closeFile返回0，本探测不据此推断失败或完整生命周期成功，需核实返回语义。

## 失败与验收修正

1. 152项历史回归中`test_timeout_terminates_owned_descendant`方法断言完成，但TemporaryDirectory清理报WinError32后WinError5。原始trace仅在工具输出，未写文件，不能伪称有原始日志归档。摘要与issue保留。Job accounting为0不足以证明文件系统句柄释放；责任进程和原因尚未查明。本批157项回归未复现，问题仍open，放到P02队尾。
2. CMOSCPU、TUTOR2在基础CaptureService.open阶段失败，未执行对象读取；source hash一致。BCD读取通过，不得误列BCD失败。C01保持deferred。
3. 8姿态矩阵首个副本native设置/保存成功，但基础open失败，零姿态案例通过；未证明几何变换错误，也未证明正确。C03保持deferred，按C01依赖故障记录。
4. OUT针对性测试最初误以为SDK非法参数会抛异常；实际返回is_error，按协议修正断言后5项通过。官方OUT脚本起初误认为数字行在模拟电压表内，核对分区后改为核对数字节点不出现在模拟结果；保留首次failed报告，不改变电压预期。
5. 第一次157项完整回归：155通过、1错误、1权限跳过；错误是旧49工具数量断言，新增工具后已更新为50。修正后第二次157项：156通过、1项原有文件符号链接权限跳过。不得把跳过计为通过，历史清理故障也不因这次绿而结案。

## 证据与复现

本地原生输出保存在忽略目录，摘要hash见`batch-03-evidence.json`：

- `.local/objects-display-stdio-20261023/objects-metadata-report.json`及`tools-list.json`：49工具链及属性修改。
- `.local/property-stdio-e02-regression-20261023/property-edits-report.json`：E01实际回归。
- `.local/object-samples-2366284703/report.json`：BCD成功记录；该脚本随后在其他样例中断，不代表全部样例成功。
- `.local/object-samples-18f01a867b/report.json`、`.local/pose-matrix-ee5c6266a1/report.json`：基础读取/姿态未通过。
- `.local/out-reader-20261023/report.json`：首次验收脚本failed；`.local/out-reader-20261023-b/report.json`：修正脚本后2官方OUT通过及50工具清单。
- `.local/regression-157-20261023.txt`：工具数量旧断言失败；`.local/regression-157-20261023-b.txt`：完整回归156通过、1跳过。
- `.local/dat-probe-2344da67af/report.json`及`probe.txt`：DAT内部探测，无对外能力声明。

公开原创工具`tools/smoke_objects_and_metadata.py`支持install-root/source/workspace-root，工作目录须新建；OUT专项见`tools/smoke_pspice_output.py`，使用官方两个固定相对路径样例及独立人工偏置预期。完整回归使用仓库venv Python，设置CADENCE_TEST_TCLSH后运行unittest discover。

官方依据：Capture Tcl/Tk主参考PDF32–38、166/169、186–188、297–302、541–544、569–570、615–620页；OUT类型见`doc/pspug/007_set_sim_PSpice_A_D_Simulation_Window.html`并结合安装内官方样例。PSpice UI Measurement Results不等于OUT测量语法，未据此实现猜测格式。DAT依据`doc/psptclsample/Accessing_PSpice_Data_Files_using_TCL_Scripts.html`及`doc/psptclcmdref/{loadFile,getJSON,getDataNames,get,getNumberofBlocks,setBlock,closeFile}.html`，实际运行与手册示例上下文分别记录。

下一步推进DAT结构化读取/复数多块独立fixture及现有库/页面编辑；随后集中定位建库、求解、层次路径、基础读取和进程退出清理故障。不能只通过导入历史数据替代P02/P03/P04本次求解关联的最终验收。

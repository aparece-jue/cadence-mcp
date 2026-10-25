# 文字原生探测与DRC资料核实

2026-10-23。75公开工具、207回归206通过/1原symlink权限skip基线未变。本批新增内部probe，不注册未通过的文字写工具。

已读取Capture主参考p455-456 NewGraphicCommentTextInst、p706-708 DboCommentText文字/位置/字体。预写expected.json后，在副本新增中文、Ω及换行说明，Arial -11及完整LOGFONT字段。原生保存和新进程重开成功，Unicode文本与14项字体字段符合预期，定义/pin-net/连接对象保持。实例GetLocation却为(0,0)，不满足预声明(300,450)。完整用例判失败，坐标问题ISS-D05-comment-text-coordinate-frame后移。不能将字体或文字成功扩大为位置/图面验收成功，也不能以观察值倒改oracle。

证据`.local/graphic-text-20261023/{expected.json,report.json,texts-before.json,texts-after.json}`；内部脚本graphic_text_probe.tcl与tools/smoke_graphic_text.py。stdout编码可能使控制台中文显示错误，以UTF8 JSON原件为准。

DRC新增官方资料CustomDRC.pdf三页及capProcessDRC.tcl/capCustomDRC.tcl，路径/hash已登记机器矩阵。本次读取PDF p1-2与源码相关过程：自定义规则登记配置会保存INI；本任务未写INI。capProcessSelection依赖GetActivePM/GetActivePMDesign，按活动PM选全部/选择页，继而按occurrence或definition遍历。日志capCustomDrcLog使用append，故后续验收必须使用新独占报告路径，不能把旧日志或简单存在当作本次结果。capTrueRunDrc返回true，配置Run只关闭dialog，均不是原生DRC检查通过。

当前Get-Process未发现Capture。只在独立tclsh加载Dbo扩展进行命令可见性检查，未见*Execute*Drc*；这不证明GUI运行时也没有入口。没有启动GUI、执行DRC或生成DRC报告，不宣称已完成V03。后续需核实主引擎签名、受控活动项目身份及规则/报告边界；自定义规则不能冒充完整原生DRC。

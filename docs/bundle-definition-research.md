# 嵌套Bundle定义研发记录（2026-10-27）

对应原H04必需范围，不是已发布能力。官方本机Tcl/Tk Extensions PDF774–789页提供Bundle类型/成员/模板映射接口；当前运行时导出SCALAR=1、BUS=2、BUNDLE=0及sMakeBool/sGetBool/sDeleteBool。辅助函数未在已索引手册页完整列出，按运行时探测记录，不把命令可见当作工作流通过。

预先冻结图：B_CHILD含READY scalar和DATA[7..0]八位bus；B_TOP含CTRL scalar和B_CHILD bundle。固定私有脚本在原已初始化空DSN的全新副本运行，原文件SHA和oracle全程不变，不写安装或真实设计。

初次无参数sMakeBool重载拒绝，保留失败；显式FALSE后创建两个模板均返回created=true，bool读取/释放完成。但DboBundle.AddMember(READY,SCALAR)发生进程级访问异常，catch不能捕获；阶段日志定位到child_scalar，仅此调用阶段明确，根因未确认。

另一私有副本使用官方DboBundleTemplateMap.AddBundleMember(name,memberOfName,type,owner)替代直接成员入口。READY、DATA范围、CTRL、嵌套B_CHILD及MarkModifiedDesign/SaveDesign均返回；随后GetBundle(B_CHILD)仍报missing_bundle，尚无独立重开图验证。可能涉及owner/内部显示名称或上下文，均只是待证假设，不能把保存返回或目标bytes变化视作正确数据存在。

本项失败移到队尾，所有报告/预期/阶段日志hash见batch118；未加MCP工具，未晋级alpha/release。独立三页43pin无bus的pin_member查询控制通过，只证明该读取分支遍历，不证明Bundle或层次连接。后续需核对官方名称映射/包含库与编辑上下文，再进行完整成员/嵌套/保存独立重开正反验收。

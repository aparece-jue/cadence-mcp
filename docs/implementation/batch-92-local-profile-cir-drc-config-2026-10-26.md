# 第92批：本地profile生成CIR、DRC配置与依赖解析

2026-10-26。对应V03/V04/P01，原34项门禁保持。

认证固定PID宿主只读取得capGetDRCConfigData、默认ERC矩阵和在线开关。实际总开关及flow为1，电气各在线规则却全部0；ERC输出对输出仍E。这证明存在规则配置缺口，但尚未证明是原冲突零错误的唯一原因。按设计读取候选内部配置键均返回给定unknown默认值，因此没有根据猜测启用规则，没有调用配置保存/全局ERC设置，也没有将原负例改判通过。新增工具仅为固定开发诊断入口。

依据安装内orPSpiceSrvrEnv.tcl的本地原语，在新私有工程副本加载profile、readSettingsLibinc、updateCirFileI。首轮返回-1，未产生CIR；官方newProfile示例会预建以profile名命名的子目录，新副本补齐AC目录后，更新返回0并生成638字节CIR。独立原profile读取核对.AC LIN 100 0.1 200、源已审计NET的相对引用、nom.lib及.END；4个错误点数/结束频率/NET引用/缺失库负例全部拒绝。原始CIR/profile/NET指纹保持。本地CLI进程退出，owned0；未调用完整远端服务包，也未运行求解器。生成CIR并不代表完整V04。

实际CIR的依赖预检首先被官方nom.lib的分号注释阻断。官方PSpice参考明确分号表示行尾注释，本批扩展显式.INC/.INCLUDE/.LIB单文件引用解析；保留原美元注释、缺失文件名和额外参数拒绝。新增2项测试覆盖带空格引号路径、无空格分号、原美元注释和非法引用。对同一CIR重测，错误由unsupported_reference推进为unsupported_encoding：实际模型库包含非UTF8内容。未猜测编码、移除库或修改原生CIR；后续需要显式可追踪的编码及依赖来源处理，完整模型闭包仍未通过。

完整回归546项，545通过、1个原符号链接权限skip；正式工具202、合同不变，完整验收6/34（17.6%）。资料只上传原创总结与元数据/指纹；原始模型、官方源码/手册全文、私有设计、认证资料、CIR/NET/原始运行记录留.local。安装目录和真实工程未改，alpha.1发布包固定。

复现工具：probe_local_profile_cir.py/.tcl接受显式install/workspace/source/netlist根，复制原设计和已核对NET后执行固定本地原语；audit_profile_cir_mapping.py只读独立检查；probe_profile_cir_closure.py通过现有输入准备器验证实际闭包。各次运行使用不同新目录，未覆盖首轮失败。证据摘要及源码/来源指纹见batch-92-evidence.json与原清单。

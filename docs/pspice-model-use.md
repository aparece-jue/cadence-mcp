# 未使用模型库的限定预检

官方参考SIM-LIB-READ-SCOPE说明LIB按需读取定义而INC读取全文。当前实现只处理无需任何库模型或子电路的平坦字面量R/C/L/V/I电路，无法替代一般模型/AKO/子电路依赖分析。

每个引用的物理行、指令和复制后路径均与manifest核对；INC/INCLUDE为立即读取，LIB为库定义。电路中的命名模型、X/U实例、参数表达式或未知指令均拒绝。只有确认未使用的可读子电路内数字U器件FILE模板可豁免；其他文件/路径形式继续拒绝。所有库字节保留，plan预览中的modelUseProof会在执行前及路径重定位后重新计算。旧的严格预检路径无需此证明。

加密块、未知顶层语句、未闭合作用域、混合LIB/INC身份不能获得证明。加密默认库仍导致原生AC案例拒绝，未将此情况视为原V04或端到端验收通过。例外路径失败时保留原unsupported_embedded_reference错误。

`tools/smoke_literal_library_cli.py --workspace-root <全新私有目录>`通过真实MCP验证自编分压器、未使用FILE模板库、独立2.5V预期及OUT/DAT来源。依赖本机已配置Cadence24.1；该最小案例不证明默认库或任意模型可用。失败过程和证据指纹见implementation/batch-98-evidence.json。

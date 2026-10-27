# 参数扫描复数DAT验收夹具

原创电路，Rtop在500Ω和1kΩ之间扫描；Rload=1kΩ，Cload=7uF，AC输入1V。独立解析式为`Vout=1/(1+Rtop/1000+j*2*pi*f*Rtop*7e-6)`，频率10、20、30Hz。`expected.json`在求解前生成，两个块按声明列表顺序对应两个电阻值，六个复数预期不由DAT读取生成。

`circuit.cir`使用本机官方文档中的强制节点选择`V([OUT])`。`circuit-ambiguous-probe.cir`保留首次歧义选择器失败输入，原生返回ORPSIM-15090；不是正例。两者的电路参数和独立数学预期相同。

`tools/smoke_step_ac_mcp.py --workspace-root <新私有目录> --fixture-root <本目录> --install-root <安装目录> --backend cli`验证实际MCP/CLI多块数值、分页、拒绝边界、CSV/JSON原生重读与新服务器幂等。独立引擎的单次doACAN未迭代STEP，现明确在建任务前拒绝；`tools/smoke_step_backend_guard.py`检查此边界。

仅支持单物理行、单个PARAM LIST字面列表扫描；不宣称其他STEP形式。此夹具的原生求解正例不修复原DAT10写入API异常，也不推断原生文件版本或数字状态标志含义。所有运行产物放入`.local`，不提交官方程序/工程或DAT。

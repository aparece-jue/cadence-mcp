# 第十四批：通用采样波形测量

2026-10-23。实际82工具；P03仍partial，原生MEAS解析与其他必需功能未完成，整体34项目标active。

## 契约与数值定义

新增pspice_dat_measure，支持summary/value_at/first_crossing，component为real/imaginary/magnitude，参数无eval/任意表达式。pspice_measure.py实施有限数值与严格单调实轴检查，最多100000点；DAT服务复用_all_samples，按精确已登记trace名字/alias调用native get。非法参数/缺trace先在主机拒绝，不将未知名字传到native。重复/非单调/复轴要求另行处理，不静默排序或丢点。

summary区分样本算术mean/RMS和轴区间加权piecewise-linear intervalMean/intervalRms；自适应采样下前者不能冒充物理时间平均。区间RMS对每段线性插值的平方精确积分，areaTrapezoidal按存储轴方向带符号；单点没有区间，interval字段为null。使用归一化避免平方溢出，最终派生范围不可表示则拒绝。

value_at在选定标量分量上分段线性插值，不外推；first_crossing按轴递增方向查找，支持rising/falling/either，明确返回not-found或plateau。复数magnitude先按采样点计算再作分量线性插值，不声称重建真实连续电路响应。单位仍来自名称约定或unknown，不假称native单位。返回revision、导入/verified-job provenance和producedByPlan；designPassed始终null。不是原生.MEAS执行/解析，不认证点间真实行为。

## 验收

7项主机测试包含：独立线性函数已知mean/RMS/带符号面积；反向轴、插值边界和外推拒绝；方向/未找到/平台交越；复数分量与实轴限制；非法参数/布尔值/数值溢出；普通导入provenance保持false且非法请求不进入native。

`.local/dat-measures-mcp-20261023/report.json`真实82工具/schema，复用第十三批已验证任务而未重求解；expected.json在调用前保存。DC来源为receipt-loss恢复正例，AC为未篡改的AC正例，transient为原541点正例：

- DC单点mean/RMS=2.5V，intervalRms=null，保留正确任务关联。
- AC截止频率处magnitude=1/sqrt(2)、imaginary=-0.5符合1e-6绝对阈值；magnitude下降交越截止频率误差≤1%。
- Transient 541点，intervalMean=0.8013474345482469V、intervalRms=0.838266810153108V，分别符合0..5ms RC解析积分的2e-4V阈值；tau处插值符合1-exp(-1)，上升交越0.001000004061376418s满足1%。阈值2V返回found=false/axisValue=null。
- 三组缺trace、错误参数组合、布尔axis和额外eval字段均拒绝；结果保留jobAssociationVerified/producedByPlan，不将采样计算扩大为设计安全通过。

完整222回归221通过、1原symlink权限skip，原始输出已保存；原生PSpice读取和Capture协议测试使用本机Tcl。契约同步真实tools/list。

## 仍需完成

原生MEAS/OUT测量与更完整诊断、通用相位展开/复杂不连续轴、原生单位、全部高级分析和CLI仍待验收。Capture profile/CIR生成、参数迭代、库/页/位号/层次/总线/DRC等原计划未缩减。下一优先回到Capture库创建/其他遗留核心能力，按失败队列继续。

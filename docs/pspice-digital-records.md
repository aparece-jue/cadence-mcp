# 数字瞬态变更记录

新增只读工具 `pspice_dat_digital_samples(datId, block, traceName, offset=0, limit=1000)`。先用 `pspice_dat_open` 导入允许读取的 DAT，再通过 `pspice_dat_query` 取得数字信号的准确名称或别名。导入数据仍属于文件来源；不能据此认定求解成功或关联到某个任务。

适用于本机24.1实测的完整数字/混合瞬态块：Time轴、完整数字目录、正数数字行列。返回逐条 `index/time/state/stateCode/strengthCode`，状态0..5对应0、1、X、R、F、Z。时间单位秒来自Time轴约定；强度返回原生0..63整数，不换算电压或电阻。字段明确标注这一有限范围。

固定原生工作进程使用 `reader getDigital <canonical>`。服务先按数字目录解析别名；工作进程再次枚举数字目录，只接受唯一准确名称。轴、模拟信号、缺失名称不得传给getDigital。曾在组合读取Time与DIN时发生独立进程异常，具体触发调用未能证明，原失败保留；后续仅读取真实数字目录成员通过。旧get/getR得到的模拟网格不能解释为数字值。

每条记录观察到四个原生字段：时间、强度码、状态字、未解释整数。最后一项只存于私有原始回执，既不返回也不解释。负数尾字段在官方示例快照中出现，因此验证其有符号32位/无符号32位范围。原生记录格式的通用性尚未证明。状态字超过5时，整条信号报 `unsupported_digital_state_flags`，即使请求的第一页不包含异常记录，也不截断返回。没有根据SDK的位掩码猜测getDigital标志含义。

分页依据每条信号自己的变更记录数。实测文件头7090行、212条数字信号，而INIT和RUN各只有4条变更记录。元数据的header行数保持原义，新增rowCountSource说明；样本接口的total来自实际记录。偏移超过单信号记录数报错。每次读取前后核验不可变快照；关闭会话后拒绝访问。原生reader关闭只调用一次，失败不重试。

## 已验收与保留问题

- 自建合法激励0→R→1→F→0→X→Z，在7us停止时共8记录；时间、六状态、500Ω与50Ω驱动的相对强弱、Z强度0通过独立预期及真实MCP复核。实测强度25/41，不声明一般换算公式。
- 原混合DIN的0→1→0→Z及末尾Z，共5记录通过。纯数字快照INIT别名U4:INIT及RUN各4记录、分页、重复读取、关闭和错误名称拒绝通过。所有源DAT字节未变。
- 非法R→F激励原生报告hazard并输出状态字26，原始失败保留；新接口安全拒绝整条信号。其标志解释、Probe显示一致性、剩余单位/格式边界、原DAT10多块写入异常仍未通过。P04保持deferred，原34项仍6项完整通过。
- 完整回归592项：591通过、1项原文件符号链接权限跳过。alpha.1发布包不变。

## 参考及复测

本机依据：PSpiceDigApiDefs.h的pspBitLevels枚举；PSpice用户指南数字仿真章的六状态/64强度；PSpice参考手册STIM允许的状态字符。getDigital签名来自实际SWIG参数错误和成功调用，不冒称官方文档已说明其全部记录格式。资料指纹见参考索引，官方正文和输出不提交。

自建源和独立预期位于 `tests/fixtures/digital-six-states/`；可使用现有受控PSpice执行流程在新的私有目录求解。`tools/smoke_digital_records.py`通过真实stdio服务复测，所有路径由参数提供：`--repo --output --install-root --read-root --legal-dat --mixed-dat --compressed-dat --flagged-dat`。后两类输入是保存在本机的既有快照/失败激励产物，不随仓库分发。脚本不启动GUI，也不重新执行DRC。

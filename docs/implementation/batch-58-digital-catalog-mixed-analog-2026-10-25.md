# 第五十八批：数字目录、混合模拟分区与关闭保护

记录日期2026-10-25，跨午夜已开始的.local证据目录保留20261024名称，不改历史文件身份。目标active，原34门禁保持1 baseline_passed/21 partial/10 deferred/2 planned；本批不宣称数字逻辑采样或完整P04完成。

## 实现

decode_headers增加严格数字/混合计数与trace角色。数字catalog不伪造模拟Time列：原生analogColumns0时getDataNames0仍返回Time的占位被排除，只按实际列数读取。数字列按本机getDataNames1的分号组拆分canonical/aliases，检查各名称长度、计数、空值、跨域歧义及总预算。纯数字7090行与混合模拟/数字不同网格分别记录；旧不完整mixed header明确digitalMetadataComplete=false，不能借它开放数值读取。

公共block/trace查询现能返回数字目录、别名及模拟/数字独立行列数。完全描述的mixed block可读取/测量其中analog trace；digital trace在调用数值native getter和测量轴之前拒绝。类型不依据trace名称猜测，数字列不套用V/I命名物理单位，sampleReadSupported/digitalReadSupported明确报告边界。

inspect_dat的native close改为一次尝试：发起close前取消清理重试标志，失败时返回错误并由进程退出释放资源，不再次close。真实受控single-trace/single-no-trace均0，double-close在第二次enter close后3221226505退出，证明不应重试未知close状态。初私有探针因重复close异常已保留；生产先前成功路径已单次close，本次补齐close返回失败时的清理边界。

工具仍155项，实际stdio契约同步元数据和mixed analog说明。PSpiceRuns可核验mixed的模拟分区，notChecked显式包含digital_logic_samples；数值通过仅指declared_trace_rows_only，designPassed始终null，不认证整个混合电路。

## Native/MCP验收

- 官方frqchk数字DAT复制/读取保持安装源hash1694bb1733d7d87ce8c0854972a248b972ef2acf0a9ea4670f4016b139aee1d5。1block、7090digital rows、212digital columns、0analog rows/columns；Native数字别名INIT组正确。数字样例get/getR及多种名字调用均空，不能作数字数值成功证据。
- digital-catalog-mcp：实际155工具读取目录并17条分页遍历212 canonical traces，INIT的4个aliases、分区行数和无物理单位声明准确；数字采样明确capability_unavailable、错误block/关闭session拒绝、fresh导入和副本篡改拒绝，源及oracle hash保持。
- 原创mixed夹具：根据本机pspcref03digita的STIM/UIO语法，独立1V/5V模拟源、1k负载与0/1/0/Z数字激励，不使用外部模型文件。新求解生成DataType2，analog58行/9列，digital5行/1列。native get DIN却返回58个零，不能当5个数字事件；该危险现象保留，数字sample/measure均拒绝。
- mixed-analog-run-mcp：全新公开prepare/plan/apply求解，全部模拟行V(ANALOG)=1V、V(DPWR)=5V、I(RLOAD)=1mA与独立预期1e-6容差一致，Time由0严格递增至4us；测量、plan/OUT/DAT关联与fresh apply/recover/open不重放通过。错误2V预期拒绝；DIN=0预期虽与错误模拟零向量吻合，仍按数字role拒绝、open拒绝/不重放。没有借数字假零值认证求解。
- complex-dat-after-digital：两次新生成原双块复数oracle，实际MCP数值/交错分页/边界/篡改全部通过。
- official-dat-after-digital：官方21块RFAMP复数兼容与EXAMPLE瞬态等12案例通过，源hash保持。

新增10项测试覆盖数字/混合计数、别名跨域碰撞、缺失字段、单位边界、旧mixed不完整分类、纯数字不伪造Time、数字不进入numeric worker/测量轴、mixed模拟取值和失败close不重试。先381完整回归380通过/1原权限skip；mixed模拟分区接入后最终383回归382通过/1原权限skip，无失败。证据及实现hash见batch-58-evidence.json。

## 保留问题

新增ISS-P04-digital-value-access记录数字getter空值/错误模拟网格问题，尚无可靠数字状态/强度/时间轴读取验收，不开放数字值接口。混合analog通过不能等同完整mixed/digital通过。DAT10多块writer AV、Capture3969、单位导出及其他34门禁遗留均保持。

下一继续P04可靠采样/单位导出并收敛已有失败；不添加任意eval、原生指针或客户端脚本入口。无GUI、安装或真实设计修改，无提交推送。

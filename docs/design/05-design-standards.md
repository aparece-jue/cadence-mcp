# 独立设计规范体系

## 1. 规范与执行分开

规范单独存储、版本化和审查，不写死在 MCP 工具描述、Tcl 脚本或 Skill 中。MCP 负责装载并执行可检查的规则；Skill 告诉 AI 何时选择 profile、如何处理冲突与交付报告。规范变化不要求修改 MCP 工具名。

规范同时含机器规则和人工检查项。规则名看似明确不代表算法已实现；未实现/缺证据时输出 unverified 或 manual_review，不能自动判通过。

## 2. 建议分层

|层|内容|示例|
|---|---|---|
|schema|规则字段、版本、兼容范围|规则 ID、selector、check、severity、source|
|base|通用数据库/连接完整性|位号唯一、引脚真实连接、隔离网不误合并|
|organization|组织标准|必填物料字段、标题栏、网名习惯、字体|
|discipline|领域规则|数字/模拟/隔离/电源/PSpice 建模|
|project|本工程批准的约束|供电范围、编号方式、接口定义、模型版本|
|user-layout|用户偏好 profile|功能框、文字、上下拉支路布局|
|waivers|具名、限对象、有限期例外|DRC 例外、受控的隐藏电源脚策略|

合并顺序为 base → organization → discipline → user-layout → project；只对声明可覆盖的字段执行后层覆盖。多个 discipline 同级冲突必须报错；base 中 locked 的连接完整性规则不能靠项目覆盖悄悄禁用。用户本次明确要求优先，并将其形成项目规则或可追踪豁免；合法工程特例不应被默认偏好阻断。

每个项目固定 profile 版本及解析后的 hash，不自动跟随“最新版”。更新时输出规则差异与受影响对象，确认采用后再重查。规则来源可以是本地规范文件、用户明确要求或物料数据手册，均需 provenance；不能将某个 STC 示例的坐标、复位极性、引脚数量变成通用标准。

## 3. 规则结构

每条至少包含 id、version、title、appliesTo、selector、check、parameters、severity、enforcement、overridable、source。check 只允许已注册 checker ID，不执行规则文件中的 Tcl/Python/表达式脚本。

- severity：error/warning/info。
- enforcement：block/report/manual；block 仅适用于已验证、判据客观的规则。
- selector：scope、对象类型及结构化属性筛选；不直接嵌入任意代码。
- source：规范文件条款、用户要求记录或数据手册版本；可附说明及审核人。
- checker 元数据另存：所需 snapshot 字段、支持 backend、单位、完整性条件、已验证版本。

`standards.example.json` 是草案，不是已批准工程标准。默认 profile 的数值和风格需项目首次采用时明确固定；不要把字体/框样式当作电气安全要求。

## 4. 原理图规则拆分

|规则族|建议内容|检查方式|
|---|---|---|
|SCH-ID|位号唯一、编号策略、封装/单元归属、映射完整|数据库自动；复杂编号须 occurrence 与 package-aware|
|SCH-CONN|预期节点连接、未连脚声明、junction、跨页/层次、隔离网|节点表 + 原生 DRC；覆盖范围必须完整|
|SCH-POWER|电源脚显式策略、global 同名合并、地命名|数据库与网表；隐藏脚策略需器件具体核对|
|SCH-PROP|型号/值/容差/额定值/物料字段、PCB Footprint 名字段|结构化字段检查；封装字段存在不证明实体库存在|
|SCH-LAYOUT|正交线、栅格、文字避让、模块框、标签短引线|几何规则 + PDF 图面审查；无可靠测量者列人工|
|SCH-LIB|物理脚号/名称/电气类型、可见性、多单元、缓存版本|OLB/DSN 分开核验，引用数据手册|
|SCH-DOC|页名、版本、标题栏、模块说明、交付清单|自动字段 + 人工内容检查|
|SIM-INPUT|参考节点 0、模型闭包、参数单位、分析适用性|CIR/依赖解析；PSpice 语法需支持的解析器|
|SIM-RESULT|预期数值/容差、求解诊断、测量定义、波形块|引擎结果 + 固定测量算法|

用户现有 Capture Skill 的 drawing-style.md 是偏好来源：功能框、Arial、关键说明、短标签、显式电源脚、单一地叫 GND、模块内自然直连、多路上下拉逐行横向支路等。建议迁移为 `user-layout/default@0.1.0`，原句保留来源，并区分“偏好”和“硬性连接约束”。其本机颜色/线型枚举属于适配器映射，不写入通用规范。

编号偏好“从 1 连续按阅读顺序”与仓库“按页 R2501”等策略不能同时默认启用。项目 profile 选择其一；同理，用户习惯的显式电源脚规则不能盲目改电气类型来规避隐藏连接。

工作目录已有《原理图设计规范整合指南.docx》，本轮未解析或修改；在后续建立正式规范时，可单独审阅并逐条提取来源、适用范围和可检验性，不能将其内容假定已合并。

## 5. 检查结果与例外

Finding 必须含 ruleId/ruleVersion、profileHash、status、severity、objectRef、expected、observed、evidenceArtifact、checkerVersion、coverage。status 枚举 pass/fail/not_applicable/unverified/manual_review/waived；not_applicable 需原因，缺字段不是 not_applicable。

豁免保存 waiverId、ruleId、具体对象范围、reason、owner、批准来源、createdAt、expiresAt 与关联工单（如有）。规则保留失败事实，再附有效 waiver；不删除 finding。过期或范围变化自动失效，不能用全局关闭掩盖个别例外。

报告至少分列：连接/原生 DRC、结构/属性、图面、仿真、人工待审、有效/过期豁免。所有自动检查通过但仍有人工项时，结论应为“自动项通过，人工项待审”，不能写“全部符合规范”。

## 6. 规范演进

先建立 10–20 条能稳定验证的基础规则，再增加布局和领域规则。每条机器规则至少配一个通过样例、一个失败样例及适用性边界。修改规则判据需变更版本并回归其样例；修改用户偏好不需要触发所有原生集成测试。

Skill 引用 profile ID，并调用 resolve/check；不得在每份 Skill 复制相同风格条款。API registry、工具契约和设计规范分别演进，通过 capability ID、checker ID 和版本范围关联。

## SCH-PDF-TEXT

原理图 PDF 默认由 File → Print 生成，必须保留可查找、可选择复制的原生文字层。以来源页的预期网络名、位号、标题和特殊字符逐页核对，并视觉检查符号、连线和文字完整。不得仅以文件存在、渲染成功、OCR 识别成功判定通过。驱动/字体改变需重验。独立网表交付与连接验证仍使用原生网表。

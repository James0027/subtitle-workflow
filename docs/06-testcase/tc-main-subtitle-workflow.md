# 首批源语闭环正式测试用例索引

版本：v0.1｜日期：2026-10-20｜状态：用例设计待评审；所有TC均NOT_RUN，没有产品/模型测试通过结论。

> 上游（我引用）：[主PRD](../05-prd/mainprd.md)、[子PRD索引](../05-prd/README.md)、[落地方案](../07-delivery-plans/source-release-solution.md)、[技术契约草案](../03-foundation/source-release-contract.md)、[测试规范](../../rules/testing.md)。
> 下游（引用我）：[实施计划](../07-delivery-plans/main-delivery-plan-source-release.md)；域内TC和未来执行报告。

## 1. 范围与方法

只处理“首批源语闭环”一个业务域，包括必要共享控制。翻译/文化/单位/口语的专门质量用例后续建立；CTX引用这些上游需求时仅验证共享资料/权限/规则供给。签发为首批SOURCE_CORE必需能力；仅外部成功回执为OPTIONAL_SHARED，不冒称平台已对接。

方法：决策表（条件/授权）、状态迁移、边界值（版本/时间/预算）、异常注入、跨模块场景。测试预期来自PRD；schema/技术草案仅补字段/操作，代码不反向定义预期。未定参数用符号或前置未齐，不能填课堂示例当生产标准。

## 2. 文件与数量

| 文件 | TC数 | 用途 |
| --- | --- | --- |
| [ASR](source-release/tc-source-asr.md) | 18 | 源语相关功能需求细化 |
| [CTX](source-release/tc-source-ctx.md) | 18 | 源语相关功能需求细化 |
| [E2E](source-release/tc-source-e2e.md) | 12 | 跨模块/边界/真实工具验证 |
| [EXEC](source-release/tc-source-exec.md) | 21 | 源语相关功能需求细化 |
| [INT](source-release/tc-source-int.md) | 24 | 源语相关功能需求细化 |
| [MAIN-A](source-release/tc-source-main-a.md) | 15 | 原主场景细化 |
| [MAIN-E](source-release/tc-source-main-e.md) | 15 | 原主场景细化 |
| [MAIN-N](source-release/tc-source-main-n.md) | 15 | 原主场景细化 |
| [OUT](source-release/tc-source-out.md) | 18 | 源语相关功能需求细化 |
| [REV](source-release/tc-source-rev.md) | 18 | 源语相关功能需求细化 |

共174条：原主15需求/45场景、局部39需求/117场景各落至少一条TC，另12条跨模块/边界/真实工具场景。全部是设计覆盖，不是执行覆盖；OPTIONAL_SHARED/REAL_TOOL分别列前置，不合并模拟和真实结果。

## 3. 数据、步骤与观察证据

数据配方：[fixture-recipes.json](source-release/fixtures/fixture-recipes.json)；合成人工参考：[reference.srt](source-release/fixtures/reference.srt)。配方要求通过有权操作建立前置状态，不直接注入HUMAN_APPROVED/PASS等预期结果。当前没有真实媒体或声音金标，没有生产SQL/数据库清理脚本。

能力ID见技术契约；执行器及具体curl/浏览器命令在T0.1技术/身份基线冻结后绑定，不伪造已可执行地址。每条TC已有前置、输入变体、明确操作、预期、执行端/界面观察、证据落点及限定清理。实际报告到第⑪步按执行批次建立，不提前生成PASS报告。

## 4. 需求→TC覆盖矩阵

| 需求 | 正常N | 异常E | 权限A | 范围 |
| --- | --- | --- | --- | --- |
| REQ-ASR-01 | [TC-SRC-ASR-01-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-01-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-01-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-ASR-02 | [TC-SRC-ASR-02-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-02-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-02-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-ASR-03 | [TC-SRC-ASR-03-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-03-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-03-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-ASR-04 | [TC-SRC-ASR-04-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-04-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-04-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-ASR-05 | [TC-SRC-ASR-05-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-05-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-05-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-ASR-06 | [TC-SRC-ASR-06-N](source-release/tc-source-asr.md) | [TC-SRC-ASR-06-E](source-release/tc-source-asr.md) | [TC-SRC-ASR-06-A](source-release/tc-source-asr.md) | SOURCE_CORE |
| REQ-CTX-01 | [TC-SRC-CTX-01-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-01-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-01-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-CTX-02 | [TC-SRC-CTX-02-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-02-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-02-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-CTX-03 | [TC-SRC-CTX-03-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-03-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-03-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-CTX-04 | [TC-SRC-CTX-04-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-04-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-04-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-CTX-05 | [TC-SRC-CTX-05-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-05-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-05-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-CTX-06 | [TC-SRC-CTX-06-N](source-release/tc-source-ctx.md) | [TC-SRC-CTX-06-E](source-release/tc-source-ctx.md) | [TC-SRC-CTX-06-A](source-release/tc-source-ctx.md) | SOURCE_CORE |
| REQ-EXEC-01 | [TC-SRC-EXEC-01-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-01-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-01-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-02 | [TC-SRC-EXEC-02-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-02-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-02-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-03 | [TC-SRC-EXEC-03-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-03-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-03-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-04 | [TC-SRC-EXEC-04-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-04-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-04-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-05 | [TC-SRC-EXEC-05-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-05-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-05-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-06 | [TC-SRC-EXEC-06-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-06-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-06-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-EXEC-07 | [TC-SRC-EXEC-07-N](source-release/tc-source-exec.md) | [TC-SRC-EXEC-07-E](source-release/tc-source-exec.md) | [TC-SRC-EXEC-07-A](source-release/tc-source-exec.md) | SOURCE_CORE |
| REQ-INT-01 | [TC-SRC-INT-01-N](source-release/tc-source-int.md) | [TC-SRC-INT-01-E](source-release/tc-source-int.md) | [TC-SRC-INT-01-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-02 | [TC-SRC-INT-02-N](source-release/tc-source-int.md) | [TC-SRC-INT-02-E](source-release/tc-source-int.md) | [TC-SRC-INT-02-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-03 | [TC-SRC-INT-03-N](source-release/tc-source-int.md) | [TC-SRC-INT-03-E](source-release/tc-source-int.md) | [TC-SRC-INT-03-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-04 | [TC-SRC-INT-04-N](source-release/tc-source-int.md) | [TC-SRC-INT-04-E](source-release/tc-source-int.md) | [TC-SRC-INT-04-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-05 | [TC-SRC-INT-05-N](source-release/tc-source-int.md) | [TC-SRC-INT-05-E](source-release/tc-source-int.md) | [TC-SRC-INT-05-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-06 | [TC-SRC-INT-06-N](source-release/tc-source-int.md) | [TC-SRC-INT-06-E](source-release/tc-source-int.md) | [TC-SRC-INT-06-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-07 | [TC-SRC-INT-07-N](source-release/tc-source-int.md) | [TC-SRC-INT-07-E](source-release/tc-source-int.md) | [TC-SRC-INT-07-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-INT-08 | [TC-SRC-INT-08-N](source-release/tc-source-int.md) | [TC-SRC-INT-08-E](source-release/tc-source-int.md) | [TC-SRC-INT-08-A](source-release/tc-source-int.md) | SOURCE_CORE |
| REQ-MAIN-R01 | [TC-SRC-MAIN-R01-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R01-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R01-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R02 | [TC-SRC-MAIN-R02-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R02-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R02-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R03 | [TC-SRC-MAIN-R03-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R03-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R03-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R04 | [TC-SRC-MAIN-R04-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R04-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R04-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R05 | [TC-SRC-MAIN-R05-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R05-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R05-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R06 | [TC-SRC-MAIN-R06-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R06-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R06-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R11 | [TC-SRC-MAIN-R11-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R11-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R11-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R12 | [TC-SRC-MAIN-R12-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R12-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R12-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R13 | [TC-SRC-MAIN-R13-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R13-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R13-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R14 | [TC-SRC-MAIN-R14-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R14-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R14-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R15 | [TC-SRC-MAIN-R15-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R15-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R15-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R16 | [TC-SRC-MAIN-R16-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R16-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R16-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R17 | [TC-SRC-MAIN-R17-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R17-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R17-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R18 | [TC-SRC-MAIN-R18-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R18-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R18-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-MAIN-R19 | [TC-SRC-MAIN-R19-N](source-release/tc-source-main-n.md) | [TC-SRC-MAIN-R19-E](source-release/tc-source-main-e.md) | [TC-SRC-MAIN-R19-A](source-release/tc-source-main-a.md) | SOURCE_CORE |
| REQ-OUT-01 | [TC-SRC-OUT-01-N](source-release/tc-source-out.md) | [TC-SRC-OUT-01-E](source-release/tc-source-out.md) | [TC-SRC-OUT-01-A](source-release/tc-source-out.md) | SOURCE_CORE |
| REQ-OUT-02 | [TC-SRC-OUT-02-N](source-release/tc-source-out.md) | [TC-SRC-OUT-02-E](source-release/tc-source-out.md) | [TC-SRC-OUT-02-A](source-release/tc-source-out.md) | SOURCE_CORE |
| REQ-OUT-03 | [TC-SRC-OUT-03-N](source-release/tc-source-out.md) | [TC-SRC-OUT-03-E](source-release/tc-source-out.md) | [TC-SRC-OUT-03-A](source-release/tc-source-out.md) | SOURCE_CORE |
| REQ-OUT-04 | [TC-SRC-OUT-04-N](source-release/tc-source-out.md) | [TC-SRC-OUT-04-E](source-release/tc-source-out.md) | [TC-SRC-OUT-04-A](source-release/tc-source-out.md) | SOURCE_CORE |
| REQ-OUT-05 | [TC-SRC-OUT-05-N](source-release/tc-source-out.md) | [TC-SRC-OUT-05-E](source-release/tc-source-out.md) | [TC-SRC-OUT-05-A](source-release/tc-source-out.md) | OPTIONAL_SHARED |
| REQ-OUT-06 | [TC-SRC-OUT-06-N](source-release/tc-source-out.md) | [TC-SRC-OUT-06-E](source-release/tc-source-out.md) | [TC-SRC-OUT-06-A](source-release/tc-source-out.md) | SOURCE_CORE |
| REQ-REV-01 | [TC-SRC-REV-01-N](source-release/tc-source-rev.md) | [TC-SRC-REV-01-E](source-release/tc-source-rev.md) | [TC-SRC-REV-01-A](source-release/tc-source-rev.md) | SOURCE_CORE |
| REQ-REV-02 | [TC-SRC-REV-02-N](source-release/tc-source-rev.md) | [TC-SRC-REV-02-E](source-release/tc-source-rev.md) | [TC-SRC-REV-02-A](source-release/tc-source-rev.md) | SOURCE_CORE |
| REQ-REV-03 | [TC-SRC-REV-03-N](source-release/tc-source-rev.md) | [TC-SRC-REV-03-E](source-release/tc-source-rev.md) | [TC-SRC-REV-03-A](source-release/tc-source-rev.md) | SOURCE_CORE |
| REQ-REV-04 | [TC-SRC-REV-04-N](source-release/tc-source-rev.md) | [TC-SRC-REV-04-E](source-release/tc-source-rev.md) | [TC-SRC-REV-04-A](source-release/tc-source-rev.md) | SOURCE_CORE |
| REQ-REV-05 | [TC-SRC-REV-05-N](source-release/tc-source-rev.md) | [TC-SRC-REV-05-E](source-release/tc-source-rev.md) | [TC-SRC-REV-05-A](source-release/tc-source-rev.md) | SOURCE_CORE |
| REQ-REV-06 | [TC-SRC-REV-06-N](source-release/tc-source-rev.md) | [TC-SRC-REV-06-E](source-release/tc-source-rev.md) | [TC-SRC-REV-06-A](source-release/tc-source-rev.md) | SOURCE_CORE |

## 5. 执行前条件与结果口径

实现接口/可信测试身份/隔离存储/Mock控制尚未建立，因此当前174条均未执行。真实工具用例另需首批素材/模型及人工参考；预算边界需批准B/币种/计次，未具备不运行。文档结构/链接/覆盖检查不计产品TC通过。

记录每个执行批次的实现/模型/输入/规则版本、输入输出/事件/拒绝、模拟范围与实际结果；失败保留证据，不通过改预期或去掉难例来通过。清理只限该TEST_RUN_ID沙箱，禁止真实素材或全库重置。

## 6. 回归集与发布演练

<a id="regression"></a>

本节统一定义用例选择与执行规则，承接本文件§1范围、§2清单和§4覆盖矩阵；灰度与回滚操作安排见[主计划§9](../07-delivery-plans/main-delivery-plan-source-release.md#rollout)。174条业务用例加6项发布演练，共180项设计，全部NOT_RUN。

此处“回归集”指变更后重复执行的既有用例集合。没有真实产品缺陷记录，不创建虚构的“历史缺陷回归”；将来实际缺陷修复需追加缺陷编号、触发输入与对应TC。复用174业务TC，另有6项发布演练；不重复计算分组交集为新增用例。

### 6.1 分组与触发

完整ID清单：[regression-manifest.json](source-release/regression-manifest.json)。它是选择清单，不是执行器；业务步骤仍以[cases.json](source-release/cases.json)/各详情为准，发布演练步骤见[六项用例](source-release/tc-source-e2e.md#release-operations)。

| 集合 | 用例数（存在重叠） | 何时执行 |
| --- | --- | --- |
| SMOKE | 13 | 每次可运行构建/修复后的快速检查；不能替代完整验收 |
| AUTH_STATE | 66 | 鉴权、预授权、状态、重试、预算、存储事务变更时 |
| SOURCE_QUALITY | 22 | 模型/工具/Prompt、切块、时间、语言或上下文处理变更时；真实用例缺样本则BLOCKED |
| EXPORT_HISTORY | 35 | 人工修订/回滚、解析器、文件生成、规范、校验或历史映射变更时 |
| FULL_CORE | 169 | 发布候选/G0准入、共享schema/编排变更、影响范围不明时 |
| REAL_TOOL | 2 | 发布候选、模型/真实工具/语种/输入条件变化时；不得用Mock替代 |
| OPTIONAL_SHARED | 3 | 仅当本版明确启用外部回执成功记录能力时；禁止越权的核心用例始终执行 |
| RELEASE_OPS | 6 | 试点开放前，停止/允许名单/回退/备份恢复实现变化及实际回退后 |

### 6.2 选择、结果与发布判定

1. 每次记录变更版本、影响模块、输入/规则/模型版本、测试数据、执行主体及选择理由。默认SMOKE加受影响模块完整用例和上下游；按上表取并集。测试人员不得仅挑成功路径。影响不明执行发布组合。
2. 人工编辑/锁定/回滚变更至少追加AUTH_STATE与EXPORT_HISTORY；共享schema/编排/鉴权底座变更追加FULL_CORE；模型/工具/时间处理变更追加SOURCE_QUALITY与REAL_TOOL；范围开关/备份/部署配置变更追加RELEASE_OPS。文档改动只做适用静态检查，不要求运行模型。
3. 本版发布候选与G0→G1准入执行FULL_CORE∪REAL_TOOL∪RELEASE_OPS，共177个独立ID；另有3条OPTIONAL_SHARED只在明确启用相应功能时加入。REAL_TOOL中路线须与冻结首批任务一致；不能因不支持而静默删失败项，调整范围须先修订批准基线。
4. 回退后至少执行SMOKE∪AUTH_STATE∪EXPORT_HISTORY∪RELEASE_OPS，并覆盖本次受影响模块；模型/工具改变再加SOURCE_QUALITY/REAL_TOOL，schema或影响不明执行发布组合。先在隔离环境演练，不在真实项目注入损坏数据。环境专用故障分支仍在隔离副本执行。
5. 结果区分PASS、FAIL、BLOCKED、NOT_RUN；不适用须列批准范围及依据，不能把它改写成PASS。当前全部NOT_RUN。Mock通过只能证明契约，真实质量需独立参考、版本和批准阈值。缺少执行器/授权/样本/阈值则BLOCKED。
6. 发布必需项不得存在未解释的FAIL/BLOCKED/NOT_RUN。真实模型阈值未批准不判达标；权限越界、冒充人审、锁定稿覆盖、文件与确认稿不一致等硬底线存在失败则禁止开放。未到观察窗口或未达有效样本要求不扩量。
7. 失败保留输入与证据；修复后重跑原失败用例、相关上下游与规定组合。报告保留首次失败和复测结果，不覆盖历史。实际缺陷进入本版缺陷记录后，再补最小复现用例，不伪造今天已发现产品bug。

### 6.3 执行记录

每个批次保存选择清单/hash、去重后TC列表、各分支结果、执行时间/环境/数据及版本、证据路径、缺陷/阻塞、复测关联、允许开放范围和审核决定。未来写入`docs/08-test-reports/<execution-id>/`；本轮仅静态检查放工作区work，不提前建立PASS报告。

现有计划/用例生成器已接入整合步骤，重生成时同步恢复本节和E2E演练并重算分组。新增/删改用例时仍须核查清单、链接与数量，禁止仅沿用文档中的旧数量。

### 6.4 影子验证参数化场景

复用已有用例的参数化分支，不新增TC ID或虚增174业务+6发布演练的条数。方法见[主计划§9.7](../07-delivery-plans/main-delivery-plan-source-release.md#shadow-validation)。本节分支同样全部NOT_RUN。

| 对应TC | 前置/数据 | 操作 | 预期与证据 |
| --- | --- | --- | --- |
| TC-SRC-E2E-09 质量正常对照 | 获准配对样本、独立人工参考、隔离候选区；固定输入/模型/规则和评估人 | 正常链路与影子独立处理，事后由获准评估人核对内容/时间；记录短长输入耗时/队列/内存 | 配对可追溯，影子不影响人工/交付；只报实际差异/耗时，未批准阈值不判达标；保留输入、版本、原始差异与评测记录 |
| TC-SRC-E2E-06 撤权/停止异常 | 影子在途调用及尚未领取任务，Mock晚到/超时；预算符号使用批准B | 撤销许可或触及停止条件，返回晚到输出，查询正常链路与费用 | 停新调用、正常稿不受影响，晚到结果隔离并保留费用；实测和Mock分报，证据含时间线/写入拒绝/账单 |
| TC-SRC-E2E-08 影子越权 | 服务主体只有影子运行/候选权限，正常稿和人工权限均保持有效 | 请求写正常稿、给正常审稿人展示、触发正式后续/导出或冒充人工签发 | 执行端拒绝，正常稿/决定无变化，没有伪造展示/接受/签发事件；证据含实际请求与拒绝、前后版本和事件 |

执行前仍需实现、可信测试鉴权和隔离数据；只清TEST_RUN_ID下核验过的测试副本，保留原样本/失败证据。真实数据处理和模型费用没有许可时BLOCKED。

## 7. 版本记录

v0.1：建立首批源语单一业务域174条正式TC设计和54条需求的三类覆盖映射。未安装依赖、执行产品、调用模型或对接平台；开发/测试阶段另补真实结果。

v0.2：灰度/回滚并入主计划§9，回归规则并入本文件§6，发布演练并入既有E2E详情；保留174业务+6演练及稳定ID，全部NOT_RUN。

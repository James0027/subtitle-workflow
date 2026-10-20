# 源语闭环正式TC：E2E

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-E2E-01：正常源语闭环

- 依据：REQ-MAIN-R17；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：正常源语闭环。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 创建Task草稿→ingest抽轨/母版确认→同ID确认Task→ASR模拟→编辑完成待审→有权真人审两条→内部生成/校验→真人签发→正式导出；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：两cue与reference.srt正文/时间对应；内部VALIDATED时Task不完成；真人签发为PUBLISH_READY并正式导出有记录后Task完成，仍非PUBLISHED；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-01/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-02：空结果阻断后续

- 依据：REQ-MAIN-R06；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：空结果阻断后续。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② Mock返回EMPTY_RESULT，再尝试审稿/导出；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：Run为FAILED，后续未执行，无成功源稿；保留失败和实际调用；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-02/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-03：并发分支边界

- 依据：REQ-MAIN-R13；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：并发分支边界。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 同source分支r并发两次保存；另用独立variant作为对照；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：同分支一份成功另一份冲突；独立分支不被误覆盖；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-03/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-04：任务范围边界

- 依据：REQ-MAIN-R02；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：任务范围边界。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 分别提交[0,6000)、[0,6001)、[2000,2000)、重叠两区间；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：合法边界可保存，越界/零长/重叠拒绝；不得静默修正范围；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-04/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-05：请求内容冲突

- 依据：REQ-MAIN-R14；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：请求内容冲突。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 同request_key先创建purpose=A，后提交purpose=B；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：同内容重送返回原Task，异内容冲突；不是默默返回旧意图；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-05/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-06：撤权和晚到账单

- 依据：REQ-MAIN-R15；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：撤权和晚到账单。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 允许调用已在途→撤权→返回结果/迟到账单→请求下步；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：不新调用或推进，结果受控留存，累计费用不丢且估算不双算；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-06/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-07：生成器损失探测

- 依据：REQ-MAIN-R17；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：生成器损失探测。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 分别让生成器删“没”、移动时间、丢必要标签；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：实际解析差异可定位，不能VALIDATED；不以文件存在判成功；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-07/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-08：服务主体不能冒充人

- 依据：REQ-MAIN-R18；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：服务主体不能冒充人。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 以service_actor提交confirm_master、内容确认、signoff；伪造请求actor_role；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：执行端全部拒绝；人类字段无变化，无真实发布调用；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-08/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-09：真实转写质量评估

- 依据：REQ-MAIN-R19；跨模块补充场景；[任务T4.1](../../07-delivery-plans/sub-delivery-plan-source-release-T4.1-acceptance-readiness.md)；状态：NOT_RUN；范围：REAL_TOOL。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：真实转写质量评估。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 使用已授权首批声音及独立人工参考，固定模型/参数后计算WER/CER/边界误差；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：记录实测值、评估版本/样本；阈值未批准不判达标，Mock结果不能当真实质量；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-09/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-10：已有稿对齐能力验证

- 依据：REQ-MAIN-R06；跨模块补充场景；[任务T4.1](../../07-delivery-plans/sub-delivery-plan-source-release-T4.1-acceptance-readiness.md)；状态：NOT_RUN；范围：REAL_TOOL。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：已有稿对齐能力验证。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 真实工具接已知text/start/end窗口，并加入无窗口/词典外字/对齐回退变体；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：文字不变；回退旧时间/缺词时间标未对齐或必审，不能只因返回时间就成功；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-10/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-11：重启不重复调用

- 依据：REQ-MAIN-R15；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：重启不重复调用。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 运行在途时终止测试服务并恢复，再查询/申请继续；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：持久attempt/费用保留，未知调用结局等待核对，不自动重复收费；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-11/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

### TC-SRC-E2E-12：视频有声与无声分支

- 依据：REQ-MAIN-R01；跨模块补充场景；[任务T3.2](../../07-delivery-plans/sub-delivery-plan-source-release-T3.2-workbench-integration.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实际实现及隔离夹具；REAL_TOOL另需D02/D03、真实模型/人工参考，当前未具备。主体：按场景的可信测试主体。
- 数据：fixture-recipes的独立TEST_RUN_ID；按步骤准备参数化变体。原场景条件：视频有声与无声分支。
- 步骤：① 记录输入/修订及工具调用基线；真实模型用例禁用Mock替代；② 分别只交含声视频及无声视频；人工确认请求按各自结果进行；③ 查询对应实体/事件/实际字节与调用记录；UI反馈单独对照。
- 预期：含声视频可派生音轨；无声阻断ASR并请求补料，人也不能凭空听打；不得把模拟通过计入真实模型/平台效果。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-E2E-12/（未建立）`；实际结果留空，不能凭文档检查填PASS。
- 清理：只清本次沙箱，保留失败证据；不得删除真实样本。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-E2E-01 | REQ-MAIN-R17 | normal | NOT_RUN |
| TC-SRC-E2E-02 | REQ-MAIN-R06 | exception | NOT_RUN |
| TC-SRC-E2E-03 | REQ-MAIN-R13 | exception | NOT_RUN |
| TC-SRC-E2E-04 | REQ-MAIN-R02 | exception | NOT_RUN |
| TC-SRC-E2E-05 | REQ-MAIN-R14 | exception | NOT_RUN |
| TC-SRC-E2E-06 | REQ-MAIN-R15 | exception | NOT_RUN |
| TC-SRC-E2E-07 | REQ-MAIN-R17 | exception | NOT_RUN |
| TC-SRC-E2E-08 | REQ-MAIN-R18 | permission | NOT_RUN |
| TC-SRC-E2E-09 | REQ-MAIN-R19 | normal | NOT_RUN |
| TC-SRC-E2E-10 | REQ-MAIN-R06 | exception | NOT_RUN |
| TC-SRC-E2E-11 | REQ-MAIN-R15 | exception | NOT_RUN |
| TC-SRC-E2E-12 | REQ-MAIN-R01 | exception | NOT_RUN |

## 发布控制演练

<a id="release-operations"></a>

本节接续前面的12条端到端业务用例，增加6项发布控制演练；均归属T4.1。执行策略以[测试总入口§6](../tc-main-subtitle-workflow.md#regression)为准，操作依据见[主计划§9](../../07-delivery-plans/main-delivery-plan-source-release.md#rollout)。机器可读镜像：[release-operations.json](release-operations.json)。

这是174条既有业务TC之外的6项发布控制演练设计，合计180条；不更改业务REQ/AC数量。不伪造历史缺陷用例；以后实际缺陷另绑定缺陷编号。

共同前置：已实现的隔离版本/可信测试鉴权、批准版本和范围、受控故障注入、可核验的备份与文件清单、实现后的操作命令及证据采集。真实模型/素材/收费另需相应许可。全部实际命令待实现绑定；现阶段不能直接执行。测试数据/主体使用独立TEST_RUN_ID，经有权能力建立状态；不得注入人工确认或测试PASS。各分支独立重建夹具，先记录正常基线。

执行主体：有明确试点/停止/恢复权限的测试主体；human_denied/service_actor作为拒绝对照，不默认服务有真人签署权。

### TC-SRC-REL-01：灰度允许范围与撤回

- 依据：REQ-MAIN-R03 / R04 / R05；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：隔离项目A/B；主体允许/不允许各一，route和语种题材固定；准备关闭、开启、撤回三种配置修订。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 关闭时申请新任务；只开启A的指定任务/语种/题材/route，再以未列入的各对照申请；撤回后重新申请并模拟旧配置缓存；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：只有名单和全部范围条件匹配且有业务权限者进入；关闭/撤回后执行端拒绝新调用，不能靠缓存或直接API绕过，原数据不删除。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-01/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

### TC-SRC-REL-02：触发阻断与在途结果隔离

- 依据：REQ-MAIN-R05 / R15 / R17；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：获准试点版本；各准备一个在途Run和未领取任务，Mock晚到输出；另准备可控导出差异或越权故障。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 在隔离环境注入故障并按已定停止条件触发处置；关闭受影响入口/领取；返回在途输出并请求下步；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：新调用和状态推进停止，原确认稿不覆盖；晚到结果隔离且原Task成本保留；影响范围不明时整个试点保持关闭，责任人可定位故障。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-02/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

### TC-SRC-REL-03：系统回退兼容与不兼容分支

- 依据：REQ-MAIN-R14 / R15；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：两组版本清单old/new；数据副本各准备兼容及不兼容schema/文件；原Run固定new manifest；另备已过期/撤回规则或许可，以及未验证的旧代码+新规则组合。。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 停止新调用并备份；在副本检查old读取当前数据，分别演练兼容切换、不兼容拒绝和首版无old；检查旧worker返回；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：兼容时新请求绑定old且原Run仍引用new；不兼容不破坏性降级，无old则关闭转人工；旧worker不推进，新旧输出/费用可回查；补充：旧规则/profile或许可已过期/撤回、旧代码与新规则组合未经验证，均不得直接重新启用；历史可回查，无可用组合关闭自动能力并交人工。。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-03/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

在隔离环境分别申请恢复上述失效/未验证组合，核对实际拒绝及无可用组合时关闭/人工接手。

### TC-SRC-REL-04：一致性备份恢复与失败分支

- 依据：REQ-MAIN-R13 / R14 / R15 / R16 / R17；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：隔离沙箱内有效备份及manifest；备份后新增人工决定/调用记录；另复制一份损坏或缺文件的备份。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 分别恢复到独立沙箱；核对数据库与文件hash/决定/版本，列出恢复点后差额并核对费用；对损坏备份尝试恢复；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：有效备份可核验且差额可对账，未核实调用不重发；损坏/不完整恢复不得替换工作数据或重新开放，不丢掉备份后的人工决定/费用。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-04/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

### TC-SRC-REL-05：回退后验证与受控恢复

- 依据：REQ-MAIN-R04 / R11 / R15 / R17；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：入口关闭且已恢复的隔离版本，具备运行/恢复权主体及无恢复权对照；必要回归结果分别设真实失败/未执行/通过的执行记录。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 在各结果分支提交恢复申请；无权者和服务主体尝试越权；有权人核对实际证据后只重开指定范围，完成一笔源稿人审导出；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：回归失败/缺证据或权限不足不能开放；有效恢复只开放明确范围，最终人审未被代签，文件解析/追踪一致；不得把手工伪造PASS当结果。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-05/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

### TC-SRC-REL-06：观察与扩量条件

- 依据：REQ-MAIN-R04 / R15 / R19；灰度/回滚安排；实施归属T4.1。状态：NOT_RUN。
- 数据：独立模拟批次，固定cohort/as_of；分别缺数量上限/窗口/阈值，观察未满、零分母、指标超限及有效通过；扩大到新语种另缺评测。
- 步骤：① 建立上述独立夹具并记录数据/版本/hash/权限基线；② 分别计算并查看真实原始事件；未获批准主体请求扩量；补全合格证据后由有权人明确批准新名单，检查旧失败批次仍存在；③ 比较实际调用、持久结果、文件和界面反馈，保存逐分支证据。
- 预期：缺参数/观察不足/超限/零有效样本/无权不扩量；新语种无真实评测不得开放；合格分支仅扩大批准范围，原失败与未知指标不被抹掉。
- 证据：未来保存到`docs/08-test-reports/<execution-id>/TC-SRC-REL-06/`，含时间线、前后版本、范围/身份、调用/费用、数据与文件hash、操作结果和拒绝原因。实际结果目前为空。
- 清理：只删除已核验属于TEST_RUN_ID的隔离副本；原样本、真实人工稿、故障及恢复证据保留，禁止在生产做故障注入或直接覆盖数据库。

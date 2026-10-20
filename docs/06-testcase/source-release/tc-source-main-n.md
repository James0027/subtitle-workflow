# 源语闭环正式TC：MAIN-N

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-MAIN-R01-N：对应视频和可用声音登记后，有权人核对

- 依据：REQ-MAIN-R01；AC-MAIN-R01-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：视频v1和同剪辑声音a1，核对引用齐备。原场景条件：对应视频和可用声音登记后，有权人核对。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前素材/核对Ref及expected_revision提交confirm_master；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：生成确认母版及来源记录；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R02-N：母版/任务/范围齐备并确认

- 依据：REQ-MAIN-R02；AC-MAIN-R02-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：母版和Task已确认、6000ms有声、manual许可。原场景条件：母版/任务/范围齐备并确认。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按当前Task/输入/规则请求阶段检查或上下文组装，查询readiness和缺项；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：相应readiness为ready，可申请执行；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R03-N：用户提供合格源稿/目标要求，仅选翻译

- 依据：REQ-MAIN-R03；AC-MAIN-R03-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：确认source_only+module_only，仅ASR。原场景条件：用户提供合格源稿/目标要求，仅选翻译。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：只跑所选模块及必要检查，完成不称全链交付；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R04-N：有权人授予当前任务范围

- 依据：REQ-MAIN-R04；AC-MAIN-R04-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：真人授予当前task_revision/模块/actions。原场景条件：有权人授予当前任务范围。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以授予主体提交scope/原因；撤销变体在领取/调用前提交撤销并等待返回；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保存授权/决定；每次动作引用有效许可；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R05-N：有有效授权、准入/校验均通过

- 依据：REQ-MAIN-R05；AC-MAIN-R05-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：合成准入通过；候选AI_PROPOSED。原场景条件：有有效授权、准入/校验均通过。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：中间候选继续，仍AI_PROPOSED；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R06-N：可用声音按指定范围转写/对齐

- 依据：REQ-MAIN-R06；AC-MAIN-R06-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：分别建立三份明确route的任务，Mock返回相应文字/时间。原场景条件：可用声音按指定范围转写/对齐。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：输出文字/时间候选、疑点及版本记录；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R11-N：有权人保存编辑草稿再明确确认

- 依据：REQ-MAIN-R11；AC-MAIN-R11-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：当前候选text有“没有”，人编辑标点后确认。原场景条件：有权人保存编辑草稿再明确确认。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：分别留草稿/决定及新修订；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R11-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R12-N：一批可接受当前候选

- 依据：REQ-MAIN-R12；AC-MAIN-R12-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两条当前可接受候选，共享batch/operation。原场景条件：一批可接受当前候选。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：逐条决定且共享批次引用；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R12-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R13-N：人工确认后新模型运行

- 依据：REQ-MAIN-R13；AC-MAIN-R13-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：同分支r上有权人工修改；另一分支独立。原场景条件：人工确认后新模型运行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：另存候选，确认稿不变；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R13-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R14-N：用产物回查task/run/attempt/step、输入输出/manifest及决定

- 依据：REQ-MAIN-R14；AC-MAIN-R14-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：文件→Segment→Candidate→Run/attempt/step→输入/决定。原场景条件：用产物回查task/run/attempt/step、输入输出/manifest及决定。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：关联齐全；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R14-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R15-N：在已批准预算/次数内的合法运行

- 依据：REQ-MAIN-R15；AC-MAIN-R15-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：有权恢复，根因已解除；预算用批准参数B。原场景条件：在已批准预算/次数内的合法运行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：真实成本/尝试可查；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R15-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R16-N：有权人恢复历史内容

- 依据：REQ-MAIN-R16；AC-MAIN-R16-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：当前r引用历史h，复制h内容为r+1。原场景条件：有权人恢复历史内容。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 选择历史修订并提交rollback，随后查询新修订和受影响依赖；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：新修订及决定，受影响检查/签发重新验证；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R16-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R17-N：人工确认源稿按任务规格导出且解析一致

- 依据：REQ-MAIN-R17；AC-MAIN-R17-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：使用人工参考两cue，与当前确认稿一致。原场景条件：人工确认源稿按任务规格导出且解析一致。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：VALIDATED源语文件及记录；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R17-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R18-N：同一人有审稿/签发权

- 依据：REQ-MAIN-R18；AC-MAIN-R18-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：首批必需签发；真人fixture有内容审核、当前包签发及下载权限。原场景条件：同一人有审稿/签发权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 在首批测试环境完成真人内容审核、内部文件校验后，由有权真人提交当前包/hash的signoff；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：内容确认及当前包检查完成后同页签发；真实回执才PUBLISHED；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R18-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R19-N：冻结批次记录完整人工/等待/返工、失败和版本

- 依据：REQ-MAIN-R19；AC-MAIN-R19-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：固定cohort和as_of，实际/估算费用分列。原场景条件：冻结批次记录完整人工/等待/返工、失败和版本。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：按metrics复算目标指标；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R19-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-MAIN-R01-N | REQ-MAIN-R01 | normal | NOT_RUN |
| TC-SRC-MAIN-R02-N | REQ-MAIN-R02 | normal | NOT_RUN |
| TC-SRC-MAIN-R03-N | REQ-MAIN-R03 | normal | NOT_RUN |
| TC-SRC-MAIN-R04-N | REQ-MAIN-R04 | normal | NOT_RUN |
| TC-SRC-MAIN-R05-N | REQ-MAIN-R05 | normal | NOT_RUN |
| TC-SRC-MAIN-R06-N | REQ-MAIN-R06 | normal | NOT_RUN |
| TC-SRC-MAIN-R11-N | REQ-MAIN-R11 | normal | NOT_RUN |
| TC-SRC-MAIN-R12-N | REQ-MAIN-R12 | normal | NOT_RUN |
| TC-SRC-MAIN-R13-N | REQ-MAIN-R13 | normal | NOT_RUN |
| TC-SRC-MAIN-R14-N | REQ-MAIN-R14 | normal | NOT_RUN |
| TC-SRC-MAIN-R15-N | REQ-MAIN-R15 | normal | NOT_RUN |
| TC-SRC-MAIN-R16-N | REQ-MAIN-R16 | normal | NOT_RUN |
| TC-SRC-MAIN-R17-N | REQ-MAIN-R17 | normal | NOT_RUN |
| TC-SRC-MAIN-R18-N | REQ-MAIN-R18 | normal | NOT_RUN |
| TC-SRC-MAIN-R19-N | REQ-MAIN-R19 | normal | NOT_RUN |

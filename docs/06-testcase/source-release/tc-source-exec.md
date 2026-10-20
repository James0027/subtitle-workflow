# 源语闭环正式TC：EXEC

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-EXEC-01-N：单模块确认且前置齐

- 依据：REQ-EXEC-01；AC-EXEC-01-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：确认source_only+module_only，仅ASR。原场景条件：单模块确认且前置齐。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：仅跑选定范围并按自身终点交接；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-01-E：缺输入/不完整多语任务

- 依据：REQ-EXEC-01；AC-EXEC-01-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：未确认/缺声音或不完整多语任务。原场景条件：缺输入/不完整多语任务。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：待补，不自动降范围；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-01-A：无该模块执行权

- 依据：REQ-EXEC-01；AC-EXEC-01-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无该模块执行权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不因能看Task而可执行；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-02-N：有权授予准确scope

- 依据：REQ-EXEC-02；AC-EXEC-02-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：真人授予当前task_revision/模块/actions。原场景条件：有权授予准确scope。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以授予主体提交scope/原因；撤销变体在领取/调用前提交撤销并等待返回；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：实际动作重验后执行；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-02-E：撤权与启动并发/在途返回

- 依据：REQ-EXEC-02；AC-EXEC-02-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：授权撤销与领取Run并发；模拟晚到返回。原场景条件：撤权与启动并发/在途返回。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以授予主体提交scope/原因；撤销变体在领取/调用前提交撤销并等待返回；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：阻止新动作并隔离晚到结果；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-02-A：无授予/撤销权

- 依据：REQ-EXEC-02；AC-EXEC-02-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无授予/撤销权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 向当前任务提交明确principal/modules/actions的授予请求；撤销分支独立重复；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，保留真实检查结果；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-03-N：有效授权且准入通过

- 依据：REQ-EXEC-03；AC-EXEC-03-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：合成准入通过；候选AI_PROPOSED。原场景条件：有效授权且准入通过。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：中间AI_PROPOSED可继续；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-03-E：未定义准入/硬阻断

- 依据：REQ-EXEC-03；AC-EXEC-03-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：没有准入版本/有硬阻断，但请求继续。原场景条件：未定义准入/硬阻断。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：等待人工，不伪造确认；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-03-A：预授权企图改锁定稿或代签最终内容

- 依据：REQ-EXEC-03；AC-EXEC-03-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：预授权企图改锁定稿或代签最终内容。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交原场景指定的accept/edit_accept/改时间或锁定正文写入请求；使用当前Ref/修订保证拒绝来自动作权限而非缺料；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-04-N：同key重送

- 依据：REQ-EXEC-04；AC-EXEC-04-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：相同Task/manifest/分支/范围，两次提交。原场景条件：同key重送。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、配置变化关联新Run而非重置费用；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：一组有效结果，attempt/step可追；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-04-E：超时/配置变化

- 依据：REQ-EXEC-04；AC-EXEC-04-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：客户端超时后再次提交；输入改配置。原场景条件：超时/配置变化。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、配置变化关联新Run而非重置费用；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：查询在途或关联新Run，原失败留存；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-04-A：跨项目输入/目标版本不符

- 依据：REQ-EXEC-04；AC-EXEC-04-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：跨项目输入/目标版本不符。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、配置变化关联新Run而非重置费用；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝调用和写入；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-05-N：有权恢复且根因解除

- 依据：REQ-EXEC-05；AC-EXEC-05-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：有权恢复，根因已解除；预算用批准参数B。原场景条件：有权恢复且根因解除。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：重检后只跑获准范围；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-05-E：并发Run、取消、晚到账单

- 依据：REQ-EXEC-05；AC-EXEC-05-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：B+epsilon、连续重试停止、并发运行或晚到账单。原场景条件：并发Run、取消、晚到账单。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：累计不丢，超预算/重试即停；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-05-A：无恢复权/换Run逃避停止

- 依据：REQ-EXEC-05；AC-EXEC-05-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无恢复权/换Run逃避停止。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝继续；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-06-N：真实事件去重

- 依据：REQ-EXEC-06；AC-EXEC-06-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：固定cohort和as_of，实际/估算费用分列。原场景条件：真实事件去重。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：费用/人工/等待可复算；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-06-E：迟到/零分母/未满窗

- 依据：REQ-EXEC-06；AC-EXEC-06-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：重复/迟到事件，零分母或观察未满窗。原场景条件：迟到/零分母/未满窗。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：重算或不可判定，不补0/成功；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-06-A：无原始记录读取权

- 依据：REQ-EXEC-06；AC-EXEC-06-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无原始记录读取权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝受限数据导出；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-07-N：产物

- 依据：REQ-EXEC-07；AC-EXEC-07-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：文件→Segment→Candidate→Run/attempt/step→输入/决定。原场景条件：产物。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：Task/Run/attempt/step/输入/决定可回查；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-07-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-07-E：缺步骤/失效输入

- 依据：REQ-EXEC-07；AC-EXEC-07-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：删除可控夹具中的一条引用关系模拟缺口。原场景条件：缺步骤/失效输入。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：显示缺口且不冒称完整追踪；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-07-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-EXEC-07-A：他项目追踪或敏感正文

- 依据：REQ-EXEC-07；AC-EXEC-07-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：他项目追踪或敏感正文。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝且不暴露存储凭据；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-EXEC-07-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-EXEC-01-N | REQ-EXEC-01 | normal | NOT_RUN |
| TC-SRC-EXEC-01-E | REQ-EXEC-01 | exception | NOT_RUN |
| TC-SRC-EXEC-01-A | REQ-EXEC-01 | permission | NOT_RUN |
| TC-SRC-EXEC-02-N | REQ-EXEC-02 | normal | NOT_RUN |
| TC-SRC-EXEC-02-E | REQ-EXEC-02 | exception | NOT_RUN |
| TC-SRC-EXEC-02-A | REQ-EXEC-02 | permission | NOT_RUN |
| TC-SRC-EXEC-03-N | REQ-EXEC-03 | normal | NOT_RUN |
| TC-SRC-EXEC-03-E | REQ-EXEC-03 | exception | NOT_RUN |
| TC-SRC-EXEC-03-A | REQ-EXEC-03 | permission | NOT_RUN |
| TC-SRC-EXEC-04-N | REQ-EXEC-04 | normal | NOT_RUN |
| TC-SRC-EXEC-04-E | REQ-EXEC-04 | exception | NOT_RUN |
| TC-SRC-EXEC-04-A | REQ-EXEC-04 | permission | NOT_RUN |
| TC-SRC-EXEC-05-N | REQ-EXEC-05 | normal | NOT_RUN |
| TC-SRC-EXEC-05-E | REQ-EXEC-05 | exception | NOT_RUN |
| TC-SRC-EXEC-05-A | REQ-EXEC-05 | permission | NOT_RUN |
| TC-SRC-EXEC-06-N | REQ-EXEC-06 | normal | NOT_RUN |
| TC-SRC-EXEC-06-E | REQ-EXEC-06 | exception | NOT_RUN |
| TC-SRC-EXEC-06-A | REQ-EXEC-06 | permission | NOT_RUN |
| TC-SRC-EXEC-07-N | REQ-EXEC-07 | normal | NOT_RUN |
| TC-SRC-EXEC-07-E | REQ-EXEC-07 | exception | NOT_RUN |
| TC-SRC-EXEC-07-A | REQ-EXEC-07 | permission | NOT_RUN |

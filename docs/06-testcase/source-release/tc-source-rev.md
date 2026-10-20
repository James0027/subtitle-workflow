# 源语闭环正式TC：REV

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-REV-01-N：有效候选接受或编辑后确认

- 依据：REQ-REV-01；AC-REV-01-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：当前候选text有“没有”，人编辑标点后确认。原场景条件：有效候选接受或编辑后确认。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；保存并提交审核仅追加review.submitted/待审，另由有审核权限的真人确认；编辑主体自行确认的权限对照须拒绝；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：新修订且两类接受分开；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-01-E：草稿保存/驳回

- 依据：REQ-REV-01；AC-REV-01-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：独立提交edit/reject，不能当accept。原场景条件：草稿保存/驳回。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；保存并提交审核仅追加review.submitted/待审，另由有审核权限的真人确认；编辑主体自行确认的权限对照须拒绝；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：不假称确认，未决保留；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-01-A：无内容确认权

- 依据：REQ-REV-01；AC-REV-01-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无内容确认权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；保存并提交审核仅追加review.submitted/待审，另由有审核权限的真人确认；编辑主体自行确认的权限对照须拒绝；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝决定写入，草稿不升级确认；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-02-N：合法批量

- 依据：REQ-REV-02；AC-REV-02-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两条当前可接受候选，共享batch/operation。原场景条件：合法批量。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：按条决定且共享batch_id；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-02-E：一条旧版/缺证据

- 依据：REQ-REV-02；AC-REV-02-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：预览后第二条版本增加或必审未完。原场景条件：一条旧版/缺证据。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：该条失败/跳过，其他逐项反馈；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-02-A：预览后某项撤权

- 依据：REQ-REV-02；AC-REV-02-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_partial。
- 数据：两个当前候选s1/s2；该主体仅可处理s1。另以预览后撤销s2授权作第二个参数化变体。原场景条件：预览后某项撤权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交同一batch内s1与s2；逐条查询决定和返回，不整体绕过s2权限；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：该项拒绝，其他仍独立检查；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-03-N：有权人工修订

- 依据：REQ-REV-03；AC-REV-03-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：同分支r上有权人工修改；另一分支独立。原场景条件：有权人工修订。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留旧稿及分支版本；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-03-E：同分支并发

- 依据：REQ-REV-03；AC-REV-03-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两个提交同expected_revision；预置稿通过获准锁定流程建立。原场景条件：同分支并发。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：旧expected_revision拒绝并保留编辑；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-03-A：Agent改人工锁定稿

- 依据：REQ-REV-03；AC-REV-03-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：service_actor。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：Agent改人工锁定稿。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交原场景指定的accept/edit_accept/改时间或锁定正文写入请求；使用当前Ref/修订保证拒绝来自动作权限而非缺料；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，只能另存候选；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-04-N：回滚历史内容

- 依据：REQ-REV-04；AC-REV-04-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：当前r引用历史h，复制h内容为r+1。原场景条件：回滚历史内容。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 选择历史修订并提交rollback，随后查询新修订和受影响依赖；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：新修订并列受影响复检；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-04-E：依赖不全

- 依据：REQ-REV-04；AC-REV-04-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：受影响依赖缺失；新版试图复用旧PASS。原场景条件：依赖不全。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 选择历史修订并提交rollback，随后查询新修订和受影响依赖；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：相关交付待核，旧PASS不作新稿证据；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-04-A：无回滚权/跨项目历史

- 依据：REQ-REV-04；AC-REV-04-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无回滚权/跨项目历史。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 指定当前r和历史h，提交rollback及reason，不得仅删除历史或直接改指针；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝且不泄露正文；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-05-N：有权人补证裁决

- 依据：REQ-REV-05；AC-REV-05-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：合成需要有权裁决的Issue及准确来源。原场景条件：有权人补证裁决。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询Issue/责任/决定，未决范围不能放行；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：依据留痕后再审阅；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-05-E：未决风险

- 依据：REQ-REV-05；AC-REV-05-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：未决Issue仍存在或输入版本变化。原场景条件：未决风险。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询Issue/责任/决定，未决范围不能放行；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留责任/阻断，不自动消失；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-05-A：普通译审越过升级裁决

- 依据：REQ-REV-05；AC-REV-05-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：普通译审越过升级裁决。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询Issue/责任/决定，未决范围不能放行；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝解除阻断；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-06-N：有权人保存决定且已形成结果

- 依据：REQ-REV-06；AC-REV-06-N；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：已有真实候选、决定及后续版本引用。原场景条件：有权人保存决定且已形成结果。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询成功决定仅一次、失败review.blocked、完整来源；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：从当前稿回查候选、输入、主体和后续版本；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-06-E：保存失败/重送

- 依据：REQ-REV-06；AC-REV-06-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：模拟保存失败，再重送原操作。原场景条件：保存失败/重送。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询成功决定仅一次、失败review.blocked、完整来源；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：失败不计接受且成功只记一次；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-REV-06-A：无历史访问权

- 依据：REQ-REV-06；AC-REV-06-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无历史访问权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询成功决定仅一次、失败review.blocked、完整来源；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝读取审阅正文与证据；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-REV-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-REV-01-N | REQ-REV-01 | normal | NOT_RUN |
| TC-SRC-REV-01-E | REQ-REV-01 | exception | NOT_RUN |
| TC-SRC-REV-01-A | REQ-REV-01 | permission | NOT_RUN |
| TC-SRC-REV-02-N | REQ-REV-02 | normal | NOT_RUN |
| TC-SRC-REV-02-E | REQ-REV-02 | exception | NOT_RUN |
| TC-SRC-REV-02-A | REQ-REV-02 | permission | NOT_RUN |
| TC-SRC-REV-03-N | REQ-REV-03 | normal | NOT_RUN |
| TC-SRC-REV-03-E | REQ-REV-03 | exception | NOT_RUN |
| TC-SRC-REV-03-A | REQ-REV-03 | permission | NOT_RUN |
| TC-SRC-REV-04-N | REQ-REV-04 | normal | NOT_RUN |
| TC-SRC-REV-04-E | REQ-REV-04 | exception | NOT_RUN |
| TC-SRC-REV-04-A | REQ-REV-04 | permission | NOT_RUN |
| TC-SRC-REV-05-N | REQ-REV-05 | normal | NOT_RUN |
| TC-SRC-REV-05-E | REQ-REV-05 | exception | NOT_RUN |
| TC-SRC-REV-05-A | REQ-REV-05 | permission | NOT_RUN |
| TC-SRC-REV-06-N | REQ-REV-06 | normal | NOT_RUN |
| TC-SRC-REV-06-E | REQ-REV-06 | exception | NOT_RUN |
| TC-SRC-REV-06-A | REQ-REV-06 | permission | NOT_RUN |

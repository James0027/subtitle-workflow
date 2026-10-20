# 源语闭环正式TC：ASR

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-ASR-01-N：已确认任务选择align_existing且声音/字幕齐备

- 依据：REQ-ASR-01；AC-ASR-01-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：align_existing，已知稿和声音覆盖所选范围。原场景条件：已确认任务选择align_existing且声音/字幕齐备。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Run.route依据、输入/范围、实际工具调用次数；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：按确切范围进入对齐路线；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-01-E：已选verify_existing但字幕未提供

- 依据：REQ-ASR-01；AC-ASR-01-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：verify_existing缺字幕，禁止切到transcribe。原场景条件：已选verify_existing但字幕未提供。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Run.route依据、输入/范围、实际工具调用次数；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：列缺项并阻断，不自动改为transcribe；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-01-A：有任务读取权无工具调用权者启动

- 依据：REQ-ASR-01；AC-ASR-01-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：有任务读取权无工具调用权者启动。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 主体可读取当前输入但无工具调用权；以有效Task和当前Ref申请所选route运行，查询Run与实际工具调用次数；请求输入须同时满足本条条件和数据变体；③ 查询Run.route依据、输入/范围、实际工具调用次数；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能发起实际收费调用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-02-N：transcribe/verify_existing/align_existing分别执行

- 依据：REQ-ASR-02；AC-ASR-02-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：分别建立三份明确route的任务，Mock返回相应文字/时间。原场景条件：transcribe/verify_existing/align_existing分别执行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：返回新稿候选/文字差异/时间候选并保留输入；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-02-E：对齐发现文字与声音不符

- 依据：REQ-ASR-02；AC-ASR-02-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：对齐返回内容不匹配区间；原字幕文字固定。原场景条件：对齐发现文字与声音不符。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留无法匹配区间并请求核对，不静默改文字；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-02-A：Agent请求覆盖已有人工确认字幕

- 依据：REQ-ASR-02；AC-ASR-02-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：service_actor。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：Agent请求覆盖已有人工确认字幕。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以service_actor对已有人工确认片段提交正文覆盖；当前Ref/修订有效，检查拒绝与原确认内容保留；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝写入，只允许有权范围内另存候选；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-03-N：跨块句子完成可验证拼接且有offset

- 依据：REQ-ASR-03；AC-ASR-03-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：块母版offset=1000ms；本地边界[0,2000)应映至[1000,3000)。原场景条件：跨块句子完成可验证拼接且有offset。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询source_spans/父段/时间/重叠标签和拒绝写入；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：母版时间与来源可回查，重叠标签保留；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-03-E：越任务范围、负时长或身份未知

- 依据：REQ-ASR-03；AC-ASR-03-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：返回负时长/越界；speaker身份留未知。原场景条件：越任务范围、负时长或身份未知。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询source_spans/父段/时间/重叠标签和拒绝写入；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：阻断非法结果或保留未知，不强配角色；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-03-A：无片段修改权者请求合并/拖轴

- 依据：REQ-ASR-03；AC-ASR-03-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无片段修改权者请求合并/拖轴。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 无片段修改权的真人分别提交合并片段和拖动时间轴请求；当前片段/修订有效，检查正文、分段和时间均未改变；请求输入须同时满足本条条件和数据变体；③ 查询source_spans/父段/时间/重叠标签和拒绝写入；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不因工程建议改变当前修订；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-04-N：有效许可及准入齐备

- 依据：REQ-ASR-04；AC-ASR-04-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：合成有效准入返回，仅测试路由分支。原场景条件：有效许可及准入齐备。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询AI_PROPOSED/人工决定分开；下一模块受理或等待；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：指定候选可交下游，仍为AI_PROPOSED；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-04-E：无有效校准但原始分很高

- 依据：REQ-ASR-04；AC-ASR-04-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：raw_score有值但校准版本/准入不存在。原场景条件：无有效校准但原始分很高。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询AI_PROPOSED/人工决定分开；下一模块受理或等待；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：转人工/等待，不假称高正确率自动放行；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-04-A：有执行权无最终内容确认权者确认源稿

- 依据：REQ-ASR-04；AC-ASR-04-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：有执行权无最终内容确认权者确认源稿。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交原场景指定的accept/edit_accept/改时间或锁定正文写入请求；使用当前Ref/修订保证拒绝来自动作权限而非缺料；请求输入须同时满足本条条件和数据变体；③ 查询AI_PROPOSED/人工决定分开；下一模块受理或等待；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，由有权人员实际决定；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-05-N：部分失败后获准按范围恢复

- 依据：REQ-ASR-05；AC-ASR-05-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：一段成功、一段失败；有权人解决原因后申请指定范围。原场景条件：部分失败后获准按范围恢复。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询FAILED/STOPPED、已有候选、attempt和累计费用；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留原候选/失败及新尝试引用；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-05-E：服务返回空结果

- 依据：REQ-ASR-05；AC-ASR-05-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：Mock返回空数组；另测撤权/STOPPED后的重试。原场景条件：服务返回空结果。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询FAILED/STOPPED、已有候选、attempt和累计费用；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：FAILED，后续未执行，不记成功源稿；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-05-A：授权已撤销或达到停止条件后申请重试

- 依据：REQ-ASR-05；AC-ASR-05-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：授权已撤销或达到停止条件后申请重试。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询FAILED/STOPPED、已有候选、attempt和累计费用；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝新调用，保留原因和既有费用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-06-N：同配置重复请求且查询完成

- 依据：REQ-ASR-06；AC-ASR-06-N；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：同输入/manifest连续重送同业务请求。原场景条件：同配置重复请求且查询完成。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、STALE_INPUT、attempt/step血缘；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：一个有效结果组，各attempt/step可追溯；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-06-E：人工已改稿仍提交旧input_revision

- 依据：REQ-ASR-06；AC-ASR-06-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：人工编辑至r+1后提交基于r的结果。原场景条件：人工已改稿仍提交旧input_revision。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、STALE_INPUT、attempt/step血缘；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：STALE_INPUT并保留候选，不自动覆盖；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-ASR-06-A：知道其他项目run_id/候选ID者查询

- 依据：REQ-ASR-06；AC-ASR-06-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：知道其他项目run_id/候选ID者查询。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询一组有效结果、STALE_INPUT、attempt/step血缘；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不返回内容或文件地址；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-ASR-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-ASR-01-N | REQ-ASR-01 | normal | NOT_RUN |
| TC-SRC-ASR-01-E | REQ-ASR-01 | exception | NOT_RUN |
| TC-SRC-ASR-01-A | REQ-ASR-01 | permission | NOT_RUN |
| TC-SRC-ASR-02-N | REQ-ASR-02 | normal | NOT_RUN |
| TC-SRC-ASR-02-E | REQ-ASR-02 | exception | NOT_RUN |
| TC-SRC-ASR-02-A | REQ-ASR-02 | permission | NOT_RUN |
| TC-SRC-ASR-03-N | REQ-ASR-03 | normal | NOT_RUN |
| TC-SRC-ASR-03-E | REQ-ASR-03 | exception | NOT_RUN |
| TC-SRC-ASR-03-A | REQ-ASR-03 | permission | NOT_RUN |
| TC-SRC-ASR-04-N | REQ-ASR-04 | normal | NOT_RUN |
| TC-SRC-ASR-04-E | REQ-ASR-04 | exception | NOT_RUN |
| TC-SRC-ASR-04-A | REQ-ASR-04 | permission | NOT_RUN |
| TC-SRC-ASR-05-N | REQ-ASR-05 | normal | NOT_RUN |
| TC-SRC-ASR-05-E | REQ-ASR-05 | exception | NOT_RUN |
| TC-SRC-ASR-05-A | REQ-ASR-05 | permission | NOT_RUN |
| TC-SRC-ASR-06-N | REQ-ASR-06 | normal | NOT_RUN |
| TC-SRC-ASR-06-E | REQ-ASR-06 | exception | NOT_RUN |
| TC-SRC-ASR-06-A | REQ-ASR-06 | permission | NOT_RUN |

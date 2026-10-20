# 源语闭环正式TC：MAIN-E

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-MAIN-R01-E：音轨属于另一剪辑

- 依据：REQ-MAIN-R01；AC-MAIN-R01-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：声音改为另剪辑a2；保留原视频v1。原场景条件：音轨属于另一剪辑。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前素材/核对Ref及expected_revision提交confirm_master；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：母版待核对，不进入依赖处理；保留检查；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R02-E：未确认任务直接请求ASR

- 依据：REQ-MAIN-R02；AC-MAIN-R02-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：Task未确认；独立变体无声音但有预授权。原场景条件：未确认任务直接请求ASR。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按当前Task/输入/规则请求阶段检查或上下文组装，查询readiness和缺项；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，列任务缺项，不出现已生成候选；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R03-E：仅选翻译但缺源稿

- 依据：REQ-MAIN-R03；AC-MAIN-R03-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：未确认/缺声音或不完整多语任务。原场景条件：仅选翻译但缺源稿。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：列输入缺项，不自动猜稿或跑未授权ASR；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R04-E：授权后撤销或任务修订变化

- 依据：REQ-MAIN-R04；AC-MAIN-R04-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：授权撤销与领取Run并发；模拟晚到返回。原场景条件：授权后撤销或任务修订变化。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以授予主体提交scope/原因；撤销变体在领取/调用前提交撤销并等待返回；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：后续动作重验，不沿用旧许可；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R05-E：已授权但缺必要上下文/质量依据

- 依据：REQ-MAIN-R05；AC-MAIN-R05-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：没有准入版本/有硬阻断，但请求继续。原场景条件：已授权但缺必要上下文/质量依据。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：等待补充，不自动通过；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R06-E：服务返回空结果

- 依据：REQ-MAIN-R06；AC-MAIN-R06-E；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：对齐返回内容不匹配区间；原字幕文字固定。原场景条件：服务返回空结果。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：FAILED，后续未执行，不记成功源稿；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R11-E：驳回候选

- 依据：REQ-MAIN-R11；AC-MAIN-R11-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：独立提交edit/reject，不能当accept。原场景条件：驳回候选。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留原稿/原因，问题未解决，不自动重跑或完成；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R11-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R12-E：批中一条版本改变/必审未完

- 依据：REQ-MAIN-R12；AC-MAIN-R12-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：预览后第二条版本增加或必审未完。原场景条件：批中一条版本改变/必审未完。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：该条失败/跳过，其他项逐条报告；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R12-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R13-E：人工提交expected_revision已过期

- 依据：REQ-MAIN-R13；AC-MAIN-R13-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两个提交同expected_revision；预置稿通过获准锁定流程建立。原场景条件：人工提交expected_revision已过期。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按所选action/候选或片段Ref/expected_revision提交单项或批量决定；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝旧版写入并保留待提交内容；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R13-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R14-E：同请求重复提交

- 依据：REQ-MAIN-R14；AC-MAIN-R14-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：删除可控夹具中的一条引用关系模拟缺口。原场景条件：同请求重复提交。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：复用有效结果，重试/失败仍保留，不增业务分母；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R14-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R15-E：超预算或达到重试停止条件

- 依据：REQ-MAIN-R15；AC-MAIN-R15-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：B+epsilon、连续重试停止、并发运行或晚到账单。原场景条件：超预算或达到重试停止条件。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：STOPPED，下一次调用拒绝；未配置预算不启付费；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R15-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R16-E：上游修订后用旧PASS签新包

- 依据：REQ-MAIN-R16；AC-MAIN-R16-E；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：受影响依赖缺失；新版试图复用旧PASS。原场景条件：上游修订后用旧PASS签新包。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 选择历史修订并提交rollback，随后查询新修订和受影响依赖；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，明确待复检范围；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R16-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R17-E：字幕越范围、未审或解析不一致

- 依据：REQ-MAIN-R17；AC-MAIN-R17-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：Mock生成器删去“没”或改时间；另测未审稿。原场景条件：字幕越范围、未审或解析不一致。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：失败定位，不称合格导出；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R17-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R18-E：当前包有未决项/内容变更/无回执

- 依据：REQ-MAIN-R18；AC-MAIN-R18-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：改稿后继续用旧Validation/hash请求签发。原场景条件：当前包有未决项/内容变更/无回执。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 在首批测试环境完成真人内容审核、内部文件校验后，由有权真人提交当前包/hash的signoff；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：分别阻断签发或保持外部未知；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R18-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R19-E：零分母/未满168小时/缺平台回执

- 依据：REQ-MAIN-R19；AC-MAIN-R19-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：重复/迟到事件，零分母或观察未满窗。原场景条件：零分母/未满168小时/缺平台回执。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：不适用或待定，不补0%/成功；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R19-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-MAIN-R01-E | REQ-MAIN-R01 | exception | NOT_RUN |
| TC-SRC-MAIN-R02-E | REQ-MAIN-R02 | exception | NOT_RUN |
| TC-SRC-MAIN-R03-E | REQ-MAIN-R03 | exception | NOT_RUN |
| TC-SRC-MAIN-R04-E | REQ-MAIN-R04 | exception | NOT_RUN |
| TC-SRC-MAIN-R05-E | REQ-MAIN-R05 | exception | NOT_RUN |
| TC-SRC-MAIN-R06-E | REQ-MAIN-R06 | exception | NOT_RUN |
| TC-SRC-MAIN-R11-E | REQ-MAIN-R11 | exception | NOT_RUN |
| TC-SRC-MAIN-R12-E | REQ-MAIN-R12 | exception | NOT_RUN |
| TC-SRC-MAIN-R13-E | REQ-MAIN-R13 | exception | NOT_RUN |
| TC-SRC-MAIN-R14-E | REQ-MAIN-R14 | exception | NOT_RUN |
| TC-SRC-MAIN-R15-E | REQ-MAIN-R15 | exception | NOT_RUN |
| TC-SRC-MAIN-R16-E | REQ-MAIN-R16 | exception | NOT_RUN |
| TC-SRC-MAIN-R17-E | REQ-MAIN-R17 | exception | NOT_RUN |
| TC-SRC-MAIN-R18-E | REQ-MAIN-R18 | exception | NOT_RUN |
| TC-SRC-MAIN-R19-E | REQ-MAIN-R19 | exception | NOT_RUN |

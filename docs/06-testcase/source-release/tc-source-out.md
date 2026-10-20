# 源语闭环正式TC：OUT

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-OUT-01-N：人工确认源稿按source_only任务规格准备

- 依据：REQ-OUT-01；AC-OUT-01-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：source_only、source分支、已确认2个片段、输出要求齐。原场景条件：人工确认源稿按source_only任务规格准备。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询交付范围/适用性；未生成合格包；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：只检查约定源语范围，内部生成校验后仍须真人签发才正式导出；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-01-E：多语缺确切profile或分支错配

- 依据：REQ-OUT-01；AC-OUT-01-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：分支不属本Task；保留多语缺profile的约束变体。原场景条件：多语缺确切profile或分支错配。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询交付范围/适用性；未生成合格包；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：列缺项并阻断受影响合格输出，不借源语模式降范围；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-01-A：无输入读取权者指定已知片段Ref

- 依据：REQ-OUT-01；AC-OUT-01-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无输入读取权者指定已知片段Ref。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询交付范围/适用性；未生成合格包；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不生成可查看他项目内容的报告；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-02-N：当前稿全部适用检查实际通过

- 依据：REQ-OUT-02；AC-OUT-02-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两个合法cue，当前规范来源/版本固定。原场景条件：当前稿全部适用检查实际通过。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询Validation逐项规则/locator、FAIL/NOT_EXECUTED；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：逐项Validation包含规则/版本/范围；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-02-E：字幕越范围或检查器未执行

- 依据：REQ-OUT-02；AC-OUT-02-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：cue越6000ms；独立变体检查器未执行。原场景条件：字幕越范围或检查器未执行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询Validation逐项规则/locator、FAIL/NOT_EXECUTED；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：失败定位/NOT_EXECUTED，不称全部PASS；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-02-A：无检查执行权者发起质检

- 依据：REQ-OUT-02；AC-OUT-02-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无检查执行权者发起质检。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询Validation逐项规则/locator、FAIL/NOT_EXECUTED；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能通过前端直接调用工具；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-03-N：确认稿内部生成文件且解析一致

- 依据：REQ-OUT-03；AC-OUT-03-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：使用人工参考两cue，与当前确认稿一致。原场景条件：确认稿内部生成文件且解析一致。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；分别测试未签、已签、签后改字/重生成不同hash、撤回签发、规则失效；只允许当前有效签发的正式文件访问；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：VALIDATED及hash/映射可追溯；未签下载拒绝，真人签发后正式导出；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-03-E：未审稿或文件解析不一致

- 依据：REQ-OUT-03；AC-OUT-03-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：Mock生成器删去“没”或改时间；另测未审稿。原场景条件：未审稿或文件解析不一致。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；分别测试未签、已签、签后改字/重生成不同hash、撤回签发、规则失效；只允许当前有效签发的正式文件访问；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：阻断合格导出并保留差异，不以文件存在判成功；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-03-A：无产物访问权者凭artifact_id下载

- 依据：REQ-OUT-03；AC-OUT-03-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无产物访问权者凭artifact_id下载。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 先由有审核/签发/下载权的human_allowed生成、校验并签发当前测试文件；再由本条无权主体直接GET已知artifact_id的file接口，不重新执行导出；请求输入须同时满足本条条件和数据变体；分别测试未签、已签、签后改字/重生成不同hash、撤回签发、规则失效；只允许当前有效签发的正式文件访问；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不返回可访问文件地址；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-04-N：同一人有审稿/签发权且实际内容决定与当前包检查完成

- 依据：REQ-OUT-04；AC-OUT-04-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：首批必需签发；真人fixture有内容审核、当前包签发及下载权限。原场景条件：同一人有审稿/签发权且实际内容决定与当前包检查完成。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 在首批测试环境完成真人内容审核、内部文件校验后，由有权真人提交当前包/hash的signoff；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：同页依次签发并PUBLISH_READY；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-04-E：当前包有未决项或内容已变

- 依据：REQ-OUT-04；AC-OUT-04-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：改稿后继续用旧Validation/hash请求签发。原场景条件：当前包有未决项或内容已变。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 在首批测试环境完成真人内容审核、内部文件校验后，由有权真人提交当前包/hash的signoff；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：阻断签发，旧签名不能签新包；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-04-A：仅审稿无签发权者放行或Agent代签

- 依据：REQ-OUT-04；AC-OUT-04-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：reviewer_only与service_actor分别参数化执行。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：仅审稿无签发权者放行或Agent代签。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 先建立当前合格测试包，再分别由仅审稿主体和服务主体提交signoff；不得发起真实外部发布；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不写release.signed；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-05-N：已签发包实际外部交付且有明确成功回执

- 依据：REQ-OUT-05；AC-OUT-05-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：OPTIONAL_SHARED。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；仅外部回执成功记录为可选后续分支，未纳入首批时保留DEFERRED，不计首批成功闸门。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：可选后续模拟回执，准确包/序号/明确结论。原场景条件：已签发包实际外部交付且有明确成功回执。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 只向测试接收适配器登记合成回执/自动发布请求，不访问任何真实平台；请求输入须同时满足本条条件和数据变体；③ 查询不产生真实发布调用；外部状态/来源/序号和结论；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：记录准确包/序号后才PUBLISHED；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-05-E：无回执、仅技术通过或外部退回

- 依据：REQ-OUT-05；AC-OUT-05-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：OPTIONAL_SHARED。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；仅外部回执成功记录为可选后续分支，未纳入首批时保留DEFERRED，不计首批成功闸门。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：无回执、仅技术通过、退回三种受控返回。原场景条件：无回执、仅技术通过或外部退回。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 只向测试接收适配器登记合成回执/自动发布请求，不访问任何真实平台；请求输入须同时满足本条条件和数据变体；③ 查询不产生真实发布调用；外部状态/来源/序号和结论；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保持未知/待处理并分列结论，不猜发布成功；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-05-A：Agent请求自动外部发布或无权者登记伪回执

- 依据：REQ-OUT-05；AC-OUT-05-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：OPTIONAL_SHARED。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；仅外部回执成功记录为可选后续分支，未纳入首批时保留DEFERRED，不计首批成功闸门。主体：service_actor与human_denied分别参数化执行。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：Agent请求自动外部发布或无权者登记伪回执。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 分别以服务主体请求自动发布、以无回执登记权真人提交伪回执；仅调用测试接收适配器，检查两项均拒绝且无真实平台调用；请求输入须同时满足本条条件和数据变体；③ 查询不产生真实发布调用；外部状态/来源/序号和结论；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不发生外部发布或成功写入；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-06-N：退回后修订、重检及重签新包

- 依据：REQ-OUT-06；AC-OUT-06-N；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：同交付单元，新包/new checksum，保留旧包。原场景条件：退回后修订、重检及重签新包。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询旧包/新包、提交序号和拒绝旧版记录；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：历史保留，同交付单元用后续提交序号；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-06-E：并发改稿后旧校验/签发请求到达

- 依据：REQ-OUT-06；AC-OUT-06-E；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：并发改稿后旧校验或签发请求到达。原场景条件：并发改稿后旧校验/签发请求到达。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询旧包/新包、提交序号和拒绝旧版记录；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝旧版推进，新稿待重检；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-OUT-06-A：无修订/签发撤销权限者借重检替换当前包

- 依据：REQ-OUT-06；AC-OUT-06-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无修订/签发撤销权限者借重检替换当前包。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交当前人工审核稿的内部检查/生成请求；受控读取实际字节重解析，未签直接GET正式文件须拒绝；由有权真人签发当前包后才正式下载，并查Validation/Artifact/签发与导出事件；请求输入须同时满足本条条件和数据变体；③ 查询旧包/新包、提交序号和拒绝旧版记录；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不改历史或自动撤回外部文件；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-OUT-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-OUT-01-N | REQ-OUT-01 | normal | NOT_RUN |
| TC-SRC-OUT-01-E | REQ-OUT-01 | exception | NOT_RUN |
| TC-SRC-OUT-01-A | REQ-OUT-01 | permission | NOT_RUN |
| TC-SRC-OUT-02-N | REQ-OUT-02 | normal | NOT_RUN |
| TC-SRC-OUT-02-E | REQ-OUT-02 | exception | NOT_RUN |
| TC-SRC-OUT-02-A | REQ-OUT-02 | permission | NOT_RUN |
| TC-SRC-OUT-03-N | REQ-OUT-03 | normal | NOT_RUN |
| TC-SRC-OUT-03-E | REQ-OUT-03 | exception | NOT_RUN |
| TC-SRC-OUT-03-A | REQ-OUT-03 | permission | NOT_RUN |
| TC-SRC-OUT-04-N | REQ-OUT-04 | normal | NOT_RUN |
| TC-SRC-OUT-04-E | REQ-OUT-04 | exception | NOT_RUN |
| TC-SRC-OUT-04-A | REQ-OUT-04 | permission | NOT_RUN |
| TC-SRC-OUT-05-N | REQ-OUT-05 | normal | NOT_RUN |
| TC-SRC-OUT-05-E | REQ-OUT-05 | exception | NOT_RUN |
| TC-SRC-OUT-05-A | REQ-OUT-05 | permission | NOT_RUN |
| TC-SRC-OUT-06-N | REQ-OUT-06 | normal | NOT_RUN |
| TC-SRC-OUT-06-E | REQ-OUT-06 | exception | NOT_RUN |
| TC-SRC-OUT-06-A | REQ-OUT-06 | permission | NOT_RUN |

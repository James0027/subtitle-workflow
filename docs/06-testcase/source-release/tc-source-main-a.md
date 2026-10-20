# 源语闭环正式TC：MAIN-A

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-MAIN-R01-A：Agent请求confirm_master

- 依据：REQ-MAIN-R01；AC-MAIN-R01-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：service_actor。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：Agent请求confirm_master。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以service_actor提交confirm_master，body中另伪造真人actor_role作防伪对照；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不伪造人工确认；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R02-A：无任务修改权限者改范围

- 依据：REQ-MAIN-R02；AC-MAIN-R02-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无任务修改权限者改范围。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前expected_revision提交修改Task.range的请求，其他必填条件保持有效；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝；旧快照不被写入；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R03-A：无该输入项目读取权

- 依据：REQ-MAIN-R03；AC-MAIN-R03-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无该输入项目读取权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询只运行所选模块、无假父任务、不冒称全链完成；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能借单模块入口跨项目；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R04-A：无授予权限者提交授权

- 依据：REQ-MAIN-R04；AC-MAIN-R04-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无授予权限者提交授权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 向当前任务提交明确principal/modules/actions的授予请求；撤销分支独立重复；请求输入须同时满足本条条件和数据变体；③ 查询授权/检查事件、新调用0、晚到输出受控留存；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不创建有效授权；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R05-A：许可只含转写却请求翻译

- 依据：REQ-MAIN-R05；AC-MAIN-R05-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：许可只含转写却请求翻译。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用指定route、输入Ref、范围和许可申请运行；轮询真实Run，再按变体重送/重试/续步；请求输入须同时满足本条条件和数据变体；③ 查询候选状态、假review事件0；锁定/代签拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝越范围动作并记录；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R06-A：无工具调用权限者启动运行

- 依据：REQ-MAIN-R06；AC-MAIN-R06-A；[任务T2.1](../../07-delivery-plans/sub-delivery-plan-source-release-T2.1-asr-routes.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无工具调用权限者启动运行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 主体可读取当前输入但无工具调用权；以有效Task和当前Ref申请所选route运行，查询Run与实际工具调用次数；请求输入须同时满足本条条件和数据变体；③ 查询Candidate种类/原文不变；三路线独立结果；在页面03/04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能产生实际收费调用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R11-A：Agent冒充reviewer接受/签发

- 依据：REQ-MAIN-R11；AC-MAIN-R11-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：service_actor。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：Agent冒充reviewer接受/签发。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交原场景指定的accept/edit_accept/改时间或锁定正文写入请求；使用当前Ref/修订保证拒绝来自动作权限而非缺料；请求输入须同时满足本条条件和数据变体；③ 查询编辑提交/待审/审核状态、review.submitted、Candidate与ReviewDecision动作；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝；自动执行不记人工接受；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R11-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R12-A：一条不在审阅人权限范围

- 依据：REQ-MAIN-R12；AC-MAIN-R12-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_partial。
- 数据：两个当前候选s1/s2；该主体仅可处理s1。另以预览后撤销s2授权作第二个参数化变体。原场景条件：一条不在审阅人权限范围。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交同一batch内s1与s2；逐条查询决定和返回，不整体绕过s2权限；请求输入须同时满足本条条件和数据变体；③ 查询每项结果/决定，成功1条不能报整批成功；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：该条拒绝，不借整批覆盖；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R12-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R13-A：后续模块写MANUAL_LOCKED正文

- 依据：REQ-MAIN-R13；AC-MAIN-R13-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：后续模块写MANUAL_LOCKED正文。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交原场景指定的accept/edit_accept/改时间或锁定正文写入请求；使用当前Ref/修订保证拒绝来自动作权限而非缺料；请求输入须同时满足本条条件和数据变体；③ 查询分支头、当前/历史正文、拒绝与未写入证据；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝且留实际未写入证据；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R13-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R14-A：无权限者读取其他项目trace

- 依据：REQ-MAIN-R14；AC-MAIN-R14-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无权限者读取其他项目trace。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询明确缺口，不补假主体；项目B读取拒绝；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不因日志入口泄露资料；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R14-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R15-A：无恢复权限者改run/请求重试

- 依据：REQ-MAIN-R15；AC-MAIN-R15-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪；批准B/币种/计次/恢复策略后才执行参数化边界。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无恢复权限者改run/请求重试。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询Task累计/在途估算、STOPPED及新调用0；不清历史；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不清零历史/Task费用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R15-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R16-A：无回滚权限者恢复内容

- 依据：REQ-MAIN-R16；AC-MAIN-R16-A；[任务T2.2](../../07-delivery-plans/sub-delivery-plan-source-release-T2.2-review-versions.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无回滚权限者恢复内容。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 指定当前r和历史h，提交rollback及reason，不得仅删除历史或直接改指针；请求输入须同时满足本条条件和数据变体；③ 查询新决定/修订、原历史不变、待复检和签名失效；在页面04核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，历史/当前稿均不被偷偷改写；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R16-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R17-A：无产物访问权限者请求文件

- 依据：REQ-MAIN-R17；AC-MAIN-R17-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无产物访问权限者请求文件。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 先由有审核/签发/下载权的human_allowed生成、校验并签发当前测试文件；再由本条无权主体直接GET已知artifact_id的file接口，不重新执行导出；请求输入须同时满足本条条件和数据变体；③ 查询真实生成bytes/hash、解析差异、Artifact状态与访问；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不因知道artifact_id获得下载权；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R17-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R18-A：仅审稿无签发权者请求放行

- 依据：REQ-MAIN-R18；AC-MAIN-R18-A；[任务T3.1](../../07-delivery-plans/sub-delivery-plan-source-release-T3.1-export-validation.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：reviewer_only与service_actor分别参数化执行。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：仅审稿无签发权者请求放行。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 先建立当前合格测试包，再分别由仅审稿主体和服务主体提交signoff；不得发起真实外部发布；请求输入须同时满足本条条件和数据变体；③ 查询独立内容决定/signoff引用、PUBLISH_READY或拒绝；在页面08核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝签发；Agent无自动外部发布权；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R18-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-MAIN-R19-A：无范围数据权限者请求报告

- 依据：REQ-MAIN-R19；AC-MAIN-R19-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无范围数据权限者请求报告。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询去重/重算、未知/待观察；不补0%成功；在页面02/03及追踪核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝或返回授权聚合，不能暴露受限素材明细；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-MAIN-R19-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-MAIN-R01-A | REQ-MAIN-R01 | permission | NOT_RUN |
| TC-SRC-MAIN-R02-A | REQ-MAIN-R02 | permission | NOT_RUN |
| TC-SRC-MAIN-R03-A | REQ-MAIN-R03 | permission | NOT_RUN |
| TC-SRC-MAIN-R04-A | REQ-MAIN-R04 | permission | NOT_RUN |
| TC-SRC-MAIN-R05-A | REQ-MAIN-R05 | permission | NOT_RUN |
| TC-SRC-MAIN-R06-A | REQ-MAIN-R06 | permission | NOT_RUN |
| TC-SRC-MAIN-R11-A | REQ-MAIN-R11 | permission | NOT_RUN |
| TC-SRC-MAIN-R12-A | REQ-MAIN-R12 | permission | NOT_RUN |
| TC-SRC-MAIN-R13-A | REQ-MAIN-R13 | permission | NOT_RUN |
| TC-SRC-MAIN-R14-A | REQ-MAIN-R14 | permission | NOT_RUN |
| TC-SRC-MAIN-R15-A | REQ-MAIN-R15 | permission | NOT_RUN |
| TC-SRC-MAIN-R16-A | REQ-MAIN-R16 | permission | NOT_RUN |
| TC-SRC-MAIN-R17-A | REQ-MAIN-R17 | permission | NOT_RUN |
| TC-SRC-MAIN-R18-A | REQ-MAIN-R18 | permission | NOT_RUN |
| TC-SRC-MAIN-R19-A | REQ-MAIN-R19 | permission | NOT_RUN |

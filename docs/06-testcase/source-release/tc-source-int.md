# 源语闭环正式TC：INT

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-INT-01-N：获准文件实际接收且来源/校验值齐备

- 依据：REQ-INT-01；AC-INT-01-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：原件SHA已知；派生音轨另记父Asset。原场景条件：获准文件实际接收且来源/校验值齐备。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交Asset接收/引用请求，记录接收请求标识；按本条变体重送或补料；请求输入须同时满足本条条件和数据变体；③ 查询Asset数量/来源/原件hash；外部工具调用次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：登记原件及Asset，派生文件另留父引用；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-01-E：同一接收请求重送或文件未传完

- 依据：REQ-INT-01；AC-INT-01-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：接收中断、缺rights_ref及相同请求重送分别准备。原场景条件：同一接收请求重送或文件未传完。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交Asset接收/引用请求，记录接收请求标识；按本条变体重送或补料；请求输入须同时满足本条条件和数据变体；③ 查询Asset数量/来源/原件hash；外部工具调用次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：返回原接收结果或实际失败，不多造成功素材；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-01-A：无项目写入/素材用途权者登记或外传

- 依据：REQ-INT-01；AC-INT-01-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无项目写入/素材用途权者登记或外传。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交Asset接收/引用请求，记录接收请求标识；按本条变体重送或补料；请求输入须同时满足本条条件和数据变体；③ 查询Asset数量/来源/原件hash；外部工具调用次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不产生可用素材或外部调用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-02-N：视频与声音对应且检查可查，有权人确认

- 依据：REQ-INT-02；AC-INT-02-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：视频v1和同剪辑声音a1，核对引用齐备。原场景条件：视频与声音对应且检查可查，有权人确认。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前素材/核对Ref及expected_revision提交confirm_master；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：CONFIRMED并保留决定，绑定同一稳定Task ID；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-02-E：独立音轨来自另一剪辑

- 依据：REQ-INT-02；AC-INT-02-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：声音改为另剪辑a2；保留原视频v1。原场景条件：独立音轨来自另一剪辑。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前素材/核对Ref及expected_revision提交confirm_master；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：NEEDS_REVIEW，保留错配依据，不能确认母版；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-02-A：工程服务/Agent请求代签confirm_master

- 依据：REQ-INT-02；AC-INT-02-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：service_actor。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：工程服务/Agent请求代签confirm_master。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以service_actor提交confirm_master，body中另伪造真人actor_role作防伪对照；请求输入须同时满足本条条件和数据变体；③ 查询Media状态/确认主体；confirm_master决定和事件；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能写人工主体或确认事件；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-03-N：转写任务缺可选脚本，已记责任与影响

- 依据：REQ-INT-03；AC-INT-03-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：脚本未交但非本阶段必需；登记owner。原场景条件：转写任务缺可选脚本，已记责任与影响。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询missing_items/readiness；未测量字段不能变0；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留缺项，其他条件齐备可检查ASR就绪；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-03-E：对白密度未测或必需材料被标waived

- 依据：REQ-INT-03；AC-INT-03-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：对白密度未测；另一变体把必需声音标waived。原场景条件：对白密度未测或必需材料被标waived。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询missing_items/readiness；未测量字段不能变0；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保持未知或阻断，不补0/假不适用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-03-A：无权者豁免缺项或改原内容评级

- 依据：REQ-INT-03；AC-INT-03-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无权者豁免缺项或改原内容评级。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询missing_items/readiness；未测量字段不能变0；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，原记录及待补状态保留；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-04-N：明选source_only及核对路线、范围、已有字幕和输出

- 依据：REQ-INT-04；AC-INT-04-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：source_only、verify_existing、source分支、whole。原场景条件：明选source_only及核对路线、范围、已有字幕和输出。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询任务定义/版本；错误项与未启动工具次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保存源语任务，目标显式不适用；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-04-E：多语缺市场/目标，或区间越母版

- 依据：REQ-INT-04；AC-INT-04-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：删除所选字幕；区间end改为6001ms；多语目标留pending。原场景条件：多语缺市场/目标，或区间越母版。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询任务定义/版本；错误项与未启动工具次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：列缺项/非法范围，不自动降为源语或扩大范围；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-04-A：无该项目素材读取权者引用输入

- 依据：REQ-INT-04；AC-INT-04-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无该项目素材读取权者引用输入。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询任务定义/版本；错误项与未启动工具次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不借任务引用跨项目素材；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-05-N：有权人先存草稿再确认准确快照

- 依据：REQ-INT-05；AC-INT-05-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：确认请求expected_revision等于当前r。原场景条件：有权人先存草稿再确认准确快照。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 查询当前Task修订后提交confirm_task；旧版变体先完成另一份有权修改；请求输入须同时满足本条条件和数据变体；③ 查询task_revision/确认字段；task.confirmed次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：分别保留草稿及confirm_task决定/事件；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-05-E：确认时task_revision已变化

- 依据：REQ-INT-05；AC-INT-05-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：先由另一主体修改到r+1，再提交旧r。原场景条件：确认时task_revision已变化。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 查询当前Task修订后提交confirm_task；旧版变体先完成另一份有权修改；请求输入须同时满足本条条件和数据变体；③ 查询task_revision/确认字段；task.confirmed次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝旧提交并保留编辑，不复用旧确认；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-05-A：只有编辑权者请求确认任务

- 依据：REQ-INT-05；AC-INT-05-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：只有编辑权者请求确认任务。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 查询当前Task修订后提交confirm_task；旧版变体先完成另一份有权修改；请求输入须同时满足本条条件和数据变体；③ 查询task_revision/确认字段；task.confirmed次数；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不能写confirmed_by或task.confirmed；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-06-N：已确认母版/任务、当前输入及实际执行许可齐备

- 依据：REQ-INT-06；AC-INT-06-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：母版和Task已确认、6000ms有声、manual许可。原场景条件：已确认母版/任务、当前输入及实际执行许可齐备。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按当前Task/输入/规则请求阶段检查或上下文组装，查询readiness和缺项；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：记录当前stage为ready，申请执行时再检查；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-06-E：已预授权但无可用声音，或仅有未确认任务

- 依据：REQ-INT-06；AC-INT-06-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：Task未确认；独立变体无声音但有预授权。原场景条件：已预授权但无可用声音，或仅有未确认任务。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 按当前Task/输入/规则请求阶段检查或上下文组装，查询readiness和缺项；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：blocked/缺项，不创建ASR成功运行；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-06-A：任务条件齐备但主体未获执行权

- 依据：REQ-INT-06；AC-INT-06-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：任务条件齐备但主体未获执行权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 使用当前合格Task/输入引用申请本条启动/重算/重试，若测试恢复则预先通过有权流程建立STOPPED运行；请求输入须同时满足本条条件和数据变体；③ 查询readiness；Run/工具调用及实际权限检查；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：给请求授权入口，不因READY发起工具调用；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-07-N：负责人改处理范围并确认新版

- 依据：REQ-INT-07；AC-INT-07-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：改为[0,4000)并重新确认新Task版本。原场景条件：负责人改处理范围并确认新版。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询旧/新Task与Media引用、旧Run原快照、复检范围；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：新task_revision及就绪检查，旧Run仍引用原快照；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-07-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-07-E：换母版后请求用旧检查开启新任务修订

- 依据：REQ-INT-07；AC-INT-07-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：新母版v2已建，但提交沿用v1校验引用。原场景条件：换母版后请求用旧检查开启新任务修订。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 提交任务创建或修改请求，保留request_key及当前修订；重复/并发变体执行第二次请求；请求输入须同时满足本条条件和数据变体；③ 查询旧/新Task与Media引用、旧Run原快照、复检范围；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝并列复检范围，旧文件/历史保留；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-07-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-07-A：无任务/母版变更权者替换选用音轨

- 依据：REQ-INT-07；AC-INT-07-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无任务/母版变更权者替换选用音轨。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 无任务/母版变更权主体以当前修订申请替换选用音轨；另测借Task修改绕过母版确认，旧确认/输入引用不得改变；请求输入须同时满足本条条件和数据变体；③ 查询旧/新Task与Media引用、旧Run原快照、复检范围；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不覆盖原母版或继承旧确认；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-07-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-08-N：先建草稿再抽轨/确认，重复提交相同request_key

- 依据：REQ-INT-08；AC-INT-08-N；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：先创建Task草稿，素材准备ingest抽轨/母版确认后正式确认，同request_key重送；全程同task_id。原场景条件：先建草稿再抽轨/确认，重复提交相同request_key。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；创建真实草稿后以module=ingest提取视频音轨，确认前请求ASR拒绝；确认后task_id保持不变，所有transform.run_id可回查；另以无Task请求抽轨验证拒绝，不新建无任务Run；③ 查询一个业务Task、对象级事件及拒绝记录；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：任务ID始终不变且仅一个任务，派生音轨关联真实ingest Run；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-08-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-08-E：相同request_key提交不同内容或查询检查失败

- 依据：REQ-INT-08；AC-INT-08-E；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：同request_key改purpose；查询依赖失败。原场景条件：相同request_key提交不同内容或查询检查失败。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；创建真实草稿后以module=ingest提取视频音轨，确认前请求ASR拒绝；确认后task_id保持不变，所有transform.run_id可回查；另以无Task请求抽轨验证拒绝，不新建无任务Run；③ 查询一个业务Task、对象级事件及拒绝记录；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：冲突/真实失败，不吞新意图或补成功事件；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-08-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-INT-08-A：无对象读取权者用已知asset_id/media_id/trace查询

- 依据：REQ-INT-08；AC-INT-08-A；[任务T1.1](../../07-delivery-plans/sub-delivery-plan-source-release-T1.1-intake-storage.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无对象读取权者用已知asset_id/media_id/trace查询。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；创建真实草稿后以module=ingest提取视频音轨，确认前请求ASR拒绝；确认后task_id保持不变，所有transform.run_id可回查；另以无Task请求抽轨验证拒绝，不新建无任务Run；③ 查询一个业务Task、对象级事件及拒绝记录；在页面01/02核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝，不泄露文件地址或其他项目存在性；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-INT-08-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-INT-01-N | REQ-INT-01 | normal | NOT_RUN |
| TC-SRC-INT-01-E | REQ-INT-01 | exception | NOT_RUN |
| TC-SRC-INT-01-A | REQ-INT-01 | permission | NOT_RUN |
| TC-SRC-INT-02-N | REQ-INT-02 | normal | NOT_RUN |
| TC-SRC-INT-02-E | REQ-INT-02 | exception | NOT_RUN |
| TC-SRC-INT-02-A | REQ-INT-02 | permission | NOT_RUN |
| TC-SRC-INT-03-N | REQ-INT-03 | normal | NOT_RUN |
| TC-SRC-INT-03-E | REQ-INT-03 | exception | NOT_RUN |
| TC-SRC-INT-03-A | REQ-INT-03 | permission | NOT_RUN |
| TC-SRC-INT-04-N | REQ-INT-04 | normal | NOT_RUN |
| TC-SRC-INT-04-E | REQ-INT-04 | exception | NOT_RUN |
| TC-SRC-INT-04-A | REQ-INT-04 | permission | NOT_RUN |
| TC-SRC-INT-05-N | REQ-INT-05 | normal | NOT_RUN |
| TC-SRC-INT-05-E | REQ-INT-05 | exception | NOT_RUN |
| TC-SRC-INT-05-A | REQ-INT-05 | permission | NOT_RUN |
| TC-SRC-INT-06-N | REQ-INT-06 | normal | NOT_RUN |
| TC-SRC-INT-06-E | REQ-INT-06 | exception | NOT_RUN |
| TC-SRC-INT-06-A | REQ-INT-06 | permission | NOT_RUN |
| TC-SRC-INT-07-N | REQ-INT-07 | normal | NOT_RUN |
| TC-SRC-INT-07-E | REQ-INT-07 | exception | NOT_RUN |
| TC-SRC-INT-07-A | REQ-INT-07 | permission | NOT_RUN |
| TC-SRC-INT-08-N | REQ-INT-08 | normal | NOT_RUN |
| TC-SRC-INT-08-E | REQ-INT-08 | exception | NOT_RUN |
| TC-SRC-INT-08-A | REQ-INT-08 | permission | NOT_RUN |

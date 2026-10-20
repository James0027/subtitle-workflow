# 源语闭环正式TC：CTX

版本：v0.1｜日期：2026-10-20｜用例设计待评审，全部NOT_RUN。

> 上游（我引用）：[主索引](../tc-main-subtitle-workflow.md)、[原需求与场景](../../05-prd/acceptance-map.md)、[技术契约草案](../../03-foundation/source-release-contract.md)。
> 下游（引用我）：[主测试索引](../tc-main-subtitle-workflow.md)；对应实施子计划和未来真实执行报告。

共同前置与数据配方见[fixture-recipes.json](fixtures/fixture-recipes.json)；合成参考为[reference.srt](fixtures/reference.srt)，它不是实际声音金标。机器可读设计镜像见[cases.json](cases.json)；预期以PRD为准，当前没有测试执行器。每条执行前建立隔离数据，不直接写入预期状态。OPTIONAL_SHARED不列入当前源语导出的成功闸门，REAL_TOOL需真实样本/模型；二者当前都未执行。

### TC-SRC-CTX-01-N：同项目用途获准

- 依据：REQ-CTX-01；AC-CTX-01-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：项目A用途获准的角色/脚本引用。原场景条件：同项目用途获准。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询实际注入列表/拒绝，不返回他项目命中信息；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：取有来源资料；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-01-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-01-E：缓存或Ref无法验证

- 依据：REQ-CTX-01；AC-CTX-01-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：引用校验失败；缓存来自项目B。原场景条件：缓存或Ref无法验证。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询实际注入列表/拒绝，不返回他项目命中信息；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：不注入并报缺项；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-01-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-01-A：跨项目/撤权

- 依据：REQ-CTX-01；AC-CTX-01-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：outsider。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：跨项目/撤权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用本条无权主体调用resolve_context或申请未获准的规则/资料替换；检查读取/外传/活动规则权限，不能依赖浏览器隐藏；请求输入须同时满足本条条件和数据变体；③ 查询实际注入列表/拒绝，不返回他项目命中信息；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝且不泄露内容或命中存在性；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-01-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-02-N：指定片段与锁词

- 依据：REQ-CTX-02；AC-CTX-02-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：当前句/可得邻句和明确角色/锁词。原场景条件：指定片段与锁词。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询manifest片段真实条目、缺失原因和外部调用0次；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：组装必要窗口及版本；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-02-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-02-E：角色不明/邻句不足

- 依据：REQ-CTX-02；AC-CTX-02-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：源角色未知，邻句不足；不可外传素材。原场景条件：角色不明/邻句不足。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询manifest片段真实条目、缺失原因和外部调用0次；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：明确缺失，不生成身份；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-02-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-02-A：仅可看不可外传资料

- 依据：REQ-CTX-02；AC-CTX-02-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：仅可看不可外传资料。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用本条无权主体调用resolve_context或申请未获准的规则/资料替换；检查读取/外传/活动规则权限，不能依赖浏览器隐藏；请求输入须同时满足本条条件和数据变体；③ 查询manifest片段真实条目、缺失原因和外部调用0次；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝送外部模型；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-02-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-03-N：有效且适用规则/profile

- 依据：REQ-CTX-03；AC-CTX-03-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：源语输出规范有固定有效版本。原场景条件：有效且适用规则/profile。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询活动集快照/范围/拒绝；DRAFT不变ACTIVE；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：固定准确活动集；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-03-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-03-E：无版本/过期/未知市场

- 依据：REQ-CTX-03；AC-CTX-03-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：缺版本/过期/未知必要scope，普通主体尝试激活包。原场景条件：无版本/过期/未知市场。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询活动集快照/范围/拒绝；DRAFT不变ACTIVE；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：相关路线待补/阻断；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-03-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-03-A：普通人员改包

- 依据：REQ-CTX-03；AC-CTX-03-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：普通人员改包。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用本条无权主体调用resolve_context或申请未获准的规则/资料替换；检查读取/外传/活动规则权限，不能依赖浏览器隐藏；请求输入须同时满足本条条件和数据变体；③ 查询活动集快照/范围/拒绝；DRAFT不变ACTIVE；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：不能把DRAFT激活或替换生效版本；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-03-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-04-N：运行快照

- 依据：REQ-CTX-04；AC-CTX-04-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：完成一次mock运行后留旧hash，再选择新版本。原场景条件：运行快照。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询新Run/hash与旧依据；历史不可改写；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：可回查当时输入/上下文/规则；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-04-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-04-E：包更新

- 依据：REQ-CTX-04；AC-CTX-04-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：修改包后请求原Run热切换。原场景条件：包更新。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询新Run/hash与旧依据；历史不可改写；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：新Run新hash，旧依据不热改；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-04-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-04-A：无历史访问权

- 依据：REQ-CTX-04；AC-CTX-04-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无历史访问权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询新Run/hash与旧依据；历史不可改写；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝展开受限manifest内容；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-04-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-05-N：有权补证且复查通过

- 依据：REQ-CTX-05；AC-CTX-05-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：明确owner补当前阶段必需材料。原场景条件：有权补证且复查通过。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询BLOCK/升级、双方依据；无权限不能解除；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：仅恢复对应范围；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-05-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-05-E：硬规则不可并存

- 依据：REQ-CTX-05；AC-CTX-05-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：两条同级适用硬规则无法并存。原场景条件：硬规则不可并存。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 调用受控resolve_context取得资料/规则；冲突场景查询双方引用及阻断，不创建运行或修改活动规则；请求输入须同时满足本条条件和数据变体；③ 查询BLOCK/升级、双方依据；无权限不能解除；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：保留BLOCK并升级；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-05-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-05-A：普通译审/模型裁决冲突

- 依据：REQ-CTX-05；AC-CTX-05-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied与service_actor分别参数化执行。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：普通译审/模型裁决冲突。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 用本条无权主体调用resolve_context或申请未获准的规则/资料替换；检查读取/外传/活动规则权限，不能依赖浏览器隐藏；请求输入须同时满足本条条件和数据变体；③ 查询BLOCK/升级、双方依据；无权限不能解除；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：拒绝解除阻断；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-05-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-06-N：页面来源可回查

- 依据：REQ-CTX-06；AC-CTX-06-N；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：有权读取的准确版本Ref。原场景条件：页面来源可回查。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询版本/缺证据提示；无权不返回正文/地址；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：看到准确版本和证据状态；实际操作/持久结果/页面三者一致；候选、人工确认、校验及发布状态分开。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-06-N/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-06-E：来源不可读

- 依据：REQ-CTX-06；AC-CTX-06-E；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_allowed发起操作；运行模块使用独立service_actor，不复用人类会话。
- 数据：源文件不可读或证据不存在。原场景条件：来源不可读。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 以当前主体查询Task/Run/Segment/Artifact的受控追踪或统计数据；请求输入须同时满足本条条件和数据变体；③ 查询版本/缺证据提示；无权不返回正文/地址；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：显示不可核验，不假称证据有效；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-06-E/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

### TC-SRC-CTX-06-A：无证据读取权

- 依据：REQ-CTX-06；AC-CTX-06-A；[任务T1.2](../../07-delivery-plans/sub-delivery-plan-source-release-T1.2-execution-controls.md)；状态：NOT_RUN；范围：SOURCE_CORE。
- 前置：实现/可信测试鉴权/隔离存储/能力ID适配可用；合成响应路由就绪。主体：human_denied。
- 数据：保持正常数据与版本，只移除本次动作授权；按原场景另选service_actor或outsider。原场景条件：无证据读取权。
- 步骤：① 用TEST_RUN_ID建立隔离数据，记录当前修订/hash、决定/事件/工具调用基线；不要直接写入预期状态；② 直接以已知受限对象ID读取对应追踪/原文/证据，不走前端隐藏入口；请求不得返回正文、下载地址或存在性信息；请求输入须同时满足本条条件和数据变体；③ 查询版本/缺证据提示；无权不返回正文/地址；在页面02及结果依据区核对反馈，并对照执行端状态/持久记录/调用次数。
- 预期：受控提示并交有权人核验；失败/拒绝不写成功决定或推进状态；已有产物/失败/费用保留，若有工具调用必须可计数。
- 证据：`docs/08-test-reports/<execution-id>/TC-SRC-CTX-06-A/（实际执行时建立；请求响应/前后差异/trace，UI另留截图）`；实际结果留空，不能凭文档检查填PASS。
- 清理：仅按fixture-recipes清理本次沙箱；共享真实资料不删除。

## 验收矩阵

| TC | 需求 | 类别 | 执行状态 |
| --- | --- | --- | --- |
| TC-SRC-CTX-01-N | REQ-CTX-01 | normal | NOT_RUN |
| TC-SRC-CTX-01-E | REQ-CTX-01 | exception | NOT_RUN |
| TC-SRC-CTX-01-A | REQ-CTX-01 | permission | NOT_RUN |
| TC-SRC-CTX-02-N | REQ-CTX-02 | normal | NOT_RUN |
| TC-SRC-CTX-02-E | REQ-CTX-02 | exception | NOT_RUN |
| TC-SRC-CTX-02-A | REQ-CTX-02 | permission | NOT_RUN |
| TC-SRC-CTX-03-N | REQ-CTX-03 | normal | NOT_RUN |
| TC-SRC-CTX-03-E | REQ-CTX-03 | exception | NOT_RUN |
| TC-SRC-CTX-03-A | REQ-CTX-03 | permission | NOT_RUN |
| TC-SRC-CTX-04-N | REQ-CTX-04 | normal | NOT_RUN |
| TC-SRC-CTX-04-E | REQ-CTX-04 | exception | NOT_RUN |
| TC-SRC-CTX-04-A | REQ-CTX-04 | permission | NOT_RUN |
| TC-SRC-CTX-05-N | REQ-CTX-05 | normal | NOT_RUN |
| TC-SRC-CTX-05-E | REQ-CTX-05 | exception | NOT_RUN |
| TC-SRC-CTX-05-A | REQ-CTX-05 | permission | NOT_RUN |
| TC-SRC-CTX-06-N | REQ-CTX-06 | normal | NOT_RUN |
| TC-SRC-CTX-06-E | REQ-CTX-06 | exception | NOT_RUN |
| TC-SRC-CTX-06-A | REQ-CTX-06 | permission | NOT_RUN |

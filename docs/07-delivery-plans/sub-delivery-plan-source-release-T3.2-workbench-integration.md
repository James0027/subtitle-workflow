# T3.2：工作台与端到端交互

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T3.2 工作台与端到端交互

**Requirement ID**：REQ-MAIN-R01, REQ-MAIN-R02, REQ-MAIN-R06, REQ-MAIN-R11, REQ-MAIN-R17；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [01子PRD](../05-prd/01-subprd-intake-task.md)，重点读契约、异常和验收节。
- [02子PRD](../05-prd/02-subprd-asr-alignment.md)，重点读契约、异常和验收节。
- [07子PRD](../05-prd/07-subprd-compliance-delivery.md)，重点读契约、异常和验收节。
- [08子PRD](../05-prd/08-subprd-review-versions.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：把V3 01/02/03/04/08的真实操作接到冻结接口：保存/确认/进度/回听/编辑/检查下载；原型仍保留，产品页面独立实现，所有错误/权限原因由执行端返回。

**核心文件**：code/web/（当前为空，页面文件在T0.1确认）；code/backend/main.py；docs/02-prototype/pages/作为只读交互参考。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：页面刷新不重跑；成功响应后才更新状态；旧版失败保留编辑；无权限有原因；可从确认任务到候选/人审/当前合格源语文件完成一次实际闭环。

**Verification Method**：执行E2E-01和对应域TC的UI观察，另测刷新/重复点击/失败编辑保留；留下浏览器与执行端同一trace证据。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T3.2/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：静态折叠、动画或Mock响应不能当真实闭环；若接口未实现则不得把展示稿记完工。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T1.1；完整联调依赖T2.1、T2.2、T3.1。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

提供授权主体可见的试点范围/开关状态和关闭反馈；实际系统版本恢复命令依运行方案实现，不提前提供无鉴权控制后台。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

## 2026-10-21确认后的完成标准

任务草稿与确认同ID；编辑区与审核区分权；源语与目标语均按内部生成/检查→真人签发→正式导出展示，未签不提供正式下载，保持准确版本/错误反馈。

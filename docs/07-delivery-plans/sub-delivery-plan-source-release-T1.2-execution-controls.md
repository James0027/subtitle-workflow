# T1.2：执行、授权和追踪控制

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T1.2 执行、授权和追踪控制

**Requirement ID**：REQ-MAIN-R03, REQ-MAIN-R04, REQ-MAIN-R05, REQ-MAIN-R14, REQ-MAIN-R15, REQ-MAIN-R19；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [01子PRD](../05-prd/01-subprd-intake-task.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：实现run受理/查询、持久状态/attempt/step、有效结果防重、授权/撤销竞争检查及Task累计停止；先接可控Mock验证，不启真实付费。

**核心文件**：code/backend/workflow/engine.py、state.py、hooks.py；shared/controls/__init__.py、shared/context/__init__.py；config/workflow.yaml。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：同键并发只一组有效结果；无任务/撤权/停止/旧版无新工具调用；在途晚到与费用保留；不同Run不能清Task累计；真实动作能回查输入/主体/步骤。

**Verification Method**：执行TC-SRC-EXEC/CTX及相关MAIN、E2E-05/06/08/11；记录Mock调用次数、原子竞争与重启证据；预算B等须已批准。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T1.2/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：缺预算/计次策略禁收费自动路线；Mock通过不记模型质量通过；未知在途结局不得自动重跑。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T1.1。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

实现受控范围开关/允许名单的执行端校验、关闭后停止领取和晚到结果隔离；权限与停止控制不可由前端绕过。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

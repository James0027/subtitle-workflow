# T2.2：人工审阅与版本保护

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T2.2 人工审阅与版本保护

**Requirement ID**：REQ-MAIN-R11, REQ-MAIN-R12, REQ-MAIN-R13, REQ-MAIN-R16；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [08子PRD](../05-prd/08-subprd-review-versions.md)，重点读契约、异常和验收节。
- [02子PRD](../05-prd/02-subprd-asr-alignment.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：实现逐条/批量接受、草稿/明确确认、驳回/升级、当前分支并发、历史与回滚；按T0.1映射控制人工锁定和下游失效。

**核心文件**：code/backend/db/__init__.py、workflow/state.py、shared/controls/__init__.py；拟建审阅/版本存取实现文件；tests/integration/。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：草稿不变人工确认；服务主体不能确认或改锁定稿；批量逐项结果正确；回滚复制历史为新修订，受影响检查/签名无效且原历史不删。

**Verification Method**：执行TC-SRC-REV及MAIN-R11/12/13/16、E2E-03/08；核对实际前后内容、决定、分支指针和依赖失效清单。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T2.2/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：锁定动作或草稿读取映射未冻结则相应写入口不开；不能用假accept或改统计状态代替确认。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T1.2；联调依赖T2.1。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

按三类回滚边界实现内容恢复为新修订、受影响校验/签发失效和历史保护；不将内容回滚当系统/数据恢复。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

## 2026-10-21确认后的完成标准

保存编辑可继续，提交表示编辑完成/待审并记录review.submitted；审核由单独授权真人确认，提交不改HUMAN_APPROVED。保留人工修复/AI辅助/复验，不做自主修复。

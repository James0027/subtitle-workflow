# T0.1：冻结首批方案并验证工具边界

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T0.1 冻结首批方案并验证工具边界

**Requirement ID**：REQ-MAIN-R01, REQ-MAIN-R02, REQ-MAIN-R06, REQ-MAIN-R15；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [01子PRD](../05-prd/01-subprd-intake-task.md)，重点读契约、异常和验收节。
- [02子PRD](../05-prd/02-subprd-asr-alignment.md)，重点读契约、异常和验收节。
- [07子PRD](../05-prd/07-subprd-compliance-delivery.md)，重点读契约、异常和验收节。
- [08子PRD](../05-prd/08-subprd-review-versions.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：审阅D01—04；固定解释器/依赖/模型权重及样本许可；明确三路线可支持输入、草稿/锁定动作、序列化、权限/预算计次；用实际兼容证据更新基线。不得据空框架或研究报告宣称工具已可用。

**核心文件**：docs/03-foundation/source-release-contract.md、schema.md；config/config.yaml；requirements.txt（依赖冻结后才写）。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：D01—04逐项有实际决定/责任；三路线能力验证记录或明确不支持输入；首批格式/身份/控制与接口字段无待补开工条件；批准的变化同步schema/规则/TC。

**Verification Method**：逐项对照方案§7和技术契约；安装/真实工具验证需相应授权，取得实际输出与版本后才能登记可用；没有许可仅能完成方案审阅。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T0.1/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：D01—04未定、安装/数据授权缺失或任一工具路线缺能力则保持阻塞，不临时换输入/假成功。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：无；D01—04及安装/数据授权待定。

**状态**：阻塞

2026-10-21准备更新：用户确定源语首批并授权Codex自主软件选型；本机原生页面、Python/FastAPI、SQLite/本地文件与单worker方向已定。[工程交接](antigravity-source-engineering-handoff.md)已准备，未发送Antigravity。当前仅技术方向部分达成，解释器/依赖兼容、真实语种/许可/权限及AI参数仍未齐，不记T0.1完成或代码开工。

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

冻结M0—M4验收/日期与人选、灰度批次必要参数、版本/兼容与恢复策略、阈值和费用口径；缺准入参数不能进入G1。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

# T4.1：真实样本验收与发布准备

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T4.1 真实样本验收与发布准备

**Requirement ID**：REQ-MAIN-R01, REQ-MAIN-R06, REQ-MAIN-R14, REQ-MAIN-R15, REQ-MAIN-R17, REQ-MAIN-R19；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [01子PRD](../05-prd/01-subprd-intake-task.md)，重点读契约、异常和验收节。
- [02子PRD](../05-prd/02-subprd-asr-alignment.md)，重点读契约、异常和验收节。
- [07子PRD](../05-prd/07-subprd-compliance-delivery.md)，重点读契约、异常和验收节。
- [08子PRD](../05-prd/08-subprd-review-versions.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：按批准范围运行核心TC与真实模型/时间评测，核对缺陷、样本/代码/工具版本，准备本版运行/恢复/备份说明和待发布清单；只准备发布，不自动部署。

**核心文件**：tests/unit/、tests/integration/、evals/；docs/08-test-reports/（实际测试时建立）；docs/09-deploy/（有真实方案时建立）。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：源语核心TC逐条有结果/证据，未执行/阻塞不算通过；独立金标与实际WER/边界/严重错误记录齐；硬底线零未解决失败；批准阈值达标；恢复演练有实际证据。

**Verification Method**：执行TC索引中适用核心与REAL_TOOL用例；用实际运行报告及缺陷清单验收。OPTIONAL_SHARED不纳入未承诺首批范围；部署需另按授权执行。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T4.1/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：样本/权限/阈值未批准，模型质量不能验收；文档检查不得替代业务测试；无部署授权不执行发布。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T3.2。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

准入验收须执行回归规定的177项组合，6项发布演练含兼容/不兼容回退、无旧版关闭、损坏备份拒绝、在途核对、撤回名单及扩量限制；形成实际运行/恢复说明、受影响对象清单和证据。G1/G2批次另记状态，不能将准备完成当试点已通过。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

## 影子验证与版本回退补充验收（2026-10-21）

完成标准追加：按主计划§9.7运行获准影子对照及代表性输入性能检查，证明正常稿/正常审稿人/交付不受影响，原始差异、环境/资源/耗时与费用可查；没有真实运行或批准门槛不记达标。验证TC索引§6.4的三组参数化分支及REL-03旧规则失效、未知组合拒绝分支。复用人工定位/AI辅助/复验，不开发自主修复循环。

当前仍阻塞、全部未执行；未改变用例ID、总数或开发状态。

## 2026-10-21确认后的完成标准

逐分支核查稳定ID/草稿准备与ASR阻断、编辑提交/审核分权、签发前拒绝正式下载、签后可导出、改字/重生成/规则失效后旧签失效、影子隔离/性能和保守回退。发布组合177项全部要有实际结果，当前未执行。

# T3.1：源语校验、导出和解析一致

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T3.1 源语校验、导出和解析一致

**Requirement ID**：REQ-MAIN-R17, REQ-MAIN-R18；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [07子PRD](../05-prd/07-subprd-compliance-delivery.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：按实际所选格式生成源语文件，重新解析并逐cue比较，保存行到片段修订映射、hash、Validation；下载每次鉴权，诊断与合格文件分开。

**核心文件**：code/backend/modules/compliance/contract.py、handler.py、tests/test_compliance.py；shared/storage/__init__.py；tests/integration/。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：未审/旧版/越范围/解析差异不VALIDATED；真实文件文字时间顺序与确认稿一致且可反查；下载越权拒绝；首批无外部回执不PUBLISHED。

**Verification Method**：执行TC-SRC-OUT核心分支、MAIN-R17/R18防越权、E2E-07；以实际字节/解析差异与记录判定，不以文件存在通过。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T3.1/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：格式/规范/允许变换未定或有损样式不能证明一致则阻塞；首批签发必须实现，外部回执成功分支后续接入，不假造平台通过。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T2.1、T2.2。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## 2026-10-21确认后的完成标准

首批必须实现真人签发：内部生成/重解析得到VALIDATED，签发绑定当前包/hash/内容/Task/规则和检查后才开放正式GET文件并记录artifact.exported；无签/旧签/撤回/无权/机器发出拒绝，不因内部检查通过而完成Task。

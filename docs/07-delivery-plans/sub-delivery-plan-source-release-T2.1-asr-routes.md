# T2.1：三路线源语处理适配

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T2.1 三路线源语处理适配

**Requirement ID**：REQ-MAIN-R06；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [02子PRD](../05-prd/02-subprd-asr-alignment.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [10子PRD](../05-prd/10-subprd-execution-tracing.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：按已确认能力接新转写、已有稿核对和文本不变的对齐；封装工具/输入解析、毫秒/offset、分段/重叠、专名和部分失败；固定manifest并仅保存候选。

**核心文件**：code/backend/modules/asr_alignment/contract.py、handler.py、prompts/；shared/tools/__init__.py、shared/models/__init__.py；模块tests/test_asr_alignment.py。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：三路线逐一有真实工具输入输出证明或明确前置缺失拒绝；对齐回退不能装成功；候选仍AI_PROPOSED，原字幕/确认稿不变；空输出FAILED且后续未执行。

**Verification Method**：执行TC-SRC-ASR和E2E-02/10/12；先Mock错误路径，再用获准真实样本验证工具边界；模型质量另按批准金标/阈值评价。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T2.1/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：任何路线不支持首批语种/窗口须报阻塞，不能静默换为转写、均分时间或人工猜稿。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T1.2。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

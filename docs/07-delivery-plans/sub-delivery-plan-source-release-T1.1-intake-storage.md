# T1.1：接收与任务版本存取

> 上游：[主计划](main-delivery-plan-source-release.md)、[看板](task-kanban-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：[主计划反向索引](main-delivery-plan-source-release.md)、未来任务执行证据。

#### T1.1 接收与任务版本存取

**Requirement ID**：REQ-MAIN-R01, REQ-MAIN-R02；相关局部REQ及TC见正式索引。

**PRD 双链·读**：

- [主PRD](../05-prd/mainprd.md) §二、六—九。
- [01子PRD](../05-prd/01-subprd-intake-task.md)，重点读契约、异常和验收节。
- [09子PRD](../05-prd/09-subprd-context-rules.md)，重点读契约、异常和验收节。
- [技术契约草案](../03-foundation/source-release-contract.md)、[schema](../03-foundation/schema.md)、[规则](../03-foundation/rule-registry.md)、[正式TC索引](../06-testcase/tc-main-subtitle-workflow.md)。

**核心逻辑**：实现同项目原件/派生引用、母版人工确认、任务草稿/确认和不可变快照；按冻结方案建立实际数据存取/事务，任务前对象记录按已有条件留痕。

**核心文件**：code/backend/main.py、db/__init__.py、shared/storage/__init__.py；拟建持久化/接收实现文件（T0.1固定）。以上均为计划修改位置，当前代码框架为空；没有创建占位实现或生产表。

**完成标准**：重复请求只一个Task；错版/无权/旧修订拒绝且有记录；原件hash不变；母版/任务确认分别保存；重启后能读取同一修订与事件。

**Verification Method**：执行TC-SRC-INT组及MAIN-R01/R02相关TC，检查实际存取/拒绝和重启结果；模拟文件与真实授权媒体分别标记。

**Evidence**：实际执行时在`docs/08-test-reports/<execution-id>/T1.1/`保存；本轮方案/链接检查放工作区work/首批落地准备/检查记录，不能计作该任务完成。

**Failure Handling**：存储/身份/条件字段与冻结契约不一致则停本任务；不得让前端自行拼确认结果。

**完成收尾：状态同步**：实际实现/验证达成后，同时回写主计划阶段表、任务看板及本子计划状态/完成日期，并更新唯一进度和日志；有失败/未完成前置不能记已完成。开工一致性脚本到实际开工再运行，不能伪造进行中满足脚本。

**Owner**：AI执行 → 人审核业务选择和验收证据。

**前置**：T0.1。

**状态**：阻塞

**阻塞原因**：当前仅授权方案/计划/用例准备；T0.1的实际范围/技术/素材/控制参数尚待确定，后续实现还缺前置任务。没有已开工代码任务。

**完成日期**：-

## ⑨补充验收与交接

实现与批准存储匹配的一致性备份及恢复核验基础，覆盖文件清单/版本与恢复点后差额；不能仅复制活动数据库文件。

依据：[灰度/回滚安排](main-delivery-plan-source-release.md#rollout)、[回归规则](../06-testcase/tc-main-subtitle-workflow.md#regression)及[发布演练](../06-testcase/source-release/tc-source-e2e.md#release-operations)。此项并入本Task完成标准；实际实现仍阻塞，未增加已完成任务。

## 2026-10-21确认后的完成标准

草稿创建即稳定task_id，先以ingest准备/抽轨，再确认Media/Task；无Task不创建抽轨，Draft不能执行ASR。派生Asset.transform.run_id指向真实准备Run；原件/失败均保留。

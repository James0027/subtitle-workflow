> 本项目适配：本文件保留计划协议/模板细节；示例技术、demo任务和状态不是当前项目事实。当前无正式开发计划，具体方案/子PRD/接口未齐，不据此开工。已获当前会话明确授权的范围不重复索取同一批准。

# T0.1 Demo Sub Delivery Plan

## 任务来源

- 主开发计划：[main-delivery-plan-demo.md](main-delivery-plan-demo.md)
- 任务看板：[task-kanban-demo.md](task-kanban-demo.md)

#### T0.1 实现演示任务

**Requirement ID**：REQ-DEMO-001

**PRD 双链·读**：
- `docs/05-prd/mainprd.md` §1

**核心逻辑**：
- 根据 PRD 处理演示任务。

**核心文件**：
- `code/src/demo.js`

**完成标准**：
- 运行 `node code/src/demo.js` 输出 demo-ok。

**Verification Method**：
- 执行 `node code/src/demo.js`。

**Evidence**：
- 当日开发日志（`docs/00-process/00-01-logs/YYYYMMDD.md`）

**Failure Handling**：
- PRD 或核心文件定位不到时阻塞。

**完成收尾：状态同步**：
- 本 Task 完成实现和验证后，把完成事实、验证证据、完成日期和建议下一 Task 同步回写三处：`main-delivery-plan-<slug>.md` 执行阶段表、`task-kanban-<slug>.md` 对应行、本子开发计划的 `**状态**` 字段。
- 同步更新 `docs/00-process/00-02-progress/progress.md` 的进度快照。
- 回写后重新运行 `node .agents/skills/delivery-planner/scripts/check-plan-consistency.mjs docs/07-delivery-plans/main-delivery-plan-<slug>.md --json`，确认三处一致；未通过前不得宣称本 Task 已完成。

**Owner**：AI 执行 -> 人审核

**前置**：无

**状态**：待审阅

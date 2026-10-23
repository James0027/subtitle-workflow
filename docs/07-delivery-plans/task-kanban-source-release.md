> 2026-10-21当前决定：用户要求清除Whisper阶段实现，先确认音频理解框架与详细开发安排，再开发；既有业务PRD/原型/契约/测试设计保留复用。项目内asr-validation环境、模型、代码和运行产物已删除，本地旧服务已停止。下方Whisper派发/运行/URL均为历史，不得照其继续执行或重装。总体框架已确认，具体实现待评审，未调用Gemini、未外发素材、未收费、未开新工程。 新审阅入口：[框架与开发安排](main-delivery-plan-source-release.md)。

# 首批源语闭环任务看板

> 上游：[主计划](main-delivery-plan-source-release.md)、[落地方案](source-release-solution.md)。
> 下游：各子开发计划及唯一项目进度。状态只记录实现任务，不把计划编写当功能完工。

2026-10-21：[工程交接准备](antigravity-source-engineering-handoff.md)已建立，软件路线由Codex选定；AI设计保留共同确认。未派发Antigravity，T0.1整体前置未齐，以下实现状态保持不变。

| Task | 子开发计划 | Owner | 前置 | 状态 | 完成日期 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| T0.1 | [冻结首批方案并验证工具边界](sub-delivery-plan-source-release-T0.1-baseline.md) | AI执行→人审核 | 无；D01—04及安装/数据授权待定 | 阻塞 | - | D01—04/前置未齐，未开工 |
| T1.1 | [接收与任务版本存取](sub-delivery-plan-source-release-T1.1-intake-storage.md) | AI执行→人审核 | T0.1 | 进行中 | - | 首版独立审核未过；Gemini按既有报告返修，待真实素材/浏览器验收 |
| T1.2 | [执行、授权和追踪控制](sub-delivery-plan-source-release-T1.2-execution-controls.md) | AI执行→人审核 | T1.1 | 阻塞 | - | D01—04/前置未齐，未开工 |
| T2.1 | [三路线源语处理适配](sub-delivery-plan-source-release-T2.1-asr-routes.md) | AI执行→人审核 | T1.2 | 进行中 | - | 已授权固定切片转写/五项质量提示工程；实际云调用待配置及许可，不含全三路线 |
| T2.2 | [人工审阅与版本保护](sub-delivery-plan-source-release-T2.2-review-versions.md) | AI执行→人审核 | T1.2；联调依赖T2.1 | 阻塞 | - | D01—04/前置未齐，未开工 |
| T3.1 | [源语校验、导出和解析一致](sub-delivery-plan-source-release-T3.1-export-validation.md) | AI执行→人审核 | T2.1、T2.2 | 阻塞 | - | D01—04/前置未齐，未开工 |
| T3.2 | [工作台与端到端交互](sub-delivery-plan-source-release-T3.2-workbench-integration.md) | AI执行→人审核 | T1.1；完整联调依赖T2.1、T2.2、T3.1 | 阻塞 | - | D01—04/前置未齐，未开工 |
| T4.1 | [真实样本验收与发布准备](sub-delivery-plan-source-release-T4.1-acceptance-readiness.md) | AI执行→人审核 | T3.2 | 阻塞 | - | D01—04/前置未齐，未开工 |

## ⑨补充交接

灰度/系统回退/回归安排已补入[主计划§9](main-delivery-plan-source-release.md)及T0.1/T1.1/T1.2/T2.2/T3.2/T4.1完成标准；未新增或开工Task。

---
name: delivery-planner
description: 在字幕项目进入已授权的代码实施阶段后，按已评审PRD生成或更新主开发计划、任务看板和单任务子计划，校验三者一致；不用于主PRD编写、纯文档任务、测试排期或自动启动开发。
---

# 开发实施计划（准备完成，按阶段使用）

先读[AGENTS](../../../AGENTS.md)、[来源核对规范](../../../rules/source-check-workflow.md)、[提交边界](../../../rules/change-and-submission.md)和本次实际需求。技能迁移不授予开发/安装/提交/部署权限。

## 1. 阶段与来源门禁

- 当前主PRD仍待评审、子PRD/接口和技术方案未齐，本轮不生成正式开发计划；到对应阶段才使用。
- 主PRD固定为`docs/05-prd/mainprd.md`，BRD为`docs/01-brd/BRD.md`；项目短名`subtitle-workflow`不要求改主PRD文件名。
- schema在`docs/03-foundation/schema.md`，规则/指标/样本在同目录；术语从已有定义定位，不创建空glossary目录。
- 接口类任务须有相关子PRD中的接口契约及实际对接依据；当前并不存在外部/本系统API目录，不能把逻辑schema当生产DDL或已接通服务。
- 按[来源读取顺序](references/source-loading-order.md)建立必需资料清单。缺子PRD/接口/真实环境时明确缺项及受影响任务，只能在用户确需时写有依据的阻塞草案，不编造接口/技术栈/完成标准。

## 2. 计划协议

输出在`docs/07-delivery-plans/`：主计划`main-delivery-plan-<slug>.md`、看板`task-kanban-<slug>.md`、每Task一个`sub-delivery-plan-<slug>-<TaskID>-<short-name>.md`。

按需读取完整模板与参考：
- [主模板](templates/main-delivery-plan-template.md)、[子模板](templates/sub-delivery-plan-template.md)、[看板模板](templates/task-kanban-template.md)。
- [计划结构与状态](references/plan-anatomy.md)、[自检门禁](references/quality-gates.md)。

模板中的demo、日期、技术/环境和示例文件均是格式示例，不是本项目真实依赖或事实。用实际批准方案替换，不默认MySQL、Java、Cloudflare或solo-local，也不因占位.py文件确定Python后端。

主计划保留以下13部分以便校验：计划元信息、本计划使用指南、PRD加载约束、读前门禁、完成前验证门禁、差距基线、分工与边界、执行阶段、任务看板、发布闸门、风险、AI执行示例、PRD→任务反向索引。

每个子任务含`PRD 双链·读`、核心逻辑、核心文件、完成标准、完成收尾：状态同步、Owner、前置、状态；关键任务加Requirement ID、Verification Method、Evidence、Failure Handling。关键Phase写Entry/Exit Criteria。

先据PRD定目标，再检查实际代码/配置/验证资产。现有代码均为空脚手架，不等于已有可运行后台。任务按可验收产物拆分，不把实现猜测写成事实。

## 3. 状态、授权与回写

新计划草稿待审阅；人已在当前会话明确批准的范围不重复请求同一批准。是否可开工由现有授权、资料、环境和任务状态共同决定，技能不能自动将草稿翻为可开发。

完成任务前执行其实际验证，保留证据，同步主计划、看板、对应子计划，再更新唯一进度；日志交project-devlog执行，避免复制两份任务正文。未满足完成标准或未回写不能记完成。

## 4. 两个独立检查器

在项目根、现有Node可用时执行：
```powershell
node .agents/skills/delivery-planner/scripts/validate-plan-structure.mjs <主计划路径> --json
node .agents/skills/delivery-planner/scripts/check-plan-consistency.mjs <主计划路径> --json
```

前者查13章、计划/看板/子任务对应及字段；后者在实际开工前查当前Task和三处状态/链接/完成日期一致，要求有且仅有一个进行中任务。前者不等于允许开发，后者不用于强迫草稿存在“进行中”任务。`0`通过、`1`参数/文件错误、`2`结构或状态失败；失败先修原因，不能降低校验标准凑PASS。

脚本仅依赖Node内置模块。迁移时只改`.agent`路径拼写，不改其验证算法；本轮仅在work夹具验证，不生成正式开发计划。

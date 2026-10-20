# 多语种字幕智能校对与文化适配系统

当前为产品设计阶段。正式产物按课件§1.5—1.6与参考工程归类；业务代码、真实ASR/规则引擎/统计/发布尚未实现。

- [十二步产物总目录](docs/README.md)：每步交什么、现在完成什么，以及与§0.3.1业务产物的区别。
- [原型](docs/02-prototype/pages/index.html)与[页面清单](docs/02-prototype/page-list.md)：当前V3：八个独立步骤交互稿，待评审。
- [数据/规则/指标](docs/03-foundation/README.md)：字段、样本、规则和统计定义。
- [主PRD v0.3](docs/05-prd/mainprd.md)：全局目标/权限、架构与导航、页面/接口、主/异常链路、数据全景及子PRD大纲；正文草稿待评审。
- [当前进度](docs/00-process/00-02-progress/progress.md)：唯一进度快照。
- [AGENTS.md](AGENTS.md)：AI工作入口、权限和来源核对。

主PRD及[十份功能子PRD](docs/05-prd/README.md)正文草稿已建立，待内容评审；局部59条需求/177项细化场景均未执行。19条P0/P1全局需求各定义正常/异常/权限场景，共57项，完整保留于[验收覆盖台账](docs/05-prd/acceptance-map.md)，尚未执行。原型辅助检查记录在工作区work，不代表业务测试阶段已完成。


## GitHub存档范围

本仓库保存当前项目文档、V3原型及现有代码框架；不是可运行后台或已上线产品。仓库要求保持Private，不启用公开Pages或自动部署。

工作区外层的work讨论/辅助检查、meeting原文、参考课件与真实素材仅保留本地，不纳入本次上传。文档中指向这些外部位置的引用用于本机追溯，单独克隆仓库时不包含；不要把缺少外部资料理解为已完成相应验证。

私有仓库：[James0027/subtitle-workflow](https://github.com/James0027/subtitle-workflow)。仅授权账号可访问；当前未邀请其他协作者。

## 首批源语落地准备（2026-10-20）

[首批方案](docs/07-delivery-plans/source-release-solution.md)、[技术契约草案](docs/03-foundation/source-release-contract.md)、[实施计划草案](docs/07-delivery-plans/main-delivery-plan-source-release.md)、[正式TC设计](docs/06-testcase/tc-main-subtitle-workflow.md)。

首批仅收料/任务→转写、核对或对齐→人工源稿审阅→源语导出；174条TC设计全部NOT_RUN，8项实现任务全部阻塞。技术方案及契约是PROPOSED，数据字段仍以schema为权威；采纳扩展须在T0.1先同步权威定义。真实样本、权限、模型/阈值和预算仍待确认；多语模块未纳入本批实现。不把静态检查或合成配方当业务验收。

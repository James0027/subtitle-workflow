# 项目产物总目录

> 上游（我引用）：[AGENTS](../AGENTS.md)；字幕课件§0.3.1、§1.5、§1.6；参考工程docs目录及原型说明。
> 下游（引用我）：[项目首页](../README.md)；[当前进度](00-process/00-02-progress/progress.md)。

## 1. 先分清两类产物

**§0.3.1：字幕业务运行时交付什么。** 这些是处理一部作品的结果，不是开发文档。

| 原文阶段 | 原文主要产出 | 当前含义 |
| --- | --- | --- |
| 素材入库 | 母版与任务单 | 数据契约定义身份和任务字段；还不代表真实母版/任务单已建立 |
| 听写对齐 | 源语字幕 | ASR/人工核实后的源语字幕；构造页面示例不算真实产出 |
| 初翻 | 目标语初稿 | 基于源字幕与目标条件产生的候选 |
| 文化审校 | 修改意见 | 有语境、规则和证据的建议/人工决定 |
| 语言审校 | 终稿 | 经授权人工确认的内容版本 |
| 格式质检 | SRT/VTT/TTML | 对应任务和有效规范的交付文件 |
| 发布 | 平台版本 | 有实际人工交接/外部回执，不把生成文件当发布 |

上述原始/派生文件的运行存储位置在真实实现时确定，不提前建空母版/字幕/平台版本目录假装已有产物。数据文档定义存什么，PRD定义何时怎样产生，代码负责落实。

## 2. §1.5十二步建设产物与当前位置

编号是课件步骤；目录编号沿用参考工程分类，二者不一一同号。

| 步骤 | 必须交付 / §1.6关键要求 | 正式位置 | 当前状态 |
| --- | --- | --- | --- |
| ① AGENTS | 目录、权限、禁止项、日志、测试与提交标准 | [AGENTS.md](../AGENTS.md)及rules | 已建立，已按本轮归位更新 |
| ② BRD | 对象、基线、目标、非目标、成本；人工分钟口径 | [01-brd/BRD.md](01-brd/BRD.md) | 内容已审阅；真实基线/目标未伪填 |
| ③ 原型 | 逐状态交互：候选/人工/冲突/失败/升级/发布，低置信/缺证据/批量/驳回/回滚 | [02-prototype](02-prototype/README.md)、[页面清单](02-prototype/page-list.md)、[HTML](02-prototype/pages/index.html) | V3八个独立步骤页待评审，V1/V2历史保留；仅一份正式目录 |
| ④ 数据锁定 | schema+样本：字段、血缘、脱敏、样本桶、标签 | [schema](03-foundation/schema.md)、[samples](03-foundation/samples.md) | v0.1定义内容认可；真实样本未冻结 |
| ⑤ 规则锁定 | 优先级、版本、市场覆盖、硬软规则 | [rule-registry](03-foundation/rule-registry.md) | v0.1认可；参考阈值未自动启用 |
| ⑥ 指标锁定 | 分母、窗口、去重、置信区间、报警线 | [metrics](03-foundation/metrics.md)、[事件](03-foundation/metric-events.md) | v0.1认可；未采集真实指标 |
| ⑦ 主PRD | 端到端状态机、角色、主/异常链路、权限及业务目标承接 | [mainprd.md](05-prd/mainprd.md) | 2026-10-20正文v0.2按确认分工重排，待评审；19条需求/57场景保留于[验收台账](05-prd/acceptance-map.md)，未执行 |
| ⑧ 子PRD | 六模块与必要共享功能的输入输出、操作、工具、停止、兜底 | [十份子PRD索引](05-prd/README.md) | 十份正文草稿已建立，59条局部需求/177场景NOT_RUN；非正式TC |
| ⑨ 计划与测试 | 里程碑/依赖/灰度/回滚/回归集及正常/异常/权限用例 | [源语实施计划](07-delivery-plans/main-delivery-plan-source-release.md)、[正式TC设计](06-testcase/tc-main-subtitle-workflow.md) | 首批源语准备稿已建立；8实现任务阻塞；174业务TC+6发布演练均NOT_RUN；[灰度/回滚](07-delivery-plans/main-delivery-plan-source-release.md#rollout)及[回归集](06-testcase/tc-main-subtitle-workflow.md#regression)已设计；多语实现计划未建立 |
| ⑩ 开发 | 代码、配置、feature flag、事件埋点 | code/、config/ | 仅既有框架，非已实现 |
| ⑪ 测试 | 离线/影子/灰度，准确/稳定/性能/安全/成本 | tests/、evals/；[工单报告](08-test-reports/20261023-e2e-report/20261023-e2e-full-pipeline-report.md) | 六段式工程实测 6/6 通过（零模型、隔离库）；业务/模型验收未执行，174 条正式 TC 仍 NOT_RUN |
| ⑫ 部署 | 版本、发布清单、监控、回滚、责任与运行手册 | docs/09-deploy（未建立） | 未部署 |

`04-diagrams`为参考模板的辅助图示位置，有需要时建立，不是额外的第十三步。未开始阶段不提前创建空文档/目录凑产物。

主子PRD的[分工与全局内容安排](05-prd/README.md)已获用户确认并落实到主PRD v0.3：系统架构、导航、页面/接口调用全景、系统数据全景及十项功能子PRD大纲。台账完整承接19需求/57场景，不构成第三级PRD；十份功能子PRD正文草稿已建立；接口/序列化等实现前待办集中于子PRD索引。

## 3. 参考模板复用与本项目调整

- 复用其00-process/01-brd/02-prototype/03-foundation/05-prd/06-testcase/07-delivery-plans/08-test-reports/09-deploy分类。
- 参考03-foundation有术语/API/schema等子层；当前基础文件较少，先平铺schema、samples、rule-registry、metrics、metric-events，不复制无内容的层级或数据库选型。
- `contracts`与`requirements`是此前助手新增的分组，不是课件强制要求；本轮已归位，不再并存两套现行入口。
- 原型是page-list、HTML和行为说明。测试用例是怎样检查，报告是实际检查结果；三者不是同一种产物。早期检查有效但仅为辅助证据，不等于⑨/⑪完成。

## 4. 过程记录与辅助材料

- 正式过程记录：[进度](00-process/00-02-progress/progress.md)、[20261019日志](00-process/00-01-logs/20261019.md)。
- 2026-10-22 实机展示：[T1.1 全链路展示案例](08-test-reports/20261022-fullstack-demo/展示案例.md)，含 T1.1 收料→双确认、10 秒切片、Gemini 3.5 Flash Lite 转写（26 候选/9 预警）截图、实际落库 ID 与 7 项返修发现；只证明工程链路可用，不代表业务/模型质量验收。
- 2026-10-22 报告合并：[验收报告合并与当前真实状态](08-test-reports/20261022/合并状态核对-20261022.md)，合并 T2.1/恢复/翻译/文化四份报告，列已核验状态、未修缺陷（F1/F2/F4）与状态文档偏差。
- 2026-10-22 知识治理返修：[修复记录](08-test-reports/20261022/knowledge-governance-fix.md)，修复知识审计主体/市场语言校验/知识事件/迁移/前端转义与登录后加载；新增 6 项测试，全量 48 passed。
- 2026-10-22 工单03 单位与格式本地化引擎：[交付报告](08-test-reports/20261022/ticket03-unit-format-engine.md)，实现实体抽取/跳步、确定性换算与反向验算、舍入控制、剧情例外硬锁（体温/密码/纪录/日期/货币）；模块 pytest 42 passed，全量 59 passed；仅工程自测，AC-UNIT 场景与正式 TC 仍 NOT_RUN。
- 2026-10-22 工单04 口语适配与节奏审校引擎：[交付报告](08-test-reports/20261022/ticket04-oral-review-engine.md)，实现 CPS/行长/时长可读性度量、复杂句打标与时间守恒无损拆句、30 组书面语→es-MX 口语词库与 written_score、四重语义保护硬闸门（否定极性/事实实体/关系称谓/情绪反讽）；模块 pytest 84 passed，全量 59 passed；零模型（manifest 标 model_used=false、token_used=0），仅工程自测，AC-ORAL 场景与正式 TC 仍 NOT_RUN。
- 2026-10-22 工单05A 平台合规质检与导出引擎：[交付报告](08-test-reports/20261022/ticket05a-compliance-engine.md)，实现 Netflix Timed Text Profile 硬校验（CPS≤20、行长 42/21、行数≤2、时长 0.833—7.0s、零时长/重叠/<2 帧空隙阻断）、SRT/WebVTT 生成、独立反解析器与四断言重解析对账、五维哈希真人签发（仅 VALIDATED 可签，禁构造 PUBLISHED）；模块 pytest 90 passed，全量 59 passed、全模块 340 passed；零模型，仅工程自测，AC-OUT 场景与正式 TC 仍 NOT_RUN。
- 2026-10-22 工单05B 六段式全链路总装：[交付报告](08-test-reports/20261022/ticket05b-e2e-pipeline-integration.md)，把单位/格式、口语审校、平台合规三引擎接入正式应用（`/api/v1/units|oral|compliance`，统一可信会话与 503/403 fail-closed），并以 `tests/integration/test_end_to_end_pipeline.py` 串通 收料→源稿确认→初翻确认→文化检测→度量衡候选→口语审校→合规质检导出→五维哈希真人签发→产物获取；端到端 6 passed、`tests/ + code/backend/modules` 346 passed（基线 340）；零外部模型，文化环节以确定性规则路径替身，产物为进程内暂存，AC 场景与正式 TC 仍 NOT_RUN。
- 2026-10-23 工单06 六段式全链路双向实测：[统一交付报告](08-test-reports/20261023-e2e-report/20261023-e2e-full-pipeline-report.md)。六环节成功/失败双向实测（ASR 切片守恒+150ms 尾片合并、锁词遗漏+乐观锁、文化 R-MX-TABOO-01 闭环、度量衡反验算+四类剧情硬锁、CPS 28→15.67 无损拆句、QC_FAILED 熔断+真人五维签发 100% 对账），附 7 份 JSON 回执、SRT/VTT 导出、8 张 Chrome 截图与两份 pytest 日志（79 + 281 passed）；零外部模型调用，隔离库执行；仅工程实测，业务/模型验收未执行。
- 讨论/摘要/学习记录：工作区根work及知识索引。
- 原型辅助检查：work/原型制作/检查记录/v1、v2；契约静态检查：work/三项锁定/检查记录。保留用例、结果和截图，已移出正式测试区。
- 本轮旧→新路径、验证和历史路径解释：work/目录梳理/migration-map.json；不改历史会话中当时记录的事实。

## 2026-10-21确认后当前范围

稳定任务ID/草稿准备、编辑提交与审核分权、影子/性能、人主导修复、成套版本维护和所有正式导出真人签发已回写现有定义/主子PRD/原型/计划/用例。已确认业务设计可进入第⑩首批实施的基线与环境准备；实际栈/语种样本/身份/预算仍在T0.1落实，未安装或运行产品。

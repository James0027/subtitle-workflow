# 指标采集事件契约 v0.2

> 状态：设计草案，待评审；事件名为本项目拟定，不代表后台已埋点。
> 上游（我引用）：[指标契约](metrics.md) §2—6；[数据契约](schema.md) Event/Run/ReviewDecision；[规则注册表](rule-registry.md)。
> 下游（引用我）：[联合基线入口](README.md)；[指标契约](metrics.md) §3—5；主/子PRD及首批用例已建立，实现未开始。；[主PRD](../05-prd/mainprd.md)（全局目标、状态、权限及验收）；[01子PRD](../05-prd/01-subprd-intake-task.md)（收料/母版/任务与开工）；[功能子PRD索引](../05-prd/README.md)（十份功能规格）

## 1. 公共信封与时间

`event_id`、`event_type`、`event_at`、`received_at`、`task_id`、`actor_id/actor_type/actor_role`、`operation_id`、`dedup_key`、`schema_version`、`metric_contract_version` 为基础采集字段；执行事件再关联Run.idempotency_key。两时间采用带毫秒精度的UTC RFC3339 timestamp（如 `2026-10-19T08:00:00.000Z`），计算间隔转换为整数毫秒。`media_id`、`run_id`、`attempt_no`、`segment_id`、`candidate_id`、`issue_id`、`decision_id`、`artifact_id` 按事件关联，不适用明确null；缺关键关联隔离为坏事件，不能静默入成功分子。

引用 `source_revision`、候选修订、manifest及规则/model/prompt/profile版本；同一业务操作多个事件共享operation_id，每个事件event_id唯一；投递去重使用dedup_key，业务执行幂等使用Run.idempotency_key，两者不能混为一谈。关联实体也保留subject_refs。`run_id`是模块执行，`attempt_no`是其重试序号；不得拿日志重发当业务重试。

`event_at`由受信服务端记录业务实际发生时间；前端采样带client_at、时钟偏差/会话信息，由服务端校验；received_at只表示收到。跨设备时钟异常、负时长与重复区间进入计时核对队列，不修成漂亮数据。payload只收统计所需字段，文本/音画用受控ID引用，不复制素材或密钥。

新流程先创建稳定ID的Task草稿；素材准备ingest Run、Asset/Media确认及后续事件均绑定Task。读取已有无Task原始收料历史可保留null，但不再新建无Task母版确认或抽轨。历史不回填，不进入请求开工任务分母；素材准备完成不等于ASR开工。条件权威见[schema§6](schema.md)。

## 2. 事件目录

| event_type | 触发/额外payload | 指标用途 |
| --- | --- | --- |
| asset.registered | 素材清单接收完成；asset_id、hash、类型、来源/派生标记、登记结果 | 入库计数、重复/缺失，非母版确认 |
| media.confirmed | 有权限人确认权威修订；media_id/source_revision、声音来源、附件关系、确认人 | 成片分钟血缘、错版检查 |
| task.confirmed | 确认任务单；task_revision、范围、任务类型、execution_mode、execution_policy引用、语言/市场/profile引用、outputs、due_at | 交付分母与适用范围冻结；单模块/全流程分层 |
| readiness.checked | 每次开工检查；check_id、stage、task_revision、required/missing/not_applicable项、result、rule引用 | MET-INT-001；重复检查不增加任务分母 |
| task.ready | 达到指定阶段就绪；stage、ready_at、revision、授权证据 | TAT起点；不能每次重跑重置 |
| authorization.granted | 预授权决定保存成功；authorization_id、decision_id、task_revision、principal、scope | 授权审计，不计字幕接受 |
| authorization.revoked | 撤销预授权保存成功；authorization_id、decision_id、task_revision、principal、scope | 撤销审计，执行时重验 |
| run.started | 执行真正开始；module、run_id、attempt_no、manifest引用、input_ids | 运行/重试/版本分层 |
| run.finished | 每attempt_no结束；success/failed/stopped、failure_code、output_ids、token、latency_ms、已结/预估费用 | 调用、失败、成本；失败保留 |
| run.stop_checked | 运行前及重试前控制；累计预算/重试数、policy_version、decision、reason | 预算和停止合规 |
| candidate.created | 候选已存；candidate_id/revision、segment_ids、module、run/attempt_no、confidence来源/校准版本 | 候选覆盖，不等于展示 |
| suggestion.shown | 候选真实进入审校可见区域；candidate_id、candidate_revision、content_hash、reviewer_id、variant_key、language、UI展示证据/来源 | 接受率分母；未展示影子输出不发 |
| review.submitted | 编辑主体保存并提交当前成果；task_revision、segment/variant/revision、候选Ref或null、submitter_id、operation_id、expected_revision | 只表示编辑完成/待审，不计审核通过/接受；失权或旧版提交拒绝，模型产出可由实际Run/候选记录交接，不伪造人类提交 |
| review.decided | 人工决定存储成功；decision_id、candidate/revision、reviewer_id、accept/edit/edit_accept/reject/skip/escalate、before/after引用、reason、parent_operation_id | 批量拆成每candidate决定；只有事务成功项计数 |
| review.blocked | 写入前校验阻断或保存失败；operation_id、batch_id、candidate/input_revision、reason_code、permission/version检查引用、outcome=skipped/failed；没有成功决定时decision_id为null | 批量逐项反馈；不发review.decided、不计接受成功 |
| review.reverted | 撤销/回滚成功；原decision_id、恢复目标修订、新decision_id、reason | 撤销结局和人工返工；不删除旧事件 |
| human.activity | 审校活动区间；session_id、actor_id、task/module、interval_start/end、active_ms、idle_ms、waiting_ms、activity_type、计时规则版本 | 人工时间；原始区间用于同人并发去重，不只存总和 |
| task.wait_changed | 进入/退出等待；wait_id、reason、external/internal、start/end、批准人 | TAT外等及队列，区间并集去重 |
| quality.assessed | 金标/人工评测完成；assessment_id/version、label_version、evaluation_batch_id、gold_item_id/error_id/occurrence_id、segment映射、severity/market、TP/FP/FN或原始匹配、评估层级、仲裁状态 | 风险/术语/实体/语义/边界评估；评估器版本必填 |
| downstream.error_confirmed | 人工确认下游错误；error_id、归因candidate/decision、发生/确认时刻、影响、仲裁人 | 7日有效接受；只凭用户抱怨未仲裁暂列待查 |
| validation.completed | 一次校验结束；validation_id、artifact/revision、profile/validator_version、check结果、首次/重检、blocked/skipped | Schema pass与校验覆盖；跳过不算通过 |
| artifact.generated | 文件存储结束；artifact_id、hash、revision、format、manifest、content时长、run引用、generation_result | 产物追溯、导出一致；不发发布成功 |
| artifact.exported | 当前包经真人签发且各依赖仍有效后，响应真人正式文件请求；artifact_id/hash、task_revision、signoff_decision_id、validation_refs、request_id、真实结果 | 正式导出记录，不等于外部发布；未签/旧签/失败/中断不得发成功事件，读取状态/内部预览不算导出 |
| release.signed | 授权人签发约定就绪；signature_id、签发修订、验证/决策引用、role | TAT终点之一与闸门；不是平台发布 |
| delivery.submitted | 外部人工/授权系统提交被记录；delivery_unit_id、submission_index、artifact、submitted_at、external_request_id | 首次提交分母，不因修补稿重建交付单元 |
| delivery.receipt | 真实外部回执；external_receipt_id、submission_index、technical/content结果、received/occurred_at、return_reason | 平台首轮/准时与7日退回观察 |
| task.closed | 完成/失败/放弃；最终交付状态、closed_at、reason、交付范围 | cohort完整性与未完成计数 |
| permission.checked | 每敏感操作检查；principal/role、action、target revision、authorization_ref（无预授权时null）、allowed/denied、实际write结果、policy_version | 越权尝试/阻断/成功分别统计；已授权不代表输入或质量检查通过 |
| cost.reconciled | 账单对齐；provider_line_id、run/attempt_no/task分摊、币种、汇率快照、含税标记、estimated/settled、allocation_version | 最终成本；迟到账单触发重算 |

上述新增采集辅助字段是Event payload契约，由schema.md公共实体引用；不是新增独立数据库表。字段实现类型与持久化由后续接口/实现阶段明确，不能用同名不同义的客户端计数覆盖服务端事实。

2026-10-20补充：授权/撤销通过既有ReviewDecision及Event记录，动作分别authorize_execution/revoke_authorization，event_type使用authorization.granted/authorization.revoked，payload引用authorization_id、decision_id、task_revision、principal及scope，不纳入字幕review.decided或接受率。中间自动继续复用真实permission.checked、run.started和input_refs链路，不伪造人工接受事件；候选未展示不发suggestion.shown。最终同页审稿与签发仍分别记录review.decided及release.signed，引用同一交付版本，权限分别检查；一次点击并不免除任何检查。

`review.decided`中的accept/edit_accept/reject等是统计结果分类：以schema既有ReviewDecision.action=accept/edit/edit_accept等为动作权威，结合before/after及候选关系推导直接/修改后接受；edit_accept已在动作枚举内，不维护第二套同义动作；skip只记录浏览跳过，不算已审成功。Candidate不可变，修改后接受引用新稿及原候选，不原位改写候选。schema.md的概念记录名与本表事件名不同处，以本表event_type为采集命名权威。

## 3. 可复算要求

1. 事件追加留痕；纠错通过supersedes_event_id/修订事件，原记录不删除。event_id或provider_line_id去重，幂等键只防同操作重复提交，不合并不同人工决定。
2. `suggestion.shown`按候选+修订+模块去重形成任务展示分母；审校人分层使用首次指定责任审校人，转交记录原/新责任及时间，不让同候选多审校人重复抬高总体样本。
3. 每份报告记录report_id、report_revision、as_of、evaluation_batch_id、cohort/filter、指标契约版本、输入事件范围/校验和、缺失/迟到/未满窗数量、计算版本、审批人。
4. 人工决定与后台实际保存成功分开；点击即失败、批量部分成功、权限拒绝不能记接受成功。角色切换演示数据不进真实统计。
5. 费用估算与账单结算分列；计费重试、失败和取消费用不能丢弃。单个共享调用总分摊不得超过原费用且不得漏分。
6. 日志缺失、采集延迟或评估覆盖不足生成数据质量问题；先解决采集问题再解释模型退化。指标报告不自行降低规则、解除人工锁或推动发布。

## 4. 最小采集验收

首批必须能从一份母版与任务单追溯一次run及attempt_no、候选、展示、人工决定、回滚、验证、文件及人工活动区间；能重算MET-INT/ASR/EFF/REV/GOV/OUT的适用项。其余模块与真实平台回执未接入时明确“不适用/未采集”，不能补Mock冒充真实数据。

计划阶段至少覆盖重复事件、离线晚到、跨任务活动重叠、批量部分成功、换母版、重跑、候选未展示、满7日边界、零分母、账单修订和失败无输出用例。此处只锁验收意图，尚无执行通过证据。

## 首批源语落地准备（2026-10-20）

[首批方案](../07-delivery-plans/source-release-solution.md)、[技术契约草案](source-release-contract.md)、[实施计划草案](../07-delivery-plans/main-delivery-plan-source-release.md)、[正式TC设计](../06-testcase/tc-main-subtitle-workflow.md)。

首批仅收料/任务→转写、核对或对齐→人工源稿审阅→源语导出；174条TC设计全部NOT_RUN，8项实现任务全部阻塞。技术方案及契约是PROPOSED，数据字段仍以schema为权威；采纳扩展须在T0.1先同步权威定义。真实样本、权限、模型/阈值和预算仍待确认；多语模块未纳入本批实现。不把静态检查或合成配方当业务验收。

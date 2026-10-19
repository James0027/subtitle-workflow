# 数据契约 v0.1

> 上游（我引用）：[AGENTS](../../AGENTS.md) §8；[BRD](../01-brd/BRD.md) §2.3、§4；[原型动作](../02-prototype/action-map.md) §2—§4；[规则登记](rule-registry.md)；[指标契约](metrics.md)。
> 下游（引用我）：[V3原型说明](../02-prototype/README.md)；[V3页面清单](../02-prototype/page-list.md)；[样本说明](samples.md) §2—§6；[规则登记](rule-registry.md)；[指标契约](metrics.md)；主子 PRD 待建立。

状态：本轮获授权形成第④步设计基线草案，待评审；**没有真实数据集锁定、建库、接口实现或生产迁移**。已确认底线必须遵守，新增字段/枚举是本项目 v0.1 设计。技术栈未选定，本文类型是逻辑类型，不直接套用参考项目 D1/SQLite。

## 1. 定义、来源与通用约束

- 复用参考工程 `docs/03-foundation/03-03-schema/schema.md` 的字段/类型/必填/关联/唯一约束和变更组织；不复制电商实体、密钥存储方式及数据库选择。
- 字幕课件依据：§0.3.1、§0.5—0.7、§1.5—1.6、§3、§4.1/4.8、§5.2/5.4、附录 A。任务单完整结构为本项目补充，不冒充课件现成 schema。
- 教师讲解：`meeting/week1.txt` 78—94 行强调判断依据、候选保护、追溯及冲突；`week2.txt` 44—56 行强调抽样、变量独立，74—80 行强调识别/工程边界及阈值协商，116—124 行强调规则证据和冲突交人。转写未回听，含错字；课堂案例数量和阈值不是当前实绩。
- 已核对 work 知识索引及 01素材入库、13联合梳理、20说明型原型；旧原型记录不取代本轮新授权，原型本轮保持原状。
- `Task` 是业务任务单；`Run` 是某模块的一次执行。课件 §4.1 用 task_id 表示一次执行，本项目将该含义映射为 run_id，避免与业务任务单混用。
- `id`/外键为不透明非空字符串，例子前缀仅可读示例，不规定 UUID 生成器。不同实体 ID 不可互换。
- `timestamp` 为UTC RFC3339并保留毫秒精度（如2026-10-19T08:00:00.000Z）；媒体时间为相对母版的非负整数毫秒，区间 `[start_ms,end_ms)`；不以显示帧码作存储主值。
- `int`、`number`、`bool`、`string`、`array<T>`、`object` 为逻辑类型。金额用十进制定点字符串并带 currency；duration/latency 明示 ms；空值不等于零或成功。
- 表中“必填”指对象建立时必填；“条件”见同格。缺失值用 null 并记录 missing_reason（unknown/not_provided/not_applicable/unavailable），禁止用空串、0、伪造置信分替代。
- 所有持久对象共有 `schema_version:string`、`created_at:timestamp`、`created_by:string`；可变投影增加 `updated_at:timestamp`、`revision:int>=1`。这里的 created_by 可能是服务身份，审核身份必须另验权限。
- `project_id` 是权限隔离边界，非目录路径。所有外键须同项目；主体账户由未来身份接口提供，本文仅保存 actor_id 与执行时角色快照。
- 引用统一 `Ref={entity_type:string,entity_id:string,revision:int|null}`；有内容修订的对象引用必须有 revision。数组中的 Ref 不得引用不存在对象。

## 2. 关系与版本

`Media 1:N Asset；Task N:1 Media；Task 1:N Run；Media 1:N Segment；Segment 1:N Candidate；Run 1:N Candidate/Issue/Validation；Candidate 1:N ReviewDecision；Task 1:N Artifact/Event`。

- `media_id` 唯一标识一个不可变母版；换剪辑、画面或母版声音必须新建 media_id，并用 supersedes_media_id 关联旧版。重复上传相同文件不自动建立新母版。
- Asset 原件不覆盖；转码/提取/脱敏另建 asset_id。checksum 相同只说明字节相同，不证明脚本/字幕语义对应；不得据此跳过人工错版核对。
- Task 的每次业务定义修改生成不可变 task_revision 快照；Run、Artifact 引用确切快照。运行中的旧版不自动改绑，新版需重新判定就绪。
- Segment 身份不随文字/时间修订改变；拆分/合并新建 ID，记录 parent_segment_ids 与 operation。旧 ID 退役保留，禁止把多个事件偷偷复用同一 ID。
- `Segment.revisions[]` 与 `Candidate` 追加保存；`Segment.current_revision` 是受控指针。确认稿不可被 Agent 原位更新；人工改稿生成新修订并使受影响校验/签发失效。
- 乐观并发：保存/采纳须提交 expected_revision；与当前不符写 STALE_INPUT 失败事件，保留旧候选，不自动覆盖或合并。
- 幂等：Run.idempotency_key 由 task_id + task_revision + module + segment_id/范围摘要 + input_revision + target_variant_key + manifest_hash 组成。相同 key 最多一个有效结果组；重试用 attempt_no 留痕。
- 同时处理多个目标时按 `target_variant_key` 分开，不能把英语不同市场混成同一候选；一个运行可产多候选，但 `(run_id,segment_id,target_variant_key,candidate_kind,candidate_index)` 唯一。
- `Task.target_variants[].variant_key` 与 Candidate/Run 的 `target_variant_key` 是同一分支键值；前者是任务内定义，后者是引用；Segment/Event的variant_key也引用此键。任何Ref指向Segment修订时另带variant_key，不能仅凭revision定位目标分支。

## 3. 入库与任务单（首批详细）

### 3.1 Media：母版确认记录

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| media_id / project_id | string/是 | 主键；项目边界 |
| title_id / episode_id | string/是 | 作品、集数稳定业务标识；未知时只能登记待补素材，不确认母版 |
| master_video_asset_id | string/确认时 | →Asset，kind=video，属于同一母版 |
| primary_audio_asset_id | string/确认时 | →Asset，可为独立或从视频提取；有声不等于听写可用 |
| duration_ms | int/确认时 | >0；源自检测，不把示例时长当真实结果 |
| frame_rate | object/确认时 | numerator/denominator:int>0；timecode_mode=cfr/vfr；VFR保留真实时间基准 |
| master_status | enum/是 | REGISTERED/NEEDS_REVIEW/CONFIRMED/RETIRED |
| match_checks | array<object>/确认时 | asset_id、check_type、result(pass/fail/unknown)、method、checked_by、checked_at、evidence_refs；含片名/集数/剪辑/音轨/脚本版本 |
| confirmed_by / confirmed_at | string,timestamp/确认时 | 人工或授权业务确认主体，Agent 不可冒充 |
| supersedes_media_id | string/null | →旧Media；换母版不覆盖旧对象 |
| content_dimensions | object/是 | genre:string\|null、rating:string\|null、content_type:live_action/animation/other/unknown、dialogue_density:number\|null；每个测量带method/version |

### 3.2 Asset：收到什么，以及文件可否使用

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| asset_id / project_id | string/是 | 主键及权限边界 |
| media_id | string/条件 | →Media；未核定对应关系时null，不强绑猜测 |
| kind | enum/是 | video/audio/subtitle/script/character/terminology/style_guide/other |
| origin | enum/是 | supplied/extracted/generated/redacted/reference；人造缺失另记样本变体，不伪装原配 |
| source_uri / rights_ref | string/是 | 受控存储引用与授权证据；禁止日志暴露带签名URL、用户绝对路径或凭据 |
| checksum_sha256 / size_bytes | string,int/是 | 64位十六进制与>=0；原件校验值不可改写 |
| mime_type / supplied_version | string/是, string/null | 类型与提供方标注版本；提供方未知须明示 |
| parent_asset_ids / transform | array<string>,object/null | 派生时必填父Asset及工具版本、参数摘要、run_id；原配父数组为空 |
| availability | enum/是 | received/readable/unreadable/quarantined；不存在的附件在Task缺项表登记，不造空Asset |
| inspection | object/条件 | 实测后：checked_at、tool_version、duration_ms、channels、sample_rate_hz、codec、sound_present:bool\|null、snr_db:number\|null、clipping_ratio:number\|null、overlap_ms:int\|null、music_ratio:number\|null、measurement_status |
| privacy | object/是 | classification:public/internal/restricted、redaction_status、allowed_purposes:string[]、external_processing_allowed:bool、retention_policy_ref:string\|null |

### 3.3 Task：母版要做什么、给谁、输出什么

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| task_id / project_id | string/是 | 业务任务单主键；同项目幂等提交避免重复任务 |
| task_revision / request_key | int,string/是 | 修订>=1；同项目request_key唯一，重复请求返回原结果 |
| media_id / parent_task_id | string/确认时,string/null | →确认Media；源语先行子任务显式关联原全局任务 |
| task_type | enum/是 | source_only/multilingual；不以目标字段空值猜测类型 |
| purpose / owner_id | string/确认时 | 用途及负责交接的人；人确认，代码检查缺项 |
| source_locale | string/确认时 | BCP47；与实测识别不符产生Issue，不静默改写 |
| processing_route | enum/确认时 | transcribe/align_existing/verify_existing；已有字幕不强行重做ASR |
| input_asset_ids | array<string>/确认时 | →Asset，含实际选用音轨及可用附件；原稿和参考答案角色分开 |
| range | object/确认时 | mode:whole/ranges；intervals:[{start_ms,end_ms}]；范围不越母版且不重叠，whole由实际duration解释 |
| target_variants | array<object>/条件 | multilingual至少1项：variant_key、target_locale、market_codes:string[]、audience、rating、regulatory_pack_ref、platform_profile_ref；target_locale不能代替市场 |
| target_scope_status | enum/是 | specified/not_applicable/pending；source_only须not_applicable并写reason，multilingual确认须specified |
| output_spec | array<object>/确认时 | variant_key(source_only为source)、format:srt/vtt/ttml/imsc/other、purpose、platform_profile_ref:{id,version}\|null；空profile仅限明确非平台验收的源语交付并注明 |
| delivery_units | array<object>/确认时 | delivery_unit_id、title_id、episode_id、media_id、variant_key、market_code、profile_id/version或明确not_applicable、range_hash、due_at:timestamp\|null；组合唯一标识交付项；多集不可只按title合并 |
| module_plan | array<object>/确认时 | module:六模块枚举、applicability:required/not_applicable/deferred、reason；未判断不等于不适用 |
| missing_items | array<object>/是 | name、reason、blocking_stage、owner_id、resolution_status:open/resolved/waived、resolution_ref；无脚本不统一阻断 |
| readiness | array<object>/是 | stage、status:pending/ready/blocked、checked_at、validation_ids、reason_codes；ASR就绪不代表多语全局就绪 |
| task_status | enum/是 | DRAFT/NEEDS_INPUT/READY/IN_PROGRESS/WAITING_REVIEW/BLOCKED/COMPLETED/CANCELLED；由实际交接投影，非Candidate状态 |
| confirmed_by / confirmed_at | string,timestamp/确认时 | 确认准确快照；修改目标/范围后原确认不沿用 |
| ready_at / completed_at | timestamp/null | 实际阶段事件投影；禁止预填完成时间 |

`audience={description:string,age_group:string,decision_ref:string}`；评级和受众不能靠模型推定。未知市场/规范不伪造版本，保持pending并阻断依赖该条件的阶段。完整多语任务未定义目标时，可另建经授权source_only子任务，不把原任务标成全局READY。

## 4. 字幕、候选、运行与问题

### 4.1 Segment 与不可变人工修订

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| segment_id / media_id / project_id | string/是 | 主键及外键 |
| sequence_no / parent_segment_ids / operation | int,array<string>,enum/是 | 展示序号可变不作ID；operation:original/split/merge |
| current_revision | int/是 | 源语分支当前修订；目标分支由branch_heads定位，不能用此字段覆盖所有语言 |
| branch_heads | array<object>/是 | {variant_key,locale,current_revision}；(segment_id,variant_key)唯一；源语variant_key=source |
| revisions | array<object>/是 | revision、locale、variant_key、source_text、final_text:string\|null、start_ms、end_ms、origin、source_refs、author_id、created_at、decision_id\|null、lock_state、locked_by\|null、locked_at\|null；(segment_id,variant_key,revision)唯一；并发校验限定分支 |
| review_state | enum/是 | 源语分支投影UNREVIEWED/HUMAN_APPROVED/MANUAL_LOCKED/NEEDS_REVIEW/RETIRED；各branch_heads同时保存对应review_state；与技术校验及发布状态独立 |
| speaker | object/是 | speaker_id:string\|null、speaker_count:int\|null、is_voice_over:bool\|null、overlap_ms:int\|null、evidence_refs；未知身份不可强配角色 |
| source_spans | array<object>/是 | asset_id、start_ms、end_ms、text_span\|null、source_revision；跨来源一一指向 |

修订对象 `origin=supplied/ai_accepted/human_edit/human_created`；`lock_state=unlocked/human_approved/manual_locked`。确认前final_text允许null；已确认后必须非空或有经人工明确的省略决定。数字、否定、专名保护信息由证据/检查记录关联，不仅依赖一段自由备注。

### 4.2 Candidate：不覆盖终稿的建议版本

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| candidate_id / task_id / run_id / segment_id | string/是 | 主键及对应外键 |
| candidate_revision | int/是 | 固定1，候选内容不可变；后续内容新建candidate_id并记录supersedes_candidate_id |
| input_revision / target_variant_key | int,string/是 | 本建议基于哪版输入、哪个目标，禁止“最新版本”模糊引用 |
| module / candidate_kind / candidate_index | enum,enum,int/是 | module见§5；kind:text/timing/risk_tag/unit_change/readability_tag；index>=0 |
| proposed | object/是 | text:string\|null、start_ms/end_ms:int\|null、labels:string[]、rationale:string；按kind至少有相应有效字段 |
| candidate_status | enum/是 | AI_PROPOSED/ACCEPTED/EDITED_ACCEPTED/REJECTED/ESCALATED/SUPERSEDED；首态AI_PROPOSED；校验/发布不塞入此枚举 |
| confidence | object/是 | raw_score:number\|null、calibrated_score:number[0,1]\|null、calibration_version:string\|null、calibration_bucket:string\|null；无校准不伪装正确率 |
| evidence / term_hits | array<object>/是 | 证据结构见§4.4；术语命中含term_id、version、source_span、required_form、observed_form、result |
| supersedes_candidate_id / content_hash | string/null,string/是 | 新候选指向被替代者；不可原位修改已展示候选内容 |

### 4.3 Run：执行快照与失败也是产物

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| run_id / task_id / task_revision / trace_id | string,string,int,string/是 | 主键、任务快照、全链相关ID |
| module / input_refs / input_revision | enum,array<Ref>,int/是 | 入库检查可用module=ingest；六处理模块见§5；批处理每个input_ref带revision |
| idempotency_key / attempt_no | string,int>=1 | run_id在同配置重试中保持不变；attempt_no是最新尝试的投影；新配置/人工重跑另建Run并可记supersedes_run_id；有效结果组只投递一次 |
| attempts | array<object>/是 | 每次尝试含attempt_no、started_at/ended_at、status、failure、steps、usage、output_refs；(run_id,attempt_no)唯一；不得只保留最后一次以丢失失败与费用；初次与重试停止解释以规则登记为准 |
| run_status / stop_reason | enum,string\|null | READY/RUNNING/SUCCEEDED/FAILED/STOPPED/WAITING_HUMAN/SKIPPED；仅确定不适用才SKIPPED，须理由 |
| context_manifest / manifest_hash | object,string/运行前 | schema_version、model/provider/version或not_used、prompt_id/version或not_used、术语/角色/风格/市场包/profile各{id,version,checksum,status}、输入素材校验值、代码/工具版本、规则集版本、校准版本；缺失明确标记 |
| steps | array<object>/是 | step_id、name、actor_type:code/model/human、input_refs、output_refs、status:pass/fail/skip/waiting、started_at、ended_at、error_code\|null、tool_version\|null |
| started_at / ended_at | timestamp/null | 真正开始/结束时写；耗时从时间或单调时钟实测 |
| usage | object/是 | latency_ms:int\|null、input_tokens/output_tokens:int\|null、cost_amount:string\|null、currency:string\|null、cost_status:actual/estimated/unavailable、billable_call_id:string\|null；未知费用不是0 |
| controls | object/是 | budget_policy_ref:string\|null、budget_scope_id:string\|null、spent_amount:string\|null、consecutive_retry_count:int、stop_reason:string\|null、resume_decision_ref:Ref\|null；数值与计次策略待规则确认 |
| output_refs / failure | array<Ref>,object\|null | failure含code、category、retryable:bool、redacted_detail、owner_role；空输出不伪装SUCCEEDED |

### 4.4 Issue：风险、证据及冲突

| 字段 | 类型/必填 | 约束与含义 |
| --- | --- | --- |
| issue_id / task_id / run_id | string/是 | 问题主键及外键；人工发现run_id可null但origin=human必填 |
| segment_id / candidate_id / affected_revision | string\|null,string\|null,int/条件 | 指向实际受影响版本；素材级问题可无segment但须asset_ref |
| category / severity / confidence | string,enum,object/是 | severity:P0/P1/P2/UNASSESSED，置信与影响严重性分轴；类别词表按规则登记 |
| market_codes / scope_ref | array<string>,Ref\|null | 文化问题必须确定适用市场，未知显式待补不作红线结论 |
| trigger_spans / evidence | array<object>/是 | evidence项：evidence_id、kind:source/rule/term/external/human、source_ref或citation、rule_id/version\|null、locator、retrieved_at、valid_from/until\|null、applicability、note；不得只放无法定位URL |
| rule_hits | array<object>/是 | run_id、segment_id\|null、input_revision、rule_id、rule_version、result、scope、parameter_version、evidence_ids、expected_action、observed_value、threshold_ref；未生效规则不得当硬拦截依据 |
| evidence_status / issue_confirmation | enum,enum/是 | evidence_status:missing/partial/valid/expired/conflicting；issue_confirmation:unverified/confirmed/refuted；确认时须confirmation_decision_id、confirmed_by、confirmed_at；风险线索不是确认事实 |
| conflict | object/null | type:faithfulness_readability/culture_creation/general_market/efficiency_safety/model_term/rule_rule/concurrent_revision；competing_refs、tradeoff_note、resolution_status、resolver_role、decision_id\|null |
| recommended_action / issue_status | string,enum/是 | OPEN/NEEDS_EVIDENCE/ESCALATED/RESOLVED/DISMISSED；推荐不等于已执行 |

P0需要有效市场/触发片段/适用规则及证据；仅模型高分不能自行提升为红线。课件附录A要求P0/P1证据，§4.4允许无证据文化线索最高P1：本项目区分“unverified待核实P1线索”与“confirmed风险”；前者允许证据数组为空但必须missing/NEEDS_EVIDENCE，后者P0/P1必须有有效证据和人工确认引用。疑似严重影响保留在说明中，不因缺证据宣称安全。规则适用性及优先级以规则登记为准。

## 5. 六模块交接骨架

| module枚举 | 读取 | 新建输出与必留信息 | 不允许 |
| --- | --- | --- | --- |
| asr_alignment | 确认母版/任务范围、音轨、可选已有字幕/脚本 | Segment/Candidate(text/timing)、Run步骤、音质/重叠/专名Issue；chunk音轨区间与母版offset_ms、重叠拼接策略版本；时间戳保留工具来源 | 无声音仍成功；删重叠说话标签；把普通代码描述成已解决真实对齐 |
| translation | 确认源修订、目标variant、局部上下文及锁定术语 | 译文Candidate、term_hits、source_spans、上下文清单与缺项 | 覆盖确认稿；跨市场混用 |
| culture_check | 指定目标修订、市场/受众/评级及规则包 | Issue、证据、严重性与置信分、升级建议；无问题也留检查范围 | 无证据红线；模型擅自净化剧情 |
| unit_format | 数值/单位/剧情上下文及地区政策 | unit_change候选：source_value/unit、target_value/unit、conversion_formula_version、rounding_policy_ref、exception_reason | 不看语境自动换算；擅自改汇率/日历 |
| oral_review | 目标稿、显示时间、角色风格、阅读规则 | readability_tag及可选候选；CPS/字符数/词数与分词版本、语义保护项 | 计数通过就宣称语义自然；直接改锁定稿 |
| compliance | 确认稿精确修订、输出规格/profile | Validation、Artifact，错误定位与规则版本 | 把校验通过或生成文件写成已发布 |

同一module可只跑代码/模型/人工中的必要部分；context_manifest明确not_used，不能为凑齐字段虚构一次模型调用。输入稿变更后的影响分析保留旧结果，仅新建复检，局部修复由人触发的语义分支须有决定引用。

## 6. 决策、校验、交付与采集

| 对象 | 必填字段（逻辑类型） | 条件及约束 |
| --- | --- | --- |
| ReviewDecision | decision_id/task_id/actor_id/actor_role/action/reason_code:string；occurred_at:timestamp；target_refs:array<Ref>；before_ref:Ref；expected_revision:int；after_ref:Ref\|null | action=accept/edit/edit_accept/reject/skip/escalate/revoke/rollback/confirm_master/confirm_task/signoff；内容动作关联candidate_id/segment_id；edit仅保存草稿，不确认；edit_accept为人工明确编辑后接受；skip为人工显式跳过，自动阻断不伪装人工决定；编辑必有after_ref；其他动作可目标对象快照替代字幕ref；reason_code不可只留自由文案 |
| ReviewDecision补充 | batch_id:string\|null、supersedes_decision_id:string\|null、undoes_decision_id:string\|null、reason_note:string\|null、permission_check_ref:Ref | 批量按候选拆单决定，共享batch_id；撤销指向原决定；rollback另建新修订且不抹去历史；旧修订冲突的单项失败单记Event，不虚构批量全成功 |
| Validation | validation_id/task_id/run_id:string；subject_refs:array<Ref>；profile_ref:{id,version}\|null；checked_at:timestamp；check_kind:string；result:PASS/FAIL/NOT_APPLICABLE/NOT_EXECUTED；checks:array<object> | checks含rule_id/version、result、observed_value、threshold_ref、locator、issue_id\|null；未执行与不适用区别；最终技术检查绑定每条确认稿和产物校验值；人工修订后旧PASS失效 |
| Artifact | artifact_id/task_id/delivery_unit_id:string；task_revision:int；kind:source_subtitle/target_subtitle/qc_report/delivery_package；format:string；storage_ref:string；checksum_sha256:string；created_at:timestamp；source_refs:array<Ref>；run_ids:string[] | delivery_package引用全部实际交付组成物；原件/候选不混成交付；文件行→segment/revision/variant_key映射必留；无效未验包可另存但标明 |
| Artifact状态 | delivery_status:DRAFT/QC_FAILED/VALIDATED/PUBLISH_READY/PUBLISHED；validation_ids:string[]；signoff_decision_id:string\|null；external_receipt_ref:string\|null | PUBLISH_READY必须有授权人签发及有效校验；PUBLISHED只能记录外部流程真实回执；系统不新增自动发布能力；源语导出不冒称平台已验收 |
| Event | event_id/project_id/task_id/trace_id/event_type/actor_id/actor_type:string；event_at/received_at:timestamp；schema_version:string；metric_contract_version:string；dedup_key:string；subject_refs:array<Ref>；payload:object | 追加不可改，(project_id,event_type,dedup_key)唯一；重送不重复记行为；media_id/run_id/attempt_no/segment_id/candidate_id/issue_id/decision_id/validation_id/artifact_id/actor_role/source_revision/variant_key及model_version/prompt_version/rule_version/profile_version按事件条件必填；记录真实发生时点，晚到可重算；同次人工操作operation_id，多事件不得被当多次操作；Run业务idempotency_key独立于事件dedup_key |

### 6.1 指标原始记录（公式只在 metrics.md）

实际event_type及必填payload以[事件契约](metric-events.md)为准。下表斜线表示相关事件组，不是另造复合事件名。事件时间统一event_at；ReviewDecision.occurred_at表示决定对象的业务发生时刻，派生Event.event_at与其相同。

| 事件/记录 | 必留原始字段 | 防误算约束 |
| --- | --- | --- |
| suggestion.shown | candidate_id、candidate_revision、content_hash、reviewer_id、module、locale、variant_key、surface、event_at | 仅真实可见时生成；刷新不改候选身份，展示与刷新埋点去重按指标契约 |
| review.decided / review.reverted | candidate_id、decision_id、action、before/after_ref、undoes_decision_id、reviewer_id、event_at | 区分直接/修改后接受及撤销；批量拆回单条，不只留batch计数 |
| human.activity | session_id、actor_id、task_id、module、activity_kind、started_at/ended_at、active_ms/idle_ms/waiting_ms:int\|null、idle_policy_version、measurement_status | 编辑/新增复核/返工分类互斥，纯模型/排队等待另记wait_interval；未知active_ms不填0；会话重叠处理由指标契约定义 |
| downstream.error_confirmed | issue_id、error_id、occurrence_id、affected_candidate_ids、origin_decision_ids、confirmed_by、confirmed_at、severity、resolution_ref | 只有被确认且能归因的错误关联；未发生错误事件不等于观察窗口完整 |
| task.ready / validation.completed / artifact.generated / delivery.receipt | readiness阶段时间、范围总时长ms、待料/排队区间、validation_id、attempt_no、artifact_id、task_revision、delivery_unit_id、external_receipt_id、submission_index、submitted_at、accepted_at | 外部回执实际关联交付项及文件版本；submission_index>=1；首轮/最终、源语/多语、失败/放弃独立留痕；不得按文件行数替代建议/错误分母 |
| quality.assessed | dataset_id/version、sample_id、gold_item_id、label_version、run_id、error_id、occurrence_id、prediction_ref、match_result、evaluator_version、assessment_version | 同一错误项多个标签不重复金标分母；匹配策略按样本说明与指标契约固定 |

## 7. 六维与冲突检查

| 课件六维 | 数据承载 | 可检查/统计的证据（定义见指标契约） |
| --- | --- | --- |
| 正确性 | source_spans、修订、专名/数字/否定Issue、金标 | 文字错误、关键实体错误、时间偏差；无金标不声称准确 |
| 可读性 | 毫秒边界、字符/词数、分词版本、profile规则 | CPS/行长/时长违规，保留忠实与压缩冲突 |
| 文化与法律 | target_variants、rating、Issue.severity/confidence/evidence | 市场分桶漏检、证据缺失、升级；严重性不等于置信分 |
| 可交付性 | Validation精确版本、Artifact checksum/profile/signoff | 首轮/最终检查、交付回执；生成不等于验收/发布 |
| 可治理性 | Run manifest、Ref、Event、ReviewDecision及权限结果 | 追溯完整、并发拒绝、人工稿保护；历史不可抹去 |
| 效率 | 展示/决定/撤销、human_activity、返工及等待 | 完整人工时间、接受与提示负担；模型等待不能混人工 |

五类业务冲突逐项保留 competing_refs 与人工决定：忠实/可读→源片段+压缩候选；文化/创作→创作说明+规则；通用/市场→两条规则scope/version；效率/安全→阻断及停止原因+人工耗时；模型/术语→锁定词版本+命中差异。另记录同级规则矛盾、并发修订冲突，不能把后者伪装成模型质量问题。

## 8. 待确认与锁定变更

待确认：首批语种/市场/profile与受众范围、真实身份角色映射、存储/保留期限、说话人识别能力、ASR工具时间基准与校准、批量部分成功交互、预算计次边界、实际字段序列化。未确认前不使用课件阈值自动放行。

评审后给 schema_version 固定版本；改字段类型/枚举/语义需影响分析，关联规则/指标/原型/PRD/用例及样本版本。兼容新增可选字段亦记录变更；删除/复用旧ID或改历史事件含义须迁移方案。本文写出约束不代表服务端已经实现。

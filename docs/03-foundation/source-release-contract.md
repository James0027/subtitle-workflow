# 首批源语技术契约草案

版本：v0.2｜日期：2026-10-21｜状态：PROPOSED，待技术/业务基线冻结；不是已实现API/生产DDL。

> 上游（我引用）：[落地方案](../07-delivery-plans/source-release-solution.md)；[schema](schema.md)；[规则](rule-registry.md)；[事件](metric-events.md)；[01/02/07/08/09/10子PRD索引](../05-prd/README.md)。
> 下游（引用我）：[实施计划](../07-delivery-plans/main-delivery-plan-source-release.md)；[正式TC](../06-testcase/tc-main-subtitle-workflow.md)。

## 1. 权威与范围

schema继续拥有实体字段/枚举，规则登记拥有执行条件，metrics拥有公式。本文明确首批的传输和落库映射建议，不静默修改共同定义。新增动作/序列化经T0.1评审后才进入对应权威文件及实现。

现有代码无端点或持久化实现。以下方法/路径是可评审的首版设计，测试通过能力名称引用它；最终绑定地址/序列化未冻结前，不伪造可直接curl成功的URL。

## 2. 身份、通用请求与返回

主体和actor_type/角色从可信鉴权上下文获得，禁止相信前端提交的actor_role或X-Actor-Id。测试可以注入明确标记的合成主体，但测试入口必须隔离、默认禁用，不能处理真实授权/签发。服务主体不持有人类审阅会话凭据；运行模块无confirm_master/confirm_task/最终内容确认/签发权。

写请求带请求关联标识及相应expected_revision；Task首次创建使用schema的request_key。服务端计算真实业务幂等键；Event.dedup_key只防事件重送，不能代替执行防重。同请求标识配不同内容返回冲突，不吞掉新意图。

建议返回壳为request_id、结果对象Ref/实际状态；失败给error.code、可展示reason、缺项/受影响范围和当前版本。接受执行返回受理及Run，不返回伪造候选。原始堆栈/凭据/其他项目对象信息不对外返回。

| 传输结果 | 建议HTTP语义 | 业务含义 |
| --- | --- | --- |
| 同步读取/保存成功 | 200；实际新建对象可201 | 保存完成才更新界面 |
| 真实执行已受理 | 202 | Run可查询，尚不是SUCCEEDED |
| 结构/输入不合法 | 400或422，最终错误表在T0.1固定 | 非法字段与阶段缺项明确区分，不先建成功运行 |
| 无动作权限 | 403 | 敏感动作未执行；跨项目对象读取统一不可见，不泄露存在性 |
| 不存在/不可见对象 | 404 | 不返回他项目标题/文件地址 |
| 旧版本/同键不同请求 | 409 | STALE_INPUT或请求内容冲突，保留待提交编辑 |
| 工具/存储暂不可用 | 503或异步Run实际FAILED | 请求受理后失败由Run报告，不伪装同步成功 |

## 3. 能力与建议端点

`/api/v1`为待冻结前缀；GET查询绝不隐式重跑。以下资源均先检查项目归属、对象可见性和动作权限。

| 能力ID | 建议方法/路径 | 关键请求 | 结果与PRD |
| --- | --- | --- | --- |
| SRC-ASSET | POST /projects/{project_id}/assets | 文件/受控已有引用、来源及使用授权；接收防重关联 | 实际Asset/可用性；01§3 |
| SRC-MASTER | POST /media/{media_id}/confirm | 当前选用视频/声音/附件、检查Ref、expected_revision | 人工confirm_master决定；绑定已创建的稳定Task草稿，01§3 |
| SRC-TASK | POST /tasks；PATCH /tasks/{task_id} | schema任务定义；request_key或当前expected_revision | 草稿/新task_revision；01§4 |
| SRC-CONFIRM | POST /tasks/{task_id}/confirm | 确切快照及母版；真实人类确认 | confirm_task决定和确认字段；01§4.3 |
| SRC-READY | POST /tasks/{task_id}/readiness | stage、Task/输入引用 | readiness及missing_items，不代替执行权限；01§5 |
| SRC-CONTEXT | 内部resolve_context能力；传输形式待冻结 | Task/模块/输入范围、资料/规则Ref与可信主体 | 有来源的最小资料集、待固定manifest片段/缺项/冲突；09，不自行创建Run |
| SRC-AUTH | POST /tasks/{task_id}/authorizations；POST /authorizations/{id}/revoke | principal、Task修订、modules/actions scope、原因 | 实际授予/撤销决定；10§5 |
| SRC-RUN | POST /tasks/{task_id}/runs；GET /runs/{run_id} | 模块、路线、输入/范围、manifest及许可Ref | 202受理/查询attempt、steps、结果；02/10 |
| SRC-REVIEW | POST /review-decisions；POST /review-batches | 既有action、候选/片段分支Ref、expected_revision、原因 | 逐项成功/拒绝、决定/新修订；08§3—5 |
| SRC-HISTORY | GET /segments/{id}/revisions；POST /segments/{id}/rollback | variant及历史/当前Ref、原因与权限 | 历史/新修订及受影响清单；08§6 |
| SRC-EXPORT | POST /tasks/{task_id}/exports；GET /artifacts/{id}/file | 确切确认稿/交付项、输出规范、所需许可 | 内部校验/生成/解析结果；GET正式文件必须当前有效真人签发与下载权；07§3—5 |
| SRC-TRACE | GET /tasks/{task_id}/trace | 当前授权范围内过滤条件 | 输入→Run/attempt/step→候选/决定→文件；10§8 |
| SRC-SIGNOFF | POST /artifacts/{id}/signoff | 当前包/hash、内容决定/检查与实际人类主体 | 所有正式源语/目标语导出必需；真人绑定当前包/hash；07§5 |
| SRC-EXTERNAL | 后续外部事实记录能力，路径未冻结 | 准确包/提交序号、来源、真实外部结论 | 07§6；无自动发布接口，成功回执用例为OPTIONAL_SHARED |

首批正式导出必须真人签发；外部提交回执仅按后续实际接入记录；本方案不增加自动发布端点。跨项目拒绝在实际调用/写入前发生，不只在页面隐藏。

## 4. 不可变内容和草稿读取建议

| 场景 | 建议映射 | 冻结要求 |
| --- | --- | --- |
| Task修改 | 新task_revision；Run/Artifact仍指原快照；确认不跨定义修订继承 | request_key仅作创建防重；修改并发按当前修订判断 |
| 保存编辑/提交审核 | 追加Segment修订，当前编辑头指新稿，review_state=NEEDS_REVIEW；历史确认稿保留 | 编辑区保存可继续编辑，保存并提交时edit与review.submitted绑定当前修订；审核区另以审核权限确认，不能以提交冒充已审；不得自动用历史确认填当前导出 |
| 明确确认编辑稿 | 有权人对当前稿操作，按现有edit_accept保存；有Candidate才更新相应候选状态 | 无Candidate人工稿以Segment Ref绑定，不造candidate_id；业务映射已按用户确认统一；物理序列化在T0.1确定 |
| 人工稿保护 | 工具/Agent只能另建Candidate，不能改HUMAN_APPROVED/MANUAL_LOCKED正文 | 所有写入口及批量逐项检查，不靠Prompt提醒 |
| 锁定/解锁 | 保护行为必须满足；独立lock/unlock动作未在现有枚举中 | T0.1若采用须更新ReviewDecision枚举/事件筛选并测试；冻结前不实现无审计切换 |
| 回滚/拆并 | 回滚另建修订；拆并新Segment ID和父引用 | 查依赖列受影响候选/问题/检查/文件，当前版本不能借旧PASS或签名 |

这是一种可评审的读取/写入方案，未证明实际事务已实现。若选择另存草稿头，应先调整schema及读写/导出用例，不允许实现中临时保存两个含义不清的“当前稿”。

## 5. 文件、媒体和manifest的具体承载建议

| 内容 | 既有对象/承载 | 建议结构及验证 |
| --- | --- | --- |
| 原件/抽轨/切块 | Asset、parent_asset_ids、transform及Run输出Ref | transform保留工具/版本/参数；块记录源Asset、母版[start_ms,end_ms)、offset_ms和拼接策略版本，实际序列化在T0.1固定 |
| 字幕输入 | Asset+解析后Segment/source_spans | 已有稿的文字/时间对应来源可查；原文件不覆盖；无时间稿粗窗口缺失不可硬均分冒充对齐 |
| 导出行映射 | Artifact.source_refs及受控映射附件引用 | 版本化JSON附件含实际文件checksum、cue/行范围、segment/variant/revision与允许变换；每条可反向定位，不能只存一组段ID |
| 解析比较 | Validation.subject_refs/checks及文件hash | 逐cue核文字/时间/顺序/所需样式；不支持的样式显式失败或经任务变更批准，不静默丢弃 |
| manifest/key | Run.context_manifest/manifest_hash、idempotency_key | 建议UTF-8、JSON键排序、无多余空格、禁止NaN/Infinity、十进制费用字符串；集合项固定排序/有序上下文保留顺序；不擅自改源文Unicode/标点 |
| 真实回执 | Event.payload/subject_refs和external_receipt_ref | 包/提交序号、来源、外部结论、发生/收到时间；引用已有事件不新造回执表；更正追加关联事件，冲突待核实 |

新增附件只在实际生成后登记，使用schema已有kind=other及受控来源/派生关系；不为例子生成真实字幕或媒体。JSON结构是序列化建议，不冒充已发布schema版本。事件更正、映射附件与Artifact引用的确切序列化须T0.1冻结。

## 6. 事务、执行与恢复的要求

| 提交点 | 同一逻辑提交应保证 | 失败/竞争 |
| --- | --- | --- |
| 人工确认/修订 | 权限/expected_revision、内容投影、决定和待投递事件一致 | 存储失败不产生成功决定；重送只返回原操作结果 |
| 授权/启动 | 检查当前授权状态、Task版本/停止、领取运行和在途预算 | 撤权先提交后，不允许缓存许可启动新动作；人工检查通过不生成假授权 |
| 结果写入 | attempt结局、输出Ref、实际费用/估算及唯一有效结果组 | 晚到/取消/旧版结果保留但不推进；不能重复投递 |
| 导出/签发 | 校验绑定当前内容/文件hash，确认/签发各有实际主体 | 并发改稿使旧请求冲突，不能签新稿沿用旧检查 |

若采用SQLite，建议单工作者和短写事务，模型调用/媒体处理在事务外，使用持久Run而非内存队列作为事实来源。事务内失败/SQLITE_BUSY须显式处理；重启查询真实运行结局，未知则WAITING_HUMAN。跨币种/未知预算、连续计次/恢复政策未配置时禁收费自动路线；具体控制算法/物理表由T0.1冻结。

## 7. 可观察证据与尚缺条件

正式TC通过能力ID调用适配后的测试接口，查实体/修订、ReviewDecision、Event、Run及模拟工具调用次数；UI用例另查按钮反馈和页面数据，不能以UI截图代替执行端拒绝。

真实身份鉴权、样本许可、首批语种/格式、模型/权重与运行环境、预算/计次、锁定/确认映射及序列化仍是开工前条件；具体位置见[实施计划T0.1](../07-delivery-plans/sub-delivery-plan-source-release-T0.1-baseline.md)。未知项留显式阻塞，不默认全权/无限预算，也不将测试注入主体作为生产身份。

## 2026-10-21确认的请求与读取约束

创建Task返回稳定ID及DRAFT，缺少尚未确认的母版/输出允许待补；仅受权ingest准备可在确认前建立Run，派生transform必须指向该Run。SRC-REVIEW的edit保存正文；请求明确submit_for_review=true时，同次保存/提交追加review.submitted，Task/Segment修订与权限复查不可少；模型生成完成仅留真实Run/候选，不伪装人类提交。审核使用独立权限的accept/edit_accept，编辑主体不得自授；无Candidate稿引用真实Segment。SRC-EXPORT的POST仅准备内部待交付文件与检查，未签返回状态不返回正式下载地址；SRC-SIGNOFF由真人核对当前全部引用/hash；GET file每次复查签发与对象/动作权限并记录真实artifact.exported结果。内容/规则/Task/包变化或签发撤回后拒绝旧链接，不自动重签。正式导出和外部PUBLISHED回执分开。

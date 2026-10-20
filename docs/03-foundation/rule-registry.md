# 规则注册表 v0.2

> 上游（我引用）：[AGENTS.md](../../AGENTS.md) §3、§8；[AI权限](../../rules/ai-permissions.md) §2；[BRD](../01-brd/BRD.md) §2.3、§4；[动作说明](../02-prototype/action-map.md) §2—4；[数据契约](schema.md)；[指标契约](metrics.md)；外部课件 §0.5—0.7、§1.4—1.6、§3.3、§4、§5、§6.5、附录 A—C；meeting/week1.txt、week2.txt（出处见 §10）。
> 下游（引用我）：[V3原型说明](../02-prototype/README.md)；[V3页面清单](../02-prototype/page-list.md)；[AGENTS.md](../../AGENTS.md) §6—8；[联合基线](README.md)；[数据契约](schema.md)；[样本](samples.md)；[指标契约](metrics.md)；[事件契约](metric-events.md)；主子PRD及首批正式TC已建立，实现未开始。；[主PRD](../05-prd/mainprd.md)（全局目标、状态、权限及验收）；[01子PRD](../05-prd/01-subprd-intake-task.md)（收料/母版/任务与开工）；[功能子PRD索引](../05-prd/README.md)（十份功能规格）

状态：**v0.1 设计定义，待评审；未部署、未配置规则引擎、未完成真实业务验证。** 用户授权联合整理第④⑤⑥步，保持现有原型。锁定指稳定 ID、范围、行为和变更程序，不代表把课件建议数字直接投入生产。

## 1. 权威边界与基本概念

- 四项已确认底线 RULE-SUB-001—004 的文字权威源为 ai-permissions.md §2，本表只细化执行契约，不改编号或削弱要求。
- 本表管理业务/运行规则；字段类型和实体权威源为 schema.md，分母、窗口、去重、统计方法权威源为 metrics.md。不同文档冲突要修订并留痕，不让实现自行挑选。
- Task 指业务任务单；Run 指一次模块执行。课件 §4.1 将一次执行也命名为 task_id，本项目以 run_id 区分，不能混用预算、重试和任务统计边界。
- `HARD` 是确定性阻断约束，`SOFT` 是提示或人工判断；它们不等同于风险 P0/P1/P2。模型自信、提示着色不产生法律事实。`BLOCK` 也必须说明阻断的是调用、修改、交付合格包还是签发。
- AI 输出默认候选；人、代码、模型分工按规则注册，最终权限由服务端控制。规则文件不是运行能力的证明。
- 2026-10-20用户确认：有权人员可预授权中间自动继续，未授权时保留请求授权入口；权限等级后补。预授权不代替必要输入、有效准入/校验、预算和硬阻断，也不代替母版/最终人工确认、签发和锁定保护。授权/检查记录以schema的execution_policy、Authorization和既有permission.checked承接，不另建重复编号。
- 课件 §0.5 是六个思考维度；§0.7 **实际列五类典型冲突**，既不是六类，也不是完整冲突全集。

## 2. 单条规则的完整登记契约

下表是规则条目的逻辑结构，由后续配置/存储实现。不能只有一句 Prompt；不得用缺省 `*` 代表未知市场或未知版本。

| 字段组 | 必须登记内容 | 缺失时 |
| --- | --- | --- |
| 身份 | 稳定 rule_id、不可变 rule_version、标题、所属模块、BRD 功能编号 | 不生效；ID 不因文案变更重用到另一行为 |
| 状态 | DRAFT / APPROVED / ACTIVE / RETIRED；审批人、审批时间、变更原因 | 新规则为 DRAFT，未批准不得进入生产活动集 |
| 来源 | source_kind、来源文档/条款、来源版本、受控快照或摘要 hash、owner、核验时间 | 外部规范缺版本为 EVIDENCE_MISSING，不能当已确认硬规范 |
| 时间 | effective_from、expires_at（允许明确无固定期限并登记复核日）、replaced_by | 未生效不执行；过期不静默继续；P0 范围阻断并升级 |
| 适用范围 | module、task_type、title/episode、source_language、target_language、locale、market、platform/profile_version、rating、content_type、risk_category | 非适用记 SKIP；执行所需维度未知记 NEEDS_CONTEXT，不能当不适用 |
| 规则主体 | condition、参数引用、HARD/SOFT、priority_class、允许动作、禁止动作、阻断位置、reason_code | 不可执行的自然语言歧义交 owner 澄清 |
| 执行与人工 | executor（代码/模型/人）、reviewer_role、escalation_owner、SLA 参数引用 | 无责任人不得启用需人工兜底的自动路线 |
| 证据 | source_span、音/画/字幕受控引用、rule_id/version、market、explanation；适用时 term/conversion/profile 命中 | 明示缺失；不能补造 citation 或 confidence |
| 关联 | metric_ids、requirement_refs、test_refs、implementation_refs | 未建立位置写待建立；规则不得伪称已有用例/实现 |
| 变更控制 | evaluation_report、影响范围、批准、灰度、rollback_to、历史版本 | 未验收的新版本不能替换活动包 |

每个 Run 固定规则活动集快照及 hash；每次命中至少记录：task_id、run_id、segment_id（素材准备可空）、input_revision、rule_id/version、实际 scope、输入证据引用、参数版本、PASS/WARN/BLOCK/SKIP/NEEDS_CONTEXT/ERROR、动作、原因、人工接手人和 Event。字段具体表示遵守 schema.md。

同一 Run 内不热切换规则版本；需改规则时停止当前路线或新建 Run。规则未命中不等于内容无风险，尤其不能把模型未报风险作为已证实安全。

## 3. 优先级、作用域与冲突裁决

以下是依据课件原则形成的 **v0.1 工程设计**，需评审；不能把它解释为市场规定能覆盖权限保护。

1. 先检查授权、已确认稿保护、修订一致性、预算/停止条件。此类系统不变量不能被市场包、Prompt、人工普通操作或效率目标覆盖。
2. 选出时间有效、版本可验证、scope 全部匹配的规则。作用域必需信息缺失先补齐，不能依靠语言猜国家、依靠国家猜语言。
3. 同一输出同时满足所有适用的确定性硬约束；若硬约束无法并存，保持 BLOCK，展示全部冲突并升级。不要用某条优先级删除另一条合法硬约束。
4. 对有权允许覆盖的**同一政策族/同一决策**，先按权威类别：已核验法律/签约平台硬规范 → 生效市场规则 → 项目锁定术语 → 项目风格指南 → 模型偏好。类别来源须有证据；不能自行把普通市场偏好提升成法律。法律和平台硬规范相互冲突，交法务/签约责任人，系统不裁决孰大。
5. 同一优先级动作相反时比较 scope specificity：A 在所有限制维度上的匹配集合均为 B 的子集，且至少一项更小，才称 A 更具体；在明确允许覆盖的政策族内选 A。仅“填写维度更多”不足以获胜。
6. A=特定市场/任意平台，B=任意市场/特定平台，二者不可比较；或相同 scope 动作相反，均生成 RULE_CONFLICT，升级 senior/legal，不能按数组顺序、新版本号大小、模型得分或默认更严来宣称已裁决。
7. 非冲突的约束合并；软建议在硬边界内比较。模型与有效确定性规则不一致时保持规则阻断并保留模型解释，人工复核规则适用性，不让模型消除命中。
8. 保存被选、被覆盖、并存及未能裁决规则的 ID/版本、scope 比较和原因。冲突不重试同配置；补证据或获批准的新规则包后创建新 Run。

示例：特定市场的日期展示偏好可覆盖通用偏好；不能因此覆盖该平台必需的时间码结构。两个市场要求不同要拆目标版本，不能在同一候选上交替改写。

### 3.1 六维覆盖检查

| §0.5 维度 | 必须落实的规则 | 检查的指标方向（公式见 metrics.md） |
| --- | --- | --- |
| 正确性 | ASR、术语、否定/实体、剧情原值、语义保护 | MET-ASR-001/002、MET-QUAL-004、MET-UNIT-003、MET-ORAL-003 |
| 可读性 | 语言/profile 对应 CPS、行长、断句、时长 | MET-ORAL-001/002、MET-ASR-003 |
| 文化与法律 | 市场隔离、证据与分级、红线升级 | MET-QUAL-002/003/005；P0/P1 分开 |
| 可交付性 | 当前修订的结构、时间、glyph 与交付校验 | MET-OUT-001/002/003 |
| 可治理性 | 权限、不可覆盖、版本、幂等、可回滚与双向追溯 | MET-GOV-001/002/003、MET-OPS-001 |
| 效率 | 分层路由、人工负担、任务成本；不得放松质量 | MET-EFF-001/002/003、MET-COST-001/002、MET-REV-004 |

### 3.2 原文五类冲突逐项落实

| 原文冲突 | 决策规则 | 落点与失败处置 |
| --- | --- | --- |
| 忠实 vs 可读 | 剧情关键信息 > 可读性 > 字面完整；硬交付上限仍必须满足 | RULE-ORAL-002；压缩/延时/分句候选；仍不兼容则人工改稿或调整交付，不删否定强行通过 |
| 文化适配 vs 创作表达 | 保留创作意图，展示风险与源语/画面证据，由授权人判断 | RULE-CULT-001/002；不自动净化角色表达；P0 不因保留表达而解除阻断 |
| 统一规则 vs 市场差异 | 生效且适用的市场规则覆盖可覆盖通用偏好 | RULE-GOV-002；市场缺失或不可比 scope 升级，不用目标语言替代市场 |
| 效率 vs 安全 | 红线只允许阻断和升级，不自动静默改 | RULE-SUB-002、RULE-CULT-001；效率收益不能抵消质量/权限约束 |
| 模型建议 vs 术语库 | 锁定术语 > 项目风格指南 > 模型偏好 | RULE-TR-001；冲突展示锁定来源，改术语需新版本审批 |

另检查规则与规则、规则与数据版本、指标收益与质量护栏的冲突；这些是补充工程情形，不改称原文六类。课堂中“术语大于角色大于文化”等口述不能泛化为覆盖法律或 P0 的总排序。

## 4. 注册表阅读方式

所有下表条目包含 §2 的公共元数据。初始 registry 版本为 v0.1；RULE-SUB 条目继承已确认底线，其余为 DRAFT 设计；数值引用 §8 的 PROPOSED 参数。`全局` = 全部已授权任务/模块，但仍须记录实际 scope；市场/平台未知时不能用于文化终审或合格交付。

表内“证据/原因”同时规定最低运行证据与失败原因；检测指标只引用 metric_id，不能以课件建议代替指标契约中的分母或采样。表内用例方向是待实现验收要求，不是已执行测试。

## 5. 全局、治理与素材入库规则

| rule_id / 范围 / 关联 BRD | 类型与执行者 | 条件 → 动作、失败/升级 | 证据/原因、指标、最低用例方向 |
| --- | --- | --- | --- |
| RULE-SUB-001 / 全局 / F-08 | HARD；代码权限+人工采纳 | Agent 企图修改 HUMAN_APPROVED/MANUAL_LOCKED 正文 → 拒绝；只准另建候选。授权人工采纳另建修订，保留原稿 | 输入修订、锁定状态、调用身份、前后引用；LOCKED_WRITE_DENIED；MET-GOV-002；并发旧版写入也拒绝 |
| RULE-SUB-002 / 交付全局 / F-07/08 | HARD；代码闸门+签发人 | 未经人工决策、当前校验或授权真人签名 → 不可正式导出/交付或标 PUBLISH_READY；VALIDATED仅为内部已验文件；系统无自动发布权 | Validation/ReviewDecision/Artifact 的版本绑定；GATE_BLOCKED；MET-GOV-003/002；旧签名不可签新稿 |
| RULE-SUB-003 / 外部规则 / F-09/10 | HARD；代码核验+规则 owner | 来源/版本/适用范围缺失 → NEEDS_CONTEXT；过期或 P0 相关上下文不全 → 阻断对应路线并升级 | 来源快照/hash、版本、有效期；RULE_VERSION_MISSING/EXPIRED；MET-GOV-001、MET-QUAL-005 |
| RULE-SUB-004 / 调用全局 / F-10 | HARD；代码控制+任务 owner | 超已批准任务预算或达到连续两次重试停止条件 → 停止自动调用，保留产物；未配置预算/计数策略不能启动付费自动路线 | 成本账本、attempt、停止原因、人工恢复；BUDGET_STOP/RETRY_STOP；MET-COST-002、MET-OPS-001；见 §7 |
| RULE-GOV-001 / 所有 Run / F-08/10 | HARD；代码 | input_revision 不等于当前受控修订，或已有同幂等键有效结果 → 拒绝旧版写入/复用既有有效结果；失败尝试仍留痕 | Task/Run/Segment/Candidate 与 context hash；STALE_REVISION/IDEMPOTENT_REPLAY；MET-GOV-001；不得多造有效下游候选 |
| RULE-GOV-002 / 规则选择全局 / F-09 | HARD；代码筛选+senior/legal | 按 §3 匹配范围并裁决；未知范围/不可比冲突 → 升级，不重试 | 全部命中与比较轨迹；RULE_CONFLICT/SCOPE_UNKNOWN；MET-GOV-001；交叉 scope 必须进入人工 |
| RULE-GOV-003 / 上下文全局 / F-09/10 | HARD；代码 ACL+人授权 | 跨项目机密、未授权个人信息、无来源论坛意见 → 不注入；合法模型/Prompt/术语/规则版本固定进 manifest | 受控引用、访问拒绝和脱敏记录；CONTEXT_DENIED/MANIFEST_MISSING；MET-GOV-001/002；日志不含凭据 |
| RULE-GOV-004 / 人工决策全局 / F-08 | HARD；代码+有权 reviewer | 接受/编辑/驳回/升级/回滚须身份、reason_code、输入版本；批量按条校验权限与版本，部分失败逐条报告；回滚生成新修订并使受影响旧校验/签名失效 | ReviewDecision、before/after 引用、Event；REVIEW_DENIED/ROLLBACK_REVALIDATE；MET-REV-001/002/003、MET-GOV-002 |
| RULE-INT-001 / 入库 / F-01 | HARD；代码登记+人核对 | 上传只登记 Asset 与检查结果，不自动选母版/建 READY；保留原件、checksum、来源与生成关系；同文件不得误作新剧情样本 | Asset 清单、来源授权、派生关系；ASSET_UNREADABLE/UNAUTHORIZED；MET-INT-001；损坏/错配不得装成功 |
| RULE-INT-002 / 母版确认 / F-01 | HARD；人确认+代码核验 | 核对视频、帧率/时长、可用声音与附件版本关系；换母版新 media_id；脚本/字幕缺失分别登记，不一律阻断 | Media→Asset 对应、确认人、缺失 owner；MASTER_UNCONFIRMED/ASSET_MISMATCH；MET-INT-001 |
| RULE-INT-003 / 任务单 / F-01/09 | HARD；人定用途+代码缺项检查 | Task 必须明确母版、处理范围、源语/声音路线、输出要求与责任；多语任务另明 target locale、市场、受众/评级及平台；纯源语任务目标条件显式不适用，不伪造默认值 | Task 版本/确认决策/适用字段；TASK_INCOMPLETE；MET-INT-001；有视频不能直接进 ASR |
| RULE-INT-004 / 阶段开工 / F-01/02 | HARD；代码门禁+人授权 | 素材准备先建真实Task草稿并以ingest Run记录；仅素材准备可在正式确认前进行。ASR等六模块须已确认任务及当前阶段条件齐备才 READY；没有独立音轨可登记从视频提取；无可用声音不能从零 ASR；已有字幕按核对/对齐任务走。用户可明确创建单模块任务，复用输入/版本/授权检查；缺目标的多语任务不自动降范围或转源语 | Task/Media/Asset 条件、阶段 Validation、授权；STAGE_NOT_READY；MET-INT-001；无任务单不启动，模块就绪不冒充全链就绪 |

入库四条为本项目补充设计，不声称课件给出完整企业 SOP；原文只明确视频/音轨/脚本输入及母版与任务单输出。原始素材质量和授权失败由人处理，代码负责客观检查，模型不承担编号、任务字段完整性和权限校验。

## 6. 六模块规则注册表

### 6.1 ASR / 时间轴对齐

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-ASR-001 / 音轨与来源语种 / F-02 | SOFT质量提示+HARD可用性检查；音频工具/代码+听打人 | 无声/不可读 → 停该识别路线；P-ASR-AUDIO 标 BAD_AUDIO → 请求净轨/人工听打，不自动重写声音 | Asset/音频测量方法与窗口；BAD_AUDIO；MET-ASR-006；§4.2 |
| RULE-ASR-002 / 语种×模型×校准版本 / F-02 | SOFT路由，自动路线启用前 HARD资格检查；代码+人 | P-ASR-CONF 三档；无有效校准/少于建议样本数 → 不启自动放行，转人；高分可路由下一候选阶段，不冒充 HUMAN_APPROVED | 原始分与校准分分存、校准集/版本；UNCALIBRATED/LOW_CONFIDENCE；MET-ASR-005/001/002；§4.2、§4.8 |
| RULE-ASR-003 / 当前母版×platform profile / F-02 | HARD合法性+SOFT同步质量；代码/对齐工具+人 | 负时长/越界按有效 profile 拒绝；偏差按 P-ASR-TIME 提示/人工拖轴；无人工参考不得编造绝对偏差 | 片段时间、参考边界及匹配；ALIGNMENT_REVIEW；MET-ASR-003；§4.2 |
| RULE-ASR-004 / 多人重叠×语种 / F-02 | HARD标签保护+SOFT风险检测；工具/模型+人 | P-ASR-OVERLAP 命中 → 保存 overlap/speaker_count；禁止自动合并说话人；未知身份保持未知；专名未知回查脚本/角色表并待定 | 声音区间、speaker/术语引用；OVERLAP_REVIEW/NAME_UNCONFIRMED；MET-ASR-004、MET-QUAL-004；§4.2、附录 C |

### 6.2 初翻 translation

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-TR-001 / 源目标语言×locale×项目术语 / F-03/09 | HARD锁词+SOFT生成；代码检索/核对+模型+译审 | 基于指定源语修订；先取 locked term；未使用要求译法 → BLOCK该候选；称谓/跨集译法冲突标黄，不由模型选胜者 | source span、term_hits、上次确认 segment/revision；TERM_MISMATCH/CONTEXT_CONFLICT；MET-QUAL-004；§4.3 |
| RULE-TR-002 / 目标语×校准QE版本 / F-03 | SOFT质量评估+HARD关键语义保护；模型+规则+人 | P-TR-QE 路由；数字/否定/实体疑似变动 → 挂问题并复核，确定违背保护则不可下游确认；重译仍受重试限额 | 源句、候选、QE/解释、实体比对；SEMANTIC_MISMATCH/LOW_QE；MET-TR-001；§4.3、附录 C |
| RULE-TR-003 / 局部/剧集上下文 / F-03/09 | HARD溯源+SOFT窗口策略；代码+模型 | 默认当前句前后各2句及相关角色/场景/术语；不整片盲塞；缺 manifest 不进入下游；扩大窗口留新 context hash | manifest、上下文命中；MANIFEST_MISSING；MET-GOV-001；§4.3、§5.2 |

### 6.3 文化 culture_check

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-CULT-001 / market×rating×内容类别×风险类别 / F-04 | HARD证据/红线边界+SOFT模型发现；代码/模型+senior/legal | 规则检索与语境发现双路；P-CULT 建议分档；有效确定性禁项可阻断；模型 P0 必有适用规则与证据；无证据最高 P1且升级；过期/范围冲突/上下文不足交人 | span+rule/version+market+explanation；EVIDENCE_MISSING/CULTURE_BLOCK；MET-QUAL-002/003/005；§4.4/§5.2 |
| RULE-CULT-002 / 同上并含speaker与叙事立场 / F-04/08 | HARD禁止自动改剧情+SOFT解释；模型+本地审校 | 分宗教政治、色情暴力/分级、群体歧视、当地禁忌、法律平台给风险候选；隐喻/反讽/引用保留语境；不净化、不静默改；P0/P1 未决不可签发 | 音画引用、speaker/narrative stance、人工原因；CULTURE_ESCALATED；MET-QUAL-001/002/005、MET-REV-004；§4.4.2 |

无证据 P1 的含义仅是“候选影响最多按黄线待核实”，必须标 EVIDENCE_MISSING，不得当已确认 P1 风险或满足附录 A 的 P0/P1 证据要求。其签发阻断来自“待决/缺证据”治理条件，不能冒充已证实违法。补证后重新判断等级；severity（候选影响）与 evidence completeness（证据充分性）分开。week2 的关键词/正则命中走红线属于课堂简化：必须同时满足规则有效、范围适用和语境证据成立，才可作为确定性红线命中。

### 6.4 单位与格式 unit_format

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-UNIT-001 / market×locale×conversion_policy版本×内容 / F-05 | HARD计算/留原值+SOFT替换；代码换算+模型识别+人 | 识别实体后读取策略再建议；保存原值、结果、因子、单位、精度、舍入和日期；高风险温度/纪录/密码不自动改 | 实体 span、换算过程、策略版本；CONVERSION_REVIEW/ORIGINAL_VALUE_LOST；MET-UNIT-001/002/003；§4.5 |
| RULE-UNIT-002 / 货币/日期/文化线索 / F-05 | HARD禁止推断+SOFT建议；代码+人 | 不实时换算剧情金额；购买信息获准换汇须 rate_source/time/base_currency；歧义日期展开月份或确认，时区/历史日不猜；颜色数字手势只提示 | 原值与语境、汇率快照；AMBIGUOUS_DATE/FX_EVIDENCE_MISSING；MET-UNIT-002/003、MET-QUAL-005；§4.5 |

### 6.5 口语 oral_review

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-ORAL-001 / language×script×locale×platform profile / F-06 | HARD有效平台上限+SOFT试点阈值；代码计算+模型候选+人 | CPS、行长/行数、时长按同一有效 profile；软超限提示，生效硬上限超限 BLOCK 合格导出，建议压缩/延时；P-ORAL 数值未经批准不作生产硬门槛 | 可见字符策略、秒数、profile版本；READABILITY_WARN/BLOCK；MET-ORAL-001/002；§4.6 |
| RULE-ORAL-002 / 语种×项目上下文 / F-06 | HARD语义保护+SOFT自然度；模型/规则+译审 | 复杂度/翻译腔按 P-ORAL 提示；不得改事实、否定、关系、情绪、术语；疑似变动需审，确定改变撤回改写；不能压缩到丢剧情 | before/after、保护实体/关系、解释；SEMANTIC_PROTECTION；MET-ORAL-003、MET-REV-002/003；§4.6 |

### 6.6 合规 compliance

| rule_id / scope / BRD | 类型与执行者 | 条件 → 行为、兜底 | 证据/原因、指标、来源 |
| --- | --- | --- | --- |
| RULE-OUT-001 / format×platform/profile×locale / F-07 | HARD结构/字符规则；代码 validator | 按任务生成 SRT/VTT/TTML/IMSC 等所选格式，检查schema、编码、时间、glyph、RTL/ruby、元数据；时间/可读性具体级别由 profile；失败定位并回原模块 | Validation逐项结果、Artifact hash、profile；QC_FAILED；MET-OUT-001/003；§4.7 |
| RULE-OUT-002 / 交付范围×当前修订 / F-07/08 | HARD内容/版本闸门；代码+审校签发 | 全部交付 segment 有授权人工决定；无未决P0/P1、缺manifest、锁词/关键语义问题；有效校验及必要senior/legal签名齐全才可进入授权签发；修改后重验 | ReviewDecision/Validation/Artifact 同版本引用；CONTENT_UNRESOLVED/SIGNATURE_REQUIRED；MET-GOV-003、MET-OUT-003；§4.7、附录B |
| RULE-OUT-003 / 发布交接 / F-07/10 | HARD权限；人/外部流程 | 只生成交付包和签发记录；无真实运营/平台回执不得记 PUBLISHED；公开通用Netflix指南不能替代签约profile | 签名、交付清单、外部回执受控引用；PUBLICATION_UNVERIFIED；MET-GOV-002/003、MET-OUT-002；§4.7/4.8 |

## 7. 停止、重试与降级：处理课件内部差异

已确认的 RULE-SUB-004 不变。§1.6“超过预算即停止”与 §5.1“单分钟成本超预算120%停止/保留P0/P1”口径不同，**本项目不得据此批准超支20%**。后者及 §6.5“P90超预算20%报警”只登记为待确认的观察建议；未明确预算边界不启动收费自动处理。停止后可展示已有证据、人工继续及运行本地只读检查，不能以“保留P0/P1”为由继续付费调用。

重试暂定设计解释：初次调用 attempt_no=1；第一次自动重试为2；第二次自动重试为3；第二次重试完成或失败后不得再自动调用；恢复另有人工授权事件，不重置历史。**该计数解释为待评审运行参数**；执行前必须确认“连续”、跨备用模型/修复调用的累加方式和 Task 边界，不能在代码中隐式选一套。任何局部上限都服从全局停止条件。

| rule_id / 失败 | 局部建议与禁止 | 降级/升级及必留记录 |
| --- | --- | --- |
| RULE-OPS-001 / 依赖超时 | §5.1建议15秒/队列SLA，指数退避最多2次；均未默认生效；不重试鉴权/权限错误 | 参数确认后执行；备用路线也计成本/尝试；原文与空候选、超时原因保留；MET-OPS-001 |
| RULE-OPS-002 / 低置信/缺上下文 | 不重试同配置；可申请扩窗一次/专用模型；上下文拉取一次亦须限额 | 记录 context 前后hash；P0不得用过期/只读默认包完成裁决；缺有效包则人工；MET-ASR-005、MET-QUAL-005 |
| RULE-OPS-003 / 非法schema | §5.1建议修复提示一次，仍受总限额；不把格式修复等同质量通过 | FAILED_SCHEMA、原始受控响应、修复记录；回上一稳定模型需新manifest；MET-OUT-001、MET-OPS-001 |
| RULE-OPS-004 / 幂等 | 按schema.md §2的完整作用域键（task_id、task_revision、module、segment_id/范围摘要、input_revision、target_variant_key、manifest_hash）只准一个有效结果组 | 课件§5.1较短公式为参考，须补任务与目标隔离；重试不制造多条有效候选、不删失败；hash序列化/并发事务待开发实现；MET-GOV-001 |

## 8. 参数登记：建议保留，审批后才生效

参数记录须有 parameter_id/version、scope、值/单位/端点、来源、校准方法/样本版本、owner、审批和有效期。以下均为 **PROPOSED、未启用**；真实平台硬规范另附签约证据再 ACTIVE，不让建议默认值顶替缺失规范。

| 参数 ID | 课件建议值与使用边界 | 生效前要求 / 指标 |
| --- | --- | --- |
| P-ASR-AUDIO | SNR<10dB 或削波>3% 提示BAD_AUDIO | 测量窗口/算法、音轨代表性、误报成本确定；MET-ASR-006 |
| P-ASR-CONF | ≥0.92高档；0.82≤分<0.92抽检；<0.82必审；每语种校准样本<500不启自动档 | 端点为避免原文区间歧义的设计定义；校准分不得以模型自评冒充；抽检比例/样本标签待确认；MET-ASR-005 |
| P-ASR-TIME | 起终偏差P95≤120ms；单边界偏差>250ms强制人工 | P95是批次质量指标，不可据此判定每条均合格；人工参考与匹配方法见metrics；MET-ASR-003 |
| P-ASR-OVERLAP | overlap>300ms保留多人/重叠标签 | 检测器与标注规范待定；附录620ms例只作样例；MET-ASR-004 |
| P-TR-QE | QE≥0.86普通复核；QE<0.72建议重译；中档加强复核为本设计补齐 | 需固定QE模型/版本/语言对，不能把不同QE分直接比较；MET-TR-001 |
| P-CULT | 有证据且P0影响+置信≥0.90，或有效确定性硬命中→P0；P1置信≥0.70或任一路高风险；P2≥0.45有解释 | 阈值不足不代表无风险；无证据最高P1；0.45以下仍可保留不确定线索待人工，不隐藏；分级校准及标签规范待定；MET-QUAL-002/003/005 |
| P-CULT-SLA | P0高级本地审校2h、P1普通审校8h、P2随任务 | SLA起止、暂停、值班与责任人未确认，不承诺真实响应；可用TAT分桶观察 |
| P-UNIT | 日常温度整数/科学按源精度；距离速度2—3有效数字 | 必须由conversion_policy按语境批准；实体召回≥98.5%、计算正确≥99.9%、剧情原值静默丢失0为课件验收建议；MET-UNIT-001/002/003 |
| P-ORAL | Latin软17/硬20 CPS，CJK软9/硬12；行长Latin42/CJK21；复杂度同语种P90；翻译腔score≥0.75 | CPS需每语种至少500条合格字幕校准，硬上限来自适用平台；没有profile不得以建议数字签发；MET-ORAL-001/002/003 |
| P-QUALITY | P0召回≥98.5%、P1≥92%；提示precision P0≥85%/P1≥65%；术语≥99.5%/P0品牌100%；P0/P1证据完整100% | 均为课件建议准入指标，启用需金标/置信区间及关键桶定义；MET-QUAL-002/003/004/005 |
| P-OUTPUT | schema一次通过≥99.5%，越权发布0 | 统计目标不允许单包硬错误被平均掩盖；MET-OUT-001、MET-GOV-002/003 |
| P-EFFICIENCY | 有效接受≥55%非硬闸门、净人工节省≥20%且质量非劣、单位成本≤基线65% | 未有项目基线不能宣称达标；公式依metrics且不重复扣新增复核；MET-REV-002、MET-EFF-002、MET-COST-001 |
| P-ROLLBACK | 附录B建议15分钟内恢复上一稳定规则/Prompt/模型/包 | 属演练目标待验证；外部模型旧版本不可用须记录无法复现，不能声称已恢复 |

Netflix 5/6秒—7秒、TTML 等仅是课件公开规范示例，**不登记为跨平台通用活动规则**；首批市场、平台、rating覆盖清单为空待确认，不假称已拥有合格规则包。

## 9. 生效、变更、回滚与验收

1. 新建 DRAFT；业务 owner 核对来源/适用范围，技术 owner 核对可执行性，高风险由本地高级审校/法务审批；角色职责待主PRD落实。
2. 为每条 HARD/P0/P1 规则建立正常、异常和权限用例；参数阈值覆盖等于/略低/略高、缺值/非法值；scope覆盖匹配、不匹配、未知、过期及不可比冲突。本文不冒用课件TEST示例为已建测试。
3. 使用固定样本版本分语种/市场/内容/平台回归；报告准确、误报负担、人工时间和成本，未通过不降低标准。与指标版本一起审查，禁止上线后换分母证明成功。
4. APPROVED后按明确scope灰度激活；旧版本不覆盖，生效时间、操作者与理由留Event。正在运行的Run仍绑定原manifest；新Run采用新活动集。
5. 回滚指定上一已批准版本；受影响Candidate/Issue/Validation/Artifact反向查询，重新校验或撤销签发，不删除历史决策。旧版本已不合法/过期不能因“稳定”自动恢复，交owner处置。
6. 锁定规则或参数的任何行为变化均新版本，并同步数据/指标、原型说明、主子PRD、用例与日志；文案无行为变化亦留修订记录。不得通过换rule_id隐去历史失败。

最低联查案例：有视频无任务单不可ASR；缺脚本但声音可用可走ASR；模型0.99无文化证据不能标P0；P0规则过期不可默用；CPS达标但否定丢失不可放行；旧修订签名不能签新包；同级scope交叉必升级；预算未配不能收费；重试不能重复造候选；Agent尝试发布必拒绝且审计。均为**待工程验证方向**。

## 10. 来源核对与待评审清单

| 实际材料 | 本轮采用 | 边界 |
| --- | --- | --- |
| 参考工程 docs/03-foundation/03-03-schema/schema.md §A/B；rules/coding-standards/09-api-design.md §1、§5；docs/05-prd/03-subprd-judge-dedup-route.md §3—4 | 字段/规则/行为/数据写入对应、明确必填/可空、来源与双向引用 | 没有照搬社群电商阈值、Cloudflare存储或camelCase接口约定；参考项目无可直接复制的字幕rule registry |
| 原课件 §0.5—0.7（53—80行）、§1.4—1.6（105—152行）、§3.3（313—324行） | 六维检查、五类冲突、白盒、范围维度及锁定目的 | 框架不是已验证企业现场数据，也不是只能有这些类别 |
| 原课件 §4（336—462行）、§5（464—509行）、§6.5（577—588行）、附录（731—774行） | 六模块规则、候选/权限、证据版本、失败/幂等、建议阈值与验收方向 | 示例数字未自动生效；停止口径差异见 §7 |
| meeting/week1.txt 76—94行（31:09—35:35） | 哪些交AI/人、依据与产出、可审计、候选优先级、冲突跨维 | 教师讲解为设计理解，不证明本项目已运行；不照抄口述总优先级 |
| meeting/week2.txt 50—62、78—94、114—118、146—154行 | 从失败/责任/更新周期/指标抽维度；规则检索+语境发现；市场包字段；工程校验及定点退回 | 转写有口误，“口语完全不需模型”不能覆盖课件§4.6语义候选；按确定性/语义职责拆分 |
| work/知识索引.md；09-六维度与治理机制的推导.md；prototype/action-map.md | 保持七业务阶段、六处理模块、母版/任务单和说明型原型边界 | 历史总结非新增批准证据；现有原型保持不改 |

待评审并阻止相应生产路线的配置：首批语种/市场/平台与rating；真实签约规则包及owner；校准数据/抽检比例；预算与重试计数/恢复；批量保存事务策略；角色授权矩阵/双人复核适用条件；SLA与保留周期。以上不妨碍本轮形成完整可评审契约，但不能在缺失时称全链路可自动运行。

## 首批源语落地准备（2026-10-20）

[首批方案](../07-delivery-plans/source-release-solution.md)、[技术契约草案](source-release-contract.md)、[实施计划草案](../07-delivery-plans/main-delivery-plan-source-release.md)、[正式TC设计](../06-testcase/tc-main-subtitle-workflow.md)。

首批仅收料/任务→转写、核对或对齐→人工源稿审阅→源语导出；174条TC设计全部NOT_RUN，8项实现任务全部阻塞。技术方案及契约是PROPOSED，数据字段仍以schema为权威；采纳扩展须在T0.1先同步权威定义。真实样本、权限、模型/阈值和预算仍待确认；多语模块未纳入本批实现。不把静态检查或合成配方当业务验收。

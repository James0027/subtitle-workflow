# 样本、脱敏与标签契约 v0.1

> 上游（我引用）：[数据契约](schema.md) §1—§7；[BRD](../01-brd/BRD.md) §2.3、§4；[规则登记](rule-registry.md)；[指标契约](metrics.md)；课件 §3.1—3.4、§5.2/5.4、附录 A。
> 下游（引用我）：[V3原型说明](../02-prototype/README.md)；[V3页面清单](../02-prototype/page-list.md)；[联合基线入口](README.md)；[数据契约](schema.md) §1；主子 PRD、评测计划与真实样本清单待建立。

状态：**样本组织和标注设计草案，不是已采集/授权/标注完成的数据集**。首批真实素材尚需逐项核验；已有调研报告与下载结果不自动成为合格输入。未生成真实金标，不填虚构样本总数、通过率或已锁定哈希。

## 1. 为什么这样分

课件 §3.1 的24部、144版本、12,000金标及§6.1的6,000/2,000/2,000是教学设计示例；不套成当前样本量。`meeting/week2.txt` 44—56 行强调样本反映正常分布与失败变量，不因案例恰好好看而选择；数量需结合实际可得素材、分桶覆盖和置信要求确定。

先明确“谁能用、来源是否可靠、覆盖了什么场景、谁确认正确答案”，再比较工具。正常分布样本与刻意困难样本分开报告；不能把挑战集错误率当线上发生率。

## 2. 清单结构与单位

### 2.1 DatasetManifest（版本不可变）

| 字段 | 类型/必填 | 约束 |
| --- | --- | --- |
| dataset_id / dataset_version / schema_version | string/是 | 数据集+版本唯一；修订清单另发版 |
| purpose | enum/是 | discovery/development/calibration/golden/challenge/regression；影子和灰度待真实运行设计 |
| manifest_checksum | string/发布时 | 清单规范序列化SHA256；草案不伪填 |
| created_at / owner_id / access_policy_ref | timestamp,string,string/是 | 确认谁管理和谁可用 |
| selection_protocol / sampling_frame_ref | string,string\|null | 采样方法及候选总体来源；便利样本须明示，不能称随机总体 |
| split_policy_version / label_policy_version | string/是 | 固定拆分及金标定义 |
| sample_ids / exclusion_log | string[],object[]/是 | 排除项含source_id、原因、操作者、时间；坏样本不可静默删除 |
| planned_counts / actual_counts | object/是 | 每桶计划、实际、已标/待标/不可判；未知null；当前真实数量待盘点 |
| release_status | enum/是 | DRAFT/REVIEWED/FROZEN/RETIRED；FROZEN须完成§7清单，不能因写了此文自动冻结 |

### 2.2 SampleItem（一条评价输入，不一定只一句字幕）

| 字段 | 类型/必填 | 约束 |
| --- | --- | --- |
| sample_id / dataset_id / dataset_version | string/是 | 主键及所属清单 |
| project_id / title_id / episode_id / media_id | string/是 | 同一母版、作品和衍生关系可回查 |
| unit | enum/是 | media_clip/segment/error_occurrence/task/artifact；不同单位不混统计 |
| asset_refs / segment_refs | Ref[]/是 | 可精确回放；无segment的入库样本数组为空但须有asset_refs |
| interval | object/是 | start_ms/end_ms相对母版；片段音频另记offset_ms，不以切片时间冒充母版时间 |
| variant_key / locale / market_codes / platform_profile_ref | string,string,string[],object\|null | 源语专项可明确market/profile不适用，目标样本不能只写语言 |
| group_id / near_duplicate_group_id | string,string\|null | group_id按作品/系列关系隔离；近重复、重剪、配音版本归组审查 |
| split | enum/是 | development/calibration/evaluation；不能只改名称消除泄漏 |
| origin | enum/是 | authentic/controlled_variant/constructed；构造样例不作真实准确率或业务收益分母 |
| parent_sample_id / interventions | string\|null,object[]/是 | controlled_variant须父样本；干预记录隐藏/提取/加噪/剪切方法与版本，保留原件 |
| availability_pattern / asset_role_map | string,object/是 | 配套完整性桶；每素材标input/held_out_reference/context，人工答案不得偷偷给待测模型 |
| bucket_tags / measurement_provenance | string[],object/是 | 标签来源human/tool/supplied、版本、时间；未测音质桶=unknown |
| rights_ref / redaction_ref / allowed_external_processing | string,string\|null,bool/是 | 下载可访问不等于可用于外部模型上传 |
| gold_item_ids / label_status | string[],enum/是 | UNLABELED/IN_REVIEW/DISPUTED/ADJUDICATED/UNJUDGEABLE；未裁决不得作正式金标 |

### 2.3 三种计数不要混

- Segment 是可稳定定位的字幕事件；拆句不能让相同内容的成片分钟翻倍。
- Suggestion 是不可变 Candidate 对用户的一次逻辑建议，是否展示/采纳由 Event 和 ReviewDecision 记录；**不是金标标签**。
- GoldItem 是独立判定单元；一段可有多个错误发生项 occurrence_id，同一错误的多个标签共用 error_id，避免重复分母。无错样本也需显式标注 inspected_categories 与 no_error，不把“没标签”当正常。

## 3. 素材包覆盖（先入库/ASR，后续逐批）

| 桶 | 原始素材条件 | 需要验证的处理/预期 | 样本性质说明 |
| --- | --- | --- | --- |
| PKG-01 | 视频+原配独立音轨+字幕+脚本 | 关联/版次核对；按任务选核对/对齐路线，不默认ASR | 完整包不保证附件正确 |
| PKG-02 | 视频含可用声音，无独立音轨 | 允许提取另存，保留父文件/参数/时间偏移 | 不称“没有音频”；提取音轨不是原配 |
| PKG-03 | 视频/可用音轨，缺已有字幕 | ASR产生候选，再人工核查 | 缺字幕不等于缺参考答案，评测另建独立金标 |
| PKG-04 | 视频/声音+已有字幕，缺脚本 | 保留原字幕并核对/对齐；脚本通常非ASR必要项 | 不一律阻断；专名不确定单列 |
| PKG-05 | 相同片名但错集/错剪辑/错音轨 | 发现错配，阻断相关路线，交人确认 | 自然错配与人为错配分别标origin |
| PKG-06 | 视频无声/音轨损坏/轨道为空 | 明确不可执行音频识别，保留错误与owner | 不能空返回成功或凭画面猜听写 |
| PKG-07 | 原有多种配音/多字幕版本 | 人确认所选源语/版次，不自动取首个附件 | 附件存在不代表被授权使用 |
| JOB-01 | 完整多语任务 | 目标语言、市场、受众、范围、输出与责任明确 | 缺目标条件不称全局就绪 |
| JOB-02 | 明确source_only | 目标条件显式not_applicable，仍有范围/输出/责任 | 源语子任务与多语母任务分别计数 |
| JOB-03 | 未定义用途/未确认母版/范围越界 | 任务单缺项、版本或范围检查阻断对应阶段 | 不能上传后直接生成“已确认源字幕” |

当前每部短剧先取少量集数是用户的研究偏好，不是统计代表性保证。真实自然缺失难收集时可从完整包隐藏附件，必须保留 parent_sample_id 与 interventions，单独报告受控结果。

## 4. 分桶维度与冲突覆盖

每条样本可多标签，但聚合时按固定主桶或明确交叉分组，不把多标签数量相加当独立样本数。

| 七类条件变量 | 桶/字段（示例，非已验证阈值） | 关键作用 |
| --- | --- | --- |
| 内容 | genre、live_action/animation、rating、对话密度、专名/数字/否定 | 忠实、阅读与剧情保护；未知不猜 |
| 音频 | clean/noisy/unknown；snr_db实测、overlap_ms、削波、音乐/画外音、多说话人 | 把噪声/重叠与语种因素分开；具体边界由规则版本定义 |
| 语言 | source_locale/target_locale、文字系统、RTL、code_switch | WER/CER分词与方向不同，分开比较 |
| 市场 | market_codes、受众/评级、regulatory_pack版本 | 同语言不同市场是独立条件 |
| 平台 | profile_id/version、format、帧率/字符/边界约束 | 格式合法不等于平台首轮通过 |
| 风险 | category、severity、证据有效/缺失/过期、隐喻/歧义/创作意图 | P0/P1与正常分开；不能只抽高风险算日常率 |
| 治理 | 人工锁定/并发旧版/重跑/权限不足/重试停止/缺manifest | 与各模块交叉，验证保护和审计而非只测模型 |

课件 §0.5 的六个质量维度另作覆盖检查：正确性→金标转写/关键实体；可读性→CPS及语义保留；文化法律→适用证据/风险；可交付性→解析/回执；可治理性→版本权限轨迹；效率→完整人工活动与返工。不能将“七条件变量”“六质量维度”“六模块”混为一套桶。

| §0.7五类冲突 | 必留对照标签/预期依据 |
| --- | --- |
| 忠实 vs 可读 | 原文关键事实/否定/专名标注、压缩前后、显示时间；关键剧情保留由人确认 |
| 文化适配 vs 创作表达 | 创作意图、目标市场、适用规则与候选；先提示/裁决，不以更温和自动当正确 |
| 统一规则 vs 市场差异 | 通用/市场规则双方版本scope、预期适用者；无法适用需升级 |
| 效率 vs 安全 | 快速采纳与必要复核/阻断分支、实际人工时；不得用平均效率掩盖关键风险 |
| 模型建议 vs 术语库 | 锁定词命中、建议译法、词表版本、人工裁决；模型偏好不能覆盖锁定词 |

补充并发/重跑/证据缺失/同级规则相反的工程边界样本，标为治理/异常覆盖，不篡改原文五类业务冲突数量。

## 5. 金标和仲裁

### 5.1 GoldItem/Annotation 结构

| 字段 | 类型/必填 | 约束 |
| --- | --- | --- |
| gold_item_id / sample_id / label_version | string/是 | 主键、输入、标签版本；标签变更另发版，不能改历史答案 |
| error_id / occurrence_id | string/null | 有错误时必填；error_id表概念错误，occurrence_id表母版/区间/目标具体发生项；正常项明确no_error |
| assessment_scope / inspected_categories | object,string[]/是 | 具体语言/市场/profile/修订/任务；只对审过的范围出正常结论 |
| reference_text / reference_timing | string\|null,object\|null | ASR金标可独立人听写；时间含start_ms/end_ms、uncertainty_ms、标注工具版本 |
| labels | object[]/是 | category、severity、span、speaker/overlap、expected_action、acceptable_variants、evidence_refs、ambiguity_note；多正确译法可并存 |
| annotations | object[]/是 | annotator_id、role、blind_status、submitted_at、label_payload、label_policy_version；原始意见保留 |
| adjudication | object/条件 | 有分歧时：adjudicator_id/role、decision_at、competing_annotation_refs、final_label、reason_code/evidence；不得让同一模型仲裁自身答案 |
| status / confidence_of_reference | enum,string/是 | IN_REVIEW/DISPUTED/ADJUDICATED/UNJUDGEABLE；参考置信来源是人/测量，不用模型分数替代 |

### 5.2 最小标注流程

1. 标注前固定音轨、字幕、母版、语言、市场、任务范围和标签手册版本。脚本可作语境资料，但不因它有文本就当真实说话金标。
2. 核心评价金标独立双人标注、对候选来源盲审；转写按听到的内容，时间边界由工具辅助并人检查；不能把ASR同一输出另存成“人工答案”。
3. 标注类别至少区分文字替换/删除/插入、专名/数字/否定/人物关系、时间起止、说话人/重叠、风险/证据、单位/阅读/技术格式。严重性分级按规则登记，不自行定模型置信阈值。
4. 先保留两份原始意见，再由合适角色仲裁；文化/法律争议需具备相应市场与审核权限。缺声音、听不清、来源不可靠时标UNJUDGEABLE，不强行选一个答案。
5. 不能判定的项及其原因单列；不进对应质量正式分母，但仍进入素材/不可判覆盖报告。正常/异常、失败、放弃数量不可默默删去。
6. 审核员意见一致性、字词规范化、错误项匹配和时间容差均需版本化；具体统计由指标契约定义。指标匹配容差不能倒推篡改金标以让结果通过。

## 6. 防泄漏、隐私与血缘

- **先分组再拆分**：同一作品/系列、重剪版、同源配音/翻译、原样本及受控变体放同group_id。不能相邻集进开发/测试导致角色、译法与剧情答案泄漏；近重复人工复核并保存分组记录。
- development 用于调试提示词与规则；calibration用于校准与阈值选择；evaluation用于最终比较。测试失败后移入回归可帮助修复，但下次“未见测试”须新留独立集，不再称原项未见。
- Golden、Challenge、Regression是用途标签，不自动保证与训练/检索/校准隔离。每次运行保存 dataset/version、实际样本清单和input/context清单；检测金标正文是否进入模型输入、上下文索引或few-shot提示。
- 术语/角色表若业务正常可得，允许按真实条件注入；专门根据测试答案编的词表不冒称原始业务资料，须记录派生和暴露范围。
- 来源授权分别确认本地研究、保存、分发、外部模型处理。包含声音/人脸的真实视频不能仅删姓名就称完全匿名；外发需对应授权或经核验的脱敏产物。
- 原始素材受限存放；公开报告/测试夹具仅受控引用或构造数据，不写密钥、签名URL、个人联系方式、真实用户路径。Asset保留rights_ref和privacy；脱敏另存并记录父件、变换、校验值。
- 文本姓名替换等会改变专名/语义/发音关系，标签与金标必须同步复审并单独标受控变体，不能拿脱敏字幕对原声音评价识别率。
- 保留期限、销毁方式和撤销授权执行人待定；未定前不宣称已具备自动删除或访问隔离。到期/撤权后停止新增使用，按批准政策处理原件、缓存、派生件和报告引用。
- 血缘可从 Artifact→精确Segment修订/Run→Task快照/manifest→Asset父链→来源授权；样本还可追到标注/仲裁/分组/划分版本。

## 7. 冻结前检查与待定项

| 检查 | 通过证据 | 当前状态 |
| --- | --- | --- |
| 来源/授权/可读性 | 每条来源、校验值、授权与媒体检查真实记录 | 待盘点 |
| 任务单与母版 | 范围/路线/语言/目标条件明确，错版与缺项有owner | 待真实任务验证 |
| 分桶覆盖 | 每桶实际数/缺失及理由；小样本不以统计显著包装 | 待采集 |
| 金标质量 | 双标、仲裁、不可判项及标签版本 | 待标注 |
| 防泄漏 | 作品组/近重复/开发校准测试隔离审查 | 待真实分组 |
| 完整性 | Manifest→Sample→Asset/Segment/Gold引用及hash可解析 | 待有真实数据后运行 |
| 规则/指标联动 | 适用规则版本、评价口径、无零分母伪值 | 契约草案并行对齐，待评审 |

待定项：首批作品与授权、语种/市场/profile、真实样本数量、正常与困难分层比例、标注人员及资格、词字规范化、时间标注工具/不确定度、保留期限。当前仅完成可执行的样本组织规范初稿，不能称“样本已锁定”或“金标集已就绪”。

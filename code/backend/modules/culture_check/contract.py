from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# 1. 基础类型与枚举定义
# ==========================================

CultureCategory = Literal[
    "legal_platform",
    "religion",
    "politics",
    "sex_violence_addiction_ratings",
    "discrimination",
    "local_taboo",
    "other",
]

SeverityLevel = Literal["P0", "P1", "P2", "UNASSESSED"]

EvidenceStatus = Literal["sufficient", "pending_supplementary", "insufficient"]

SuggestedAction = Literal[
    "block_release",
    "modify_dialogue",
    "add_warning",
    "contextual_review",
    "ignore_with_reason",
]

HumanDecisionAction = Literal["accept", "edit_accept", "reject", "ignore_with_reason"]

SourceVerificationStatus = Literal["VERIFIED", "PENDING_VERIFICATION", "FAILED"]

RuleReviewStatus = Literal["VERIFIED", "UNVERIFIED"]

RuleStatus = Literal["ACTIVE", "CANDIDATE", "DISABLED"]

CaseCredibilityLevel = Literal["HIGH", "MEDIUM", "CANDIDATE_ONLY", "UNVERIFIED"]


# ==========================================
# 2. 墨西哥与拉美文化规则及来源登记实体
# ==========================================

class CultureSourceRegistryItem(BaseModel):
    """公开来源元数据登记（依据2026-10-22公开检索与法律查验）"""
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(..., description="来源编号，如 MX-OFF-01, MX-OFF-02")
    source_level: Literal["OFFICIAL", "INDUSTRY_CASE", "COMMUNITY"] = Field(..., description="来源级别")
    title: str = Field(..., description="法规或文献标题")
    url: str = Field(..., description="官方或公开访问URL")
    published_at: Optional[str] = Field(None, description="发布或修订日期，未知为null")
    retrieved_at: str = Field(..., description="检索取得时间")
    source_version: str = Field(..., description="版本或签署标识")
    applicable_channels: List[str] = Field(default_factory=list, description="适用渠道")
    retrieval_status: Literal["SUCCESS_READ", "SUCCESS_METADATA_ONLY", "FAILED_CAPTCHA", "FAILED_REDIRECT"] = Field(
        ..., description="抓取状态"
    )
    verification_status: SourceVerificationStatus = Field(..., description="核验状态")
    usage_limitations: str = Field(..., description="使用限制与法律效力说明")


class CultureRuleItem(BaseModel):
    """文化审查具体规则项"""
    model_config = ConfigDict(extra="forbid", strict=True)

    rule_id: str = Field(..., description="规则编号，如 R-MX-DISCRIM-01")
    source_ref: str = Field(..., description="关联来源编号，如 MX-OFF-02")
    clause_ref: str = Field(..., description="具体条款引用")
    scope: str = Field(..., description="适用范围")
    category: CultureCategory = Field(..., description="问题大类")
    trigger_condition: str = Field(..., description="触发条件描述")
    exceptions: str = Field(..., description="例外情况说明")
    severity_default: SeverityLevel = Field("P1", description="默认参考严重性")
    rule_version: str = Field("2026-10-22.1", description="规则版本")
    validity_basis: str = Field(..., description="生效依据与过渡条款约束")
    review_status: RuleReviewStatus = Field("UNVERIFIED", description="法务/专家核验状态")
    status: RuleStatus = Field("CANDIDATE", description="活动状态：仅VERIFIED可设为ACTIVE")

    @model_validator(mode="after")
    def validate_active_requires_verified(self) -> "CultureRuleItem":
        if self.status == "ACTIVE" and self.review_status != "VERIFIED":
            raise ValueError(
                f"规则 {self.rule_id} 未经核验(review_status={self.review_status})，严禁标记为 ACTIVE 活动状态！"
            )
        return self


class CultureCaseItem(BaseModel):
    """行业与社媒案例登记"""
    model_config = ConfigDict(extra="forbid", strict=True)

    case_id: str = Field(..., description="案例编号，如 MX-CASE-01")
    source_ref: str = Field(..., description="关联来源编号")
    author_identity_verified: bool = Field(False, description="作者身份与资质是否已核实")
    scenario_or_context: str = Field(..., description="发生场景或涉及剧目")
    source_translation_observation: str = Field(..., description="源语与译文观察")
    boundary_scope: str = Field(..., description="适用边界与例外")
    credibility_level: CaseCredibilityLevel = Field(..., description="可信度说明")
    status: Literal["ACTIVE_REFERENCE", "CANDIDATE", "RESEARCH_ONLY"] = "CANDIDATE"


# ==========================================
# 3. 待检输入契约 (Client -> Server)
# ==========================================

class CultureUnitInput(BaseModel):
    """待检单句源译及上下文"""
    model_config = ConfigDict(extra="forbid", strict=True)

    unit_id: str = Field(..., description="对话单元编号，如 u_001")
    translation_id: Optional[str] = None
    translation_revision: Optional[int] = Field(None, ge=1)
    source_text: str = Field(..., description="源语忠实台词")
    target_text: str = Field(..., description="初翻目标语言译文")
    speaker_id: Optional[str] = Field(None, description="说话人编号")
    character_name: Optional[str] = Field(None, description="角色名")
    narrative_stance: Optional[str] = Field(None, description="叙事立场")
    start_ms: Optional[int] = Field(None, ge=0, description="起始毫秒")
    end_ms: Optional[int] = Field(None, ge=0, description="结束毫秒")
    prev_units: List[Dict[str, str]] = Field(default_factory=list, max_length=2, description="前至多2句上下文")
    next_units: List[Dict[str, str]] = Field(default_factory=list, max_length=2, description="后至多2句上下文")


class MediaEvidence(BaseModel):
    """音画证据及覆盖范围说明"""
    model_config = ConfigDict(extra="forbid", strict=True)

    has_audio: bool = Field(False, description="是否覆盖音频信息")
    has_video_frames: bool = Field(False, description="是否覆盖视频画面信息")
    coverage_note: str = Field("仅检查提供的台词文本，未检查音频与画面", description="覆盖说明")


class CultureCheckRequest(BaseModel):
    """文化检测任务请求"""
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field("1.0.0", description="Schema版本")
    task_ref: str = Field(..., description="任务编号")
    task_revision: int = Field(..., ge=1, description="任务当前源译修订版本")
    source_language: str = Field("zh-CN", description="源语言")
    target_language: Literal["es-MX"] = Field("es-MX", description="目标语言")
    target_market: Literal["MX"] = Field("MX", description="目标市场代码，冻结MX")
    target_audience: Optional[str] = Field(None, description="目标受众")
    target_rating: Optional[str] = Field(None, description="期望分级")
    distribution_channel: Optional[str] = Field(None, description="发行平台渠道")
    missing_channel_or_audience: bool = Field(False, description="受众或渠道缺失标记")
    units: List[CultureUnitInput] = Field(..., min_length=1, description="待检测的字幕单元列表")
    selected_rule_ids: Optional[List[str]] = Field(None, description="指定规则ID列表")
    case_refs: Optional[List[str]] = Field(None, description="参考案例ID列表")
    media_evidence: MediaEvidence = Field(default_factory=MediaEvidence, description="音画证据覆盖")
    simulate: bool = Field(False, description="是否使用本地隔离模拟引擎")

    @model_validator(mode="after")
    def check_units(self):
        ids = [unit.unit_id for unit in self.units]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate input unit IDs")
        for unit in self.units:
            if not unit.unit_id.strip() or not unit.source_text.strip() or not unit.target_text.strip():
                raise ValueError("Input units require nonempty IDs and source/translation text")
            if unit.start_ms is not None and unit.end_ms is not None and unit.end_ms <= unit.start_ms:
                raise ValueError("Invalid input time range")
        return self



# ==========================================
# 4. LLM 纯模型层输出契约 (Model -> Server)
# 严格禁止 ranking_score, status, run_id, manifest
# ==========================================

class LLMTriggerSpan(BaseModel):
    """LLM 输出的触发跨度"""
    model_config = ConfigDict(extra="forbid", strict=True)

    source_span: Optional[str] = None
    target_span: Optional[str] = None
    start_char: Optional[int] = Field(None, ge=0)
    end_char: Optional[int] = Field(None, ge=0)


class LLMCultureIssue(BaseModel):
    """LLM 纯模型原始检出项（无服务端状态、无系统打分）"""
    model_config = ConfigDict(extra="forbid", strict=True)

    unit_id: str
    category: CultureCategory
    trigger_spans: List[LLMTriggerSpan] = Field(..., min_length=1)
    severity_proposal: SeverityLevel
    impact_level: Optional[int] = Field(None, ge=1, le=3)
    occurrence_likelihood: Optional[int] = Field(None, ge=1, le=3)
    remediation_difficulty: Optional[int] = Field(None, ge=1, le=3)
    factor_reasons: Optional[Dict[str, str]] = None
    confidence_raw: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_basis: str
    rule_refs: List[str] = Field(default_factory=list)
    case_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus
    speaker_ref: Optional[str] = None
    narrative_stance: Optional[str] = None
    explanation: str
    suggested_action: SuggestedAction
    suggested_translation: Optional[str] = None
    missing_context: List[str] = Field(default_factory=list)


class UncheckedUnit(BaseModel):
    """未检单元记录"""
    model_config = ConfigDict(extra="forbid", strict=True)

    unit_id: str
    reason: str


class LLMCultureCheckOutput(BaseModel):
    """LLM 响应根对象"""
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0.0"] = "1.0.0"
    issues: List[LLMCultureIssue]
    checked_unit_ids: List[str]
    unchecked_units: List[UncheckedUnit]
    coverage_limitations: List[str]


# ==========================================
# 5. 服务端业务与交付契约 (Server -> Client)
# ==========================================

class TriggerSpan(BaseModel):
    """经工程精确校验并补齐边界的触发跨度"""
    model_config = ConfigDict(extra="forbid", strict=True)

    source_span: Optional[str] = None
    target_span: Optional[str] = None
    start_char: Optional[int] = Field(None, ge=0)
    end_char: Optional[int] = Field(None, ge=0)


class FactorReasons(BaseModel):
    """排序因子依据"""
    model_config = ConfigDict(extra="forbid", strict=True)

    impact_reason: Optional[str] = None
    likelihood_reason: Optional[str] = None
    remediation_reason: Optional[str] = None


class ConfidenceDetail(BaseModel):
    """置信度与标定分离模型：未接入独立校准时，calibrated_score 必须为严格 None"""
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    calibrated_score: Literal[None] = None
    calibration_version: Literal[None] = None
    basis: str


class CultureCheckIssue(BaseModel):
    """服务端完整处理后、可持久化并展示的风险项"""
    model_config = ConfigDict(extra="forbid", strict=True)

    issue_id: str
    unit_id: str
    category: CultureCategory
    trigger_spans: List[TriggerSpan] = Field(..., min_length=1)
    severity_proposal: SeverityLevel
    impact_level: Optional[int] = Field(None, ge=1, le=3)
    occurrence_likelihood: Optional[int] = Field(None, ge=1, le=3)
    remediation_difficulty: Optional[int] = Field(None, ge=1, le=3)
    ranking_score: Optional[int] = Field(None, ge=1, le=27)
    factor_reasons: Optional[FactorReasons] = None
    confidence: ConfidenceDetail
    rule_refs: List[str] = Field(default_factory=list)
    case_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus
    speaker_ref: Optional[str] = None
    narrative_stance: Optional[str] = None
    explanation: str
    suggested_action: SuggestedAction
    suggested_translation: Optional[str] = None
    missing_context: List[str] = Field(default_factory=list)
    downgraded_from_p0: bool = False
    downgrade_reason: Optional[str] = None
    status: Literal["AI_PROPOSED", "CONFIRMED", "EDITED", "REJECTED", "IGNORED", "PENDING_RECHECK"] = "AI_PROPOSED"
    decision_action: Optional[str] = None
    decision_by: Optional[str] = None
    decision_at: Optional[str] = None


class CultureCheckResult(BaseModel):
    """文化检测完整交付产物"""
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field("1.0.0", description="Schema版本")
    run_id: str = Field(..., description="本次Run唯一标识")
    task_ref: str = Field(..., description="任务编号")
    task_revision: int = Field(..., ge=1, description="任务源译修订版本")
    target_market: Literal["MX"] = Field("MX", description="目标市场")
    issues: List[CultureCheckIssue] = Field(default_factory=list)
    checked_unit_ids: List[str] = Field(default_factory=list)
    unchecked_units: List[UncheckedUnit] = Field(default_factory=list)
    coverage_limitations: List[str] = Field(default_factory=list)
    manifest: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# 6. 人工裁决与回滚请求契约 (Body 严禁携带 actor/role)
# 身份由可信服务端上下文/鉴权注入，拒绝客户端自报与默认值
# ==========================================

class HumanIssueDecisionRequest(BaseModel):
    """人工审阅裁决单个风险项（客户端请求体）"""
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int = Field(..., ge=1, description="乐观锁防并发：期望的目标当前修订版本")
    decision_action: HumanDecisionAction = Field(..., description="裁决动作")
    edited_translation: Optional[str] = Field(None, description="若为edit_accept，则为人工修改后的新译文")
    ignore_reason: Optional[str] = Field(None, description="若为ignore_with_reason，必须提供忽略原因")


class RollbackRequest(BaseModel):
    """译文回滚请求（客户端请求体）"""
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int = Field(..., ge=1, description="乐观锁：期望当前修订版本")
    target_revision: int = Field(..., ge=1, description="要回滚到的历史版本")
    reason: str = Field(..., min_length=2, description="回滚原因与依据")

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# Task A: 源语整理与说话人/角色候选
# ==========================================

class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chunk_id: str = Field(..., description="来源切片标识")
    start_ms: Optional[int] = Field(None, ge=0, description="片段相对起始毫秒")
    end_ms: Optional[int] = Field(None, ge=0, description="片段相对结束毫秒")
    original_text: str = Field(..., description="切片中的原始忠实文字")


class SpeakerCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    speaker_id: str = Field(..., description="匿名或暂定说话人编号，如 spk_1, spk_2")
    character_ref: Optional[str] = Field(None, description="建议映射的角色ID；若无证据必须为 null/unknown，严禁主观凭声线臆测")
    evidence_refs: List[str] = Field(default_factory=list, description="判定依据（如台词直接呼告、自我介绍、切片ID）")
    uncertainties: List[str] = Field(default_factory=list, description="说话人/角色疑点说明")


class SourceUtterance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    unit_id: str = Field(..., description="整理后的对话单元编号，如 u_001")
    text: str = Field(..., description="整理后的源语忠实完整台词，保留原字，可修正跨切片标点与断句")
    source_spans: List[SourceSpan] = Field(..., min_length=1, description="回溯对应切片与原文区间；跨切片合并保留多个父引用")
    speaker_id: Optional[str] = Field(None, description="对应说话人编号")
    character_ref: Optional[str] = Field(None, description="对应角色ID（有证据时由系统或人工填充）")
    start_ms: Optional[int] = Field(None, ge=0, description="母本全局对齐起始毫秒；若无法精确定位则为null或切片粗起点")
    end_ms: Optional[int] = Field(None, ge=0, description="母本全局对齐结束毫秒；若无法精确定位则为null或切片粗终点")
    timing_precision: Literal["word", "phrase", "chunk_fallback"] = Field("chunk_fallback", description="时间精度级别")
    uncertainties: List[str] = Field(default_factory=list, description="疑点列表")


class SourceCleanupOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["stitch", "split", "punctuate", "filter_noise"] = Field(..., description="整理操作类型")
    detail: str = Field(..., description="操作说明")
    unit_id: Optional[str] = None


class SourceCleanupIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detail: str = Field(..., min_length=1)
    unit_id: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)
    severity: Literal["BLOCK", "WARN", "INFO"] = "WARN"


class SourceCleanupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0.0"] = Field("1.0.0", description="Schema版本")
    speakers: List[SpeakerCandidate] = Field(default_factory=list)
    utterances: List[SourceUtterance] = Field(default_factory=list)
    operations: List[SourceCleanupOperation] = Field(default_factory=list)
    issues: List[SourceCleanupIssue] = Field(default_factory=list)


# Task A Server Encapsulation Input
class SourceCleanupInput(BaseModel):
    schema_version: str = "1.0.0"
    task_ref: str
    task_revision: int
    source_language: str = "zh-CN"
    source_refs: List[Dict[str, Any]]
    context_refs: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# Task B: 初翻生成
# ==========================================

class TermHit(BaseModel):
    source_term: str = Field(..., description="源语术语/锁词")
    required_target: str = Field(..., description="要求的译法")
    actual_target: str = Field(..., description="初翻中实际采纳的译法")
    term_ref: Optional[str] = Field(None, description="知识库词条ID")
    matched: bool = Field(True, description="是否满足要求")


class UnitTranslation(BaseModel):
    unit_id: str = Field(..., description="对应源语对话单元ID")
    translation: str = Field(..., description="初翻目标语言译文")
    term_hits: List[TermHit] = Field(default_factory=list, description="锁词命中及遵守情况")
    brief_source_paraphrase: Optional[str] = Field(None, description="源语语义要点回述，以证明理解准确")
    issues: List[str] = Field(default_factory=list, description="译文潜在疑点或备选说明")


class TranslationTaskOutput(BaseModel):
    schema_version: str = "1.0.0"
    translations: List[UnitTranslation] = Field(default_factory=list)


# Task B Server Encapsulation Input
class TranslationUnitInput(BaseModel):
    unit_id: str
    text: str
    speaker_id: Optional[str] = None
    character_name: Optional[str] = None
    prev_units: List[str] = Field(default_factory=list, description="前至多2句上下文（仅用于辅助理解）")
    next_units: List[str] = Field(default_factory=list, description="后至多2句上下文（仅用于辅助理解）")


class TranslationTaskInput(BaseModel):
    schema_version: str = "1.0.0"
    task_ref: str
    source_revision: int
    source_language: str = "zh-CN"
    target_language: str = "en"
    target_market: str = Field(..., description="用户明确选择的目标市场（如 US, ES, LATAM 等），严禁硬编码默认")
    units: List[TranslationUnitInput]
    locked_terms: List[Dict[str, Any]] = Field(default_factory=list)
    character_context: List[Dict[str, Any]] = Field(default_factory=list)


# ==========================================
# Task C: 语义检查
# ==========================================

class SemanticCheckIssue(BaseModel):
    check_id: Optional[str] = None
    unit_id: str
    category: Literal[
        "omission", "addition", "number", "negation", "entity",
        "relationship", "address", "context", "other"
    ]
    severity: Literal["BLOCK", "WARN", "INFO"] = "WARN"
    source_span: Optional[str] = None
    target_span: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    detail: str
    suggestion: Optional[str] = None
    uncertainty: Optional[str] = None
    status: Literal["OPEN", "RESOLVED", "IGNORED"] = "OPEN"


class SemanticCheckOutput(BaseModel):
    schema_version: str = "1.0.0"
    issues: List[SemanticCheckIssue] = Field(default_factory=list)
    qe_status: str = Field("未评估", description="工程QE评估状态，未独立接入时如实显示'未评估'，严禁伪填评分")


# ==========================================
# Knowledge & Memory
# ==========================================

class KnowledgeItemCreate(BaseModel):
    project_id: str = "PRJ-DEFAULT"
    task_id: Optional[str] = None
    category: Literal["glossary", "character", "scene", "rule"] = "glossary"
    source_text: str = Field(..., min_length=1)
    target_text: Optional[str] = None
    target_language: Optional[str] = None
    target_market: Optional[str] = None
    is_locked: bool = False
    status: Literal["PROPOSED", "CONFIRMED"] = "CONFIRMED"
    scope: Literal["project", "episode", "task"] = "project"
    evidence: Optional[str] = None


class KnowledgeItemUpdate(BaseModel):
    """知识条目更新；target_language/target_market 仅在显式传入时生效（含显式置 null 清空）。

    注意：市场与语言的匹配由服务端 KnowledgeService 统一校验，不接受自相矛盾的组合。
    """

    source_text: Optional[str] = None
    target_text: Optional[str] = None
    is_locked: Optional[bool] = None
    status: Optional[Literal["PROPOSED", "CONFIRMED"]] = None
    target_language: Optional[str] = None
    target_market: Optional[str] = None


# ==========================================
# Human Review & Gate Requests
# ==========================================

class EditUtteranceRequest(BaseModel):
    expected_revision: int = Field(..., description="期望的当前源稿修订版本号，用于乐观锁防冲突")
    text: Optional[str] = None
    speaker_id: Optional[str] = None
    character_ref: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class ConfirmSourceTranscriptRequest(BaseModel):
    expected_revision: int
    force_ignore_doubts: bool = False
    reason: Optional[str] = None


class GenerateTranslationRequest(BaseModel):
    target_language: str = "en"
    target_market: str = Field(..., description="目标市场（必须由用户指定，例如 US, ES, LATAM）")
    simulate: bool = False


class TranslationRevisionRequest(BaseModel):
    expected_revision: int
    source_revision: int


class ConfirmAllTranslationsRequest(BaseModel):
    source_revision: int
    expected_revisions: Dict[str, int]


class EditTranslationRequest(TranslationRevisionRequest):
    text: str


class RollbackTranslationRequest(TranslationRevisionRequest):
    target_revision: int
    reason: Optional[str] = "人工回滚至历史版本"

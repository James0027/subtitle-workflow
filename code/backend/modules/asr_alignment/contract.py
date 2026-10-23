from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class TimingCandidate(BaseModel):
    start_ms: Optional[int] = Field(None, ge=0, description="片内相对起始毫秒；未知留空，严禁均分伪造")
    end_ms: Optional[int] = Field(None, ge=0, description="片内相对结束毫秒；未知留空，严禁均分伪造")
    text: str = Field(..., description="对应文字片段")

    @model_validator(mode="after")
    def check_time_range(self):
        if self.start_ms is not None and self.end_ms is not None:
            if self.start_ms > self.end_ms:
                raise ValueError(f"TimingCandidate 倒置时间区间: start_ms={self.start_ms} > end_ms={self.end_ms}")
        return self


class UncertaintyCandidate(BaseModel):
    start_ms: Optional[int] = Field(None, ge=0, description="疑点相对起始毫秒")
    end_ms: Optional[int] = Field(None, ge=0, description="疑点相对结束毫秒")
    description: str = Field(..., description="疑点说明（如听不清、切点截断、语言疑似不符）")


class OverlapCandidate(BaseModel):
    start_ms: Optional[int] = Field(None, ge=0, description="重叠说话相对起始毫秒")
    end_ms: Optional[int] = Field(None, ge=0, description="重叠说话相对结束毫秒")
    text: str = Field(..., description="涉及原文内容")
    speaker_count: Optional[int] = Field(None, ge=1, description="可辨重叠说话人数；未知留空为 null，绝不冒充稳定说话人身份")
    description: str = Field("", description="重叠特征描述")


class EntityCandidate(BaseModel):
    name: str = Field(..., description="专有名词原文")
    category: str = Field("other", description="类别：person/location/organization/brand/work/other")
    context: str = Field("", description="出现语境")
    match_status: str = Field("pending_confirmation", description="词表匹配状态：matched / pending_confirmation (待确认)")
    glossary_ref: Optional[str] = Field(None, description="匹配到的项目术语表/辅助资料引用标识")


class ChunkTranscriptionResult(BaseModel):
    schema_version: str = Field("1.0.0", description="Schema版本标识")
    chunk_id: str
    offset_ms: int
    duration_ms: int
    text: str = Field(..., description="整片实际听到的忠实源语文字")
    timing_candidates: List[TimingCandidate] = Field(default_factory=list)
    uncertainties: List[UncertaintyCandidate] = Field(default_factory=list)
    overlap_candidates: List[OverlapCandidate] = Field(default_factory=list)
    entity_candidates: List[EntityCandidate] = Field(default_factory=list)
    no_speech: bool = False
    model_self_eval_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="模型自评主观分数 (0-1)，未校准不可作正确率")
    confidence_label: str = Field("模型自评/未校准", description="明确标注未校准")
    is_simulated: bool = False
    input_hash: Optional[str] = Field(None, description="系统输入(音频+Prompt)的SHA-256哈希")
    prompt_params: Optional[Dict[str, Any]] = Field(None, description="模型Prompt及参数快照")
    usage_info: Optional[Dict[str, Any]] = Field(None, description="API返回的usage与token统计")
    finish_reason: Optional[str] = Field(None, description="模型输出finish_reason")

    @model_validator(mode="after")
    def validate_speech_text_consistency(self):
        text_content = self.text.strip() if self.text else ""
        if self.no_speech and text_content:
            raise ValueError("no_speech 为 True 但 text 包含非空语音文字，状态与文字冲突")
        if not self.no_speech and not text_content:
            raise ValueError("no_speech 为 False 但 text 为空，未检测到有效忠实转写文字")
        return self


class MasterSegmentResult(BaseModel):
    schema_version: str = Field("1.0.0", description="Schema版本标识")
    segment_id: str
    chunk_id: str
    master_start_ms: int
    master_end_ms: int
    text: str
    timing_precise: bool = Field(False, description="是否具有模型原生细粒度时间戳；若为 False 则回退到切片粗范围回听")
    uncertainties: List[str] = Field(default_factory=list)
    overlap_candidates: List[OverlapCandidate] = Field(default_factory=list)
    entity_candidates: List[EntityCandidate] = Field(default_factory=list)
    confidence_label: str = "模型自评/未校准"
    status: str = "AI_PROPOSED"
    is_simulated: bool = False


class ASRStatusResponse(BaseModel):
    model_id: str
    has_api_key: bool
    external_outbound_authorized: bool
    budget_authorized: bool
    status: str = Field("待配置/待授权", description="状态：'待配置/待授权' 或 '就绪'")
    missing_items: List[str] = Field(default_factory=list)
    allowed_in_pilot: bool = False
    message: str = ""

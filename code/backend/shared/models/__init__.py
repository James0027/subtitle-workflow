from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

# Common Types
class Interval(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

class RangeSpec(BaseModel):
    mode: Literal["whole", "ranges"] = "whole"
    intervals: List[Interval] = Field(default_factory=list)

class MissingItem(BaseModel):
    name: str
    reason: str
    blocking_stage: str
    owner_id: str
    resolution_status: Literal["open", "resolved", "waived"] = "open"
    resolution_ref: Optional[Dict[str, Any]] = None

class ReadinessItem(BaseModel):
    stage: str
    status: Literal["pending", "ready", "blocked"] = "pending"
    checked_at: str
    validation_ids: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)

class MatchCheck(BaseModel):
    asset_id: str
    check_type: str  # codec_readability, sound_presence, duration_alignment, clip_version
    result: Literal["pass", "fail", "unknown"]
    method: str
    checked_by: Optional[str] = None
    checked_at: Optional[str] = None
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)

# API Request Models
class RegisterOperatorRequest(BaseModel):
    display_name: str
    role: str = "media_operator"

class LoginRequest(BaseModel):
    operator_id: str

class CreateTaskRequest(BaseModel):
    project_id: str = "PRJ-DEFAULT"
    request_key: str
    task_type: Literal["source_only", "multilingual"] = "source_only"
    execution_mode: Literal["workflow", "module_only"] = "workflow"
    purpose: Optional[str] = "生成源语字幕，供内部审核与后续翻译使用"
    owner_id: Optional[str] = "task_owner_01"
    source_locale: str = "zh-CN"
    processing_route: Literal["transcribe", "align_existing", "verify_existing"] = "transcribe"
    range: RangeSpec = Field(default_factory=RangeSpec)
    media_id: Optional[str] = None
    input_asset_ids: List[str] = Field(default_factory=list)

class UpdateTaskRequest(BaseModel):
    expected_revision: int
    purpose: Optional[str] = None
    owner_id: Optional[str] = None
    source_locale: Optional[str] = None
    processing_route: Optional[Literal["transcribe", "align_existing", "verify_existing"]] = None
    range: Optional[RangeSpec] = None
    media_id: Optional[str] = None
    input_asset_ids: Optional[List[str]] = None

class RegisterMediaRequest(BaseModel):
    project_id: str = "PRJ-DEFAULT"
    title_id: str
    episode_id: str
    master_video_asset_id: Optional[str] = None
    primary_audio_asset_id: Optional[str] = None
    content_dimensions: Dict[str, Any] = Field(default_factory=lambda: {
        "genre": None,
        "rating": None,
        "content_type": "unknown",
        "dialogue_density": None,
    })

class ConfirmMasterRequest(BaseModel):
    expected_revision: int
    master_video_asset_id: str
    primary_audio_asset_id: str
    match_checks: List[MatchCheck] = Field(default_factory=list)

class ConfirmTaskRequest(BaseModel):
    expected_revision: int
    media_id: str

class ExtractAudioRequest(BaseModel):
    video_asset_id: str
    track_index: int = 1  # 0-based or stream_index

class RequestRunRequest(BaseModel):
    module: str
    input_refs: List[Dict[str, Any]] = Field(default_factory=list)

# ASR Request Models (T2.1)
class ASRTranscribeRequest(BaseModel):
    simulate: bool = False
    source_language: Optional[str] = None

class EditCandidateRequest(BaseModel):
    expected_revision: int
    text: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    confirm: Optional[bool] = Field(None, description="是否直接确认候选。False为仅保存编辑草稿，True为人工确认接受(EDITED_ACCEPTED)")

class ConfirmEntityRequest(BaseModel):
    name: str
    category: str = "other"
    confirmed_name: Optional[str] = None

# Actor Context
class ActorContext(BaseModel):
    actor_id: str
    actor_type: Literal["human", "service_actor"] = "human"
    actor_role: str = "media_operator"  # media_operator, task_owner, reviewer, service_worker, human_denied
    allowed: bool = True

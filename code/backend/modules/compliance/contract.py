"""平台合规质检、多格式导出与双向重解析模块 —— 契约层（状态、问题码、实体、产物包）。

设计依据：docs/05-prd/07-subprd-compliance-delivery.md §2026-10-22（平台合规输出与
发布闸门补充规范：Profile 硬校验、双向重解析、五维签发哈希、四态发布流转）；
docs/03-foundation/schema.md 的 Validation / Artifact / Artifact状态 定义；
docs/03-foundation/metrics.md MET-OUT-001（Schema pass）、MET-OUT-003（导出一致率）。

本层固化四条不可绕过的结构约束：

1. 状态门禁：``VALIDATED`` 必须携带通过校验快照（``ValidationResult.is_valid``）；
   ``PUBLISH_READY`` 必须携带真人签发记录 ``SignoffData``；``PUBLISHED`` 只能由外部
   平台真实回执写入，本模块**禁止构造**（RULE-SUB-002 / RULE-OUT-003：系统不自动发布）。
2. 问题码封闭：违规原因只允许 ``ComplianceIssueType`` 十项，禁止自造字符串绕过统计。
3. Profile 数值可复算：默认值即 Netflix Timed Text 基准，CJK 行长上限单列
   （``cjk_max_line_length=21``），随 ``COMPLIANCE_POLICY_VERSION`` 固化。
4. 产物与校验同档：``ArtifactPackage`` 内嵌校验结果、重解析对账结果与 manifest，
   使 MET-OUT-003「逐字段差异留存」不依赖外部日志。

字段命名对齐 schema.md：Artifact 用 ``artifact_sha256``（对应 checksum_sha256），
状态字段对应 ``delivery_status``。
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

COMPLIANCE_SCHEMA_VERSION = "1.0.0"
COMPLIANCE_POLICY_VERSION = "2026-10-22.1"

DEFAULT_PLATFORM_PROFILE = "netflix_timed_text"
SUPPORTED_EXPORT_FORMATS = ("srt", "vtt")
SUPPORTED_PLATFORM_PROFILES = ("netflix_timed_text",)

# 有权执行合规签发的真人审核员角色（RULE-SUB-002: viewer / media_operator 不得签发）
AUTHORIZED_SIGNOFF_ROLES = (
    "reviewer",
    "compliance_reviewer",
    "auditor",
    "quality_manager",
    "admin",
    "culture_senior",
    "legal_reviewer",
)

# 拉丁语等以空格分词的字幕行长上限；CJK 按方块字宽单独收紧
LATIN_MAX_LINE_LENGTH = 42
CJK_MAX_LINE_LENGTH = 21


# ==========================================
# 1. 状态与问题码枚举
# ==========================================


class ComplianceStatus(str, Enum):
    """产物生命周期（PRD 四态 + 待检草稿）。

    - DRAFT：已生成、尚未完成技术质检
    - QC_FAILED：质检或重解析反查失败，严禁开放下载
    - VALIDATED：技术质检与重解析反查均通过，仅供内部受控预览
    - PUBLISH_READY：有权真人完成数字签发，开放正式导出
    - PUBLISHED：仅由外部平台真实回执写入，本模块不得产生
    """

    VALIDATED = "VALIDATED"
    QC_FAILED = "QC_FAILED"
    DRAFT = "DRAFT"
    PUBLISH_READY = "PUBLISH_READY"
    PUBLISHED = "PUBLISHED"


COMPLIANCE_STATUSES = tuple(status.value for status in ComplianceStatus)


class ComplianceIssueType(str, Enum):
    """平台合规问题码（封闭集合，逐项可定位到 cue 行）。"""

    CPS_EXCEEDED = "CPS_EXCEEDED"
    LINE_LENGTH_EXCEEDED = "LINE_LENGTH_EXCEEDED"
    LINE_COUNT_EXCEEDED = "LINE_COUNT_EXCEEDED"
    DURATION_TOO_SHORT = "DURATION_TOO_SHORT"
    DURATION_TOO_LONG = "DURATION_TOO_LONG"
    DURATION_INVALID = "DURATION_INVALID"
    TIMECODE_OVERLAP = "TIMECODE_OVERLAP"
    GAP_TOO_SMALL = "GAP_TOO_SMALL"
    ROUND_TRIP_MISMATCH = "ROUND_TRIP_MISMATCH"
    SIGNOFF_INVALID = "SIGNOFF_INVALID"


COMPLIANCE_ISSUE_TYPES = tuple(issue.value for issue in ComplianceIssueType)


# ==========================================
# 2. 字幕单元与平台 Profile
# ==========================================


class SubtitleCue(BaseModel):
    """待导出/待质检的一条字幕（人工确认稿的精确修订快照）。

    不在此处断言 ``end_time > start_time``：零时长/负时长必须能被
    ``DURATION_INVALID`` 检出并阻断，而不是在建模阶段抛校验错误。
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=1, description="序号（按时间轴递增，从 1 开始）")
    start_time: float = Field(..., description="开始时间（秒）")
    end_time: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="台词文本，可含 \\n 分行")


class ParsedCue(BaseModel):
    """独立反解析器从成品文件读回的字幕（不信任生成器内存结构）。"""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=1, description="文件中的序号")
    start_time: float = Field(..., description="解析出的开始时间（秒）")
    end_time: float = Field(..., description="解析出的结束时间（秒）")
    text: str = Field(..., description="解析出的台词文本（保留分行）")


class PlatformProfile(BaseModel):
    """平台交付规格。默认值即 PRD §2026-10-22 §1 的 Netflix Timed Text 基准。

    公开 Netflix 指南只是课件参考，不是签约 profile；数值经规则注册表登记、
    有适用语种/市场与审批后才可作生产硬门槛（rule-registry P-ORAL 现状：
    REFERENCE_NOT_ENABLED）。当前作为工程默认值使用，manifest 标注来源。
    """

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(DEFAULT_PLATFORM_PROFILE, description="profile 标识")
    max_line_length: int = Field(LATIN_MAX_LINE_LENGTH, ge=1, description="拉丁语单行字符上限")
    cjk_max_line_length: int = Field(CJK_MAX_LINE_LENGTH, ge=1, description="CJK 单行字符上限")
    max_lines: int = Field(2, ge=1, description="单条字幕屏幕行数上限")
    min_duration_sec: float = Field(0.833, gt=0, description="单条最短显示时长（约 833ms）")
    max_duration_sec: float = Field(7.0, gt=0, description="单条最长显示时长")
    max_cps: float = Field(20.0, gt=0, description="阅读速度硬上限（可见字符/秒）")
    min_gap_sec: float = Field(0.083, ge=0, description="相邻字幕最小空隙（2 帧 @24fps）")

    @model_validator(mode="after")
    def _check_profile(self) -> "PlatformProfile":
        if not self.profile_name:
            raise ValueError("profile_name 不得为空")
        if self.min_duration_sec >= self.max_duration_sec:
            raise ValueError(
                f"profile {self.profile_name} 的最短时长大等于最长时长："
                f"{self.min_duration_sec} >= {self.max_duration_sec}"
            )
        return self


# ==========================================
# 3. 问题、校验结果与重解析对账结果
# ==========================================


class ComplianceIssue(BaseModel):
    """单条违规记录（含实测值/阈值，供 MET-OUT-001 逐项定位）。"""

    model_config = ConfigDict(extra="forbid")

    issue_type: ComplianceIssueType = Field(..., description="问题码")
    cue_index: Optional[int] = Field(None, ge=1, description="关联字幕序号；跨句问题记后一句")
    message: str = Field(..., min_length=1, description="人类可读说明")
    details: Dict[str, Any] = Field(default_factory=dict, description="observed/threshold/rule 等证据")


class ValidationResult(BaseModel):
    """平台 Profile 校验结论（校验器输出，不含生成/签发）。"""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = Field(..., description="是否全部适用检查通过")
    status: ComplianceStatus = Field(..., description="QC_FAILED 或 VALIDATED")
    issues: List[ComplianceIssue] = Field(default_factory=list)
    checked_cue_count: int = Field(..., ge=0, description="实际检查的字幕条数")
    profile_used: str = Field(..., description="本次校验实际使用的 profile 标识")

    @model_validator(mode="after")
    def _check_consistency(self) -> "ValidationResult":
        if self.status not in (ComplianceStatus.VALIDATED, ComplianceStatus.QC_FAILED):
            raise ValueError(f"校验结果状态只能是 VALIDATED 或 QC_FAILED，收到 {self.status.value}")
        if self.is_valid and self.issues:
            raise ValueError("is_valid=True 却携带违规项，禁止把未通过校验说成通过")
        if not self.is_valid and not self.issues:
            raise ValueError("is_valid=False 必须给出至少一条可定位的违规项")
        if self.is_valid and self.status != ComplianceStatus.VALIDATED:
            raise ValueError("is_valid=True 时状态必须为 VALIDATED")
        return self


class RoundTripResult(BaseModel):
    """生成文件经独立反解析器读回后的逐字段对账结果。"""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = Field(..., description="对账是否 100% 一致")
    format: str = Field(..., description="srt / vtt")
    cue_count: int = Field(..., ge=0, description="反解析得到的条数")
    discrepancies: List[str] = Field(default_factory=list, description="逐条差异，禁止只留布尔结论")
    status: ComplianceStatus = Field(..., description="QC_FAILED 或 VALIDATED")

    @model_validator(mode="after")
    def _check_consistency(self) -> "RoundTripResult":
        if self.format not in SUPPORTED_EXPORT_FORMATS:
            raise ValueError(f"不支持的对账格式：{self.format}")
        if self.status not in (ComplianceStatus.VALIDATED, ComplianceStatus.QC_FAILED):
            raise ValueError(f"对账状态只能是 VALIDATED 或 QC_FAILED，收到 {self.status.value}")
        if self.is_valid and self.discrepancies:
            raise ValueError("is_valid=True 却携带差异记录，违反 100% 一致门禁")
        if not self.is_valid and not self.discrepancies:
            raise ValueError("is_valid=False 必须给出具体差异")
        return self


# ==========================================
# 4. 五维签发
# ==========================================


class SignoffData(BaseModel):
    """真人数字签发记录：五维不可逆哈希绑定上游一切受影响依据。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1)
    translation_revision: str = Field(..., min_length=1, description="译文内容修订标识")
    rule_version: str = Field(..., min_length=1, description="规则/profile 版本")
    validation_id: str = Field(..., min_length=1, description="本次校验结论标识")
    artifact_sha256: str = Field(..., min_length=64, max_length=64, description="实际交付文件 sha256")
    signoff_hash: str = Field(..., min_length=64, max_length=64, description="五维签发哈希")
    signer_id: str = Field(..., min_length=1, description="有权真人审核员标识；机器/Agent 不得填写")
    signed_at: str = Field(..., min_length=1, description="签发时间（ISO8601，真实发生时间）")


# ==========================================
# 5. 交付产物包
# ==========================================


class ArtifactPackage(BaseModel):
    """打包后的交付产物：文件内容 + hash + 校验快照 + 重解析对账 + 签发。"""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    format: str = Field(..., description="srt / vtt")
    content: str = Field(..., description="成品文件全文；QC_FAILED 时恒为空串（不产出可交付文件）")
    artifact_sha256: str = Field(..., min_length=64, max_length=64, description="content 的 sha256")
    status: ComplianceStatus = Field(..., description="交付状态")
    validation_result: Optional[ValidationResult] = Field(None, description="校验快照")
    round_trip_result: Optional[RoundTripResult] = Field(None, description="重解析对账快照")
    signoff: Optional[SignoffData] = Field(None, description="真人签发记录")
    validation_id: Optional[str] = Field(None, description="校验结论标识，签发必须精确绑定同一 id")
    manifest: Dict[str, Any] = Field(default_factory=dict, description="model_used/token_used/版本等执行事实")

    @model_validator(mode="after")
    def _enforce_state_gates(self) -> "ArtifactPackage":
        if self.format not in SUPPORTED_EXPORT_FORMATS:
            raise ValueError(f"不支持的导出格式：{self.format}")

        # 1) 系统不得自行构造 PUBLISHED（只能据外部平台真实回执写入）
        if self.status == ComplianceStatus.PUBLISHED:
            raise ValueError(
                "PUBLISHED 只能依据外部平台真实成功回执（external_id + 回执时间戳）写入，"
                "本模块禁止构造该状态"
            )

        # 2) VALIDATED 必须有通过的技术校验快照
        if self.status == ComplianceStatus.VALIDATED:
            if self.validation_result is None:
                raise ValueError("状态 VALIDATED 必须携带 ValidationResult，不得空口称已验证")
            if not self.validation_result.is_valid:
                raise ValueError("状态 VALIDATED 却携带未通过的校验结果")

        # 3) PUBLISH_READY 必须有真人签发记录
        if self.status == ComplianceStatus.PUBLISH_READY and self.signoff is None:
            raise ValueError("状态 PUBLISH_READY 必须携带真人 SignoffData，机器不得代签")

        # 4) 未通过校验/重解析的包不得携带可交付文件
        if self.status == ComplianceStatus.QC_FAILED and self.content:
            raise ValueError("状态 QC_FAILED 时不得保留可交付文件内容（防止绕过签发直接下载）")
        return self

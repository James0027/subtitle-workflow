"""平台合规质检、多格式导出与双向重解析模块（module: compliance）。

对外导出：契约（状态/问题码/实体/产物包）+ 校验器 + 生成器 + 反解析器 + 签发。

    >>> from code.backend.modules.compliance import (
    ...     SubtitleCue, validate_and_export_artifact, build_signoff,
    ...     verify_and_apply_signoff,
    ... )
    >>> pkg = validate_and_export_artifact(
    ...     task_id="task-001", translation_revision="tr-3",
    ...     rule_version="2026-10-22.1",
    ...     cues=[SubtitleCue(index=1, start_time=0.0, end_time=2.0, text="Hola.")],
    ... )
    >>> pkg.status.value
    'VALIDATED'
    >>> signed = verify_and_apply_signoff(pkg, build_signoff(
    ...     pkg, task_id="task-001", translation_revision="tr-3",
    ...     rule_version="2026-10-22.1", validation_id=pkg.validation_id,
    ...     signer_id="reviewer-01",
    ... ))
    >>> signed.status.value
    'PUBLISH_READY'

底线提示：本模块全确定性、零模型零计费；``PUBLISHED`` 只能由外部平台真实回执写入，
模块不构造该状态；机器/Agent 不得代签（``signer_id`` 命中机器前缀直接拒绝）。
"""

from code.backend.modules.compliance.contract import (
    CJK_MAX_LINE_LENGTH,
    COMPLIANCE_ISSUE_TYPES,
    COMPLIANCE_POLICY_VERSION,
    COMPLIANCE_SCHEMA_VERSION,
    COMPLIANCE_STATUSES,
    DEFAULT_PLATFORM_PROFILE,
    LATIN_MAX_LINE_LENGTH,
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_PLATFORM_PROFILES,
    ArtifactPackage,
    ComplianceIssue,
    ComplianceIssueType,
    ComplianceStatus,
    ParsedCue,
    PlatformProfile,
    RoundTripResult,
    SignoffData,
    SubtitleCue,
    ValidationResult,
)
from code.backend.modules.compliance.handler import (
    CJK_RATIO_THRESHOLD,
    CPS_EPS,
    MACHINE_SIGNER_PREFIXES,
    ROUND_TRIP_TIME_TOLERANCE,
    RULE_DELIVERY_GATE,
    RULE_READABILITY,
    RULE_SIGNOFF,
    TIME_EPS,
    ComplianceError,
    SignoffError,
    SubtitleParseError,
    build_signoff,
    compute_signoff_hash,
    count_cjk_chars,
    count_visible_chars,
    detect_script,
    format_timecode,
    generate_srt,
    generate_vtt,
    line_char_count,
    normalize_format,
    normalize_text,
    parse_srt,
    parse_subtitle,
    parse_vtt,
    sha256_text,
    split_lines,
    validate_and_export_artifact,
    validate_platform_profile,
    verify_and_apply_signoff,
    verify_round_trip,
    visible_char_count,
)

__all__ = [
    # 契约：常量
    "CJK_MAX_LINE_LENGTH",
    "COMPLIANCE_ISSUE_TYPES",
    "COMPLIANCE_POLICY_VERSION",
    "COMPLIANCE_SCHEMA_VERSION",
    "COMPLIANCE_STATUSES",
    "DEFAULT_PLATFORM_PROFILE",
    "LATIN_MAX_LINE_LENGTH",
    "SUPPORTED_EXPORT_FORMATS",
    "SUPPORTED_PLATFORM_PROFILES",
    # 契约：模型与枚举
    "ArtifactPackage",
    "ComplianceIssue",
    "ComplianceIssueType",
    "ComplianceStatus",
    "ParsedCue",
    "PlatformProfile",
    "RoundTripResult",
    "SignoffData",
    "SubtitleCue",
    "ValidationResult",
    # 处理：常量与错误
    "CJK_RATIO_THRESHOLD",
    "CPS_EPS",
    "MACHINE_SIGNER_PREFIXES",
    "ROUND_TRIP_TIME_TOLERANCE",
    "RULE_DELIVERY_GATE",
    "RULE_READABILITY",
    "RULE_SIGNOFF",
    "TIME_EPS",
    "ComplianceError",
    "SignoffError",
    "SubtitleParseError",
    # 处理：校验器
    "validate_platform_profile",
    # 处理：生成器
    "format_timecode",
    "generate_srt",
    "generate_vtt",
    # 处理：反解析器
    "parse_srt",
    "parse_subtitle",
    "parse_vtt",
    # 处理：重解析对账
    "verify_round_trip",
    # 处理：签发
    "build_signoff",
    "compute_signoff_hash",
    "sha256_text",
    "verify_and_apply_signoff",
    # 处理：主调度
    "validate_and_export_artifact",
    # 文本口径
    "count_cjk_chars",
    "count_visible_chars",
    "detect_script",
    "line_char_count",
    "normalize_format",
    "normalize_text",
    "split_lines",
    "visible_char_count",
]

"""单位与格式本地化模块（module: unit_format）。

对外导出契约数据结构与两段式白盒处理函数：

    >>> from code.backend.modules.unit_format import (
    ...     extract_and_convert_units, UnitFormatRequest, UnitFormatUnitInput,
    ... )
    >>> result = extract_and_convert_units(UnitFormatRequest(
    ...     task_ref="task-001", task_revision=1,
    ...     units=[UnitFormatUnitInput(unit_id="u_001", target_text="Son 26.2 miles.")],
    ... ))

约束提示：货币禁止汇率折算；密码/纪录/日期等剧情线索不做机器替换；
无实体的台词整步 SKIPPED（零 Token、零延迟）。
"""

from code.backend.modules.unit_format.contract import (
    CANDIDATE_STATUSES,
    CONVERSION_POLICY_VERSION,
    DEFAULT_LOCALE,
    DEFAULT_MARKET,
    ENTITY_TYPES,
    NON_AUTO_APPLICABLE_STATUSES,
    PLOT_LOCKED_ENTITY_TYPES,
    UNIT_FORMAT_SCHEMA_VERSION,
    CandidateStatus,
    ReverseVerification,
    UnitCandidate,
    UnitEntity,
    UnitFormatRequest,
    UnitFormatResult,
    UnitFormatUnitInput,
    UnitOutcome,
)
from code.backend.modules.unit_format.handler import (
    CONVERSION_TABLE,
    FEVER_CELSIUS_THRESHOLD,
    FEVER_FAHRENHEIT_THRESHOLD,
    MULTIPLICATIVE_TOLERANCE,
    TEMPERATURE_TOLERANCE,
    ConversionSpec,
    UnitConversionError,
    assert_rounding_within_quantum,
    build_candidates_for_entity,
    convert_fahrenheit_to_celsius,
    convert_with_verification,
    extract_and_convert_units,
    extract_entities,
    format_number,
    parse_number,
    round_value,
    scan_and_convert_text,
    verify_temperature_reverse,
)

__all__ = [
    # 契约
    "CANDIDATE_STATUSES",
    "CONVERSION_POLICY_VERSION",
    "DEFAULT_LOCALE",
    "DEFAULT_MARKET",
    "ENTITY_TYPES",
    "NON_AUTO_APPLICABLE_STATUSES",
    "PLOT_LOCKED_ENTITY_TYPES",
    "UNIT_FORMAT_SCHEMA_VERSION",
    "CandidateStatus",
    "ReverseVerification",
    "UnitCandidate",
    "UnitEntity",
    "UnitFormatRequest",
    "UnitFormatResult",
    "UnitFormatUnitInput",
    "UnitOutcome",
    # 处理
    "CONVERSION_TABLE",
    "FEVER_CELSIUS_THRESHOLD",
    "FEVER_FAHRENHEIT_THRESHOLD",
    "MULTIPLICATIVE_TOLERANCE",
    "TEMPERATURE_TOLERANCE",
    "ConversionSpec",
    "UnitConversionError",
    "assert_rounding_within_quantum",
    "build_candidates_for_entity",
    "convert_fahrenheit_to_celsius",
    "convert_with_verification",
    "extract_and_convert_units",
    "extract_entities",
    "format_number",
    "parse_number",
    "round_value",
    "scan_and_convert_text",
    "verify_temperature_reverse",
]

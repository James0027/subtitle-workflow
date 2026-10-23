"""单位与格式本地化模块 —— 契约层（实体、候选、请求、响应）。

设计依据：docs/05-prd/05-subprd-unit-format.md（含 2026-10-22 两段式白盒换算与
AI 状态机规格补充）。

本层固化三条不可绕过的结构约束：

1. 原值零丢失原则：``UnitCandidate`` 必须并排暴露原值（raw_text/raw_value/raw_unit）
   与建议值（target_value/target_unit/display_text），且 ``display_text`` 必须包含
   原值字面量，界面可并排展示 ``[建议值 (原值: xxx)]``。
2. 剧情货币禁止套汇率：``entity_type == "money"`` 时 ``conversion_factor`` 恒为
   ``None``，且目标币种必须与原币种完全相同（含"符号歧义"时的同为 None）。
3. 剧情关键线索禁止机器替换：``numeric_code`` / ``record`` / ``date`` 三类实体的
   ``target_value`` / ``suggested_text`` 恒为 ``None``，状态恒为
   ``MANUAL_DECISION_REQUIRED``；凡 ``MANUAL_DECISION_REQUIRED`` /
   ``ORIGINAL_RETAINED`` / ``SKIPPED`` 状态，``auto_apply_allowed`` 必须为 False。

以上约束既在 handler 中实现，也在 pydantic 校验器中二次断言，避免下游误用。
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

UNIT_FORMAT_SCHEMA_VERSION = "1.0.0"
CONVERSION_POLICY_VERSION = "2026-10-22.1"
DEFAULT_MARKET = "MX"
DEFAULT_LOCALE = "es-MX"


# ==========================================
# 1. 实体类型与状态枚举
# ==========================================

ENTITY_TYPES = (
    "temperature",
    "distance",
    "speed",
    "money",
    "date",
    "numeric_code",
    "record",
)

# 剧情例外：机器强制剥夺自动替换权的实体类型（金额另由货币硬锁处理）
PLOT_LOCKED_ENTITY_TYPES = ("numeric_code", "record", "date")

ROUNDING_POLICIES = ("integer", "one_decimal", "none")

SCAN_STATUSES = ("SKIPPED", "PROCESSED")

EXCEPTION_FEVER = "PLOT_FEVER_TEMPERATURE"
EXCEPTION_SENSITIVE_TEMPERATURE = "SEMANTIC_SENSITIVE_TEMPERATURE"
EXCEPTION_SENSITIVE_MEASURE = "SEMANTIC_SENSITIVE_MEASUREMENT"
EXCEPTION_CURRENCY = "PLOT_CURRENCY_NO_FX"
EXCEPTION_NUMERIC_CODE = "PLOT_NUMERIC_CODE"
EXCEPTION_RECORD = "PLOT_RECORD_VALUE"
EXCEPTION_DATE = "DATE_REQUIRES_CONFIRMATION"


class CandidateStatus(str, Enum):
    """候选状态枚举（PRD §2026-10-22 补充 §3 的四态 + 跳步/待裁定两态）。

    - AI_PROPOSED：机器建议替换，待人工裁定（⚡ [AI建议]）
    - HUMAN_APPROVED：人工采纳机器换算，保留 AI 血缘（⚡ [AI生成 · 人工已确认]）
    - MANUAL_EDITED：人工在 AI 候选基础上改值（✎ [人工修改 · 基于AI候选]）
    - ORIGINAL_RETAINED：人工确认原值为剧情线索，锁定原值（🛡️ [人工锁定 · 保留源单位]）
    - SKIPPED：整步跳过（无任何实体，零 Token、零延迟），不产生候选
    - MANUAL_DECISION_REQUIRED：机器强制剥夺自动替换权，等待人工裁定
    """

    AI_PROPOSED = "AI_PROPOSED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    MANUAL_EDITED = "MANUAL_EDITED"
    ORIGINAL_RETAINED = "ORIGINAL_RETAINED"
    SKIPPED = "SKIPPED"
    MANUAL_DECISION_REQUIRED = "MANUAL_DECISION_REQUIRED"


CANDIDATE_STATUSES = tuple(status.value for status in CandidateStatus)

# 机器不得自动落盘的终态/挂起态
NON_AUTO_APPLICABLE_STATUSES = (
    CandidateStatus.MANUAL_DECISION_REQUIRED.value,
    CandidateStatus.ORIGINAL_RETAINED.value,
    CandidateStatus.SKIPPED.value,
)


def _numeric_literal(text: str) -> float:
    """把原值字面量解析为浮点（仅用于契约断言，不参与生产换算）。

    分隔符处理：若同时出现 "," 与 "."，按英文习惯（"," 千分位，"." 小数）；
    仅出现 "," 且后接 1-2 位数字时，按小数逗号解析（es-MX 常见写法）。
    """
    cleaned = text.strip().replace(" ", "").replace("\u00a0", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        head, _, tail = cleaned.rpartition(",")
        if head and 1 <= len(tail) <= 2:
            cleaned = f"{head}.{tail}"
        else:
            cleaned = cleaned.replace(",", "")
    return float(cleaned)


# ==========================================
# 2. 请求契约（客户端 -> 服务端）
# ==========================================

class UnitFormatUnitInput(BaseModel):
    """待处理的单条字幕单元（默认读人工修订后的目标稿）。"""

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(..., min_length=1, description="对话单元编号，如 u_001")
    target_text: str = Field(..., min_length=1, description="待本地化的目标语言台词")
    source_text: Optional[str] = Field(None, description="源语台词，仅供对照，不参与本模块换算")
    input_revision: int = Field(1, ge=1, description="目标稿修订版本")
    prev_context: Optional[str] = Field(None, description="前一句上下文（仅用于语境分类）")
    next_context: Optional[str] = Field(None, description="后一句上下文（仅用于语境分类）")


class UnitFormatRequest(BaseModel):
    """单位与格式本地化单模块任务请求。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(UNIT_FORMAT_SCHEMA_VERSION, description="Schema 版本")
    task_ref: str = Field(..., min_length=1, description="任务编号")
    task_revision: int = Field(..., ge=1, description="当前任务修订版本")
    target_language: str = Field(DEFAULT_LOCALE, description="目标语言变体，首批固定 es-MX")
    target_market: str = Field(DEFAULT_MARKET, description="目标市场代码，首批固定 MX")
    conversion_policy_ref: str = Field(
        f"conversion-policy:{CONVERSION_POLICY_VERSION}",
        description="换算策略引用；公式/精度/舍入版本随候选固化",
    )
    units: List[UnitFormatUnitInput] = Field(..., min_length=1, description="待处理字幕单元")

    @model_validator(mode="after")
    def _check_units(self) -> "UnitFormatRequest":
        ids = [unit.unit_id for unit in self.units]
        if len(ids) != len(set(ids)):
            raise ValueError("units 中存在重复的 unit_id")
        for unit in self.units:
            if not unit.target_text.strip():
                raise ValueError(f"unit {unit.unit_id} 的 target_text 为空")
        return self


# ==========================================
# 3. 实体抽取结果
# ==========================================

class UnitEntity(BaseModel):
    """一条被识别出的度量衡/格式实体（原值字面量完整保留）。"""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=1, description="实体编号，如 u_001-e001")
    unit_id: str = Field(..., min_length=1, description="所属字幕单元")
    entity_type: str = Field(..., description="实体类型，见 ENTITY_TYPES")
    raw_text: str = Field(..., min_length=1, description="实体在台词中的原始文本")
    raw_value: str = Field(..., min_length=1, description="原值字面量，零丢失")
    raw_unit: Optional[str] = Field(None, description="原单位/币种/格式标记")
    start_char: int = Field(..., ge=0, description="实体起始字符偏移")
    end_char: int = Field(..., ge=0, description="实体结束字符偏移（不含）")
    context_flags: List[str] = Field(default_factory=list, description="语境标记，如 FEVER_CONTEXT")

    @model_validator(mode="after")
    def _check_span(self) -> "UnitEntity":
        if self.entity_type not in ENTITY_TYPES:
            raise ValueError(f"未知实体类型：{self.entity_type}")
        if self.end_char <= self.start_char:
            raise ValueError(f"实体 {self.entity_id} 的字符跨度非法")
        if not self.raw_text.strip() or not self.raw_value.strip():
            raise ValueError(f"实体 {self.entity_id} 必须保留非空原值")
        return self


# ==========================================
# 4. 候选契约（不覆盖终稿的建议版本）
# ==========================================

class ReverseVerification(BaseModel):
    """确定性反向验算记录（不得留空冒充已验算）。"""

    model_config = ConfigDict(extra="forbid")

    performed: bool = Field(..., description="是否执行了反向验算")
    passed: bool = Field(..., description="反向验算是否通过")
    tolerance: Optional[float] = Field(None, description="容差")
    residual: Optional[float] = Field(None, description="实测残差")
    formula: Optional[str] = Field(None, description="反向验算公式与代入值")


class UnitCandidate(BaseModel):
    """单条单位换算/格式规范化候选：原值与建议值并排暴露，原值永久保留。"""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    unit_id: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., description="实体类型")
    candidate_kind: str = Field("unit_change", description="候选种类，本模块固定 unit_change")

    # --- 原值（零丢失，永久可回查）---
    raw_text: str = Field(..., min_length=1, description="原始文本")
    raw_value: str = Field(..., min_length=1, description="原值字面量")
    raw_unit: Optional[str] = Field(None, description="原单位/币种")

    # --- 建议值 ---
    target_value: Optional[float] = Field(None, description="建议数值；剧情例外不得给出替换值")
    target_unit: Optional[str] = Field(None, description="建议单位/币种")
    display_text: str = Field(..., min_length=1, description="界面并排展示文本：建议值 (原值: xxx)")
    suggested_text: Optional[str] = Field(None, description="可替换片段的建议文本；例外项恒 None")

    # --- 计算依据 ---
    conversion_factor: Optional[float] = Field(None, description="乘法换算因子；货币恒为 None")
    conversion_formula: Optional[str] = Field(None, description="换算公式")
    conversion_formula_version: str = Field(CONVERSION_POLICY_VERSION, description="公式版本")
    rounding_policy: str = Field("integer", description="integer / one_decimal / none")

    raw_currency_code: Optional[str] = Field(None, description="原币种 ISO 代码；符号歧义时为 None")
    target_currency_code: Optional[str] = Field(None, description="目标币种 ISO 代码，必须与原币种一致")

    reverse_verification: ReverseVerification = Field(..., description="确定性反向验算记录")

    # --- 状态与例外 ---
    status: CandidateStatus = Field(CandidateStatus.AI_PROPOSED, description="候选状态（六态）")
    plot_exception: bool = Field(False, description="是否命中剧情例外硬锁")
    exception_reason: Optional[str] = Field(None, description="例外原因代码")
    auto_apply_allowed: bool = Field(False, description="是否允许机器自动落盘（例外项恒 False）")
    rationale: str = Field(..., min_length=1, description="判断与计算依据说明")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="原值、公式、精度、策略版本等证据")

    @model_validator(mode="after")
    def _enforce_zero_loss_and_plot_guard(self) -> "UnitCandidate":
        if self.entity_type not in ENTITY_TYPES:
            raise ValueError(f"未知实体类型：{self.entity_type}")
        if self.rounding_policy not in ROUNDING_POLICIES:
            raise ValueError(f"未知舍入策略：{self.rounding_policy}")

        # 1) 原值零丢失：原值必须出现在界面展示文本中
        if self.raw_value not in self.display_text and self.raw_text not in self.display_text:
            raise ValueError(
                f"候选 {self.candidate_id} 的展示文本未并排保留原值，违反原值零丢失原则"
            )

        # 2) 货币硬锁：禁止汇率折算、禁止改币种、禁止改金额
        if self.entity_type == "money":
            if self.conversion_factor is not None:
                raise ValueError(f"候选 {self.candidate_id} 为货币，严禁携带汇率/换算因子")
            if self.target_currency_code != self.raw_currency_code:
                raise ValueError(
                    f"候选 {self.candidate_id} 试图变更币种"
                    f"（{self.raw_currency_code} -> {self.target_currency_code}），违反剧情货币硬锁"
                )
            if self.target_value is None:
                raise ValueError(f"候选 {self.candidate_id} 为货币，必须保留原金额数值")
            if abs(self.target_value - _numeric_literal(self.raw_value)) > 0.005:
                raise ValueError(
                    f"候选 {self.candidate_id} 变更了金额数值，违反剧情货币硬锁"
                )

        # 3) 剧情关键线索：密码、纪录、日期不做机器替换
        if self.entity_type in PLOT_LOCKED_ENTITY_TYPES:
            if self.target_value is not None or self.suggested_text is not None:
                raise ValueError(
                    f"候选 {self.candidate_id}（{self.entity_type}）不得生成机器替换值"
                )
            if self.status != CandidateStatus.MANUAL_DECISION_REQUIRED:
                raise ValueError(
                    f"候选 {self.candidate_id}（{self.entity_type}）必须为 MANUAL_DECISION_REQUIRED"
                )

        # 4) 机器自动落盘权：仅 AI_PROPOSED 且通过反向验算
        if self.status == CandidateStatus.AI_PROPOSED:
            if not (self.reverse_verification.performed and self.reverse_verification.passed):
                raise ValueError(f"候选 {self.candidate_id} 为 AI_PROPOSED 却未通过反向验算")
        if self.status in NON_AUTO_APPLICABLE_STATUSES and self.auto_apply_allowed:
            raise ValueError(
                f"候选 {self.candidate_id} 状态为 {self.status.value}，不得允许机器自动落盘"
            )

        # 5) 证据中必须保留原值
        if self.evidence.get("raw_text") != self.raw_text:
            raise ValueError(f"候选 {self.candidate_id} 的 evidence 未记录原值文本")
        return self


# ==========================================
# 5. 响应契约（服务端 -> 客户端）
# ==========================================

class UnitOutcome(BaseModel):
    """单条字幕单元的处理结果（含跳步事实）。"""

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(..., min_length=1)
    status: str = Field(..., description="SKIPPED / PROCESSED")
    entity_count: int = Field(0, ge=0)
    candidate_count: int = Field(0, ge=0)
    token_used: int = Field(0, ge=0)
    latency_ms: int = Field(0, ge=0)
    reason: Optional[str] = Field(None, description="跳步或阻断原因")

    @model_validator(mode="after")
    def _check_status(self) -> "UnitOutcome":
        if self.status not in SCAN_STATUSES:
            raise ValueError(f"未知处理状态：{self.status}")
        if self.status == "SKIPPED" and (self.entity_count or self.candidate_count):
            raise ValueError(f"unit {self.unit_id} 标记 SKIPPED 却存在实体/候选")
        if self.status == "SKIPPED" and self.token_used:
            raise ValueError(f"unit {self.unit_id} 标记 SKIPPED 却记录了 Token 消耗")
        return self


class UnitFormatResult(BaseModel):
    """单位与格式本地化完整交付产物。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(UNIT_FORMAT_SCHEMA_VERSION)
    run_id: str = Field(..., min_length=1)
    task_ref: str = Field(..., min_length=1)
    task_revision: int = Field(..., ge=1)
    target_language: str = Field(DEFAULT_LOCALE)
    target_market: str = Field(DEFAULT_MARKET)
    status: str = Field(..., description="整体状态：SKIPPED 表示全范围无实体")
    entities: List[UnitEntity] = Field(default_factory=list)
    candidates: List[UnitCandidate] = Field(default_factory=list)
    unit_outcomes: List[UnitOutcome] = Field(default_factory=list)
    manifest: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_result(self) -> "UnitFormatResult":
        if self.status not in SCAN_STATUSES:
            raise ValueError(f"未知整体状态：{self.status}")
        if self.status == "SKIPPED" and (self.entities or self.candidates):
            raise ValueError("整体状态为 SKIPPED 时不得返回实体或候选")
        if self.status == "PROCESSED" and not self.entities:
            raise ValueError("整体状态为 PROCESSED 时必须返回实体，禁止空输出冒充已检查")
        return self

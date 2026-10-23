"""口语适配与节奏审校模块 —— 契约层（实体、度量、候选、请求、响应）。

设计依据：docs/05-prd/06-subprd-oral-review.md §10（2026-10-22 口语审校与节奏优化
规格补充）、docs/03-foundation/rule-registry.md（RULE-ORAL-001/002、P-ORAL）、
docs/03-foundation/metrics.md（MET-ORAL-001/002/003）。

本层固化四条不可绕过的结构约束：

1. 可读性度量必须自洽：``is_duration_valid=False`` 时 ``cps`` 必须为 ``None``（非法
   时长不参与 CPS 美化），且 ``DURATION_INVALID`` 必须出现在 ``issues`` 中；``lines``
   与 ``line_count`` / ``max_line_length`` 必须逐一对应。
2. 无损拆句不得暗改时间轴：``SplitSegmentCandidate.duration_sec`` 必须等于
   ``end_time - start_time``，字符数必须等于文本长度（禁止伪造统计）。
3. 四重语义保护硬闸门：``guard_check.is_blocked=True`` 时，候选必须
   ``is_blocked=True`` 且 ``auto_apply_allowed=False``（违规候选一律废弃）；
   反之未阻断的候选不得自我声明 ``is_blocked=True``。
4. 零外部模型：``OralReviewResult.manifest`` 必须显式写 ``model_used=False``、
   ``token_used=0``；不得用空 manifest 冒充"已检查"。

以上约束在 handler 中实现，并在 pydantic 校验器中二次断言，避免下游误用。
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ORAL_REVIEW_SCHEMA_VERSION = "1.0.0"
ORAL_POLICY_VERSION = "2026-10-22.1"
DEFAULT_LOCALE = "es-MX"

# --- P-ORAL 阈值（Latin 软/硬 CPS、行长、行数、时长极值）---
# 说明：P-ORAL 数值尚未经每语种 ≥500 条合格字幕校准，此处仅为试点软/硬阈值常量，
# 未经批准不得当作生产签发门槛（rule-registry P-ORAL）。
CPS_SOFT_LIMIT = 17.0        # 软阈值：超过即 WARN（标黄提示）
CPS_HARD_LIMIT = 20.0        # 硬阈值：超过即 BLOCK（阻断合格交付包）
MAX_LINE_LENGTH = 42         # Latin 行长上限（字符）
MAX_LINE_COUNT = 2           # 行数上限
MIN_DURATION_SEC = 0.833     # 极短时长下限（≈0.83s）
MAX_DURATION_SEC = 7.0       # 超长时长上限（超出提示拆分/延时）

# --- 复杂度与拆句 ---
COMPLEX_CONJUNCTION_THRESHOLD = 2   # 从属连词 ≥2 个即判复杂句
NESTING_DEPTH_THRESHOLD = 4         # 嵌套深度 >4 即判复杂句（无依存树时的确定性代理）
SPLIT_TIME_TOLERANCE = 0.001        # 拆句总时长绝对吻合容差（秒）
MIN_SPLIT_PART_DURATION = MIN_DURATION_SEC

# --- 翻译腔 ---
WRITTEN_SCORE_WARN_THRESHOLD = 0.75


class ReadabilityStatus(str, Enum):
    """可读性状态：PASS 通过、WARN 标黄提示、BLOCK 阻断合格交付包。"""

    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


_READABILITY_RANK = {
    ReadabilityStatus.PASS: 0,
    ReadabilityStatus.WARN: 1,
    ReadabilityStatus.BLOCK: 2,
}


def worst_status(*statuses: ReadabilityStatus) -> ReadabilityStatus:
    """返回最差状态（PASS < WARN < BLOCK）；无输入视为 PASS。"""
    worst = ReadabilityStatus.PASS
    for status in statuses:
        if _READABILITY_RANK[status] > _READABILITY_RANK[worst]:
            worst = status
    return worst


class ReadabilityIssueType(str, Enum):
    """可读性问题码（RULE-ORAL-001 / MET-ORAL-001）。"""

    CPS_WARN = "CPS_WARN"                          # 17 < CPS <= 20，标黄
    CPS_BLOCK = "CPS_BLOCK"                        # CPS > 20，阻断
    LINE_LENGTH_EXCEEDED = "LINE_LENGTH_EXCEEDED"  # 单行 > 42 字符
    LINE_COUNT_EXCEEDED = "LINE_COUNT_EXCEEDED"    # 行数 > 2
    DURATION_TOO_SHORT = "DURATION_TOO_SHORT"      # < 0.833s
    DURATION_TOO_LONG = "DURATION_TOO_LONG"        # > 7.0s
    DURATION_INVALID = "DURATION_INVALID"          # <= 0s，硬非法


class ComplexityType(str, Enum):
    """复杂度打标（§10.1）。"""

    COMPLEX_SENTENCE = "COMPLEX_SENTENCE"


class DeviationType(str, Enum):
    """口语偏离打标（§10.2）。"""

    ORAL_DEVIATION_WARN = "ORAL_DEVIATION_WARN"


class SemanticViolationType(str, Enum):
    """四类语义风险规则检查违规码（§10.3）；任一命中即 BLOCK 并废弃候选。"""

    POLARITY_MISMATCH = "POLARITY_MISMATCH"
    ENTITY_MISMATCH = "ENTITY_MISMATCH"
    RELATIONSHIP_MISMATCH = "RELATIONSHIP_MISMATCH"
    STANCE_MISMATCH = "STANCE_MISMATCH"


READABILITY_ISSUE_CODES = tuple(item.value for item in ReadabilityIssueType)
SEMANTIC_VIOLATION_CODES = tuple(item.value for item in SemanticViolationType)


# ==========================================
# 1. 输入契约
# ==========================================

class CharacterContext(BaseModel):
    """人物语境卡：称谓/立场/反讽由人工或上游模块给定，本模块只读不改。"""

    model_config = ConfigDict(extra="forbid")

    speaker: Optional[str] = Field(None, description="说话人")
    listener: Optional[str] = Field(None, description="听话人")
    honorific_register: Optional[str] = Field(
        None, description="称谓 register，如 formal / informal / usted / tu"
    )
    stance: Optional[str] = Field(
        None, description="情绪立场，如 hostile / polite / neutral / sarcastic"
    )
    is_sarcastic: bool = Field(False, description="是否反讽（反讽含义不得被改写抹平）")


class SubtitleSegment(BaseModel):
    """单条待审字幕句（时间轴来自上游 ASR/对齐，本模块不改原时间轴）。"""

    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(..., min_length=1, description="句子编号，如 seg_001")
    text: str = Field("", description="目标语字幕文本（可含换行符分行）")
    start_time: float = Field(..., description="起始时间（秒）")
    end_time: float = Field(..., description="结束时间（秒）")
    speaker_id: Optional[str] = Field(None, description="说话人编号")
    context: Optional[CharacterContext] = Field(None, description="人物语境卡")


class OralReviewRequest(BaseModel):
    """口语审校单模块任务请求。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(ORAL_REVIEW_SCHEMA_VERSION)
    request_id: str = Field(..., min_length=1, description="请求/运行编号")
    task_ref: Optional[str] = Field(None, description="任务标识；若提供必须与路径任务一致")
    target_language: str = Field(DEFAULT_LOCALE, description="目标语言变体，首批固定 es-MX")
    segments: List[SubtitleSegment] = Field(..., min_length=1, description="待审字幕句")

    @model_validator(mode="after")
    def _check_segments(self) -> "OralReviewRequest":
        ids = [segment.segment_id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segments 中存在重复的 segment_id")
        return self


# ==========================================
# 2. 可读性度量
# ==========================================

class ReadabilityMetrics(BaseModel):
    """单句可读性度量（MET-ORAL-001 的可复算基础：字符策略 + 显示秒数）。"""

    model_config = ConfigDict(extra="forbid")

    visible_char_count: int = Field(..., ge=0, description="可见字符数（含词间单空格与标点）")
    duration_sec: float = Field(..., description="显示时长 = end_time - start_time（秒）")
    cps: Optional[float] = Field(None, description="字符/秒；时长为硬非法时恒 None")
    line_count: int = Field(..., ge=1, description="行数（以 \\n 分行）")
    max_line_length: int = Field(..., ge=0, description="最长行字符数")
    lines: List[str] = Field(..., description="分行文本（已去首尾空白）")
    is_duration_valid: bool = Field(..., description="时长是否合法（> 0）")
    cps_status: ReadabilityStatus = Field(...)
    line_status: ReadabilityStatus = Field(...)
    duration_status: ReadabilityStatus = Field(...)
    issues: List[str] = Field(default_factory=list, description="问题码，见 ReadabilityIssueType")
    syntax_line_break_suggestion: Optional[str] = Field(
        None, description="断行建议（行超限时给出，含 \\n）"
    )

    @model_validator(mode="after")
    def _check_internal_consistency(self) -> "ReadabilityMetrics":
        if self.line_count != len(self.lines):
            raise ValueError(
                f"line_count={self.line_count} 与 lines 条数 {len(self.lines)} 不一致"
            )
        expected_max = max((len(line) for line in self.lines), default=0)
        if self.max_line_length != expected_max:
            raise ValueError(
                f"max_line_length={self.max_line_length} 与实测 {expected_max} 不一致"
            )
        unknown = [code for code in self.issues if code not in READABILITY_ISSUE_CODES]
        if unknown:
            raise ValueError(f"未知可读性问题码：{unknown}")

        # 硬非法时长：cps 必须缺省，且必须登记 DURATION_INVALID
        if not self.is_duration_valid:
            if self.cps is not None:
                raise ValueError("时长为硬非法时不得给出 CPS（禁止用 CPS 美化非法时长）")
            if ReadabilityIssueType.DURATION_INVALID.value not in self.issues:
                raise ValueError("时长为硬非法时必须登记 DURATION_INVALID")
            if self.duration_status != ReadabilityStatus.BLOCK:
                raise ValueError("时长为硬非法时 duration_status 必须为 BLOCK")
        else:
            if self.cps is None:
                raise ValueError("时长合法时必须给出 CPS")
            if ReadabilityIssueType.DURATION_INVALID.value in self.issues:
                raise ValueError("时长合法却登记了 DURATION_INVALID")

        # CPS 问题码与 cps_status 必须互相印证（时长为硬非法时 CPS 不可评价，
        # 不得伪造 CPS_* 问题码，但 cps_status 仍按阻断处理）
        if self.cps_status == ReadabilityStatus.BLOCK and self.cps is not None:
            if ReadabilityIssueType.CPS_BLOCK.value not in self.issues:
                raise ValueError("cps_status=BLOCK 时必须登记 CPS_BLOCK")
        if self.cps_status == ReadabilityStatus.WARN:
            if self.cps is None:
                raise ValueError("CPS 不可评价时不得声明 WARN")
            if ReadabilityIssueType.CPS_WARN.value not in self.issues:
                raise ValueError("cps_status=WARN 时必须登记 CPS_WARN")
        return self


class SplitSegmentCandidate(BaseModel):
    """无损拆句子句：时间连续、总时长与原句严格吻合。"""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(..., ge=0, description="子句序号，从 0 起")
    text: str = Field(..., min_length=1, description="子句文本")
    start_time: float = Field(..., description="子句起始（秒）")
    end_time: float = Field(..., description="子句结束（秒）")
    duration_sec: float = Field(..., ge=0, description="子句时长 = end - start")
    char_count: int = Field(..., ge=1, description="子句字符数，必须等于 len(text)")

    @model_validator(mode="after")
    def _check_duration_and_chars(self) -> "SplitSegmentCandidate":
        if self.end_time < self.start_time:
            raise ValueError(f"子句 {self.part_index} 的 end_time 早于 start_time")
        measured = self.end_time - self.start_time
        if abs(measured - self.duration_sec) > SPLIT_TIME_TOLERANCE:
            raise ValueError(
                f"子句 {self.part_index} 的 duration_sec={self.duration_sec} "
                f"与 end-start={measured} 不一致（禁止伪造时长）"
            )
        if self.char_count != len(self.text):
            raise ValueError(
                f"子句 {self.part_index} 的 char_count={self.char_count} "
                f"与文本长度 {len(self.text)} 不一致"
            )
        return self


# ==========================================
# 3. 复杂度与口语偏离
# ==========================================

class ComplexityAnalysis(BaseModel):
    """从句复杂度判定与无损拆句建议（§10.1）。"""

    model_config = ConfigDict(extra="forbid")

    is_complex: bool = Field(..., description="是否判为复杂句")
    subordinate_conjunction_count: int = Field(..., ge=0, description="从属连词出现次数")
    detected_conjunctions: List[str] = Field(default_factory=list, description="命中的从属连词")
    nesting_depth: int = Field(
        ..., ge=0, description="从句嵌套深度（确定性代理：主句 1 + 同一句内连词数）"
    )
    issue_tag: Optional[str] = Field(None, description="打标，复杂句为 COMPLEX_SENTENCE")
    split_suggestion: Optional[List[SplitSegmentCandidate]] = Field(
        None, description="时间连续的无损拆句方案；无法满足约束时为 None"
    )

    @model_validator(mode="after")
    def _check_tag(self) -> "ComplexityAnalysis":
        if self.is_complex != (self.issue_tag == ComplexityType.COMPLEX_SENTENCE.value):
            raise ValueError("is_complex 与 issue_tag 不一致")
        if self.is_complex:
            reached_count = self.subordinate_conjunction_count >= COMPLEX_CONJUNCTION_THRESHOLD
            reached_depth = self.nesting_depth > NESTING_DEPTH_THRESHOLD
            if not (reached_count or reached_depth):
                raise ValueError("判为复杂句但连词数与嵌套深度均未达阈值（不得凭空打标）")
        return self


class OralDeviationAnalysis(BaseModel):
    """翻译腔/书面语偏离度（§10.2）：written_score > 0.75 标黄并给地道口语候选。"""

    model_config = ConfigDict(extra="forbid")

    written_score: float = Field(..., ge=0.0, le=1.0, description="书面语倾向分，0—1")
    is_warn: bool = Field(..., description="是否触发 ORAL_DEVIATION_WARN")
    detected_written_terms: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="命中的书面词及口语候选：[{term, matched, oral_candidates, rationale}]",
    )
    suggested_rewrite: Optional[str] = Field(None, description="确定性替换后的口语化改写文本")

    @model_validator(mode="after")
    def _check_warn_flag(self) -> "OralDeviationAnalysis":
        if self.is_warn != (self.written_score > WRITTEN_SCORE_WARN_THRESHOLD):
            raise ValueError(
                "is_warn 必须严格等于 (written_score > "
                f"{WRITTEN_SCORE_WARN_THRESHOLD})，不得手工放宽/收紧"
            )
        for item in self.detected_written_terms:
            if not item.get("term") or not item.get("oral_candidates"):
                raise ValueError("书面词命中项必须包含 term 与 oral_candidates（可解释替换）")
        return self


# ==========================================
# 4. 四重语义保护
# ==========================================

class SemanticGuardCheck(BaseModel):
    """四重语义保护闸门结果（§10.3）；任一违规即 BLOCK 并废弃改写候选。"""

    model_config = ConfigDict(extra="forbid")

    polarity_consistent: bool = Field(...)
    entity_consistent: bool = Field(...)
    relationship_consistent: bool = Field(...)
    stance_consistent: bool = Field(...)
    violations: List[str] = Field(default_factory=list, description="违规码，见 SemanticViolationType")
    is_blocked: bool = Field(..., description="是否阻断（任一违规即 True）")
    block_reasons: List[str] = Field(default_factory=list, description="可读的阻断理由")

    @model_validator(mode="after")
    def _check_gate(self) -> "SemanticGuardCheck":
        unknown = [code for code in self.violations if code not in SEMANTIC_VIOLATION_CODES]
        if unknown:
            raise ValueError(f"未知语义违规码：{unknown}")
        if self.is_blocked != bool(self.violations):
            raise ValueError("is_blocked 必须严格等于 (violations 非空)")
        if self.is_blocked and not self.block_reasons:
            raise ValueError("阻断必须给出 block_reasons，不得只给标志位")
        flags = {
            SemanticViolationType.POLARITY_MISMATCH.value: self.polarity_consistent,
            SemanticViolationType.ENTITY_MISMATCH.value: self.entity_consistent,
            SemanticViolationType.RELATIONSHIP_MISMATCH.value: self.relationship_consistent,
            SemanticViolationType.STANCE_MISMATCH.value: self.stance_consistent,
        }
        for code in self.violations:
            if flags[code]:
                raise ValueError(f"违规码 {code} 与对应一致标志位矛盾")
        return self


# ==========================================
# 5. 候选与单句结果
# ==========================================

class OralCandidate(BaseModel):
    """口语适配候选：原句永久保留，建议另存，绝不写入已确认/锁定稿（RULE-SUB-001）。"""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., min_length=1)
    original_text: str = Field(..., min_length=1, description="原句（零丢失）")
    suggested_text: Optional[str] = Field(None, description="口语化改写建议（确定性规则生成）")
    split_candidates: Optional[List[SplitSegmentCandidate]] = Field(
        None, description="时间连续拆句方案"
    )
    guard_check: SemanticGuardCheck = Field(..., description="四重语义保护结果")
    is_blocked: bool = Field(..., description="候选是否被硬闸门阻断废弃")
    auto_apply_allowed: bool = Field(..., description="是否允许自动流转（仍不得写入锁定稿）")
    explanation: str = Field(..., min_length=1, description="判断依据与改写理由")

    @model_validator(mode="after")
    def _enforce_guard_gate(self) -> "OralCandidate":
        # 闸门硬约束：阻断候选一律废弃，禁止自动落盘
        if self.guard_check.is_blocked:
            if not self.is_blocked:
                raise ValueError(f"候选 {self.candidate_id} 的闸门已阻断却声明 is_blocked=False")
            if self.auto_apply_allowed:
                raise ValueError(
                    f"候选 {self.candidate_id} 被语义闸门阻断，禁止 auto_apply_allowed=True"
                )
            if self.suggested_text is None and not self.split_candidates:
                raise ValueError(f"候选 {self.candidate_id} 既无改写也无拆句，属空候选")
            return self

        if self.is_blocked:
            raise ValueError(f"候选 {self.candidate_id} 未触发任何违规却声明 is_blocked=True")
        if self.suggested_text is None and not self.split_candidates:
            raise ValueError(f"候选 {self.candidate_id} 既无改写也无拆句，属空候选")
        # 拆句必须保持原句文本无损 + 时间连续
        if self.split_candidates:
            joined = " ".join(part.text.strip() for part in self.split_candidates)
            if self._normalize(joined) != self._normalize(self.original_text):
                raise ValueError(
                    f"候选 {self.candidate_id} 的拆句文本与原句不一致（声称无损却丢字）"
                )
            total = sum(part.duration_sec for part in self.split_candidates)
            span = self.split_candidates[-1].end_time - self.split_candidates[0].start_time
            if abs(total - span) > SPLIT_TIME_TOLERANCE:
                raise ValueError(f"候选 {self.candidate_id} 的拆句时长求和不连续")
            for previous, current in zip(self.split_candidates, self.split_candidates[1:]):
                if abs(previous.end_time - current.start_time) > SPLIT_TIME_TOLERANCE:
                    raise ValueError(
                        f"候选 {self.candidate_id} 的拆句时间轴不连续"
                        f"（{previous.end_time} != {current.start_time}）"
                    )
        return self

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())


class OralReviewItemResult(BaseModel):
    """单句审校结果。"""

    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(..., min_length=1)
    original_text: str = Field(..., description="原句文本")
    readability: ReadabilityMetrics = Field(...)
    complexity: ComplexityAnalysis = Field(...)
    deviation: OralDeviationAnalysis = Field(...)
    candidate: Optional[OralCandidate] = Field(None, description="无任何建议时为 None")
    status: ReadabilityStatus = Field(..., description="单句结论状态")

    @model_validator(mode="after")
    def _check_status(self) -> "OralReviewItemResult":
        # 候选被阻断 → 该句必须进入人工复核，不得随包自动交付
        if self.candidate is not None and self.candidate.is_blocked:
            if self.status != ReadabilityStatus.BLOCK:
                raise ValueError(
                    f"句 {self.segment_id} 的候选被语义闸门阻断，status 必须为 BLOCK"
                )
        if self.readability.cps_status == ReadabilityStatus.BLOCK:
            if self.status != ReadabilityStatus.BLOCK:
                raise ValueError(f"句 {self.segment_id} CPS 硬超限，status 必须为 BLOCK")
        return self


# ==========================================
# 6. 响应契约
# ==========================================

class OralReviewResult(BaseModel):
    """口语审校完整交付产物（含 manifest 溯源）。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(..., min_length=1)
    task_ref: Optional[str] = Field(None, description="任务标识")
    run_id: Optional[str] = Field(None, description="运行标识")
    items: List[OralReviewItemResult] = Field(..., min_length=1)
    manifest: Dict[str, Any] = Field(..., description="溯源与成本清单")
    overall_status: ReadabilityStatus = Field(..., description="整批最差状态")

    @model_validator(mode="after")
    def _check_result(self) -> "OralReviewResult":
        expected = worst_status(*(item.status for item in self.items))
        if self.overall_status != expected:
            raise ValueError(
                f"overall_status={self.overall_status.value} "
                f"与逐句最差状态 {expected.value} 不一致"
            )
        # 零外部模型硬声明：不得省略、不得伪造调用
        if self.manifest.get("model_used") is not False:
            raise ValueError("manifest 必须显式声明 model_used=False（本模块零外部模型）")
        if self.manifest.get("token_used") != 0:
            raise ValueError("manifest 必须显式声明 token_used=0")
        if self.manifest.get("model_invocation") != "NOT_INVOKED":
            raise ValueError("manifest 必须显式声明 model_invocation=NOT_INVOKED")
        return self

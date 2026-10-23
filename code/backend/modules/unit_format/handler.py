"""单位与格式本地化模块 —— 两段式白盒处理器。

第一段（纯工程，本文件实现）：
    正则/规则扫描实体 → 无实体整步 SKIP（零 Token、零延迟）→ 有标准物理单位时由
    Python 做确定性换算 + 数学反向验算 + 舍入。

第二段（语境与例外分类）：
    PRD 规定由 AI 只做语境分类、不做算术。本轮未获模型调用授权，故以**确定性规则
    分类器**（关键词 + 阈值）实现同等硬约束：命中发烧体温、密码/PIN、比赛纪录、
    日期、货币即强制置 ``MANUAL_DECISION_REQUIRED``，剥夺机器自动替换权，
    manifest 明确标注 ``model_used=False``，不伪造模型调用。

数值权威性：
    - 距离/速度：``abs(target * factor ** -1 - raw) < 0.01``；
    - 温度：``abs(target_c * 9 / 5 + 32 - raw_f) < 0.05``；
    - 另加**参考常数交叉验算**（以 SI 定义米为基准独立推导），防止"因子被改坏但
      自洽"的静默错误；任一验算超差立即抛 ``UnitConversionError``（ValueError 子类），
      绝不输出未经反向验算的数值。
"""

import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from code.backend.modules.unit_format.contract import (
    CONVERSION_POLICY_VERSION,
    EXCEPTION_CURRENCY,
    EXCEPTION_DATE,
    EXCEPTION_FEVER,
    EXCEPTION_NUMERIC_CODE,
    EXCEPTION_RECORD,
    EXCEPTION_SENSITIVE_MEASURE,
    EXCEPTION_SENSITIVE_TEMPERATURE,
    CandidateStatus,
    ReverseVerification,
    UnitCandidate,
    UnitEntity,
    UnitFormatRequest,
    UnitFormatResult,
    UnitOutcome,
)

# ==========================================
# 0. 常量与错误类型
# ==========================================

MULTIPLICATIVE_TOLERANCE = 0.01
TEMPERATURE_TOLERANCE = 0.05
CURRENCY_IDENTITY_TOLERANCE = 0.005

FEVER_FAHRENHEIT_THRESHOLD = 99.5
FEVER_CELSIUS_THRESHOLD = 37.5


class UnitConversionError(ValueError):
    """确定性换算/反向验算失败。继承 ValueError，调用方必须阻断替换。"""


# ==========================================
# 1. 确定性换算表（含独立参考常数）
# ==========================================

# 以 SI 定义米为唯一基准的参考常数，与生产因子分开维护：
# 生产因子被误改时，交叉验算会立即失败，而不是"自洽地算错"。
_REFERENCE_METERS: Dict[str, float] = {
    "mile": 1609.344,      # 国际英里（1959 协定）
    "foot": 0.3048,        # 国际英尺 = 0.3048 m
    "inch": 0.0254,        # 国际英寸 = 0.0254 m
    "yard": 0.9144,        # 国际码 = 0.9144 m
    "meter": 1.0,
    "cm": 0.01,
    "km": 1000.0,
}


@dataclass
class ConversionSpec:
    """一条乘法换算规格：生产因子 + 独立参考因子 + 公式说明。"""

    from_unit: str
    to_unit: str
    factor: float
    reference_factor: float
    formula: str
    category: str


def _ratio(unit_from: str, unit_to: str) -> float:
    """由 SI 基准独立推导参考因子（不读取生产因子）。"""
    return _REFERENCE_METERS[unit_from] / _REFERENCE_METERS[unit_to]


CONVERSION_TABLE: Dict[Tuple[str, str], ConversionSpec] = {
    ("mile", "km"): ConversionSpec(
        "mile", "km", 1.609344, _ratio("mile", "km"),
        "km = mile × 1.609344", "distance",
    ),
    ("foot", "m"): ConversionSpec(
        "foot", "m", 0.3048, _ratio("foot", "meter"),
        "m = foot × 0.3048", "distance",
    ),
    ("inch", "cm"): ConversionSpec(
        "inch", "cm", 2.54, _ratio("inch", "cm"),
        "cm = inch × 2.54", "distance",
    ),
    ("yard", "m"): ConversionSpec(
        "yard", "m", 0.9144, _ratio("yard", "meter"),
        "m = yard × 0.9144", "distance",
    ),
    ("mph", "km/h"): ConversionSpec(
        "mph", "km/h", 1.609344, _ratio("mile", "km"),
        "km/h = mph × 1.609344", "speed",
    ),
    # 公制内部：目标市场已符合，因子 1.0，仅做规范化记录
    ("km", "km"): ConversionSpec(
        "km", "km", 1.0, _ratio("km", "km"), "km = km（公制无需换算）", "distance",
    ),
    ("meter", "meter"): ConversionSpec(
        "meter", "meter", 1.0, _ratio("meter", "meter"),
        "m = m（公制无需换算）", "distance",
    ),
    ("km/h", "km/h"): ConversionSpec(
        "km/h", "km/h", 1.0, _ratio("km", "km"),
        "km/h = km/h（公制无需换算）", "speed",
    ),
}


def convert_with_verification(
    raw_value: float,
    spec: ConversionSpec,
    tolerance: float = MULTIPLICATIVE_TOLERANCE,
) -> Tuple[float, ReverseVerification]:
    """执行乘法换算并做双重反向验算。

    1. 反向验算（PRD 硬要求）：``abs(target × factor⁻¹ − raw) < tolerance``；
    2. 参考常数交叉验算：``abs(target − raw × reference_factor) < tolerance``。

    任一不满足即抛 :class:`UnitConversionError`，绝不返回未经验算的结果。
    """
    if spec.factor == 0:
        raise UnitConversionError(
            f"换算因子非法（{spec.from_unit}->{spec.to_unit}）：factor=0 不可用于除法反向验算"
        )
    target = raw_value * spec.factor
    residual = abs(target * (spec.factor ** -1) - raw_value)
    if not residual < tolerance:
        raise UnitConversionError(
            f"反向验算超差：{spec.from_unit}->{spec.to_unit} raw={raw_value} "
            f"target={target} residual={residual} tolerance={tolerance}"
        )
    reference_residual = abs(target - raw_value * spec.reference_factor)
    if not reference_residual < tolerance:
        raise UnitConversionError(
            f"参考常数交叉验算超差：{spec.from_unit}->{spec.to_unit} raw={raw_value} "
            f"target={target} factor={spec.factor} reference_factor={spec.reference_factor} "
            f"residual={reference_residual} tolerance={tolerance}"
        )
    verification = ReverseVerification(
        performed=True,
        passed=True,
        tolerance=tolerance,
        residual=max(residual, reference_residual),
        formula=(
            f"{spec.formula}；反向验算 |{target:.6f} × {spec.factor}⁻¹ − {raw_value}| = "
            f"{residual:.9f} < {tolerance}；参考交叉 |{target:.6f} − "
            f"{raw_value} × {spec.reference_factor:.6f}| = {reference_residual:.9f} < {tolerance}"
        ),
    )
    return target, verification


def verify_temperature_reverse(
    fahrenheit: float,
    celsius: float,
    tolerance: float = TEMPERATURE_TOLERANCE,
) -> float:
    """温度反向验算：``abs(celsius × 9 / 5 + 32 − fahrenheit) < tolerance``。"""
    residual = abs(celsius * 9 / 5 + 32 - fahrenheit)
    if not residual < tolerance:
        raise UnitConversionError(
            f"温度反向验算超差：{fahrenheit}°F -> {celsius}°C residual={residual} "
            f"tolerance={tolerance}"
        )
    return residual


def convert_fahrenheit_to_celsius(
    fahrenheit: float,
    tolerance: float = TEMPERATURE_TOLERANCE,
) -> Tuple[float, ReverseVerification]:
    """°F -> °C 确定性换算（(F − 32) × 5 / 9）并立即反向验算。"""
    celsius = (fahrenheit - 32) * 5 / 9
    residual = verify_temperature_reverse(fahrenheit, celsius, tolerance)
    return celsius, ReverseVerification(
        performed=True,
        passed=True,
        tolerance=tolerance,
        residual=residual,
        formula=(
            f"°C = ({fahrenheit} − 32) × 5 / 9 = {celsius:.6f}；"
            f"反向验算 |{celsius:.6f} × 9 / 5 + 32 − {fahrenheit}| = {residual:.9f} < {tolerance}"
        ),
    )


# ==========================================
# 2. 舍入控制（Decimal 半入，避免浮点/银行家舍入漂移）
# ==========================================

def round_value(value: float, policy: str) -> float:
    """按策略舍入：integer 取整；one_decimal 保留 1 位小数；none 原样。"""
    if policy == "none":
        return float(value)
    if policy == "integer":
        quantum = Decimal("1")
    elif policy == "one_decimal":
        quantum = Decimal("0.1")
    else:
        raise ValueError(f"未知舍入策略：{policy}")
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def format_number(value: float, policy: str) -> str:
    """按策略渲染数值文本（整数策略不显示 .0）。"""
    if policy == "integer":
        return str(int(round_value(value, "integer")))
    if policy == "one_decimal":
        return f"{round_value(value, 'one_decimal'):.1f}"
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


_ROUNDING_HALF_QUANTUM = {"integer": 0.5, "one_decimal": 0.05, "none": 0.0}


def assert_rounding_within_quantum(rounded: float, exact: float, policy: str) -> None:
    """舍入后的值必须落在量化半格之内，防止"舍入"掩盖换算错误。"""
    limit = _ROUNDING_HALF_QUANTUM.get(policy)
    if limit is None:
        raise ValueError(f"未知舍入策略：{policy}")
    deviation = abs(rounded - exact)
    if deviation > limit + 1e-9:
        raise UnitConversionError(
            f"舍入偏差超限：rounded={rounded} exact={exact} policy={policy} "
            f"deviation={deviation} limit={limit}"
        )


# ==========================================
# 3. 数值与单位解析
# ==========================================

# 支持 "1,000.50" 千分位与 "26,2" 小数逗号
_NUM = r"-?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"


def parse_number(text: str) -> float:
    """解析原值字面量（兼容千分位与小数为逗号的西语写法）。"""
    cleaned = text.strip().replace(" ", "").replace("\u00a0", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        head, _, tail = cleaned.rpartition(",")
        if head and 1 <= len(tail) <= 2:
            cleaned = f"{head}.{tail}"
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError as exc:  # pragma: no cover - 防御性
        raise UnitConversionError(f"无法解析数值字面量：{text!r}") from exc


# ---- 正则目录 ----

_TEMP_TOKEN = (
    r"°\s*[CF]"
    r"|º\s*[CF]"
    r"|degrees?\s+(?:Fahrenheit|Celsius|F|C)"
    r"|grados?\s+(?:Fahrenheit|Celsius|F|C)"
    r"|Fahrenheit|Celsius"
    r"|[FC](?![A-Za-z])"
)
_TEMPERATURE_RE = re.compile(rf"(?P<value>{_NUM})\s*(?P<tunit>{_TEMP_TOKEN})", re.IGNORECASE)

_SPEED_RE = re.compile(
    rf"(?P<value>{_NUM})\s*(?P<sunit>"
    r"mph|miles?\s+per\s+hour|millas?\s+por\s+hora"
    r"|km\s*/\s*h|kmh|kph"
    r"|kil[oó]metros?\s+por\s+hora|kilometers?\s+per\s+hour"
    r")\b",
    re.IGNORECASE,
)

_MONEY_PREFIX_RE = re.compile(rf"(?P<symbol>US\$|\$|€|£|¥)\s?(?P<value>{_NUM})")
_MONEY_SUFFIX_RE = re.compile(
    rf"(?P<value>{_NUM})\s*(?P<code>USD|EUR|MXN|GBP|JPY|dollars?|d[oó]lares?|euros?|pesos?|pounds?)\b",
    re.IGNORECASE,
)

_DISTANCE_RE = re.compile(
    rf"(?P<value>{_NUM})\s*(?P<dunit>"
    r"miles?|millas?|kil[oó]metros?|kilometers?|km"
    r"|meters?|metros?|feet|foot|ft|inches|inch|pulgadas?|yards?|yardas?"
    r")\b",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"                                   # ISO
    r"|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b"                      # 10/21/2026, 21.10.2026
    rf"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December"
    rf"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:January|February|March|April|May|June|July|August"
    rf"|September|October|November|December)\b"
    r"|\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre"
    r"|octubre|noviembre|diciembre)(?:\s+de\s+\d{4})?\b",
    re.IGNORECASE,
)

_CODE_KEYWORD_RE = re.compile(
    r"\b(?:pin|password|passcode|pass\s*word|combination|code|clave|contrase[nñ]a|c[oó]digo)\b"
    r"|密码|验证码|口令",
    re.IGNORECASE,
)
_CODE_VALUE_RE = re.compile(r"(?<!\d)\d{3,8}(?!\d)")

_RECORD_KEYWORD_RE = re.compile(
    r"\b(?:world\s+record|record|r[eé]cord|lap\s+time|best\s+lap|fastest\s+lap|marca\s+personal"
    r"|r[eé]cord\s+mundial)\b|纪录|记录|圈速",
    re.IGNORECASE,
)
_RECORD_VALUE_RE = re.compile(r"(?<![\d.])(?:\d{1,2}:\d{2}(?:[.,]\d+)?|\d+(?:[.,]\d+)?)")


# ---- 单位规范化 ----

_DISTANCE_ALIASES = {
    "mile": "mile", "miles": "mile", "milla": "mile", "millas": "mile",
    "km": "km", "kilometro": "km", "kilometros": "km", "kilómetro": "km", "kilómetros": "km",
    "kilometer": "km", "kilometers": "km",
    "meter": "meter", "meters": "meter", "metro": "meter", "metros": "meter",
    "foot": "foot", "feet": "foot", "ft": "foot", "pie": "foot", "pies": "foot",
    "inch": "inch", "inches": "inch", "pulgada": "inch", "pulgadas": "inch",
    "yard": "yard", "yards": "yard", "yarda": "yard", "yardas": "yard",
}

# 目标市场 es-MX 的公制落点（英制必须换算，公制原样保留）
_DISTANCE_TARGET_UNIT = {
    "mile": "km",
    "foot": "m",
    "inch": "cm",
    "yard": "m",
    "km": "km",
    "meter": "meter",
}

_SPEED_ALIASES = {
    "mph": "mph", "miles per hour": "mph", "mile per hour": "mph",
    "millas por hora": "mph", "milla por hora": "mph",
    "km/h": "km/h", "kmh": "km/h", "kph": "km/h",
    "kilómetros por hora": "km/h", "kilometros por hora": "km/h", "kilómetro por hora": "km/h",
    "kilometers per hour": "km/h", "kilometer per hour": "km/h",
}

_CURRENCY_BY_WORD = {
    "usd": "USD", "dollar": "USD", "dollars": "USD", "dólar": "USD", "dólares": "USD",
    "dolar": "USD", "dolares": "USD",
    "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "mxn": "MXN", "peso": "MXN", "pesos": "MXN",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "jpy": "JPY",
}

_CURRENCY_BY_SYMBOL = {
    "US$": "USD",
    "$": None,   # 符号歧义：USD / MXN 均用 "$"，禁止猜测
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

# 语境关键词
_FEVER_CONTEXT_RE = re.compile(
    r"\b(?:fever|fiebre|calentura|body\s+temperature|temperatura\s+corporal|sick|ill|enferm[oa]?"
    r"|thermometer|term[oó]metro|chills|escalofr[ií]os)\b|发烧|发热|体温|生病|感冒",
    re.IGNORECASE,
)
_SCIENTIFIC_CONTEXT_RE = re.compile(
    r"\b(?:scientific|cient[ií]fico|experiment|experimento|laboratory|laboratorio|precise|preciso"
    r"|exact|exacto)\b|实验|精确|科学",
    re.IGNORECASE,
)


class _RawMatch:
    """扫描阶段的候选命中（内部结构，不对外暴露）。"""

    __slots__ = ("start", "end", "entity_type", "value_text", "unit_text", "priority", "meta")

    def __init__(self, start: int, end: int, entity_type: str, value_text: str,
                 unit_text: Optional[str], priority: int, meta: Optional[Dict[str, Any]] = None):
        self.start = start
        self.end = end
        self.entity_type = entity_type
        self.value_text = value_text
        self.unit_text = unit_text
        self.priority = priority
        self.meta = meta or {}


def _canonical_distance_unit(token: str) -> Optional[str]:
    return _DISTANCE_ALIASES.get(token.strip().lower())


def _canonical_speed_unit(token: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", token.strip().lower())
    return _SPEED_ALIASES.get(normalized)


def _temperature_scale(token: str) -> str:
    """从单位片段判断温标（F/C）。"""
    text = token.lower().replace("°", " ").replace("º", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if "fahrenheit" in text:
        return "F"
    if "celsius" in text:
        return "C"
    if text.endswith("f"):
        return "F"
    return "C"


def _plausible_bare_temperature(value: float, scale: str) -> bool:
    """单字母 F/C 容错：仅在合理温度区间内接受，避免 "Chapter 5 C" 类误命中。"""
    if scale == "F":
        return 20.0 <= value <= 130.0
    return -20.0 <= value <= 60.0


def _contextual_number_matches(
    text: str,
    keyword_re: "re.Pattern[str]",
    value_re: "re.Pattern[str]",
    window_after: int = 44,
    window_before: int = 20,
) -> List["re.Match[str]"]:
    """在关键词附近寻找数值（密码/纪录类实体没有单位，只能靠语境定位）。"""
    hits: List["re.Match[str]"] = []
    for keyword in keyword_re.finditer(text):
        after_start = keyword.end()
        after_end = min(len(text), keyword.end() + window_after)
        match = value_re.search(text, after_start, after_end) if after_start < after_end else None
        if match is None:
            before_start = max(0, keyword.start() - window_before)
            candidates = list(value_re.finditer(text, before_start, keyword.start()))
            match = candidates[-1] if candidates else None
        if match is not None and all(
            not (match.start() < existing.end() and existing.start() < match.end()) for existing in hits
        ):
            hits.append(match)
    return hits


def _collect_raw_matches(text: str) -> List[_RawMatch]:
    """按优先级扫描全部实体并消除重叠（上下文实体优先，速度优先于距离）。"""
    matches: List[_RawMatch] = []

    # 0) 密码 / PIN
    for m in _contextual_number_matches(text, _CODE_KEYWORD_RE, _CODE_VALUE_RE):
        matches.append(_RawMatch(m.start(), m.end(), "numeric_code", m.group(0), None, 0))

    # 1) 比赛纪录
    for m in _contextual_number_matches(text, _RECORD_KEYWORD_RE, _RECORD_VALUE_RE):
        matches.append(_RawMatch(m.start(), m.end(), "record", m.group(0), None, 1))

    # 2) 温度
    for m in _TEMPERATURE_RE.finditer(text):
        token = m.group("tunit")
        scale = _temperature_scale(token)
        value = parse_number(m.group("value"))
        if token.strip().upper() in ("F", "C") and not _plausible_bare_temperature(value, scale):
            # 仅对无度符号的单字母温标做区间容错，避免 "Chapter 5 C" 类误命中
            continue
        matches.append(
            _RawMatch(m.start(), m.end(), "temperature", m.group("value"), token, 2,
                      {"scale": scale})
        )

    # 3) 货币（前缀符号与后缀币种词分别扫描）
    for m in _MONEY_PREFIX_RE.finditer(text):
        symbol = m.group("symbol")
        matches.append(
            _RawMatch(m.start(), m.end(), "money", m.group("value"), symbol, 3,
                      {"symbol": symbol, "currency_code": _CURRENCY_BY_SYMBOL.get(symbol)})
        )
    for m in _MONEY_SUFFIX_RE.finditer(text):
        code = m.group("code")
        matches.append(
            _RawMatch(m.start(), m.end(), "money", m.group("value"), code, 3,
                      {"symbol": None, "currency_code": _CURRENCY_BY_WORD.get(code.lower())})
        )

    # 4) 速度（先于距离，避免 "60 mph" 被当作 "60 m"）
    for m in _SPEED_RE.finditer(text):
        canonical = _canonical_speed_unit(m.group("sunit"))
        if canonical is None:
            continue
        matches.append(
            _RawMatch(m.start(), m.end(), "speed", m.group("value"), m.group("sunit"), 4,
                      {"canonical": canonical})
        )

    # 5) 距离
    for m in _DISTANCE_RE.finditer(text):
        canonical = _canonical_distance_unit(m.group("dunit"))
        if canonical is None:
            continue
        matches.append(
            _RawMatch(m.start(), m.end(), "distance", m.group("value"), m.group("dunit"), 5,
                      {"canonical": canonical})
        )

    # 6) 日期（不做任何展开/换算）
    for m in _DATE_RE.finditer(text):
        matches.append(_RawMatch(m.start(), m.end(), "date", m.group(0), None, 6))

    # 消除重叠：优先级高者先占位
    accepted: List[_RawMatch] = []
    for candidate in sorted(matches, key=lambda item: (item.priority, item.start)):
        if any(candidate.start < existing.end and existing.start < candidate.end
               for existing in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item.start)


def extract_entities(
    unit_id: str,
    text: str,
    context: str = "",
) -> List[UnitEntity]:
    """第一段：纯工程实体抽取。无实体返回空列表（调用方据此整步 SKIP）。"""
    context_text = f"{context} {text}".strip()
    entities: List[UnitEntity] = []
    for index, raw in enumerate(_collect_raw_matches(text), start=1):
        flags: List[str] = []
        if raw.entity_type == "temperature":
            scale = raw.meta.get("scale", "C")
            value = parse_number(raw.value_text)
            is_fever_range = (
                value > FEVER_FAHRENHEIT_THRESHOLD if scale == "F"
                else value > FEVER_CELSIUS_THRESHOLD
            )
            if is_fever_range:
                flags.append("FEVER_RANGE")
            if _FEVER_CONTEXT_RE.search(context_text):
                flags.append("FEVER_CONTEXT")
            if _SCIENTIFIC_CONTEXT_RE.search(context_text):
                flags.append("SCIENTIFIC_CONTEXT")
        elif raw.entity_type == "money" and raw.meta.get("currency_code") is None:
            flags.append("AMBIGUOUS_CURRENCY_SYMBOL")

        raw_text = text[raw.start:raw.end]
        entities.append(
            UnitEntity(
                entity_id=f"{unit_id}-e{index:03d}",
                unit_id=unit_id,
                entity_type=raw.entity_type,
                raw_text=raw_text,
                raw_value=raw.value_text,
                raw_unit=raw.unit_text,
                start_char=raw.start,
                end_char=raw.end,
                context_flags=flags,
            )
        )
    return entities


# ==========================================
# 4. 候选构建（换算 + 例外硬锁）
# ==========================================

def _base_evidence(entity: UnitEntity, policy_ref: str) -> Dict[str, Any]:
    """原值、跨度、策略版本等结构化证据（原值永久保留）。"""
    return {
        "raw_text": entity.raw_text,
        "raw_value": entity.raw_value,
        "raw_unit": entity.raw_unit,
        "span": {"start": entity.start_char, "end": entity.end_char},
        "context_flags": list(entity.context_flags),
        "conversion_policy_ref": policy_ref,
        "conversion_policy_version": CONVERSION_POLICY_VERSION,
        "source": "deterministic_python",
    }


def _build_temperature_candidate(
    entity: UnitEntity,
    policy_ref: str,
    candidate_id: str,
) -> UnitCandidate:
    scale = _temperature_scale(entity.raw_unit or "C")
    raw_value = parse_number(entity.raw_value)
    evidence = _base_evidence(entity, policy_ref)
    evidence["source_scale"] = "fahrenheit" if scale == "F" else "celsius"

    if scale == "F":
        celsius_exact, verification = convert_fahrenheit_to_celsius(raw_value)
        formula = f"°C = ({entity.raw_value} − 32) × 5 / 9"
    else:
        celsius_exact = raw_value
        residual = abs(celsius_exact - raw_value)
        verification = ReverseVerification(
            performed=True,
            passed=True,
            tolerance=TEMPERATURE_TOLERANCE,
            residual=residual,
            formula=f"°C = {entity.raw_value}（已为公制温标，反向验算 |{celsius_exact:.6f} − {raw_value}| = {residual:.9f} < {TEMPERATURE_TOLERANCE}）",
        )
        formula = "°C = °C（公制温标无需换算）"

    flags = set(entity.context_flags)
    is_fever_range = (
        raw_value > FEVER_FAHRENHEIT_THRESHOLD if scale == "F"
        else raw_value > FEVER_CELSIUS_THRESHOLD
    )
    fever = is_fever_range and "FEVER_CONTEXT" in flags
    sensitive = fever or "FEVER_CONTEXT" in flags or "SCIENTIFIC_CONTEXT" in flags
    rounding_policy = "one_decimal" if sensitive else "integer"

    target_value = round_value(celsius_exact, rounding_policy)
    assert_rounding_within_quantum(target_value, celsius_exact, rounding_policy)
    display_value = format_number(target_value, rounding_policy)
    display_text = f"{display_value} °C (原值: {entity.raw_text})"

    if fever:
        status = CandidateStatus.MANUAL_DECISION_REQUIRED
        exception_reason = EXCEPTION_FEVER
        rationale = (
            "命中剧情例外硬锁：发烧体温属于剧情关键线索，机器不得自动替换；"
            f"仅并排提供参考换算 {display_value} °C，原值 {entity.raw_text} 永久保留，待人工裁定。"
        )
    elif sensitive:
        status = CandidateStatus.MANUAL_DECISION_REQUIRED
        exception_reason = EXCEPTION_SENSITIVE_TEMPERATURE
        rationale = (
            "体温/实验等语义敏感温度，按 PRD 先人工核实；"
            f"参考换算 {display_value} °C，原值原样保留供审校。"
        )
    else:
        status = CandidateStatus.AI_PROPOSED
        exception_reason = None
        rationale = (
            f"日常气温按 {scale}→°C 确定性换算，{rounding_policy} 舍入，"
            "已通过温度反向验算，待人工裁定。"
        )

    evidence.update(
        {
            "formula": formula,
            "rounding_policy": rounding_policy,
            "fever_range": is_fever_range,
            "reverse_check": verification.formula,
        }
    )

    return UnitCandidate(
        candidate_id=candidate_id,
        unit_id=entity.unit_id,
        entity_id=entity.entity_id,
        entity_type="temperature",
        raw_text=entity.raw_text,
        raw_value=entity.raw_value,
        raw_unit=entity.raw_unit,
        target_value=target_value,
        target_unit="°C",
        display_text=display_text,
        suggested_text=f"{display_value} °C" if status == CandidateStatus.AI_PROPOSED else None,
        conversion_factor=None,
        conversion_formula=formula,
        rounding_policy=rounding_policy,
        reverse_verification=verification,
        status=status,
        plot_exception=status == CandidateStatus.MANUAL_DECISION_REQUIRED,
        exception_reason=exception_reason,
        auto_apply_allowed=status == CandidateStatus.AI_PROPOSED,
        rationale=rationale,
        evidence=evidence,
    )


def _build_measure_candidate(
    entity: UnitEntity,
    policy_ref: str,
    candidate_id: str,
) -> UnitCandidate:
    """距离/速度：公制目标市场确定性换算 + 反向验算 + 舍入。"""
    canonical = (entity.raw_unit or "").strip().lower()
    if entity.entity_type == "speed":
        canonical = _canonical_speed_unit(canonical) or canonical
        target_unit = "km/h"
    else:
        canonical = _canonical_distance_unit(canonical) or canonical
        target_unit = _DISTANCE_TARGET_UNIT.get(canonical)
        if target_unit is None:
            raise UnitConversionError(
                f"缺少 {canonical} 到公制目标单位的换算策略，阻断替换（不猜公式）"
            )

    spec = CONVERSION_TABLE.get((canonical, target_unit))
    if spec is None:
        raise UnitConversionError(
            f"缺少 {canonical}->{target_unit} 的有效换算策略，阻断替换（不猜公式）"
        )

    raw_value = parse_number(entity.raw_value)
    target_exact, verification = convert_with_verification(raw_value, spec)

    sensitive = "SCIENTIFIC_CONTEXT" in entity.context_flags
    rounding_policy = "one_decimal" if sensitive else ("none" if spec.factor == 1.0 else "integer")
    target_value = round_value(target_exact, rounding_policy)
    assert_rounding_within_quantum(target_value, target_exact, rounding_policy)
    display_value = format_number(target_value, rounding_policy)
    display_text = f"{display_value} {target_unit} (原值: {entity.raw_text})"

    status = CandidateStatus.MANUAL_DECISION_REQUIRED if sensitive else CandidateStatus.AI_PROPOSED
    evidence = _base_evidence(entity, policy_ref)
    evidence.update(
        {
            "formula": spec.formula,
            "factor": spec.factor,
            "reference_factor": spec.reference_factor,
            "rounding_policy": rounding_policy,
            "reverse_check": verification.formula,
        }
    )

    return UnitCandidate(
        candidate_id=candidate_id,
        unit_id=entity.unit_id,
        entity_id=entity.entity_id,
        entity_type=entity.entity_type,
        raw_text=entity.raw_text,
        raw_value=entity.raw_value,
        raw_unit=entity.raw_unit,
        target_value=target_value,
        target_unit=target_unit,
        display_text=display_text,
        suggested_text=f"{display_value} {target_unit}" if status == CandidateStatus.AI_PROPOSED else None,
        conversion_factor=spec.factor,
        conversion_formula=spec.formula,
        rounding_policy=rounding_policy,
        reverse_verification=verification,
        status=status,
        plot_exception=status == CandidateStatus.MANUAL_DECISION_REQUIRED,
        exception_reason=EXCEPTION_SENSITIVE_MEASURE if sensitive else None,
        auto_apply_allowed=status == CandidateStatus.AI_PROPOSED,
        rationale=(
            f"目标市场 es-MX 使用公制：{spec.formula}；已通过乘法反向验算与参考常数交叉验算，"
            f"按 {rounding_policy} 舍入；原值 {entity.raw_text} 保留。"
        ),
        evidence=evidence,
    )


def _normalized_money_text(amount: float, code: Optional[str], symbol: Optional[str]) -> str:
    """仅规范符号与千分位/小数位，绝不改变币种与金额。"""
    amount_text = f"{amount:,.2f}"
    if code:
        return f"{code} {amount_text}"
    if symbol:
        return f"{symbol}{amount_text}"
    return amount_text


def _build_money_candidate(
    entity: UnitEntity,
    policy_ref: str,
    candidate_id: str,
) -> UnitCandidate:
    """剧情货币硬锁：禁止任何汇率折算，仅做符号/分隔符规范化，原币原额永久保留。"""
    raw_value = parse_number(entity.raw_value)
    code = _CURRENCY_BY_WORD.get((entity.raw_unit or "").lower())
    symbol = None
    if code is None and entity.raw_unit:
        symbol = entity.raw_unit
        code = _CURRENCY_BY_SYMBOL.get(entity.raw_unit)

    normalized = _normalized_money_text(raw_value, code, symbol)
    residual = abs(raw_value - parse_number(entity.raw_value))
    verification = ReverseVerification(
        performed=True,
        passed=True,
        tolerance=CURRENCY_IDENTITY_TOLERANCE,
        residual=residual,
        formula=(
            "identity: target_amount == raw_amount"
            f"（|{raw_value} − {raw_value}| = {residual:.9f} < {CURRENCY_IDENTITY_TOLERANCE}）；"
            "汇率换算硬锁禁用，不读取任何汇率/日期/基准币种"
        ),
    )
    evidence = _base_evidence(entity, policy_ref)
    evidence.update(
        {
            "fx_conversion": "FORBIDDEN",
            "exchange_rate": None,
            "rate_source": None,
            "currency_code": code,
            "currency_symbol": symbol,
            "normalization_scope": "symbol_and_separators_only",
            "reverse_check": verification.formula,
        }
    )
    return UnitCandidate(
        candidate_id=candidate_id,
        unit_id=entity.unit_id,
        entity_id=entity.entity_id,
        entity_type="money",
        raw_text=entity.raw_text,
        raw_value=entity.raw_value,
        raw_unit=entity.raw_unit,
        target_value=raw_value,
        target_unit=code or symbol or "UNKNOWN",
        display_text=f"{normalized} (原值: {entity.raw_text})",
        suggested_text=normalized,
        conversion_factor=None,
        conversion_formula=None,
        rounding_policy="none",
        raw_currency_code=code,
        target_currency_code=code,
        reverse_verification=verification,
        status=CandidateStatus.MANUAL_DECISION_REQUIRED,
        plot_exception=True,
        exception_reason=EXCEPTION_CURRENCY,
        auto_apply_allowed=False,
        rationale=(
            "剧情金额硬锁：严禁按汇率折算（例如把 100 美元算成比索），"
            "仅规范符号与千分位/小数点，原币种与原金额永久保留，由人工裁定是否采纳展示格式。"
        ),
        evidence=evidence,
    )


def _build_locked_candidate(
    entity: UnitEntity,
    policy_ref: str,
    candidate_id: str,
    exception_reason: str,
    rationale: str,
) -> UnitCandidate:
    """密码/PIN、比赛纪录、日期：禁止机器自动替换，仅保留原值并交人工裁定。"""
    evidence = _base_evidence(entity, policy_ref)
    evidence["machine_replacement"] = "FORBIDDEN"
    evidence["exception_reason"] = exception_reason
    return UnitCandidate(
        candidate_id=candidate_id,
        unit_id=entity.unit_id,
        entity_id=entity.entity_id,
        entity_type=entity.entity_type,
        raw_text=entity.raw_text,
        raw_value=entity.raw_value,
        raw_unit=entity.raw_unit,
        target_value=None,
        target_unit=None,
        display_text=f"{entity.raw_text}（原值锁定，禁止机器自动替换）",
        suggested_text=None,
        conversion_factor=None,
        conversion_formula=None,
        rounding_policy="none",
        reverse_verification=ReverseVerification(
            performed=False,
            passed=False,
            tolerance=None,
            residual=None,
            formula=None,
        ),
        status=CandidateStatus.MANUAL_DECISION_REQUIRED,
        plot_exception=True,
        exception_reason=exception_reason,
        auto_apply_allowed=False,
        rationale=rationale,
        evidence=evidence,
    )


def build_candidates_for_entity(
    entity: UnitEntity,
    policy_ref: str,
    candidate_id: str,
) -> UnitCandidate:
    """按实体类型选择构建路径；未知类型直接阻断（不猜处理方式）。"""
    if entity.entity_type == "temperature":
        return _build_temperature_candidate(entity, policy_ref, candidate_id)
    if entity.entity_type in ("distance", "speed"):
        return _build_measure_candidate(entity, policy_ref, candidate_id)
    if entity.entity_type == "money":
        return _build_money_candidate(entity, policy_ref, candidate_id)
    if entity.entity_type == "numeric_code":
        return _build_locked_candidate(
            entity, policy_ref, candidate_id, EXCEPTION_NUMERIC_CODE,
            "密码/PIN/锁码属于剧情关键线索，严禁机器改写或换算；原值永久保留，待人工裁定。",
        )
    if entity.entity_type == "record":
        return _build_locked_candidate(
            entity, policy_ref, candidate_id, EXCEPTION_RECORD,
            "比赛纪录/计时属于剧情关键线索，严禁机器改写或换单位；原值永久保留，待人工裁定。",
        )
    if entity.entity_type == "date":
        return _build_locked_candidate(
            entity, policy_ref, candidate_id, EXCEPTION_DATE,
            "日期含义需人工确认（不推断历史日期/时区/日历），机器不得自动展开或改写。",
        )
    raise UnitConversionError(f"未支持的实体类型：{entity.entity_type}")


# ==========================================
# 5. 对外主流程
# ==========================================

def _build_context(unit) -> str:
    return " ".join(
        part for part in (unit.prev_context, unit.target_text, unit.next_context) if part
    )


def scan_and_convert_text(
    unit_id: str,
    text: str,
    context: str = "",
    policy_ref: str = f"conversion-policy:{CONVERSION_POLICY_VERSION}",
) -> Tuple[List[UnitEntity], List[UnitCandidate]]:
    """单条文本的抽取 + 换算（供单测/局部重算直接调用）。"""
    entities = extract_entities(unit_id, text, context=context)
    candidates = [
        build_candidates_for_entity(entity, policy_ref, f"{unit_id}-c{index:03d}")
        for index, entity in enumerate(entities, start=1)
    ]
    return entities, candidates


def extract_and_convert_units(request: UnitFormatRequest) -> UnitFormatResult:
    """两段式流水线入口：抽取 → 跳步判定 → 确定性换算 → 例外硬锁。

    无任何实体的单元整步 SKIP：不构建候选、不产生 Token、不引入延迟；
    若整个请求范围都无实体，结果 status 为 ``SKIPPED``。
    """
    started = datetime.now(timezone.utc)
    run_id = f"run-unit-{uuid.uuid4().hex[:12]}"

    entities: List[UnitEntity] = []
    candidates: List[UnitCandidate] = []
    outcomes: List[UnitOutcome] = []
    type_counts: Counter = Counter()
    skipped_units: List[str] = []

    for unit in request.units:
        unit_entities = extract_entities(
            unit.unit_id, unit.target_text, context=_build_context(unit)
        )
        if not unit_entities:
            skipped_units.append(unit.unit_id)
            outcomes.append(
                UnitOutcome(
                    unit_id=unit.unit_id,
                    status="SKIPPED",
                    entity_count=0,
                    candidate_count=0,
                    token_used=0,
                    latency_ms=0,
                    reason="NO_UNIT_ENTITY_IN_TEXT",
                )
            )
            continue

        unit_candidates = [
            build_candidates_for_entity(
                entity, request.conversion_policy_ref, f"{unit.unit_id}-c{index:03d}"
            )
            for index, entity in enumerate(unit_entities, start=1)
        ]
        entities.extend(unit_entities)
        candidates.extend(unit_candidates)
        type_counts.update(entity.entity_type for entity in unit_entities)
        outcomes.append(
            UnitOutcome(
                unit_id=unit.unit_id,
                status="PROCESSED",
                entity_count=len(unit_entities),
                candidate_count=len(unit_candidates),
                token_used=0,
                latency_ms=0,
                reason=None,
            )
        )

    overall_status = "PROCESSED" if entities else "SKIPPED"
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    manifest: Dict[str, Any] = {
        "schema_version": request.schema_version,
        "conversion_policy_ref": request.conversion_policy_ref,
        "conversion_policy_version": CONVERSION_POLICY_VERSION,
        "target_market": request.target_market,
        "target_language": request.target_language,
        "pipeline": "two_stage_deterministic_first",
        "stage1_entity_scan": "regex_rules",
        "stage2_context_classifier": "deterministic_rules_only",
        "model_used": False,
        "model_invocation": "NOT_INVOKED",
        "token_used": 0,
        "latency_ms": elapsed_ms,
        "entity_count": len(entities),
        "candidate_count": len(candidates),
        "entity_type_counts": dict(type_counts),
        "skipped_unit_ids": skipped_units,
        "skipped_unit_count": len(skipped_units),
        "reverse_verification": "ENFORCED",
        "currency_fx": "FORBIDDEN",
        "auto_apply_allowed_count": sum(1 for c in candidates if c.auto_apply_allowed),
        "manual_decision_required_count": sum(
            1 for c in candidates if c.status == CandidateStatus.MANUAL_DECISION_REQUIRED
        ),
    }

    return UnitFormatResult(
        run_id=run_id,
        task_ref=request.task_ref,
        task_revision=request.task_revision,
        target_language=request.target_language,
        target_market=request.target_market,
        status=overall_status,
        entities=entities,
        candidates=candidates,
        unit_outcomes=outcomes,
        manifest=manifest,
    )

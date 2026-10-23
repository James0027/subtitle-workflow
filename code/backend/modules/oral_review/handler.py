"""口语适配与节奏审校模块 —— 纯白盒处理引擎（确定性、零外部模型）。

设计依据：docs/05-prd/06-subprd-oral-review.md §10、rule-registry RULE-ORAL-001/002
与 P-ORAL、metrics MET-ORAL-001/002/003。

四层处理流水线（全部为 Python 规则/算术，不调用任何大模型）：

    1. 可读性度量（RULE-ORAL-001 / MET-ORAL-001）
       visible_char_count → CPS = chars / duration；CPS>17 标黄、CPS>20 阻断；
       行长 ≤42、行数 ≤2；时长 <0.833s / >7.0s 提示；≤0s 为硬非法（cps=None，
       绝不参与 CPS 统计美化），同时给出确定性断行建议。
    2. 句法复杂度与无损拆句（§10.1）
       从属连词命中 ≥2 或嵌套深度（代理）>4 → COMPLEX_SENTENCE；
       拆句严格时间连续、总时长与原句吻合（容差 0.001s），按字符比例分配中切点，
       两侧子句均须 ≥0.833s；不满足则不给方案，绝不暗改时间轴。
    3. 翻译腔与书面语偏离度（§10.2）
       es-MX 影视高频口语 ↔ 书面语词库（30 组）；written_score 由命中数与密度合成，
       >0.75 标 ORAL_DEVIATION_WARN 并给出可解释的口语候选与确定性改写文本。
    4. 四类语义风险规则检查硬闸门（§10.3 / MET-ORAL-003）
       否定极性、事实实体、人物关系称谓、情绪立场反讽四项逐项比对；任一违规即
       BLOCK 并废弃候选，manifest 记录拦截计数。

时间轴原则：本模块只读取 start/end，除"无损拆句"按比例切分并严格守恒总时长外，
不产生任何时间轴变更；拆句结果必须通过 :func:`verify_split_time_invariance`。
"""

import re
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from code.backend.modules.oral_review.contract import (
    COMPLEX_CONJUNCTION_THRESHOLD,
    CPS_HARD_LIMIT,
    CPS_SOFT_LIMIT,
    MAX_DURATION_SEC,
    MAX_LINE_COUNT,
    MAX_LINE_LENGTH,
    MIN_DURATION_SEC,
    MIN_SPLIT_PART_DURATION,
    NESTING_DEPTH_THRESHOLD,
    ORAL_POLICY_VERSION,
    ORAL_REVIEW_SCHEMA_VERSION,
    SPLIT_TIME_TOLERANCE,
    WRITTEN_SCORE_WARN_THRESHOLD,
    ComplexityAnalysis,
    ComplexityType,
    DeviationType,
    OralCandidate,
    OralDeviationAnalysis,
    OralReviewItemResult,
    OralReviewRequest,
    OralReviewResult,
    ReadabilityIssueType,
    ReadabilityMetrics,
    ReadabilityStatus,
    SemanticGuardCheck,
    SemanticViolationType,
    SplitSegmentCandidate,
    SubtitleSegment,
    worst_status,
)

# ==========================================
# 0. 错误类型
# ==========================================


class SplitTimeInvarianceError(ValueError):
    """无损拆句时间轴校验失败（时间不连续、总时长被暗改）。继承 ValueError。"""


# ==========================================
# 1. 文本工具
# ==========================================

_WS_RE = re.compile(r"\s+")


def normalize_visible_text(text: str) -> str:
    """可见字符口径：换行/连续空白归一为单空格并去首尾空白。

    按工单口径，可见字符数**包含**词间单空格与标点（MET-ORAL-001 的字符策略，
    版本随 ORAL_POLICY_VERSION 固化）。
    """
    return _WS_RE.sub(" ", text.replace("\r\n", "\n")).strip()


def split_lines(text: str) -> List[str]:
    """以 \\n 分行并去每行首尾空白；空文本视为一行空串。"""
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return [""]
    return [line.strip() for line in cleaned.split("\n")]


def count_visible_chars(text: str) -> int:
    """可见字符数（含词间单空格与标点，不含换行）。"""
    return len(normalize_visible_text(text))


def _fold(text: str) -> str:
    """去重音折叠（jamás→jamas、señor→senor），仅用于确定性比对，不用于展示。"""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(text)


# ==========================================
# 2. 可读性度量（RULE-ORAL-001 / MET-ORAL-001）
# ==========================================

_LINE_BREAK_CHARS = ",;:."


def _wrap_into_two_lines(text: str) -> Optional[str]:
    """把一行文本按语法断点折成 ≤2 行、每行 ≤42 字符；无法满足时返回 None。"""
    clean = normalize_visible_text(text)
    if len(clean) <= MAX_LINE_LENGTH:
        return clean
    middle = len(clean) / 2.0

    def _split_at(index: int) -> Tuple[str, str]:
        return clean[:index].strip(), clean[index:].strip()

    # 1) 优先在标点后断行（保留标点在左行）
    punctuation_cuts = [i + 1 for i, ch in enumerate(clean) if ch in _LINE_BREAK_CHARS]
    # 2) 其次在词边界断行
    space_cuts = [i + 1 for i, ch in enumerate(clean) if ch == " "]

    for cuts in (punctuation_cuts, space_cuts):
        viable = []
        for cut in cuts:
            left, right = _split_at(cut)
            if not left or not right:
                continue
            if len(left) <= MAX_LINE_LENGTH and len(right) <= MAX_LINE_LENGTH:
                viable.append((abs(cut - middle), cut))
        if viable:
            _, best = min(viable)
            left, right = _split_at(best)
            return f"{left}\n{right}"
    return None


def suggest_line_breaks(text: str) -> Optional[str]:
    """行长/行数超限时的确定性断行建议（≤2 行、每行 ≤42 字符）。"""
    clean = normalize_visible_text(text)
    if not clean:
        return None
    wrapped = _wrap_into_two_lines(clean)
    if wrapped is None:
        return None
    if wrapped == clean and len(split_lines(text)) <= MAX_LINE_COUNT:
        return None
    return wrapped


def analyze_readability(segment: SubtitleSegment) -> ReadabilityMetrics:
    """计算单句可读性度量、问题码与断行建议。

    - ``duration = end_time - start_time``，保留 3 位小数按秒计；
    - ``duration <= 0`` → DURATION_INVALID 硬非法：``cps=None``、``cps_status=BLOCK``、
      ``duration_status=BLOCK``，绝不把非法时长折算进 CPS（避免"美化"）；
    - ``duration < 0.833s`` → DURATION_TOO_SHORT（WARN，极短时长观众读不完）；
    - ``duration > 7.0s`` → DURATION_TOO_LONG（WARN，建议拆句/延时）；
    - ``cps = round(chars / duration, 2)``：≤17 PASS、17<CPS≤20 WARN、>20 BLOCK；
    - 行数 ≤2 且每行 ≤42 字符，超限给断行建议（LINE_LENGTH_EXCEEDED /
      LINE_COUNT_EXCEEDED，WARN 级：可读性问题由人工按建议改稿）。
    """
    text = segment.text or ""
    duration = round(segment.end_time - segment.start_time, 3)
    visible = count_visible_chars(text)
    lines = split_lines(text)
    line_count = len(lines)
    max_line_length = max((len(line) for line in lines), default=0)

    is_duration_valid = duration > 0
    issues: List[str] = []

    # --- CPS ---
    if is_duration_valid:
        cps: Optional[float] = round(visible / duration, 2)
        if cps > CPS_HARD_LIMIT:
            cps_status = ReadabilityStatus.BLOCK
            issues.append(ReadabilityIssueType.CPS_BLOCK.value)
        elif cps > CPS_SOFT_LIMIT:
            cps_status = ReadabilityStatus.WARN
            issues.append(ReadabilityIssueType.CPS_WARN.value)
        else:
            cps_status = ReadabilityStatus.PASS
    else:
        cps = None
        # CPS 不可评价：直接按阻断处理，但不伪造 CPS 数值，也不登记 CPS_* 问题码
        cps_status = ReadabilityStatus.BLOCK

    # --- 时长极值 ---
    if not is_duration_valid:
        duration_status = ReadabilityStatus.BLOCK
        issues.append(ReadabilityIssueType.DURATION_INVALID.value)
    elif duration < MIN_DURATION_SEC:
        duration_status = ReadabilityStatus.WARN
        issues.append(ReadabilityIssueType.DURATION_TOO_SHORT.value)
    elif duration > MAX_DURATION_SEC:
        duration_status = ReadabilityStatus.WARN
        issues.append(ReadabilityIssueType.DURATION_TOO_LONG.value)
    else:
        duration_status = ReadabilityStatus.PASS

    # --- 行长与行数 ---
    too_long_line = max_line_length > MAX_LINE_LENGTH
    too_many_lines = line_count > MAX_LINE_COUNT
    if too_long_line:
        issues.append(ReadabilityIssueType.LINE_LENGTH_EXCEEDED.value)
    if too_many_lines:
        issues.append(ReadabilityIssueType.LINE_COUNT_EXCEEDED.value)
    line_status = (
        ReadabilityStatus.WARN if (too_long_line or too_many_lines) else ReadabilityStatus.PASS
    )

    suggestion = suggest_line_breaks(text) if (too_long_line or too_many_lines) else None

    return ReadabilityMetrics(
        visible_char_count=visible,
        duration_sec=duration,
        cps=cps,
        line_count=line_count,
        max_line_length=max_line_length,
        lines=lines,
        is_duration_valid=is_duration_valid,
        cps_status=cps_status,
        line_status=line_status,
        duration_status=duration_status,
        issues=issues,
        syntax_line_break_suggestion=suggestion,
    )


# ==========================================
# 3. 句法复杂度与无损拆句（§10.1）
# ==========================================

# 西班牙语从属连词/引导词库（多词项在前，保证最长匹配优先）
SUBORDINATE_CONJUNCTIONS: Tuple[str, ...] = (
    "a pesar de que",
    "a fin de que",
    "a menos que",
    "antes de que",
    "con tal de que",
    "de modo que",
    "después de que",
    "en caso de que",
    "tan pronto como",
    "mientras que",
    "siempre que",
    "debido a que",
    "puesto que",
    "salvo que",
    "ya que",
    "dado que",
    "para que",
    "por más que",
    "en cuanto",
    "así que",
    "si bien",
    "aunque",
    "mientras",
    "porque",
    "cuando",
    "donde",
    "como",
    "quien",
    "cual",
    "cuyo",
    "que",
    "si",
)

_SENTENCE_SPLIT_RE = re.compile(r"[.!?;:]+")


def _conjunction_regex() -> "re.Pattern[str]":
    """按长度降序拼装连词正则，保证 "porque" 不被拆成 "que"。"""
    ordered = sorted({_fold(item) for item in SUBORDINATE_CONJUNCTIONS}, key=len, reverse=True)
    alternatives = "|".join(
        r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in ordered
    )
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


_SUBORDINATE_RE = _conjunction_regex()


def detect_subordinate_conjunctions(text: str) -> List[str]:
    """按最长匹配返回命中的从属连词（保持原文词形，去重后按出现顺序）。"""
    hits: List[str] = []
    for match in _SUBORDINATE_RE.finditer(text or ""):
        hits.append(_WS_RE.sub(" ", match.group(0)).strip())
    return hits


def compute_nesting_depth(text: str, conjunction_count: int) -> int:
    """从句嵌套深度（确定性代理，不依赖句法分析器）。

    依赖树不可得时以"同一句内堆叠的从属连词数"作代理：主句记 1，句内每多一个从属
    连词即多一层（深度 = 1 + 该句内连词数），取全文最大句内值。该代理与
    ``> 4`` 阈值配合，用于筛选需拆句的长复句。
    """
    if conjunction_count <= 0:
        return 1 if (text or "").strip() else 0
    depth = 1
    for span in _SENTENCE_SPLIT_RE.split(text):
        if not span.strip():
            continue
        count = len(list(_SUBORDINATE_RE.finditer(span)))
        depth = max(depth, 1 + count)
    return depth


def _best_split_cut(text: str) -> Optional[int]:
    """选取合法断点（返回右半句起始索引）：优先标点、其次词边界，靠近字符比例中点。"""
    clean = normalize_visible_text(text)
    if len(clean) < 2:
        return None
    middle = len(clean) / 2.0
    punctuation = [i + 1 for i, ch in enumerate(clean) if ch in _LINE_BREAK_CHARS]
    spaces = [i for i, ch in enumerate(clean) if ch == " "]
    for cuts in (punctuation, spaces):
        viable: List[Tuple[float, int]] = []
        for cut in cuts:
            left, right = clean[:cut].strip(), clean[cut:].strip()
            if not left or not right:
                continue
            if len(left) > MAX_LINE_LENGTH or len(right) > MAX_LINE_LENGTH:
                continue
            viable.append((abs(cut - middle), cut))
        if viable:
            _, best = min(viable)
            return best
    return None


def build_lossless_split(
    text: str,
    start_time: float,
    end_time: float,
) -> Optional[List[SplitSegmentCandidate]]:
    """把单句无损拆为两段连续子句，时间轴严格守恒。

    切点取靠近字符比例中点的语法断点；按 ``len(part1)/(len(part1)+len(part2))``
    比例分配中切时间（3 位小数）。任一侧短于 0.833s 或不满足行长约束则返回 None
    （宁可不给方案，也不偷偷改时间轴或硬切）。
    """
    original_duration = round(end_time - start_time, 3)
    clean = normalize_visible_text(text)
    cut = _best_split_cut(clean)
    if cut is None:
        return None
    part1, part2 = clean[:cut].strip(), clean[cut:].strip()
    if not part1 or not part2:
        return None

    ratio = len(part1) / (len(part1) + len(part2))
    mid_time = round(start_time + original_duration * ratio, 3)
    if not (start_time < mid_time < end_time):
        return None
    if (mid_time - start_time) < MIN_SPLIT_PART_DURATION:
        return None
    if (end_time - mid_time) < MIN_SPLIT_PART_DURATION:
        return None

    parts = [
        SplitSegmentCandidate(
            part_index=0,
            text=part1,
            start_time=start_time,
            end_time=mid_time,
            duration_sec=round(mid_time - start_time, 3),
            char_count=len(part1),
        ),
        SplitSegmentCandidate(
            part_index=1,
            text=part2,
            start_time=mid_time,
            end_time=end_time,
            duration_sec=round(end_time - mid_time, 3),
            char_count=len(part2),
        ),
    ]
    verify_split_time_invariance(start_time, end_time, parts)
    return parts


def verify_split_time_invariance(
    original_start: float,
    original_end: float,
    parts: Sequence[SplitSegmentCandidate],
    tolerance: float = SPLIT_TIME_TOLERANCE,
) -> None:
    """拆句时间轴硬校验：首尾对齐、逐段连续、总时长绝对吻合。

    违反任一条即抛 :class:`SplitTimeInvarianceError`（禁止"暗改时间轴"）。
    """
    if len(parts) < 2:
        raise SplitTimeInvarianceError("拆句至少需要 2 个子句")
    if abs(parts[0].start_time - original_start) > 1e-9:
        raise SplitTimeInvarianceError(
            f"拆句起点 {parts[0].start_time} 与原句起点 {original_start} 不一致"
        )
    if abs(parts[-1].end_time - original_end) > 1e-9:
        raise SplitTimeInvarianceError(
            f"拆句终点 {parts[-1].end_time} 与原句终点 {original_end} 不一致"
        )
    for previous, current in zip(parts, parts[1:]):
        if abs(previous.end_time - current.start_time) > 1e-9:
            raise SplitTimeInvarianceError(
                f"拆句时间轴不连续：{previous.end_time} != {current.start_time}"
            )
    original_duration = original_end - original_start
    total = sum(part.duration_sec for part in parts)
    if not abs(total - original_duration) < tolerance:
        raise SplitTimeInvarianceError(
            f"拆句总时长 {total:.6f}s 与原句 {original_duration:.6f}s 偏差 "
            f"≥ {tolerance}s（暗改时间轴）"
        )


def analyze_complexity(
    text: str,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> ComplexityAnalysis:
    """判定句法复杂度；给定时间轴时附带无损拆句方案。"""
    hits = detect_subordinate_conjunctions(text)
    count = len(hits)
    depth = compute_nesting_depth(text, count)
    is_complex = count >= COMPLEX_CONJUNCTION_THRESHOLD or depth > NESTING_DEPTH_THRESHOLD

    split: Optional[List[SplitSegmentCandidate]] = None
    if is_complex and start_time is not None and end_time is not None:
        split = build_lossless_split(text, start_time, end_time)

    return ComplexityAnalysis(
        is_complex=is_complex,
        subordinate_conjunction_count=count,
        detected_conjunctions=hits,
        nesting_depth=depth,
        issue_tag=ComplexityType.COMPLEX_SENTENCE.value if is_complex else None,
        split_suggestion=split,
    )


# ==========================================
# 4. 翻译腔与书面语偏离度（§10.2）
# ==========================================

# (书面词, 匹配正则, es-MX 口语候选, 语境理由)
WRITTEN_TERM_LEXICON: Tuple[Tuple[str, str, Tuple[str, ...], str], ...] = (
    ("no obstante", r"no\s+obstante", ("pero", "sin embargo"),
     "影视对白转折几乎只用 pero / sin embargo；no obstante 属公报体"),
    ("asimismo", r"as[ií]mismo", ("también", "además"),
     "口语并列用 también / además，asimismo 只见于书面公文"),
    ("por ende", r"por\s+ende", ("por eso", "así que"),
     "por ende 是拉美书面连接词；母语观众口语说 por eso"),
    ("con el fin de", r"con\s+el\s+fin\s+de", ("para",),
     "目的状语口语直接说 para，con el fin de 属法律文本"),
    ("en vista de que", r"en\s+vista\s+de\s+que", ("ya que", "como"),
     "原因从句口语用 ya que / como"),
    ("a la brevedad", r"a\s+la\s+brevedad", ("cuanto antes", "pronto"),
     "催促语境口语说 cuanto antes，a la brevedad 为商务套话"),
    ("posee", r"\bpose(?:e|en|er|ía|ían|y[oó]|emos|imos)\b", ("tiene", "tienen"),
     "拥有义口语一律用 tener；poseer 属财产文书"),
    ("efectuar", r"\befect[uú](?:a|an|ar|e|en|ó|aron|aba)\b", ("hacer", "haz"),
     "动作义口语用 hacer；efectuar 为行政书面语"),
    ("requerir", r"\brequier(?:e|en|o|es|a|an|ó|ieron)\b|\brequer(?:imos|ir|ia|ía|ian|ían)\b",
     ("necesita", "necesitar", "necesitan"),
     "需要义口语用 necesitar；requerir 属正式文书"),
    ("adquirir", r"\badquier(?:e|en|o|es|a|an)\b|\badquir(?:ió|ieron|imos|ir|ía|ían)\b",
     ("compra", "comprar", "compran"),
     "购买义口语用 comprar；adquirir 属合同语域"),
    ("mediante el cual", r"mediante\s+(?:el|la)\s+cual", ("con el que", "con la que"),
     "工具从句口语用 con el que；mediante el cual 为法条结构"),
    ("debido a que", r"debido\s+a\s+que", ("porque",),
     "原因从句口语首选 porque"),
    ("puesto que", r"puesto\s+que", ("porque", "ya que"),
     "puesto que 书面色彩重，口语用 porque"),
    ("dado que", r"dado\s+que", ("porque", "ya que"),
     "dado que 常见于报告；对白用 porque"),
    ("de igual manera", r"de\s+igual\s+manera", ("igual", "también"),
     "口语并列用 igual / también"),
    ("en consecuencia", r"en\s+consecuencia", ("entonces", "así que"),
     "推论口语用 entonces / así que"),
    ("por consiguiente", r"por\s+consiguiente", ("así que", "entonces"),
     "por consiguiente 为论文体连接词"),
    ("cabe destacar", r"cabe\s+destacar", ("ojo", "fíjate"),
     "提示语口语用 ojo / fíjate"),
    ("a fin de", r"a\s+fin\s+de(?!\s+que)", ("para",),
     "目的状语口语用 para"),
    ("ulteriormente", r"\bulteriormente\b", ("después", "luego"),
     "时间副词口语用 después / luego"),
    ("posteriormente", r"\bposteriormente\b", ("después", "luego"),
     "时间副词口语用 después / luego"),
    ("previo a", r"previo\s+a", ("antes de",),
     "时间介词口语用 antes de"),
    ("en lo que respecta a", r"en\s+lo\s+que\s+respecta\s+a", ("sobre",),
     "话题标记口语用 sobre"),
    ("con relación a", r"con\s+relaci[oó]n\s+a", ("sobre",),
     "话题标记口语用 sobre"),
    ("de manera que", r"de\s+manera\s+que", ("así que",),
     "结果从句口语用 así que"),
    ("solicitar", r"\bsolicit(?:a|an|ar|o|ó|aron|e|en)\b", ("pide", "pedir", "piden"),
     "请求义口语用 pedir；solicitar 属窗口办事用语"),
    ("obtener", r"\bobteng(?:a|an|o)\b|\bobtener\b", ("conseguir", "consigue"),
     "获得义口语用 conseguir"),
    ("realizar", r"\brealiz(?:a|an|ar|o|ó|aron)\b", ("hacer", "haz"),
     "动作义口语用 hacer；realizar 为书面泛动词"),
    ("comunicar", r"\bcomunic(?:a|an|ar|ó|aron)\b", ("avisar", "decir"),
     "告知义口语用 avisar / decir"),
    ("aproximadamente", r"\baproximadamente\b", ("como", "más o menos"),
     "约数口语用 como / más o menos"),
)

_COMPILED_WRITTEN_TERMS: Tuple[Tuple[str, "re.Pattern[str]", Tuple[str, ...], str], ...] = tuple(
    (term, re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE), candidates, rationale)
    for term, pattern, candidates, rationale in WRITTEN_TERM_LEXICON
)

# 书面语命中饱和点：3 个书面词即视为命中密度满分
WRITTEN_HIT_SATURATION = 3.0
# 密度满分系数：每 10 个词命中 1 个书面词即密度满分
WRITTEN_DENSITY_FACTOR = 10.0


def _pick_oral_candidate(matched: str, candidates: Sequence[str]) -> str:
    """按数（单/复数）择优：匹配词以 n 结尾时优先选复数候选。"""
    plural = matched.strip().lower().endswith("n")
    if plural:
        for candidate in candidates:
            if candidate.endswith("n"):
                return candidate
    else:
        for candidate in candidates:
            if not candidate.endswith("n"):
                return candidate
    return candidates[0]


def _match_case(source: str, replacement: str) -> str:
    """保持首字母大小写（句首替换不破坏排版）。"""
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def analyze_oral_deviation(text: str) -> OralDeviationAnalysis:
    """翻译腔/书面语偏离度：命中数与密度合成的书面语倾向分。

    ``written_score = 0.6 × min(1, hits/3) + 0.4 × min(1, hits/词数 × 10)``，
    结果取 4 位小数并裁剪到 [0,1]。> 0.75 触发 ORAL_DEVIATION_WARN（标黄），
    同时给出地道口语候选与上下文理由；``suggested_rewrite`` 为确定性替换结果，
    必须再通过四重语义闸门才能成为可用候选。
    """
    raw = text or ""
    span_hits: List[Tuple[int, int, int, str, Tuple[str, ...], str]] = []
    for index, (term, pattern, candidates, rationale) in enumerate(_COMPILED_WRITTEN_TERMS):
        for match in pattern.finditer(raw):
            span_hits.append(
                (match.start(), match.end(), index, match.group(0), candidates, rationale)
            )

    # 消除重叠：先占位者优先（长词条天然先命中，短词不重复计数）
    span_hits.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    accepted: List[Tuple[int, int, int, str, Tuple[str, ...], str]] = []
    for hit in span_hits:
        if any(hit[0] < other[1] and other[0] < hit[1] for other in accepted):
            continue
        accepted.append(hit)
    accepted.sort(key=lambda item: item[0])

    hits = len(accepted)
    word_count = max(1, len(_words(raw)))
    hit_factor = min(1.0, hits / WRITTEN_HIT_SATURATION)
    density_factor = min(1.0, hits / word_count * WRITTEN_DENSITY_FACTOR)
    written_score = round(min(1.0, 0.6 * hit_factor + 0.4 * density_factor), 4)

    detected: List[Dict[str, Any]] = []
    grouped: Dict[str, Dict[str, Any]] = {}
    for start, end, index, matched, candidates, rationale in accepted:
        term = WRITTEN_TERM_LEXICON[index][0]
        entry = grouped.setdefault(
            term,
            {
                "term": term,
                "matched": [],
                "oral_candidates": list(candidates),
                "rationale": rationale,
                "count": 0,
            },
        )
        entry["matched"].append(matched)
        entry["count"] += 1
    detected = list(grouped.values())

    # 确定性改写（从右向左替换，避免位移错乱）
    rewrite: Optional[str] = None
    if accepted:
        chars = raw
        for start, end, index, matched, candidates, _ in reversed(accepted):
            chars = chars[:start] + _match_case(matched, _pick_oral_candidate(matched, candidates)) + chars[end:]
        rewrite = chars

    return OralDeviationAnalysis(
        written_score=written_score,
        is_warn=written_score > WRITTEN_SCORE_WARN_THRESHOLD,
        detected_written_terms=detected,
        suggested_rewrite=rewrite,
    )


# ==========================================
# 5. 四类语义风险规则检查硬闸门（§10.3）
# ==========================================

NEGATION_WORDS: Tuple[str, ...] = (
    "no", "nunca", "jamas", "tampoco", "nadie", "nada",
    "ninguno", "ninguna", "ningun", "ni",
)

# 固定搭配里的"no"不是否定（no obstante = sin embargo），比对前先遮蔽
NEGATION_IDIOMS: Tuple[str, ...] = (
    "no obstante", "no bien", "no solo", "no solamente", "nada mas", "si no",
)

# 只收 ≥2 的数词，避免冠词 un/una 造成实体误伤
NUMBER_WORDS: Tuple[str, ...] = (
    "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
    "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete",
    "dieciocho", "diecinueve", "veinte", "treinta", "cuarenta", "cincuenta",
    "sesenta", "setenta", "ochenta", "noventa", "cien", "ciento", "mil",
    "millon", "millones", "docena", "decenas",
)

VAGUE_QUANTIFIERS: Tuple[str, ...] = (
    "algunos", "algunas", "algun", "alguna", "varios", "varias", "unos", "unas",
    "muchos", "muchas", "pocos", "pocas", "cualquier", "cualquiera", "cierto",
    "cierta", "ciertos", "ciertas", "gente",
)

FORMAL_MARKERS: Tuple[str, ...] = (
    "usted", "ustedes", "su", "sus", "senor", "senora", "senorita", "senores",
    "don", "dona", "licenciado", "licenciada", "doctor", "doctora", "caballero",
    "le", "les",
)

INFORMAL_MARKERS: Tuple[str, ...] = (
    "tu", "tus", "vos", "vosotros", "vosotras", "mijo", "mija", "hijo", "hija",
    "chico", "chica", "tio", "tia", "compa", "guey", "wey",
)

INSULT_LEXICON: Tuple[str, ...] = (
    "idiota", "estupido", "estupida", "imbecil", "pendejo", "pendeja",
    "cabron", "cabrona", "mierda", "maldito", "maldita", "tarado", "tarada",
    "inutil", "basura", "patetico", "patetica", "ridiculo", "ridicula",
    "cobarde", "traidor", "traidora", "gordo", "gorda", "asqueroso",
    "asquerosa", "cerdo", "hijo de puta", "jodete", "chingada",
)

POLITE_MARKERS: Tuple[str, ...] = (
    "por favor", "disculpe", "disculpa", "perdon", "perdone", "con permiso",
    "le ruego", "se lo suplico", "muchas gracias",
)

SARCASM_CUES: Tuple[str, ...] = (
    "claro", "seguro", "por supuesto", "obvio", "desde luego", "que bonito",
    "que lindo", "excelente", "maravilloso", "genial", "perfecto", "bravo",
    "anda ya", "no me digas", "claro que si",
)

INTENSIFIERS: Tuple[str, ...] = (
    "muy", "demasiado", "tanto", "tan", "totalmente", "completamente",
    "absolutamente", "sumamente", "extremadamente", "increiblemente",
)

# 常见西语功能词/高频句首词（折叠重音后比对）：不作为专有名词证据。
# 目的：句首大写不会自动被当成人名，避免"Con el que""Después"之类误判；
# 不在本表内的句首大写词按人名/地名保守处理（宁可拦交人工，不放过丢名）。
CAPITALIZED_STOPWORDS: Tuple[str, ...] = (
    # 冠词/介词/连词/代词/限定词
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas", "de", "del",
    "al", "a", "en", "con", "por", "para", "sin", "sobre", "entre", "hasta",
    "desde", "hacia", "segun", "que", "como", "cuando", "donde", "quien",
    "cual", "cuales", "cuyo", "cuya", "y", "o", "u", "e", "ni", "pero",
    "sino", "aunque", "porque", "pues", "si", "no", "se", "le", "les", "me",
    "te", "nos", "os", "mi", "mis", "tu", "tus", "su", "sus", "nuestro",
    "nuestra", "nuestros", "nuestras", "yo", "ella", "ellos", "ellas",
    "usted", "ustedes", "nosotros", "vosotros", "esto", "eso", "esa", "ese",
    "esta", "este", "estos", "estas", "esos", "esas", "aquello", "aquella",
    "todo", "toda", "todos", "todas", "nada", "nadie", "alguien", "algo",
    # 高频副词/话语标记
    "ya", "ahora", "antes", "despues", "luego", "entonces", "tambien",
    "tampoco", "siempre", "nunca", "jamas", "aqui", "alli", "ahi", "alla",
    "aca", "muy", "mas", "menos", "bien", "mal", "asi", "solo", "solamente",
    "adios", "bueno", "buena", "claro", "seguro", "obvio", "vale", "mira",
    "oye", "hola", "gracias", "perdon", "disculpe", "disculpa", "ojala",
    "quizas", "tal", "vez", "ademas", "embargo", "mientras", "primero",
    "primera", "primer", "segundo", "segunda", "tercero", "tercera",
    "finalmente", "despacio", "rapido", "mucho", "mucha", "muchos", "muchas",
    "poco", "poca", "pocos", "pocas", "otro", "otra", "otros", "otras",
    "mismo", "misma", "cada", "mama", "papa",
    # 高频动词/助动词（各人称）
    "es", "son", "era", "eran", "fue", "fueron", "ser", "soy", "eres",
    "somos", "estoy", "estan", "estaba", "estaban",
    "estar", "hay", "habia", "ha", "han", "he", "hemos", "tener", "tengo",
    "tiene", "tienes", "tenemos", "tienen", "puedo", "puede", "pueden",
    "podemos", "puedes", "debo", "debe", "deben", "quiero", "quiere",
    "quieren", "quieres", "vamos", "voy", "va", "vas", "van", "vete", "ven",
    "espera", "esperate", "escucha", "escuchame", "dejame", "dime", "digame",
    "dijo", "dice", "dicen", "digo", "creo", "cree", "crees", "creemos",
    "sabes", "sabe", "saben", "sabemos", "haz", "hace", "hacen", "hacer",
    "hago", "ves", "veo", "ver", "toma", "tomalo", "sigue", "sigueme",
    "anda", "andas", "andate", "venga", "vengan", "pasa", "pase",
    "perdona", "perdone", "perdoname", "siento", "sientes",
)

# 书面词条与其口语候选同样不构成专有名词证据（"Posteriormente"→"Después"是同一槽位改写）
_LEXICON_SURFACE_WORDS = frozenset(
    _fold(word)
    for term, _pattern, candidates, _rationale in WRITTEN_TERM_LEXICON
    for phrase in (term, *candidates)
    for word in phrase.split()
)
_PROPER_NOUN_STOPWORDS = frozenset(
    _fold(item) for item in CAPITALIZED_STOPWORDS
) | _LEXICON_SURFACE_WORDS


def _phrase_pattern(terms: Iterable[str]) -> "re.Pattern[str]":
    ordered = sorted({_fold(term) for term in terms}, key=len, reverse=True)
    alternatives = "|".join(
        r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in ordered
    )
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def _count_phrase_hits(folded_text: str, pattern: "re.Pattern[str]") -> Counter:
    return Counter(match.group(0) for match in pattern.finditer(folded_text))


_NEGATION_RE = _phrase_pattern(NEGATION_WORDS)
_NEGATION_IDIOM_RE = _phrase_pattern(NEGATION_IDIOMS)
_NUMBER_WORD_RE = _phrase_pattern(NUMBER_WORDS)
_VAGUE_RE = _phrase_pattern(VAGUE_QUANTIFIERS)
_FORMAL_RE = _phrase_pattern(FORMAL_MARKERS)
_INFORMAL_RE = _phrase_pattern(INFORMAL_MARKERS)
_INSULT_RE = _phrase_pattern(INSULT_LEXICON)
_POLITE_RE = _phrase_pattern(POLITE_MARKERS)
_SARCASM_RE = _phrase_pattern(SARCASM_CUES)
_INTENSIFIER_RE = _phrase_pattern(INTENSIFIERS)

_ARABIC_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PROPER_NOUN_RE = re.compile(r"\b([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\b")


def extract_negations(text: str) -> Counter:
    """否定词多重集合（先遮蔽 no obstante 等固定搭配，避免把转折当否定）。"""
    folded = _fold(text or "")
    masked_chars = list(folded)
    for match in _NEGATION_IDIOM_RE.finditer(folded):
        for index in range(match.start(), match.end()):
            masked_chars[index] = " "
    return _count_phrase_hits("".join(masked_chars), _NEGATION_RE)


def extract_numbers(text: str) -> Counter:
    """数字集合（阿拉伯数字 + ≥2 的西语数词），用于事实实体比对。"""
    raw = text or ""
    counter: Counter = Counter()
    for match in _ARABIC_NUMBER_RE.finditer(raw):
        literal = match.group(0).replace(",", ".")
        # 归一前导零与尾随 .0，避免 03 与 3 被当作不同事实
        if "." in literal:
            literal = literal.rstrip("0").rstrip(".") or "0"
        literal = literal.lstrip("0") or "0"
        counter[literal] += 1
    counter.update(_count_phrase_hits(_fold(raw), _NUMBER_WORD_RE))
    return counter


def extract_proper_nouns(text: str) -> Counter:
    """专有名词（人名/地名/机构名）候选，用于"事实与实体零丢失"校验。

    规则：首字母大写且后续小写的词，折叠重音后不在常见西语词表/书面词表中即视为
    专有名词（句首同样计入）。局限：与常用词同形的人名（如 Sol、Esperanza）无法
    区分；ALL-CAPS 强调词不参与。宁可把可疑大写词交人工复核，也不放过丢名。
    """
    counter: Counter = Counter()
    for match in _PROPER_NOUN_RE.finditer(text or ""):
        token = _fold(match.group(1))
        if token in _PROPER_NOUN_STOPWORDS:
            continue
        counter[token] += 1
    return counter


def _relationship_violation(
    original: str,
    suggested: str,
    context: Optional[Any],
) -> Optional[str]:
    """称谓/长幼尊卑一致性：不得把 usted 口语化成 tú，也不得抹掉敬称。"""
    folded_original, folded_suggested = _fold(original), _fold(suggested)
    formal_before = sum(_count_phrase_hits(folded_original, _FORMAL_RE).values())
    formal_after = sum(_count_phrase_hits(folded_suggested, _FORMAL_RE).values())
    informal_before = sum(_count_phrase_hits(folded_original, _INFORMAL_RE).values())
    informal_after = sum(_count_phrase_hits(folded_suggested, _INFORMAL_RE).values())

    if informal_after > informal_before:
        return (
            "改写引入非正式称谓词（tú/tu/vos 等），原文语气更正式，"
            "称谓与长幼尊卑不得被口语化抹平"
        )
    if formal_after < formal_before:
        return (
            f"改写丢失敬称标记（正式标记 {formal_before} → {formal_after}），"
            "usted/su/敬称不得被替换或省略"
        )
    register = _fold(getattr(context, "honorific_register", "") or "")
    if ("informal" in register or register in {"tu"}) and formal_after > formal_before:
        return "语境卡指定非正式称谓，改写引入了正式敬称"
    return None


def _stance_violation(
    original: str,
    suggested: str,
    context: Optional[Any],
) -> Optional[str]:
    """情绪强度与反讽立场一致性：禁止把角色攻击性台词"净化"成中性表达。"""
    folded_original, folded_suggested = _fold(original), _fold(suggested)
    insults_before = _count_phrase_hits(folded_original, _INSULT_RE)
    insults_after = _count_phrase_hits(folded_suggested, _INSULT_RE)
    for term, count in insults_before.items():
        if insults_after.get(term, 0) < count:
            return f"改写削弱/删除攻击性词「{term.strip()}」，角色敌意被净化"
    for term, count in insults_after.items():
        if count > insults_before.get(term, 0):
            return f"改写新增攻击性词「{term.strip()}」，原文立场被加强"

    intens_before = sum(_count_phrase_hits(folded_original, _INTENSIFIER_RE).values())
    intens_after = sum(_count_phrase_hits(folded_suggested, _INTENSIFIER_RE).values())
    if insults_before and intens_after < intens_before:
        return "攻击性台词的强度副词被削减，情绪强度不一致"

    stance = _fold(getattr(context, "stance", "") or "")
    polite_before = sum(_count_phrase_hits(folded_original, _POLITE_RE).values())
    polite_after = sum(_count_phrase_hits(folded_suggested, _POLITE_RE).values())
    if stance == "hostile" and polite_after > polite_before:
        return "语境立场为敌意，改写却加入礼貌套话，人物立场被抹平"
    if stance == "polite" and sum(insults_after.values()) > sum(insults_before.values()):
        return "语境立场为礼貌，改写却引入攻击性表达"

    is_sarcastic = bool(getattr(context, "is_sarcastic", False)) or stance == "sarcastic"
    if is_sarcastic:
        cues_before = sum(_count_phrase_hits(folded_original, _SARCASM_RE).values())
        cues_after = sum(_count_phrase_hits(folded_suggested, _SARCASM_RE).values())
        if cues_before and cues_after < cues_before:
            return "反讽语境下改写过删除反讽标记，反讽含义被抹平"
    return None


def check_semantic_guards(
    original_text: str,
    suggested_text: str,
    context: Optional[Any] = None,
) -> SemanticGuardCheck:
    """四类语义风险规则检查闸门：否定极性、事实实体、关系称谓、情绪反讽。

    任一违规即 ``is_blocked=True``，调用方必须废弃该候选（``auto_apply_allowed``
    不得为真）。identity 情况（suggested == original）恒通过。
    """
    original = original_text or ""
    suggested = suggested_text or ""
    violations: List[str] = []
    reasons: List[str] = []

    # 1) 否定极性规则比对
    neg_before = extract_negations(original)
    neg_after = extract_negations(suggested)
    if neg_before != neg_after:
        violations.append(SemanticViolationType.POLARITY_MISMATCH.value)
        reasons.append(
            "否定极性被改变：原文否定词 "
            f"{dict(sorted(neg_before.items()))} → 改写 {dict(sorted(neg_after.items()))}"
        )

    # 2) 事实与实体集合一致（数字 + 专有名词 + 禁概括化模糊）
    num_before, num_after = extract_numbers(original), extract_numbers(suggested)
    if num_before != num_after:
        violations.append(SemanticViolationType.ENTITY_MISMATCH.value)
        reasons.append(
            f"数字/数量事实被改变：原文 {dict(sorted(num_before.items()))} → "
            f"改写 {dict(sorted(num_after.items()))}"
        )
    else:
        proper_before = extract_proper_nouns(original)
        proper_after = extract_proper_nouns(suggested)
        if proper_before != proper_after:
            violations.append(SemanticViolationType.ENTITY_MISMATCH.value)
            reasons.append(
                f"专有名词（人名/地名）集合被改变：原文 {dict(sorted(proper_before.items()))} → "
                f"改写 {dict(sorted(proper_after.items()))}"
            )
        else:
            vague_before = _count_phrase_hits(_fold(original), _VAGUE_RE)
            vague_after = _count_phrase_hits(_fold(suggested), _VAGUE_RE)
            added = {
                term: count - vague_before.get(term, 0)
                for term, count in vague_after.items()
                if count > vague_before.get(term, 0)
            }
            if added:
                violations.append(SemanticViolationType.ENTITY_MISMATCH.value)
                reasons.append(
                    f"改写引入概括化模糊量词 {list(added)}，事实被概括化（如 3 personas → algunas personas）"
                )

    # 3) 人物关系与称谓一致
    relationship_reason = _relationship_violation(original, suggested, context)
    if relationship_reason:
        violations.append(SemanticViolationType.RELATIONSHIP_MISMATCH.value)
        reasons.append(relationship_reason)

    # 4) 情绪强度与反讽立场一致
    stance_reason = _stance_violation(original, suggested, context)
    if stance_reason:
        violations.append(SemanticViolationType.STANCE_MISMATCH.value)
        reasons.append(stance_reason)

    return SemanticGuardCheck(
        polarity_consistent=SemanticViolationType.POLARITY_MISMATCH.value not in violations,
        entity_consistent=SemanticViolationType.ENTITY_MISMATCH.value not in violations,
        relationship_consistent=SemanticViolationType.RELATIONSHIP_MISMATCH.value not in violations,
        stance_consistent=SemanticViolationType.STANCE_MISMATCH.value not in violations,
        violations=violations,
        is_blocked=bool(violations),
        block_reasons=reasons,
    )


# ==========================================
# 6. 单句与整批主流程
# ==========================================

def _build_candidate(
    segment: SubtitleSegment,
    readability: ReadabilityMetrics,
    complexity: ComplexityAnalysis,
    deviation: OralDeviationAnalysis,
) -> Optional[OralCandidate]:
    """组合改写/拆句建议并强制过四重闸门；无建议返回 None。"""
    suggested = deviation.suggested_rewrite if deviation.is_warn else None
    splits = complexity.split_suggestion

    if suggested is None and not splits:
        return None

    if suggested is not None:
        guard_text = suggested
    else:
        guard_text = " ".join(part.text for part in splits or [])
    guard = check_semantic_guards(segment.text, guard_text, segment.context)

    reasons: List[str] = []
    if suggested is not None:
        terms = "、".join(
            f"{item['term']}→{'/'.join(item['oral_candidates'])}"
            for item in deviation.detected_written_terms
        )
        reasons.append(
            f"书面语倾向分 {deviation.written_score} > {WRITTEN_SCORE_WARN_THRESHOLD}，"
            f"命中 {terms}；按 es-MX 影视口语改写，改写文本须过语义闸门"
        )
    if splits:
        reasons.append(
            "复杂句按语法断点提供时间连续无损拆句（"
            + " + ".join(f"{part.duration_sec}s" for part in splits)
            + f" = {readability.duration_sec}s，总时长守恒）"
        )
    if readability.syntax_line_break_suggestion and not splits:
        reasons.append("行长/行数超限，提供 ≤2 行、每行 ≤42 字符的断行建议")
    if guard.is_blocked:
        reasons.append("语义闸门阻断：" + "；".join(guard.block_reasons) + "；候选废弃，仅留审计")

    candidate_id = f"{segment.segment_id}-cand-001"
    return OralCandidate(
        candidate_id=candidate_id,
        original_text=segment.text,
        suggested_text=suggested,
        split_candidates=splits,
        guard_check=guard,
        is_blocked=guard.is_blocked,
        auto_apply_allowed=not guard.is_blocked,
        explanation="；".join(reasons) if reasons else "无改写建议",
    )


def review_oral_segment(segment: SubtitleSegment) -> OralReviewItemResult:
    """单句口语审校：可读性 + 复杂度 + 翻译腔 + 候选（含四重闸门）。"""
    readability = analyze_readability(segment)
    complexity = analyze_complexity(segment.text, segment.start_time, segment.end_time)
    deviation = analyze_oral_deviation(segment.text)
    candidate = _build_candidate(segment, readability, complexity, deviation)

    readability_status = worst_status(
        readability.cps_status, readability.line_status, readability.duration_status
    )
    style_status = ReadabilityStatus.PASS
    if deviation.is_warn or complexity.is_complex:
        style_status = ReadabilityStatus.WARN
    gate_status = (
        ReadabilityStatus.BLOCK
        if (candidate is not None and candidate.is_blocked)
        else ReadabilityStatus.PASS
    )
    status = worst_status(readability_status, style_status, gate_status)

    return OralReviewItemResult(
        segment_id=segment.segment_id,
        original_text=segment.text,
        readability=readability,
        complexity=complexity,
        deviation=deviation,
        candidate=candidate,
        status=status,
    )


def review_oral_request(request: OralReviewRequest) -> OralReviewResult:
    """整批口语审校入口：逐句处理 + manifest 溯源（零模型、零 Token）。"""
    total_chars = sum(len(segment.text) for segment in request.segments)
    if total_chars > 10000:
        raise ValueError(
            f"ORAL_CONTEXT_BUDGET_EXCEEDED: 输入字符总数 ({total_chars}) 超出单批预算上限 (10000)，请分批处理"
        )
    started = datetime.now(timezone.utc)
    items = [review_oral_segment(segment) for segment in request.segments]
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    issue_counter: Counter = Counter()
    for item in items:
        issue_counter.update(item.readability.issues)
    blocked_candidates = [item for item in items if item.candidate and item.candidate.is_blocked]
    candidates = [item.candidate for item in items if item.candidate]

    manifest: Dict[str, Any] = {
        "schema_version": ORAL_REVIEW_SCHEMA_VERSION,
        "policy_version": ORAL_POLICY_VERSION,
        "target_language": request.target_language,
        "pipeline": "deterministic_rules_only",
        "stages": [
            "readability_metrics",
            "complexity_and_lossless_split",
            "oral_deviation_scoring",
            "semantic_invariant_guard",
        ],
        "model_used": False,
        "model_invocation": "NOT_INVOKED",
        "token_used": 0,
        "latency_ms": elapsed_ms,
        "thresholds": {
            "cps_soft_limit": CPS_SOFT_LIMIT,
            "cps_hard_limit": CPS_HARD_LIMIT,
            "max_line_length": MAX_LINE_LENGTH,
            "max_line_count": MAX_LINE_COUNT,
            "min_duration_sec": MIN_DURATION_SEC,
            "max_duration_sec": MAX_DURATION_SEC,
            "complex_conjunction_threshold": COMPLEX_CONJUNCTION_THRESHOLD,
            "nesting_depth_threshold": NESTING_DEPTH_THRESHOLD,
            "written_score_warn_threshold": WRITTEN_SCORE_WARN_THRESHOLD,
            "split_time_tolerance": SPLIT_TIME_TOLERANCE,
        },
        "profile_status": "PILOT_THRESHOLDS_UNCALIBRATED",  # P-ORAL 未经批准不作生产硬门槛
        "segment_count": len(items),
        "issue_counts": dict(sorted(issue_counter.items())),
        "candidate_count": len(candidates),
        "blocked_candidate_count": len(blocked_candidates),
        "auto_apply_allowed_count": sum(1 for c in candidates if c.auto_apply_allowed),
        "complex_sentence_count": sum(1 for item in items if item.complexity.is_complex),
        "split_suggestion_count": sum(1 for item in items if item.complexity.split_suggestion),
        "deviation_warn_count": sum(1 for item in items if item.deviation.is_warn),
        "semantic_guard": "ENFORCED",
        "split_time_invariance": "ENFORCED",
        "human_review_required": bool(blocked_candidates)
        or any(item.status != ReadabilityStatus.PASS for item in items),
        "rule_mode": "deterministic_heuristic",
        "naturalness_model": "NOT_CONNECTED",
        "coverage_limitations": [
            "CPS、行长与时长为代码确定性计算；词表自然度与反讽/极性信号仅作启发式辅助",
            "未接入大语言模型，不承诺全场景口语自然度与深层反讽/语义零风险保护，需人工审核员终审",
        ],
        "note": "纯白盒规则引擎；不调用任何大模型，不写入已人工确认/锁定稿",
    }

    return OralReviewResult(
        request_id=request.request_id,
        task_ref=request.task_ref,
        items=items,
        manifest=manifest,
        overall_status=worst_status(*(item.status for item in items)),
    )

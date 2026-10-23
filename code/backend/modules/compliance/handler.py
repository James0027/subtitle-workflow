"""平台合规质检、多格式导出与双向重解析模块 —— 纯确定性处理器。

流水线（全 Python，零模型、零网络、零计费）::

    cues ──① validate_platform_profile ── 违规 → QC_FAILED（不生成交付文件）
                                     └─ 通过
          ──② generate_srt / generate_vtt ── 成品文本
          ──③ verify_round_trip（独立 parser 读回）── 差异 → QC_FAILED
                                     └─ 一致
          ──④ sha256 打包 → VALIDATED
          ──⑤ verify_and_apply_signoff（真人五维哈希）→ PUBLISH_READY

口径与版本（``COMPLIANCE_POLICY_VERSION = 2026-10-22.1``）：

- 可见字符：拉丁/西里尔等按「换行归一为单空格、行内连续空白折叠为单空格、去首尾空白」
  计数（含词间空格与标点）；CJK 按**非空白字符**计数（方块字无词间空格），
  满足 MET-ORAL-001「字符计数口径随版本固化」。
- 脚本判定：非空白字符中 CJK 占比 ≥ 0.3 判为 CJK，取 ``cjk_max_line_length``。
- CPS = 可见字符数 / 显示秒数；``duration <= 0`` 为硬非法（``DURATION_INVALID``），
  不参与 CPS 计算，避免除零与「非法句美化 CPS」。
- 时间码精度：毫秒四舍五入（``ROUND_HALF_UP`` 于 Decimal），反解析对账容差 0.001s。

安全底线：本模块只产出候选成品与校验/签发记录；不写人工稿、不自动发布、
不构造 ``PUBLISHED``、不代替真人签发（RULE-SUB-001/002、RULE-OUT-002/003）。
"""

import hashlib
import hmac
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from code.backend.modules.compliance.contract import (
    CJK_MAX_LINE_LENGTH,
    COMPLIANCE_POLICY_VERSION,
    COMPLIANCE_SCHEMA_VERSION,
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

# ==========================================
# 0. 常量与错误类型
# ==========================================

# 浮点容差：只在边界比较时使用，不允许用来「抹平」真实超限
CPS_EPS = 1e-9
TIME_EPS = 1e-9
ROUND_TRIP_TIME_TOLERANCE = 0.001

MINUTE_MS = 60_000
HOUR_MS = 3_600_000

CJK_RATIO_THRESHOLD = 0.3

# 机器/代理签发者前缀：首个冒号/连字符前命中即拒绝（人工签发人标识不得使用）
MACHINE_SIGNER_PREFIXES = ("agent", "model", "system", "bot", "ai", "automation", "pipeline")

RULE_READABILITY = "RULE-ORAL-001"
RULE_DELIVERY_GATE = "RULE-OUT-002"
RULE_SIGNOFF = "RULE-SUB-002"

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class ComplianceError(ValueError):
    """合规模块的确定性阻断错误（输入非法、状态越权、导出被拦）。"""


class SubtitleParseError(ComplianceError):
    """成品文件反解析失败（格式非法、序号断裂、台词为空/截断）。"""


class SignoffError(ComplianceError):
    """签发校验失败（非 VALIDATED、五维哈希失效、文件 hash 不符、机器代签）。"""


# ==========================================
# 1. 文本口径工具
# ==========================================

_INLINE_WS_RE = re.compile(r"[ \t\u00a0\u3000]+")

# CJK 统一表意文字/扩展 A、假名、谚文、兼容表意文字、扩展 B 以上平面
_CJK_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x3040, 0x30FF),
    (0xAC00, 0xD7AF),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2FA1F),
)


def _is_cjk_char(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK_RANGES)


def count_cjk_chars(text: str) -> int:
    return sum(1 for char in text if _is_cjk_char(char))


def count_visible_chars(text: str) -> int:
    """可见字符总数（含标点与词间单空格，不含换行；换行按词间隔计 1 个空格）。"""
    return len(" ".join(split_lines(text)))


def visible_char_count(text: str, script: Optional[str] = None) -> int:
    """按脚本口径计数：CJK 去空白，拉丁类含词间单空格。

    换行视为词间隔（折叠为一个空格），与 oral_review 的可见字符口径一致，
    避免「多加换行」被算成更低 CPS。
    """
    resolved = script or detect_script(text)
    joined = " ".join(split_lines(text))
    if resolved == "cjk":
        return sum(1 for char in joined if not char.isspace())
    return len(joined)


def detect_script(text: str) -> str:
    """非空白字符中 CJK 占比 ≥ 0.3 → ``cjk``，否则 ``latin``。"""
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return "latin"
    ratio = count_cjk_chars(text) / len(non_space)
    return "cjk" if ratio >= CJK_RATIO_THRESHOLD else "latin"


def normalize_text(text: str) -> str:
    """反查对账口径：统一换行、行内空白折叠为单空格、去首尾空白与首尾空行。

    保留行结构（不把 ``\\n`` 折叠为空格），否则「生成器丢行/并句」会被误判为一致。
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_INLINE_WS_RE.sub(" ", line).strip() for line in unified.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(line for line in lines)


def split_lines(text: str) -> List[str]:
    """按行切分并逐行规范化空白；空文本返回空列表。"""
    normalized = normalize_text(text)
    if not normalized:
        return []
    return normalized.split("\n")


def line_char_count(line: str, script: Optional[str] = None) -> int:
    """单行字符数（行长上限口径，与 CPS 可见字符口径一致）。"""
    return visible_char_count(line, script)


def _render_text(text: str) -> str:
    """生成文件用的文本：只统一换行，绝不改写台词内容。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_format(fmt: str) -> str:
    """格式别名归一：``.srt``/``SRT``/``webvtt`` → ``srt``/``vtt``。"""
    cleaned = (fmt or "").strip().lower().lstrip(".")
    aliases = {"srt": "srt", "subrip": "srt", "vtt": "vtt", "webvtt": "vtt", "web_vtt": "vtt"}
    resolved = aliases.get(cleaned)
    if resolved is None or resolved not in SUPPORTED_EXPORT_FORMATS:
        raise ComplianceError(f"不支持的导出格式：{fmt!r}（当前仅 {SUPPORTED_EXPORT_FORMATS}）")
    return resolved


# ==========================================
# 2. 平台 Profile 校验器
# ==========================================


def _issue(
    issue_type: ComplianceIssueType,
    cue_index: Optional[int],
    message: str,
    **details: Any,
) -> ComplianceIssue:
    payload: Dict[str, Any] = {"policy_version": COMPLIANCE_POLICY_VERSION}
    payload.update(details)
    return ComplianceIssue(issue_type=issue_type, cue_index=cue_index, message=message, details=payload)


def validate_platform_profile(
    cues: Sequence[SubtitleCue],
    profile: Optional[PlatformProfile] = None,
) -> ValidationResult:
    """按平台 profile 逐条校验（行长/行数/时长/CPS/时间轴），任一违规即 QC_FAILED。

    时间轴按**传入顺序**判定相邻关系：调用方必须按时间轴正序传入确认稿。
    空集合与空台词直接阻断，不出具「通过」结论（不装成功）。
    """
    resolved_profile = profile or PlatformProfile()
    if resolved_profile.profile_name not in SUPPORTED_PLATFORM_PROFILES:
        raise ComplianceError(
            f"未登记的平台 profile：{resolved_profile.profile_name}"
            f"（已登记：{SUPPORTED_PLATFORM_PROFILES}）；缺 profile 不得降标准放行"
        )
    if not cues:
        raise ComplianceError("空字幕集合不得出具校验通过结论（空结果不装成功）")

    issues: List[ComplianceIssue] = []
    previous: Optional[SubtitleCue] = None

    for cue in cues:
        if not normalize_text(cue.text):
            raise ComplianceError(f"第 {cue.index} 条字幕台词为空，属输入非法，阻断校验")

        script = detect_script(cue.text)
        line_limit = (
            resolved_profile.cjk_max_line_length if script == "cjk" else resolved_profile.max_line_length
        )
        lines = split_lines(cue.text)
        duration = cue.end_time - cue.start_time

        # (1) 屏幕行数
        if len(lines) > resolved_profile.max_lines:
            issues.append(
                _issue(
                    ComplianceIssueType.LINE_COUNT_EXCEEDED,
                    cue.index,
                    f"第 {cue.index} 条字幕 {len(lines)} 行，超过上限 {resolved_profile.max_lines} 行",
                    rule_id=RULE_READABILITY,
                    profile=resolved_profile.profile_name,
                    observed=len(lines),
                    threshold=resolved_profile.max_lines,
                )
            )

        # (2) 单行字符数
        for line_no, line in enumerate(lines, start=1):
            char_count = line_char_count(line, script)
            if char_count > line_limit:
                issues.append(
                    _issue(
                        ComplianceIssueType.LINE_LENGTH_EXCEEDED,
                        cue.index,
                        f"第 {cue.index} 条第 {line_no} 行 {char_count} 字符，"
                        f"超过 {script} 上限 {line_limit} 字符",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        script=script,
                        line_index=line_no,
                        observed=char_count,
                        threshold=line_limit,
                    )
                )

        # (3) 持续时间（零/负时长硬非法，不参与 CPS）
        if duration <= 0:
            issues.append(
                _issue(
                    ComplianceIssueType.DURATION_INVALID,
                    cue.index,
                    f"第 {cue.index} 条字幕显示时长 {duration:.3f}s 非法（必须 > 0）",
                    rule_id=RULE_READABILITY,
                    profile=resolved_profile.profile_name,
                    observed=duration,
                    threshold="> 0",
                )
            )
        else:
            if duration < resolved_profile.min_duration_sec - TIME_EPS:
                issues.append(
                    _issue(
                        ComplianceIssueType.DURATION_TOO_SHORT,
                        cue.index,
                        f"第 {cue.index} 条字幕 {duration * 1000:.0f}ms，"
                        f"低于最短 {resolved_profile.min_duration_sec * 1000:.0f}ms",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        observed=round(duration, 6),
                        threshold=resolved_profile.min_duration_sec,
                    )
                )
            if duration > resolved_profile.max_duration_sec + TIME_EPS:
                issues.append(
                    _issue(
                        ComplianceIssueType.DURATION_TOO_LONG,
                        cue.index,
                        f"第 {cue.index} 条字幕 {duration:.3f}s，"
                        f"超过最长 {resolved_profile.max_duration_sec:.3f}s",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        observed=round(duration, 6),
                        threshold=resolved_profile.max_duration_sec,
                    )
                )

            # (4) 阅读速度 CPS
            chars = visible_char_count(cue.text, script)
            cps = chars / duration
            if cps - resolved_profile.max_cps > CPS_EPS:
                issues.append(
                    _issue(
                        ComplianceIssueType.CPS_EXCEEDED,
                        cue.index,
                        f"第 {cue.index} 条字幕 CPS={cps:.2f}，超过硬上限 {resolved_profile.max_cps:.2f}",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        script=script,
                        observed=round(cps, 3),
                        threshold=resolved_profile.max_cps,
                        visible_chars=chars,
                        duration_sec=round(duration, 6),
                    )
                )

        # (5) 镜头与空隙（相邻字幕）
        if previous is not None:
            gap = cue.start_time - previous.end_time
            if gap < -TIME_EPS:
                issues.append(
                    _issue(
                        ComplianceIssueType.TIMECODE_OVERLAP,
                        cue.index,
                        f"第 {cue.index} 条开始时间 {cue.start_time:.3f}s "
                        f"早于上一条结束时间 {previous.end_time:.3f}s（重叠 {-gap * 1000:.0f}ms）",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        observed=round(gap, 6),
                        threshold=">= 0",
                        previous_index=previous.index,
                    )
                )
            elif gap < resolved_profile.min_gap_sec - TIME_EPS:
                issues.append(
                    _issue(
                        ComplianceIssueType.GAP_TOO_SMALL,
                        cue.index,
                        f"第 {cue.index} 条与上一条间隔 {gap * 1000:.0f}ms，"
                        f"小于最小 {resolved_profile.min_gap_sec * 1000:.0f}ms（2 帧）",
                        rule_id=RULE_READABILITY,
                        profile=resolved_profile.profile_name,
                        observed=round(gap, 6),
                        threshold=resolved_profile.min_gap_sec,
                        previous_index=previous.index,
                    )
                )
        previous = cue

    is_valid = not issues
    return ValidationResult(
        is_valid=is_valid,
        status=ComplianceStatus.VALIDATED if is_valid else ComplianceStatus.QC_FAILED,
        issues=issues,
        checked_cue_count=len(cues),
        profile_used=resolved_profile.profile_name,
    )


# ==========================================
# 3. 多格式生成器
# ==========================================


def format_timecode(seconds: float, separator: str = ",") -> str:
    """秒 → ``HH:MM:SS{sep}mmm``（毫秒 3 位补零；SRT 用 ``,``，WebVTT 用 ``.``）。"""
    if separator not in (",", "."):
        raise ComplianceError(f"时间码分隔符非法：{separator!r}（仅 ',' 或 '.'）")
    if seconds < 0:
        raise ComplianceError(f"时间码不得为负：{seconds}")
    total_ms = int((Decimal(str(seconds)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    hours, remainder = divmod(total_ms, HOUR_MS)
    minutes, remainder = divmod(remainder, MINUTE_MS)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _render_blocks(cues: Sequence[SubtitleCue], separator: str) -> List[str]:
    """生成序号严格递增的字幕块；序号按传入顺序重排为 1..n（交付件不继承内部序号）。"""
    blocks: List[str] = []
    for position, cue in enumerate(cues, start=1):
        text = _render_text(cue.text)
        if not normalize_text(text):
            raise ComplianceError(f"第 {cue.index} 条字幕台词为空，不得写入交付文件")
        blocks.append(
            f"{position}\n"
            f"{format_timecode(cue.start_time, separator)} --> "
            f"{format_timecode(cue.end_time, separator)}\n"
            f"{text}"
        )
    return blocks


def generate_srt(cues: Sequence[SubtitleCue]) -> str:
    """生成标准 SRT：毫秒用 ``,`` 分隔，块间双换行，文件以单个换行收尾。"""
    blocks = _render_blocks(cues, ",")
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def generate_vtt(cues: Sequence[SubtitleCue]) -> str:
    """生成标准 WebVTT：``WEBVTT`` 标头 + 空行，毫秒用 ``.`` 分隔，块间双换行。"""
    blocks = _render_blocks(cues, ".")
    header = "WEBVTT\n\n"
    if not blocks:
        return header
    return header + "\n\n".join(blocks) + "\n"


# ==========================================
# 4. 独立反解析器（不共享生成器代码）
# ==========================================

_BLOCK_SPLIT_RE = re.compile(r"\n[ \t]*\n")

_SRT_TIMECODE_RE = re.compile(
    r"^(?P<h1>\d{2,}):(?P<m1>[0-5]\d):(?P<s1>[0-5]\d),(?P<ms1>\d{3})"
    r"[ \t]*-->[ \t]*"
    r"(?P<h2>\d{2,}):(?P<m2>[0-5]\d):(?P<s2>[0-5]\d),(?P<ms2>\d{3})$"
)

_VTT_TIMECODE_RE = re.compile(
    r"^(?P<h1>\d{2,}):(?P<m1>[0-5]\d):(?P<s1>[0-5]\d)\.(?P<ms1>\d{3})"
    r"[ \t]*-->[ \t]*"
    r"(?P<h2>\d{2,}):(?P<m2>[0-5]\d):(?P<s2>[0-5]\d)\.(?P<ms2>\d{3})$"
)


def _normalize_document(content: str) -> str:
    return content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _ms_to_seconds(match: "re.Match[str]", prefix: str) -> float:
    return (
        int(match.group(f"h{prefix}")) * 3600
        + int(match.group(f"m{prefix}")) * 60
        + int(match.group(f"s{prefix}"))
        + int(match.group(f"ms{prefix}")) / 1000
    )


def parse_srt(content: str) -> List[ParsedCue]:
    """反解析 SRT 文本。格式非法/序号断裂/台词为空一律抛 ``SubtitleParseError``。"""
    document = _normalize_document(content).strip("\n")
    if not document.strip():
        return []

    cues: List[ParsedCue] = []
    for position, block in enumerate(_BLOCK_SPLIT_RE.split(document), start=1):
        lines = block.split("\n")
        if len(lines) < 2:
            raise SubtitleParseError(f"SRT 第 {position} 块缺少时间码行（疑似截断）")
        index_text = lines[0].strip()
        if not index_text.isdigit():
            raise SubtitleParseError(f"SRT 第 {position} 块序号非法：{index_text!r}")
        index = int(index_text)
        if index != position:
            raise SubtitleParseError(f"SRT 序号断裂：第 {position} 块序号为 {index}")
        match = _SRT_TIMECODE_RE.match(lines[1].strip())
        if match is None:
            raise SubtitleParseError(f"SRT 第 {position} 块时间码非法：{lines[1].strip()!r}")
        body = lines[2:]
        if not any(line.strip() for line in body):
            raise SubtitleParseError(f"SRT 第 {position} 块台词为空（疑似丢字/截断）")
        cues.append(
            ParsedCue(
                index=index,
                start_time=_ms_to_seconds(match, "1"),
                end_time=_ms_to_seconds(match, "2"),
                text="\n".join(body),
            )
        )
    return cues


def parse_vtt(content: str) -> List[ParsedCue]:
    """反解析 WebVTT 文本。

    支持 ``NOTE`` / ``STYLE`` / ``REGION`` 注释块与可选数字块标识；
    带 cue 设置（如 ``align:center``）的时间码行直接拒绝——本模块契约不含样式模型，
    静默忽略样式即属有损转换（MET-OUT-003 要求有损转换须预先批准）。
    """
    document = _normalize_document(content)
    if not document.strip():
        raise SubtitleParseError("WebVTT 缺少 WEBVTT 标头")
    lines = document.split("\n")
    if not lines[0].strip().startswith("WEBVTT"):
        raise SubtitleParseError(f"WebVTT 首行必须是 WEBVTT 标头，实际：{lines[0].strip()!r}")

    rest = "\n".join(lines[1:]).strip("\n")
    if not rest.strip():
        return []

    cues: List[ParsedCue] = []
    expected_index = 1
    for position, block in enumerate(_BLOCK_SPLIT_RE.split(rest), start=1):
        block_lines = [line for line in block.split("\n")] if block.strip() else []
        if not block_lines:
            continue
        head = block_lines[0].strip()
        if head.startswith(("NOTE", "STYLE", "REGION")):
            continue

        if head.isdigit():
            index = int(head)
            if len(block_lines) < 2:
                raise SubtitleParseError(f"WebVTT 第 {position} 块缺少时间码行")
            timecode_line = block_lines[1].strip()
            body = block_lines[2:]
        else:
            index = expected_index
            timecode_line = head
            body = block_lines[1:]

        if "-->" in timecode_line and _VTT_TIMECODE_RE.match(timecode_line) is None:
            raise SubtitleParseError(
                f"WebVTT 第 {position} 块时间码含未支持的 cue 设置或格式：{timecode_line!r}"
            )
        match = _VTT_TIMECODE_RE.match(timecode_line)
        if match is None:
            raise SubtitleParseError(f"WebVTT 第 {position} 块时间码非法：{timecode_line!r}")
        if index != expected_index:
            raise SubtitleParseError(f"WebVTT 序号断裂：第 {position} 块序号为 {index}")
        if not any(line.strip() for line in body):
            raise SubtitleParseError(f"WebVTT 第 {position} 块台词为空（疑似丢字/截断）")

        cues.append(
            ParsedCue(
                index=index,
                start_time=_ms_to_seconds(match, "1"),
                end_time=_ms_to_seconds(match, "2"),
                text="\n".join(body),
            )
        )
        expected_index += 1
    return cues


def parse_subtitle(content: str, fmt: str) -> List[ParsedCue]:
    """按格式分发到对应反解析器。"""
    resolved = normalize_format(fmt)
    return parse_srt(content) if resolved == "srt" else parse_vtt(content)


# ==========================================
# 5. 双向重解析一致性反查
# ==========================================


def _round_trip_failure(fmt: str, reason: str) -> RoundTripResult:
    return RoundTripResult(
        is_valid=False,
        format=fmt,
        cue_count=0,
        discrepancies=[reason],
        status=ComplianceStatus.QC_FAILED,
    )


def verify_round_trip(
    original_cues: Sequence[SubtitleCue],
    generated_content: str,
    format: str,
) -> RoundTripResult:
    """把成品文件重新解析回内存，与原始台词逐条对账（100% 一致才放行）。

    四条断言：条数、序号顺序、起止时间（容差 0.001s）、规范化空白后的文本。
    """
    fmt = normalize_format(format)
    try:
        parsed = parse_subtitle(generated_content, fmt)
    except SubtitleParseError as exc:
        return _round_trip_failure(fmt, f"反解析失败：{exc}")

    discrepancies: List[str] = []
    original = list(original_cues)
    if len(parsed) != len(original):
        discrepancies.append(
            f"台词条数不一致：原始 {len(original)} 条，反解析 {len(parsed)} 条（丢句或重复写入）"
        )

    for position, (source, restored) in enumerate(zip(original, parsed), start=1):
        if restored.index != position:
            discrepancies.append(
                f"第 {position} 条序号顺序不一致：原始 {source.index}，反解析 {restored.index}"
            )
        if abs(restored.start_time - source.start_time) >= ROUND_TRIP_TIME_TOLERANCE:
            discrepancies.append(
                f"第 {position} 条开始时间偏移：原始 {source.start_time:.3f}s，"
                f"反解析 {restored.start_time:.3f}s"
            )
        if abs(restored.end_time - source.end_time) >= ROUND_TRIP_TIME_TOLERANCE:
            discrepancies.append(
                f"第 {position} 条结束时间偏移：原始 {source.end_time:.3f}s，"
                f"反解析 {restored.end_time:.3f}s"
            )
        if normalize_text(restored.text) != normalize_text(source.text):
            discrepancies.append(
                f"第 {position} 条文本不一致：原始 {normalize_text(source.text)!r}，"
                f"反解析 {normalize_text(restored.text)!r}"
            )

    is_valid = not discrepancies
    return RoundTripResult(
        is_valid=is_valid,
        format=fmt,
        cue_count=len(parsed),
        discrepancies=discrepancies,
        status=ComplianceStatus.VALIDATED if is_valid else ComplianceStatus.QC_FAILED,
    )


# ==========================================
# 6. 五维哈希与真人签发
# ==========================================


def sha256_text(content: str) -> str:
    """成品文件 sha256（UTF-8 字节；与 schema Artifact.checksum_sha256 口径一致）。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_signoff_hash(
    task_id: str,
    translation_revision: str,
    rule_version: str,
    validation_id: str,
    artifact_sha256: str,
) -> str:
    """五维签发哈希：sha256("task:revision:rule:validation:artifact_sha256")。"""
    for name, value in (
        ("task_id", task_id),
        ("translation_revision", translation_revision),
        ("rule_version", rule_version),
        ("validation_id", validation_id),
        ("artifact_sha256", artifact_sha256),
    ):
        if not value or not str(value).strip():
            raise SignoffError(f"签发要素 {name} 为空，不得用空值凑哈希")
    payload = f"{task_id}:{translation_revision}:{rule_version}:{validation_id}:{artifact_sha256}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assert_artifact_integrity(artifact: ArtifactPackage) -> None:
    """文件内容必须与其声明 hash 一致（防止内容被替换而 hash 字段照抄）。"""
    if not artifact.content:
        raise SignoffError("ARTIFACT_EMPTY: 产物内容为空，不得签发")
    actual = sha256_text(artifact.content)
    if not hmac.compare_digest(actual, artifact.artifact_sha256):
        raise SignoffError(
            f"ARTIFACT_HASH_MISMATCH: 内容实际 sha256={actual}，声明 {artifact.artifact_sha256}"
        )


def _assert_human_signer(signer_id: str) -> None:
    cleaned = signer_id.strip().lower()
    if not cleaned:
        raise SignoffError("SIGNOFF_NO_SIGNER: 签发人标识为空")
    prefix = re.split(r"[:\-_/@]", cleaned, maxsplit=1)[0]
    if prefix in MACHINE_SIGNER_PREFIXES:
        raise SignoffError(
            f"SIGNOFF_MACHINE_FORBIDDEN: {signer_id!r} 属于机器/代理标识，"
            "必须由有权真人审核员签发（RULE-SUB-002）"
        )


def build_signoff(
    artifact: ArtifactPackage,
    *,
    task_id: str,
    translation_revision: str,
    rule_version: str,
    validation_id: str,
    signer_id: str,
    signed_at: Optional[str] = None,
) -> SignoffData:
    """构造签发记录（哈希按当前产物与五维要素确定计算）。

    本函数只做确定性哈希绑定，不判断签署人是否有权——权限由 RBAC/权限层拒绝，
    本模块不假称已校核真人身份。
    """
    _assert_artifact_integrity(artifact)
    _assert_human_signer(signer_id)
    return SignoffData(
        task_id=task_id,
        translation_revision=translation_revision,
        rule_version=rule_version,
        validation_id=validation_id,
        artifact_sha256=artifact.artifact_sha256,
        signoff_hash=compute_signoff_hash(
            task_id, translation_revision, rule_version, validation_id, artifact.artifact_sha256
        ),
        signer_id=signer_id,
        signed_at=signed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def verify_and_apply_signoff(
    artifact: ArtifactPackage,
    signoff: SignoffData,
) -> ArtifactPackage:
    """验签并跃迁状态：仅 ``VALIDATED`` 可签，五维哈希必须精确匹配当前包。

    任一上游要素（task / revision / rule / validation / artifact 内容）改变都会使
    哈希失配 → ``SignoffError``，必须重新质检并重签（旧签名不能签新包）。
    """
    if artifact.status != ComplianceStatus.VALIDATED:
        raise SignoffError(
            f"SIGNOFF_NOT_VALIDATED: 当前状态 {artifact.status.value}，"
            "只有通过质检与重解析反查的 VALIDATED 包才可签发"
        )
    if artifact.validation_result is None or not artifact.validation_result.is_valid:
        raise SignoffError("SIGNOFF_NO_VALIDATION: 缺少有效校验结论，不得签发")

    _assert_artifact_integrity(artifact)
    _assert_human_signer(signoff.signer_id)

    if artifact.validation_id is not None and signoff.validation_id != artifact.validation_id:
        raise SignoffError(
            f"SIGNOFF_VALIDATION_MISMATCH: 签发绑定 validation_id={signoff.validation_id!r}，"
            f"当前包为 {artifact.validation_id!r}（旧结论不能签新包）"
        )
    if signoff.artifact_sha256 != artifact.artifact_sha256:
        raise SignoffError(
            f"SIGNOFF_ARTIFACT_MISMATCH: 签发绑定文件 hash={signoff.artifact_sha256}，"
            f"当前包为 {artifact.artifact_sha256}"
        )

    manifest_rev = (artifact.manifest or {}).get("translation_revision")
    if manifest_rev and signoff.translation_revision != manifest_rev:
        raise SignoffError(
            f"SIGNOFF_REVISION_MISMATCH: 签发绑定 translation_revision={signoff.translation_revision!r}，"
            f"产物 manifest 声明为 {manifest_rev!r}（五维要素未绑定产物事实）"
        )
    manifest_rule = (artifact.manifest or {}).get("rule_version")
    if manifest_rule and signoff.rule_version != manifest_rule:
        raise SignoffError(
            f"SIGNOFF_RULE_MISMATCH: 签发绑定 rule_version={signoff.rule_version!r}，"
            f"产物 manifest 声明为 {manifest_rule!r}（五维要素未绑定产物事实）"
        )

    computed = compute_signoff_hash(
        signoff.task_id,
        signoff.translation_revision,
        signoff.rule_version,
        signoff.validation_id,
        signoff.artifact_sha256,
    )
    if not hmac.compare_digest(computed, signoff.signoff_hash):
        raise SignoffError(
            "SIGNOFF_HASH_INVALID: 五维要素与签发哈希不符"
            f"（任务/译文修订/规则版本/校验标识/文件 hash 任一被改动；computed={computed}）"
        )

    return artifact.model_copy(update={"status": ComplianceStatus.PUBLISH_READY, "signoff": signoff})


# ==========================================
# 7. 主调度
# ==========================================


def _base_manifest(
    *,
    task_id: str,
    translation_revision: str,
    rule_version: str,
    validation_id: str,
    profile: PlatformProfile,
    fmt: str,
    cue_count: int,
    elapsed_ms: int,
) -> Dict[str, Any]:
    return {
        "schema_version": COMPLIANCE_SCHEMA_VERSION,
        "policy_version": COMPLIANCE_POLICY_VERSION,
        "task_id": task_id,
        "translation_revision": translation_revision,
        "rule_version": rule_version,
        "validation_id": validation_id,
        "profile_name": profile.profile_name,
        "profile_source": "PRD 2026-10-22 §1 公开 Netflix 基准；规则注册表未登记生产硬门槛",
        "format": fmt,
        "deterministic_python": True,
        "model_used": False,
        "model_invocation": "NOT_INVOKED",
        "token_used": 0,
        "external_api_calls": 0,
        "cue_count": cue_count,
        "char_policy": "latin_with_spaces/cjk_without_spaces",
        "round_trip": "PERFORMED",
        "human_signoff_required": True,
        "system_auto_publish": False,
        "latency_ms": elapsed_ms,
    }


def validate_and_export_artifact(
    *,
    task_id: str,
    translation_revision: str,
    rule_version: str,
    cues: Sequence[SubtitleCue],
    format: str = "srt",
    profile: Optional[PlatformProfile] = None,
    artifact_id: Optional[str] = None,
    validation_id: Optional[str] = None,
) -> ArtifactPackage:
    """主调度：平台校验 → 生成文件 → 重解析反查 → 哈希打包。

    返回 ``VALIDATED`` 包（尚不可对外交付，仅内部受控预览）或 ``QC_FAILED`` 包
    （``content`` 恒为空，不含可交付文件，`manifest` 保留阻断原因）。
    """
    started = datetime.now(timezone.utc)
    fmt = normalize_format(format)
    resolved_profile = profile or PlatformProfile()
    if not cues:
        raise ComplianceError("空字幕集合不得导出（空结果不装成功）")

    resolved_artifact_id = artifact_id or f"artifact-{uuid.uuid4().hex[:12]}"
    resolved_validation_id = validation_id or f"val-{uuid.uuid4().hex[:12]}"

    validation = validate_platform_profile(cues, resolved_profile)
    manifest = _base_manifest(
        task_id=task_id,
        translation_revision=translation_revision,
        rule_version=rule_version,
        validation_id=resolved_validation_id,
        profile=resolved_profile,
        fmt=fmt,
        cue_count=len(cues),
        elapsed_ms=0,
    )
    manifest["artifact_id"] = resolved_artifact_id

    if not validation.is_valid:
        manifest.update(
            {
                "deliverable_emitted": False,
                "gate": "BLOCKED_BY_PLATFORM_PROFILE",
                "issue_types": sorted({issue.issue_type.value for issue in validation.issues}),
                "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            }
        )
        return ArtifactPackage(
            artifact_id=resolved_artifact_id,
            format=fmt,
            content="",
            artifact_sha256=EMPTY_SHA256,
            status=ComplianceStatus.QC_FAILED,
            validation_result=validation,
            round_trip_result=None,
            validation_id=resolved_validation_id,
            manifest=manifest,
        )

    content = generate_srt(cues) if fmt == "srt" else generate_vtt(cues)
    digest = sha256_text(content)
    round_trip = verify_round_trip(cues, content, fmt)

    if not round_trip.is_valid:
        manifest.update(
            {
                "deliverable_emitted": False,
                "gate": "BLOCKED_BY_ROUND_TRIP",
                "discrepancy_count": len(round_trip.discrepancies),
                "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            }
        )
        return ArtifactPackage(
            artifact_id=resolved_artifact_id,
            format=fmt,
            content="",
            artifact_sha256=EMPTY_SHA256,
            status=ComplianceStatus.QC_FAILED,
            validation_result=validation,
            round_trip_result=round_trip,
            validation_id=resolved_validation_id,
            manifest=manifest,
        )

    manifest.update(
        {
            "deliverable_emitted": True,
            "gate": "VALIDATED_INTERNAL_PREVIEW_ONLY",
            "artifact_sha256": digest,
            "round_trip_cue_count": round_trip.cue_count,
            "bytes": len(content.encode("utf-8")),
            "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }
    )
    return ArtifactPackage(
        artifact_id=resolved_artifact_id,
        format=fmt,
        content=content,
        artifact_sha256=digest,
        status=ComplianceStatus.VALIDATED,
        validation_result=validation,
        round_trip_result=round_trip,
        validation_id=resolved_validation_id,
        manifest=manifest,
    )

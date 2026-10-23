"""compliance 模块单元测试（工单 05A）。

覆盖范围与工单条目对应：

- 1/2(1) 平台 Profile 校验：CPS、行长（拉丁 42 / CJK 21）、行数、时长上下限、
  零/负时长、时间码重叠、< 2 帧空隙 → 全部 QC_FAILED 阻断。
- 2(2) SRT / WebVTT 生成：毫秒分隔符（``,`` 与 ``.``）、3 位补零、多行、双换行、
  序号严格递增、小时进位。
- 2(3) 独立反解析器 + 双向重解析对账：无损 100% 一致；删句/删字/时间微调/格式破坏
  必须被检出。
- 2(4) 五维哈希签发：哈希公式、正确签发跃迁 PUBLISH_READY、任一要素篡改失效、
  非 VALIDATED 拦截、机器代签拦截。
- 2(5)/3 主调度与包级导出。

全部为确定性工程自测，不调用任何模型或外部接口，不代表真实业务验收。
"""

import hashlib
import re

import pytest
from pydantic import ValidationError

from code.backend.modules.compliance import (
    CJK_MAX_LINE_LENGTH,
    COMPLIANCE_ISSUE_TYPES,
    COMPLIANCE_STATUSES,
    LATIN_MAX_LINE_LENGTH,
    ArtifactPackage,
    ComplianceError,
    ComplianceIssueType,
    ComplianceStatus,
    PlatformProfile,
    SignoffData,
    SignoffError,
    SubtitleCue,
    SubtitleParseError,
    ValidationResult,
    build_signoff,
    compute_signoff_hash,
    count_visible_chars,
    detect_script,
    format_timecode,
    generate_srt,
    generate_vtt,
    normalize_format,
    normalize_text,
    parse_srt,
    parse_vtt,
    sha256_text,
    validate_and_export_artifact,
    validate_platform_profile,
    verify_and_apply_signoff,
    verify_round_trip,
    visible_char_count,
)

TASK_ID = "task-05a"
REVISION = "tr-3"
RULE_VERSION = "2026-10-22.1"
CJK = "字"


# ==========================================
# 辅助构造
# ==========================================


def cue(index: int, start: float, end: float, text: str) -> SubtitleCue:
    return SubtitleCue(index=index, start_time=start, end_time=end, text=text)


def two_cues(text1: str = "Hola, mundo.", text2: str = "Adios.") -> list:
    return [cue(1, 1.234, 3.5, text1), cue(2, 4.0, 6.0, text2)]


def issue_types(result: ValidationResult) -> list:
    return [issue.issue_type for issue in result.issues]


def export(cues, fmt: str = "srt", **kwargs) -> ArtifactPackage:
    return validate_and_export_artifact(
        task_id=TASK_ID,
        translation_revision=REVISION,
        rule_version=RULE_VERSION,
        cues=cues,
        format=fmt,
        **kwargs,
    )


def sign(package: ArtifactPackage, **overrides) -> SignoffData:
    fields = {
        "task_id": TASK_ID,
        "translation_revision": REVISION,
        "rule_version": RULE_VERSION,
        "validation_id": package.validation_id,
        "signer_id": "reviewer-01",
    }
    fields.update(overrides)
    return build_signoff(package, **fields)


# ==========================================
# 1. 契约层
# ==========================================


class TestContract:
    def test_status_enum_covers_five_states(self):
        assert COMPLIANCE_STATUSES == (
            "VALIDATED",
            "QC_FAILED",
            "DRAFT",
            "PUBLISH_READY",
            "PUBLISHED",
        )

    def test_issue_types_are_closed_set_of_ten(self):
        assert len(COMPLIANCE_ISSUE_TYPES) == 10
        for expected in (
            "CPS_EXCEEDED",
            "LINE_LENGTH_EXCEEDED",
            "LINE_COUNT_EXCEEDED",
            "DURATION_TOO_SHORT",
            "DURATION_TOO_LONG",
            "DURATION_INVALID",
            "TIMECODE_OVERLAP",
            "GAP_TOO_SMALL",
            "ROUND_TRIP_MISMATCH",
            "SIGNOFF_INVALID",
        ):
            assert expected in COMPLIANCE_ISSUE_TYPES

    def test_profile_defaults_are_netflix_baseline(self):
        profile = PlatformProfile()
        assert profile.profile_name == "netflix_timed_text"
        assert profile.max_line_length == 42
        assert profile.cjk_max_line_length == 21
        assert profile.max_lines == 2
        assert profile.min_duration_sec == 0.833
        assert profile.max_duration_sec == 7.0
        assert profile.max_cps == 20.0
        assert profile.min_gap_sec == 0.083

    def test_profile_rejects_inverted_duration_bounds(self):
        with pytest.raises(ValidationError):
            PlatformProfile(min_duration_sec=8.0, max_duration_sec=7.0)

    def test_cue_requires_positive_index(self):
        with pytest.raises(ValidationError):
            SubtitleCue(index=0, start_time=0.0, end_time=1.0, text="Hola.")

    def test_validation_result_rejects_valid_with_issues(self):
        with pytest.raises(ValidationError):
            ValidationResult(
                is_valid=True,
                status=ComplianceStatus.VALIDATED,
                issues=[
                    {
                        "issue_type": "CPS_EXCEEDED",
                        "cue_index": 1,
                        "message": "CPS 超限",
                    }
                ],
                checked_cue_count=1,
                profile_used="netflix_timed_text",
            )

    def test_artifact_forbids_published_state(self):
        with pytest.raises(ValidationError) as excinfo:
            ArtifactPackage(
                artifact_id="artifact-x",
                format="srt",
                content="1\n00:00:01,000 --> 00:00:02,000\nHola.\n",
                artifact_sha256=sha256_text("x"),
                status=ComplianceStatus.PUBLISHED,
            )
        assert "PUBLISHED" in str(excinfo.value)

    def test_artifact_validated_requires_passed_validation(self):
        with pytest.raises(ValidationError):
            ArtifactPackage(
                artifact_id="artifact-x",
                format="srt",
                content="",
                artifact_sha256=sha256_text(""),
                status=ComplianceStatus.VALIDATED,
            )

    def test_artifact_publish_ready_requires_signoff(self):
        validation = validate_platform_profile(two_cues())
        with pytest.raises(ValidationError):
            ArtifactPackage(
                artifact_id="artifact-x",
                format="srt",
                content="1\n00:00:01,234 --> 00:00:03,500\nHola, mundo.\n",
                artifact_sha256=sha256_text("x"),
                status=ComplianceStatus.PUBLISH_READY,
                validation_result=validation,
            )

    def test_artifact_qc_failed_must_not_carry_deliverable(self):
        failed = validate_platform_profile([cue(1, 0.0, 0.1, "Hola.")])
        with pytest.raises(ValidationError):
            ArtifactPackage(
                artifact_id="artifact-x",
                format="srt",
                content="1\n00:00:00,000 --> 00:00:00,100\nHola.\n",
                artifact_sha256=sha256_text("x"),
                status=ComplianceStatus.QC_FAILED,
                validation_result=failed,
            )


# ==========================================
# 2. SRT 生成
# ==========================================


class TestSrtGeneration:
    def test_timecode_uses_comma_and_three_digit_millis(self):
        assert format_timecode(1.234, ",") == "00:00:01,234"
        assert format_timecode(3.5, ",") == "00:00:03,500"
        assert format_timecode(0.005, ",") == "00:00:00,005"

    def test_block_structure_uses_blank_line_separator(self):
        content = generate_srt(two_cues())
        assert content == (
            "1\n00:00:01,234 --> 00:00:03,500\nHola, mundo.\n"
            "\n"
            "2\n00:00:04,000 --> 00:00:06,000\nAdios.\n"
        )
        assert content.endswith("\n") and not content.endswith("\n\n")

    def test_multiline_text_is_preserved_verbatim(self):
        content = generate_srt([cue(1, 1.0, 3.0, "Adios.\nHasta luego.")])
        assert content == "1\n00:00:01,000 --> 00:00:03,000\nAdios.\nHasta luego.\n"

    def test_sequence_is_renumbered_strictly_increasing(self):
        content = generate_srt([cue(7, 1.0, 3.0, "A"), cue(9, 4.0, 6.0, "B")])
        assert [line for line in content.split("\n") if line.isdigit()] == ["1", "2"]

    def test_hour_rollover_is_padded(self):
        assert format_timecode(3661.5, ",") == "01:01:01,500"

    def test_sub_millisecond_is_rounded_half_up(self):
        assert format_timecode(1.2345, ",") == "00:00:01,235"
        assert format_timecode(1.2344, ",") == "00:00:01,234"

    def test_negative_timecode_is_rejected(self):
        with pytest.raises(ComplianceError):
            format_timecode(-0.001, ",")

    def test_carriage_return_is_normalized(self):
        content = generate_srt([cue(1, 1.0, 3.0, "Linea 1\r\nLinea 2")])
        assert "\r" not in content
        assert content == "1\n00:00:01,000 --> 00:00:03,000\nLinea 1\nLinea 2\n"


# ==========================================
# 3. WebVTT 生成
# ==========================================


class TestVttGeneration:
    def test_header_and_blank_line(self):
        content = generate_vtt(two_cues())
        assert content.startswith("WEBVTT\n\n")

    def test_timecode_uses_dot_separator(self):
        content = generate_vtt([cue(1, 1.234, 3.5, "Hola mundo.")])
        assert "00:00:01.234 --> 00:00:03.500" in content
        assert "," not in content

    def test_blocks_and_multiline_text(self):
        content = generate_vtt([cue(1, 1.05, 3.0, "Uno\nDos")])
        assert content == "WEBVTT\n\n1\n00:00:01.050 --> 00:00:03.000\nUno\nDos\n"

    def test_empty_cue_list_returns_header_only(self):
        assert generate_vtt([]) == "WEBVTT\n\n"


# ==========================================
# 4. 独立反解析器
# ==========================================


class TestParser:
    def test_parse_srt_basic(self):
        parsed = parse_srt("1\n00:00:01,234 --> 00:00:03,500\nHola.\n")
        assert len(parsed) == 1
        assert parsed[0].index == 1
        assert parsed[0].start_time == pytest.approx(1.234)
        assert parsed[0].end_time == pytest.approx(3.5)
        assert parsed[0].text == "Hola."

    def test_parse_srt_tolerates_bom_and_crlf(self):
        content = "\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\nHola.\r\n"
        parsed = parse_srt(content)
        assert parsed[0].start_time == pytest.approx(1.0)
        assert parsed[0].text == "Hola."

    def test_parse_srt_multiline_body(self):
        parsed = parse_srt("1\n00:00:01,000 --> 00:00:02,000\nUno\nDos\n")
        assert parsed[0].text == "Uno\nDos"

    def test_parse_srt_rejects_truncated_block(self):
        with pytest.raises(SubtitleParseError):
            parse_srt("1\n00:00:01,000 --> 00:00:02,000\n")

    def test_parse_srt_rejects_index_gap(self):
        content = "1\n00:00:01,000 --> 00:00:02,000\nA\n\n3\n00:00:03,000 --> 00:00:04,000\nB\n"
        with pytest.raises(SubtitleParseError):
            parse_srt(content)

    def test_parse_srt_rejects_dot_separator(self):
        with pytest.raises(SubtitleParseError):
            parse_srt("1\n00:00:01.000 --> 00:00:02.000\nA\n")

    def test_parse_vtt_requires_header(self):
        with pytest.raises(SubtitleParseError):
            parse_vtt("1\n00:00:01.000 --> 00:00:02.000\nA\n")

    def test_parse_vtt_skips_note_blocks(self):
        content = "WEBVTT\n\nNOTE 校对说明\n不参与解析\n\n1\n00:00:01.000 --> 00:00:02.000\nA\n"
        parsed = parse_vtt(content)
        assert len(parsed) == 1
        assert parsed[0].text == "A"

    def test_parse_vtt_rejects_cue_settings(self):
        content = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000 align:center\nA\n"
        with pytest.raises(SubtitleParseError):
            parse_vtt(content)

    def test_parse_vtt_supports_implicit_index(self):
        parsed = parse_vtt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nA\n")
        assert parsed[0].index == 1

    def test_normalize_format_aliases(self):
        assert normalize_format(".SRT") == "srt"
        assert normalize_format("webvtt") == "vtt"
        with pytest.raises(ComplianceError):
            normalize_format("ass")


# ==========================================
# 5. 双向重解析对账
# ==========================================


class TestRoundTrip:
    def test_srt_round_trip_is_lossless(self):
        cues = two_cues()
        result = verify_round_trip(cues, generate_srt(cues), "srt")
        assert result.is_valid is True
        assert result.discrepancies == []
        assert result.cue_count == 2
        assert result.status == ComplianceStatus.VALIDATED

    def test_vtt_round_trip_is_lossless(self):
        cues = two_cues(text1="Uno\nDos", text2="Tres")
        result = verify_round_trip(cues, generate_vtt(cues), "vtt")
        assert result.is_valid is True
        assert result.cue_count == 2

    def test_whitespace_differences_are_normalized_not_ignored(self):
        cues = [cue(1, 1.0, 3.0, "Hola   mundo.  ")]
        result = verify_round_trip(cues, generate_srt(cues), "srt")
        assert result.is_valid is True
        assert normalize_text("Hola   mundo.  ") == "Hola mundo."

    def test_removed_cue_is_detected(self):
        cues = two_cues()
        content = "1\n00:00:01,234 --> 00:00:03,500\nHola, mundo.\n"
        result = verify_round_trip(cues, content, "srt")
        assert result.is_valid is False
        assert result.status == ComplianceStatus.QC_FAILED
        assert any("条数" in item for item in result.discrepancies)

    def test_truncated_text_is_detected(self):
        cues = [cue(1, 1.0, 3.0, "Hola, mundo cruel.")]
        content = "1\n00:00:01,000 --> 00:00:03,000\nHola, mundo\n"
        result = verify_round_trip(cues, content, "srt")
        assert result.is_valid is False
        assert any("文本不一致" in item for item in result.discrepancies)

    def test_merged_lines_are_detected(self):
        cues = [cue(1, 1.0, 3.0, "Uno\nDos")]
        content = "1\n00:00:01,000 --> 00:00:03,000\nUno Dos\n"
        result = verify_round_trip(cues, content, "srt")
        assert result.is_valid is False
        assert any("文本不一致" in item for item in result.discrepancies)

    def test_time_shift_is_detected(self):
        cues = two_cues()
        tampered = generate_srt(cues).replace("00:00:03,500", "00:00:03,520")
        result = verify_round_trip(cues, tampered, "srt")
        assert result.is_valid is False
        assert any("结束时间偏移" in item for item in result.discrepancies)

    def test_sub_millisecond_shift_is_tolerated(self):
        cues = [cue(1, 1.0, 3.0, "Hola.")]
        tampered = "1\n00:00:01,000 --> 00:00:03,000\nHola.\n"
        assert verify_round_trip([cue(1, 1.0004, 3.0004, "Hola.")], tampered, "srt").is_valid is True

    def test_malformed_content_yields_qc_failed_instead_of_silence(self):
        result = verify_round_trip(two_cues(), "这不是字幕文件", "srt")
        assert result.is_valid is False
        assert result.cue_count == 0
        assert any("反解析失败" in item for item in result.discrepancies)

    def test_unsupported_format_raises(self):
        with pytest.raises(ComplianceError):
            verify_round_trip(two_cues(), "", "ass")


# ==========================================
# 6. 平台 Profile 硬校验
# ==========================================


class TestProfileValidation:
    def test_clean_cues_pass(self):
        result = validate_platform_profile(two_cues())
        assert result.is_valid is True
        assert result.status == ComplianceStatus.VALIDATED
        assert result.checked_cue_count == 2
        assert result.profile_used == "netflix_timed_text"

    def test_cps_above_20_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 2.0, "a" * 42)])
        assert result.is_valid is False
        assert ComplianceIssueType.CPS_EXCEEDED in issue_types(result)
        detail = result.issues[0].details
        assert detail["observed"] == pytest.approx(21.0)
        assert detail["threshold"] == 20.0

    def test_cps_exactly_20_passes(self):
        result = validate_platform_profile([cue(1, 0.0, 2.0, "a" * 40)])
        assert result.is_valid is True

    def test_latin_line_42_chars_passes(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, "a" * LATIN_MAX_LINE_LENGTH)])
        assert result.is_valid is True

    def test_latin_line_43_chars_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, "a" * 43)])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.LINE_LENGTH_EXCEEDED]
        assert result.issues[0].details["script"] == "latin"

    def test_cjk_line_21_chars_passes(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, CJK * CJK_MAX_LINE_LENGTH)])
        assert result.is_valid is True

    def test_cjk_line_22_chars_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, CJK * 22)])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.LINE_LENGTH_EXCEEDED]
        assert result.issues[0].details["script"] == "cjk"
        assert result.issues[0].details["threshold"] == 21

    def test_detect_script_threshold(self):
        assert detect_script(CJK * 10) == "cjk"
        assert detect_script("Hello world") == "latin"

    def test_three_lines_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, "A\nB\nC")])
        assert result.is_valid is False
        assert ComplianceIssueType.LINE_COUNT_EXCEEDED in issue_types(result)

    def test_two_lines_pass(self):
        result = validate_platform_profile([cue(1, 0.0, 3.0, "A\nB")])
        assert result.is_valid is True

    def test_duration_below_833ms_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 0.832, "Hola.")])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.DURATION_TOO_SHORT]

    def test_duration_exactly_833ms_passes(self):
        result = validate_platform_profile([cue(1, 0.0, 0.833, "Hola.")])
        assert result.is_valid is True

    def test_duration_above_7s_is_blocked(self):
        result = validate_platform_profile([cue(1, 0.0, 7.001, "Hola.")])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.DURATION_TOO_LONG]

    def test_duration_exactly_7s_passes(self):
        result = validate_platform_profile([cue(1, 0.0, 7.0, "Hola.")])
        assert result.is_valid is True

    def test_zero_duration_is_invalid(self):
        result = validate_platform_profile([cue(1, 2.0, 2.0, "Hola.")])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.DURATION_INVALID]

    def test_negative_duration_is_invalid(self):
        result = validate_platform_profile([cue(1, 3.0, 2.0, "Hola.")])
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.DURATION_INVALID]

    def test_timecode_overlap_is_blocked(self):
        result = validate_platform_profile(
            [cue(1, 0.0, 2.0, "Uno"), cue(2, 1.5, 3.5, "Dos")]
        )
        assert result.is_valid is False
        assert ComplianceIssueType.TIMECODE_OVERLAP in issue_types(result)
        assert result.issues[0].cue_index == 2

    def test_gap_below_two_frames_is_blocked(self):
        result = validate_platform_profile(
            [cue(1, 0.0, 2.0, "Uno"), cue(2, 2.02, 4.0, "Dos")]
        )
        assert result.is_valid is False
        assert issue_types(result) == [ComplianceIssueType.GAP_TOO_SMALL]

    def test_gap_exactly_083s_passes(self):
        result = validate_platform_profile(
            [cue(1, 0.0, 2.0, "Uno"), cue(2, 2.083, 4.0, "Dos")]
        )
        assert result.is_valid is True

    def test_zero_gap_is_blocked(self):
        result = validate_platform_profile(
            [cue(1, 0.0, 2.0, "Uno"), cue(2, 2.0, 4.0, "Dos")]
        )
        assert result.is_valid is False
        assert ComplianceIssueType.GAP_TOO_SMALL in issue_types(result)

    def test_multiple_issues_are_all_reported(self):
        result = validate_platform_profile(
            [cue(1, 0.0, 1.0, "a" * 43), cue(2, 1.0, 1.9, "Dos")]
        )
        types = set(issue_types(result))
        assert ComplianceIssueType.LINE_LENGTH_EXCEEDED in types
        assert ComplianceIssueType.CPS_EXCEEDED in types
        assert ComplianceIssueType.GAP_TOO_SMALL in types
        assert result.status == ComplianceStatus.QC_FAILED
        assert len(result.issues) >= 3

    def test_empty_cue_list_does_not_pass(self):
        with pytest.raises(ComplianceError):
            validate_platform_profile([])

    def test_blank_text_is_rejected(self):
        with pytest.raises(ComplianceError):
            validate_platform_profile([cue(1, 0.0, 2.0, "   ")])

    def test_unregistered_profile_is_rejected(self):
        with pytest.raises(ComplianceError):
            validate_platform_profile(two_cues(), PlatformProfile(profile_name="custom_platform"))

    def test_custom_thresholds_are_honored(self):
        strict = PlatformProfile(max_cps=10.0)
        result = validate_platform_profile([cue(1, 0.0, 2.0, "a" * 30)], strict)
        assert result.is_valid is False
        assert ComplianceIssueType.CPS_EXCEEDED in issue_types(result)

    def test_visible_char_counts(self):
        assert count_visible_chars("Uno Dos") == 7
        assert visible_char_count("Uno\nDos") == 7
        assert visible_char_count(CJK * 5) == 5


# ==========================================
# 7. 五维签发
# ==========================================


class TestSignoff:
    def test_hash_formula_matches_spec(self):
        payload = "t1:rev-3:rules-1:val-9:" + "0" * 64
        expected = hashlib.sha256(payload.encode()).hexdigest()
        assert compute_signoff_hash("t1", "rev-3", "rules-1", "val-9", "0" * 64) == expected
        assert re.fullmatch(r"[0-9a-f]{64}", expected)

    def test_empty_element_is_rejected(self):
        with pytest.raises(SignoffError):
            compute_signoff_hash("t1", "", "rules-1", "val-9", "0" * 64)

    def test_valid_signoff_moves_to_publish_ready(self):
        package = export(two_cues())
        assert package.status == ComplianceStatus.VALIDATED
        signed = verify_and_apply_signoff(package, sign(package))
        assert signed.status == ComplianceStatus.PUBLISH_READY
        assert signed.signoff is not None
        assert signed.signoff.signer_id == "reviewer-01"
        assert signed.content == package.content
        assert signed.artifact_sha256 == package.artifact_sha256

    def test_signoff_binds_validation_id(self):
        package = export(two_cues())
        record = sign(package)
        assert record.validation_id == package.validation_id
        assert record.artifact_sha256 == package.artifact_sha256

    def test_tampered_revision_invalidates_signoff(self):
        package = export(two_cues())
        record = sign(package)
        forged = record.model_copy(update={"translation_revision": "tr-4"})
        with pytest.raises(SignoffError) as excinfo:
            verify_and_apply_signoff(package, forged)
        assert "SIGNOFF_REVISION_MISMATCH" in str(excinfo.value)

    def test_tampered_artifact_content_invalidates_signoff(self):
        package = export(two_cues())
        record = sign(package)
        tampered = package.model_copy(
            update={
                "content": package.content.replace("Hola, mundo.", "Hola mundo."),
            }
        )
        with pytest.raises(SignoffError) as excinfo:
            verify_and_apply_signoff(tampered, record)
        assert "ARTIFACT_HASH_MISMATCH" in str(excinfo.value)

    def test_rehash_after_content_change_still_requires_new_validation(self):
        package = export(two_cues())
        record = sign(package)
        new_content = package.content + ""
        rehashed = package.model_copy(
            update={"content": new_content + "\n", "artifact_sha256": sha256_text(new_content + "\n")}
        )
        with pytest.raises(SignoffError):
            verify_and_apply_signoff(rehashed, record)

    def test_draft_state_cannot_be_signed(self):
        package = export(two_cues())
        draft = package.model_copy(update={"status": ComplianceStatus.DRAFT})
        with pytest.raises(SignoffError) as excinfo:
            verify_and_apply_signoff(draft, sign(package))
        assert "SIGNOFF_NOT_VALIDATED" in str(excinfo.value)

    def test_qc_failed_package_cannot_be_signed(self):
        failed = export([cue(1, 0.0, 0.2, "Hola.")])
        assert failed.status == ComplianceStatus.QC_FAILED
        record = SignoffData(
            task_id=TASK_ID,
            translation_revision=REVISION,
            rule_version=RULE_VERSION,
            validation_id=failed.validation_id,
            artifact_sha256=failed.artifact_sha256,
            signoff_hash=compute_signoff_hash(
                TASK_ID, REVISION, RULE_VERSION, failed.validation_id, failed.artifact_sha256
            ),
            signer_id="reviewer-01",
            signed_at="2026-10-22T10:00:00+08:00",
        )
        with pytest.raises(SignoffError):
            verify_and_apply_signoff(failed, record)

    def test_validation_id_mismatch_is_blocked(self):
        package = export(two_cues())
        record = sign(package, validation_id="val-other")
        with pytest.raises(SignoffError) as excinfo:
            verify_and_apply_signoff(package, record)
        assert "SIGNOFF_VALIDATION_MISMATCH" in str(excinfo.value)

    def test_machine_signer_is_rejected(self):
        package = export(two_cues())
        with pytest.raises(SignoffError) as excinfo:
            sign(package, signer_id="agent:hermes")
        assert "SIGNOFF_MACHINE_FORBIDDEN" in str(excinfo.value)

    def test_resigned_publish_ready_package_is_blocked(self):
        package = export(two_cues())
        signed = verify_and_apply_signoff(package, sign(package))
        with pytest.raises(SignoffError):
            verify_and_apply_signoff(signed, sign(package))


# ==========================================
# 8. 主调度
# ==========================================


class TestDispatcher:
    def test_srt_export_is_validated_with_manifest_facts(self):
        package = export(two_cues())
        assert package.status == ComplianceStatus.VALIDATED
        assert package.format == "srt"
        assert package.artifact_sha256 == sha256_text(package.content)
        assert package.round_trip_result is not None and package.round_trip_result.is_valid
        assert package.validation_result is not None and package.validation_result.is_valid
        assert package.manifest["model_used"] is False
        assert package.manifest["token_used"] == 0
        assert package.manifest["external_api_calls"] == 0
        assert package.manifest["human_signoff_required"] is True
        assert package.manifest["system_auto_publish"] is False

    def test_vtt_export_is_validated(self):
        package = export(two_cues(), fmt="vtt")
        assert package.status == ComplianceStatus.VALIDATED
        assert package.content.startswith("WEBVTT\n\n")

    def test_profile_violation_returns_qc_failed_without_deliverable(self):
        package = export([cue(1, 0.0, 2.0, "a" * 43)])
        assert package.status == ComplianceStatus.QC_FAILED
        assert package.content == ""
        assert package.manifest["deliverable_emitted"] is False
        assert package.manifest["gate"] == "BLOCKED_BY_PLATFORM_PROFILE"
        assert "LINE_LENGTH_EXCEEDED" in package.manifest["issue_types"]

    def test_lossy_generation_is_caught_by_round_trip(self):
        # 台词内含空行会破坏 SRT 块结构；放宽行数上限让 profile 校验先通过，
        # 以确保拦截来自重解析反查而不是平台规则
        relaxed = PlatformProfile(max_lines=3, max_duration_sec=10.0)
        package = export([cue(1, 1.0, 3.0, "Uno\n\nDos")], profile=relaxed)
        assert package.status == ComplianceStatus.QC_FAILED
        assert package.content == ""
        assert package.manifest["gate"] == "BLOCKED_BY_ROUND_TRIP"
        assert package.round_trip_result is not None
        assert package.round_trip_result.discrepancies

    def test_blank_line_in_text_is_blocked_by_line_count(self):
        package = export([cue(1, 1.0, 3.0, "Uno\n\nDos")])
        assert package.status == ComplianceStatus.QC_FAILED
        assert "LINE_COUNT_EXCEEDED" in package.manifest["issue_types"]

    def test_empty_cue_list_is_blocked(self):
        with pytest.raises(ComplianceError):
            export([])

    def test_unsupported_format_is_blocked(self):
        with pytest.raises(ComplianceError):
            export(two_cues(), fmt="ass")

    def test_end_to_end_export_then_sign(self):
        package = export(two_cues(), fmt="vtt")
        signed = verify_and_apply_signoff(package, sign(package))
        assert signed.status == ComplianceStatus.PUBLISH_READY
        assert signed.manifest["deliverable_emitted"] is True
        assert signed.validation_result.status == ComplianceStatus.VALIDATED
        assert parse_vtt(signed.content)[0].text == "Hola, mundo."

    def test_artifact_ids_are_unique_per_call(self):
        first, second = export(two_cues()), export(two_cues())
        assert first.artifact_id != second.artifact_id
        assert first.validation_id != second.validation_id

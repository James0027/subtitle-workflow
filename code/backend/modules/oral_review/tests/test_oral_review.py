"""oral_review 模块单元测试。

覆盖范围（对应工单 04 的 6 项要求）：

1. 可读性度量：可见字符口径、CPS 公式与 17/20 软硬阈值、行长/行数、时长极值、
   ≤0s 硬非法（cps=None、BLOCK、DURATION_INVALID）。
2. 断行建议：≤2 行、每行 ≤42 字符且文本零丢失。
3. 句法复杂度：从属连词最长匹配、≥2 打标 COMPLEX_SENTENCE、嵌套深度代理。
4. 无损拆句：时间连续、总时长绝对吻合（严禁暗改时间轴）、子句最低时长、
   篡改时间轴立即抛错。
5. 翻译腔：书面语词库 ≥15 组、written_score 合成、>0.75 标黄并给口语候选。
6. 四重语义保护闸门：否定极性、事实实体（数字/人名）、关系称谓、情绪反讽，
   任一违规 BLOCK；合规改写正常通过。
7. 契约校验器边界：阻断候选不得 auto_apply、度量自洽、manifest 零模型声明。

全部为确定性工程自测，不调用任何模型，不代表业务验收（AC-ORAL-* 仍 NOT_RUN）。
"""

import pytest
from pydantic import ValidationError

from code.backend.modules.oral_review import (
    CAPITALIZED_STOPWORDS,
    CPS_HARD_LIMIT,
    CPS_SOFT_LIMIT,
    MAX_DURATION_SEC,
    MAX_LINE_COUNT,
    MAX_LINE_LENGTH,
    MIN_DURATION_SEC,
    ORAL_POLICY_VERSION,
    SPLIT_TIME_TOLERANCE,
    SUBORDINATE_CONJUNCTIONS,
    WRITTEN_SCORE_WARN_THRESHOLD,
    WRITTEN_TERM_LEXICON,
    CharacterContext,
    ComplexityType,
    OralCandidate,
    OralDeviationAnalysis,
    OralReviewRequest,
    OralReviewResult,
    ReadabilityIssueType,
    ReadabilityMetrics,
    ReadabilityStatus,
    SemanticGuardCheck,
    SemanticViolationType,
    SplitSegmentCandidate,
    SplitTimeInvarianceError,
    SubtitleSegment,
    analyze_complexity,
    analyze_oral_deviation,
    analyze_readability,
    build_lossless_split,
    check_semantic_guards,
    compute_nesting_depth,
    count_visible_chars,
    detect_subordinate_conjunctions,
    extract_negations,
    extract_numbers,
    extract_proper_nouns,
    normalize_visible_text,
    review_oral_request,
    review_oral_segment,
    split_lines,
    suggest_line_breaks,
    verify_split_time_invariance,
    worst_status,
)

# --- 标定过的真实样例（数值由实际运行得出，不手算）---
PLAIN = "Te espero afuera, no tardes."                      # 28 可见字符
PLAIN_CHARS = 28
MID = "El gerente dijo que la reunión empieza a las ocho de la mañana."  # 63 字符
MID_CHARS = 63
TARGET_40 = "Dime la verdad ahora mismo, sin excusas."       # 40 字符
TARGET_40_ALT = "No sé si voy a llegar a tiempo, avísame."   # 40 字符
LINE43 = "Necesito que vengas ahora mismo, por favor."       # 43 字符
LINE62 = "Nunca imaginé que llegaríamos a este punto de la conversación."  # 62 字符
THREE_LINES = "Primera línea corta\nSegunda línea corta\nTercera línea"
COMPLEX = "No me digas que no vienes porque tienes miedo, aunque te lo pedí mil veces."
WRITTEN = "No obstante, requerimos efectuar el pago a la brevedad."


def seg(text, start=0.0, end=2.0, segment_id="seg_001", context=None):
    return SubtitleSegment(
        segment_id=segment_id, text=text, start_time=start, end_time=end, context=context
    )


# ==========================================
# 1. 阈值常量与文本口径
# ==========================================

def test_threshold_constants_match_p_oral():
    assert CPS_SOFT_LIMIT == 17.0
    assert CPS_HARD_LIMIT == 20.0
    assert MAX_LINE_LENGTH == 42
    assert MAX_LINE_COUNT == 2
    assert MIN_DURATION_SEC == 0.833
    assert MAX_DURATION_SEC == 7.0
    assert WRITTEN_SCORE_WARN_THRESHOLD == 0.75
    assert SPLIT_TIME_TOLERANCE == 0.001
    assert ORAL_POLICY_VERSION


def test_visible_chars_include_single_space_and_punctuation():
    assert count_visible_chars("Hola, mundo.") == 12
    assert count_visible_chars(PLAIN) == PLAIN_CHARS
    assert count_visible_chars(MID) == MID_CHARS


def test_visible_chars_normalize_newlines_and_repeated_spaces():
    raw = "  Hola,   mundo.\n\n  ¿Qué tal?  "
    assert normalize_visible_text(raw) == "Hola, mundo. ¿Qué tal?"
    assert count_visible_chars(raw) == 22


def test_split_lines_strips_each_line():
    assert split_lines("Hola\n  mundo  \n") == ["Hola", "mundo"]
    assert split_lines("") == [""]


def test_worst_status_ordering():
    assert worst_status(ReadabilityStatus.PASS, ReadabilityStatus.WARN) == ReadabilityStatus.WARN
    assert worst_status(ReadabilityStatus.WARN, ReadabilityStatus.BLOCK) == ReadabilityStatus.BLOCK
    assert worst_status() == ReadabilityStatus.PASS


# ==========================================
# 2. CPS 与时长
# ==========================================

def test_cps_pass_below_soft_limit():
    m = analyze_readability(seg(PLAIN, 0.0, 2.0))
    assert m.visible_char_count == PLAIN_CHARS
    assert m.duration_sec == 2.0
    assert m.cps == 14.0
    assert m.cps_status == ReadabilityStatus.PASS
    assert m.issues == []


def test_cps_exactly_soft_limit_still_pass():
    # 40 / 2.353 = 16.999… → round 17.0，17.0 不 > 17，故 PASS
    m = analyze_readability(seg(TARGET_40, 0.0, 2.353))
    assert m.cps == 17.0
    assert m.cps_status == ReadabilityStatus.PASS
    assert ReadabilityIssueType.CPS_WARN.value not in m.issues


def test_cps_warn_between_soft_and_hard():
    m = analyze_readability(seg(MID, 0.0, 3.405))
    assert m.cps == 18.5
    assert m.cps_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.CPS_WARN.value in m.issues


def test_cps_exactly_hard_limit_is_warn_not_block():
    m = analyze_readability(seg(TARGET_40_ALT, 0.0, 2.0))
    assert m.cps == 20.0
    assert m.cps_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.CPS_BLOCK.value not in m.issues


def test_cps_above_hard_limit_blocks():
    m = analyze_readability(seg(MID, 0.0, 2.864))
    assert m.cps == 22.0
    assert m.cps_status == ReadabilityStatus.BLOCK
    assert ReadabilityIssueType.CPS_BLOCK.value in m.issues


def test_cps_formula_is_chars_divided_by_duration_rounded_two():
    m = analyze_readability(seg(TARGET_40, 0.0, 1.9))
    assert m.cps == round(m.visible_char_count / m.duration_sec, 2) == 21.05


def test_duration_invalid_zero_is_hard_illegal():
    m = analyze_readability(seg(PLAIN, 2.0, 2.0))
    assert m.is_duration_valid is False
    assert m.duration_sec == 0.0
    assert m.cps is None
    assert m.cps_status == ReadabilityStatus.BLOCK
    assert m.duration_status == ReadabilityStatus.BLOCK
    assert m.issues == [ReadabilityIssueType.DURATION_INVALID.value]


def test_duration_invalid_negative_is_hard_illegal():
    m = analyze_readability(seg(PLAIN, 3.0, 2.5))
    assert m.duration_sec == -0.5
    assert m.is_duration_valid is False
    assert m.cps is None
    assert ReadabilityIssueType.DURATION_INVALID.value in m.issues


def test_duration_too_short_warns_without_blocking_cps():
    m = analyze_readability(seg("Sí.", 0.0, 0.5))
    assert m.duration_sec == 0.5
    assert m.duration_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.DURATION_TOO_SHORT.value in m.issues
    assert m.cps == 6.0
    assert m.cps_status == ReadabilityStatus.PASS


def test_duration_too_long_warns():
    m = analyze_readability(seg(PLAIN, 0.0, 7.4))
    assert m.duration_sec == 7.4
    assert m.duration_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.DURATION_TOO_LONG.value in m.issues
    assert m.cps == 3.78


def test_empty_text_has_zero_chars_and_zero_cps():
    m = analyze_readability(seg("", 0.0, 2.0))
    assert m.visible_char_count == 0
    assert m.cps == 0.0
    assert m.line_count == 1
    assert m.max_line_length == 0


# ==========================================
# 3. 行长 / 行数 / 断行建议
# ==========================================

def test_line_within_limits_has_no_suggestion():
    m = analyze_readability(seg("Dime la verdad ahora mismo.", 0.0, 3.0))
    assert m.line_status == ReadabilityStatus.PASS
    assert m.syntax_line_break_suggestion is None


def test_line_length_exceeded_triggers_suggestion():
    m = analyze_readability(seg(LINE43, 0.0, 4.0))
    assert m.max_line_length == len(LINE43) == 43
    assert m.line_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.LINE_LENGTH_EXCEEDED.value in m.issues
    suggestion = m.syntax_line_break_suggestion
    assert suggestion is not None
    parts = suggestion.split("\n")
    assert len(parts) <= MAX_LINE_COUNT
    assert all(len(part) <= MAX_LINE_LENGTH for part in parts)
    assert normalize_visible_text(suggestion) == normalize_visible_text(LINE43)


def test_line_count_exceeded_reflows_into_two_lines():
    m = analyze_readability(seg(THREE_LINES, 0.0, 6.0))
    assert m.line_count == 3
    assert m.line_status == ReadabilityStatus.WARN
    assert ReadabilityIssueType.LINE_COUNT_EXCEEDED.value in m.issues
    suggestion = m.syntax_line_break_suggestion
    assert suggestion is not None
    parts = suggestion.split("\n")
    assert len(parts) <= MAX_LINE_COUNT
    assert all(len(part) <= MAX_LINE_LENGTH for part in parts)
    assert normalize_visible_text(suggestion) == normalize_visible_text(THREE_LINES)


def test_long_single_line_suggestion_splits_at_word_boundary():
    suggestion = suggest_line_breaks(LINE62)
    assert suggestion is not None
    parts = suggestion.split("\n")
    assert len(parts) == 2
    assert all(len(part) <= MAX_LINE_LENGTH for part in parts)
    assert " ".join(parts) == LINE62


def test_short_text_has_no_line_break_suggestion():
    assert suggest_line_breaks("Hola.") is None


# ==========================================
# 4. 句法复杂度与无损拆句
# ==========================================

def test_two_subordinate_conjunctions_tag_complex_sentence():
    analysis = analyze_complexity("Creo que no vienes porque no quieres.")
    assert analysis.subordinate_conjunction_count == 2
    assert analysis.is_complex is True
    assert analysis.issue_tag == ComplexityType.COMPLEX_SENTENCE.value


def test_single_conjunction_is_not_complex():
    analysis = analyze_complexity("Dijo que llegaría tarde.")
    assert analysis.subordinate_conjunction_count == 1
    assert analysis.is_complex is False
    assert analysis.issue_tag is None
    assert analysis.nesting_depth == 2


def test_conjunction_matching_is_longest_first():
    hits = detect_subordinate_conjunctions("Lo hizo porque quiso, a pesar de que llovía.")
    assert hits == ["porque", "a pesar de que"]
    assert "que" not in hits


def test_multiword_conjunctions_are_not_double_counted():
    hits = detect_subordinate_conjunctions("Aunque llueva, ya que insistes, vamos.")
    assert hits == ["Aunque", "ya que"]
    assert len(hits) == 2


def test_nesting_depth_proxy_exceeds_threshold():
    text = "Si vienes cuando quieres y como puedes porque quieres, que avises."
    depth = compute_nesting_depth(text, len(detect_subordinate_conjunctions(text)))
    assert depth > 4


def test_lossless_split_is_time_continuous_and_conserves_duration():
    parts = build_lossless_split(COMPLEX, 1.0, 5.0)
    assert parts is not None and len(parts) == 2
    first, second = parts
    assert first.start_time == 1.0
    assert first.end_time == second.start_time
    assert second.end_time == 5.0
    total = first.duration_sec + second.duration_sec
    assert abs(total - 4.0) < SPLIT_TIME_TOLERANCE
    assert first.text + " " + second.text == COMPLEX
    assert first.part_index == 0 and second.part_index == 1


def test_split_mid_time_follows_character_ratio():
    parts = build_lossless_split(COMPLEX, 0.0, 4.0)
    first, second = parts
    expected = round(0.0 + 4.0 * (len(first.text) / (len(first.text) + len(second.text))), 3)
    assert first.end_time == expected


def test_split_parts_respect_line_length():
    parts = build_lossless_split(COMPLEX, 1.0, 5.0)
    assert all(len(part.text) <= MAX_LINE_LENGTH for part in parts)


def test_split_refused_when_part_would_be_too_short():
    assert build_lossless_split(COMPLEX, 0.0, 1.5) is None


def test_split_without_times_not_offered():
    analysis = analyze_complexity(COMPLEX)
    assert analysis.is_complex is True
    assert analysis.split_suggestion is None


def test_complex_sentence_with_times_offers_split():
    analysis = analyze_complexity(COMPLEX, 1.0, 5.0)
    assert analysis.split_suggestion is not None
    verify_split_time_invariance(1.0, 5.0, analysis.split_suggestion)


def test_verify_detects_tampered_total_duration():
    parts = build_lossless_split(COMPLEX, 1.0, 5.0)
    tampered = [
        parts[0],
        SplitSegmentCandidate(
            part_index=1,
            text=parts[1].text,
            start_time=parts[1].start_time,
            end_time=4.5,          # 暗改：总时长被缩短 0.5s
            duration_sec=4.5 - parts[1].start_time,
            char_count=len(parts[1].text),
        ),
    ]
    with pytest.raises(SplitTimeInvarianceError):
        verify_split_time_invariance(1.0, 5.0, tampered)


def test_verify_detects_discontinuity():
    parts = build_lossless_split(COMPLEX, 1.0, 5.0)
    broken = [
        parts[0],
        SplitSegmentCandidate(
            part_index=1,
            text=parts[1].text,
            start_time=parts[1].start_time + 0.2,   # 中间挖空 0.2s
            end_time=5.2,
            duration_sec=round(5.2 - (parts[1].start_time + 0.2), 3),
            char_count=len(parts[1].text),
        ),
    ]
    with pytest.raises(SplitTimeInvarianceError):
        verify_split_time_invariance(1.0, 5.2, broken)


# ==========================================
# 5. 翻译腔与书面语偏离度
# ==========================================

def test_written_lexicon_has_at_least_fifteen_pairs():
    assert len(WRITTEN_TERM_LEXICON) >= 15
    for term, _pattern, candidates, rationale in WRITTEN_TERM_LEXICON:
        assert term and candidates and rationale


def test_written_sentence_scores_high_and_warns():
    analysis = analyze_oral_deviation(WRITTEN)
    assert analysis.written_score == 1.0
    assert analysis.is_warn is True
    terms = {item["term"] for item in analysis.detected_written_terms}
    assert {"no obstante", "requerir", "efectuar", "a la brevedad"} <= terms
    for item in analysis.detected_written_terms:
        assert item["oral_candidates"] and item["rationale"]


def test_written_rewrite_offers_es_mx_colloquial_forms():
    analysis = analyze_oral_deviation(WRITTEN)
    rewrite = analysis.suggested_rewrite
    assert rewrite.startswith("Pero,")          # no obstante → pero，且保留句首大写
    assert "necesita" in rewrite                # requerir → necesitar
    assert "hacer" in rewrite                   # efectuar → hacer
    assert "cuanto antes" in rewrite            # a la brevedad → cuanto antes
    assert "no obstante" not in rewrite.lower()


def test_plural_verb_picks_plural_oral_candidate():
    analysis = analyze_oral_deviation("Poseen dos autos y asimismo una casa.")
    assert analysis.suggested_rewrite.startswith("Tienen")


def test_colloquial_sentence_has_zero_score_and_no_rewrite():
    analysis = analyze_oral_deviation("Vamos a la playa mañana.")
    assert analysis.written_score == 0.0
    assert analysis.is_warn is False
    assert analysis.detected_written_terms == []
    assert analysis.suggested_rewrite is None


def test_single_written_term_in_long_sentence_stays_below_threshold():
    analysis = analyze_oral_deviation("Cabe destacar que la reunión será en la sala dos, previo aviso.")
    assert analysis.written_score < WRITTEN_SCORE_WARN_THRESHOLD
    assert analysis.is_warn is False
    assert analysis.detected_written_terms          # 仍记录命中，便于人工判断
    assert analysis.suggested_rewrite is not None


def test_deviation_warn_flag_cannot_be_relaxed_by_hand():
    with pytest.raises(ValidationError):
        OralDeviationAnalysis(written_score=0.5, is_warn=True)


# ==========================================
# 6. 四重语义保护硬闸门
# ==========================================

def test_polarity_affirmative_to_negative_blocks():
    guard = check_semantic_guards("No quiero ir contigo.", "Quiero ir contigo.")
    assert guard.polarity_consistent is False
    assert guard.violations == [SemanticViolationType.POLARITY_MISMATCH.value]
    assert guard.is_blocked is True
    assert guard.block_reasons


def test_polarity_double_negation_removal_blocks():
    guard = check_semantic_guards("No puedo no ir.", "Puedo ir.")
    assert SemanticViolationType.POLARITY_MISMATCH.value in guard.violations


def test_polarity_kept_passes():
    guard = check_semantic_guards("No quiero ir contigo.", "No quiero ir con usted.")
    assert guard.is_blocked is False
    assert guard.violations == []


def test_negation_idiom_no_obstante_is_not_polarity_flip():
    # "no obstante" 是转折固定搭配，改写为 pero 不算否定极性改变
    assert extract_negations("No obstante, no quiero nada.") == {"no": 1, "nada": 1}
    guard = check_semantic_guards(WRITTEN, "Pero, necesita hacer el pago cuanto antes.")
    assert SemanticViolationType.POLARITY_MISMATCH.value not in guard.violations


def test_entity_number_generalized_to_vague_blocks():
    guard = check_semantic_guards(
        "Hay 3 personas esperando afuera.", "Hay algunas personas esperando afuera."
    )
    assert guard.entity_consistent is False
    assert SemanticViolationType.ENTITY_MISMATCH.value in guard.violations


def test_entity_person_name_loss_blocks():
    guard = check_semantic_guards("María dijo que llegaría tarde.", "Ella dijo que llegaría tarde.")
    assert SemanticViolationType.ENTITY_MISMATCH.value in guard.violations
    assert extract_proper_nouns("María dijo que llegaría tarde.") == {"maria": 1}


def test_entity_compliant_rewrite_passes():
    guard = check_semantic_guards(
        "Hay 3 personas esperando afuera.", "Hay 3 personas esperando."
    )
    assert guard.entity_consistent is True
    assert guard.is_blocked is False


def test_entity_vague_quantifier_injection_blocks():
    guard = check_semantic_guards("Llegaron 5 amigos.", "Llegaron varios amigos.")
    assert SemanticViolationType.ENTITY_MISMATCH.value in guard.violations


def test_number_extraction_handles_words_and_decimals():
    numbers = extract_numbers("Hay 3 personas y llegaron dos amigos en 1,5 horas.")
    assert numbers["3"] == 1
    assert numbers["dos"] == 1
    assert numbers["1.5"] == 1


def test_relationship_usted_to_tu_blocks():
    guard = check_semantic_guards(
        "Usted sabe que su hijo está aquí.", "Tú sabes que tu hijo está aquí."
    )
    assert guard.relationship_consistent is False
    assert SemanticViolationType.RELATIONSHIP_MISMATCH.value in guard.violations


def test_relationship_honorific_loss_blocks():
    guard = check_semantic_guards(
        "Señor Gómez, firme el documento.", "Gómez, firma el documento."
    )
    assert SemanticViolationType.RELATIONSHIP_MISMATCH.value in guard.violations


def test_relationship_with_formal_context_blocks():
    context = CharacterContext(honorific_register="formal", speaker="jefe", listener="empleado")
    guard = check_semantic_guards(
        "Usted sabe que su hijo está aquí.",
        "Tú sabes que tu hijo está aquí.",
        context,
    )
    assert SemanticViolationType.RELATIONSHIP_MISMATCH.value in guard.violations


def test_relationship_compliant_rewrite_passes():
    context = CharacterContext(honorific_register="formal")
    guard = check_semantic_guards(
        "Usted sabe que su hijo está aquí.",
        "Usted sabe que su hijo está acá.",
        context,
    )
    assert guard.relationship_consistent is True


def test_stance_insult_purification_blocks():
    guard = check_semantic_guards(
        "Eres un idiota, maldito perro.", "Eres una persona difícil."
    )
    assert guard.stance_consistent is False
    assert SemanticViolationType.STANCE_MISMATCH.value in guard.violations


def test_stance_intensifier_reduction_blocks():
    guard = check_semantic_guards(
        "Eres un idiota total, maldito seas.", "Eres un idiota."
    )
    assert SemanticViolationType.STANCE_MISMATCH.value in guard.violations


def test_stance_sarcasm_cue_removal_blocks():
    context = CharacterContext(stance="sarcastic", is_sarcastic=True)
    guard = check_semantic_guards(
        "Claro, seguro que llegas temprano.", "Sí, llegarás temprano.", context
    )
    assert guard.stance_consistent is False
    assert SemanticViolationType.STANCE_MISMATCH.value in guard.violations


def test_stance_polite_context_rejects_added_insult():
    context = CharacterContext(stance="polite")
    guard = check_semantic_guards(
        "Gracias por su ayuda.", "Gracias, idiota.", context
    )
    assert SemanticViolationType.STANCE_MISMATCH.value in guard.violations


def test_stance_identity_passes():
    guard = check_semantic_guards("Eres un idiota.", "Eres un idiota.")
    assert guard.is_blocked is False


def test_guard_identity_passes_for_any_text():
    for text in (WRITTEN, COMPLEX, PLAIN, "María no quiere nada."):
        assert check_semantic_guards(text, text).is_blocked is False


def test_multiple_violations_reported_together():
    guard = check_semantic_guards(
        "María no quiere pagar 3 facturas, idiota.",
        "Ella quiere pagar algunas facturas, amiga.",
    )
    codes = set(guard.violations)
    assert {
        SemanticViolationType.POLARITY_MISMATCH.value,
        SemanticViolationType.ENTITY_MISMATCH.value,
        SemanticViolationType.STANCE_MISMATCH.value,
    } <= codes


# ==========================================
# 7. 契约校验器硬约束
# ==========================================

def _identity_guard() -> SemanticGuardCheck:
    return SemanticGuardCheck(
        polarity_consistent=True,
        entity_consistent=True,
        relationship_consistent=True,
        stance_consistent=True,
        violations=[],
        is_blocked=False,
        block_reasons=[],
    )


def _blocked_guard() -> SemanticGuardCheck:
    return SemanticGuardCheck(
        polarity_consistent=False,
        entity_consistent=True,
        relationship_consistent=True,
        stance_consistent=True,
        violations=[SemanticViolationType.POLARITY_MISMATCH.value],
        is_blocked=True,
        block_reasons=["否定极性被改变"],
    )


def test_candidate_blocked_guard_forbids_auto_apply():
    with pytest.raises(ValidationError):
        OralCandidate(
            candidate_id="c1",
            original_text="No quiero ir.",
            suggested_text="Quiero ir.",
            guard_check=_blocked_guard(),
            is_blocked=True,
            auto_apply_allowed=True,   # 违规：阻断候选不得自动落盘
            explanation="测试",
        )


def test_candidate_blocked_guard_requires_is_blocked_true():
    with pytest.raises(ValidationError):
        OralCandidate(
            candidate_id="c1",
            original_text="No quiero ir.",
            suggested_text="Quiero ir.",
            guard_check=_blocked_guard(),
            is_blocked=False,
            auto_apply_allowed=False,
            explanation="测试",
        )


def test_candidate_cannot_self_declare_blocked_without_violation():
    with pytest.raises(ValidationError):
        OralCandidate(
            candidate_id="c1",
            original_text="Hola.",
            suggested_text="Hola.",
            guard_check=_identity_guard(),
            is_blocked=True,
            auto_apply_allowed=False,
            explanation="测试",
        )


def test_candidate_rejects_lossy_split_text():
    parts = build_lossless_split(COMPLEX, 0.0, 4.0)
    parts[1] = parts[1].model_copy(update={"text": "aunque te lo pedí.", "char_count": 20})
    with pytest.raises(ValidationError):
        OralCandidate(
            candidate_id="c1",
            original_text=COMPLEX,
            split_candidates=parts,
            guard_check=_identity_guard(),
            is_blocked=False,
            auto_apply_allowed=True,
            explanation="测试",
        )


def test_split_candidate_rejects_fake_duration():
    with pytest.raises(ValidationError):
        SplitSegmentCandidate(
            part_index=0,
            text="Hola",
            start_time=0.0,
            end_time=2.0,
            duration_sec=1.0,   # 与 end-start 不符
            char_count=4,
        )


def test_split_candidate_rejects_fake_char_count():
    with pytest.raises(ValidationError):
        SplitSegmentCandidate(
            part_index=0,
            text="Hola",
            start_time=0.0,
            end_time=2.0,
            duration_sec=2.0,
            char_count=99,
        )


def test_readability_metrics_reject_cps_when_duration_invalid():
    metrics = analyze_readability(seg(PLAIN, 2.0, 2.0))
    payload = metrics.model_dump()
    payload["cps"] = 12.0
    with pytest.raises(ValidationError):
        ReadabilityMetrics(**payload)


def test_readability_metrics_reject_missing_duration_invalid_issue():
    metrics = analyze_readability(seg(PLAIN, 2.0, 2.0))
    payload = metrics.model_dump()
    payload["issues"] = []
    with pytest.raises(ValidationError):
        ReadabilityMetrics(**payload)


def test_readability_metrics_reject_line_count_mismatch():
    metrics = analyze_readability(seg(THREE_LINES, 0.0, 6.0))
    payload = metrics.model_dump()
    payload["line_count"] = 1
    with pytest.raises(ValidationError):
        ReadabilityMetrics(**payload)


def test_semantic_guard_requires_reasons_when_blocked():
    with pytest.raises(ValidationError):
        SemanticGuardCheck(
            polarity_consistent=False,
            entity_consistent=True,
            relationship_consistent=True,
            stance_consistent=True,
            violations=[SemanticViolationType.POLARITY_MISMATCH.value],
            is_blocked=True,
            block_reasons=[],   # 只有标志位、无理由
        )


def test_request_rejects_duplicate_segment_ids():
    with pytest.raises(ValidationError):
        OralReviewRequest(
            request_id="req-1",
            segments=[
                seg("Hola.", 0.0, 1.0, segment_id="seg_001"),
                seg("Adiós.", 1.0, 2.0, segment_id="seg_001"),
            ],
        )


def test_result_rejects_wrong_overall_status():
    request = OralReviewRequest(
        request_id="req-1", segments=[seg(PLAIN, 2.0, 2.0)]
    )
    result = review_oral_request(request)
    payload = result.model_dump()
    payload["overall_status"] = ReadabilityStatus.PASS
    with pytest.raises(ValidationError):
        OralReviewResult(**payload)


def test_result_manifest_must_declare_zero_model_usage():
    request = OralReviewRequest(request_id="req-1", segments=[seg(PLAIN, 0.0, 2.0)])
    payload = review_oral_request(request).model_dump()
    payload["manifest"] = dict(payload["manifest"], model_used=True)
    with pytest.raises(ValidationError):
        OralReviewResult(**payload)
    payload["manifest"] = dict(payload["manifest"], model_used=False, token_used=128)
    with pytest.raises(ValidationError):
        OralReviewResult(**payload)


# ==========================================
# 8. 模块主流程
# ==========================================

def test_clean_segment_has_no_candidate():
    item = review_oral_segment(seg("Dime la verdad ahora mismo.", 0.0, 3.0))
    assert item.status == ReadabilityStatus.PASS
    assert item.candidate is None
    assert item.complexity.is_complex is False


def test_written_segment_yields_passing_candidate():
    item = review_oral_segment(seg(WRITTEN, 1.5, 5.0))
    assert item.deviation.is_warn is True
    candidate = item.candidate
    assert candidate is not None
    assert candidate.is_blocked is False
    assert candidate.auto_apply_allowed is True
    assert candidate.guard_check.is_blocked is False
    assert candidate.suggested_text.startswith("Pero,")
    assert candidate.candidate_id == "seg_001-cand-001"
    assert item.status in (ReadabilityStatus.WARN, ReadabilityStatus.PASS)


def test_complex_segment_yields_time_conserving_split():
    item = review_oral_segment(seg(COMPLEX, 1.0, 5.0))
    assert item.complexity.is_complex is True
    candidate = item.candidate
    assert candidate is not None and candidate.split_candidates
    verify_split_time_invariance(1.0, 5.0, candidate.split_candidates)
    assert item.status == ReadabilityStatus.WARN


def test_poisoned_rewrite_is_blocked_and_marks_segment_block(monkeypatch):
    """闸门接线验证：故意注入极性反转的改写，候选必须被废弃且整句转人工。"""
    from code.backend.modules.oral_review import handler as handler_module

    def poisoned(text: str) -> OralDeviationAnalysis:
        return OralDeviationAnalysis(
            written_score=0.9,
            is_warn=True,
            detected_written_terms=[
                {"term": "x", "matched": ["x"], "oral_candidates": ["y"], "rationale": "测试"}
            ],
            suggested_rewrite="Quiero ir.",
        )

    monkeypatch.setattr(handler_module, "analyze_oral_deviation", poisoned)
    item = review_oral_segment(seg("No quiero ir.", 0.0, 2.0))
    candidate = item.candidate
    assert candidate is not None
    assert candidate.is_blocked is True
    assert candidate.auto_apply_allowed is False
    assert candidate.guard_check.is_blocked is True
    assert SemanticViolationType.POLARITY_MISMATCH.value in candidate.guard_check.violations
    assert "语义闸门阻断" in candidate.explanation
    assert item.status == ReadabilityStatus.BLOCK


def test_request_manifest_is_zero_model_and_traceable():
    request = OralReviewRequest(
        request_id="req-manifest",
        segments=[
            seg(PLAIN, 0.0, 2.0, segment_id="seg_001"),
            seg(WRITTEN, 2.0, 4.5, segment_id="seg_002"),
            seg(COMPLEX, 4.5, 8.5, segment_id="seg_003"),
        ],
    )
    result = review_oral_request(request)
    manifest = result.manifest
    assert manifest["model_used"] is False
    assert manifest["model_invocation"] == "NOT_INVOKED"
    assert manifest["token_used"] == 0
    assert manifest["pipeline"] == "deterministic_rules_only"
    assert manifest["semantic_guard"] == "ENFORCED"
    assert manifest["split_time_invariance"] == "ENFORCED"
    assert manifest["profile_status"] == "PILOT_THRESHOLDS_UNCALIBRATED"
    assert manifest["segment_count"] == 3
    assert manifest["thresholds"]["cps_hard_limit"] == CPS_HARD_LIMIT
    assert len(result.items) == 3


def test_request_overall_status_is_worst_case():
    request = OralReviewRequest(
        request_id="req-worst",
        segments=[
            seg("Dime la verdad ahora mismo.", 0.0, 3.0, segment_id="seg_001"),
            seg(PLAIN, 5.0, 5.0, segment_id="seg_002"),   # 硬非法时长 → BLOCK
        ],
    )
    result = review_oral_request(request)
    assert result.items[0].status == ReadabilityStatus.PASS
    assert result.items[1].status == ReadabilityStatus.BLOCK
    assert result.overall_status == ReadabilityStatus.BLOCK
    assert result.manifest["issue_counts"]["DURATION_INVALID"] == 1


def test_repeated_run_is_deterministic():
    request = OralReviewRequest(request_id="req-idem", segments=[seg(WRITTEN, 1.0, 3.5)])
    first = review_oral_request(request)
    second = review_oral_request(request)
    assert first.items[0].model_dump(exclude={"readability"}) == second.items[0].model_dump(
        exclude={"readability"}
    )
    assert first.items[0].readability.model_dump() == second.items[0].readability.model_dump()
    assert first.items[0].candidate.candidate_id == second.items[0].candidate.candidate_id


def test_subordinate_conjunction_lexicon_contains_core_spanish_markers():
    assert {"que", "porque", "aunque", "como", "cuando", "si", "donde"} <= set(
        SUBORDINATE_CONJUNCTIONS
    )
    assert "a pesar de que" in SUBORDINATE_CONJUNCTIONS
    assert "ya que" in SUBORDINATE_CONJUNCTIONS


def test_capitalized_stopwords_cover_core_spanish_words():
    """句首常用词表覆盖率下限（防止后续误删导致人名误判）。"""
    assert len(CAPITALIZED_STOPWORDS) >= 120
    for word in ("pero", "que", "ella", "tiene", "despues", "usted", "vamos"):
        assert word in CAPITALIZED_STOPWORDS


def test_own_rewrite_surface_forms_are_not_treated_as_entities():
    """自家改写产生的句首词不得被误判为专有名词，否则会自我阻断。"""
    for text in (
        "Pero, necesita hacer el pago.",
        "Después pide permiso.",
        "Tiene dos autos.",
        "Ojo que la reunión es hoy.",
        "Sobre la deuda, nada.",
        "Entonces avísame.",
    ):
        assert extract_proper_nouns(text) == {}

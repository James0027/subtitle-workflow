"""unit_format 模块单元测试。

覆盖范围（对应工单 03 的 7 项要求 + 契约硬锁）：

1. 无实体台词跳步（SKIPPED，零 Token、零延迟）
2. 日常距离/速度确定性换算（英制 -> 公制，取整，反向验算通过）
3. 反向验算断言机制（篡改因子/异常即抛 ValueError）
4. 舍入控制对比（日常取整 vs 体温/敏感数据保留 1 位小数）
5. 剧情例外：发烧体温 -> MANUAL_DECISION_REQUIRED 且原值保留
6. 剧情例外：密码/PIN/比赛纪录/日期不被篡改
7. 货币汇率防篡改（禁止汇率折算，原币种原金额保留）

测试仅验证确定性工程路径，不调用任何模型，不代表真实业务验收。
"""

import pytest
from pydantic import ValidationError

from code.backend.modules.unit_format import (
    CANDIDATE_STATUSES,
    CONVERSION_TABLE,
    CandidateStatus,
    UnitCandidate,
    UnitConversionError,
    UnitFormatRequest,
    UnitFormatUnitInput,
    convert_fahrenheit_to_celsius,
    convert_with_verification,
    extract_and_convert_units,
    extract_entities,
    round_value,
    scan_and_convert_text,
    verify_temperature_reverse,
)


def make_request(*units: UnitFormatUnitInput, task_ref: str = "task-ticket03") -> UnitFormatRequest:
    return UnitFormatRequest(task_ref=task_ref, task_revision=1, units=list(units))


def process_text(text: str, unit_id: str = "u_001", **kwargs):
    """便捷封装：单条文本 -> (result, candidates)。"""
    unit = UnitFormatUnitInput(unit_id=unit_id, target_text=text, **kwargs)
    result = extract_and_convert_units(make_request(unit))
    return result, result.candidates


# ==========================================
# 1. 无实体台词跳步
# ==========================================

def test_skip_when_no_entity_returns_skipped_and_zero_cost():
    result, candidates = process_text("Te quiero mucho, mi amor. No pasa nada.")

    assert result.status == "SKIPPED"
    assert result.entities == []
    assert candidates == []
    assert len(result.unit_outcomes) == 1

    outcome = result.unit_outcomes[0]
    assert outcome.status == "SKIPPED"
    assert outcome.reason == "NO_UNIT_ENTITY_IN_TEXT"
    assert outcome.entity_count == 0
    assert outcome.candidate_count == 0
    assert outcome.token_used == 0
    assert outcome.latency_ms == 0

    # 跳步事实必须写进 manifest，且不得伪造模型调用
    assert result.manifest["model_used"] is False
    assert result.manifest["token_used"] == 0
    assert result.manifest["skipped_unit_ids"] == ["u_001"]
    assert result.manifest["pipeline"] == "two_stage_deterministic_first"


def test_skip_scan_is_pure_regex_and_entity_free_text_stays_empty():
    assert extract_entities("u_001", "Vamos a casa, ¿vienes?") == []


def test_mixed_request_keeps_skip_unit_and_processes_other_unit():
    request = make_request(
        UnitFormatUnitInput(unit_id="u_001", target_text="Está a 10 miles."),
        UnitFormatUnitInput(unit_id="u_002", target_text="Nos vemos mañana."),
    )
    result = extract_and_convert_units(request)

    assert result.status == "PROCESSED"
    assert [o.unit_id for o in result.unit_outcomes] == ["u_001", "u_002"]
    assert result.unit_outcomes[0].status == "PROCESSED"
    assert result.unit_outcomes[1].status == "SKIPPED"
    assert result.manifest["skipped_unit_ids"] == ["u_002"]
    assert len(result.candidates) == 1
    assert result.candidates[0].unit_id == "u_001"


# ==========================================
# 2. 日常距离/速度换算
# ==========================================

def test_distance_miles_to_km_rounds_to_integer_and_verifies():
    result, candidates = process_text("Está a 26.2 miles de aquí.")

    assert result.status == "PROCESSED"
    assert len(candidates) == 1
    candidate = candidates[0]

    assert candidate.entity_type == "distance"
    assert candidate.status == CandidateStatus.AI_PROPOSED
    assert candidate.raw_value == "26.2"
    assert candidate.raw_text == "26.2 miles"
    assert candidate.target_unit == "km"
    assert candidate.target_value == 42.0           # 26.2 × 1.609344 = 42.16 -> 42
    assert candidate.rounding_policy == "integer"
    assert isinstance(candidate.target_value, float)
    assert candidate.conversion_factor == pytest.approx(1.609344)

    verification = candidate.reverse_verification
    assert verification.performed is True
    assert verification.passed is True
    assert verification.residual < 0.01
    assert candidate.auto_apply_allowed is True

    # 原值零丢失：界面并排展示原值
    assert "26.2 miles" in candidate.display_text
    assert candidate.evidence["raw_text"] == "26.2 miles"


def test_speed_mph_to_kmh_rounds_to_integer_and_verifies():
    result, candidates = process_text("Conduce a 60 mph por la carretera.")

    candidate = candidates[0]
    assert candidate.entity_type == "speed"
    assert candidate.raw_unit == "mph"
    assert candidate.target_unit == "km/h"
    assert candidate.target_value == 97.0           # 60 × 1.609344 = 96.56 -> 97
    assert candidate.rounding_policy == "integer"
    assert candidate.reverse_verification.passed is True

    # 直接在未舍入值上验算题目要求的反向公式
    spec = CONVERSION_TABLE[("mph", "km/h")]
    exact, _ = convert_with_verification(60.0, spec)
    assert abs(exact * (spec.factor ** -1) - 60.0) < 0.01


def test_feet_and_yards_convert_to_metric():
    _, candidates = process_text("Mide 6 feet y 2 yards de largo.")

    assert [c.entity_type for c in candidates] == ["distance", "distance"]
    assert candidates[0].target_unit == "m"
    assert candidates[0].target_value == pytest.approx(2.0, abs=0.5)   # 6 ft = 1.8288 m -> 2
    assert candidates[1].target_unit == "m"
    assert candidates[1].target_value == pytest.approx(2.0, abs=0.5)   # 2 yd = 1.8288 m -> 2
    assert all(c.reverse_verification.passed for c in candidates)


def test_metric_passthrough_is_not_reconverted():
    _, candidates = process_text("Faltan 5 km para llegar.")

    candidate = candidates[0]
    assert candidate.target_unit == "km"
    assert candidate.target_value == 5.0
    assert candidate.conversion_factor == 1.0
    assert candidate.reverse_verification.passed is True
    assert "5 km" in candidate.display_text


# ==========================================
# 3. 反向验算断言机制
# ==========================================

def test_tampered_factor_raises_before_any_candidate_is_emitted(monkeypatch):
    """因子被改坏时必须抛错，而不是"自洽地"算出一个错误数值。"""
    spec = CONVERSION_TABLE[("mile", "km")]
    original = spec.factor
    monkeypatch.setattr(spec, "factor", 1.5)

    with pytest.raises(UnitConversionError) as excinfo:
        scan_and_convert_text("u_001", "Está a 26.2 miles de aquí.")
    assert "交叉验算超差" in str(excinfo.value)

    # ValueError 子类，调用方可用 ValueError 统一阻断
    assert issubclass(UnitConversionError, ValueError)
    monkeypatch.setattr(spec, "factor", original)


def test_convert_with_verification_rejects_impossible_factor():
    from code.backend.modules.unit_format.handler import ConversionSpec

    bad_spec = ConversionSpec(
        from_unit="mile",
        to_unit="km",
        factor=1.5,                 # 被篡改的因子
        reference_factor=1.609344,  # SI 基准推导出的独立参考
        formula="tampered",
        category="distance",
    )
    with pytest.raises(ValueError):
        convert_with_verification(10.0, bad_spec)


def test_zero_factor_is_rejected():
    from code.backend.modules.unit_format.handler import ConversionSpec

    zero_spec = ConversionSpec("mile", "km", 0.0, 1.609344, "zero", "distance")
    with pytest.raises(UnitConversionError):
        convert_with_verification(10.0, zero_spec)


def test_temperature_reverse_verification_raises_on_wrong_celsius():
    # 101.3 °F 正确值是 38.5 °C；故意传入 30 °C 必须被拒绝
    assert abs(convert_fahrenheit_to_celsius(101.3)[0] - 38.5) < 0.01
    with pytest.raises(UnitConversionError) as excinfo:
        verify_temperature_reverse(101.3, 30.0)
    assert "温度反向验算超差" in str(excinfo.value)


def test_temperature_reverse_verification_accepts_correct_value():
    celsius, verification = convert_fahrenheit_to_celsius(212.0)
    assert celsius == pytest.approx(100.0)
    assert verification.passed is True
    assert verification.residual < 0.05


# ==========================================
# 4. 舍入控制对比
# ==========================================

def test_daily_weather_temperature_rounds_to_integer():
    _, candidates = process_text("Hace 70 degrees Fahrenheit afuera.")

    candidate = candidates[0]
    assert candidate.entity_type == "temperature"
    assert candidate.rounding_policy == "integer"
    assert candidate.target_value == 21.0          # (70-32)*5/9 = 21.11 -> 21
    assert candidate.target_unit == "°C"
    assert candidate.status == CandidateStatus.AI_PROPOSED


def test_fever_temperature_keeps_one_decimal():
    _, candidates = process_text("Tengo fiebre, 101.3 degrees Fahrenheit.")

    candidate = candidates[0]
    assert candidate.rounding_policy == "one_decimal"
    assert candidate.target_value == 38.5          # (101.3-32)*5/9 = 38.5
    assert candidate.target_value != 39.0          # 不得被日常取整策略吞掉精度


def test_body_temperature_context_keeps_one_decimal_even_below_fever():
    _, candidates = process_text("Su temperatura corporal es 98.6 F.")

    candidate = candidates[0]
    assert candidate.rounding_policy == "one_decimal"
    assert candidate.target_value == 37.0          # 37.0 而不是 37（精度可见）
    assert "37.0" in candidate.display_text
    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED


def test_round_value_respects_half_up_and_policies():
    assert round_value(2.5, "integer") == 3
    assert round_value(2.45, "one_decimal") == 2.5
    assert round_value(2.4567, "none") == 2.4567
    with pytest.raises(ValueError):
        round_value(1.0, "unknown_policy")


def test_rounding_guard_rejects_deviation_beyond_quantum():
    from code.backend.modules.unit_format import assert_rounding_within_quantum

    assert_rounding_within_quantum(42.0, 42.1648128, "integer")     # 合法：偏差 0.16 < 0.5
    with pytest.raises(UnitConversionError):
        assert_rounding_within_quantum(50.0, 42.1648128, "integer")  # 舍入掩盖了换算错误
    with pytest.raises(UnitConversionError):
        assert_rounding_within_quantum(38.9, 38.5, "one_decimal")    # 偏差 0.4 > 0.05


# ==========================================
# 5. 剧情例外：发烧体温
# ==========================================

def test_fever_temperature_is_locked_for_manual_decision():
    result, candidates = process_text("Tengo fiebre, 101.3 degrees Fahrenheit.")

    assert len(candidates) == 1
    candidate = candidates[0]

    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED
    assert candidate.plot_exception is True
    assert candidate.exception_reason == "PLOT_FEVER_TEMPERATURE"
    assert candidate.auto_apply_allowed is False
    assert candidate.suggested_text is None          # 不得给出可直接落盘的替换

    # 原值永久保留，建议值仅并排参考
    assert candidate.raw_value == "101.3"
    assert candidate.raw_unit == "degrees Fahrenheit"
    assert candidate.evidence["raw_text"] == "101.3 degrees Fahrenheit"
    assert candidate.target_value == 38.5
    assert "101.3 degrees Fahrenheit" in candidate.display_text

    # 体温仍要求执行反算（数值本身必须可信）
    assert candidate.reverse_verification.performed is True
    assert candidate.reverse_verification.passed is True

    assert result.manifest["manual_decision_required_count"] == 1
    assert result.manifest["auto_apply_allowed_count"] == 0


def test_high_temperature_without_fever_context_is_not_plot_locked():
    _, candidates = process_text("En el desierto hace 105 F al mediodía.")

    candidate = candidates[0]
    assert candidate.status == CandidateStatus.AI_PROPOSED
    assert candidate.exception_reason is None


# ==========================================
# 6. 剧情例外：密码/PIN、比赛纪录、日期
# ==========================================

def test_pin_is_locked_and_original_digits_preserved():
    _, candidates = process_text("El código PIN es 4821.")

    candidate = candidates[0]
    assert candidate.entity_type == "numeric_code"
    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED
    assert candidate.exception_reason == "PLOT_NUMERIC_CODE"
    assert candidate.raw_value == "4821"
    assert candidate.target_value is None            # 禁止任何机器替换值
    assert candidate.suggested_text is None
    assert candidate.auto_apply_allowed is False
    assert "4821" in candidate.display_text
    assert candidate.evidence["machine_replacement"] == "FORBIDDEN"


def test_4_digit_code_phrase_does_not_confuse_hint_number():
    _, candidates = process_text("Introduce el código de 4 dígitos: 7391")

    codes = [c for c in candidates if c.entity_type == "numeric_code"]
    assert codes, "应识别出密码实体"
    assert codes[0].raw_value == "7391"
    assert codes[0].status == CandidateStatus.MANUAL_DECISION_REQUIRED


def test_race_record_is_locked_and_not_reformatted():
    _, candidates = process_text("Su récord de vuelta es 58.3 segundos.")

    candidate = candidates[0]
    assert candidate.entity_type == "record"
    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED
    assert candidate.exception_reason == "PLOT_RECORD_VALUE"
    assert candidate.raw_text == "58.3"
    assert candidate.raw_value == "58.3"
    assert candidate.target_value is None
    assert candidate.auto_apply_allowed is False


def test_date_is_locked_pending_human_confirmation():
    _, candidates = process_text("La fecha límite es October 21, 2026.")

    candidate = candidates[0]
    assert candidate.entity_type == "date"
    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED
    assert candidate.exception_reason == "DATE_REQUIRES_CONFIRMATION"
    assert candidate.target_value is None
    assert "October 21, 2026" in candidate.display_text


# ==========================================
# 7. 货币汇率防篡改
# ==========================================

def test_plot_money_never_applies_exchange_rate():
    _, candidates = process_text("Cuesta 100 dollars en total.")

    candidate = candidates[0]
    assert candidate.entity_type == "money"
    assert candidate.status == CandidateStatus.MANUAL_DECISION_REQUIRED
    assert candidate.exception_reason == "PLOT_CURRENCY_NO_FX"

    # 金额与币种原样保留，禁止折算
    assert candidate.target_value == 100.0
    assert candidate.conversion_factor is None
    assert candidate.raw_currency_code == "USD"
    assert candidate.target_currency_code == "USD"
    assert "MXN" not in candidate.display_text
    assert "pesos" not in candidate.display_text.lower()
    assert candidate.target_value != pytest.approx(100.0 * 18.5)  # 反例：汇率折算值
    assert candidate.evidence["fx_conversion"] == "FORBIDDEN"
    assert candidate.evidence["exchange_rate"] is None
    assert candidate.auto_apply_allowed is False


def test_money_amount_and_thousands_separator_preserved():
    _, candidates = process_text("Eran 1,000.50 dólares.")

    candidate = candidates[0]
    assert candidate.raw_value == "1,000.50"
    assert candidate.target_value == 1000.5
    assert candidate.target_unit == "USD"
    assert candidate.conversion_factor is None
    assert "1,000.50" in candidate.display_text
    assert "1,000.50" in candidate.evidence["raw_text"]


def test_ambiguous_dollar_symbol_is_never_guessed_as_pesos():
    _, candidates = process_text("Solo tengo $100 encima.")

    candidate = candidates[0]
    assert candidate.entity_type == "money"
    assert candidate.raw_currency_code is None      # "$" 在 MX 同时可指 USD/MXN，不猜
    assert candidate.target_currency_code is None
    assert candidate.target_value == 100.0
    assert candidate.conversion_factor is None
    assert "AMBIGUOUS_CURRENCY_SYMBOL" in candidate.evidence["context_flags"]


def test_contract_blocks_fx_conversion_attempt():
    """契约层二次拦截：即使下游伪造汇率候选，pydantic 也必须拒绝。"""
    _, candidates = process_text("Cuesta 100 dollars en total.")
    payload = candidates[0].model_dump()
    payload["target_currency_code"] = "MXN"
    payload["conversion_factor"] = 18.5
    payload["target_value"] = 1850.0

    with pytest.raises(ValidationError):
        UnitCandidate(**payload)


def test_contract_blocks_plot_locked_candidate_with_machine_value():
    _, candidates = process_text("El código PIN es 4821.")
    payload = candidates[0].model_dump()
    payload["target_value"] = 9999.0
    payload["suggested_text"] = "9999"

    with pytest.raises(ValidationError):
        UnitCandidate(**payload)


# ==========================================
# 契约与导出
# ==========================================

def test_candidate_status_enum_exposes_six_states():
    assert set(CANDIDATE_STATUSES) == {
        "AI_PROPOSED",
        "HUMAN_APPROVED",
        "MANUAL_EDITED",
        "ORIGINAL_RETAINED",
        "SKIPPED",
        "MANUAL_DECISION_REQUIRED",
    }


def test_candidate_rejects_missing_raw_value():
    _, candidates = process_text("Está a 26.2 miles de aquí.")
    payload = candidates[0].model_dump()
    payload["raw_value"] = ""

    with pytest.raises(ValidationError):
        UnitCandidate(**payload)


def test_candidate_display_must_keep_raw_value():
    _, candidates = process_text("Está a 26.2 miles de aquí.")
    payload = candidates[0].model_dump()
    payload["display_text"] = "42 km"      # 丢掉原值即违反零丢失原则

    with pytest.raises(ValidationError):
        UnitCandidate(**payload)


def test_result_is_json_serializable_with_original_values():
    result, _ = process_text("Corre 5 millas a 60 mph y dice 100 dollars.")
    dumped = result.model_dump(mode="json")

    assert dumped["status"] == "PROCESSED"
    raw_texts = [item["raw_text"] for item in dumped["entities"]]
    assert "5 millas" in raw_texts
    assert "60 mph" in raw_texts
    assert "100 dollars" in raw_texts
    assert all(item["status"] for item in dumped["candidates"])


def test_entities_are_ordered_by_text_position():
    result, _ = process_text("Corre 5 millas a 60 mph.")

    entities = result.entities
    assert [e.entity_type for e in entities] == ["distance", "speed"]
    assert entities[0].start_char < entities[1].start_char
    assert entities[0].entity_id.endswith("-e001")
    assert entities[1].entity_id.endswith("-e002")


# ==========================================
# 扫描器覆盖（实体类型与单位变体）
# ==========================================

@pytest.mark.parametrize(
    "text, entity_type, expected_unit, expected_target",
    [
        ("Hace 70°F afuera.", "temperature", "°C", 21.0),
        ("Hace 21 °C afuera.", "temperature", "°C", 21.0),
        ("Son 2 miles de camino.", "distance", "km", 3.0),
        ("Son 2 millas de camino.", "distance", "km", 3.0),
        ("Camina 500 meters.", "distance", "meter", 500.0),
        ("Maneja a 100 km/h.", "speed", "km/h", 100.0),
        ("Maneja a 100 kilómetros por hora.", "speed", "km/h", 100.0),
    ],
)
def test_scanner_recognizes_unit_variants(text, entity_type, expected_unit, expected_target):
    result, candidates = process_text(text)

    assert result.status == "PROCESSED"
    assert candidates[0].entity_type == entity_type
    assert candidates[0].target_unit == expected_unit
    assert candidates[0].target_value == expected_target


def test_scanner_recognizes_currency_symbols_without_converting():
    for text, expected_code in (
        ("Cuesta €50 el libro.", "EUR"),
        ("Cuesta £50 el libro.", "GBP"),
        ("Cuesta ¥5000 el libro.", "JPY"),
        ("Cuesta 50 USD el libro.", "USD"),
    ):
        _, candidates = process_text(text)
        candidate = candidates[0]
        expected_amount = 5000.0 if expected_code == "JPY" else 50.0
        assert candidate.entity_type == "money"
        assert candidate.target_value == expected_amount
        assert candidate.conversion_factor is None
        assert candidate.target_currency_code == candidate.raw_currency_code


def test_scanner_does_not_treat_plain_text_number_as_entity():
    result, candidates = process_text("Te llamo en 5 minutos, ¿va?")

    assert result.status == "SKIPPED"
    assert candidates == []


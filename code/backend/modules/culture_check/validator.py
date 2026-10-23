import uuid
from typing import Any, Dict, List, Optional, Set
from code.backend.modules.culture_check.contract import (
    CultureCheckIssue,
    CultureCheckRequest,
    CultureRuleItem,
    FactorReasons,
    TriggerSpan,
    UncheckedUnit,
)


class CultureValidationError(ValueError):
    """文化检测跨度、引用、覆盖、因子类型或结构校验异常"""
    pass


def compute_ranking_score(
    impact_level: Optional[int],
    occurrence_likelihood: Optional[int],
    remediation_difficulty: Optional[int],
) -> Optional[int]:
    """
    计算系统排序值 = impact * occurrence * remediation
    严格类型要求：
    - 绝不允许 bool、float、str (Python 中 bool 是 int 的子类，必须显式 isinstance(x, bool) 拦截)
    - 各因子必须为严格 int 且属于 {1, 2, 3}
    - 若缺任一因子则返回 None，绝不填补默认值
    """
    if impact_level is None or occurrence_likelihood is None or remediation_difficulty is None:
        return None

    for val, name in [
        (impact_level, "impact_level"),
        (occurrence_likelihood, "occurrence_likelihood"),
        (remediation_difficulty, "remediation_difficulty"),
    ]:
        if isinstance(val, bool) or not isinstance(val, int):
            raise CultureValidationError(f"排序因子 {name} 必须为严格 int 类型，收到: {type(val).__name__} ({val})")
        if val not in (1, 2, 3):
            raise CultureValidationError(f"排序因子 {name} 值必须在 1..3 之间，当前为: {val}")

    return impact_level * occurrence_likelihood * remediation_difficulty


def build_evidence_allowlist(
    active_rules: List[CultureRuleItem],
    request: CultureCheckRequest,
) -> Set[str]:
    """
    基于当前有效规则、来源及输入媒体，构建确凿证据允许列表 (evidence allowlist)。
    严禁任何模型输出虚构的外部法条、网页或无来源编号。
    """
    allowlist: Set[str] = {"unit:" + u.unit_id for u in request.units}
    for r in active_rules:
        allowlist.add(r.rule_id)
        allowlist.add(r.source_ref)
    if request.media_evidence.has_audio:
        allowlist.add("MEDIA-AUDIO")
    if request.media_evidence.has_video_frames:
        allowlist.add("MEDIA-VIDEO")

    return allowlist


def validate_and_process_culture_issues(
    request: CultureCheckRequest,
    raw_issues: List[Dict[str, Any]],
    checked_unit_ids: List[str],
    unchecked_units: List[UncheckedUnit],
    active_rules: List[CultureRuleItem],
    active_case_ids: Set[str],
) -> List[CultureCheckIssue]:
    """
    执行工程级严格校验与护栏处理：
    1. 覆盖性与互斥去重校验：checked 与 unchecked 必须互斥、去重且完全覆盖请求所有 unit_id。
    2. 单元归属与跨度精确校验：trigger_spans 必须真实存在；若提供字符 start/end 必须实际匹配对应文本。
    3. 引用真实性校验：rule_refs 必须在已激活规则中；case_refs 必须在 active_case_ids 中（空时拒任意case_refs）。
    4. 证据依据校验：evidence_refs 必须来自输入 allowlist，禁止假造证据。
    5. 严格因子类型校验：拒绝 bool/float/str，必须为严格整数 1..3。
    6. 证据充分性与 P0 降级护栏：无充分有效证据的 P0 强制降级为待补证 P1，保留重大说明。
    """
    req_unit_ids = [u.unit_id for u in request.units]
    req_unit_set = set(req_unit_ids)
    unit_map = {u.unit_id: u for u in request.units}
    valid_rule_ids = {r.rule_id for r in active_rules}
    evidence_allowlist = build_evidence_allowlist(active_rules, request)

    # 1. checked_unit_ids / unchecked_units 互斥与去重全量覆盖校验
    checked_set = set(checked_unit_ids)
    if len(checked_set) != len(checked_unit_ids):
        raise CultureValidationError("checked_unit_ids 列表中存在重复单元 ID")

    unchecked_ids = [u.unit_id for u in unchecked_units]
    unchecked_set = set(unchecked_ids)
    if len(unchecked_set) != len(unchecked_ids):
        raise CultureValidationError("unchecked_units 列表中存在重复单元 ID")

    # 互斥检查
    overlap = checked_set & unchecked_set
    if overlap:
        raise CultureValidationError(f"checked_unit_ids 与 unchecked_units 存在重叠单元 ID (必须互斥): {overlap}")

    # 合法性检查：是否均属于请求的单元
    unknown_checked = checked_set - req_unit_set
    if unknown_checked:
        raise CultureValidationError(f"checked_unit_ids 包含了请求中未定义的单元 ID: {unknown_checked}")

    unknown_unchecked = unchecked_set - req_unit_set
    if unknown_unchecked:
        raise CultureValidationError(f"unchecked_units 包含了请求中未定义的单元 ID: {unknown_unchecked}")

    # 覆盖性检查：并集必须精确等于请求单元集
    combined = checked_set | unchecked_set
    if combined != req_unit_set:
        missing = req_unit_set - combined
        raise CultureValidationError(f"待检单元覆盖不全，以下单元既未检也未在未检列表中说明: {missing}")

    processed_issues: List[CultureCheckIssue] = []

    for idx, raw in enumerate(raw_issues):
        unit_id = raw.get("unit_id")
        if not unit_id or unit_id not in unit_map:
            raise CultureValidationError(f"Issue[{idx}] 的 unit_id '{unit_id}' 不在请求待检单元列表中")
        if unit_id not in checked_set:
            raise CultureValidationError(f"Issue[{idx}] 的 unit_id '{unit_id}' 未包含在已检单元 checked_unit_ids 中")

        unit = unit_map[unit_id]
        if raw.get("speaker_ref") is not None and raw["speaker_ref"] != unit.speaker_id:
            raise CultureValidationError("Speaker reference does not match the checked unit")

        # 2. 跨度精确校验
        raw_spans = raw.get("trigger_spans", [])
        if not raw_spans:
            raise CultureValidationError(f"Issue[{idx}] 缺少触发片段 trigger_spans")

        validated_spans: List[TriggerSpan] = []
        for s_idx, span in enumerate(raw_spans):
            src_span = span.get("source_span")
            tgt_span = span.get("target_span")

            if not src_span and not tgt_span:
                raise CultureValidationError(f"Issue[{idx}] span[{s_idx}] source_span 与 target_span 不能同时为空")

            if src_span is not None and src_span not in unit.source_text:
                raise CultureValidationError(
                    f"Issue[{idx}] 源语片段 '{src_span}' 不存在于单元 {unit_id} 的源语台词 '{unit.source_text}' 中"
                )
            if tgt_span is not None and tgt_span not in unit.target_text:
                raise CultureValidationError(
                    f"Issue[{idx}] 译文片段 '{tgt_span}' 不存在于单元 {unit_id} 的目标译文 '{unit.target_text}' 中"
                )

            # start_char / end_char 严格校验
            start_c = span.get("start_char")
            end_c = span.get("end_char")

            if tgt_span is not None:
                if start_c is not None or end_c is not None:
                    # 两者必须同时提供且为严格 int
                    if start_c is None or end_c is None:
                        raise CultureValidationError(f"Issue[{idx}] span[{s_idx}] start_char 与 end_char 必须同时提供")
                    if isinstance(start_c, bool) or not isinstance(start_c, int) or isinstance(end_c, bool) or not isinstance(end_c, int):
                        raise CultureValidationError(f"Issue[{idx}] span[{s_idx}] start_char 与 end_char 必须为严格整数类型")
                    if not (0 <= start_c < end_c <= len(unit.target_text)):
                        raise CultureValidationError(
                            f"Issue[{idx}] span[{s_idx}] 字符切片范围 [start_char={start_c}, end_char={end_c}] 超出译文长度 {len(unit.target_text)}"
                        )
                    actual_slice = unit.target_text[start_c:end_c]
                    if actual_slice != tgt_span:
                        raise CultureValidationError(
                            f"Issue[{idx}] span[{s_idx}] start_char/end_char 切片 '{actual_slice}' 与 target_span '{tgt_span}' 不匹配"
                        )
                else:
                    # 补齐字符位置
                    start_c = unit.target_text.find(tgt_span)
                    end_c = start_c + len(tgt_span)

            validated_spans.append(TriggerSpan(
                source_span=src_span,
                target_span=tgt_span,
                start_char=start_c,
                end_char=end_c,
            ))

        # 3. 引用真实性校验 (规则)
        r_refs = raw.get("rule_refs", [])
        for r_ref in r_refs:
            if r_ref not in valid_rule_ids:
                raise CultureValidationError(
                    f"Issue[{idx}] 虚构或引用了未被核准的规则 ID '{r_ref}'；允许的规则包括: {list(valid_rule_ids)}"
                )

        # 4. 引用真实性校验 (案例: active_case_ids 为空时仍须拒绝任意 case_refs)
        c_refs = raw.get("case_refs", [])
        for c_ref in c_refs:
            if not active_case_ids or c_ref not in active_case_ids:
                raise CultureValidationError(
                    f"Issue[{idx}] 引用了不存在或未激活的案例 ID '{c_ref}'；当前允许案例: {list(active_case_ids)}"
                )

        # 5. 证据真实性校验 (evidence_refs 必须来自 allowlist)
        ev_refs = raw.get("evidence_refs", [])
        for ev_ref in ev_refs:
            if ev_ref not in evidence_allowlist:
                raise CultureValidationError(
                    f"Issue[{idx}] 引用了未知或不在输入允许范围的证据 ID '{ev_ref}'；允许证据包括: {list(evidence_allowlist)}"
                )

        # 6. 排序因子严格类型校验与打分计算
        impact = raw.get("impact_level")
        likelihood = raw.get("occurrence_likelihood")
        remediation = raw.get("remediation_difficulty")
        score = compute_ranking_score(impact, likelihood, remediation)

        # 7. 置信度未校准强约束校验
        raw_conf = raw.get("confidence", {})
        if raw_conf.get("calibrated_score") is not None:
            raise CultureValidationError(f"Issue[{idx}] 当前未接入独立校准模型，calibrated_score 必须为 null")
        if raw_conf.get("calibration_version") is not None:
            raise CultureValidationError(f"Issue[{idx}] calibration_version 必须为 null")

        # 8. P0 降级护栏：“缺证据P0降待补证P1且保留重大说明”
        sev = raw.get("severity_proposal", "P2")
        ev_status = raw.get("evidence_status", "insufficient")
        downgraded = False
        downgrade_reason = None

        if sev == "P0":
            # 严格依据：充分且至少有一条有效规则及一条来自 allowlist 的证据引用
            has_sufficient_evidence = (
                ev_status == "sufficient"
                and len(r_refs) > 0
                and len(ev_refs) > 0
                and all(e in evidence_allowlist for e in ev_refs)
            )
            if not has_sufficient_evidence:
                sev = "P1"
                downgraded = True
                downgrade_reason = (
                    "缺少直接法定强制条款编号或有效音画证据支撑硬阻断，依据RULE-CULT-001"
                    "从红线P0降级为待补证P1，保留重大疑点与影响打分供人工核查"
                )

        factor_reasons_raw = raw.get("factor_reasons")
        factor_reasons = None
        if isinstance(factor_reasons_raw, dict):
            factor_reasons = FactorReasons(**factor_reasons_raw)

        issue = CultureCheckIssue(
            issue_id=f"iss_{uuid.uuid4().hex[:20]}",
            unit_id=unit_id,
            category=raw.get("category", "other"),
            trigger_spans=validated_spans,
            severity_proposal=sev,
            impact_level=impact,
            occurrence_likelihood=likelihood,
            remediation_difficulty=remediation,
            ranking_score=score,
            factor_reasons=factor_reasons,
            confidence={
                "raw_score": raw_conf.get("raw_score") if raw_conf.get("raw_score") is not None else raw.get("confidence_raw"),
                "calibrated_score": None,
                "calibration_version": None,
                "basis": raw_conf.get("basis") or raw.get("confidence_basis") or "LLM自评(uncalibrated)",
            },
            rule_refs=r_refs,
            case_refs=c_refs,
            evidence_refs=ev_refs,
            evidence_status=ev_status,
            speaker_ref=raw.get("speaker_ref"),
            narrative_stance=raw.get("narrative_stance", unit.narrative_stance),
            explanation=raw.get("explanation", ""),
            suggested_action=raw.get("suggested_action", "modify_dialogue"),
            suggested_translation=raw.get("suggested_translation"),
            missing_context=raw.get("missing_context", []),
            downgraded_from_p0=downgraded,
            downgrade_reason=downgrade_reason,
            status="AI_PROPOSED",
        )
        processed_issues.append(issue)

    return processed_issues

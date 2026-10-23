import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL_ID,
    TEST_MODE,
)
import config.settings as settings
from code.backend.db import utc_now_iso
from code.backend.modules.asr_alignment.handler import (
    _post_gemini_serial,
    check_cloud_authorization,
    sanitize_error_message,
    GeminiProviderError,
)
from code.backend.modules.culture_check.contract import (
    LLMCultureCheckOutput,
    CultureCheckIssue,
    CultureCheckRequest,
    CultureCheckResult,
    CultureRuleItem,
    CultureUnitInput,
    FactorReasons,
    TriggerSpan,
    UncheckedUnit,
)
from code.backend.modules.culture_check.registry import (
    CultureRegistry,
    default_registry,
)
from code.backend.modules.culture_check.validator import (
    CultureValidationError,
    compute_ranking_score,
    validate_and_process_culture_issues,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent / "rules" / "schemas"

# Gemini 官方响应结构契约 (文化检测专属)
GEMINI_CULTURE_CHECK_SCHEMA = LLMCultureCheckOutput.model_json_schema()
# Pydantic 生成的 schema 含 $defs/$ref，只能用 responseJsonSchema，不能换成 response_schema。


def get_prompt_templates() -> Tuple[str, str]:
    """读取并返回系统提示词和用户任务模板"""
    sys_path = PROMPTS_DIR / "system.txt"
    user_path = PROMPTS_DIR / "user_task.txt"
    sys_content = sys_path.read_text(encoding="utf-8").strip() if sys_path.exists() else "文化与合规审查引擎"
    user_content = user_path.read_text(encoding="utf-8").strip() if user_path.exists() else "{units_json}"
    return sys_content, user_content


def build_prompts(
    request: CultureCheckRequest,
    rules: List[CultureRuleItem],
    cases: List[Any],
) -> Tuple[str, str, str, str]:
    """
    构造注入严格结构化数据后的 Prompts 并计算校验 Hash。
    返回: (sys_prompt, user_prompt, prompt_hash, input_hash)
    """
    sys_prompt, user_tmpl = get_prompt_templates()

    # 结构化准备单元数据
    units_payload = []
    for u in request.units:
        units_payload.append({
            "unit_id": u.unit_id,
            "text_evidence_ref": "unit:" + u.unit_id,
            "source_text": u.source_text,
            "target_text": u.target_text,
            "speaker_id": u.speaker_id,
            "character_name": u.character_name,
            "narrative_stance": u.narrative_stance,
            "prev_units": u.prev_units,
            "next_units": u.next_units,
        })

    rules_payload = [
        {
            "rule_id": r.rule_id,
            "clause_ref": r.clause_ref,
            "scope": r.scope,
            "category": r.category,
            "trigger_condition": r.trigger_condition,
            "exceptions": r.exceptions,
            "severity_default": r.severity_default,
            "version": r.rule_version,
            "status": r.status,
        }
        for r in rules
    ]

    cases_payload = [
        {
            "case_id": getattr(c, "case_id", ""),
            "observation": getattr(c, "source_translation_observation", ""),
            "boundary": getattr(c, "boundary_scope", ""),
        }
        for c in cases
    ]

    user_prompt = user_tmpl.format(
        schema_version=request.schema_version,
        task_ref=request.task_ref,
        task_revision=request.task_revision,
        source_language=request.source_language,
        target_language=request.target_language,
        target_market=request.target_market,
        target_audience=request.target_audience or "未知，不能推断全年龄",
        target_rating=request.target_rating or "未指定",
        distribution_channel=request.distribution_channel or "未知，不能推断发行渠道",
        missing_channel_or_audience=request.missing_channel_or_audience,
        media_coverage_json=json.dumps(request.media_evidence.model_dump(), ensure_ascii=False),
        rules_json=json.dumps(rules_payload, ensure_ascii=False, indent=2),
        cases_json=json.dumps(cases_payload, ensure_ascii=False, indent=2),
        units_json=json.dumps(units_payload, ensure_ascii=False, indent=2),
    )

    prompt_hash = hashlib.sha256((sys_prompt + user_prompt).encode("utf-8")).hexdigest()
    input_hash = hashlib.sha256(json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return sys_prompt, user_prompt, prompt_hash, input_hash


def execute_rule_based_path(
    units: List[CultureUnitInput],
    active_rules: List[CultureRuleItem],
) -> List[Dict[str, Any]]:
    """
    第一路：基于已核验规则的确定性/模式检索。
    精准定位明确的禁忌词、种族蔑称、毒品违禁词。
    """
    rule_map = {r.rule_id: r for r in active_rules}
    issues = []

    # 模式字典 (拉美/墨西哥针对性违规关键词)
    patterns = [
        {
            "rule_id": "R-MX-DISCRIM-01",
            "regex": re.compile(r"\b(indio mugroso|naco mugroso|pinche indio)\b", re.IGNORECASE),
            "source_regex": re.compile(r"(土包子|下等人|穷酸民|乡巴佬)"),
            "category": "discrimination",
            "severity": "P1",
            "impact": 2,
            "occurrence": 2,
            "remediation": 2,
            "explanation": "译文包含对墨西哥原住民/特定族群的严重歧视侮辱性词汇(indio mugroso)，违反反歧视法第9条XV款。",
            "suggested_action": "modify_dialogue",
            "suggested_translation": "ese don nadie",
            "evidence_status": "sufficient",
            "evidence_refs": ["MX-OFF-02-ART9-XV"],
        },
        {
            "rule_id": "R-MX-TABOO-01",
            # 覆盖 trigger_condition 已声明的两类形态：chingar 衍生严重脏词 + cabrón 恶意辱骂。
            # 早前只登记前者，导致 "maldito cabrón" 类台词漏检（2026-10-23 全链路由实测发现）。
            "regex": re.compile(
                r"\b(chingar a tu madre|hijo de la chingada"
                r"|mal(?:dito|dita)\s+cabr[oó]n|cabr[oó]n\s+mal(?:dito|dita))\b",
                re.IGNORECASE,
            ),
            "source_regex": re.compile(r"(去死吧|混蛋|王八蛋)"),
            "category": "local_taboo",
            "severity": "P2",
            "impact": 1,
            "occurrence": 2,
            "remediation": 1,
            "explanation": "译文滥用了墨西哥高度粗鄙的极端辱骂词，在全年龄/泛拉美传播中易引发观众反感及平台降权。",
            "suggested_action": "modify_dialogue",
            "suggested_translation": "vete al diablo",
            "evidence_status": "sufficient",
            "evidence_refs": ["MX-CASE-01-PRINCIPLE3"],
        },
        {
            "rule_id": "R-MX-CINEMA-01",
            "regex": re.compile(r"\b(cocaína pura|inyéctate heroína|fumemos mota)\b", re.IGNORECASE),
            "source_regex": re.compile(r"(纯度很高|吸一口|来点粉)"),
            "category": "sex_violence_addiction_ratings",
            "severity": "P1",
            "impact": 2,
            "occurrence": 2,
            "remediation": 2,
            "explanation": "台词涉及未成年人不适宜的成瘾性物质吸食细节，需做年龄分级提示或弱化露骨描写。",
            "suggested_action": "modify_dialogue",
            "suggested_translation": "algo de mercancía",
            "evidence_status": "sufficient",
            "evidence_refs": ["MX-OFF-01-TRANS-4"],
        },
    ]

    for u in units:
        for p in patterns:
            rule_id = p["rule_id"]
            if rule_id not in rule_map:
                continue

            tgt_match = p["regex"].search(u.target_text)
            if tgt_match:
                tgt_span = tgt_match.group(0)
                # 寻找源语对应片段
                src_match = p["source_regex"].search(u.source_text)
                src_span = src_match.group(0) if src_match else None

                issues.append({
                    "unit_id": u.unit_id,
                    "category": p["category"],
                    "trigger_spans": [{"source_span": src_span, "target_span": tgt_span}],
                    "severity_proposal": p["severity"],
                    "impact_level": p["impact"],
                    "occurrence_likelihood": p["occurrence"],
                    "remediation_difficulty": p["remediation"],
                    "factor_reasons": {
                        "impact_reason": f"触犯规则 {rule_id} 明确界定的禁用/受限模式",
                        "likelihood_reason": "拉美市场合规审查命中率极高",
                        "remediation_reason": "存在标准es-MX平替方案",
                    },
                    "confidence": {
                        "raw_score": None,
                        "calibrated_score": None,
                        "calibration_version": None,
                        "basis": "规则模式库精确命中(uncalibrated)",
                    },
                    "rule_refs": [rule_id],
                    "case_refs": ["MX-CASE-01"] if "TABOO" in rule_id else [],
                    "evidence_refs": [rule_map[rule_id].source_ref],
                    "evidence_status": p["evidence_status"],
                    "speaker_ref": u.speaker_id,
                    "narrative_stance": u.narrative_stance,
                    "explanation": p["explanation"],
                    "suggested_action": p["suggested_action"],
                    "suggested_translation": u.target_text.replace(tgt_span, p["suggested_translation"]),
                    "missing_context": [],
                })
    return issues


def mock_culture_check_execution(
    request: CultureCheckRequest,
    active_rules: List[CultureRuleItem],
    active_cases: List[Any],
) -> Dict[str, Any]:
    """
    高保真隔离模拟文化检测引擎：
    结合规则路与语境模型路，严格输出符合 Gemini 格式的 JSON 结果。
    """
    # 1. 规则检索命中
    rule_issues = execute_rule_based_path(request.units, active_rules)
    checked_unit_ids = [u.unit_id for u in request.units]
    unchecked_units = []

    # 2. 语境判定：检查是否属于反派口吻（narrative_stance == 'character_villain'）或反讽
    # 若存在角色设定，调整解释与补救建议
    final_issues = []
    unit_map = {u.unit_id: u for u in request.units}

    for iss in rule_issues:
        u = unit_map.get(iss["unit_id"])
        if u and u.narrative_stance == "character_villain":
            iss["narrative_stance"] = "character_villain"
            iss["explanation"] += " (注意：本句为反派角色台词，非作品主观倡导，但依据拉美平台公序良俗，仍建议避免极度敏感的族群侮辱)"
        final_issues.append(iss)

    return {
        "issues": final_issues,
        "checked_unit_ids": checked_unit_ids,
        "unchecked_units": unchecked_units,
        "coverage_limitations": [
            "首版检测仅覆盖台词文本与对话角色立场，未对视频画面画面、服化道或音乐音效进行多模态审查"
        ],
    }


def execute_culture_check(
    request: CultureCheckRequest,
    registry: CultureRegistry = default_registry,
    timeout_sec: float = 30.0,
) -> CultureCheckResult:
    """
    执行文化检测核心流水线：
    1. 适用规则与参考案例受控检索（未核规则严禁进入）。
    2. Prompt 与输入哈希生成。
    3. 双路检测：规则路径 + 语境模型路径（支持 Mock 与真实 Gemini 串行调用）。
    4. 严格工程校验：覆盖度、存在性跨度、引用真实性、排序因子、P0 降级护栏。
    5. 构建不可变执行 Manifest 与最终结果。
    """
    run_id = f"crun_{uuid.uuid4().hex[:12]}"

    # 1. 受控检索适用规则 (未核规则不 ACTIVE)
    if request.selected_rule_ids:
        active_rules = [
            r for r in registry.retrieve_applicable_rules(target_market=request.target_market, only_active=True)
            if r.rule_id in request.selected_rule_ids
        ]
    else:
        active_rules = registry.retrieve_applicable_rules(
            target_market=request.target_market,
            channel=request.distribution_channel,
            only_active=True,
        )

    active_cases = registry.retrieve_applicable_cases(
        target_market=request.target_market,
        only_active=True,
    )
    active_case_ids = {getattr(c, "case_id", "") for c in active_cases}

    # 2. 构建 Prompts 与 Manifest 数据
    sys_prompt, user_prompt, prompt_hash, input_hash = build_prompts(request, active_rules, active_cases)

    # 3. 决定运行模式：模拟 或 云调用
    is_simulated = bool(request.simulate)
    if is_simulated:
        if not settings.TEST_MODE:
            # 在非测试模式下若显式请求模拟，检查权限保护
            raise PermissionError("正式模式禁止模拟文化结果")
    else:
        auth = check_cloud_authorization()
        if not auth.allowed_in_pilot:
            raise PermissionError("本次工程批次未授权实际素材外传或云端调用: " + "、".join(auth.missing_items))

    manifest_usage: Dict[str, Any] = {}
    manifest_model = GEMINI_MODEL_ID if not is_simulated else "mock-gemini-3.5-flash-lite"

    if is_simulated:
        raw_output = mock_culture_check_execution(request, active_rules, active_cases)
        manifest_usage = {"prompt_tokens": 0, "completion_tokens": 0, "is_mock": True}
    else:
        # 复用已有安全调用、限流与串行控制，不写密钥
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": sys_prompt}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "responseJsonSchema": GEMINI_CULTURE_CHECK_SCHEMA,
                "temperature": 0.1,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        }
        try:
            with httpx.Client(timeout=timeout_sec) as client:
                resp = _post_gemini_serial(client, endpoint, headers, payload)
                if resp.status_code != 200:
                    raise GeminiProviderError(resp.status_code, "API_ERROR", f"Gemini culture check failed: {resp.status_code}")
                resp_json = resp.json()
        except Exception as e:
            raise RuntimeError(f"Gemini 文化检测调用异常: {sanitize_error_message(e)}")

        cands = resp_json.get("candidates", [])
        if not cands:
            raise RuntimeError("Gemini API 返回无 candidates")
        if cands[0].get("finishReason") != "STOP":
            raise ValueError("文化模型输出未完整结束，未创建成功结果")
        raw_text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        raw_output = json.loads(raw_text)
        manifest_usage = resp_json.get("usageMetadata", {})

    if not is_simulated:
        raw_output = LLMCultureCheckOutput.model_validate(raw_output).model_dump()
    # 4. 执行工程级严格校验与 P0 降级护栏
    raw_issues = raw_output.get("issues", [])
    checked_unit_ids = raw_output.get("checked_unit_ids", [])
    raw_unchecked = raw_output.get("unchecked_units", [])
    unchecked_units = [UncheckedUnit(**u) for u in raw_unchecked]

    processed_issues = validate_and_process_culture_issues(
        request=request,
        raw_issues=raw_issues,
        checked_unit_ids=checked_unit_ids,
        unchecked_units=unchecked_units,
        active_rules=active_rules,
        active_case_ids=active_case_ids,
    )

    # Deterministic results are retained even when the model misses or disagrees.
    rule_results = execute_rule_based_path(request.units, active_rules)
    if rule_results:
        deterministic = validate_and_process_culture_issues(
            request, rule_results, [u.unit_id for u in request.units], [], active_rules, active_case_ids)
        existing = {(i.unit_id, i.category, tuple((s.source_span,s.target_span) for s in i.trigger_spans)) for i in processed_issues}
        for item in deterministic:
            key = (item.unit_id,item.category,tuple((s.source_span,s.target_span) for s in item.trigger_spans))
            if key not in existing:
                processed_issues.append(item)
                existing.add(key)

    manifest = {
        "run_id": run_id,
        "task_ref": request.task_ref,
        "task_revision": request.task_revision,
        "translation_refs": {u.unit_id: {"translation_id": u.translation_id, "revision": u.translation_revision} for u in request.units},
        "model_id": manifest_model,
        "prompt_version": "2026-10-22.1",
        "prompt_hash": prompt_hash,
        "input_hash": input_hash,
        "rule_versions": {r.rule_id: r.rule_version for r in active_rules},
        "target_market": request.target_market,
        "target_language": request.target_language,
        "schema_version": request.schema_version,
        "output_schema_hash": hashlib.sha256(json.dumps(GEMINI_CULTURE_CHECK_SCHEMA, sort_keys=True).encode()).hexdigest(),
        "case_refs": [c.case_id for c in active_cases],
        "risk_policy_version": "2026-10-22.1",
        "risk_ranking_formula": "impact_level * occurrence_likelihood * remediation_difficulty (1..27)",
        "evidence_downgrade_policy": "MISSING_EVIDENCE_P0_DOWNGRADED_TO_P1",
        "usage": manifest_usage,
        "is_simulated": is_simulated,
        "temperature": 0.1,
        "model_version": resp_json.get("modelVersion") if not is_simulated else None,
        "source_coverage": "text_only",
        "cost": None,
        "created_at": utc_now_iso(),
    }

    return CultureCheckResult(
        schema_version=request.schema_version,
        run_id=run_id,
        task_ref=request.task_ref,
        task_revision=request.task_revision,
        target_market=request.target_market,
        issues=processed_issues,
        checked_unit_ids=checked_unit_ids,
        unchecked_units=unchecked_units,
        coverage_limitations=list(dict.fromkeys(raw_output.get("coverage_limitations", []) + ["本次仅检查字幕文本，未直接分析音频或画面", "当前正式规则条目仍待适用性核验；未发现问题不代表合规"])),
        manifest=manifest,
    )

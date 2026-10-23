import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from config.settings import (
    BASE_DIR,
    GEMINI_API_KEY,
    GEMINI_MODEL_ID,
    TEST_MODE,
)
import config.settings as settings
from code.backend.db import Database, db, utc_now_iso
from code.backend.modules.asr_alignment.handler import (
    _post_gemini_serial,
    check_cloud_authorization,
    sanitize_error_message,
    GeminiProviderError,
)
from code.backend.modules.translation.contract import (
    GenerateTranslationRequest,
    SemanticCheckIssue,
    SemanticCheckOutput,
    TermHit,
    TranslationTaskInput,
    TranslationTaskOutput,
    TranslationUnitInput,
    UnitTranslation,
)
from code.backend.modules.translation.prompt_contract import PromptTranslationOutput, PromptCheckOutput
from code.backend.modules.translation.knowledge import knowledge_service, KnowledgeService

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

GEMINI_TRANSLATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "unit_id": {"type": "STRING"},
                    "translation": {"type": "STRING"},
                    "term_hits": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "source_term": {"type": "STRING"},
                                "required_target": {"type": "STRING"},
                                "actual_target": {"type": "STRING"},
                                "term_ref": {"type": "STRING"},
                                "matched": {"type": "BOOLEAN"},
                            },
                            "required": ["source_term", "required_target", "actual_target", "matched"],
                        },
                    },
                    "brief_source_paraphrase": {"type": "STRING"},
                    "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["unit_id", "translation", "term_hits", "brief_source_paraphrase", "issues"],
            },
        },
    },
    "required": ["translations"],
}

GEMINI_SEMANTIC_CHECK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "issues": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "unit_id": {"type": "STRING"},
                    "category": {
                        "type": "STRING",
                        "enum": [
                            "omission", "addition", "number", "negation", "entity",
                            "relationship", "address", "context", "other"
                        ],
                    },
                    "severity": {
                        "type": "STRING",
                        "enum": ["BLOCK", "WARN", "INFO"],
                    },
                    "source_span": {"type": "STRING"},
                    "target_span": {"type": "STRING"},
                    "detail": {"type": "STRING"},
                    "suggestion": {"type": "STRING"},
                    "uncertainty": {"type": "STRING"},
                },
                "required": ["unit_id", "category", "severity", "detail"],
            },
        },
        "qe_status": {"type": "STRING"},
    },
    "required": ["issues"],
}


def get_check_prompts(
    source_language: str,
    target_language: str,
    target_market: str,
    locked_terms: List[Dict[str, Any]],
    pairs: List[Dict[str, Any]],
    context_bundle: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    sys_file = PROMPTS_DIR / "check_system.txt"
    user_file = PROMPTS_DIR / "check_user.txt"

    sys_prompt = sys_file.read_text(encoding="utf-8").strip() if sys_file.exists() else "短剧双语语义审查引擎"
    user_tmpl = user_file.read_text(encoding="utf-8").strip() if user_file.exists() else "{pairs_json}"

    user_prompt = user_tmpl.format(
        source_language=source_language,
        target_language=target_language,
        target_market=target_market,
        locked_terms_json=json.dumps(locked_terms, ensure_ascii=False, indent=2),
        pairs_json=json.dumps(pairs, ensure_ascii=False, indent=2),
        context_bundle_json=json.dumps(context_bundle or {},ensure_ascii=False,indent=2),
    )
    return sys_prompt, user_prompt


def get_translation_prompts(
    source_language: str,
    target_language: str,
    target_market: str,
    source_revision: int,
    locked_terms: List[Dict[str, Any]],
    character_context: List[Dict[str, Any]],
    units: List[Dict[str, Any]],
    history_context: Optional[List[Dict[str, Any]]] = None,
    scene_context: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str]:
    sys_file = PROMPTS_DIR / "translate_system.txt"
    user_file = PROMPTS_DIR / "translate_user.txt"

    sys_prompt = sys_file.read_text(encoding="utf-8").strip() if sys_file.exists() else "短剧出海初翻引擎"
    user_tmpl = user_file.read_text(encoding="utf-8").strip() if user_file.exists() else "{units_json}"

    user_prompt = user_tmpl.format(
        source_language=source_language,
        target_language=target_language,
        target_market=target_market,
        source_revision=source_revision,
        locked_terms_json=json.dumps(locked_terms, ensure_ascii=False, indent=2),
        character_context_json=json.dumps(character_context, ensure_ascii=False, indent=2),
        units_json=json.dumps(units, ensure_ascii=False, indent=2),
        history_context_json=json.dumps(history_context or [],ensure_ascii=False,indent=2),
        scene_context_json=json.dumps(scene_context or [],ensure_ascii=False,indent=2),
    )
    return sys_prompt, user_prompt


def run_deterministic_semantic_checks(
    source_text: str,
    translation_text: str,
    unit_id: str,
    locked_terms: List[Dict[str, Any]],
) -> List[SemanticCheckIssue]:
    """
    Independent deterministic rule-based checks:
    1. Locked terms omission: if source contains locked term and target does not -> BLOCK
    2. Number mismatch -> WARN
    3. Negation mismatch -> WARN
    4. Gender / address conflicts -> WARN
    """
    issues: List[SemanticCheckIssue] = []

    # 1. Locked terms check
    for term in locked_terms:
        src = term.get("source_term", "")
        tgt = term.get("target_term", "")
        if src and src.lower() in source_text.lower():
            if not tgt or tgt.lower() not in translation_text.lower():
                issues.append(SemanticCheckIssue(
                    check_id=f"chk_term_{uuid.uuid4().hex[:8]}",
                    unit_id=unit_id,
                    category="omission",
                    severity="BLOCK",
                    source_span=src,
                    target_span=None,
                    evidence_refs=[term.get("term_id", "term")],
                    detail=f"违反强制锁词: 源句包含锁词 '{src}'，但译文未包含指定译法 '{tgt}'！",
                    suggestion=f"请在译文中强制使用 '{tgt}'",
                    status="OPEN",
                ))

    # 2. Number check
    # Extract digit sequences
    src_nums = set(re.findall(r"\d+", source_text))
    tgt_nums = set(re.findall(r"\d+", translation_text))
    # Chinese numbers check
    cn_num_map = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
    for cn, d in cn_num_map.items():
        if cn in source_text and (d not in tgt_nums and cn not in translation_text):
            # Check English word equivalent
            en_words = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}
            if en_words.get(d) not in translation_text.lower():
                issues.append(SemanticCheckIssue(
                    check_id=f"chk_num_{uuid.uuid4().hex[:8]}",
                    unit_id=unit_id,
                    category="number",
                    severity="WARN",
                    source_span=cn,
                    target_span=None,
                    evidence_refs=[unit_id],
                    detail=f"数字一致性存疑: 源语包含数字 '{cn}'，译文中未找到对应数字",
                    suggestion=f"请核对译文是否准确表达了数字 '{cn}'",
                    status="OPEN",
                ))

    # 3. Negation check
    negations_cn = ["不", "没", "未", "无", "休", "别", "勿", "绝不"]
    negations_en = ["not", "no", "never", "n't", "none", "neither", "nor", "without", "hardly"]
    has_cn_neg = any(n in source_text for n in negations_cn)
    has_en_neg = any(n in translation_text.lower().split() or "n't" in translation_text.lower() for n in negations_en)
    if has_cn_neg and not has_en_neg:
        issues.append(SemanticCheckIssue(
            check_id=f"chk_neg_{uuid.uuid4().hex[:8]}",
            unit_id=unit_id,
            category="negation",
            severity="WARN",
            source_span="[否定词]",
            target_span=None,
            evidence_refs=[unit_id],
            detail="肯定/否定极性疑似颠倒: 原句包含否定表达，译文未检测到明确否定词",
            suggestion="请人工核查译文是否反转了原句肯定/否定关系",
            status="OPEN",
        ))

    # 4. Address conflict check
    if "少爷" in source_text and "young master" not in translation_text.lower():
        issues.append(SemanticCheckIssue(
            check_id=f"chk_addr_{uuid.uuid4().hex[:8]}",
            unit_id=unit_id,
            category="address",
            severity="WARN",
            source_span="少爷",
            target_span=None,
            evidence_refs=[unit_id],
            detail="称谓敬语提示: 源语包含'少爷'，建议核查目标市场尊称习惯",
            suggestion="建议译为 'Young Master' 或保留语境称谓",
            status="OPEN",
        ))

    return issues


def mock_translate_units(
    units: List[TranslationUnitInput],
    locked_terms: List[Dict[str, Any]],
    target_language: str,
    target_market: str,
) -> TranslationTaskOutput:
    """
    Deterministic rule-based mock translation for unit tests.
    """
    results: List[UnitTranslation] = []
    for u in units:
        text = u.text
        # Simple rule mock translation
        trans = f"[Translated to {target_language}-{target_market}]: {text}"
        term_hits: List[TermHit] = []

        # Apply locked terms substitution
        for lt in locked_terms:
            s_term = lt.get("source_term", "")
            t_term = lt.get("target_term", "")
            if s_term and s_term in text:
                trans = trans.replace(s_term, t_term)
                term_hits.append(TermHit(
                    source_term=s_term,
                    required_target=t_term,
                    actual_target=t_term,
                    term_ref=lt.get("term_id"),
                    matched=True,
                ))

        results.append(UnitTranslation(
            unit_id=u.unit_id,
            translation=trans,
            term_hits=term_hits,
            brief_source_paraphrase=f"原句回述: {text}",
            issues=[],
        ))

    return TranslationTaskOutput(schema_version="1.0.0", translations=results)


def execute_translation_pipeline(
    task_id: str,
    req: GenerateTranslationRequest,
    actor_id: str = "operator",
    database: Optional[Database] = None,
    timeout_sec: float = 45.0,
) -> Dict[str, Any]:
    """
    Executes Task B (Translation Generation) and Task C (Semantic Check).
    Strict boundaries:
    - Source transcript MUST be in CONFIRMED status (Gate 1).
    - Target market MUST be user-chosen (cannot be empty or defaulted).
    - Pre-retrieves locked terms and characters.
    - Context window: ±2 units.
    - Preserves locked translations.
    """
    if database is None:
        database = db
    if not req.target_market or not req.target_market.strip():
        raise ValueError("目标市场 (target_market) 必须由用户显式选择，严禁为空或系统盲猜！")

    with database.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise ValueError("任务不存在")

        # Find latest confirmed source transcript
        cur.execute("""
        SELECT * FROM source_transcripts
        WHERE task_id = ?
        ORDER BY revision DESC LIMIT 1
        """, (task_id,))
        trans_row = cur.fetchone()
        if not trans_row:
            raise ValueError("尚未执行源语整理，请先执行源语整理并完成人工确认")

        if trans_row["status"] != "CONFIRMED":
            raise ValueError(f"STAGE_NOT_READY: 当前源稿版本 (rev: {trans_row['revision']}) 尚未人工确认，禁止启动初翻！")

        confirmed_revision = trans_row["revision"]
        source_language = trans_row["source_language"]

        # Fetch confirmed source utterances
        cur.execute("""
        SELECT * FROM source_utterances
        WHERE task_id = ? AND transcript_revision = ?
        ORDER BY unit_index ASC
        """, (task_id, confirmed_revision))
        utt_rows = [dict(r) for r in cur.fetchall()]
        if not utt_rows:
            raise ValueError("当前确认源稿中没有对话单元")

    # Resolve context through the explicitly injected database, not a global store.
    context_service = KnowledgeService(database)
    # Retrieve locked terms & characters
    all_texts = [u["text"] for u in utt_rows]
    locked_terms = context_service.query_locked_terms_for_units(
        project_id=task_row["project_id"],
        units_text=all_texts,
        target_language=req.target_language,
        target_market=req.target_market,
        task_id=task_id,
    )
    character_context = context_service.query_characters(project_id=task_row["project_id"],units_text=all_texts,
        character_refs=[u.get("character_ref") for u in utt_rows if u.get("character_ref")],task_id=task_id,
        target_language=req.target_language,target_market=req.target_market)
    history_context = context_service.query_confirmed_history(task_row["project_id"],task_id,all_texts,req.target_language,req.target_market)
    scene_context = [item for item in context_service.list_items(task_row["project_id"],category="scene",only_confirmed=True)
        if context_service._applies(item,req.target_language,req.target_market,task_id)
        and (item.get("task_id")==task_id or item["source_text"] in all_texts)]
    context_bundle = {"source_revision":confirmed_revision,"locked_terms":locked_terms,"characters":character_context,
        "scenes":[context_service.snapshot_ref(item) for item in scene_context],"confirmed_history":history_context}
    context_hash=hashlib.sha256(json.dumps(context_bundle,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    # Prepare unit inputs with ±2 context window
    unit_inputs: List[TranslationUnitInput] = []
    for idx, u in enumerate(utt_rows):
        prev_texts = [utt_rows[i]["text"] for i in range(max(0, idx - 2), idx)]
        next_texts = [utt_rows[i]["text"] for i in range(idx + 1, min(len(utt_rows), idx + 3))]
        unit_inputs.append(TranslationUnitInput(
            unit_id=u["unit_id"],
            text=u["text"],
            speaker_id=u.get("speaker_id"),
            character_name=u.get("character_ref"),
            prev_units=prev_texts,
            next_units=next_texts,
        ))

    is_simulated = bool(req.simulate)
    if is_simulated:
        if not getattr(settings, "TEST_MODE", False):
            raise PermissionError("普通正式环境禁止使用模拟初翻。模拟仅允许在显式服务端测试模式（SUBTITLE_TEST_MODE=1）及隔离测试环境下运行。")
    else:
        auth = check_cloud_authorization()
        if not auth.allowed_in_pilot:
            raise PermissionError("本次工程批次未授权实际素材外传或云端调用: " + "、".join(auth.missing_items))

    manifest_usage: Dict[str, Any] = {}
    manifest_model = GEMINI_MODEL_ID
    sys_prompt, user_prompt = get_translation_prompts(
        source_language=source_language,
        target_language=req.target_language,
        target_market=req.target_market,
        source_revision=confirmed_revision,
        locked_terms=locked_terms,
        character_context=character_context,
        units=[u.model_dump() for u in unit_inputs],
        history_context=history_context,
        scene_context=scene_context,
    )
    prompt_hash = hashlib.sha256((sys_prompt + user_prompt).encode()).hexdigest()
    input_hash = hashlib.sha256(json.dumps([u.model_dump() for u in unit_inputs], sort_keys=True).encode()).hexdigest()

    if is_simulated:
        trans_output = mock_translate_units(
            units=unit_inputs,
            locked_terms=locked_terms,
            target_language=req.target_language,
            target_market=req.target_market,
        )
        manifest_usage = {"prompt_tokens": 0, "completion_tokens": 0, "is_mock": True, "note": "SIMULATED_MOCK_NO_USAGE"}
    else:
        # Call Gemini via serial lane
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": sys_prompt}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": GEMINI_TRANSLATION_SCHEMA,
                "temperature": 0.2,
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
                    raise GeminiProviderError(resp.status_code, "API_ERROR", f"Task B Gemini failed: {resp.status_code}")
                resp_json = resp.json()
        except Exception as e:
            raise RuntimeError(f"Task B 调用异常: {sanitize_error_message(e)}")

        cands = resp_json.get("candidates", [])
        if not cands:
            raise RuntimeError("Gemini API 返回无 candidates")
        if cands[0].get("finishReason", "STOP") != "STOP":
            raise ValueError("模型输出被截断，拒绝写入")
        raw_text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        parsed = PromptTranslationOutput.model_validate(json.loads(raw_text)).model_dump()

        trans_list = []
        for t in parsed.get("translations", []):
            trans_list.append(UnitTranslation(
                unit_id=t["unit_id"],
                translation=t["translation"],
                term_hits=[TermHit(**th) for th in t.get("term_hits", [])],
                brief_source_paraphrase=t.get("brief_source_paraphrase"),
                issues=t.get("issues", []),
            ))
        allowed_terms={term['term_id']:term for term in locked_terms}
        for translated in trans_list:
            for hit in translated.term_hits:
                term=allowed_terms.get(hit.term_ref) if hit.term_ref else next((x for x in locked_terms if x['source_term']==hit.source_term),None)
                if term is None or term['source_term'] != hit.source_term or term['target_term'] != hit.required_target:
                    raise ValueError("初翻引用了输入外的术语或篡改锁定译法")
                if hit.actual_target and hit.actual_target not in translated.translation:
                    raise ValueError("term_hits实际译法不在当前译文中")
        trans_output = TranslationTaskOutput(schema_version="1.0.0", translations=trans_list)
        expected_ids = {u.unit_id for u in unit_inputs}
        returned_ids = [t.unit_id for t in trans_list]
        if set(returned_ids) != expected_ids or len(returned_ids) != len(expected_ids) or any(not t.translation.strip() for t in trans_list):
            raise ValueError("初翻返回缺项、重复/越界单元或空译文，拒绝写入")
        manifest_usage = resp_json.get("usageMetadata", {})

    # Execute Task C: Deterministic Semantic Checks on each translated unit
    all_issues: List[SemanticCheckIssue] = []
    unit_map = {u["unit_id"]: u["text"] for u in utt_rows}

    # Derive terminology provenance from actual input/output, not the model's matched claim.
    for translated in trans_output.translations:
        translated.term_hits = [TermHit(source_term=term['source_term'], required_target=term['target_term'],
            actual_target=term['target_term'] if term['target_term'] and term['target_term'].casefold() in translated.translation.casefold() else '',
            term_ref=term['term_id'], matched=bool(term['target_term'] and term['target_term'].casefold() in translated.translation.casefold()))
            for term in locked_terms if term['source_term'].casefold() in unit_map[translated.unit_id].casefold()]

    for t in trans_output.translations:
        src_text = unit_map.get(t.unit_id, "")
        issues = run_deterministic_semantic_checks(
            source_text=src_text,
            translation_text=t.translation,
            unit_id=t.unit_id,
            locked_terms=locked_terms,
        )
        all_issues.extend(issues)

    # Execute Task C: Genuine Independent Semantic Model Check (Prompt/Schema)
    check_failure = None
    check_usage = None
    check_prompt_hash = None
    if not is_simulated:
        check_pairs = [
            {
                "unit_id": t.unit_id,
                "source_text": unit_map.get(t.unit_id, ""),
                "translation": t.translation,
                "brief_paraphrase": t.brief_source_paraphrase,
            }
            for t in trans_output.translations
        ]
        chk_sys_prompt, chk_user_prompt = get_check_prompts(
            source_language=source_language,
            target_language=req.target_language,
            target_market=req.target_market,
            locked_terms=locked_terms,
            pairs=check_pairs,
            context_bundle={**context_bundle,"units":[u.model_dump() for u in unit_inputs]},
        )
        chk_payload = {
            "systemInstruction": {"parts": [{"text": chk_sys_prompt}]},
            "contents": [
                {"role": "user", "parts": [{"text": chk_user_prompt}]}
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": GEMINI_SEMANTIC_CHECK_SCHEMA,
                "temperature": 0.0,
            },
        }
        check_prompt_hash = hashlib.sha256((chk_sys_prompt + chk_user_prompt).encode()).hexdigest()
        try:
            with httpx.Client(timeout=timeout_sec) as client:
                c_resp = _post_gemini_serial(client, endpoint, headers, chk_payload)
                if c_resp.status_code == 200:
                    check_usage = c_resp.json().get('usageMetadata')
                    c_cand = c_resp.json().get("candidates", [{}])[0]
                    c_text = c_cand.get("content", {}).get("parts", [{}])[0].get("text", "{}")
                    c_parsed = PromptCheckOutput.model_validate(json.loads(c_text)).model_dump()
                    if c_cand.get('finishReason', 'STOP') != 'STOP' or not isinstance(c_parsed, dict) or not isinstance(c_parsed.get('issues'), list):
                        raise ValueError('语义检查结果缺失issues或输出被截断')
                    for ci in c_parsed.get("issues", []):
                        if ci.get('unit_id') not in unit_map:
                            raise ValueError('语义检查引用了输入外的单元')
                        target_text=next(t.translation for t in trans_output.translations if t.unit_id==ci['unit_id'])
                        if ci.get('source_span') and ci['source_span'] not in unit_map[ci['unit_id']]:
                            raise ValueError('语义检查源文跨度不存在')
                        if ci.get('target_span') and ci['target_span'] not in target_text:
                            raise ValueError('语义检查译文跨度不存在')
                        all_issues.append(SemanticCheckIssue(
                            check_id=f"chk_model_{uuid.uuid4().hex[:8]}",
                            unit_id=ci.get("unit_id", "u_001"),
                            category=ci.get("category", "other"),
                            severity=ci.get("severity", "WARN"),
                            source_span=ci.get("source_span"),
                            target_span=ci.get("target_span"),
                            evidence_refs=[ci.get("unit_id", "u_001")],
                            detail=ci.get("detail", "模型语义检查报警"),
                            suggestion=ci.get("suggestion"),
                            uncertainty=ci.get("uncertainty"),
                            status="OPEN",
                        ))
                else:
                    check_failure = {"http_status": c_resp.status_code, "message": "语义检查服务未完成，请恢复后重新检查"}
                    all_issues.append(SemanticCheckIssue(
                        check_id=f"chk_err_{uuid.uuid4().hex[:8]}",
                        unit_id=trans_output.translations[0].unit_id if trans_output.translations else "all",
                        category="other",
                        severity="BLOCK",
                        detail=f"Task C 语义模型检查接口返回异常 (HTTP {c_resp.status_code})，保留候选供人工核查",
                        status="OPEN",
                    ))
        except Exception as e:
            check_failure = {"message": sanitize_error_message(e)}
            all_issues.append(SemanticCheckIssue(
                check_id=f"chk_err_{uuid.uuid4().hex[:8]}",
                unit_id=trans_output.translations[0].unit_id if trans_output.translations else "all",
                category="other",
                severity="BLOCK",
                detail=f"Task C 语义模型检查异常: {sanitize_error_message(e)}，已保留译稿供人工核查",
                status="OPEN",
            ))

    if check_failure:
        # A failed global semantic check prevents every generated unit from approval.
        for candidate in trans_output.translations:
            if not any(i.unit_id == candidate.unit_id and i.severity == "BLOCK" for i in all_issues):
                all_issues.append(SemanticCheckIssue(
                    check_id=f"chk_unchecked_{uuid.uuid4().hex[:8]}", unit_id=candidate.unit_id,
                    category="other", severity="BLOCK", detail="语义检查未完成，不能确认此候选", status="OPEN"))

    # Persist into database: translations and translation_checks
    run_id = f"run_trans_{uuid.uuid4().hex[:12]}"
    now = utc_now_iso()

    with database.transaction() as conn:
        # Check existing translations for locked items
        cur = conn.cursor()
        latest_source = cur.execute("SELECT revision,status FROM source_transcripts WHERE task_id=? ORDER BY revision DESC LIMIT 1", (task_id,)).fetchone()
        if not latest_source or latest_source['revision'] != confirmed_revision or latest_source['status'] != 'CONFIRMED':
            raise ValueError("生成期间源稿已变化，结果未写入，请刷新后重试")
        cur.execute("""
        SELECT unit_id, is_locked, text, status, translation_revision FROM translations
        WHERE task_id = ? AND source_revision = ?
        ORDER BY translation_revision ASC, rowid ASC
        """, (task_id, confirmed_revision))
        existing_trans = {r["unit_id"]: dict(r) for r in cur.fetchall()}

        # Insert run
        conn.execute("""
        INSERT INTO runs (
            run_id, task_id, task_revision, trace_id, authorization_ref,
            permission_check_ref, module, input_refs, input_revision,
            idempotency_key, attempt_no, attempts, run_status, stop_reason,
            context_manifest, manifest_hash, steps, started_at, ended_at,
            usage, controls, output_refs, failure, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            run_id, task_id, task_row["task_revision"], f"trace_{uuid.uuid4().hex[:8]}",
            "AUTH-TRANSLATION", "PERM-CHECK-001", "translation",
            json.dumps([{"unit_id": u.unit_id} for u in unit_inputs]),
            confirmed_revision, f"idem_{uuid.uuid4().hex[:8]}", 1, json.dumps([]),
            "FAILED" if check_failure else "SUCCEEDED", "SEMANTIC_CHECK_FAILED" if check_failure else None,
            json.dumps({
                "model_id": manifest_model,
                "prompt_hash": prompt_hash,
                "target_market": req.target_market,
                "temperature": 0.2,
                "input_hash": input_hash,
                "is_simulated": is_simulated,
                "semantic_check_prompt_hash": check_prompt_hash,
                "context_hash": context_hash,
                "context_snapshot": context_bundle,
                "prompt_version": "2026-10-22.2",
            }),
            prompt_hash, json.dumps(["retrieve_context", "translate", "semantic_check", "persist"]),
            now, now, json.dumps({"translation": manifest_usage, "semantic_check": check_usage}), json.dumps({"shared_interval": 4.5}),
            json.dumps([{"translations_count": len(trans_output.translations), "locked_candidate_proposals": [t.model_dump() for t in trans_output.translations if existing_trans.get(t.unit_id, {}).get('is_locked')]}]), json.dumps(check_failure) if check_failure else None, now, actor_id
        ))

        # Checks belong to their exact candidate; preserve all historical evidence.
        generated_ids = {}

        for t in trans_output.translations:
            exist = existing_trans.get(t.unit_id)
            if exist and (exist.get("is_locked") or exist.get("status") == "CONFIRMED"):
                # Locked item: DO NOT overwrite! Preserve locked content and mark candidate proposal
                continue

            trans_id = f"tr_trans_{uuid.uuid4().hex[:12]}"
            generated_ids[t.unit_id] = trans_id
            cur_rev = (exist["translation_revision"] + 1) if exist else 1

            conn.execute("""
            INSERT OR REPLACE INTO translations (
                translation_id, task_id, unit_id, source_revision,
                translation_revision, target_language, target_market,
                text, brief_paraphrase, term_hits, status, is_locked,
                run_id, confirmed_by, confirmed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                trans_id, task_id, t.unit_id, confirmed_revision,
                cur_rev, req.target_language, req.target_market,
                t.translation, t.brief_source_paraphrase,
                json.dumps([th.model_dump() for th in t.term_hits]),
                "AI_PROPOSED", 0, run_id, None, None, now, now
            ))

            # Record history
            conn.execute("""
            INSERT INTO translation_history (
                history_id, task_id, unit_id, translation_id, revision,
                text, status, actor_id, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"th_{uuid.uuid4().hex[:12]}", task_id, t.unit_id, trans_id,
                cur_rev, t.translation, "AI_PROPOSED", actor_id, "ai_generate", now
            ))

        # Insert semantic check issues
        for iss in all_issues:
            iss_id = iss.check_id or f"chk_{uuid.uuid4().hex[:12]}"
            tr_id = generated_ids.get(iss.unit_id)
            if not tr_id:
                continue  # protected human candidate: do not attach new AI checks to it

            conn.execute("""
            INSERT INTO translation_checks (
                check_id, task_id, unit_id, translation_id, category,
                severity, source_span, target_span, evidence_refs,
                detail, suggestion, uncertainty, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                iss_id, task_id, iss.unit_id, tr_id, iss.category,
                iss.severity, iss.source_span, iss.target_span,
                json.dumps(iss.evidence_refs), iss.detail, iss.suggestion,
                iss.uncertainty, iss.status, now
            ))

    return {
        "status": "CHECK_FAILED" if check_failure else "AI_PROPOSED",
        "task_id": task_id,
        "source_revision": confirmed_revision,
        "target_language": req.target_language,
        "target_market": req.target_market,
        "translations_count": len(trans_output.translations),
        "issues_count": len(all_issues),
        "blocking_issues_count": sum(1 for i in all_issues if i.severity == "BLOCK"),
        "qe_status": "未评估",
        "check_failure": check_failure,
        "manifest": {
            "model_id": manifest_model,
            "prompt_hash": prompt_hash,
            "run_id": run_id,
            "target_market": req.target_market,
            "is_simulated": is_simulated,
            "usage": manifest_usage,
            "context_hash": context_hash,
        },
    }

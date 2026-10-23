import base64
import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_BUDGET_AUTHORIZED,
    GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED,
    GEMINI_MODEL_ID,
    TEST_MODE,
)
from code.backend.modules.asr_alignment.contract import (
    ASRStatusResponse,
    ChunkTranscriptionResult,
    EntityCandidate,
    MasterSegmentResult,
    OverlapCandidate,
    TimingCandidate,
    UncertaintyCandidate,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_provider_request_lock = threading.Lock()
_last_request_started = None
MIN_REQUEST_INTERVAL_SECONDS = 4.5


def _post_gemini_serial(client, endpoint, headers, payload):
    """One process-wide lane across tasks; no retry and no request burst."""
    global _last_request_started
    with _provider_request_lock:
        if _last_request_started is not None:
            remaining = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_started)
            if remaining > 0:
                time.sleep(remaining)
        _last_request_started = time.monotonic()
        return client.post(endpoint, headers=headers, json=payload)

# Official Gemini response_schema specification for structured ASR output
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "text": {
            "type": "STRING",
            "description": "整片实际听到的忠实源语文字；无语音可为空，听不清处不造词",
        },
        "timing_candidates": {
            "type": "ARRAY",
            "description": "可选原文片段及片内起止毫秒候选；未知留空，严禁均分",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "start_ms": {"type": "INTEGER"},
                    "end_ms": {"type": "INTEGER"},
                    "text": {"type": "STRING"},
                },
                "required": ["text"],
            },
        },
        "uncertainties": {
            "type": "ARRAY",
            "description": "听不清/切点截断/指定语言疑似不符的说明及可定位范围",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "start_ms": {"type": "INTEGER"},
                    "end_ms": {"type": "INTEGER"},
                    "description": {"type": "STRING"},
                },
                "required": ["description"],
            },
        },
        "overlap_candidates": {
            "type": "ARRAY",
            "description": "重叠区间/涉及原文及可辨人数候选；未知留空，不冒称稳定说话人身份",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "start_ms": {"type": "INTEGER"},
                    "end_ms": {"type": "INTEGER"},
                    "text": {"type": "STRING"},
                    "speaker_count": {"type": "INTEGER"},
                    "description": {"type": "STRING"},
                },
                "required": ["text"],
            },
        },
        "entity_candidates": {
            "type": "ARRAY",
            "description": "专名原词、类别及出现语境候选",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "context": {"type": "STRING"},
                },
                "required": ["name"],
            },
        },
        "no_speech": {
            "type": "BOOLEAN",
            "description": "模型是否判断无语音，不能将该判断当已验证静音事实",
        },
        "model_self_eval_confidence": {
            "type": "NUMBER",
            "description": "模型自评未校准参考分 (0-1)",
        },
    },
    "required": [
        "text",
        "timing_candidates",
        "uncertainties",
        "overlap_candidates",
        "entity_candidates",
        "no_speech",
    ],
}


def sanitize_error_message(err: Any) -> str:
    """Strips API key patterns from error messages to prevent leakage into logs."""
    msg = str(err)
    if GEMINI_API_KEY:
        msg = msg.replace(GEMINI_API_KEY, "***")
    msg = re.sub(r"AIza[a-zA-Z0-9_\-]+", "***", msg)
    return re.sub(r"key=[a-zA-Z0-9_\-]+", "key=***", msg)


class GeminiProviderError(RuntimeError):
    """Safe provider failure metadata; no request URL, headers or audio retained here."""
    def __init__(self, http_status: int, provider_error: str, message: str, retry_delay=None):
        self.http_status = http_status
        self.provider_error = sanitize_error_message(provider_error)
        self.retry_delay = sanitize_error_message(retry_delay) if retry_delay is not None else None
        self.global_failure = http_status in (401, 403, 404, 429, 503)
        super().__init__(sanitize_error_message(message))

    def safe_detail(self):
        return {"http_status": self.http_status, "provider_error": self.provider_error,
                "message": str(self), "retry_delay": self.retry_delay}


def validate_gemini_response_structure(parsed: Dict[str, Any], finish_reason: Optional[str] = None) -> None:
    """
    Validates minimum genuine structure of Gemini ASR response.
    Enforces required fields, value ranges, timestamp monotonicity, and checks for truncation.
    """
    if finish_reason and finish_reason in ("MAX_TOKENS", "SAFETY", "RECITATION"):
        raise ValueError(f"Gemini ASR输出异常中止/截断: finishReason={finish_reason}")

    required_keys = ["text", "timing_candidates", "uncertainties", "overlap_candidates", "entity_candidates", "no_speech"]
    for k in required_keys:
        if k not in parsed:
            raise ValueError(f"Gemini ASR返回结构不全: 缺少字段 '{k}'")

    text = str(parsed.get("text", "")).strip()
    no_speech = bool(parsed.get("no_speech", False))
    if not no_speech and not text:
        raise ValueError("Gemini ASR返回非法空文字: no_speech=False 但 text 为空")
    if no_speech and text:
        raise ValueError("Gemini ASR返回冲突状态: no_speech=True 但 text 非空")

    timing_cands = parsed.get("timing_candidates", [])
    if not isinstance(timing_cands, list):
        raise ValueError("timing_candidates 必须为数组")
    for idx, tc in enumerate(timing_cands):
        if not isinstance(tc, dict):
            raise ValueError(f"timing_candidates[{idx}] 必须为对象")
        s = tc.get("start_ms")
        e = tc.get("end_ms")
        if s is not None:
            if not isinstance(s, int) or s < 0:
                raise ValueError(f"timing_candidates[{idx}].start_ms 必须为非负整数")
        if e is not None:
            if not isinstance(e, int) or e < 0:
                raise ValueError(f"timing_candidates[{idx}].end_ms 必须为非负整数")
        if s is not None and e is not None and s > e:
            raise ValueError(f"timing_candidates[{idx}] 时间倒置: start_ms={s} > end_ms={e}")

    conf = parsed.get("model_self_eval_confidence")
    if conf is not None:
        if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
            raise ValueError(f"model_self_eval_confidence 必须在 0.0 至 1.0 之间，收到: {conf}")


def get_prompts(source_language: str, chunk_duration_sec: float) -> Tuple[str, str]:
    sys_file = PROMPTS_DIR / "system.txt"
    user_file = PROMPTS_DIR / "user_task.txt"

    if sys_file.exists():
        system_prompt = sys_file.read_text(encoding="utf-8").strip()
    else:
        system_prompt = (
            "你是一个高精度的音频源语忠实听写系统。你的唯一职责是将音频中的语音内容以原文原语忠实转写出来。\n"
            "绝对不要进行翻译、润色或剧情分析；若有多人说话标记重叠候选；若无法精准定位起止时间严禁均分伪造。"
        )

    if user_file.exists():
        user_template = user_file.read_text(encoding="utf-8").strip()
    else:
        user_template = (
            "请将本段音频中的语音忠实转写为原文。源语言为：{source_language}，本片时长为：{chunk_duration_sec}秒。\n"
            "只根据实际声音转写，不翻译不润色，以约定的 JSON 结构返回。"
        )

    user_prompt = user_template.format(
        source_language=source_language,
        chunk_duration_sec=f"{chunk_duration_sec:.1f}",
    )
    return system_prompt, user_prompt


def check_cloud_authorization() -> ASRStatusResponse:
    """
    Checks authorization boundaries for external Gemini cloud API access.
    Strict rule: Cloud API adapter exists, but actual outbound material upload and billing
    require separate explicit authorization flags. If missing, status is prominently marked
    '待配置/待授权', and no cloud calls or uploads are made.
    """
    has_key = bool(GEMINI_API_KEY and len(GEMINI_API_KEY.strip()) > 5)
    outbound_auth = GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED
    budget_auth = GEMINI_BUDGET_AUTHORIZED

    missing: List[str] = []
    if not has_key:
        missing.append("GEMINI_API_KEY (云端API密钥未配置)")
    if not outbound_auth:
        missing.append("GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED (素材外传未经独立授权)")
    if not budget_auth:
        missing.append("GEMINI_BUDGET_AUTHORIZED (调用预算及计费未经独立授权)")

    allowed = has_key and outbound_auth and budget_auth
    status_str = "就绪" if allowed else "待配置/待授权"

    msg = (
        "云端接口适配器及结构化校验已就绪。"
        if allowed
        else "本次工程批次未授权实际素材外传或云端调用。云接口适配器与配置流程已就绪，但阻断未经授权的外传与收费。"
    )

    return ASRStatusResponse(
        model_id=GEMINI_MODEL_ID,
        has_api_key=has_key,
        external_outbound_authorized=outbound_auth,
        budget_authorized=budget_auth,
        status=status_str,
        missing_items=missing,
        allowed_in_pilot=allowed,
        message=msg,
    )


def transcribe_chunk_gemini(
    audio_path: Path,
    chunk_id: str,
    offset_ms: int,
    duration_ms: int,
    source_language: str = "zh-CN",
    timeout_sec: float = 30.0,
) -> ChunkTranscriptionResult:
    """
    Adapter for Google Gemini API generateContent with audio inline data and JSON response_schema.
    Enforces authorization check; never leaks API credentials to logs, frontend, or git.
    Captures input hash, prompt parameters, usage metadata, and finish_reason.
    """
    auth = check_cloud_authorization()
    if not auth.allowed_in_pilot:
        raise PermissionError(
            f"待配置/待授权: 阻断云端调用。未满足项: {', '.join(auth.missing_items)}"
        )

    if not audio_path.exists():
        raise FileNotFoundError(f"Chunk audio not found: {audio_path}")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()

    chunk_dur_sec = duration_ms / 1000.0
    sys_prompt, user_prompt = get_prompts(source_language, chunk_dur_sec)

    # Compute system input hash (audio hash + sys_prompt + user_prompt)
    input_hasher = hashlib.sha256()
    input_hasher.update(audio_hash.encode("ascii"))
    input_hasher.update(sys_prompt.encode("utf-8"))
    input_hasher.update(user_prompt.encode("utf-8"))
    input_hash = input_hasher.hexdigest()

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": audio_b64,
                        }
                    },
                    {
                        "text": user_prompt,
                    },
                ],
            }
        ],
        "system_instruction": {
            "parts": [
                {
                    "text": sys_prompt,
                }
            ]
        },
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": GEMINI_RESPONSE_SCHEMA,
            "temperature": 0.0,
        },
    }

    prompt_params = {
        "model_id": GEMINI_MODEL_ID,
        "temperature": 0.0,
        "source_language": source_language,
        "schema_version": "v1_fixed_pilot",
        "chunk_duration_sec": chunk_dur_sec,
    }

    # Use header to pass API key rather than query param to avoid URL exposure in logs
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = _post_gemini_serial(client, endpoint, headers, payload)
            if resp.status_code != 200:
                try:
                    error = resp.json().get("error", {})
                    if not isinstance(error, dict):
                        error = {}
                except Exception:
                    error = {}
                retry_delay = resp.headers.get("Retry-After")
                for item in error.get("details", []):
                    if isinstance(item, dict) and item.get("@type", "").endswith("RetryInfo"):
                        retry_delay = item.get("retryDelay", retry_delay)
                raise GeminiProviderError(resp.status_code, error.get("status", "UNKNOWN"),
                                          error.get("message", f"Gemini HTTP {resp.status_code}"), retry_delay)
            resp_data = resp.json()
    except GeminiProviderError:
        raise
    except Exception as e:
        safe_msg = sanitize_error_message(e)
        raise RuntimeError(f"Gemini API调用异常: {safe_msg}") from None

    # Extract text content and usage metadata from response
    candidates = resp_data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini API returned no candidates")

    cand_0 = candidates[0]
    finish_reason = cand_0.get("finishReason", "UNKNOWN")
    raw_text = cand_0.get("content", {}).get("parts", [{}])[0].get("text", "{}")

    try:
        parsed = json.loads(raw_text)
    except Exception as e:
        raise ValueError(f"Gemini API返回的JSON解析失败: {str(e)}")

    # Enforce minimum genuine structure validation
    validate_gemini_response_structure(parsed, finish_reason=finish_reason)

    usage_data = resp_data.get("usageMetadata", {})

    # Convert to typed structures
    timing_candidates = [
        TimingCandidate(**t) for t in parsed.get("timing_candidates", [])
    ]
    uncertainties = [
        UncertaintyCandidate(**u) for u in parsed.get("uncertainties", [])
    ]
    overlap_candidates = [
        OverlapCandidate(**o) for o in parsed.get("overlap_candidates", [])
    ]
    entity_candidates = [
        EntityCandidate(**e) for e in parsed.get("entity_candidates", [])
    ]

    return ChunkTranscriptionResult(
        chunk_id=chunk_id,
        offset_ms=offset_ms,
        duration_ms=duration_ms,
        text=parsed.get("text", "").strip(),
        timing_candidates=timing_candidates,
        uncertainties=uncertainties,
        overlap_candidates=overlap_candidates,
        entity_candidates=entity_candidates,
        no_speech=bool(parsed.get("no_speech", False)),
        model_self_eval_confidence=parsed.get("model_self_eval_confidence"),
        confidence_label="模型自评/未校准",
        is_simulated=False,
        input_hash=input_hash,
        prompt_params=prompt_params,
        usage_info=usage_data,
        finish_reason=finish_reason,
    )


def mock_transcribe_chunk(
    chunk_id: str,
    offset_ms: int,
    duration_ms: int,
    is_silent: bool = False,
    simulated_text: Optional[str] = None,
) -> ChunkTranscriptionResult:
    """
    Controlled Mock adapter used STRICTLY within isolated test environments.
    Strict rule: Explicitly tagged SIMULATED, never mixed into normal tasks as real recognition.
    """
    if is_silent:
        return ChunkTranscriptionResult(
            chunk_id=chunk_id,
            offset_ms=offset_ms,
            duration_ms=duration_ms,
            text="",
            timing_candidates=[],
            uncertainties=[
                UncertaintyCandidate(start_ms=0, end_ms=duration_ms, description="检测为数字静音/无语音")
            ],
            overlap_candidates=[],
            entity_candidates=[],
            no_speech=True,
            model_self_eval_confidence=None,
            confidence_label="模型自评/未校准 (SIMULATED)",
            is_simulated=True,
        )

    text = simulated_text or "这是受控隔离模拟的源语识别测试文本。"
    # Provide one sample timing candidate if duration >= 4000
    timings: List[TimingCandidate] = []
    if duration_ms >= 4000:
        timings.append(TimingCandidate(start_ms=500, end_ms=min(3500, duration_ms), text=text))

    return ChunkTranscriptionResult(
        chunk_id=chunk_id,
        offset_ms=offset_ms,
        duration_ms=duration_ms,
        text=text,
        timing_candidates=timings,
        uncertainties=[],
        overlap_candidates=[],
        entity_candidates=[
            EntityCandidate(name="测试专名", category="brand", context="这是受控隔离模拟的源语识别测试文本")
        ],
        no_speech=False,
        model_self_eval_confidence=0.88,
        confidence_label="模型自评/未校准 (SIMULATED)",
        is_simulated=True,
    )


def match_glossary(
    entities: List[EntityCandidate],
    glossary_terms: Optional[List[Dict[str, str]]] = None,
) -> List[EntityCandidate]:
    """
    Matches entity candidates strictly against verified project-scoped glossary terms.
    Strict rule: Never trusts model's self-reported 'matched' state!
    All entities are first reset to 'pending_confirmation' with glossary_ref=None.
    Only when an exact match is confirmed in the task's glossary terms does engineering
    code assign 'matched' status and record the glossary_ref.
    """
    # Defensive reset: never trust model self-filled 'matched'
    for e in entities:
        e.match_status = "pending_confirmation"
        e.glossary_ref = None

    if not glossary_terms:
        return entities

    glossary_map = {
        str(t.get("term", "")).strip().lower(): t.get("term_id", "TERM-REF")
        for t in glossary_terms
        if t.get("term")
    }

    for e in entities:
        norm_name = e.name.strip().lower()
        if norm_name in glossary_map:
            e.match_status = "matched"
            e.glossary_ref = glossary_map[norm_name]
        else:
            e.match_status = "pending_confirmation"
    return entities


def check_cross_slice_boundaries(
    results: List[ChunkTranscriptionResult],
) -> List[Dict[str, Any]]:
    """
    Inspects adjacent slice boundaries for suspected truncations, mid-sentence cuts, or repeats.
    """
    issues: List[Dict[str, Any]] = []

    for i in range(len(results) - 1):
        c1 = results[i]
        c2 = results[i + 1]

        # Check if c1 ends with uncertainty about boundary cut
        boundary_cut = False
        for u in c1.uncertainties:
            if "截断" in u.description or "切点" in u.description:
                boundary_cut = True
                break

        # Check text ending without punctuation or with ellipsis
        t1 = c1.text.strip()
        t2 = c2.text.strip()

        if t1 and t2:
            # If t1 doesn't end with sentence terminator (。！？!?), possible cross-slice cut
            if t1[-1] not in "。！？!?…~":
                boundary_cut = True

        if boundary_cut:
            issues.append({
                "issue_id": f"iss_boundary_{uuid.uuid4().hex[:8]}",
                "category": "boundary_truncation",
                "severity": "P1",
                "chunk_id": c1.chunk_id,
                "detail": f"切片 {c1.chunk_id} (offset: {c1.offset_ms}ms) 与 {c2.chunk_id} (offset: {c2.offset_ms}ms) 边界处疑似存在句子截断或跨片衔接疑点，需人工回听核验。",
                "confidence": "PROPOSED",
            })

    return issues


def map_chunks_to_master(
    chunks: List[Dict[str, Any]],
    results: List[ChunkTranscriptionResult],
    glossary_terms: Optional[List[Dict[str, str]]] = None,
) -> List[MasterSegmentResult]:
    """
    Maps slice-relative results to the master timeline using accurate offset_ms.
    Strict rule: Unknown sentence-level timestamps MUST NOT be evenly interpolated/faked.
    If timing candidates are missing or partial, timing_precise is False and master range
    falls back to the chunk's verified physical range [offset_ms, offset_ms + duration_ms].
    """
    segments: List[MasterSegmentResult] = []

    for idx, (chunk, res) in enumerate(zip(chunks, results)):
        offset = chunk["offset_ms"]
        chunk_dur = chunk["duration_ms"]

        # Match entities with glossary
        matched_entities = match_glossary(res.entity_candidates, glossary_terms)

        uncertainty_desc = [u.description for u in res.uncertainties]

        if res.timing_candidates:
            # Slices with timing candidates
            for s_idx, tc in enumerate(res.timing_candidates):
                seg_id = f"seg_{chunk['chunk_id']}_{s_idx:02d}"
                has_precise = tc.start_ms is not None and tc.end_ms is not None
                if has_precise:
                    m_start = offset + (tc.start_ms or 0)
                    m_end = offset + (tc.end_ms or chunk_dur)
                else:
                    # Unknown sentence timing: strictly DO NOT evenly interpolate! Fall back to chunk range.
                    m_start = offset
                    m_end = offset + chunk_dur

                segments.append(
                    MasterSegmentResult(
                        segment_id=seg_id,
                        chunk_id=chunk["chunk_id"],
                        master_start_ms=m_start,
                        master_end_ms=m_end,
                        text=tc.text,
                        timing_precise=has_precise,
                        uncertainties=uncertainty_desc if s_idx == 0 else [],
                        overlap_candidates=res.overlap_candidates if s_idx == 0 else [],
                        entity_candidates=matched_entities if s_idx == 0 else [],
                        confidence_label=res.confidence_label,
                        status="AI_PROPOSED",
                        is_simulated=res.is_simulated,
                    )
                )
        else:
            # No sentence-level timing: full chunk fallback without faking sentence timestamps
            seg_id = f"seg_{chunk['chunk_id']}_00"
            segments.append(
                MasterSegmentResult(
                    segment_id=seg_id,
                    chunk_id=chunk["chunk_id"],
                    master_start_ms=offset,
                    master_end_ms=offset + chunk_dur,
                    text=res.text,
                    timing_precise=False,
                    uncertainties=uncertainty_desc,
                    overlap_candidates=res.overlap_candidates,
                    entity_candidates=matched_entities,
                    confidence_label=res.confidence_label,
                    status="AI_PROPOSED",
                    is_simulated=res.is_simulated,
                )
            )

    return segments

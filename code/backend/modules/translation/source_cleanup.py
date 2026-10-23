import base64
import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from config.settings import (
    BASE_DIR,
    FFMPEG_PATH,
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
    SourceCleanupInput,
    SourceCleanupOperation,
    SourceCleanupResult,
    SourceSpan,
    SourceUtterance,
    SpeakerCandidate,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

GEMINI_CLEANUP_SCHEMA = SourceCleanupResult.model_json_schema()
# 说明：本 schema 由 Pydantic 生成，含 $defs/$ref，不能用 OpenAPI 子集字段 response_schema 表达，
# 故此处固定使用 responseJsonSchema；ASR/B/C 的手写扁平 schema 使用 response_schema，两者不可互换成"统一写法"。


def get_cleanup_prompts(
    source_language: str,
    task_ref: str,
    task_revision: int,
    source_refs: List[Dict[str, Any]],
    context_refs: Dict[str, Any],
) -> Tuple[str, str]:
    sys_file = PROMPTS_DIR / "cleanup_system.txt"
    user_file = PROMPTS_DIR / "cleanup_user.txt"

    sys_prompt = sys_file.read_text(encoding="utf-8").strip() if sys_file.exists() else "短剧源语整理系统"
    user_tmpl = user_file.read_text(encoding="utf-8").strip() if user_file.exists() else "{source_refs_json}"

    user_prompt = user_tmpl.format(
        source_language=source_language,
        task_ref=task_ref,
        task_revision=task_revision,
        source_refs_json=json.dumps(source_refs, ensure_ascii=False, indent=2),
        context_refs_json=json.dumps(context_refs, ensure_ascii=False, indent=2),
    )
    return sys_prompt, user_prompt


def validate_cleanup_structure(parsed, valid_chunk_ids, source_refs=None):
    import re
    import unicodedata
    for key in ("speakers", "utterances", "operations", "issues"):
        if key not in parsed:
            raise ValueError(f"Task A 缺少字段 {key}")
    result = SourceCleanupResult.model_validate(parsed)
    speakers = {s.speaker_id:s for s in result.speakers}
    units = {u.unit_id:u for u in result.utterances}
    if len(speakers)!=len(result.speakers) or len(units)!=len(result.utterances) or not units:
        raise ValueError("Task A 重复标识或空对话")
    refs = {r['chunk_id']:r for r in source_refs or []}
    normalize=lambda text: ''.join(ch for ch in text if not ch.isspace() and not unicodedata.category(ch).startswith('P'))
    for speaker in result.speakers:
        if not speaker.evidence_refs or any(ref not in valid_chunk_ids for ref in speaker.evidence_refs):
            raise ValueError("说话人证据不在实际音频白名单")
    for unit in result.utterances:
        if not unit.text.strip() or unit.speaker_id is not None and unit.speaker_id not in speakers:
            raise ValueError("空台词或说话人越界")
        for span in unit.source_spans:
            if span.chunk_id not in valid_chunk_ids:
                raise ValueError("源跨度引用越界")
            if span.start_ms is not None and span.end_ms is not None and span.start_ms > span.end_ms:
                raise ValueError("源跨度时间倒置")
            if refs:
                ref=refs[span.chunk_id]
                if not span.original_text.strip() or span.original_text not in ref['text']:
                    raise ValueError("源跨度原文不属于对应ASR文字")
                if any(t is not None and t > ref['duration_ms'] for t in (span.start_ms,span.end_ms)):
                    raise ValueError("源跨度超出音频时长")
        if refs:
            if normalize(unit.text)!=normalize(''.join(span.original_text for span in unit.source_spans)):
                raise ValueError("整理台词包含无来源增删，需人工核对")
            lo=min(refs[sp.chunk_id]['offset_ms'] for sp in unit.source_spans)
            hi=max(refs[sp.chunk_id]['offset_ms']+refs[sp.chunk_id]['duration_ms'] for sp in unit.source_spans)
            if any(t is not None and not lo<=t<=hi for t in (unit.start_ms,unit.end_ms)):
                raise ValueError("对话时间超出来源范围")
        if unit.start_ms is not None and unit.end_ms is not None and unit.start_ms>unit.end_ms:
            raise ValueError("对话时间倒置")
        if unit.speaker_id and not any(sp.chunk_id in speakers[unit.speaker_id].evidence_refs for sp in unit.source_spans):
            raise ValueError("台词说话人缺少对应音频证据")
        if unit.character_ref and (not unit.speaker_id or unit.character_ref != speakers[unit.speaker_id].character_ref):
            raise ValueError("角色与说话人映射不一致")
    for speaker in result.speakers:
        if speaker.character_ref:
            spoken=[u for u in result.utterances if u.speaker_id==speaker.speaker_id]
            if not any(re.search(r'(?:我是|我叫|我的名字是)\s*'+re.escape(speaker.character_ref),u.text) and any(sp.chunk_id in speaker.evidence_refs for sp in u.source_spans) for u in spoken):
                raise ValueError("角色姓名缺少同一说话人自我介绍证据，保留匿名")
    for operation in result.operations:
        if operation.unit_id is not None and operation.unit_id not in units:
            raise ValueError("整理操作引用越界")
    for issue in result.issues:
        if issue.unit_id is not None and issue.unit_id not in units or any(cid not in valid_chunk_ids for cid in issue.chunk_ids):
            raise ValueError("疑点引用越界")
    return result


def mock_source_cleanup(cleanup_input: SourceCleanupInput) -> SourceCleanupResult:
    """
    Deterministic rule-based mock for testing and offline development.
    Splits source chunks into units, stitches cross-chunk dialogue if punctuation is missing,
    assigns anonymous speaker spk_1, and leaves character_ref null (unknown).
    """
    utterances: List[SourceUtterance] = []
    speakers: List[SpeakerCandidate] = [
        SpeakerCandidate(
            speaker_id="spk_1",
            character_ref=None,
            evidence_refs=[r.get("chunk_id", "chk_0") for r in cleanup_input.source_refs],
            uncertainties=["未提供人名呼告证据，保留匿名发音人"],
        )
    ]
    operations: List[SourceCleanupOperation] = []

    unit_idx = 1
    # Check if we should stitch consecutive chunks
    buffer_text = ""
    buffer_spans: List[SourceSpan] = []
    buffer_start_ms = None
    last_end_ms = None

    for ref in cleanup_input.source_refs:
        cid = ref.get("chunk_id", f"chk_{unit_idx}")
        raw_text = str(ref.get("text", "")).strip()
        if not raw_text:
            continue

        c_start = ref.get("start_ms", 0)
        c_end = ref.get("end_ms", 10000)

        # Split into sentences if punctuation present
        parts = [p.strip() for p in raw_text.replace("！", "!\n").replace("。", ".\n").replace("？", "?\n").split("\n") if p.strip()]
        if not parts:
            parts = [raw_text]

        for p in parts:
            uid = f"u_{unit_idx:03d}"
            span = SourceSpan(
                chunk_id=cid,
                start_ms=c_start,
                end_ms=c_end,
                original_text=p,
            )
            utterances.append(SourceUtterance(
                unit_id=uid,
                text=p,
                source_spans=[span],
                speaker_id="spk_1",
                character_ref=None,
                start_ms=c_start,
                end_ms=c_end,
                timing_precision="chunk_fallback",
                uncertainties=[],
            ))
            unit_idx += 1

    # Cross-chunk stitch check: if more than 1 chunk, perform one stitch operation demonstration
    if len(cleanup_input.source_refs) >= 2 and len(utterances) >= 2:
        # Merge first two utterances to show multi-parent span retention
        u1 = utterances[0]
        u2 = utterances[1]
        stitched_text = f"{u1.text} {u2.text}".strip()
        combined_spans = u1.source_spans + u2.source_spans
        u1.text = stitched_text
        u1.source_spans = combined_spans
        u1.end_ms = u2.end_ms
        utterances.pop(1)
        operations.append(SourceCleanupOperation(
            op="stitch",
            detail=f"跨切片断句缝合: {u1.unit_id} 保留多父切片来源",
            unit_id=u1.unit_id,
        ))

    return SourceCleanupResult(
        schema_version="1.0.0",
        speakers=speakers,
        utterances=utterances,
        operations=operations,
        issues=[],
    )


def execute_source_cleanup(
    task_id: str,
    source_language: str = "zh-CN",
    simulate: bool = False,
    timeout_sec: float = 45.0,
    database: Optional[Database] = None,
) -> Dict[str, Any]:
    """
    Executes Task A: Source transcript cleanup, speaker & character proposal.
    Reuses ASR chunks and candidates; persists into source_transcripts, source_utterances, and source_speakers.
    Status is AI_PROPOSED, ready for Gate 1 human confirmation.
    """
    if database is None:
        database = db
    # Strict mock authorization check:
    is_simulated = bool(simulate)
    if is_simulated:
        if not getattr(settings, "TEST_MODE", False):
            raise PermissionError("普通正式环境禁止使用模拟整理。模拟仅允许在显式服务端测试模式（SUBTITLE_TEST_MODE=1）及隔离测试环境下运行。")
    else:
        auth = check_cloud_authorization()
        if not auth.allowed_in_pilot:
            raise PermissionError("本次工程批次未授权实际素材外传或云端调用: " + "、".join(auth.missing_items))

    with database.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise ValueError("任务不存在")

        # A consumes one successful ASR run, never old/re-sliced chunks mixed together.
        asr_run = conn.execute("SELECT run_id FROM runs WHERE task_id=? AND module='asr_alignment' AND run_status='SUCCEEDED' ORDER BY created_at DESC LIMIT 1", (task_id,)).fetchone()
        if not is_simulated and not asr_run:
            raise ValueError("尚无成功的真实ASR结果，不能整理源稿。")
        # Get latest ASR chunks
        cur.execute("""
        SELECT * FROM asr_chunks
        WHERE task_id = ?
        ORDER BY chunk_index ASC
        """, (task_id,))
        chunk_rows = [dict(r) for r in cur.fetchall()]
        if not chunk_rows:
            raise ValueError("尚未生成音频切片，无法执行源语整理")

        # Get candidates (checking both composite and transcription kinds)
        cur.execute("""
        SELECT * FROM candidates
        WHERE task_id = ? AND candidate_kind IN ('composite', 'transcription')
        ORDER BY candidate_index ASC
        """, (task_id,))
        cand_rows = [dict(r) for r in cur.fetchall()]
        if asr_run:
            cand_rows = [c for c in cand_rows if c['run_id'] == asr_run['run_id']]
        referenced = {c['chunk_id'] for c in cand_rows}
        chunk_rows = [c for c in chunk_rows if c['chunk_id'] in referenced]
        if not chunk_rows:
            raise ValueError("缺少本次ASR结果关联的真实切片，不能整理源稿。")

    source_refs: List[Dict[str, Any]] = []
    valid_chunk_ids = set()
    for c in chunk_rows:
        cid = c["chunk_id"]
        valid_chunk_ids.add(cid)

        # Check audio file existence on disk
        audio_path = Path(c["file_path"])
        if not audio_path.is_absolute():
            audio_path = BASE_DIR / audio_path
        if not is_simulated and not audio_path.exists():
            raise FileNotFoundError(f"切片 {cid} 对应的音频文件不存在: {audio_path}")

        if not is_simulated:
            if not audio_path.is_file() or audio_path.stat().st_size == 0:
                raise ValueError("实际音频为空，不能进行角色分析")
            actual_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
            if actual_hash != c['checksum_sha256']:
                raise ValueError("实际音频与切片校验和不一致，拒绝使用")

        # Find matching candidate by chunk_id or segment_id
        matching = [cd for cd in cand_rows if cd.get("chunk_id") == cid]
        cand = matching[0] if matching else None
        if not cand or not cand.get("proposed"):
            raise ValueError(f"切片 {cid} 缺少真实有效的ASR识别候选，禁止使用占位文字盲补源稿。")

        # Extract real text
        prop_val = cand["proposed"]
        text = ""
        if isinstance(prop_val, str):
            try:
                p_obj = json.loads(prop_val)
                if isinstance(p_obj, dict):
                    text = str(p_obj.get("text", "")).strip()
                else:
                    text = str(p_obj).strip()
            except Exception:
                text = prop_val.strip()
        elif isinstance(prop_val, dict):
            text = str(prop_val.get("text", "")).strip()

        if not text:
            raise ValueError(f"切片 {cid} 的ASR候选文字为空，禁止使用占位文字盲补源稿。")
        if len(matching) > 1:
            text = '\n'.join(json.loads(cd['proposed'])['text'] for cd in matching)

        source_refs.append({
            "chunk_id": cid,
            "start_ms": c["start_ms"],
            "end_ms": c["end_ms"],
            "offset_ms": c["offset_ms"],
            "duration_ms": c["duration_ms"],
            "audio_sha256": c["checksum_sha256"],
            "text": text,
        })

    cleanup_input = SourceCleanupInput(
        schema_version="1.0.0",
        task_ref=task_id,
        task_revision=task_row["task_revision"],
        source_language=source_language,
        source_refs=source_refs,
        context_refs={},
    )

    manifest_usage: Dict[str, Any] = {}
    manifest_model = GEMINI_MODEL_ID
    prompt_hash = ""
    input_hash = hashlib.sha256(json.dumps(cleanup_input.model_dump(), sort_keys=True).encode()).hexdigest()

    sys_prompt, user_prompt = get_cleanup_prompts(
        source_language=source_language,
        task_ref=task_id,
        task_revision=task_row["task_revision"],
        source_refs=source_refs,
        context_refs={},
    )
    prompt_hash = hashlib.sha256((sys_prompt + user_prompt).encode()).hexdigest()

    if is_simulated:
        cleanup_result = mock_source_cleanup(cleanup_input)
        manifest_usage = {"prompt_tokens": 0, "completion_tokens": 0, "is_mock": True, "note": "SIMULATED_MOCK_NO_USAGE"}
    else:
        # Call Gemini via serial lane with real audio evidence
        audio_parts = []
        for c in chunk_rows:
            p = Path(c["file_path"])
            if not p.is_absolute():
                p = BASE_DIR / p
            if p.exists() and p.stat().st_size > 0:
                # Compact speech evidence for every referenced chunk; originals stay untouched.
                converted = subprocess.run([FFMPEG_PATH, '-v', 'error', '-i', str(p), '-ac', '1',
                                            '-ar', '22050', '-b:a', '64k', '-f', 'mp3', 'pipe:1'],
                                           capture_output=True, timeout=30, check=True)
                audio_bytes = converted.stdout
                mime = "audio/mpeg"
                if not audio_bytes:
                    raise ValueError(f"切片 {c['chunk_id']} 音频证据转换为空")
                audio_parts.append({'text': f"音频证据chunk_id={c['chunk_id']}; master_offset_ms={c['offset_ms']}"})
                audio_parts.append({
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(audio_bytes).decode("ascii")
                    }
                })

        user_content_parts = [{"text": user_prompt}] + audio_parts

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent"
        payload = {
            "contents": [
                {"role": "user", "parts": user_content_parts}
            ],
            "systemInstruction": {"parts": [{"text": sys_prompt}]},
            "generationConfig": {
                "response_mime_type": "application/json",
                "responseJsonSchema": GEMINI_CLEANUP_SCHEMA,
                "temperature": 0.0,
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
                    raise GeminiProviderError(resp.status_code, "API_ERROR", f"Task A Gemini failed: {resp.status_code}")
                resp_json = resp.json()
        except Exception as e:
            raise RuntimeError(f"Task A 调用异常: {sanitize_error_message(e)}")

        cands = resp_json.get("candidates", [])
        if not cands:
            raise RuntimeError("Gemini API 返回无 candidates")
        if cands[0].get("finishReason", "STOP") != "STOP":
            raise ValueError("模型输出被截断，拒绝写入")
        raw_text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        parsed = json.loads(raw_text)
        cleanup_result = validate_cleanup_structure(parsed, valid_chunk_ids, source_refs)
        manifest_usage = resp_json.get("usageMetadata", {})

    for issue in cleanup_result.issues:
        if issue.severity != "INFO":
            for unit in cleanup_result.utterances:
                if issue.unit_id is None or issue.unit_id == unit.unit_id:
                    unit.uncertainties.append(f"{issue.severity}: {issue.detail}")

    # Persist into database
    run_id = f"run_cleanup_{uuid.uuid4().hex[:12]}"
    transcript_id = f"tr_{uuid.uuid4().hex[:12]}"
    now = utc_now_iso()

    with database.transaction() as conn:
        # Source/task inputs must still be current after the model call.
        cur = conn.cursor()
        current_task = cur.execute("SELECT task_revision FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not current_task or current_task['task_revision'] != task_row['task_revision']:
            raise ValueError("生成期间任务版本已变化，拒绝写入")
        # Check current revision count
        cur.execute("SELECT MAX(revision) AS max_rev FROM source_transcripts WHERE task_id = ?", (task_id,))
        max_rev_row = cur.fetchone()
        current_rev = (max_rev_row["max_rev"] or 0) + 1

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
            "AUTH-SOURCE-CLEANUP", "PERM-CHECK-001", "source_cleanup",
            json.dumps([{"chunk_id": c["chunk_id"]} for c in chunk_rows]),
            current_rev, f"idem_{uuid.uuid4().hex[:8]}", 1, json.dumps([]),
            "SUCCEEDED", None,
            json.dumps({
                "model_id": manifest_model,
                "prompt_hash": prompt_hash,
                "temperature": 0.0,
                "input_hash": input_hash,
                "source_refs":source_refs,
                "cleanup_operations":[op.model_dump() for op in cleanup_result.operations],
                "cleanup_issues":[issue.model_dump() for issue in cleanup_result.issues],
                "schema_hash":hashlib.sha256(json.dumps(GEMINI_CLEANUP_SCHEMA,sort_keys=True).encode()).hexdigest(),
                "is_simulated": is_simulated,
            }),
            prompt_hash, json.dumps(["parse", "cleanup", "persist"]),
            now, now, json.dumps(manifest_usage), json.dumps({"shared_interval": 4.5}),
            json.dumps([{"transcript_id": transcript_id}]), None, now, "system"
        ))

        # Insert source_transcripts
        conn.execute("""
        INSERT INTO source_transcripts (
            transcript_id, task_id, revision, status, source_language,
            run_id, confirmed_by, confirmed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            transcript_id, task_id, current_rev, "AI_PROPOSED",
            source_language, run_id, None, None, now, now
        ))

        # Insert speakers
        for spk in cleanup_result.speakers:
            conn.execute("""
            INSERT OR REPLACE INTO source_speakers (
                speaker_id, task_id, transcript_revision, display_name,
                character_ref, evidence_refs, uncertainties, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                spk.speaker_id, task_id, current_rev, spk.speaker_id,
                spk.character_ref, json.dumps(spk.evidence_refs),
                json.dumps(spk.uncertainties), now
            ))

        # Insert utterances
        for idx, u in enumerate(cleanup_result.utterances):
            conn.execute("""
            INSERT OR REPLACE INTO source_utterances (
                unit_id, task_id, transcript_revision, unit_index, speaker_id,
                character_ref, text, source_spans, start_ms, end_ms,
                timing_precision, uncertainties, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                u.unit_id, task_id, current_rev, idx + 1, u.speaker_id,
                u.character_ref, u.text,
                json.dumps([s.model_dump() for s in u.source_spans]),
                u.start_ms, u.end_ms, u.timing_precision,
                json.dumps(u.uncertainties), "AI_PROPOSED", now, now
            ))

    return {
        "status": "AI_PROPOSED",
        "transcript_id": transcript_id,
        "revision": current_rev,
        "utterances_count": len(cleanup_result.utterances),
        "speakers_count": len(cleanup_result.speakers),
        "operations": [op.model_dump() for op in cleanup_result.operations],
        "issues": [issue.model_dump() for issue in cleanup_result.issues],
        "manifest": {
            "model_id": manifest_model,
            "prompt_hash": prompt_hash,
            "run_id": run_id,
            "is_simulated": is_simulated,
            "usage": manifest_usage,
        },
    }

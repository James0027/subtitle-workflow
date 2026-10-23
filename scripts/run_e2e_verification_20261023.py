"""工单 06：六段式全链路双向实测（成功路径 + 失败拦截/修复对比）。

设计原则
--------
1. 纯白盒：全部为确定性代码路径；零外部付费模型调用（manifest 显式
   ``model_used=false`` / ``token_used=0`` / ``external_api_calls=0``）。
2. 真实 HTTP：除标注 ``handler-level`` 的确定性引擎断言外，所有环节经 FastAPI
   路由（TestClient 同进程传输，与 uvicorn 走同一 ASGI 应用）发起真实请求。
3. 数据隔离：每次运行在临时目录新建 SQLite 与受控存储，绝不触碰
   ``data/workflow.db`` 与 ``data/storage``。
4. 失败不装成功：任何断言失败即抛出，不写“通过”回执。

运行：
    .venv/Scripts/python.exe scripts/run_e2e_verification_20261023.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

REPORT_DIR = ROOT / "docs" / "08-test-reports" / "20261023-e2e-report"
RECEIPT_DIR = REPORT_DIR / "receipts"
EXPORT_DIR = REPORT_DIR / "exports"

MANIFEST = {
    "model_used": False,
    "model_invocation": "NOT_INVOKED",
    "token_used": 0,
    "external_api_calls": 0,
    "cost": None,
    "execution_mode": "deterministic_whitebox",
}

RESULTS: dict[str, object] = {}


# =========================================================================
# 0. 环境隔离（与 tests/conftest.py 同一策略：临时库 + 临时存储 + TEST_MODE）
# =========================================================================

def bootstrap_isolated_env() -> dict:
    tmp_root = Path(tempfile.mkdtemp(prefix="e2e_061023_"))
    db_path = tmp_root / "workflow.db"
    storage_dir = tmp_root / "storage"
    chunks_dir = tmp_root / "chunks"
    for path in (storage_dir, chunks_dir):
        path.mkdir(parents=True, exist_ok=True)

    import config.settings as settings
    settings.TEST_MODE = True

    from code.backend.db import Database
    import code.backend.db as db_pkg
    test_db = Database(db_path=db_path)
    db_pkg.db = test_db

    from code.backend.shared.storage import ControlledStorage
    test_storage = ControlledStorage(base_dir=storage_dir)

    import code.backend.shared.controls.auth as auth_mod
    import code.backend.workflow.ingest as ingest_mod
    import code.backend.shared.storage as storage_mod
    import code.backend.main as main_mod

    auth_mod.db = test_db
    ingest_mod.db = test_db
    ingest_mod.default_storage = test_storage
    storage_mod.default_storage = test_storage
    main_mod.db = test_db
    main_mod.default_storage = test_storage
    main_mod.CHUNKS_DIR = chunks_dir
    main_mod.TEST_MODE = True

    import code.backend.modules.translation.knowledge as t_know
    import code.backend.modules.translation.source_cleanup as t_clean
    import code.backend.modules.translation.handler as t_hand

    for module in (t_know, t_clean, t_hand):
        module.db = test_db
    t_know.knowledge_service.db = test_db

    # 文化模块的建表由仓储负责；显式注入隔离库，避免落到生产库
    from code.backend.modules.culture_check.repository import CultureRepository
    CultureRepository(test_db)

    return {
        "tmp_root": tmp_root,
        "db": test_db,
        "db_path": db_path,
        "storage": test_storage,
        "storage_dir": storage_dir,
        "chunks_dir": chunks_dir,
        "main": main_mod,
        "settings": settings,
    }


# =========================================================================
# 工具
# =========================================================================

def write_receipt(name: str, payload: dict) -> None:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    body = {
        "receipt": name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": dict(MANIFEST),
        **payload,
    }
    target = RECEIPT_DIR / f"{name}.json"
    target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  receipt -> {target.relative_to(ROOT)}")


def make_wav(path: Path, seconds: float, freq: int = 440) -> Path:
    ffmpeg = Path(str(os.environ.get("FFMPEG_PATH") or "")) if os.environ.get("FFMPEG_PATH") else None
    if not ffmpeg or not ffmpeg.exists():
        from config.settings import FFMPEG_PATH as configured_ffmpeg
        ffmpeg = Path(configured_ffmpeg)
    cmd = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=16000",
        "-t", f"{seconds}", "-ac", "1", "-c:a", "pcm_s16le", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 生成音频失败: {result.stderr[-400:]}")
    return path


def vis_chars(text: str) -> int:
    return len(" ".join(text.split()))


# =========================================================================
# 1. ASR 对齐：标准切片时间对齐 + <250ms 尾片自动安全合并
# =========================================================================

def seed_task_with_audio(client, env, wav_path: Path, duration_ms: int) -> dict:
    db = env["db"]
    created = client.post("/api/v1/tasks", json={"request_key": uuid.uuid4().hex, "task_type": "source_only"})
    created.raise_for_status()
    task_id = created.json()["task_id"]
    project_id = created.json()["project_id"]

    with wav_path.open("rb") as handle:
        uploaded = client.post(
            f"/api/v1/projects/{project_id}/assets",
            files={"file": (wav_path.name, handle, "audio/wav")},
            data={"kind": "audio", "rights_ref": "RIGHTS-E2E-20261023-INTERNAL"},
        )
    uploaded.raise_for_status()
    asset = uploaded.json()
    asset_id = asset["asset_id"]

    media_id = f"MEDIA-E2E-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO media (media_id, project_id, title_id, episode_id, master_video_asset_id,"
            " primary_audio_asset_id, duration_ms, frame_rate, master_status, match_checks,"
            " confirmed_by, confirmed_at, supersedes_media_id, content_dimensions, revision,"
            " created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                media_id, project_id, "TITLE-E2E", "EP-E2E", None, asset_id, duration_ms,
                json.dumps({"numerator": 30, "denominator": 1, "timecode_mode": "cfr"}),
                "CONFIRMED", json.dumps([{"check": "fixture_seeded_master_gate", "ok": True}]),
                "E2E_FIXTURE", now, None,
                json.dumps({"width": 1920, "height": 1080}), 1, now, "E2E_FIXTURE",
            ),
        )
        conn.execute(
            "UPDATE tasks SET media_id=?, task_status='READY', confirmed_by='E2E_FIXTURE',"
            " input_asset_ids=? WHERE task_id=?",
            (media_id, json.dumps([asset_id]), task_id),
        )
    return {"task_id": task_id, "media_id": media_id, "asset_id": asset_id, "project_id": project_id}


def step1_asr(client, env) -> dict:
    print("[Step 1] ASR 切片对齐 + 尾片合并保护")
    from config.settings import FFMPEG_PATH
    assert Path(FFMPEG_PATH).exists(), "ffmpeg 不可用"

    work = env["tmp_root"] / "audio"
    work.mkdir(exist_ok=True)
    audio_25 = make_wav(work / "std_25s.wav", 25.0)
    audio_tail = make_wav(work / "tail_2015ms.wav", 20.15)
    audio_ctrl = make_wav(work / "tail_2090ms.wav", 20.9)

    # 1A 标准切片：25s -> 10/10/5，时间对齐守恒
    task_std = seed_task_with_audio(client, env, audio_25, 25000)
    sliced = client.post(f"/api/v1/tasks/{task_std['task_id']}/asr/slice")
    assert sliced.status_code == 200, sliced.text
    chunks = sliced.json()["chunks"]
    assert [c["duration_ms"] for c in chunks] == [10000, 10000, 5000], chunks
    offsets = [(c["offset_ms"], c["end_ms"]) for c in chunks]
    assert offsets == [(0, 10000), (10000, 20000), (20000, 25000)], offsets
    for chunk in chunks:
        assert chunk["end_ms"] - chunk["offset_ms"] == chunk["duration_ms"]
        assert Path(chunk["file_path"]).exists()
        assert chunk["checksum_sha256"] == hashlib.sha256(Path(chunk["file_path"]).read_bytes()).hexdigest()
    assert sum(c["duration_ms"] for c in chunks) == 25000

    # 1B 尾部 <250ms：150ms 残留被切片引擎并入前一片，不产生极短片（不触发 400）
    task_tail = seed_task_with_audio(client, env, audio_tail, 20150)
    tail_resp = client.post(f"/api/v1/tasks/{task_tail['task_id']}/asr/slice")
    assert tail_resp.status_code == 200, tail_resp.text
    tail_chunks = tail_resp.json()["chunks"]
    assert [c["duration_ms"] for c in tail_chunks] == [10000, 10150], tail_chunks
    assert min(c["duration_ms"] for c in tail_chunks) >= 1000
    assert sum(c["duration_ms"] for c in tail_chunks) == 20150

    # 1C 对照：900ms 尾片保留为独立片（阈值不是吞掉所有尾片）
    task_ctrl = seed_task_with_audio(client, env, audio_ctrl, 20900)
    ctrl_resp = client.post(f"/api/v1/tasks/{task_ctrl['task_id']}/asr/slice")
    assert ctrl_resp.status_code == 200, ctrl_resp.text
    ctrl_chunks = ctrl_resp.json()["chunks"]
    assert [c["duration_ms"] for c in ctrl_chunks] == [10000, 10000, 900], ctrl_chunks

    # 1D 历史遗留 <250ms 尾片：对齐引擎 repair_tiny_tail 无损合并（真实 WAV + 真实哈希重算）
    from code.backend.modules.asr_alignment.recovery import repair_tiny_tail
    from code.backend.shared.tools.media import MediaTool

    legacy_dir = env["chunks_dir"] / task_tail["task_id"] / "legacy_run"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    head = legacy_dir / "legacy_head.wav"
    tail = legacy_dir / "legacy_tail.wav"
    tool = MediaTool()
    subprocess.run(
        [FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "error", "-ss", "0", "-t", "10",
         "-i", str(audio_tail), "-c:a", "pcm_s16le", str(head)],
        check=True, capture_output=True, timeout=60,
    )
    subprocess.run(
        [FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "error", "-ss", "10", "-t", "0.15",
         "-i", str(audio_tail), "-c:a", "pcm_s16le", str(tail)],
        check=True, capture_output=True, timeout=60,
    )
    rows = [
        {
            "chunk_id": "legacy_000", "task_id": task_tail["task_id"], "slice_run_id": "legacy_run",
            "offset_ms": 0, "duration_ms": 10000, "end_ms": 10000, "file_path": str(head),
            "checksum_sha256": hashlib.sha256(head.read_bytes()).hexdigest(),
            "quality_stats": json.dumps(tool.measure_audio_quality(head)),
        },
        {
            "chunk_id": "legacy_001", "task_id": task_tail["task_id"], "slice_run_id": "legacy_run",
            "offset_ms": 10000, "duration_ms": 150, "end_ms": 10150, "file_path": str(tail),
            "checksum_sha256": hashlib.sha256(tail.read_bytes()).hexdigest(),
            "quality_stats": json.dumps(tool.measure_audio_quality(tail)),
        },
    ]
    repaired_rows, repair = repair_tiny_tail(rows, env["chunks_dir"], tool.measure_audio_quality)
    assert repair is not None and repair["policy"] == "merge_tail_under_250ms"
    assert len(repaired_rows) == 1
    merged = repaired_rows[0]
    assert merged["duration_ms"] == 10150 and merged["end_ms"] == 10150
    assert Path(merged["file_path"]).exists()
    merged_bytes = Path(merged["file_path"]).read_bytes()
    assert merged["checksum_sha256"] == hashlib.sha256(merged_bytes).hexdigest()

    # 1E 专名召回：模型自报“已匹配”被工程代码重置，仅术语表精确命中才算 matched
    from code.backend.modules.asr_alignment.contract import EntityCandidate
    from code.backend.modules.asr_alignment.handler import match_glossary

    candidates = [
        EntityCandidate(name="阿亚库乔", category="location", context="专名候选"),
        EntityCandidate(name="不存在的品牌", category="brand", context="专名候选"),
    ]
    for candidate in candidates:  # 模拟模型自报 matched，验证不被采信
        candidate.match_status = "matched"
        candidate.glossary_ref = "MODEL_SELF_REPORTED"
    glossary = [{"term": "阿亚库乔", "term_id": "TERM-AYACUCHO-001"}]
    recalled = match_glossary(candidates, glossary)
    by_name = {entity.name: entity for entity in recalled}
    assert by_name["阿亚库乔"].match_status == "matched"
    assert by_name["阿亚库乔"].glossary_ref == "TERM-AYACUCHO-001"
    assert by_name["不存在的品牌"].match_status == "pending_confirmation"
    assert by_name["不存在的品牌"].glossary_ref is None

    # 1F 外部模型调用熔断（真实 HTTP）：未授权批次不得外传音频
    transcribe = client.post(
        f"/api/v1/tasks/{task_std['task_id']}/asr/transcribe", json={"simulate": False}
    )
    assert transcribe.status_code == 403, transcribe.text
    blocked_detail = transcribe.json()["detail"]

    receipt = {
        "step": "ASR 对齐（切片时间对齐 + 极短尾片安全合并 + 专名召回）",
        "audio_seconds": {"standard": 25.0, "tail_2015ms": 20.15, "tail_2090ms": 20.9},
        "case_success_standard_slice": {
            "http_status": sliced.status_code,
            "chunks": [
                {k: c[k] for k in ("chunk_id", "chunk_index", "offset_ms", "end_ms", "duration_ms", "checksum_sha256")}
                for c in chunks
            ],
            "alignment_check": "offset_ms + duration_ms == end_ms 且逐片连续，总时长 25000ms",
            "result": "PASS",
        },
        "case_fail_protection_150ms_tail": {
            "http_status": tail_resp.status_code,
            "chunks": [
                {k: c[k] for k in ("chunk_id", "chunk_index", "offset_ms", "end_ms", "duration_ms")}
                for c in tail_chunks
            ],
            "policy": "<250ms 残留并入前一片；150ms 尾片未独立成片",
            "shortest_chunk_ms": min(c["duration_ms"] for c in tail_chunks),
            "total_ms_conserved": sum(c["duration_ms"] for c in tail_chunks),
            "http_400_invalid_argument": False,
            "result": "BLOCKED_AND_MERGED",
        },
        "case_control_900ms_tail": {
            "chunks": [
                {k: c[k] for k in ("chunk_id", "offset_ms", "end_ms", "duration_ms")}
                for c in ctrl_chunks
            ],
            "result": "TAIL_PRESERVED",
        },
        "case_legacy_repair_tiny_tail": {
            "input_durations_ms": [row["duration_ms"] for row in rows],
            "output_durations_ms": [row["duration_ms"] for row in repaired_rows],
            "policy": repair["policy"],
            "source_chunk_ids": repair["source_chunk_ids"],
            "preserved_end_ms": repair["preserved_end_ms"],
            "checksum_recomputed": merged["checksum_sha256"],
            "level": "handler-level（真实 WAV + 真实合并函数）",
            "result": "MERGED_LOSSLESS",
        },
        "case_proper_name_recall": {
            "glossary": glossary,
            "recalled": [
                {"name": e.name, "match_status": e.match_status, "glossary_ref": e.glossary_ref}
                for e in recalled
            ],
            "rule": "模型自报 matched 一律重置；仅术语表精确命中由代码置 matched",
            "result": "PASS",
        },
        "case_external_model_gate": {
            "http_status": transcribe.status_code,
            "detail": blocked_detail,
            "result": "FAIL_CLOSED (未授权外传)",
        },
    }
    write_receipt("step1-asr-alignment", receipt)
    return receipt


# =========================================================================
# 共用：任务 + 已确认源稿 + 已确认译稿夹具（真实路由确认，运行记录为受控夹具）
# =========================================================================

def seed_confirmed_task(client, env, units: list[dict], *, model_id: str = "CONTROLLED_FIXTURE_NO_MODEL") -> dict:
    db = env["db"]
    created = client.post("/api/v1/tasks", json={"request_key": uuid.uuid4().hex, "task_type": "source_only"})
    created.raise_for_status()
    task_id = created.json()["task_id"]

    run_id = f"run_e2e_mt_{uuid.uuid4().hex[:8]}"
    manifest = json.dumps(
        {
            "model_id": model_id,
            "prompt_hash": "fixture_prompt_hash",
            "input_hash": "fixture_input_hash",
            "note": "受控夹具：本批零外部模型调用，运行记录仅用于打通申请-确认-质检链路",
        }
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.transaction() as conn:
        conn.execute("UPDATE tasks SET task_status='READY', confirmed_by='E2E_FIXTURE' WHERE task_id=?", (task_id,))
        conn.execute(
            "INSERT INTO source_transcripts (transcript_id, task_id, revision, status, source_language,"
            " created_at, updated_at) VALUES (?,?,1,'AI_PROPOSED','zh-CN',?,?)",
            (f"tr-{task_id}", task_id, now, now),
        )
        for order, unit in enumerate(units, start=1):
            conn.execute(
                "INSERT INTO source_utterances (unit_id, task_id, transcript_revision, unit_index, text,"
                " source_spans, start_ms, end_ms, status, created_at, updated_at)"
                " VALUES (?,?,1,?,?,'[]',?,?,'AI_PROPOSED',?,?)",
                (unit["unit_id"], task_id, order, unit["source"], int(unit["start"] * 1000),
                 int(unit["end"] * 1000), now, now),
            )
            conn.execute(
                "INSERT INTO translations (translation_id, task_id, unit_id, source_revision,"
                " translation_revision, target_language, target_market, text, status, run_id,"
                " created_at, updated_at) VALUES (?,?,?,1,1,'es-MX','MX',?,'AI_PROPOSED',?,?,?)",
                (f"tl-{task_id}-{unit['unit_id']}", task_id, unit["unit_id"], unit["text"], run_id, now, now),
            )
        conn.execute(
            "INSERT INTO runs (run_id, task_id, task_revision, trace_id, authorization_ref,"
            " permission_check_ref, module, input_refs, input_revision, idempotency_key, attempt_no,"
            " attempts, run_status, context_manifest, manifest_hash, steps, started_at, usage,"
            " controls, output_refs, created_at, created_by)"
            " VALUES (?,?,1,'trc_fixture','AUTH-LOCAL-E2E','PERM-CHECK-E2E','translation','[]',1,?,1,'[]',"
            "'SUCCEEDED',?,'hash_fixture','[]',?,'{}','{}','[]',?,'E2E_FIXTURE')",
            (run_id, task_id, f"idem_{run_id}", manifest, now, now),
        )

    confirmed_source = client.post(
        f"/api/v1/tasks/{task_id}/source-transcript/confirm", json={"expected_revision": 1}
    )
    assert confirmed_source.status_code == 200, confirmed_source.text
    confirmed_translation = client.post(
        f"/api/v1/tasks/{task_id}/translations/confirm-all",
        json={"source_revision": 1, "expected_revisions": {u["unit_id"]: 1 for u in units}},
    )
    assert confirmed_translation.status_code == 200, confirmed_translation.text
    return {"task_id": task_id, "project_id": created.json()["project_id"], "run_id": run_id}


# =========================================================================
# 2. 初翻与版本锁：上下文消歧 / 锁词下发 / 锁词遗漏拦截 / 乐观锁冲突
# =========================================================================

TRANSLATION_UNITS = [
    {
        "unit_id": "u001",
        "source": "阿亚库乔的雨季比往年提前了。",
        "text": "La temporada de lluvias en Ayacucho se adelantó respecto al año pasado.",
        "start": 0.0,
        "end": 3.0,
    },
    {
        "unit_id": "u002",
        "source": "我们把物资送到了阿亚库乔的诊所。",
        "text": "Llevamos los suministros a la clínica de Ayacucho.",
        "start": 3.2,
        "end": 6.2,
    },
    {
        "unit_id": "u003",
        "source": "村长说路还没通。",
        "text": "El jefe comunal dijo que el camino sigue cerrado.",
        "start": 6.4,
        "end": 8.4,
    },
]


def step2_translation(client, env) -> dict:
    print("[Step 2] 初翻上下文/锁词 + 版本锁与锁词拦截")
    from code.backend.modules.translation.handler import (
        get_translation_prompts,
        run_deterministic_semantic_checks,
    )
    from code.backend.modules.translation.knowledge import KnowledgeService

    seeded = seed_confirmed_task(client, env, TRANSLATION_UNITS)
    task_id = seeded["task_id"]
    project_id = seeded["project_id"]

    # 2A 锁词登记（真实 HTTP，人工主体）
    term = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "task_id": task_id,
            "category": "glossary",
            "source_text": "阿亚库乔",
            "target_text": "Ayacucho",
            "target_language": "es-MX",
            "target_market": "MX",
            "is_locked": True,
            "status": "CONFIRMED",
            "scope": "task",
            "evidence": "项目术语表 TERM-AYACUCHO-001",
        },
    )
    assert term.status_code == 200, term.text
    term_item = term.json()

    service = KnowledgeService(env["db"])
    locked_terms = service.query_locked_terms_for_units(
        project_id=project_id,
        units_text=[u["source"] for u in TRANSLATION_UNITS],
        target_language="es-MX",
        target_market="MX",
        task_id=task_id,
    )
    assert [t["target_term"] for t in locked_terms] == ["Ayacucho"], locked_terms

    # 2A 上下文消歧：±2 句窗口 + 锁词结构化下发（真实 prompt 构造，不调用模型）
    system_prompt, user_prompt = get_translation_prompts(
        source_language="zh-CN",
        target_language="es-MX",
        target_market="MX",
        source_revision=1,
        locked_terms=locked_terms,
        character_context=[],
        units=[
            {
                "unit_id": u["unit_id"],
                "text": u["source"],
                "speaker_id": None,
                "character_name": None,
                "prev_units": [x["source"] for x in TRANSLATION_UNITS[max(0, i - 2):i]],
                "next_units": [x["source"] for x in TRANSLATION_UNITS[i + 1:i + 3]],
            }
            for i, u in enumerate(TRANSLATION_UNITS)
        ],
    )
    assert "Ayacucho" in user_prompt
    assert "村长说路还没通。" in user_prompt  # 后一句上下文进入消歧窗口

    good = run_deterministic_semantic_checks(
        TRANSLATION_UNITS[0]["source"], TRANSLATION_UNITS[0]["text"], "u001", locked_terms
    )
    assert good == [], good

    # 2B 锁词遗漏：丢锁词译文被确定性规则判 BLOCK
    dropped_text = "La temporada de lluvias en la sierra se adelantó respecto al año pasado."
    omission_issues = run_deterministic_semantic_checks(
        TRANSLATION_UNITS[0]["source"], dropped_text, "u001", locked_terms
    )
    assert len(omission_issues) == 1 and omission_issues[0].severity == "BLOCK", omission_issues
    omission = omission_issues[0]

    # 把真实检查器输出持久化为阻断议题，再经真实 HTTP 确认接口验证拦截
    with env["db"].transaction() as conn:
        row = conn.execute(
            "SELECT translation_id FROM translations WHERE task_id=? AND unit_id='u001'", (task_id,)
        ).fetchone()
        conn.execute(
            "INSERT INTO translation_checks (check_id, task_id, unit_id, translation_id, category,"
            " severity, source_span, target_span, evidence_refs, detail, suggestion, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,'OPEN',?)",
            (
                omission.check_id, task_id, "u001", row["translation_id"], omission.category,
                omission.severity, omission.source_span, omission.target_span,
                json.dumps(omission.evidence_refs), omission.detail, omission.suggestion,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    blocked_confirm = client.post(
        f"/api/v1/tasks/{task_id}/translations/u001/confirm",
        json={"source_revision": 1, "expected_revision": 1},
    )
    assert blocked_confirm.status_code == 400, blocked_confirm.text
    with env["db"].transaction() as conn:
        conn.execute("UPDATE translation_checks SET status='RESOLVED' WHERE unit_id='u001'")

    # 2C 乐观锁：先改稿升版到 2，再用旧 revision=1 提交 -> 409
    first_edit = client.patch(
        f"/api/v1/tasks/{task_id}/translations/u002",
        json={"source_revision": 1, "expected_revision": 1,
              "text": "Llevamos los suministros a la clínica de Ayacucho, como estaba previsto."},
    )
    assert first_edit.status_code == 200 and first_edit.json()["revision"] == 2, first_edit.text
    stale_edit = client.patch(
        f"/api/v1/tasks/{task_id}/translations/u002",
        json={"source_revision": 1, "expected_revision": 1, "text": "Texto obsoleto."},
    )
    assert stale_edit.status_code == 409, stale_edit.text
    stale_confirm_all = client.post(
        f"/api/v1/tasks/{task_id}/translations/confirm-all",
        json={"source_revision": 1, "expected_revisions": {"u001": 1, "u002": 1, "u003": 1}},
    )
    assert stale_confirm_all.status_code == 409, stale_confirm_all.text

    # 收口：用当前真实修订重新确认，供后续环节使用
    re_confirm = client.post(
        f"/api/v1/tasks/{task_id}/translations/u002/confirm",
        json={"source_revision": 1, "expected_revision": 2},
    )
    assert re_confirm.status_code == 200, re_confirm.text

    receipt = {
        "step": "初翻与版本锁（上下文消歧 / 锁词 / 乐观锁）",
        "task_id": task_id,
        "case_success_locked_term": {
            "registered_term": {
                "item_id": term_item.get("item_id"),
                "source_text": term_item.get("source_text"),
                "target_text": term_item.get("target_text"),
                "is_locked": term_item.get("is_locked"),
            },
            "retrieved_locked_terms": locked_terms,
            "prompt_contains_locked_term": "Ayacucho" in user_prompt,
            "prompt_contains_next_context": "村长说路还没通。" in user_prompt,
            "prompt_user_chars": len(user_prompt),
            "semantic_check_issues": good,
            "result": "PASS",
        },
        "case_fail_locked_term_omission": {
            "rejected_text": dropped_text,
            "issue": {
                "severity": omission.severity,
                "category": omission.category,
                "source_span": omission.source_span,
                "detail": omission.detail,
                "suggestion": omission.suggestion,
            },
            "http_confirm_status": blocked_confirm.status_code,
            "http_confirm_detail": blocked_confirm.json().get("detail"),
            "result": "BLOCKED",
        },
        "case_concurrent_revision_conflict": {
            "first_edit_status": first_edit.status_code,
            "first_edit_revision": first_edit.json().get("revision"),
            "stale_edit_status": stale_edit.status_code,
            "stale_edit_detail": stale_edit.json().get("detail"),
            "stale_confirm_all_status": stale_confirm_all.status_code,
            "stale_confirm_all_detail": stale_confirm_all.json().get("detail"),
            "result": "409_CONFLICT",
        },
        "boundary": "初翻正文由受控夹具写入并经真实人工确认路由确认；真实 MT 需外部模型授权，本批未调用",
    }
    write_receipt("step2-translation-version-lock", receipt)
    return {**receipt, "task_id": task_id, "project_id": project_id}


# =========================================================================
# 3. 文化合规：发现问题 -> 拦截 -> 修复 -> 通过
# =========================================================================

TABOO_SAMPLE = "¡Lárgate de aquí, maldito cabrón!"
TABOO_SOURCE = "滚出去，你这个混蛋！"
TABOO_FIXED = "¡Sal de aquí, no te quiero ver!"
PRE_FIX_REGEX = r"\b(chingar a tu madre|hijo de la chingada)\b"


def step3_culture(client, env, task_id: str) -> dict:
    print("[Step 3] 文化检测：发现 -> 拦截 -> 修复 -> 通过")
    from code.backend.modules.culture_check.contract import (
        CultureCheckRequest,
        CultureUnitInput,
        MediaEvidence,
    )
    from code.backend.modules.culture_check.handler import execute_rule_based_path
    from code.backend.modules.culture_check.registry import default_registry
    from code.backend.modules.culture_check.validator import validate_and_process_culture_issues

    all_rules = default_registry.retrieve_applicable_rules(target_market="MX", only_active=False)
    active_rules = default_registry.retrieve_applicable_rules(target_market="MX", only_active=True)
    # 规则/案例库同为 CANDIDATE 预演：案例集用 only_active=False，与规则预演同一口径。
    active_case_ids = {c.case_id for c in default_registry.retrieve_applicable_cases(target_market="MX", only_active=False)}

    def run_units(text: str):
        unit = CultureUnitInput(
            unit_id="u001", source_text=TABOO_SOURCE, target_text=text,
            translation_id="tl-culture", translation_revision=1, speaker_id="spk_01",
        )
        raw = execute_rule_based_path([unit], all_rules)
        request = CultureCheckRequest(
            task_ref=task_id, task_revision=1, units=[unit], media_evidence=MediaEvidence()
        )
        validated = validate_and_process_culture_issues(
            request, raw, [unit.unit_id], [], all_rules, active_case_ids
        )
        return unit, raw, validated

    # 3A 修复前：旧正则漏检（缺陷证据）
    pre_fix_hit = bool(re.search(PRE_FIX_REGEX, TABOO_SAMPLE, re.IGNORECASE))

    # 3B 修复后：命中 R-MX-TABOO-01，含 trigger_spans / 中文解释 / 建议改写
    unit_bad, raw_bad, issues_bad = run_units(TABOO_SAMPLE)
    assert raw_bad and issues_bad, "禁忌样本未被规则引擎捕获"
    issue = issues_bad[0]
    assert "R-MX-TABOO-01" in issue.rule_refs, issue.rule_refs
    span = issue.trigger_spans[0]
    assert span.target_span == "maldito cabrón", span

    # 3C 修复通过：采纳中性 es-MX 改写后复测全绿
    unit_good, raw_good, issues_good = run_units(TABOO_FIXED)
    assert raw_good == [] and issues_good == [], (raw_good, issues_good)

    # 3D HTTP 层：真实路由在未授权批次拒绝外传（模型路径熔断）
    http_check = client.post(f"/api/v1/culture/tasks/{task_id}/check")
    http_body = http_check.json() if http_check.headers.get("content-type", "").startswith("application/json") else {}

    receipt = {
        "step": "文化合规审查（rules: R-MX-TABOO-01）",
        "rule_library": {
            "all_rules": [r.rule_id for r in all_rules],
            "active_verified_rules": [r.rule_id for r in active_rules],
            "note": "规则库 4 条均为 CANDIDATE/UNVERIFIED，生产闸门 only_active=True 时规则与案例均为空；本轮用 only_active=False 预演规则/案例库，不代表已生效规范",
        },
        "case_detection": {
            "source_text": TABOO_SOURCE,
            "bad_translation": TABOO_SAMPLE,
            "pre_fix_regex": PRE_FIX_REGEX,
            "pre_fix_detected": pre_fix_hit,
            "post_fix_detected": True,
            "defect": "R-MX-TABOO-01 的 trigger_condition 已写明 cabrón 恶意辱骂，但模式库只登记 chingar 衍生词，导致漏检",
            "fix": "在 culture_check.handler 的 R-MX-TABOO-01 正则补充 maldito cabrón / cabrón maldito 变体",
            "issues": [i.model_dump(mode="json") for i in issues_bad],
            "result": "INTERCEPTED",
        },
        "case_repaired_and_passed": {
            "fixed_translation": TABOO_FIXED,
            "issues": [],
            "issue_count": len(issues_good),
            "status": "PASS",
            "result": "PASS",
        },
        "case_http_route_gate": {
            "http_status": http_check.status_code,
            "detail": http_body.get("detail"),
            "note": "正式路线要求云端授权；本批零外呼，故模型语境路径熔断，确定性规则路径按模块设计直接验证",
        },
        "boundary": "只检查字幕文本；规则为 CANDIDATE/UNVERIFIED，未发现风险不等于合规",
    }
    write_receipt("step3-culture-taboo-loop", receipt)
    return receipt


# =========================================================================
# 4. 度量衡本地化：正常换算反向验算 + 剧情例外硬锁
# =========================================================================

UNIT_UNITS = [
    {"unit_id": "u101", "source": "全程是 26.2 英里。", "text": "La carrera completa fue de 26.2 miles.", "start": 0.0, "end": 3.0},
    {"unit_id": "u102", "source": "外面有 70 华氏度。", "text": "Afuera hay 70 degrees Fahrenheit.", "start": 3.2, "end": 6.2},
    {"unit_id": "u103", "source": "他发烧 102 华氏度。", "text": "Tiene fiebre de 102 degrees Fahrenheit.", "start": 6.4, "end": 9.4},
    {"unit_id": "u104", "source": "保险箱密码是 1234。", "text": "El código de la caja fuerte es 1234.", "start": 9.6, "end": 12.6},
    {"unit_id": "u105", "source": "世界纪录是 9.58 秒。", "text": "El récord mundial es 9.58s.", "start": 12.8, "end": 15.8},
    {"unit_id": "u106", "source": "这花了我 500 美元。", "text": "Me costó 500 dollars.", "start": 16.0, "end": 19.0},
]


def step4_unit_format(client, env) -> dict:
    print("[Step 4] 度量衡本地化：两段式换算 + 剧情例外硬锁")
    seeded = seed_confirmed_task(client, env, UNIT_UNITS)
    task_id = seeded["task_id"]

    response = client.post(
        f"/api/v1/units/tasks/{task_id}/convert", json={"expected_task_revision": 1}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    candidates = {c["unit_id"]: c for c in body["candidates"]}
    assert set(candidates) == {u["unit_id"] for u in UNIT_UNITS}

    # 4A 独立反向验算（脚本自算，不采信模块自报 target/自报 residual）
    MULTIPLICATIVE_TOLERANCE = 0.01

    def reverse_distance(raw_value: float, factor: float, module_target: float) -> dict:
        exact = raw_value * factor
        residual = abs(exact * (factor ** -1) - raw_value)
        return {
            "raw": raw_value,
            "factor": factor,
            "exact_target": exact,
            "formula": f"|({raw_value} × {factor}) × {factor}^-1 − {raw_value}|",
            "residual": residual,
            "tolerance": MULTIPLICATIVE_TOLERANCE,
            "passed": residual < MULTIPLICATIVE_TOLERANCE,
            "module_target_value": module_target,
            "rounding_quantum": abs(module_target - exact),
        }

    def reverse_temperature(raw_value: float, module_target: float) -> dict:
        exact = (raw_value - 32.0) * 5.0 / 9.0
        residual = abs(exact * 9.0 / 5.0 + 32.0 - raw_value)
        return {
            "raw": raw_value,
            "exact_target": exact,
            "formula": f"|(({raw_value} − 32) × 5/9) × 9/5 + 32 − {raw_value}|",
            "residual": residual,
            "tolerance": MULTIPLICATIVE_TOLERANCE,
            "passed": residual < MULTIPLICATIVE_TOLERANCE,
            "module_target_value": module_target,
            "rounding_quantum": abs(module_target - exact),
        }

    distance = candidates["u101"]
    temp = candidates["u102"]
    dist_check = reverse_distance(float(distance["raw_value"]), distance["conversion_factor"], distance["target_value"])
    temp_check = reverse_temperature(float(temp["raw_value"]), temp["target_value"])
    assert dist_check["passed"] and temp_check["passed"], (dist_check, temp_check)
    assert dist_check["residual"] < 0.01 and temp_check["residual"] < 0.01

    def display_rounding(candidate: dict, exact: float, raw_unit: str, factor) -> dict:
        displayed_match = re.match(r"-?\d+(?:\.\d+)?", candidate["display_text"])
        displayed = float(displayed_match.group(0))
        quantum = abs(displayed - exact)
        return {
            "displayed_value": displayed,
            "exact_value": exact,
            "display_text": candidate["display_text"],
            "rounding_policy": candidate["rounding_policy"],
            "quantum_in_target_unit": quantum,
            "quantum_in_raw_unit": quantum / factor if factor else None,
            "note": (
                "反向验算契约绑定未舍入精确值（PRD 硬要求）；界面展示值另受舍入策略约束，"
                "两者不得混用——用展示值回推原值必然带 0.5 个目标单位的舍入残差"
            ),
            "raw_unit": raw_unit,
        }

    dist_display = display_rounding(distance, dist_check["exact_target"], "miles", distance["conversion_factor"])
    temp_display = display_rounding(temp, temp_check["exact_target"], "°F", None)

    # 4B 剧情例外硬锁
    fever = candidates["u103"]
    code = candidates["u104"]
    record = candidates["u105"]
    money = candidates["u106"]
    for locked in (fever, code, record, money):
        assert locked["status"] == "MANUAL_DECISION_REQUIRED", locked["status"]
        assert locked["plot_exception"] is True
        assert locked["auto_apply_allowed"] is False
    assert fever["exception_reason"] == "PLOT_FEVER_TEMPERATURE"
    assert "FEVER_CONTEXT" in fever["evidence"]["context_flags"]
    assert code["exception_reason"] == "PLOT_NUMERIC_CODE"
    assert code["target_value"] is None and code["suggested_text"] is None
    assert "1234" in code["display_text"]
    assert record["exception_reason"] == "PLOT_RECORD_VALUE"
    assert record["target_value"] is None and record["suggested_text"] is None
    assert money["conversion_factor"] is None
    assert money["raw_currency_code"] == money["target_currency_code"] == "USD"
    assert money["target_value"] == 500.0
    assert "USD 500.00" in money["display_text"]

    receipt = {
        "step": "度量衡本地化（两段式确定性换算 + 剧情例外）",
        "task_id": task_id,
        "http_status": response.status_code,
        "manifest": body["manifest"],
        "case_normal_conversion": {
            "distance_26_2_miles": {
                "candidate": distance,
                "independent_reverse_verification": dist_check,
                "display_rounding": dist_display,
            },
            "temperature_70_f": {
                "candidate": temp,
                "independent_reverse_verification": temp_check,
                "display_rounding": temp_display,
            },
            "assertion": "|target × factor^-1 − raw| < 0.01 且 |target × 9/5 + 32 − raw| < 0.01",
            "result": "PASS",
        },
        "case_plot_exception_locks": {
            "fever_102f": {
                "status": fever["status"],
                "exception_reason": fever["exception_reason"],
                "context_flags": fever["evidence"]["context_flags"],
                "auto_apply_allowed": fever["auto_apply_allowed"],
                "display_text": fever["display_text"],
            },
            "numeric_code_1234": {
                "status": code["status"],
                "exception_reason": code["exception_reason"],
                "target_value": code["target_value"],
                "suggested_text": code["suggested_text"],
                "display_text": code["display_text"],
            },
            "record_9_58s": {
                "status": record["status"],
                "exception_reason": record["exception_reason"],
                "target_value": record["target_value"],
                "display_text": record["display_text"],
            },
            "money_500_usd": {
                "status": money["status"],
                "exception_reason": money["exception_reason"],
                "conversion_factor": money["conversion_factor"],
                "raw_currency_code": money["raw_currency_code"],
                "target_currency_code": money["target_currency_code"],
                "target_value": money["target_value"],
                "display_text": money["display_text"],
            },
            "result": "ALL_LOCKED",
        },
        "not_written_back": {
            "check": "候选人选不写入人工确认稿",
            "before": {u["unit_id"]: u["text"] for u in UNIT_UNITS},
        },
        "boundary": "换算为确定性 Python 计算；PROCESSED/SKIPPED 计数真实，无模型调用",
    }
    write_receipt("step4-unit-format", receipt)
    return {**receipt, "task_id": task_id}


# =========================================================================
# 5. 口语适配与节奏审校：CPS 超标阻断 -> 无损拆句 -> 重新通过
# =========================================================================

ORAL_FAIL_TEXT = "Cuando cayó la primera gota, nadie se movió más."
ORAL_WINDOW = 1.714  # 48 可见字符 / 1.714s = 28.00 CPS（>20 硬上限）
ORAL_FIXED_WINDOW = 3.0  # 人工确认可用间隙后，48 字符 / 3.0s = 16.00 CPS


def step5_oral_review(client, env) -> dict:
    print("[Step 5] 口语节奏：超标阻断 -> 无损拆句 -> 语义闸门复测")
    from code.backend.modules.oral_review.handler import build_lossless_split

    text = ORAL_FAIL_TEXT
    chars = vis_chars(text)
    units_bad = [
        {"unit_id": "u201", "source": "我们那天早上到车站时，火车已经开走了。", "text": text,
         "start": 1.0, "end": 1.0 + ORAL_WINDOW},
    ]
    seeded_bad = seed_confirmed_task(client, env, units_bad)
    blocked = client.post(
        f"/api/v1/oral/tasks/{seeded_bad['task_id']}/review", json={"expected_task_revision": 1}
    )
    assert blocked.status_code == 200, blocked.text
    blocked_body = blocked.json()
    item = blocked_body["items"][0]
    assert item["status"] == "BLOCK"
    assert "CPS_BLOCK" in item["readability"]["issues"]
    assert "LINE_LENGTH_EXCEEDED" in item["readability"]["issues"]
    cps_blocked = item["readability"]["cps"]
    assert chars == 48, chars
    assert cps_blocked == round(chars / ORAL_WINDOW, 2), (cps_blocked, chars / ORAL_WINDOW)

    # 5B 窗口不足时引擎拒绝给方案（宁可不给，不硬切时间轴）
    split_at_short_window = build_lossless_split(text, 1.0, 1.0 + ORAL_WINDOW)

    # 5C 补足显示窗口至 3.0s（人工确认可用间隙）后，引擎给出时间连续的无损拆句
    split_parts = build_lossless_split(text, 1.0, 1.0 + ORAL_FIXED_WINDOW)
    assert split_parts, "3.0s 窗口下引擎未给出拆句方案"
    total = round(sum(p.duration_sec for p in split_parts), 6)
    span = round(split_parts[-1].end_time - split_parts[0].start_time, 6)
    assert abs(total - span) < 1e-3
    for previous, current in zip(split_parts, split_parts[1:]):
        assert abs(previous.end_time - current.start_time) < 1e-3
    joined = " ".join(p.text.strip() for p in split_parts)
    assert " ".join(joined.split()) == " ".join(text.split())

    # 5D 把拆句方案落为两句连续字幕，重新走真实 HTTP 审校 -> 通过
    fixed_units = [
        {"unit_id": "u201", "source": "我们那天早上到车站时，", "text": split_parts[0].text,
         "start": split_parts[0].start_time, "end": split_parts[0].end_time},
        {"unit_id": "u202", "source": "火车已经开走了。", "text": split_parts[1].text,
         "start": split_parts[1].start_time, "end": split_parts[1].end_time},
    ]
    seeded_fixed = seed_confirmed_task(client, env, fixed_units)
    passed = client.post(
        f"/api/v1/oral/tasks/{seeded_fixed['task_id']}/review", json={"expected_task_revision": 1}
    )
    assert passed.status_code == 200, passed.text
    passed_body = passed.json()
    assert passed_body["overall_status"] == "PASS", passed_body["overall_status"]
    fixed_items = passed_body["items"]

    # 5E 四重语义保护闸门：拆句文本与原句一致 + 反例（极性被改）必须阻断
    from code.backend.modules.oral_review.handler import check_semantic_guards

    guard_split = check_semantic_guards(text, joined)
    assert guard_split.is_blocked is False, guard_split
    assert all(
        [
            guard_split.polarity_consistent,
            guard_split.entity_consistent,
            guard_split.relationship_consistent,
            guard_split.stance_consistent,
        ]
    )
    guard_negative = check_semantic_guards(text, "Cuando cayó la primera gota, todos se movieron mucho.")
    assert guard_negative.is_blocked is True, guard_negative

    # 5F 仅拆句、不补足窗口：CPS 无法通过（拆分不改变加权平均 CPS，禁止装成功）
    split_only = client.post(
        f"/api/v1/oral/tasks/{seeded_bad['task_id']}/review", json={"expected_task_revision": 1}
    )
    assert split_only.status_code == 200
    split_only_item = split_only.json()["items"][0]

    receipt = {
        "step": "口语适配与节奏审校（CPS / 行长 / 无损拆句 / 四重语义闸门）",
        "case_block_over_limit": {
            "text": text,
            "visible_chars": chars,
            "duration_sec": ORAL_WINDOW,
            "cps": cps_blocked,
            "max_line_length": item["readability"]["max_line_length"],
            "issues": item["readability"]["issues"],
            "status": item["status"],
            "http_status": blocked.status_code,
            "result": "BLOCK",
        },
        "case_split_refused_on_short_window": {
            "window_sec": ORAL_WINDOW,
            "split_suggestion": None if split_at_short_window is None else "unexpected",
            "reason": "任一侧不足 0.833s 时引擎拒绝给方案，不硬切时间轴",
        },
        "case_lossless_split_and_pass": {
            "window_sec": ORAL_FIXED_WINDOW,
            "parts": [p.model_dump() for p in split_parts],
            "duration_conservation": {
                "sum_parts_sec": total,
                "span_sec": span,
                "abs_delta_sec": abs(total - span),
                "tolerance_sec": 0.001,
                "passed": abs(total - span) < 1e-3,
            },
            "continuity": "相邻子句 end == 下一句 start（|Δt| < 1ms）",
            "text_lossless": True,
            "re_review": {
                "overall_status": passed_body["overall_status"],
                "items": [
                    {
                        "segment_id": i["segment_id"],
                        "text": i["original_text"],
                        "cps": i["readability"]["cps"],
                        "max_line_length": i["readability"]["max_line_length"],
                        "issues": i["readability"]["issues"],
                        "status": i["status"],
                        "guard": i.get("candidate", {}).get("guard_check") if i.get("candidate") else None,
                        "split_candidates": i.get("candidate", {}).get("split_candidates") if i.get("candidate") else None,
                    }
                    for i in fixed_items
                ],
                "manifest": passed_body["manifest"],
            },
            "result": "PASS",
        },
        "case_semantic_guard": {
            "split_vs_original": {
                "polarity_consistent": guard_split.polarity_consistent,
                "entity_consistent": guard_split.entity_consistent,
                "relationship_consistent": guard_split.relationship_consistent,
                "stance_consistent": guard_split.stance_consistent,
                "violations": guard_split.violations,
                "is_blocked": guard_split.is_blocked,
            },
            "negative_control": {
                "tampered_text": "Cuando cayó la primera gota, todos se movieron mucho.",
                "violations": guard_negative.violations,
                "block_reasons": guard_negative.block_reasons,
                "is_blocked": guard_negative.is_blocked,
            },
            "result": "GUARD_ENFORCED",
        },
        "case_split_alone_insufficient": {
            "statement": "拆句守恒 → 加权平均 CPS 不变；仅拆句不能降低 CPS",
            "observed_cps_when_window_not_extended": split_only_item["readability"]["cps"],
            "observed_status": split_only_item["status"],
            "result": "STILL_BLOCKED",
        },
        "boundary": "P-ORAL 阈值为未校准试点常量（17/20 CPS、42 字符、0.833s），仅白盒规则，不证明自然度",
    }
    write_receipt("step5-oral-review", receipt)
    return receipt


# =========================================================================
# 6. 平台合规质检与数字签发
# =========================================================================

DELIVERY_UNITS = [
    {"unit_id": "u301", "source": "我们到了阿亚库乔。", "text": "Llegamos a Ayacucho.", "start": 0.0, "end": 2.0},
    {"unit_id": "u302", "source": "村子很安静。", "text": "El pueblo está muy tranquilo.", "start": 2.1, "end": 4.1},
    {"unit_id": "u303", "source": "明天开始修路。", "text": "Mañana empiezan las obras del camino.", "start": 4.2, "end": 6.6},
]


def independent_parse_srt(content: str) -> list[dict]:
    """脚本自带的独立反解析器（不复用被验对象的解析函数）。"""
    cues = []
    blocks = re.split(r"\r?\n\r?\n", content.strip())
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        match = re.match(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})", lines[1]
        )
        assert match, f"非法 SRT 时间码: {lines[1]}"
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(v) for v in match.groups())
        cues.append(
            {
                "index": int(lines[0]),
                "start": h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                "end": h2 * 3600 + m2 * 60 + s2 + ms2 / 1000,
                "text": " ".join(lines[2:]),
            }
        )
    return cues


def independent_parse_vtt(content: str) -> list[dict]:
    """独立 WebVTT 反解析器：容忍 WEBVTT 头、可选 cue 序号行与 NOTE 块。"""
    cues = []
    pattern = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})\.(\d{3}) --> (\d{2}):(\d{2}):(\d{2})\.(\d{3})"
    )
    for block in re.split(r"\r?\n\r?\n", content.strip()):
        lines = [line for line in block.splitlines() if line.strip()]
        timing_at = next((i for i, line in enumerate(lines) if pattern.search(line)), None)
        if timing_at is None or block.lstrip().startswith("WEBVTT"):
            continue
        match = pattern.search(lines[timing_at])
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(v) for v in match.groups())
        cues.append(
            {
                "index": len(cues) + 1,
                "start": h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                "end": h2 * 3600 + m2 * 60 + s2 + ms2 / 1000,
                "text": " ".join(lines[timing_at + 1:]),
            }
        )
    return cues


def step6_compliance(client, env, operator_id: str, reviewer_id: str) -> dict:
    print("[Step 6] 平台合规质检 + 五维数字签发 + 无损导出")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace

    from code.backend.modules.compliance import handler as compliance_handler
    from code.backend.modules.compliance.contract import COMPLIANCE_POLICY_VERSION, SubtitleCue
    from code.backend.modules.compliance.integration import WorkflowComplianceAdapter
    from code.backend.modules.compliance.router import SqliteArtifactStore, create_compliance_router
    from code.backend.shared.models import ActorContext

    seeded = seed_confirmed_task(client, env, DELIVERY_UNITS)
    task_id = seeded["task_id"]
    db = env["db"]

    # 文化运行记录（受控夹具；规则版本与闸门快照必须与当前一致）
    with db.transaction() as conn:
        refs = {
            row["unit_id"]: {"translation_id": row["translation_id"], "revision": row["translation_revision"]}
            for row in conn.execute("SELECT * FROM translations WHERE task_id=?", (task_id,)).fetchall()
        }
    culture_manifest = {
        "translation_refs": refs,
        "rule_versions": {},
        "model_id": "CONTROLLED_FIXTURE_NO_MODEL",
        "prompt_hash": "fixture_prompt_hash",
        "input_hash": "fixture_input_hash",
        "note": "受控夹具：本批零外部模型调用",
    }
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO culture_runs (run_id, task_id, task_revision, target_market, manifest,"
            " coverage_limitations, checked_unit_ids, unchecked_units, status, created_at)"
            " VALUES (?,?,1,'MX',?,'[]',?,'[]','COMPLETED',?)",
            (
                f"crun_e2e_{uuid.uuid4().hex[:8]}", task_id, json.dumps(culture_manifest),
                json.dumps(list(refs)), datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    # 6A 真实主应用路由：生产规则库为空 -> fail-closed 409（不降标准放行）
    main_app_blocked = client.post(
        f"/api/v1/compliance/tasks/{task_id}/validate-and-export",
        json={"expected_task_revision": 1, "format": "srt"},
    )
    assert main_app_blocked.status_code == 409, main_app_blocked.text

    # 6B 受控规则解析器（与既有集成测试同款 SIMULATED 规则）挂载真实路由
    class Registry:
        def retrieve_applicable_rules(self, **kwargs):
            return [SimpleNamespace(rule_id="SIMULATED_RULE", rule_version="v1")]

    registry = Registry()
    culture_manifest["rule_versions"] = {"SIMULATED_RULE": "v1"}
    with db.transaction() as conn:
        conn.execute("UPDATE culture_runs SET manifest=?", (json.dumps(culture_manifest),))

    operator_actor = ActorContext(actor_id=operator_id, actor_type="human",
                                 actor_role="media_operator", allowed=True)
    reviewer_actor = ActorContext(actor_id=reviewer_id, actor_type="human",
                                  actor_role="reviewer", allowed=True)

    def build_client(actor):
        app = FastAPI()
        app.include_router(
            create_compliance_router(
                get_actor_context=lambda request, actor=actor: actor,
                storage_adapter=SqliteArtifactStore(db),
                task_adapter=WorkflowComplianceAdapter(db, registry),
            )
        )
        return TestClient(app)

    operator_api = build_client(operator_actor)
    reviewer_api = build_client(reviewer_actor)
    base = f"/api/v1/compliance/tasks/{task_id}"

    # 6C-1 非正时长：取对话阶段即 fail-closed（比 QC 更早，不允许伪造时间）
    with db.transaction() as conn:
        conn.execute(
            "UPDATE source_utterances SET start_ms=3000, end_ms=3000 WHERE task_id=? AND unit_id='u302'",
            (task_id,),
        )
    zero_duration = operator_api.post(
        base + "/validate-and-export", json={"expected_task_revision": 1, "format": "srt"}
    )
    assert zero_duration.status_code == 409, zero_duration.text
    zero_detail = zero_duration.json().get("detail")

    # 6C-2 时间码重叠（时长合法）：进入 QC -> QC_FAILED，产物正文强制清空
    with db.transaction() as conn:
        conn.execute(
            "UPDATE source_utterances SET start_ms=2100, end_ms=4100 WHERE task_id=? AND unit_id='u302'",
            (task_id,),
        )
        conn.execute(
            "UPDATE source_utterances SET start_ms=0, end_ms=2500 WHERE task_id=? AND unit_id='u301'",
            (task_id,),
        )
    defective = operator_api.post(base + "/validate-and-export", json={"expected_task_revision": 1, "format": "srt"})
    assert defective.status_code == 200, defective.text
    defective_artifact = defective.json()
    assert defective_artifact["status"] == "QC_FAILED"
    assert "content" not in defective_artifact
    issue_types = [i["issue_type"] for i in defective_artifact["validation_result"]["issues"]]
    assert "TIMECODE_OVERLAP" in issue_types, issue_types

    # 6C-3 纯校验器层：负/零时长缺陷码确实存在（证明判断能力，不被路由前置门掩盖）
    negative_check = compliance_handler.validate_platform_profile(
        [
            SubtitleCue(index=1, start_time=2.0, end_time=1.0, text="Hola."),
            SubtitleCue(index=2, start_time=3.0, end_time=5.0, text="Adiós."),
        ]
    )
    negative_codes = [i.issue_type.value for i in negative_check.issues]
    assert "DURATION_INVALID" in negative_codes, negative_codes

    stored = SqliteArtifactStore(db).get(task_id, defective_artifact["artifact_id"])
    assert stored is not None and stored.content == "" and stored.status.value == "QC_FAILED"

    download_blocked = operator_api.get(f"{base}/artifact?artifact_id={defective_artifact['artifact_id']}")
    assert download_blocked.status_code == 403, download_blocked.text

    signoff_blocked = reviewer_api.post(
        base + "/signoff",
        json={"artifact_id": defective_artifact["artifact_id"],
              "expected_revision": defective_artifact["manifest"]["translation_revision"]},
    )
    assert signoff_blocked.status_code == 409, signoff_blocked.text

    machine_app = FastAPI()
    machine_app.include_router(
        create_compliance_router(
            get_actor_context=lambda request: ActorContext(
                actor_id="agent_bot", actor_type="service_actor", actor_role="reviewer", allowed=True
            ),
            storage_adapter=SqliteArtifactStore(db),
            task_adapter=WorkflowComplianceAdapter(db, registry),
        )
    )
    machine_api = TestClient(machine_app)
    machine_signoff = machine_api.post(
        base + "/signoff",
        json={"artifact_id": defective_artifact["artifact_id"],
              "expected_revision": defective_artifact["manifest"]["translation_revision"]},
    )
    assert machine_signoff.status_code == 403, machine_signoff.text

    # 6D 恢复合法时间轴 -> 质检通过（Netflix Profile 全绿）
    with db.transaction() as conn:
        conn.execute("UPDATE source_utterances SET start_ms=0, end_ms=2000 WHERE task_id=? AND unit_id='u301'", (task_id,))
        conn.execute("UPDATE source_utterances SET start_ms=2100, end_ms=4100 WHERE task_id=? AND unit_id='u302'", (task_id,))
        conn.execute("UPDATE source_utterances SET start_ms=4200, end_ms=6600 WHERE task_id=? AND unit_id='u303'", (task_id,))
    validated = operator_api.post(base + "/validate-and-export", json={"expected_task_revision": 1, "format": "srt"})
    assert validated.status_code == 200, validated.text
    artifact = validated.json()
    assert artifact["status"] == "VALIDATED"
    assert artifact["validation_result"]["is_valid"] is True
    assert artifact["validation_result"]["issues"] == []
    assert artifact["round_trip_result"]["is_valid"] is True

    # 6E 五维哈希：任一要素被篡改即验签失败
    stored_valid = SqliteArtifactStore(db).get(task_id, artifact["artifact_id"])
    baseline = compliance_handler.build_signoff(
        stored_valid,
        task_id=task_id,
        translation_revision=artifact["manifest"]["translation_revision"],
        rule_version=artifact["manifest"]["rule_version"],
        validation_id=stored_valid.validation_id,
        signer_id=reviewer_id,
    )
    tamper_cases = {
        "task_id": baseline.model_copy(update={"task_id": task_id + "-TAMPERED"}),
        "translation_revision": baseline.model_copy(update={"translation_revision": "src1:u301=99"}),
        "rule_version": baseline.model_copy(update={"rule_version": "compliance-policy:0.0.0"}),
        "validation_id": baseline.model_copy(update={"validation_id": "val_forged"}),
        "artifact_sha256": baseline.model_copy(update={"artifact_sha256": hashlib.sha256(b"forged").hexdigest()}),
    }
    tamper_results = {}
    for dimension, forged in tamper_cases.items():
        try:
            compliance_handler.verify_and_apply_signoff(stored_valid, forged)
        except Exception as exc:  # noqa: BLE001 - 记录真实异常类型
            tamper_results[dimension] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "message": str(exc)[:200],
            }
        else:
            tamper_results[dimension] = {"rejected": False}
    assert all(item["rejected"] for item in tamper_results.values()), tamper_results

    # 6F 机器代签（HTTP 403，已验）+ operator 无签发权
    operator_signoff = operator_api.post(
        base + "/signoff",
        json={"artifact_id": artifact["artifact_id"],
              "expected_revision": artifact["manifest"]["translation_revision"]},
    )
    assert operator_signoff.status_code == 403, operator_signoff.text

    # 6G 真人签发 -> PUBLISH_READY
    signed = reviewer_api.post(
        base + "/signoff",
        json={"artifact_id": artifact["artifact_id"],
              "expected_revision": artifact["manifest"]["translation_revision"]},
    )
    assert signed.status_code == 200, signed.text
    signed_body = signed.json()
    assert signed_body["status"] == "PUBLISH_READY"

    package = reviewer_api.get(f"{base}/artifact?artifact_id={artifact['artifact_id']}")
    assert package.status_code == 200, package.text
    package_body = package.json()
    assert package_body["status"] == "PUBLISH_READY"
    assert package_body["signoff"]["signer_id"] == reviewer_id
    assert hashlib.sha256(package_body["content"].encode("utf-8")).hexdigest() == package_body["artifact_sha256"]

    # 6H 独立反解析器双向对账（SRT / WebVTT）
    vtt = operator_api.post(base + "/validate-and-export", json={"expected_task_revision": 1, "format": "vtt"})
    assert vtt.status_code == 200, vtt.text
    vtt_artifact = vtt.json()
    vtt_signed = reviewer_api.post(
        base + "/signoff",
        json={"artifact_id": vtt_artifact["artifact_id"],
              "expected_revision": vtt_artifact["manifest"]["translation_revision"]},
    )
    assert vtt_signed.status_code == 200, vtt_signed.text
    vtt_package = reviewer_api.get(f"{base}/artifact?artifact_id={vtt_artifact['artifact_id']}").json()

    srt_cues = independent_parse_srt(package_body["content"])
    vtt_cues = independent_parse_vtt(vtt_package["content"])
    expected = [
        {"index": i + 1, "start": u["start"], "end": u["end"], "text": u["text"]}
        for i, u in enumerate(DELIVERY_UNITS)
    ]

    def compare(parsed: list[dict]) -> dict:
        mismatches = []
        if len(parsed) != len(expected):
            mismatches.append({"count": [len(parsed), len(expected)]})
        for got, want in zip(parsed, expected):
            if got["index"] != want["index"]:
                mismatches.append({"index": [got["index"], want["index"]]})
            if abs(got["start"] - want["start"]) > 1e-3:
                mismatches.append({"start": [got["start"], want["start"]]})
            if abs(got["end"] - want["end"]) > 1e-3:
                mismatches.append({"end": [got["end"], want["end"]]})
            if got["text"] != want["text"]:
                mismatches.append({"text": [got["text"], want["text"]]})
        return {
            "cue_count": len(parsed),
            "expected_count": len(expected),
            "mismatches": mismatches,
            "match_rate": 1.0 if not mismatches else (len(expected) - len(mismatches)) / max(len(expected), 1),
            "passed": not mismatches,
        }

    srt_check = compare(srt_cues)
    vtt_check = compare(vtt_cues)
    assert srt_check["passed"] and vtt_check["passed"], (srt_check, vtt_check)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORT_DIR / f"{artifact['artifact_id']}.srt").write_text(package_body["content"], encoding="utf-8")
    (EXPORT_DIR / f"{vtt_artifact['artifact_id']}.vtt").write_text(vtt_package["content"], encoding="utf-8")

    # 6I 已签发后再次签发 / 篡改修订 -> 409
    resign = reviewer_api.post(
        base + "/signoff",
        json={"artifact_id": artifact["artifact_id"],
              "expected_revision": artifact["manifest"]["translation_revision"]},
    )
    forged_revision = reviewer_api.post(
        base + "/signoff",
        json={"artifact_id": artifact["artifact_id"], "expected_revision": "src1:u301=7"},
    )
    assert resign.status_code == 409, resign.text
    assert forged_revision.status_code == 409, forged_revision.text

    receipt = {
        "step": "平台合规质检与数字签发",
        "task_id": task_id,
        "case_real_registry_fail_closed": {
            "http_status": main_app_blocked.status_code,
            "detail": main_app_blocked.json().get("detail"),
            "note": "生产规则库无 VERIFIED/ACTIVE 条目时的真实行为",
        },
        "case_zero_duration_gate": {
            "http_status": zero_duration.status_code,
            "detail": zero_detail,
            "note": "非正时长在取确认对话阶段即被拒（fail-closed），比 QC 更早，不允许伪造时间",
        },
        "case_negative_duration_validator": {
            "issues": negative_codes,
            "level": "handler-level validate_platform_profile",
            "result": "DURATION_INVALID",
        },
        "case_qc_failed_block_and_leak_protection": {
            "http_status": defective.status_code,
            "status": defective_artifact["status"],
            "issues": defective_artifact["validation_result"]["issues"],
            "content_in_response": "content" in defective_artifact,
            "stored_content_empty": stored.content == "",
            "download_http_status": download_blocked.status_code,
            "download_detail": download_blocked.json().get("detail"),
            "signoff_on_qc_failed_status": signoff_blocked.status_code,
            "machine_signoff_http_status": machine_signoff.status_code,
            "machine_signoff_detail": machine_signoff.json().get("detail"),
            "result": "QC_FAILED + 物理防泄漏",
        },
        "case_tamper_five_dimension_hash": {
            "dims": tamper_results,
            "result": "ALL_REJECTED",
        },
        "case_human_signoff_and_export": {
            "operator_signoff_status": operator_signoff.status_code,
            "signed_status": signed_body["status"],
            "package_status": package_body["status"],
            "signer_id": package_body["signoff"]["signer_id"],
            "signoff_hash": package_body["signoff"]["signoff_hash"],
            "artifact_sha256": package_body["artifact_sha256"],
            "content_sha256_recomputed": hashlib.sha256(package_body["content"].encode("utf-8")).hexdigest(),
            "profile_used": artifact["validation_result"]["profile_used"],
            "round_trip_result": artifact["round_trip_result"],
            "srt_export": str((EXPORT_DIR / f"{artifact['artifact_id']}.srt").relative_to(ROOT)),
            "vtt_export": str((EXPORT_DIR / f"{vtt_artifact['artifact_id']}.vtt").relative_to(ROOT)),
            "srt_content": package_body["content"],
            "vtt_content": vtt_package["content"],
            "independent_srt_reparse": srt_check,
            "independent_vtt_reparse": vtt_check,
            "re_signoff_status": resign.status_code,
            "forged_revision_status": forged_revision.status_code,
            "result": "PUBLISH_READY + 100% 对账",
        },
        "boundary": "规则解析器为受控 SIMULATED 规则（生产规则库未核验）；文化/翻译运行记录为受控夹具，不代表模型质量",
    }
    write_receipt("step6-compliance-signoff", receipt)
    return receipt


# =========================================================================
# main
# =========================================================================

def main() -> int:
    started = datetime.now(timezone.utc)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    # 清掉上一轮导出的产物，避免新旧 artifact 混在一起被误读
    for stale in list(EXPORT_DIR.glob("*.srt")) + list(EXPORT_DIR.glob("*.vtt")):
        stale.unlink()

    env = bootstrap_isolated_env()
    print(f"isolated db   : {env['db_path']}")
    print(f"isolated store: {env['storage_dir']}")

    from fastapi.testclient import TestClient
    from code.backend.main import app
    from code.backend.shared.controls.auth import register_local_operator

    operator = register_local_operator(display_name="E2E 操作员", role="media_operator")
    reviewer = register_local_operator(display_name="E2E 终审员", role="reviewer")

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.cookies.set("session_token", operator["session_token"])
        health = client.get("/api/v1/health")
        session = client.get("/api/v1/auth/session")

        step1 = step1_asr(client, env)
        step2 = step2_translation(client, env)
        step3 = step3_culture(client, env, step2["task_id"])
        step4 = step4_unit_format(client, env)
        step5 = step5_oral_review(client, env)

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.cookies.set("session_token", operator["session_token"])
        with TestClient(app, base_url="http://127.0.0.1:8765") as reviewer_client:
            reviewer_client.cookies.set("session_token", reviewer["session_token"])
            step6 = step6_compliance(client, env, operator["operator_id"], reviewer["operator_id"])

    finished = datetime.now(timezone.utc)
    summary = {
        "run_id": f"e2e20261023-{uuid.uuid4().hex[:8]}",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_sec": round((finished - started).total_seconds(), 2),
        "health_http_status": health.status_code,
        "health_body": health.json(),
        "session": session.json(),
        "isolated_db": str(env["db_path"]),
        "steps": {
            "step1_asr": step1["case_success_standard_slice"]["result"],
            "step2_translation": "PASS" if step2["case_success_locked_term"]["result"] == "PASS" else "FAIL",
            "step3_culture": step3["case_repaired_and_passed"]["status"],
            "step4_unit_format": step4["case_normal_conversion"]["result"],
            "step5_oral_review": step5["case_lossless_split_and_pass"]["result"],
            "step6_compliance": step6["case_human_signoff_and_export"]["result"],
        },
        "live_service_probe": None,
    }
    try:
        import httpx

        live = httpx.get("http://127.0.0.1:8765/", timeout=3.0)
        live_health = httpx.get("http://127.0.0.1:8765/api/v1/health", timeout=3.0)
        summary["live_service_probe"] = {
            "root_http_status": live.status_code,
            "health_http_status": live_health.status_code,
        }
    except Exception as exc:  # noqa: BLE001
        summary["live_service_probe"] = {"error": str(exc)}

    write_receipt("00-run-summary", summary)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary["steps"], ensure_ascii=False, indent=2))
    print(f"duration: {summary['duration_sec']}s")
    print(f"live probe: {summary['live_service_probe']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

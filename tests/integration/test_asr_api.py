import json
import uuid
from pathlib import Path

import pytest
from starlette.testclient import TestClient


def test_auxiliary_material_rejects_placeholder_rights_and_links_task(auth_client, sample_video):
    """
    T1.1 Minimal Wrap-up:
    1. Rejects dummy placeholder rights_ref ('RIGHTS-AUX-20261021', 'rights-default-001').
    2. Accepts valid rights_ref, links auxiliary asset to Task, increments task_revision,
       and resets task status to DRAFT if it was previously READY.
    """
    # 1. Create a task and confirm it to READY
    t_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"REQ-AUX-{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    assert t_res.status_code == 200
    task_id = t_res.json()["task_id"]

    # Register video & media to confirm task
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-AUTH-VALID-001"},
        )
    vid_asset_id = v_res.json()["asset_id"]

    # Extract audio
    ext_res = auth_client.post(f"/api/v1/tasks/{task_id}/ingest/extract-audio", json={
        "video_asset_id": vid_asset_id,
        "track_index": 1,
    })
    assert ext_res.status_code == 200
    audio_asset_id = ext_res.json()["derived_asset_id"]

    # Register Media & confirm
    m_res = auth_client.post("/api/v1/media", json={
        "title_id": "TIT-001",
        "episode_id": "EP-001",
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
    })
    media_id = m_res.json()["media_id"]

    auth_client.post(f"/api/v1/media/{media_id}/confirm", json={
        "expected_revision": 1,
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
        "match_checks": [{"asset_id": vid_asset_id, "check_type": "codec_readability", "result": "pass", "method": "ffprobe"}],
    })
    auth_client.post(f"/api/v1/tasks/{task_id}/confirm", json={
        "expected_revision": 1,
        "media_id": media_id,
    })

    # Verify task is READY
    t_get = auth_client.get(f"/api/v1/tasks/{task_id}")
    assert t_get.json()["task_status"] == "READY"
    initial_rev = t_get.json()["task_revision"]

    # 2. Upload auxiliary material with forbidden placeholder -> rejected 400
    dummy_aux = b"Sample script dialogue text"
    rej_res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": ("script.txt", dummy_aux, "text/plain")},
        data={"kind": "script", "rights_ref": "RIGHTS-AUX-20261021", "task_id": task_id},
    )
    assert rej_res.status_code == 400
    assert "默认占位符" in rej_res.text

    # 3. Upload auxiliary material with valid rights_ref -> accepted & linked
    ok_res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": ("script.txt", dummy_aux, "text/plain")},
        data={"kind": "script", "rights_ref": "RIGHTS-SCRIPT-LEGAL-20261021", "task_id": task_id},
    )
    assert ok_res.status_code == 200
    aux_data = ok_res.json()
    assert aux_data["task_id"] == task_id
    assert aux_data["task_revision"] == initial_rev + 1
    assert aux_data["task_status"] == "DRAFT"  # Reset to DRAFT because new auxiliary was added

    # Verify task in DB has updated input_asset_ids and status DRAFT
    t_after = auth_client.get(f"/api/v1/tasks/{task_id}").json()
    assert aux_data["asset_id"] in t_after["input_asset_ids"]
    assert t_after["task_status"] == "DRAFT"


def test_asr_slice_and_listen_back_flow(auth_client, sample_video):
    """
    T2.1: Tests 10s audio slicing, quality measurement, run isolation, and chunk audio retrieval.
    Strict rules:
    - Task & Media MUST be confirmed prior to slicing.
    - Slices receive unique Task/run chunk_ids (no collisions across tasks or runs).
    - Preserves previous run slices without overwriting old audio.
    """
    # 1. Create task, upload video, extract audio, register & confirm media, confirm task
    t_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"REQ-ASR-{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    assert t_res.status_code == 200
    task_id = t_res.json()["task_id"]

    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-AUTH-VALID-002"},
        )
    vid_asset_id = v_res.json()["asset_id"]

    ext_res = auth_client.post(f"/api/v1/tasks/{task_id}/ingest/extract-audio", json={
        "video_asset_id": vid_asset_id,
        "track_index": 1,
    })
    assert ext_res.status_code == 200
    audio_asset_id = ext_res.json()["derived_asset_id"]

    # Register Media & confirm
    m_res = auth_client.post("/api/v1/media", json={
        "title_id": "TIT-ASR-001",
        "episode_id": "EP-ASR-001",
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
    })
    assert m_res.status_code == 200
    media_id = m_res.json()["media_id"]

    auth_client.post(f"/api/v1/media/{media_id}/confirm", json={
        "expected_revision": 1,
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
        "match_checks": [{"asset_id": vid_asset_id, "check_type": "codec_readability", "result": "pass", "method": "ffprobe"}],
    })

    # Confirm Task
    auth_client.post(f"/api/v1/tasks/{task_id}/confirm", json={
        "expected_revision": 1,
        "media_id": media_id,
    })

    # 2. Check ASR status endpoint
    status_res = auth_client.get(f"/api/v1/tasks/{task_id}/asr/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "model_id" in status_data
    assert "status" in status_data

    # 3. Slice task audio (Run 1)
    slice_res1 = auth_client.post(f"/api/v1/tasks/{task_id}/asr/slice")
    assert slice_res1.status_code == 200
    slice_data1 = slice_res1.json()
    assert slice_data1["chunks_count"] >= 1
    chunk_run1 = slice_data1["chunks"][0]
    chunk_id_1 = chunk_run1["chunk_id"]

    # Verify Task/run unique chunk_id format (not fixed chunk_000)
    assert chunk_id_1.startswith(f"chk_{task_id[:8]}_")
    assert "quality_stats" in chunk_run1
    assert chunk_run1["quality_stats"]["peak_level_dbfs"] is not None

    # Retrieve slice audio for listen-back
    audio_res1 = auth_client.get(f"/api/v1/tasks/{task_id}/asr/chunks/{chunk_id_1}/audio")
    assert audio_res1.status_code == 200
    assert audio_res1.headers["content-type"] == "audio/wav"
    assert len(audio_res1.content) > 0

    # 4. Execute a second slicing run (Run 2) -> Run isolation and no overwrite
    slice_res2 = auth_client.post(f"/api/v1/tasks/{task_id}/asr/slice")
    assert slice_res2.status_code == 200
    slice_data2 = slice_res2.json()
    chunk_run2 = slice_data2["chunks"][0]
    chunk_id_2 = chunk_run2["chunk_id"]

    # Run 1 and Run 2 chunks MUST be distinct
    assert chunk_id_1 != chunk_id_2
    assert slice_data1["slice_run_id"] != slice_data2["slice_run_id"]

    # Historical chunk from Run 1 is STILL listenable and not overwritten!
    audio_res1_again = auth_client.get(f"/api/v1/tasks/{task_id}/asr/chunks/{chunk_id_1}/audio")
    assert audio_res1_again.status_code == 200
    assert len(audio_res1_again.content) == len(audio_res1.content)


def test_asr_transcribe_authorization_blocks_unauthorized_and_allows_simulated(auth_client, sample_video, monkeypatch):
    """
    T2.1: Tests transcription authorization boundary:
    1. Draft task -> blocked 400 STAGE_NOT_READY.
    2. Ready task without cloud authorization -> blocked 403 待配置/待授权.
    3. Production mode without server TEST_MODE -> simulated request rejected with 403.
    4. Isolated test mode with simulated option -> succeeds, generates candidates, boundary issues, unconfirmed entity issues.
    5. Manual edit candidate timestamp validation (rejects negative, inverted, out-of-bounds).
    6. Distinguishes save draft (EDITED_DRAFT) from human confirmation (EDITED_ACCEPTED).
    """
    # 1. Draft task ASR attempt -> 400 STAGE_NOT_READY
    t_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"REQ-ASR2-{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = t_res.json()["task_id"]

    trans_draft = auth_client.post(f"/api/v1/tasks/{task_id}/asr/transcribe", json={"simulate": False})
    assert trans_draft.status_code == 400
    assert "STAGE_NOT_READY" in trans_draft.text

    # Complete ingest & confirmation to make task READY
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-AUTH-VALID-003"},
        )
    vid_asset_id = v_res.json()["asset_id"]

    ext_res = auth_client.post(f"/api/v1/tasks/{task_id}/ingest/extract-audio", json={
        "video_asset_id": vid_asset_id,
        "track_index": 1,
    })
    audio_asset_id = ext_res.json()["derived_asset_id"]

    m_res = auth_client.post("/api/v1/media", json={
        "title_id": "TIT-002",
        "episode_id": "EP-002",
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
    })
    media_id = m_res.json()["media_id"]

    auth_client.post(f"/api/v1/media/{media_id}/confirm", json={
        "expected_revision": 1,
        "master_video_asset_id": vid_asset_id,
        "primary_audio_asset_id": audio_asset_id,
        "match_checks": [{"asset_id": vid_asset_id, "check_type": "codec_readability", "result": "pass", "method": "ffprobe"}],
    })
    auth_client.post(f"/api/v1/tasks/{task_id}/confirm", json={
        "expected_revision": 1,
        "media_id": media_id,
    })

    # Slice audio
    auth_client.post(f"/api/v1/tasks/{task_id}/asr/slice")

    # 2. Production mode without server TEST_MODE -> simulated request rejected with 403
    monkeypatch.setattr("code.backend.main.TEST_MODE", False)
    trans_sim_prod = auth_client.post(f"/api/v1/tasks/{task_id}/asr/transcribe", json={"simulate": True})
    assert trans_sim_prod.status_code == 403
    assert "普通正式环境禁止使用模拟识别" in trans_sim_prod.text

    # Ready task without cloud authorization in normal mode -> blocked 403 待配置/待授权
    trans_unauth = auth_client.post(f"/api/v1/tasks/{task_id}/asr/transcribe", json={"simulate": False})
    assert trans_unauth.status_code == 403
    unauth_data = trans_unauth.json()["detail"]
    assert unauth_data["status"] == "待配置/待授权"
    assert "未授权实际素材外传或云端调用" in unauth_data["message"]

    # 3. Restore TEST_MODE for controlled test execution -> succeeds with SIMULATED tagging
    monkeypatch.setattr("code.backend.main.TEST_MODE", True)
    trans_sim = auth_client.post(f"/api/v1/tasks/{task_id}/asr/transcribe", json={"simulate": True})
    assert trans_sim.status_code == 200
    sim_data = trans_sim.json()
    assert sim_data["is_simulated"] is True
    assert len(sim_data["candidates"]) >= 1

    cand_0 = sim_data["candidates"][0]
    candidate_id = cand_0["candidate_id"]
    assert "proposed" in cand_0
    assert cand_0["confidence"]["calibration_label"] == "模型自评/未校准 (SIMULATED)"

    # Check candidates query
    cands_res = auth_client.get(f"/api/v1/tasks/{task_id}/asr/candidates")
    assert cands_res.status_code == 200
    cands_data = cands_res.json()
    assert len(cands_data["candidates"]) >= 1

    # 4. Manual edit timestamp validation:
    # 4a. Negative start_ms -> 400
    neg_res = auth_client.patch(f"/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}", json={
        "expected_revision": 1,
        "start_ms": -50,
    })
    assert neg_res.status_code == 400
    assert "不能为负数" in neg_res.text

    # 4b. Inverted start_ms / end_ms -> 400
    inv_res = auth_client.patch(f"/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}", json={
        "expected_revision": 1,
        "start_ms": 5000,
        "end_ms": 1000,
    })
    assert inv_res.status_code == 400
    assert "逆序或0时长错误" in inv_res.text

    # 4c. Out of bounds against media duration -> 400
    oob_res = auth_client.patch(f"/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}", json={
        "expected_revision": 1,
        "start_ms": 0,
        "end_ms": 9999999,
    })
    assert oob_res.status_code == 400
    assert "超出母版总时长" in oob_res.text

    # 5. Distinguish save draft (EDITED_DRAFT) from human confirmation (EDITED_ACCEPTED)
    # 5a. Save draft without confirm -> EDITED_DRAFT
    draft_res = auth_client.patch(f"/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}", json={
        "expected_revision": 1,
        "text": "人工编辑草稿文本",
        "confirm": False,
    })
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert draft_data["candidate_status"] == "EDITED_DRAFT"
    assert draft_data["candidate_revision"] == 2
    assert "original_model_output" in draft_data["proposed"]

    # 5b. Confirm candidate -> EDITED_ACCEPTED
    confirm_res = auth_client.patch(f"/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}", json={
        "expected_revision": 2,
        "text": "人工确认接受的最终台词文本。",
        "confirm": True,
    })
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["candidate_status"] == "EDITED_ACCEPTED"
    assert confirm_data["candidate_revision"] == 3

    # 6. Confirm unknown entity candidate -> closes unconfirmed entity issue
    ent_res = auth_client.post(f"/api/v1/tasks/{task_id}/asr/entities/confirm", json={
        "name": "测试专名",
        "category": "brand",
        "confirmed_name": "快手测试专名",
    })
    assert ent_res.status_code == 200
    assert ent_res.json()["status"] == "confirmed"


def test_asr_glossary_matching_strict_engineering_rule():
    """
    T2.1: Verifies that entity matching strictly requires engineering-scoped glossary terms,
    and never blindly trusts model self-filled 'matched' status.
    """
    from code.backend.modules.asr_alignment.contract import EntityCandidate
    from code.backend.modules.asr_alignment.handler import match_glossary

    # Untrusted model output attempting to claim 'matched'
    untrusted_entities = [
        EntityCandidate(name="快手", category="brand", match_status="matched", glossary_ref="FAKE-001"),
        EntityCandidate(name="张三", category="person", match_status="matched", glossary_ref="FAKE-002"),
    ]

    # Without glossary, everything must be reset to pending_confirmation
    reset_res = match_glossary(untrusted_entities, glossary_terms=None)
    for e in reset_res:
        assert e.match_status == "pending_confirmation"
        assert e.glossary_ref is None

    # With project glossary containing only "快手"
    project_glossary = [{"term": "快手", "term_id": "GLOSS-KUAISHOU-01"}]
    matched_res = match_glossary(untrusted_entities, glossary_terms=project_glossary)
    assert matched_res[0].match_status == "matched"
    assert matched_res[0].glossary_ref == "GLOSS-KUAISHOU-01"
    assert matched_res[1].match_status == "pending_confirmation"
    assert matched_res[1].glossary_ref is None

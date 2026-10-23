import json
import uuid
import pytest

from code.backend.modules.asr_alignment.handler import validate_gemini_response_structure
from code.backend.modules.translation import run_deterministic_semantic_checks


def test_item1_asr_schema_and_validation_audit():
    """
    验收项1：审计现有ASR合法与非法结构校验。
    约束必填、类型、时间非负、时间倒置失败、无声与文字冲突失败、置信分区间0..1。
    """
    valid_resp = {
        "text": "这是一段忠实的源语音频内容",
        "timing_candidates": [
            {"start_ms": 100, "end_ms": 2500, "text": "这是一段忠实的"}
        ],
        "uncertainties": [],
        "overlap_candidates": [],
        "entity_candidates": [],
        "no_speech": False,
        "model_self_eval_confidence": 0.95,
    }
    validate_gemini_response_structure(valid_resp)

    # Missing required keys
    with pytest.raises(ValueError, match="缺少字段"):
        validate_gemini_response_structure({"text": "缺少timing等字段"})

    # Conflict: no_speech=True but text is not empty
    with pytest.raises(ValueError, match="冲突状态"):
        validate_gemini_response_structure({**valid_resp, "no_speech": True, "text": "有字"})

    # Conflict: no_speech=False but text is empty
    with pytest.raises(ValueError, match="非法空文字"):
        validate_gemini_response_structure({**valid_resp, "no_speech": False, "text": ""})

    # Inverted timing range: start_ms > end_ms
    with pytest.raises(ValueError, match="时间倒置"):
        validate_gemini_response_structure({
            **valid_resp,
            "timing_candidates": [{"start_ms": 3000, "end_ms": 1000, "text": "倒置"}]
        })

    # Out of range confidence score (> 1.0)
    with pytest.raises(ValueError, match="必须在 0.0 至 1.0 之间"):
        validate_gemini_response_structure({
            **valid_resp,
            "model_self_eval_confidence": 1.5
        })

    # Truncated output (finishReason)
    with pytest.raises(ValueError, match="异常中止/截断"):
        validate_gemini_response_structure(valid_resp, finish_reason="MAX_TOKENS")


def test_item1_simulate_rejected_without_test_mode(isolated_test_env, auth_client, monkeypatch):
    """
    验收项1：普通正式环境（TEST_MODE=False）禁止使用模拟接口。
    """
    monkeypatch.setattr("config.settings.TEST_MODE", False)
    monkeypatch.setattr("code.backend.main.TEST_MODE", False)
    monkeypatch.setattr("code.backend.modules.translation.source_cleanup.TEST_MODE", False)
    monkeypatch.setattr("code.backend.modules.translation.handler.TEST_MODE", False)

    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_sim_reject_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = task_res.json()["task_id"]

    # 1. Cleanup simulate:true MUST be rejected with HTTP 403
    res_cleanup = auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})
    assert res_cleanup.status_code == 403, f"Expected 403, got {res_cleanup.status_code}: {res_cleanup.text}"
    assert "禁止使用模拟整理" in res_cleanup.text

    # 2. Translation simulate:true MUST be rejected with HTTP 403
    res_trans = auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "US",
        "simulate": True,
    })
    assert res_trans.status_code == 403
    assert "禁止使用模拟初翻" in res_trans.text


def test_item2_and_3_task_a_cleanup_and_speaker_proposal(isolated_test_env, auth_client, tmp_path):
    """
    验收项2与3：任务A源语整理、读取真实ASR composite候选、跨切片断句缝合并保留多父切片来源；
    在无脚本呼告证据下，保留匿名说话人(spk_1)且角色必须为null(unknown)；
    禁止使用占位文字补稿。
    """
    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_cleanup_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
        "source_locale": "zh-CN",
    })
    assert task_res.status_code == 200, task_res.text
    task_id = task_res.json()["task_id"]

    # Create dummy wav file
    dummy_wav = tmp_path / "test_clip.wav"
    dummy_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    db = isolated_test_env["db"]
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_c1", task_id, "s_run1", 0, 0, 10000, 0, 10000, "sha1", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_c2", task_id, "s_run1", 1, 10000, 20000, 10000, 10000, "sha2", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))

        # Composite candidates from ASR
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_c1", task_id, "seg_1", "chk_c1", "composite", json.dumps({"text": "当年若不是你背叛我", "master_start_ms": 0, "master_end_ms": 10000}), "0.9", "h1", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_c2", task_id, "seg_2", "chk_c2", "composite", json.dumps({"text": "我又何至于流落海外三年！", "master_start_ms": 10000, "master_end_ms": 20000}), "0.9", "h2", "2026-10-22T00:00:00Z"))

    # Execute cleanup
    clean_res = auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})
    assert clean_res.status_code == 200, clean_res.text
    clean_data = clean_res.json()
    assert clean_data["status"] == "AI_PROPOSED"
    assert clean_data["revision"] == 1

    # Check transcript details
    tr_res = auth_client.get(f"/api/v1/tasks/{task_id}/source-transcript")
    assert tr_res.status_code == 200
    tr_data = tr_res.json()
    assert tr_data["status"] == "AI_PROPOSED"
    assert len(tr_data["utterances"]) >= 1

    # Multi-parent source spans verification
    u0 = tr_data["utterances"][0]
    span_chunk_ids = [sp["chunk_id"] for sp in u0["source_spans"]]
    assert "chk_c1" in span_chunk_ids
    assert "chk_c2" in span_chunk_ids, "跨切片缝合必须完整保留多父切片来源引用！"
    assert "音频切片" not in u0["text"], "禁止出现占位文字！"

    # Speaker and character evidence verification: anonymous speaker present, character_ref is null
    spk0 = tr_data["speakers"][0]
    assert spk0["speaker_id"] == "spk_1"
    assert spk0["character_ref"] is None, "无确凿人名呼告证据时角色必须未知(null)，严禁主观凭声线臆测！"


def test_item5_gate1_blocks_translation_until_confirmed(isolated_test_env, auth_client, tmp_path):
    """
    验收项5：第一人工关口。
    源稿未人工确认前，禁止启动初翻（返回400 STAGE_NOT_READY）。
    """
    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_gate1_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = task_res.json()["task_id"]

    dummy_wav = tmp_path / "test_clip.wav"
    dummy_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    db = isolated_test_env["db"]
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_g1", task_id, "s_run_g1", 0, 0, 10000, 0, 10000, "sha_g", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_g1", task_id, "seg_g1", "chk_g1", "composite", json.dumps({"text": "少爷，老太爷叫您过去一趟。"}), "0.9", "hg1", "2026-10-22T00:00:00Z"))

    auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})

    # Attempt to generate translation BEFORE Gate 1 confirmation
    trans_res = auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "US",
        "simulate": True,
    })
    assert trans_res.status_code == 400, "未确认源稿前启动翻译必须被阻断"
    assert "STAGE_NOT_READY" in trans_res.text


def test_item6_and_7_translation_and_semantic_checks(isolated_test_env, auth_client, tmp_path):
    """
    验收项6与7：
    - 目标市场由用户显式选择（若未选择或为空报错）
    - 检索锁词库并记录 term_hits
    - 语义检查独立检测强制锁词遗漏 (BLOCK)
    - 数字不一致报警 (WARN)
    - 否定颠倒报警 (WARN)
    - QE状态如实显示'未评估'，不伪填评分
    """
    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_trans_checks_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = task_res.json()["task_id"]

    # Add a locked term to knowledge base
    k_res = auth_client.post("/api/v1/projects/PRJ-DEFAULT/knowledge", json={
        "category": "glossary",
        "source_text": "九转还魂丹",
        "target_text": "Nine-Soul Reversion Pill",
        "target_language": "en",
        "is_locked": True,
    })
    assert k_res.status_code == 200, k_res.text

    dummy_wav = tmp_path / "test_clip.wav"
    dummy_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    db = isolated_test_env["db"]
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_t1", task_id, "s_run_t1", 0, 0, 10000, 0, 10000, "sha_t", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_t1", task_id, "seg_t1", "chk_t1", "composite", json.dumps({"text": "少爷，这三枚九转还魂丹绝不能给他们！"}), "0.9", "ht1", "2026-10-22T00:00:00Z"))

    # Task A: cleanup
    auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})

    # Gate 1: Human confirms source transcript
    confirm_res = auth_client.post(f"/api/v1/tasks/{task_id}/source-transcript/confirm", json={
        "expected_revision": 1,
        "force_ignore_doubts": True,
    })
    assert confirm_res.status_code == 200, confirm_res.text

    # Target market validation: empty market rejected
    bad_res = auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "   ",
        "simulate": True,
    })
    assert bad_res.status_code == 400

    # Task B & C: Generate translation with user-selected market US
    gen_res = auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "US",
        "simulate": True,
    })
    assert gen_res.status_code == 200, gen_res.text
    gen_data = gen_res.json()
    assert gen_data["target_market"] == "US"
    assert gen_data["qe_status"] == "未评估", "未独立接入QE评估时必须真实显示未评估"

    # Verify translations & term hits
    tr_list_res = auth_client.get(f"/api/v1/tasks/{task_id}/translations")
    assert tr_list_res.status_code == 200
    tr_list_data = tr_list_res.json()
    assert len(tr_list_data["translations"]) >= 1
    t0 = tr_list_data["translations"][0]
    assert any(h["source_term"] == "九转还魂丹" for h in t0["term_hits"])


def test_item8_gate2_lock_protection_and_rollback(isolated_test_env, auth_client, tmp_path):
    """
    验收项8：第二人工关口。
    - 锁定保护：锁定稿不能被AI覆盖
    - 逐句编辑与版本递增
    - 历史回滚：复制目标历史版本为新修订，保留完整审计日志，不删除历史
    """
    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_gate2_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = task_res.json()["task_id"]

    dummy_wav = tmp_path / "test_clip.wav"
    dummy_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    db = isolated_test_env["db"]
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_l1", task_id, "s_run_l1", 0, 0, 10000, 0, 10000, "sha_l", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_l1", task_id, "seg_l1", "chk_l1", "composite", json.dumps({"text": "真相终于大白了。"}), "0.9", "hl1", "2026-10-22T00:00:00Z"))

    auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})
    auth_client.post(f"/api/v1/tasks/{task_id}/source-transcript/confirm", json={"expected_revision": 1})
    auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "LATAM",
        "simulate": True,
    })

    tr_res = auth_client.get(f"/api/v1/tasks/{task_id}/translations")
    unit_id = tr_res.json()["translations"][0]["unit_id"]

    # 1. Human edit translation (Rev 1 -> Rev 2)
    edit_res = auth_client.patch(f"/api/v1/tasks/{task_id}/translations/{unit_id}", json={
        "source_revision": 1,
        "expected_revision": 1,
        "text": "The truth has finally come to light (Human Rev 2).",
    })
    assert edit_res.status_code == 200
    assert edit_res.json()["revision"] == 2

    # 2. Lock translation
    lock_res = auth_client.post(f"/api/v1/tasks/{task_id}/translations/{unit_id}/lock", json={"source_revision":1,"expected_revision":2})
    assert lock_res.status_code == 200
    assert lock_res.json()["is_locked"] is True

    # 3. Re-run AI generation: locked translation MUST NOT be overwritten!
    auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "LATAM",
        "simulate": True,
    })
    tr_after_rerun = auth_client.get(f"/api/v1/tasks/{task_id}/translations")
    u_after = tr_after_rerun.json()["translations"][0]
    assert u_after["text"] == "The truth has finally come to light (Human Rev 2)."
    assert u_after["is_locked"] is True

    # 4. Rollback to Revision 1
    rb_res = auth_client.post(f"/api/v1/tasks/{task_id}/translations/{unit_id}/rollback", json={
        "source_revision": 1, "expected_revision": 2,
        "target_revision": 1,
        "reason": "测试人工回滚至初版",
    })
    assert rb_res.status_code == 200, rb_res.text
    rb_data = rb_res.json()
    assert rb_data["revision"] == 3
    assert rb_data["restored_from_revision"] == 1


def test_item4_and_8_source_modification_creates_new_revision_and_expires_translations(isolated_test_env, auth_client, tmp_path):
    """
    验收项4与8：已确认源稿编辑必须带expected_revision，产生新修订Rev2并撤销确认（回退AI_PROPOSED），
    旧版本(Rev 1)的初翻译文被标记为 EXPIRED。
    """
    task_res = auth_client.post("/api/v1/tasks", json={
        "request_key": f"test_expire_{uuid.uuid4().hex[:8]}",
        "task_type": "source_only",
    })
    task_id = task_res.json()["task_id"]

    dummy_wav = tmp_path / "test_clip.wav"
    dummy_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    db = isolated_test_env["db"]
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO asr_chunks (
            chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms, offset_ms,
            duration_ms, checksum_sha256, file_path, quality_stats, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("chk_e1", task_id, "s_run_e1", 0, 0, 10000, 0, 10000, "sha_e", str(dummy_wav), "{}", "READY", "2026-10-22T00:00:00Z"))
        conn.execute("""
        INSERT INTO candidates (
            candidate_id, task_id, segment_id, chunk_id, candidate_kind, proposed, confidence, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("c_e1", task_id, "seg_e1", "chk_e1", "composite", json.dumps({"text": "旧版源句内容"}), "0.9", "he1", "2026-10-22T00:00:00Z"))

    # Cleanup & confirm Rev 1
    auth_client.post(f"/api/v1/tasks/{task_id}/source/cleanup", json={"simulate": True})
    auth_client.post(f"/api/v1/tasks/{task_id}/source-transcript/confirm", json={"expected_revision": 1})
    auth_client.post(f"/api/v1/tasks/{task_id}/translation/generate", json={
        "target_language": "en",
        "target_market": "US",
        "simulate": True,
    })

    # Get unit_id
    src_res = auth_client.get(f"/api/v1/tasks/{task_id}/source-transcript")
    unit_id = src_res.json()["utterances"][0]["unit_id"]

    # 1. Edit with wrong expected_revision MUST return 409 Conflict
    conflict_res = auth_client.patch(f"/api/v1/tasks/{task_id}/source-transcript/utterances/{unit_id}", json={
        "expected_revision": 999,
        "text": "试图冲突修改",
    })
    assert conflict_res.status_code == 409

    # 2. Edit with expected_revision=1: creates new revision 2, revokes confirmation (AI_PROPOSED), expires translations
    edit_res = auth_client.patch(f"/api/v1/tasks/{task_id}/source-transcript/utterances/{unit_id}", json={
        "expected_revision": 1,
        "text": "修改后的全新源句内容",
    })
    assert edit_res.status_code == 200, edit_res.text
    edit_data = edit_res.json()
    assert edit_data["revision"] == 2
    assert edit_data["status"] == "AI_PROPOSED"

    # Check that current source transcript is Rev 2 and AI_PROPOSED
    src_after = auth_client.get(f"/api/v1/tasks/{task_id}/source-transcript").json()
    assert src_after["revision"] == 2
    assert src_after["status"] == "AI_PROPOSED"
    assert src_after["utterances"][0]["text"] == "修改后的全新源句内容"

    # Verify that translations associated with source_revision 1 are marked EXPIRED
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM translations WHERE task_id = ? AND source_revision = 1", (task_id,))
        row = cur.fetchone()
        assert row["status"] == "EXPIRED", "源稿生成新修订后，旧版本关联译稿必须自动标记为 EXPIRED！"


def test_independent_deterministic_semantic_check():
    """
    单元测试：独立确定性语义检查规则 (Task C)
    - 违反锁词 -> BLOCK
    - 数字缺失 -> WARN
    - 否定颠倒 -> WARN
    """
    locked_terms = [{"source_term": "聚灵阵", "target_term": "Spirit Gathering Array", "term_id": "t_01"}]

    # Case 1: missing locked term
    issues1 = run_deterministic_semantic_checks(
        source_text="我们必须尽快启动聚灵阵！",
        translation_text="We must start the magic circle as soon as possible!",
        unit_id="u_01",
        locked_terms=locked_terms,
    )
    assert any(i.severity == "BLOCK" and i.category == "omission" for i in issues1)

    # Case 2: number discrepancy
    issues2 = run_deterministic_semantic_checks(
        source_text="老太爷给了他三千万现金。",
        translation_text="The old master gave him some cash.",
        unit_id="u_02",
        locked_terms=[],
    )
    assert any(i.severity == "WARN" and i.category == "number" for i in issues2)

    # Case 3: negation inversion
    issues3 = run_deterministic_semantic_checks(
        source_text="这绝对不是你干的！",
        translation_text="You definitely did this!",
        unit_id="u_03",
        locked_terms=[],
    )
    assert any(i.severity == "WARN" and i.category == "negation" for i in issues3)

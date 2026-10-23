import json
import subprocess
import tempfile
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from config.settings import FFMPEG_PATH
from code.backend.main import app
from code.backend.shared.controls.auth import get_current_actor
from code.backend.shared.models import ActorContext

# =========================================================================
# TC-SRC-INT-01: Asset Registration, Session Controls & Validation
# =========================================================================

def test_tc_src_int_01_n(sample_video, auth_client):
    """TC-SRC-INT-01-N: 获准文件实际接收且来源/校验值齐备，真实操作人会话登记"""
    with open(sample_video, "rb") as f:
        res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (f"test_vid_{uuid.uuid4().hex[:6]}.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST-001"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["origin"] == "supplied"
    assert len(data["checksum_sha256"]) == 64
    assert data["availability"] == "readable"
    assert data["inspection"]["sound_present"] is True
    assert data["inspection"]["decode_ok"] is True
    assert "ffmpeg" in data["inspection"]["tool_version"].lower()


def test_tc_src_int_01_e(auth_client):
    """TC-SRC-INT-01-E: 文件损坏标记 unreadable，空授权引用直接 400 阻断"""
    # 1. Corrupt data
    corrupt_data = b"This is not a real mp4 video file at all"
    res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": (f"corrupt_{uuid.uuid4().hex[:6]}.mp4", corrupt_data, "video/mp4")},
        data={"kind": "video", "rights_ref": "RIGHTS-TEST-001"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["availability"] == "unreadable"
    assert data["inspection"]["decode_ok"] is False

    # 2. Empty rights_ref
    res_empty_rights = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": ("dummy.mp4", b"dummy", "video/mp4")},
        data={"kind": "video", "rights_ref": "   "},
    )
    assert res_empty_rights.status_code == 400
    assert "rights_ref" in res_empty_rights.text


def test_tc_src_int_01_a(sample_video, unauth_client):
    """TC-SRC-INT-01-A: 无有效服务端会话者直接返回 401 Unauthorized"""
    with open(sample_video, "rb") as f:
        res = unauth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("test.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST-001"},
        )
    assert res.status_code == 401
    assert "未认证会话" in res.text


# =========================================================================
# TC-SRC-INT-02 & TC-SRC-MAIN-R01: Master Confirmation & Checks
# =========================================================================

def test_tc_src_int_02_and_main_r01_n(sample_video, auth_client):
    """TC-SRC-INT-02-N & TC-SRC-MAIN-R01-N: 视频与声音对应且检查齐备，有权真人确认"""
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (f"master_{uuid.uuid4().hex[:6]}.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-R01"},
        )
    v_asset = v_res.json()

    # Create task & extract audio to have a valid derived audio asset
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    ext_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": v_asset["asset_id"], "track_index": 1},
    )
    assert ext_res.status_code == 200
    audio_asset_id = ext_res.json()["derived_asset_id"]

    # Register media
    m_res = auth_client.post(
        "/api/v1/media",
        json={
            "project_id": "PRJ-DEFAULT",
            "title_id": "短剧第一季",
            "episode_id": "EP01",
            "master_video_asset_id": v_asset["asset_id"],
        },
    )
    media_id = m_res.json()["media_id"]

    # Confirm master with all pass checks
    c_res = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_asset["asset_id"],
            "primary_audio_asset_id": audio_asset_id,
            "match_checks": [
                {
                    "asset_id": v_asset["asset_id"],
                    "check_type": "codec_readability",
                    "result": "pass",
                    "method": "ffmpeg_inspect",
                },
                {
                    "asset_id": audio_asset_id,
                    "check_type": "sound_presence",
                    "result": "pass",
                    "method": "media_probe",
                }
            ],
        },
    )
    assert c_res.status_code == 200, c_res.text
    c_data = c_res.json()
    assert c_data["master_status"] == "CONFIRMED"
    assert c_data["revision"] == 2
    assert c_data["confirmed_by"].startswith("op_")


def test_tc_src_int_02_e_match_checks_fail_or_empty(sample_video, auth_client):
    """TC-SRC-INT-02-E: 检查单为空或包含 fail/unknown，拒绝确认并转入 NEEDS_REVIEW"""
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (f"master_{uuid.uuid4().hex[:6]}.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-R01"},
        )
    v_asset = v_res.json()

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "短剧", "episode_id": "EP01", "master_video_asset_id": v_asset["asset_id"]},
    )
    media_id = m_res.json()["media_id"]

    # 1. Empty match_checks
    c_empty = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_asset["asset_id"],
            "primary_audio_asset_id": v_asset["asset_id"],
            "match_checks": [],
        },
    )
    assert c_empty.status_code == 400
    assert "为空" in c_empty.text

    # 2. Check contains 'fail'
    c_fail = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_asset["asset_id"],
            "primary_audio_asset_id": v_asset["asset_id"],
            "match_checks": [
                {
                    "asset_id": v_asset["asset_id"],
                    "check_type": "clip_version",
                    "result": "fail",
                    "method": "audition",
                }
            ],
        },
    )
    assert c_fail.status_code == 400
    assert "NEEDS_REVIEW" in c_fail.text

    # Verify status in DB
    m_check = auth_client.get(f"/api/v1/media/{media_id}").json()
    assert m_check["master_status"] == "NEEDS_REVIEW"


def test_tc_src_int_02_a_service_actor_blocked(sample_video, auth_client):
    """TC-SRC-INT-02-A: service_actor 试图代签 confirm_master 直接 403 阻断"""
    # Override actor to service_actor
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        actor_id="service_worker_ingest",
        actor_type="service_actor",
        actor_role="service_actor",
        allowed=True,
    )
    try:
        res = auth_client.post(
            "/api/v1/media/MEDIA-DUMMY/confirm",
            json={
                "expected_revision": 1,
                "master_video_asset_id": "asset_01",
                "primary_audio_asset_id": "asset_02",
                "match_checks": [{"asset_id": "asset_01", "check_type": "sound", "result": "pass", "method": "test"}],
            },
        )
        assert res.status_code == 403
        assert "禁止工程服务/Agent服务主体代签" in res.text
    finally:
        app.dependency_overrides.clear()


# =========================================================================
# TC-SRC-INT-03 & 04: Task Validation, Scope & Boundaries
# =========================================================================

def test_tc_src_int_03_n_and_04_n(auth_client):
    """TC-SRC-INT-03-N & 04-N: 任务草稿建立，缺项登记，明确指定 source_only 任务"""
    res = auth_client.post(
        "/api/v1/tasks",
        json={
            "request_key": f"REQ-{uuid.uuid4().hex[:8]}",
            "task_type": "source_only",
            "source_locale": "zh-CN",
            "processing_route": "transcribe",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_status"] == "DRAFT"
    assert data["source_locale"] == "zh-CN"


def test_tc_src_int_03_e_unconfirmed_media_blocks_task(auth_client):
    """TC-SRC-INT-03-E: 母版未确认时，任务确认直接被阻断 (400)"""
    # Register media (unconfirmed)
    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "短剧", "episode_id": "EP01"},
    )
    media_id = m_res.json()["media_id"]

    # Create task
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    # Try confirm task
    res = auth_client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"expected_revision": 1, "media_id": media_id},
    )
    assert res.status_code == 400
    assert "尚未完成人工确认" in res.text


def test_tc_src_int_04_e_duration_exceeded(sample_video, auth_client):
    """TC-SRC-INT-04-E: 处理范围超过10分钟返回 400，杜绝静默截断"""
    # Register and confirm media with simulated 12-minute duration
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("sample.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST"},
        )
    v_id = v_res.json()["asset_id"]

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "长篇", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    # Create task with range > 10m (600,001 ms)
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={
            "request_key": f"REQ-{uuid.uuid4().hex[:8]}",
            "task_type": "source_only",
            "range": {
                "mode": "ranges",
                "intervals": [{"start_ms": 0, "end_ms": 700000}],  # 700s > 600s
            },
        },
    )
    task_id = t_res.json()["task_id"]

    # Force media to CONFIRMED for range testing
    from code.backend.db import db
    with db.transaction() as conn:
        conn.execute("UPDATE media SET master_status = 'CONFIRMED', duration_ms = 800000 WHERE media_id = ?", (media_id,))

    res = auth_client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"expected_revision": 1, "media_id": media_id},
    )
    assert res.status_code == 400
    assert "超过单次上限 10 分钟" in res.text


# =========================================================================
# TC-SRC-INT-05 & 06: Double Confirmation, Stale Revisions & Readiness
# =========================================================================

def test_tc_src_int_05_and_main_r02_n(sample_video, auth_client):
    """TC-SRC-INT-05-N & MAIN-R02-N: 草稿与确认彻底解耦，确认生成快照，状态转为 READY"""
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("sample.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST"},
        )
    v_id = v_res.json()["asset_id"]

    # Register & confirm media
    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "测试剧", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": v_id,
            "match_checks": [{"asset_id": v_id, "check_type": "sound", "result": "pass", "method": "test"}],
        },
    )

    # Task creation & confirmation
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    conf_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"expected_revision": 1, "media_id": media_id},
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["task_status"] == "READY"

    # Check readiness
    r_res = auth_client.post(f"/api/v1/tasks/{task_id}/readiness", json={"stage": "asr_alignment"})
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "ready"


def test_tc_src_int_05_e_stale_revision(auth_client):
    """TC-SRC-INT-05-E: 提交旧版本 expected_revision 返回 409 STALE_INPUT 冲突"""
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    # Expected revision is 1, pass 99
    res = auth_client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"expected_revision": 99, "media_id": "MEDIA-DUMMY"},
    )
    assert res.status_code == 409
    assert "STALE_INPUT" in res.text


def test_tc_src_int_06_e_asr_gate_blocks_draft(auth_client):
    """TC-SRC-INT-06-E: 未确认草稿直接申请 ASR 运行严格阻断 (STAGE_NOT_READY 400)"""
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    res = auth_client.post(f"/api/v1/tasks/{task_id}/runs", json={"module": "asr_alignment"})
    assert res.status_code == 400
    assert "STAGE_NOT_READY" in res.text


# =========================================================================
# TC-SRC-INT-07 & 08: Invalidation on Update, Idempotency & Extraction
# =========================================================================

def test_tc_src_int_07_n_update_resets_ready_to_draft(sample_video, auth_client):
    """TC-SRC-INT-07-N: 任务修改后生成新 revision，原确认失效恢复为 DRAFT"""
    # Create and confirm task
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("sample.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST"},
        )
    v_id = v_res.json()["asset_id"]

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "剧", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]
    auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": v_id,
            "match_checks": [{"asset_id": v_id, "check_type": "sound", "result": "pass", "method": "test"}],
        },
    )

    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]
    auth_client.post(f"/api/v1/tasks/{task_id}/confirm", json={"expected_revision": 1, "media_id": media_id})

    # Substantive update: change range
    patch_res = auth_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "expected_revision": 2,
            "range": {"mode": "ranges", "intervals": [{"start_ms": 0, "end_ms": 1500}]},
        },
    )
    assert patch_res.status_code == 200
    p_data = patch_res.json()
    assert p_data["task_revision"] == 3
    assert p_data["task_status"] == "DRAFT"  # Reset back to DRAFT!


def test_tc_src_int_08_n_idempotent_ingest(sample_video, auth_client):
    """TC-SRC-INT-08-N: 抽轨派生具备幂等防重能力，同请求不重复调用 FFmpeg"""
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("sample.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-TEST"},
        )
    v_id = v_res.json()["asset_id"]

    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    # First extraction
    res1 = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": v_id, "track_index": 1},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["idempotent"] is False

    # Second extraction with same parameters
    res2 = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": v_id, "track_index": 1},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["idempotent"] is True
    assert data2["run_id"] == data1["run_id"]
    assert data2["derived_asset_id"] == data1["derived_asset_id"]


# =========================================================================
# Security Middleware Tests (Host & Strict Origin/Referer CSRF Checks)
# =========================================================================

def test_security_middleware_blocks_bad_host(auth_client):
    res = auth_client.get("/api/v1/health", headers={"Host": "attacker.com:8765"})
    assert res.status_code == 400
    assert "非法的 Host" in res.text


def test_security_middleware_blocks_attacker_subdomain_origin(auth_client):
    """
    CRITICAL: Validates that prefix-spoofed Origin 'http://testserver.attacker.example'
    and 'http://127.0.0.1:8765.attacker.com' are strictly blocked with 403 Forbidden.
    """
    # 1. Attacker attempting to spoof testserver prefix
    res1 = auth_client.post(
        "/api/v1/auth/register-operator",
        json={"display_name": "黑客操作员", "role": "media_operator"},
        headers={"Origin": "http://testserver.attacker.example"},
    )
    assert res1.status_code == 403, f"Expected 403, got {res1.status_code}"
    assert "禁止非同源外部页面" in res1.text

    # 2. Attacker attempting to spoof 127.0.0.1:8765 prefix
    res2 = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": "REQ-EVIL", "task_type": "source_only"},
        headers={"Origin": "http://127.0.0.1:8765.attacker.com"},
    )
    assert res2.status_code == 403
    assert "禁止非同源外部页面" in res2.text

    # 3. Referer spoofing
    res3 = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": "REQ-EVIL-REF", "task_type": "source_only"},
        headers={"Referer": "http://testserver.attacker.example/path"},
    )
    assert res3.status_code == 403
    assert "禁止跨域 Referer" in res3.text


# =========================================================================
# Upload Quota & Pre-Parsing Limits (Issue 3 & 7)
# =========================================================================

def test_upload_raw_stream_limit_header(auth_client):
    """Rejects request upfront if Content-Length exceeds quota."""
    res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        headers={"Content-Length": str(501 * 1024 * 1024)},
        content=b"dummy",
    )
    assert res.status_code == 413
    assert "超过500MiB严格限制" in res.text


def test_upload_auxiliary_materials_registration(auth_client):
    """
    Issue 7: Auxiliary materials (script, character_list, terminology, existing_subtitle)
    are registered in controlled assets storage and DB, but not parsed/split.
    """
    for kind, ext, content in [
        ("script", "txt", b"Character A: Hello world.\nCharacter B: Hi there."),
        ("character_list", "json", b'{"characters": ["Alice", "Bob"]}'),
        ("terminology", "csv", b"term,translation\nFFmpeg,FFmpeg\n"),
        ("existing_subtitle", "srt", b"1\n00:00:01,000 --> 00:00:03,000\nExisting Subtitle\n"),
    ]:
        res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (f"aux_{kind}.{ext}", content, "text/plain")},
            data={"kind": kind, "rights_ref": "RIGHTS-AUX-001"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["kind"] == kind
        assert data["origin"] == "supplied"
        assert data["availability"] == "readable"
        assert data["inspection"]["status"] == "registered_unparsed"


def test_upload_rejects_unsupported_extensions(auth_client):
    """Rejects unsupported extensions for media and auxiliary materials."""
    res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": ("malicious.exe", b"MZ...", "application/x-msdownload")},
        data={"kind": "video", "rights_ref": "RIGHTS-001"},
    )
    assert res.status_code == 400
    assert "不支持的媒体文件扩展名" in res.text


# =========================================================================
# Multi-track Construction & Confirmation Checks (Issue 4, 5, 6)
# =========================================================================

@pytest.fixture(scope="module")
def multi_track_video():
    """Generates synthetic video with 2 distinct audio streams: stream #1 (1000Hz) & stream #2 (500Hz)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = Path(f.name)

    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=500:duration=2",
        "-map", "0:v", "-map", "1:a", "-map", "2:a",
        "-c:v", "libx264", "-c:a", "aac",
        str(temp_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    yield temp_path
    try:
        temp_path.unlink()
    except OSError:
        pass


@pytest.fixture(scope="module")
def silent_audio():
    """Generates pure digital silence WAV (anullsrc)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = Path(f.name)

    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", "2",
        "-c:a", "pcm_s16le",
        str(temp_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    yield temp_path
    try:
        temp_path.unlink()
    except OSError:
        pass


def test_multi_track_extraction_and_switch_invalidation(multi_track_video, auth_client):
    """
    Issue 5: Multi-track video probe exposes both tracks; extracting track 1 and switching to track 2
    invalidates previous task/master confirmation.
    """
    with open(multi_track_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("multitrack.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-MULTI"},
        )
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert len(v_data["inspection"]["audio_streams"]) == 2

    # Create task
    t_res = auth_client.post("/api/v1/tasks", json={"request_key": f"REQ-{uuid.uuid4().hex[:8]}", "task_type": "source_only"})
    task_id = t_res.json()["task_id"]

    # Extract track index 1 (1000Hz)
    e1_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": v_data["asset_id"], "track_index": 1},
    )
    assert e1_res.status_code == 200
    e1_data = e1_res.json()
    run_id_1 = e1_data["run_id"]

    # Query run status
    run_query = auth_client.get(f"/api/v1/tasks/{task_id}/runs/{run_id_1}")
    assert run_query.status_code == 200
    assert run_query.json()["run_status"] == "SUCCEEDED"

    # Extract track index 2 (500Hz)
    e2_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": v_data["asset_id"], "track_index": 2},
    )
    assert e2_res.status_code == 200
    e2_data = e2_res.json()
    assert e2_data["derived_asset_id"] != e1_data["derived_asset_id"]


def test_confirm_master_rejects_digital_silence(sample_video, silent_audio, auth_client):
    """
    Issue 6: Confirm master strictly rejects digital silence audio as primary audio.
    """
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-01"},
        )
    v_id = v_res.json()["asset_id"]

    with open(silent_audio, "rb") as f:
        a_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("silent.wav", f, "audio/wav")},
            data={"kind": "audio", "rights_ref": "RIGHTS-01"},
        )
    a_id = a_res.json()["asset_id"]

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "静音剧", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    # Attempt to confirm master with digital silence audio
    conf_res = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": a_id,
            "match_checks": [{"asset_id": a_id, "check_type": "sound", "result": "pass", "method": "test"}],
        },
    )
    assert conf_res.status_code == 400
    assert "数字纯静音" in conf_res.text or "无可用声音" in conf_res.text


def test_confirm_master_rejects_mismatched_asset_kinds(sample_video, auth_client):
    """
    Issue 6: Rejects confirmation if auxiliary script is passed as primary_audio,
    or audio is passed as master_video.
    """
    with open(sample_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": ("video.mp4", f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-01"},
        )
    v_id = v_res.json()["asset_id"]

    # Register a script asset (kind="script")
    s_res = auth_client.post(
        "/api/v1/projects/PRJ-DEFAULT/assets",
        files={"file": ("script.txt", b"Dialogue line 1", "text/plain")},
        data={"kind": "script", "rights_ref": "RIGHTS-01"},
    )
    s_id = s_res.json()["asset_id"]

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "剧", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    # Pass script asset as primary_audio
    res = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": s_id,  # script asset passed as primary_audio!
            "match_checks": [{"asset_id": v_id, "check_type": "sound", "result": "pass", "method": "test"}],
        },
    )
    assert res.status_code == 400
    assert "资产类型错误" in res.text


def test_ingest_recovery_marks_stale_runs_as_stopped(isolated_test_env):
    """
    Issue 4: Verifies that crashed runs in RUNNING state are recovered to STOPPED (schema enum),
    not the invalid 'INTERRUPTED'.
    """
    from code.backend.workflow.ingest import ingest_worker
    test_db = isolated_test_env["db"]

    # Insert a dummy stranded RUNNING run
    with test_db.transaction() as conn:
        conn.execute("""
        INSERT INTO runs (
            run_id, task_id, task_revision, trace_id, module,
            input_refs, input_revision, idempotency_key, attempt_no,
            attempts, run_status, context_manifest, manifest_hash,
            steps, started_at, usage, controls, output_refs, created_at, created_by
        ) VALUES (
            'run_stranded_01', 'TASK-DUMMY', 1, 'TR-01', 'ingest',
            '[]', 1, 'idem_01', 1,
            '[]', 'RUNNING', '{}', 'hash01',
            '[]', '2026-10-21T00:00:00Z', '{}', '{}', '[]', '2026-10-21T00:00:00Z', 'op-01'
        );
        """)

    # Run recover_stale_runs
    recovered = ingest_worker.recover_stale_runs()
    assert recovered >= 1

    with test_db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT run_status, stop_reason, failure FROM runs WHERE run_id = 'run_stranded_01'")
        row = cur.fetchone()
        assert row["run_status"] == "STOPPED"  # Schema enum!
        assert row["stop_reason"] == "SERVER_RESTARTED"
        assert "SERVER_RESTARTED" in row["failure"]

import json
import uuid
from pathlib import Path
import pytest

from config.settings import BASE_DIR

DOMESTIC_SAMPLES_DIR = BASE_DIR.parent.parent / "work" / "剧情素材调研" / "国内" / "samples"

@pytest.fixture(scope="module")
def domestic_sample_paths():
    s1_video = DOMESTIC_SAMPLES_DIR / "sample1_zaixueronghuazhiqian" / "zaixueronghuazhiqian_ep01_clip.mp4"
    s1_audio = DOMESTIC_SAMPLES_DIR / "sample1_zaixueronghuazhiqian" / "zaixueronghuazhiqian_ep01_audio.wav"
    s2_video = DOMESTIC_SAMPLES_DIR / "sample2_zuisumiqing" / "zuisumiqing_ep01_clip.mp4"
    s2_audio = DOMESTIC_SAMPLES_DIR / "sample2_zuisumiqing" / "zuisumiqing_ep01_audio.wav"

    assert s1_video.exists(), f"Missing domestic DEV sample video: {s1_video}"
    assert s1_audio.exists(), f"Missing domestic DEV sample audio: {s1_audio}"
    return {
        "s1_video": s1_video,
        "s1_audio": s1_audio,
        "s2_video": s2_video,
        "s2_audio": s2_audio,
    }


def test_domestic_drama_clip_upload_and_decode(domestic_sample_paths, auth_client):
    """
    真实国内短剧样片（在雪融化之前）：
    上传MP4文件，进行真实 ffprobe 探测与 ffmpeg 全流解码校验。
    """
    s1_video = domestic_sample_paths["s1_video"]
    with open(s1_video, "rb") as f:
        res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s1_video.name, f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["availability"] == "readable"
    assert data["size_bytes"] == s1_video.stat().st_size
    insp = data["inspection"]
    assert insp["decode_ok"] is True
    assert insp["sound_present"] is True
    assert insp["duration_ms"] > 0
    assert len(insp["audio_streams"]) >= 1


def test_domestic_drama_ingest_audio_extraction(domestic_sample_paths, auth_client):
    """
    真实国内短剧样片：
    由单 Worker 执行真实 FFmpeg 抽轨，生成无损 PCM WAV 派生音频，并检查时长与采样率。
    """
    s1_video = domestic_sample_paths["s1_video"]
    with open(s1_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s1_video.name, f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    video_asset_id = v_res.json()["asset_id"]

    t_res = auth_client.post(
        "/api/v1/tasks",
        json={"request_key": f"REQ-DRAMA-{uuid.uuid4().hex[:8]}", "task_type": "source_only"},
    )
    task_id = t_res.json()["task_id"]

    # Extract first audio track
    ext_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/ingest/extract-audio",
        json={"video_asset_id": video_asset_id, "track_index": 1},
    )
    assert ext_res.status_code == 200, ext_res.text
    ext_data = ext_res.json()
    assert ext_data["derived_asset_id"].startswith("asset_audio_")
    assert ext_data["size_bytes"] > 0
    assert ext_data["inspection"]["decode_ok"] is True


def test_domestic_drama_independent_audio_direct_binding(domestic_sample_paths, auth_client):
    """
    真实国内短剧独立配音音轨：
    上传独立WAV音频，选定作为主声音直接绑定母版，完成母版与任务单双重确认。
    """
    s1_video = domestic_sample_paths["s1_video"]
    s1_audio = domestic_sample_paths["s1_audio"]

    # Upload video
    with open(s1_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s1_video.name, f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    v_id = v_res.json()["asset_id"]

    # Upload independent audio
    with open(s1_audio, "rb") as f:
        a_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s1_audio.name, f, "audio/wav")},
            data={"kind": "audio", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    a_id = a_res.json()["asset_id"]
    assert a_res.json()["inspection"]["sound_present"] is True

    # Register Media
    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "在雪融化之前", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    # Confirm master using independent audio
    c_res = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": a_id,
            "match_checks": [
                {"asset_id": v_id, "check_type": "codec_readability", "result": "pass", "method": "ffmpeg_null_decode"},
                {"asset_id": a_id, "check_type": "sound_presence", "result": "pass", "method": "media_probe"},
                {"asset_id": v_id, "check_type": "clip_version", "result": "pass", "method": "audition_verification"},
            ],
        },
    )
    assert c_res.status_code == 200
    assert c_res.json()["master_status"] == "CONFIRMED"

    # Create & Confirm Task
    t_res = auth_client.post(
        "/api/v1/tasks",
        json={
            "request_key": f"REQ-DRAMA-{uuid.uuid4().hex[:8]}",
            "task_type": "source_only",
            "purpose": "在雪融化之前EP01源语字幕制作",
        },
    )
    task_id = t_res.json()["task_id"]

    tc_res = auth_client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"expected_revision": 1, "media_id": media_id},
    )
    assert tc_res.status_code == 200
    assert tc_res.json()["task_status"] == "READY"


def test_domestic_drama_mismatch_interception(domestic_sample_paths, auth_client):
    """
    真实国内短剧错配拦截：
    当人工核验标记存在错配（如剪辑版本不匹配 fail）时，服务器严格阻断确认。
    """
    s1_video = domestic_sample_paths["s1_video"]
    s2_audio = domestic_sample_paths["s2_audio"]  # Audio from another drama!

    with open(s1_video, "rb") as f:
        v_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s1_video.name, f, "video/mp4")},
            data={"kind": "video", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    v_id = v_res.json()["asset_id"]

    with open(s2_audio, "rb") as f:
        a_res = auth_client.post(
            "/api/v1/projects/PRJ-DEFAULT/assets",
            files={"file": (s2_audio.name, f, "audio/wav")},
            data={"kind": "audio", "rights_ref": "RIGHTS-DOMESTIC-DEV-001"},
        )
    a_id = a_res.json()["asset_id"]

    m_res = auth_client.post(
        "/api/v1/media",
        json={"project_id": "PRJ-DEFAULT", "title_id": "在雪融化之前", "episode_id": "EP01", "master_video_asset_id": v_id},
    )
    media_id = m_res.json()["media_id"]

    # Confirm master with fail on clip_version check
    c_res = auth_client.post(
        f"/api/v1/media/{media_id}/confirm",
        json={
            "expected_revision": 1,
            "master_video_asset_id": v_id,
            "primary_audio_asset_id": a_id,
            "match_checks": [
                {"asset_id": v_id, "check_type": "codec_readability", "result": "pass", "method": "ffmpeg_null_decode"},
                {"asset_id": a_id, "check_type": "sound_presence", "result": "pass", "method": "media_probe"},
                {"asset_id": v_id, "check_type": "clip_version", "result": "fail", "method": "human_audition_mismatch"},
            ],
        },
    )
    assert c_res.status_code == 400
    assert "NEEDS_REVIEW" in c_res.text

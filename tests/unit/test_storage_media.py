import io
import subprocess
import tempfile
from pathlib import Path
import pytest

from config.settings import FFMPEG_PATH, FFPROBE_PATH
from code.backend.shared.storage import (
    ControlledStorage,
    FileSizeLimitExceededError,
    PathTraversalError,
)
from code.backend.shared.tools.media import (
    MediaDurationLimitError,
    MediaError,
    MediaTool,
)

# =========================================================================
# Controlled Storage Unit Tests
# =========================================================================

def test_storage_save_and_sha256(tmp_path):
    storage = ControlledStorage(base_dir=tmp_path / "storage")
    data = b"Hello, Subtitle Workflow Intake!"
    sha, size, rel_uri, mime = storage.save_bytes(
        data=data,
        filename="test.txt",
        project_id="PRJ-01",
        asset_id="asset-001",
    )
    assert size == len(data)
    assert len(sha) == 64
    assert rel_uri == "PRJ-01/asset-001/test.txt"
    real_path = storage.get_real_path(rel_uri)
    assert real_path.exists()
    assert real_path.read_bytes() == data


def test_storage_size_limit(tmp_path):
    storage = ControlledStorage(base_dir=tmp_path / "storage")
    big_data = b"X" * 1024
    with pytest.raises(FileSizeLimitExceededError):
        storage.save_bytes(
            data=big_data,
            filename="big.bin",
            project_id="PRJ-01",
            asset_id="asset-001",
            max_bytes=512,  # 512 bytes limit
        )


def test_storage_path_traversal_boundaries(tmp_path):
    base_dir = tmp_path / "storage"
    sibling_dir = tmp_path / "storage_sibling"
    sibling_dir.mkdir(parents=True, exist_ok=True)
    storage = ControlledStorage(base_dir=base_dir)

    # 1. Traversal in project_id or asset_id
    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "file.txt", project_id="../escape", asset_id="asset01")

    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "file.txt", project_id="PRJ-01", asset_id="../../escape")

    # 2. Dangerous filenames
    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "..", project_id="PRJ-01", asset_id="asset01")

    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "file\x00.txt", project_id="PRJ-01", asset_id="asset01")

    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "CON.txt", project_id="PRJ-01", asset_id="asset01")

    with pytest.raises(PathTraversalError):
        storage.save_bytes(b"data", "NUL", project_id="PRJ-01", asset_id="asset01")

    # 3. get_real_path traversal check
    with pytest.raises(PathTraversalError):
        storage.get_real_path("../storage_sibling/secret.txt")

    with pytest.raises(PathTraversalError):
        storage.get_real_path("/etc/passwd")

    with pytest.raises(PathTraversalError):
        storage.get_real_path("PRJ-01/asset01/../../escape.txt")


# =========================================================================
# Media Tool Unit Tests
# =========================================================================

@pytest.fixture(scope="module")
def synthetic_sample_video():
    """Generates a short 2-second valid MP4 with video (stream #0) and audio (stream #1)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = Path(f.name)

    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-c:a", "aac",
        str(temp_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    yield temp_path
    try:
        temp_path.unlink()
    except OSError:
        pass


def test_media_tool_dynamic_versions():
    tool = MediaTool()
    v_ffmpeg = tool.get_ffmpeg_version()
    v_ffprobe = tool.get_ffprobe_version()
    assert "ffmpeg" in v_ffmpeg.lower()
    assert "ffprobe" in v_ffprobe.lower()


def test_media_tool_probe_and_decode(synthetic_sample_video):
    tool = MediaTool()
    insp = tool.inspect_file(synthetic_sample_video)
    assert insp["decode_ok"] is True
    assert insp["sound_present"] is True
    assert len(insp["video_streams"]) == 1
    assert len(insp["audio_streams"]) == 1
    assert insp["duration_ms"] is not None and insp["duration_ms"] > 0
    assert insp["decode_coverage"]["all_tracks_checked"] is True


def test_media_tool_duration_flag_retains_original(synthetic_sample_video):
    """
    Rule: Original files exceeding 10 minutes are retained and inspected (not unlinked).
    Processing limits are enforced at Task range confirmation.
    """
    tool = MediaTool()
    # Set limit to 1 second (1000 ms), sample is 2 seconds
    insp = tool.inspect_file(synthetic_sample_video, max_duration_ms=1000)
    assert insp["exceeds_task_limit"] is True
    assert insp["decode_ok"] is True
    assert insp["duration_ms"] is not None and insp["duration_ms"] > 1000
    assert synthetic_sample_video.exists()


def test_media_tool_digital_silence_detection(tmp_path):
    """
    Distinguishes digital silence from usable sound.
    """
    silent_wav = tmp_path / "silent.wav"
    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", "2",
        "-c:a", "pcm_s16le",
        str(silent_wav),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    tool = MediaTool()
    vol = tool.detect_volume(silent_wav)
    assert vol["is_silent"] is True
    assert vol["usable"] is False


def test_media_tool_corrupted_file(tmp_path):
    tool = MediaTool()
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_bytes(b"NOT_A_VALID_VIDEO_FILE_HEADER")

    insp = tool.inspect_file(corrupt_file)
    assert insp["decode_ok"] is False
    assert insp["measurement_status"] == "failed"
    assert insp["decode_error"] is not None


def test_media_tool_extract_audio_track(synthetic_sample_video, tmp_path):
    tool = MediaTool()
    out_wav = tmp_path / "out.wav"
    # Audio stream is index 1
    res = tool.extract_audio_track(
        video_path=synthetic_sample_video,
        stream_index=1,
        output_wav_path=out_wav,
    )
    assert out_wav.exists()
    assert res["codec"] == "pcm_s16le"
    assert res["channels"] == 1


def test_media_tool_rejects_extracting_video_stream_as_audio(synthetic_sample_video, tmp_path):
    tool = MediaTool()
    out_wav = tmp_path / "bad.wav"
    # Video stream is index 0
    with pytest.raises(MediaError) as exc_info:
        tool.extract_audio_track(
            video_path=synthetic_sample_video,
            stream_index=0,
            output_wav_path=out_wav,
        )
    assert "VIDEO stream" in str(exc_info.value)

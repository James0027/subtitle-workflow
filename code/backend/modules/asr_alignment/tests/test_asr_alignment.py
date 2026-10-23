import json
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest
from config.settings import FFMPEG_PATH, FFPROBE_PATH
from code.backend.modules.asr_alignment import (
    check_cloud_authorization,
    check_cross_slice_boundaries,
    map_chunks_to_master,
    match_glossary,
    mock_transcribe_chunk,
    transcribe_chunk_gemini,
)
from code.backend.modules.asr_alignment.contract import (
    ChunkTranscriptionResult,
    EntityCandidate,
    TimingCandidate,
    UncertaintyCandidate,
)
from code.backend.shared.tools.media import MediaTool


@pytest.fixture
def test_audio_25s(tmp_path):
    """Generates a sample 25.5 second PCM WAV audio file with sine wave and silence."""
    wav_path = tmp_path / "test_25s.wav"
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=25.5",
        "-c:a", "pcm_s16le",
        str(wav_path),
    ]
    subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return wav_path


def test_slice_audio_fixed_10s_and_tail_duration(test_audio_25s, tmp_path):
    """
    Verifies fixed 10-second slice logic:
    - 25.5s audio should slice into 3 chunks: 10.0s, 10.0s, and 5.5s (tail slice real duration).
    - Chunk offset, duration, and SHA-256 must be computed accurately.
    """
    tool = MediaTool(ffmpeg_path=FFMPEG_PATH, ffprobe_path=FFPROBE_PATH)
    out_dir = tmp_path / "slices"
    chunks = tool.slice_audio_fixed(test_audio_25s, out_dir, slice_duration_sec=10.0)

    assert len(chunks) == 3
    # Chunk 0
    assert chunks[0]["chunk_id"] == "chunk_000"
    assert chunks[0]["offset_ms"] == 0
    assert chunks[0]["duration_ms"] == 10000
    assert len(chunks[0]["checksum_sha256"]) == 64
    assert Path(chunks[0]["file_path"]).exists()

    # Chunk 1
    assert chunks[1]["chunk_id"] == "chunk_001"
    assert chunks[1]["offset_ms"] == 10000
    assert chunks[1]["duration_ms"] == 10000
    assert len(chunks[1]["checksum_sha256"]) == 64

    # Chunk 2 (Tail slice preserving real duration: 5500 ms)
    assert chunks[2]["chunk_id"] == "chunk_002"
    assert chunks[2]["offset_ms"] == 20000
    assert chunks[2]["duration_ms"] == 5500
    assert len(chunks[2]["checksum_sha256"]) == 64


def test_measure_audio_quality_astats_and_unmeasured_fields(test_audio_25s):
    """
    Verifies real FFmpeg astats measurement and explicit unmeasured flags:
    - Real peak_level_dbfs and rms_level_dbfs.
    - Explicit unmeasured SNR, P95 boundary error, and calibration score (None / 未测).
    """
    tool = MediaTool(ffmpeg_path=FFMPEG_PATH, ffprobe_path=FFPROBE_PATH)
    stats = tool.measure_audio_quality(test_audio_25s)

    assert stats["channels"] == 1
    assert stats["sample_rate_hz"] == 44100
    assert stats["peak_level_dbfs"] is not None
    assert stats["rms_level_dbfs"] is not None
    assert stats["usable"] is True
    assert stats["is_silent"] is False

    # Strict contract: unmeasured fields must be None and labeled 未测
    assert stats["snr_db"] is None
    assert "未测" in stats["snr_status"]
    assert stats["p95_boundary_error_ms"] is None
    assert "未测" in stats["p95_status"]
    assert stats["calibrated_confidence"] is None
    assert "未测" in stats["calibration_status"]


def test_cloud_authorization_boundary_blocks_unauthorized(monkeypatch):
    """
    Strict boundary test:
    Without explicit authorization flags, check_cloud_authorization reports '待配置/待授权'
    and transcribe_chunk_gemini raises PermissionError.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED", "0")
    monkeypatch.setenv("GEMINI_BUDGET_AUTHORIZED", "0")

    auth = check_cloud_authorization()
    assert auth.allowed_in_pilot is False
    assert auth.status == "待配置/待授权"
    assert len(auth.missing_items) == 3

    # Attempting to call Gemini adapter must raise PermissionError
    dummy_file = Path("dummy.wav")
    with pytest.raises(PermissionError) as exc_info:
        transcribe_chunk_gemini(dummy_file, "chunk_000", 0, 10000)
    assert "待配置/待授权" in str(exc_info.value)


def test_mock_transcription_marked_simulated():
    """
    Verifies that controlled mock transcription is strictly marked SIMULATED.
    """
    mock_res = mock_transcribe_chunk("chunk_000", 0, 10000, is_silent=False)
    assert mock_res.is_simulated is True
    assert "SIMULATED" in mock_res.confidence_label
    assert mock_res.text != ""


def test_cross_slice_boundary_detection():
    """
    Verifies that boundary uncertainties or mid-sentence breaks between adjacent chunks
    are accurately identified as boundary truncation issues.
    """
    c1 = ChunkTranscriptionResult(
        chunk_id="chunk_000",
        offset_ms=0,
        duration_ms=10000,
        text="我们明天去",  # No terminator, mid-sentence cut
        timing_candidates=[],
        uncertainties=[UncertaintyCandidate(start_ms=9000, end_ms=10000, description="切点截断疑点")],
        overlap_candidates=[],
        entity_candidates=[],
    )
    c2 = ChunkTranscriptionResult(
        chunk_id="chunk_001",
        offset_ms=10000,
        duration_ms=10000,
        text="快手短剧拍摄基地报到。",
        timing_candidates=[],
        uncertainties=[],
        overlap_candidates=[],
        entity_candidates=[],
    )

    issues = check_cross_slice_boundaries([c1, c2])
    assert len(issues) >= 1
    assert issues[0]["category"] == "boundary_truncation"
    assert "chunk_000" in issues[0]["detail"]


def test_glossary_matching_matched_and_pending_confirmation():
    """
    Verifies glossary matching:
    - Matched entities marked 'matched'.
    - Unmatched entities marked 'pending_confirmation' (待确认).
    """
    entities = [
        EntityCandidate(name="快手", category="brand"),
        EntityCandidate(name="张三丰", category="person"),
    ]
    glossary = [
        {"term": "快手", "term_id": "TERM-001"}
    ]

    matched = match_glossary(entities, glossary)
    assert matched[0].match_status == "matched"
    assert matched[0].glossary_ref == "TERM-001"
    assert matched[1].match_status == "pending_confirmation"
    assert matched[1].glossary_ref is None


def test_map_chunks_to_master_no_sentence_interpolation():
    """
    Strict rule: Unknown sentence-level timestamps MUST NOT be evenly interpolated/faked.
    If timing candidates are missing, timing_precise is False and master range
    falls back to the verified physical chunk range.
    """
    chunks = [
        {"chunk_id": "chunk_000", "offset_ms": 10000, "duration_ms": 10000},
    ]
    results = [
        ChunkTranscriptionResult(
            chunk_id="chunk_000",
            offset_ms=10000,
            duration_ms=10000,
            text="整片源语听写文字",
            timing_candidates=[],  # No fine-grained timings
            uncertainties=[],
            overlap_candidates=[],
            entity_candidates=[],
        )
    ]

    segments = map_chunks_to_master(chunks, results)
    assert len(segments) == 1
    assert segments[0].master_start_ms == 10000
    assert segments[0].master_end_ms == 20000
    assert segments[0].timing_precise is False  # Explicit fallback, no fake sentence timestamps!

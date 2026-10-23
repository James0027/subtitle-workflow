import os
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = DATA_DIR / "storage"
CHUNKS_DIR = DATA_DIR / "chunks"
DB_PATH = DATA_DIR / "workflow.db"
WEB_DIR = BASE_DIR / "code" / "web"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# Media Tools
WINGET_FFMPEG = Path(
    r"C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
)
WINGET_FFPROBE = Path(
    r"C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"
)

FFMPEG_PATH = str(WINGET_FFMPEG) if WINGET_FFMPEG.exists() else (shutil.which("ffmpeg") or "ffmpeg")
FFPROBE_PATH = str(WINGET_FFPROBE) if WINGET_FFPROBE.exists() else (shutil.which("ffprobe") or "ffprobe")

# Media Constraints
MAX_MEDIA_SIZE_BYTES = 500 * 1024 * 1024  # 500 MiB strict limit
MAX_AUXILIARY_SIZE_BYTES = 50 * 1024 * 1024  # 50 MiB strict limit for auxiliary files
MAX_PROCESS_DURATION_MS = 10 * 60 * 1000  # 10 minutes (600,000 ms) strict limit

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm",
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg",
}
ALLOWED_AUXILIARY_EXTENSIONS = {
    ".txt", ".docx", ".pdf", ".json", ".csv", ".xlsx",
    ".srt", ".vtt", ".ass",
}

# Environment & Testing
TEST_MODE = os.environ.get("SUBTITLE_TEST_MODE", "0") in ("1", "true", "True")

# Gemini ASR Configuration & Authorization Boundaries
# Configurable Flash candidate (supporting audio input and structured JSON response)
GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.5-flash-lite")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Explicit independent authorization gates: material outbound and billing budget
GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED = os.environ.get("GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED", "0") in ("1", "true", "True")
GEMINI_BUDGET_AUTHORIZED = os.environ.get("GEMINI_BUDGET_AUTHORIZED", "0") in ("1", "true", "True")

# ASR Slice Configuration
ASR_SLICE_DURATION_SEC = 10.0  # Pilot default fixed 10s slice

# Service
HOST = "127.0.0.1"
PORT = 8765

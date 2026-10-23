import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from code.backend.db import Database, db
from code.backend.shared.controls.auth import get_current_actor, register_local_operator
from code.backend.shared.models import ActorContext
from code.backend.shared.storage import ControlledStorage, default_storage
from code.backend.main import app

@pytest.fixture(autouse=True)
def isolated_test_env(tmp_path, monkeypatch):
    """
    Ensures EVERY test runs with an isolated database and isolated storage directory,
    never modifying data/workflow.db or data/storage.
    """
    test_db_path = tmp_path / "test_workflow.db"
    test_storage_dir = tmp_path / "test_storage"
    test_chunks_dir = tmp_path / "test_chunks"
    test_storage_dir.mkdir(parents=True, exist_ok=True)
    test_chunks_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate isolated db and storage
    test_db = Database(db_path=test_db_path)
    test_storage = ControlledStorage(base_dir=test_storage_dir)

    # Patch global instances
    monkeypatch.setattr("code.backend.db.db", test_db)
    monkeypatch.setattr("code.backend.shared.controls.auth.db", test_db)
    monkeypatch.setattr("code.backend.workflow.ingest.db", test_db)
    monkeypatch.setattr("code.backend.main.db", test_db)

    monkeypatch.setattr("code.backend.shared.storage.default_storage", test_storage)
    monkeypatch.setattr("code.backend.workflow.ingest.default_storage", test_storage)
    monkeypatch.setattr("code.backend.main.default_storage", test_storage)
    monkeypatch.setattr("code.backend.main.CHUNKS_DIR", test_chunks_dir)

    # Patch translation module DB instances
    try:
        import code.backend.modules.translation.knowledge as t_know
        import code.backend.modules.translation.source_cleanup as t_clean
        import code.backend.modules.translation.handler as t_hand
        monkeypatch.setattr(t_know, "db", test_db)
        monkeypatch.setattr(t_know.knowledge_service, "db", test_db)
        monkeypatch.setattr(t_clean, "db", test_db)
        monkeypatch.setattr(t_hand, "db", test_db)
    except Exception:
        pass

    # Enable TEST_MODE for testing environment
    monkeypatch.setattr("config.settings.TEST_MODE", True)
    monkeypatch.setattr("code.backend.main.TEST_MODE", True)

    # Register default test operator in isolated db
    reg = register_local_operator(display_name="测试操作员-张工", role="media_operator")
    test_token = reg["session_token"]
    test_op_id = reg["operator_id"]

    yield {
        "db": test_db,
        "storage": test_storage,
        "operator_id": test_op_id,
        "session_token": test_token,
    }

    # Clear dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(isolated_test_env):
    """
    TestClient with pre-configured session cookie and REAL lifespan lifecycle entered via context manager.
    """
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.cookies.set("session_token", isolated_test_env["session_token"])
        yield client


@pytest.fixture
def unauth_client():
    """
    TestClient without session authentication, with REAL lifespan lifecycle.
    """
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        yield client


@pytest.fixture
def sample_video():
    """Generates a small valid MP4 test video with video and audio streams."""
    import subprocess
    from config.settings import FFMPEG_PATH

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

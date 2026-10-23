import hashlib
import json
import urllib.parse
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio
from pydantic import BaseModel
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Header,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from config.settings import (
    ALLOWED_AUXILIARY_EXTENSIONS,
    ALLOWED_MEDIA_EXTENSIONS,
    ASR_SLICE_DURATION_SEC,
    CHUNKS_DIR,
    FFMPEG_PATH,
    FFPROBE_PATH,
    GEMINI_MODEL_ID,
    HOST,
    MAX_AUXILIARY_SIZE_BYTES,
    MAX_MEDIA_SIZE_BYTES,
    MAX_PROCESS_DURATION_MS,
    PORT,
    STORAGE_DIR,
    TEST_MODE,
    WEB_DIR,
)
from code.backend.db import db, utc_now_iso
from code.backend.modules.asr_alignment import (
    ASRStatusResponse,
    check_cloud_authorization,
    check_cross_slice_boundaries,
    map_chunks_to_master,
    mock_transcribe_chunk,
    transcribe_chunk_gemini,
)
from code.backend.modules.asr_alignment.contract import (
    ChunkTranscriptionResult,
    EntityCandidate,
    MasterSegmentResult,
    OverlapCandidate,
    TimingCandidate,
    UncertaintyCandidate,
)
from code.backend.modules.asr_alignment.handler import GeminiProviderError, sanitize_error_message
from code.backend.modules.translation.contract import TranslationRevisionRequest, ConfirmAllTranslationsRequest
from code.backend.modules.translation import (
    ConfirmSourceTranscriptRequest,
    EditTranslationRequest,
    EditUtteranceRequest,
    GenerateTranslationRequest,
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    RollbackTranslationRequest,
    execute_source_cleanup,
    execute_translation_pipeline,
    knowledge_service,
)
from code.backend.shared.controls.auth import (
    create_operator_session,
    get_current_actor,
    get_session_info,
    list_local_operators,
    register_local_operator,
    require_human_actor,
    require_permission,
)
from code.backend.shared.models import (
    ASRTranscribeRequest,
    ActorContext,
    ConfirmEntityRequest,
    ConfirmMasterRequest,
    ConfirmTaskRequest,
    CreateTaskRequest,
    EditCandidateRequest,
    ExtractAudioRequest,
    LoginRequest,
    RegisterMediaRequest,
    RegisterOperatorRequest,
    RequestRunRequest,
    UpdateTaskRequest,
)
from code.backend.shared.storage import (
    FileSizeLimitExceededError,
    PathTraversalError,
    default_storage,
)
from code.backend.shared.tools.media import (
    MediaDecodeError,
    MediaDurationLimitError,
    MediaProbeError,
    MediaTimeoutError,
    media_tool,
)
from code.backend.workflow.ingest import IngestError, ingest_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: recover any stranded running runs from previous session crashes to STOPPED (schema enum)
    ingest_worker.recover_stale_runs()
    yield


app = FastAPI(
    title="Subtitle Intake & Storage Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Standard Allowed Origins and Hosts
DEFAULT_ALLOWED_ORIGINS = {
    "http://127.0.0.1:8765",
    "http://localhost:8765",
}
DEFAULT_ALLOWED_HOSTS = {
    "127.0.0.1:8765",
    "localhost:8765",
    "127.0.0.1",
    "localhost",
}

def is_test_mode() -> bool:
    return bool(getattr(settings, "TEST_MODE", False) and globals().get("TEST_MODE", False))

def get_allowed_origins() -> set:
    origins = set(DEFAULT_ALLOWED_ORIGINS)
    if is_test_mode():
        origins.add("http://testserver")
    return origins

def get_allowed_hosts() -> set:
    hosts = set(DEFAULT_ALLOWED_HOSTS)
    if is_test_mode():
        hosts.add("testserver")
    return hosts

def parse_origin_norm(url_str: str) -> Optional[str]:
    """
    Parses origin or referer into strictly normalized scheme://host[:port].
    Strips path, query, and trailing slashes.
    """
    try:
        p = urllib.parse.urlparse(url_str.strip())
        if not p.scheme or not p.netloc:
            return None
        # Normalize netloc to lowercase
        netloc = p.netloc.lower()
        return f"{p.scheme.lower()}://{netloc}"
    except Exception:
        return None


@app.middleware("http")
async def host_origin_security_middleware(request: Request, call_next):
    # 1. Host validation: exact match against allowed hosts set
    host_hdr = request.headers.get("host", "").lower().strip()
    allowed_hosts = get_allowed_hosts()
    if host_hdr and host_hdr not in allowed_hosts:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"非法的 Host 标头: {host_hdr}，服务仅允许本机回环访问。"},
        )

    # 2. Origin / Referer CSRF protection on mutating requests: strict exact scheme/host/port match
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        allowed_origins = get_allowed_origins()
        origin_hdr = request.headers.get("origin")
        if origin_hdr:
            norm_origin = parse_origin_norm(origin_hdr)
            if not norm_origin or norm_origin not in allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"禁止非同源外部页面向本机服务发起写操作: {origin_hdr}"},
                )

        referer_hdr = request.headers.get("referer")
        if referer_hdr:
            norm_referer = parse_origin_norm(referer_hdr)
            if not norm_referer or norm_referer not in allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"禁止跨域 Referer 写操作: {referer_hdr}"},
                )

    return await call_next(request)


@app.middleware("http")
async def streaming_upload_limit_middleware(request: Request, call_next):
    """
    Guarantees raw upload stream byte quota is enforced BEFORE/DURING streaming receive,
    handling requests without Content-Length or chunked Transfer-Encoding to prevent infinite spooling.
    """
    if request.method == "POST" and "/assets" in request.url.path:
        # Pre-check Content-Length header upfront
        cl_hdr = request.headers.get("content-length")
        if cl_hdr and cl_hdr.isdigit():
            cl_val = int(cl_hdr)
            if cl_val > MAX_MEDIA_SIZE_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": f"请求体大小 ({cl_val} 字节) 超过500MiB严格限制 ({MAX_MEDIA_SIZE_BYTES} 字节)。"},
                )

        # Wrap receive method to accumulate raw stream bytes on the fly
        original_receive = request._receive
        accumulated_bytes = 0

        async def limited_receive():
            nonlocal accumulated_bytes
            message = await original_receive()
            if message.get("type") == "http.request":
                chunk = message.get("body", b"")
                accumulated_bytes += len(chunk)
                if accumulated_bytes > MAX_MEDIA_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"原始上传流累计字节 ({accumulated_bytes}) 超过500MiB严格限制 ({MAX_MEDIA_SIZE_BYTES} 字节)。",
                    )
            return message

        request._receive = limited_receive

    try:
        return await call_next(request)
    except HTTPException as he:
        return JSONResponse(
            status_code=he.status_code,
            content={"detail": he.detail},
        )


# Restrict CORS to localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_allowed_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health():
    return {
        "status": "healthy",
        "service": "subtitle-intake-storage",
        "version": "1.0.0",
        "tools": {
            "ffmpeg": media_tool.get_ffmpeg_version(),
            "ffprobe": media_tool.get_ffprobe_version(),
            "ffmpeg_path": FFMPEG_PATH,
            "ffprobe_path": FFPROBE_PATH,
        },
        "limits": {
            "max_media_bytes": MAX_MEDIA_SIZE_BYTES,
            "max_duration_ms": MAX_PROCESS_DURATION_MS,
        },
    }


# -------------------------------------------------------------
# Local Operator & Session Management (Priority 1)
# -------------------------------------------------------------

@app.get("/api/v1/auth/session")
def get_session(request: Request):
    """
    Checks active session and returns operator info and operator list.
    """
    token = request.cookies.get("session_token") or request.headers.get("X-Session-Token")
    operators = list_local_operators()
    session_info = get_session_info(token) if token else None

    return {
        "authenticated": session_info is not None,
        "operator": session_info,
        "operators": operators,
        "initialized": len(operators) > 0,
    }


@app.post("/api/v1/auth/register-operator")
def register_operator(req: RegisterOperatorRequest, response: Response):
    """
    Explicit first-time or local operator registration.
    Sets session cookie and returns session token.
    """
    try:
        res = register_local_operator(display_name=req.display_name, role=req.role)
        response.set_cookie(
            key="session_token",
            value=res["session_token"],
            httponly=True,
            samesite="lax",
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/v1/auth/login")
def login_operator(req: LoginRequest, response: Response):
    """
    Switches active session to a registered local operator.
    """
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM local_operators WHERE operator_id = ?", (req.operator_id,))
        op = cur.fetchone()
        if not op:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="操作人员未登记")

    token = create_operator_session(req.operator_id)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return {
        "operator_id": op["operator_id"],
        "display_name": op["display_name"],
        "role": op["role"],
        "session_token": token,
    }


@app.post("/api/v1/auth/logout")
def logout_operator(request: Request, response: Response):
    token = request.cookies.get("session_token") or request.headers.get("X-Session-Token")
    if token:
        with db.transaction() as conn:
            conn.execute("DELETE FROM local_sessions WHERE session_token = ?", (token,))
    response.delete_cookie(key="session_token")
    return {"status": "logged_out"}


# -------------------------------------------------------------
# Asset Endpoints (SRC-ASSET)
# -------------------------------------------------------------

@app.post("/api/v1/projects/{project_id}/assets")
async def register_asset(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form("video"),
    rights_ref: str = Form(...),
    supplied_version: Optional[str] = Form(None),
    task_id: Optional[str] = Form(None),
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "登记素材")
    now = utc_now_iso()

    VALID_KINDS = {"video", "audio", "script", "character_list", "terminology", "existing_subtitle"}
    if kind not in VALID_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资产种类 kind={kind}，必须是 {VALID_KINDS} 之一。",
        )

    clean_filename = file.filename or "upload.bin"
    ext = Path(clean_filename).suffix.lower()

    if kind in ["video", "audio"]:
        if ext and ext not in ALLOWED_MEDIA_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的媒体文件扩展名: '{ext}'。允许的媒体类型为: {sorted(list(ALLOWED_MEDIA_EXTENSIONS))}",
            )
        effective_limit_bytes = MAX_MEDIA_SIZE_BYTES
    else:
        # Auxiliary files (script, character_list, terminology, existing_subtitle)
        if ext and ext not in ALLOWED_AUXILIARY_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的辅助资料文件扩展名: '{ext}'。允许的类型为: {sorted(list(ALLOWED_AUXILIARY_EXTENSIONS))}",
            )
        effective_limit_bytes = MAX_AUXILIARY_SIZE_BYTES

    # Raw stream Content-Length check upfront
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            cl = int(content_length)
            if cl > effective_limit_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"请求体大小 ({cl} 字节) 超过该文件类型限额 ({effective_limit_bytes} 字节)。",
                )
        except ValueError:
            pass

    clean_rights = rights_ref.strip() if rights_ref else ""
    if not clean_rights:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rights_ref 授权引用不能为空，必须提供真实有效的授权凭证或编号。",
        )

    # Disallow default mock / placeholder authorization references
    FORBIDDEN_RIGHTS_PLACEHOLDERS = {
        "rights-default-001",
        "rights-aux-20261021",
        "placeholder",
        "undefined",
        "null",
    }
    if clean_rights.lower() in FORBIDDEN_RIGHTS_PLACEHOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"授权引用不能使用默认占位符（如 '{clean_rights}'），必须提供真实有效的项目授权凭证或编号。",
        )

    asset_id = f"asset_{kind}_{uuid.uuid4().hex[:12]}"

    # Save to controlled storage asynchronously to avoid blocking event loop
    try:
        sha256, size_bytes, rel_uri, mime_type = await anyio.to_thread.run_sync(
            default_storage.save_stream,
            file.file,
            clean_filename,
            project_id,
            asset_id,
            effective_limit_bytes,
        )
    except FileSizeLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"素材超出限制：{str(e)}",
        )
    except PathTraversalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"路径安全拦截：{str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件存储失败: {str(e)}",
        )

    # Perform technical inspection if media (async thread pool)
    inspection = None
    real_path = default_storage.get_real_path(rel_uri)
    availability = "readable"

    if kind in ["video", "audio"]:
        try:
            inspection = await anyio.to_thread.run_sync(
                media_tool.inspect_file,
                real_path,
                MAX_PROCESS_DURATION_MS,
            )
            if not inspection.get("decode_ok", False):
                availability = "unreadable"
        except Exception as e:
            availability = "unreadable"
            inspection = {
                "decode_ok": False,
                "decode_error": str(e),
                "measurement_status": "failed",
                "tool_version": media_tool.get_ffmpeg_version(),
            }
    else:
        # Auxiliary files: registered only, not parsed in T1.1
        inspection = {
            "status": "registered_unparsed",
            "note": "辅助资料仅登记，本批不执行内容抽取与解析",
        }

    # Record Asset in DB and optionally link to Task
    task_revision_val: Optional[int] = None
    task_status_val: Optional[str] = None

    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO assets (
            asset_id, project_id, media_id, kind, origin,
            source_uri, rights_ref, checksum_sha256, size_bytes,
            mime_type, supplied_version, parent_asset_ids,
            transform, availability, inspection, privacy, revision,
            created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            asset_id, project_id, None, kind, "supplied",
            rel_uri, clean_rights, sha256, size_bytes,
            mime_type, supplied_version, json.dumps([]),
            None, availability, json.dumps(inspection) if inspection else None,
            json.dumps({"classification": "internal", "external_processing_allowed": False}),
            1, now, actor.actor_id,
        ))

        # If task_id is provided, associate asset into Task's input_asset_ids and update status/revision
        if task_id:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id = ? AND project_id = ?", (task_id, project_id))
            t_row = cur.fetchone()
            if t_row:
                input_assets = json.loads(t_row["input_asset_ids"])
                if asset_id not in input_assets:
                    input_assets.append(asset_id)
                new_rev = t_row["task_revision"] + 1
                # If task was READY, adding new auxiliary material invalidates stale confirmation and forces re-confirmation
                new_status = "DRAFT" if t_row["task_status"] == "READY" else t_row["task_status"]
                conn.execute("""
                UPDATE tasks
                SET task_revision = ?, input_asset_ids = ?, task_status = ?, updated_at = ?
                WHERE task_id = ?;
                """, (new_rev, json.dumps(input_assets), new_status, now, task_id))
                task_revision_val = new_rev
                task_status_val = new_status

        # Emit asset.registered event
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "asset.registered", now, now, task_id,
            None, None, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({"asset_id": asset_id, "checksum_sha256": sha256, "kind": kind, "availability": availability, "task_id": task_id}),
            now,
        ))

    return {
        "asset_id": asset_id,
        "project_id": project_id,
        "task_id": task_id,
        "task_revision": task_revision_val,
        "task_status": task_status_val,
        "kind": kind,
        "origin": "supplied",
        "source_uri": rel_uri,
        "rights_ref": clean_rights,
        "checksum_sha256": sha256,
        "size_bytes": size_bytes,
        "mime_type": mime_type,
        "availability": availability,
        "inspection": inspection,
        "revision": 1,
        "created_at": now,
    }


@app.get("/api/v1/projects/{project_id}/assets/{asset_id}")
def get_asset(
    project_id: str,
    asset_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "读取素材")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM assets WHERE asset_id = ? AND project_id = ?", (asset_id, project_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在或无权限读取")
        d = dict(row)
        d["parent_asset_ids"] = json.loads(d["parent_asset_ids"])
        d["transform"] = json.loads(d["transform"]) if d["transform"] else None
        d["inspection"] = json.loads(d["inspection"]) if d["inspection"] else None
        d["privacy"] = json.loads(d["privacy"]) if d["privacy"] else None
        return d


@app.get("/api/v1/projects/{project_id}/assets/{asset_id}/file")
def get_asset_file(
    project_id: str,
    asset_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "下载素材文件")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM assets WHERE asset_id = ? AND project_id = ?", (asset_id, project_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
        source_uri = row["source_uri"]

    real_path = default_storage.get_real_path(source_uri)
    return FileResponse(
        path=real_path,
        media_type=row["mime_type"],
        filename=real_path.name,
    )


# -------------------------------------------------------------
# Media Endpoints (SRC-MASTER)
# -------------------------------------------------------------

@app.post("/api/v1/media")
def register_media(
    req: RegisterMediaRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "登记母版")
    now = utc_now_iso()
    media_id = f"MEDIA-{uuid.uuid4().hex[:8].upper()}"

    # Extract video duration if master_video_asset_id provided
    duration_ms = None
    if req.master_video_asset_id:
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT inspection FROM assets WHERE asset_id = ?", (req.master_video_asset_id,))
            row = cur.fetchone()
            if row and row["inspection"]:
                insp = json.loads(row["inspection"])
                duration_ms = insp.get("duration_ms")

    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO media (
            media_id, project_id, title_id, episode_id,
            master_video_asset_id, primary_audio_asset_id,
            duration_ms, frame_rate, master_status, match_checks,
            confirmed_by, confirmed_at, supersedes_media_id,
            content_dimensions, revision, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            media_id, req.project_id, req.title_id, req.episode_id,
            req.master_video_asset_id, req.primary_audio_asset_id,
            duration_ms, json.dumps({"numerator": 30, "denominator": 1, "timecode_mode": "cfr"}),
            "REGISTERED", json.dumps([]), None, None, None,
            json.dumps(req.content_dimensions), 1, now, actor.actor_id,
        ))

    return {
        "media_id": media_id,
        "project_id": req.project_id,
        "title_id": req.title_id,
        "episode_id": req.episode_id,
        "master_video_asset_id": req.master_video_asset_id,
        "primary_audio_asset_id": req.primary_audio_asset_id,
        "duration_ms": duration_ms,
        "master_status": "REGISTERED",
        "revision": 1,
        "created_at": now,
    }


@app.get("/api/v1/media/{media_id}")
def get_media(media_id: str, actor: ActorContext = Depends(get_current_actor)):
    require_permission(actor, "读取母版")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM media WHERE media_id = ?", (media_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="母版不存在")
        d = dict(row)
        d["match_checks"] = json.loads(d["match_checks"])
        d["content_dimensions"] = json.loads(d["content_dimensions"])
        return d


@app.post("/api/v1/media/{media_id}/confirm")
def confirm_master(
    media_id: str,
    req: ConfirmMasterRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    # Rule: Human only! Service actor cannot sign.
    require_human_actor(actor, "母版确认 (confirm_master)")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM media WHERE media_id = ?", (media_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="母版不存在")

        # Optimistic locking check
        if row["revision"] != req.expected_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_INPUT: 母版修订冲突（当前修订 {row['revision']} != 预期 {req.expected_revision}）",
            )

        project_id = row["project_id"]

        # 1. Strict check of match_checks upfront: cannot be empty!
        if not req.match_checks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="母版配套检查单为空，必须进行真实客观技术核验与人工试听核验后方可确认。",
            )

        # 2. Master Video validation
        cur.execute("SELECT * FROM assets WHERE asset_id = ? AND project_id = ?", (req.master_video_asset_id, project_id))
        video_asset = cur.fetchone()
        if not video_asset:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="主视频资产不存在或不属于同项目。")
        if video_asset["kind"] != "video":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"主视频资产类型错误: 期望 video，实际为 {video_asset['kind']}。")
        if video_asset["availability"] != "readable":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="主视频损坏或不可读，无法确认母版。")

        video_insp = json.loads(video_asset["inspection"]) if video_asset["inspection"] else {}
        if not video_insp.get("decode_ok", False):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="主视频解码校验失败，无法确认母版。")

        # 3. Primary Audio validation (Audio asset or Video asset containing embedded audio stream)
        cur.execute("SELECT * FROM assets WHERE asset_id = ? AND project_id = ?", (req.primary_audio_asset_id, project_id))
        audio_asset = cur.fetchone()
        if not audio_asset:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选用主音频资产不存在或不属于同项目。")
        if audio_asset["kind"] not in ("audio", "video"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"选用主音频资产类型错误: 期望 audio 或含内嵌音轨的 video，实际为 {audio_asset['kind']}。")
        if audio_asset["availability"] != "readable":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选用主音频损坏或不可读，无法确认母版。")

        audio_insp = json.loads(audio_asset["inspection"]) if audio_asset["inspection"] else {}
        if not audio_insp.get("decode_ok", False):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选用主音频解码校验失败，无法确认母版。")

        # 4. Usable Sound verification (strictly distinguish 'track exists' from 'usable sound exists')
        if not audio_insp.get("sound_present", False):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选用主音频不含音频数据流 (无声音)，无法确认母版。")
        if audio_insp.get("is_silent", False):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选用主音频经技术核验为数字纯静音/无可用声音，无法确认母版。")

        # 5. Coverage & Duration Mapping
        video_dur = video_insp.get("duration_ms") or row["duration_ms"]
        audio_dur = audio_insp.get("duration_ms")
        if audio_asset["origin"] == "extracted":
            # If extracted from video, duration must match video (tolerance <= 1000ms)
            if video_dur and audio_dur and abs(video_dur - audio_dur) > 1000:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"派生音频时长与主视频不一致（视频 {video_dur} ms != 音频 {audio_dur} ms），可能发生抽轨截断，阻断确认。",
                )

        # Every item in match_checks must strictly be 'pass' (reject unknown, fail, missing, etc.)
        failed_or_unknown = [mc for mc in req.match_checks if mc.result != "pass"]
        if failed_or_unknown:
            conn.execute("""
            UPDATE media
            SET master_status = 'NEEDS_REVIEW', match_checks = ?
            WHERE media_id = ?;
            """, (json.dumps([mc.model_dump() for mc in req.match_checks]), media_id))
            reasons = [f"[{mc.check_type}: {mc.result}]" for mc in failed_or_unknown]
            review_error = f"母版配套检查存在非通过项（如错配/未知/损坏: {', '.join(reasons)}），母版已置为 NEEDS_REVIEW，阻断确认。"
        else:
            review_error = None

    if review_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=review_error)

    with db.transaction() as conn:

        # Overwrite reviewer identities with the verified session actor
        recorded_checks = []
        for mc in req.match_checks:
            item = mc.model_dump()
            item["checked_by"] = actor.actor_id
            item["checked_at"] = now
            recorded_checks.append(item)

        # Confirm master
        new_rev = row["revision"] + 1
        video_dur = video_insp.get("duration_ms") or row["duration_ms"]

        conn.execute("""
        UPDATE media
        SET master_status = 'CONFIRMED',
            master_video_asset_id = ?,
            primary_audio_asset_id = ?,
            duration_ms = ?,
            match_checks = ?,
            confirmed_by = ?,
            confirmed_at = ?,
            revision = ?
        WHERE media_id = ?;
        """, (
            req.master_video_asset_id,
            req.primary_audio_asset_id,
            video_dur,
            json.dumps(recorded_checks),
            actor.actor_id,
            now,
            new_rev,
            media_id,
        ))

        # Record Decision
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            decision_id, None, media_id, "confirm_master", "confirm",
            actor.actor_id, actor.actor_role,
            json.dumps({"entity_type": "Media", "entity_id": media_id, "revision": new_rev}),
            json.dumps({"match_checks": recorded_checks}),
            now,
        ))

        # Record media.confirmed event
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "media.confirmed", now, now, None,
            media_id, None, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({
                "media_id": media_id,
                "revision": new_rev,
                "confirmed_by": actor.actor_id,
                "video_asset_id": req.master_video_asset_id,
                "audio_asset_id": req.primary_audio_asset_id,
            }),
            now,
        ))

    return {
        "media_id": media_id,
        "master_status": "CONFIRMED",
        "confirmed_by": actor.actor_id,
        "confirmed_at": now,
        "revision": new_rev,
        "decision_id": decision_id,
    }


# -------------------------------------------------------------
# Task Endpoints (SRC-TASK & SRC-CONFIRM)
# -------------------------------------------------------------

@app.post("/api/v1/tasks")
def create_task(
    req: CreateTaskRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "创建任务")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        # Idempotency check on (project_id, request_key)
        cur.execute("SELECT * FROM tasks WHERE project_id = ? AND request_key = ?", (req.project_id, req.request_key))
        existing = cur.fetchone()
        if existing:
            if existing["task_type"] != req.task_type or existing["source_locale"] != req.source_locale:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="同 request_key 提交了不同的业务内容，发生冲突。",
                )
            d = dict(existing)
            d["range"] = json.loads(d["range"])
            d["input_asset_ids"] = json.loads(d["input_asset_ids"])
            d["missing_items"] = json.loads(d["missing_items"])
            d["readiness"] = json.loads(d["readiness"])
            return d

        # Create new Task draft with stable ID
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        missing_items = [
            {
                "name": "master_video",
                "reason": "尚未选择或确认母版",
                "blocking_stage": "ingest",
                "owner_id": req.owner_id or actor.actor_id,
                "resolution_status": "open",
            }
        ]
        readiness = [
            {
                "stage": "asr_alignment",
                "status": "pending",
                "checked_at": now,
                "validation_ids": [],
                "reason_codes": ["STAGE_NOT_READY"],
            }
        ]

        conn.execute("""
        INSERT INTO tasks (
            task_id, project_id, task_revision, request_key,
            media_id, parent_task_id, task_type, execution_mode,
            execution_policy, purpose, owner_id, source_locale,
            processing_route, input_asset_ids, range,
            target_variants, target_scope_status, output_spec,
            delivery_units, module_plan, missing_items, readiness,
            task_status, confirmed_by, confirmed_at, created_at,
            created_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            task_id, req.project_id, 1, req.request_key,
            req.media_id, None, req.task_type, req.execution_mode,
            json.dumps({"review_mode": "manual", "authorization_ref": None}),
            req.purpose, req.owner_id, req.source_locale,
            req.processing_route, json.dumps(req.input_asset_ids),
            json.dumps(req.range.model_dump()), json.dumps([]),
            "not_applicable" if req.task_type == "source_only" else "pending",
            json.dumps([{"variant_key": "source", "format": "srt", "purpose": req.purpose}]),
            json.dumps([]), json.dumps([{"module": "asr_alignment", "applicability": "required", "reason": "源语听写"}]),
            json.dumps(missing_items), json.dumps(readiness),
            "DRAFT", None, None, now, actor.actor_id, now,
        ))

    return {
        "task_id": task_id,
        "project_id": req.project_id,
        "task_revision": 1,
        "request_key": req.request_key,
        "task_status": "DRAFT",
        "source_locale": req.source_locale,
        "processing_route": req.processing_route,
        "range": req.range.model_dump(),
        "created_at": now,
    }


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str, actor: ActorContext = Depends(get_current_actor)):
    require_permission(actor, "读取任务")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        d = dict(row)
        d["range"] = json.loads(d["range"])
        d["input_asset_ids"] = json.loads(d["input_asset_ids"])
        d["missing_items"] = json.loads(d["missing_items"])
        d["readiness"] = json.loads(d["readiness"])
        return d


@app.patch("/api/v1/tasks/{task_id}")
def update_task(
    task_id: str,
    req: UpdateTaskRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "修改任务")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # Concurrency / Stale revision check
        if row["task_revision"] != req.expected_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_INPUT: 任务修订冲突（当前修订 {row['task_revision']} != 预期 {req.expected_revision}）",
            )

        new_rev = row["task_revision"] + 1

        purpose = req.purpose if req.purpose is not None else row["purpose"]
        owner_id = req.owner_id if req.owner_id is not None else row["owner_id"]
        source_locale = req.source_locale if req.source_locale is not None else row["source_locale"]
        processing_route = req.processing_route if req.processing_route is not None else row["processing_route"]
        range_data = req.range.model_dump() if req.range is not None else json.loads(row["range"])
        media_id = req.media_id if req.media_id is not None else row["media_id"]
        input_asset_ids = req.input_asset_ids if req.input_asset_ids is not None else json.loads(row["input_asset_ids"])

        # Any substantive update resets confirmation to DRAFT if it was previously READY
        task_status = "DRAFT" if (row["task_status"] == "READY") else row["task_status"]

        conn.execute("""
        UPDATE tasks
        SET task_revision = ?, purpose = ?, owner_id = ?,
            source_locale = ?, processing_route = ?, range = ?,
            media_id = ?, input_asset_ids = ?, task_status = ?,
            updated_at = ?
        WHERE task_id = ?;
        """, (
            new_rev, purpose, owner_id, source_locale, processing_route,
            json.dumps(range_data), media_id, json.dumps(input_asset_ids),
            task_status, now, task_id,
        ))

    return {
        "task_id": task_id,
        "task_revision": new_rev,
        "task_status": task_status,
        "updated_at": now,
    }


@app.post("/api/v1/tasks/{task_id}/ingest/extract-audio")
def extract_audio(
    task_id: str,
    req: ExtractAudioRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "抽轨操作")
    try:
        res = ingest_worker.extract_audio(
            task_id=task_id,
            video_asset_id=req.video_asset_id,
            stream_index=req.track_index,
            actor=actor,
        )
        return res
    except IngestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"抽轨派生异常: {str(e)}")


@app.post("/api/v1/tasks/{task_id}/confirm")
def confirm_task(
    task_id: str,
    req: ConfirmTaskRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "任务确认 (confirm_task)")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        if task_row["task_revision"] != req.expected_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_INPUT: 任务修订冲突（当前 {task_row['task_revision']} != 预期 {req.expected_revision}）",
            )

        # Check Media is CONFIRMED
        cur.execute("SELECT * FROM media WHERE media_id = ?", (req.media_id,))
        media_row = cur.fetchone()
        if not media_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"关联母版不存在: {req.media_id}")

        if media_row["master_status"] != "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="关联母版尚未完成人工确认（状态非 CONFIRMED），不可确认任务单。",
            )

        # Range validation
        range_data = json.loads(task_row["range"])
        duration_ms = media_row["duration_ms"] or 0

        audio_dur = 0
        if media_row["primary_audio_asset_id"]:
            cur.execute("SELECT inspection FROM assets WHERE asset_id = ?", (media_row["primary_audio_asset_id"],))
            aud_row = cur.fetchone()
            if aud_row and aud_row["inspection"]:
                aud_insp = json.loads(aud_row["inspection"])
                audio_dur = aud_insp.get("duration_ms") or 0

        if range_data.get("mode") == "whole":
            if duration_ms > 0:
                if duration_ms > MAX_PROCESS_DURATION_MS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"母版总时长超过10分钟上限（{duration_ms} ms > {MAX_PROCESS_DURATION_MS} ms），不可整片处理，请指定10分钟以内的分段区间（不进行静默截断）。",
                    )
                range_data["intervals"] = [{"start_ms": 0, "end_ms": duration_ms}]
        else:
            intervals = range_data.get("intervals", [])
            if not intervals:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="区间模式下必须指定至少一个有效处理区间。")
            for iv in intervals:
                interval_len = iv["end_ms"] - iv["start_ms"]
                if interval_len <= 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="处理区间起点必须小于终点。")
                if interval_len > MAX_PROCESS_DURATION_MS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"处理范围超过单次上限 10 分钟（{interval_len} ms > {MAX_PROCESS_DURATION_MS} ms），系统禁止静默截断，请缩小处理区间。",
                    )
                if duration_ms > 0 and iv["end_ms"] > duration_ms:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"处理范围越界（区间终点 {iv['end_ms']} ms > 母版时长 {duration_ms} ms）。",
                    )
                if audio_dur > 0 and iv["end_ms"] > audio_dur:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"处理范围越界（区间终点 {iv['end_ms']} ms > 主音频时长 {audio_dur} ms）。",
                    )

        new_rev = task_row["task_revision"] + 1

        # Mark Task READY
        readiness = [
            {
                "stage": "asr_alignment",
                "status": "ready",
                "checked_at": now,
                "validation_ids": ["VAL-INT-001"],
                "reason_codes": [],
            }
        ]

        conn.execute("""
        UPDATE tasks
        SET task_revision = ?, media_id = ?, range = ?,
            task_status = 'READY', confirmed_by = ?, confirmed_at = ?,
            readiness = ?, updated_at = ?
        WHERE task_id = ?;
        """, (
            new_rev, req.media_id, json.dumps(range_data),
            actor.actor_id, now, json.dumps(readiness), now, task_id,
        ))

        # Record Decision
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            decision_id, task_id, req.media_id, "confirm_task", "confirm",
            actor.actor_id, actor.actor_role,
            json.dumps({"entity_type": "Task", "entity_id": task_id, "revision": new_rev}),
            json.dumps({"range": range_data}), now,
        ))

        # Emit task.confirmed and task.ready
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "task.confirmed", now, now, task_id,
            req.media_id, None, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({"task_id": task_id, "task_revision": new_rev, "confirmed_by": actor.actor_id}),
            now,
        ))

    return {
        "task_id": task_id,
        "task_revision": new_rev,
        "task_status": "READY",
        "confirmed_by": actor.actor_id,
        "confirmed_at": now,
        "decision_id": decision_id,
    }


@app.post("/api/v1/tasks/{task_id}/readiness")
def check_readiness(
    task_id: str,
    stage: str = "asr_alignment",
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "检查就绪")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # Emit readiness.checked event
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "readiness.checked", now, now, task_id,
            task_row["media_id"], None, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({"stage": stage, "task_status": task_row["task_status"]}),
            now,
        ))

        return {
            "task_id": task_id,
            "stage": stage,
            "status": "ready" if task_row["task_status"] == "READY" else "pending",
            "task_status": task_row["task_status"],
            "missing_items": json.loads(task_row["missing_items"]),
        }


@app.post("/api/v1/tasks/{task_id}/runs")
def request_run(
    task_id: str,
    req: RequestRunRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    """
    Blocks ASR run if task is still in DRAFT or unconfirmed.
    """
    require_permission(actor, "申请执行")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        if req.module == "asr_alignment" and task_row["task_status"] != "READY":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STAGE_NOT_READY: 任务草稿尚未完成人工确认，禁止启动 ASR 识别。",
            )

        # In T1.1, ASR model processing is not launched
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="T1.1 执行范围为素材接收与准备，后续 ASR 理解尚未开放。",
        )


@app.get("/api/v1/tasks/{task_id}/runs/{run_id}")
def get_task_run(
    task_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    """
    Queries detailed execution status, steps, and artifacts of a specific run.
    """
    require_permission(actor, "查询执行状态")
    run_info = ingest_worker.get_run(task_id, run_id)
    if not run_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run 不存在: {run_id}")
    return run_info


@app.get("/api/v1/tasks/{task_id}/trace")
def get_task_trace(task_id: str, actor: ActorContext = Depends(get_current_actor)):
    require_permission(actor, "查询审计追踪")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        cur.execute("SELECT * FROM events WHERE task_id = ? ORDER BY event_at ASC", (task_id,))
        events = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM runs WHERE task_id = ?", (task_id,))
        runs = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM decisions WHERE task_id = ? OR media_id = ?", (task_id, task_row["media_id"]))
        decisions = [dict(r) for r in cur.fetchall()]

        return {
            "task_id": task_id,
            "task": dict(task_row),
            "events": events,
            "runs": runs,
            "decisions": decisions,
        }


# -------------------------------------------------------------
# ASR Alignment Endpoints (T2.1: Slicing, Quality Cues, Review)
# -------------------------------------------------------------

@app.get("/api/v1/tasks/{task_id}/asr/status")
def get_asr_status(
    task_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "查询执行状态")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    auth = check_cloud_authorization()
    return auth.model_dump()


@app.post("/api/v1/tasks/{task_id}/asr/slice")
def slice_task_audio(
    task_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    """
    Slices the task's primary audio into fixed 10-second chunks (preserving tail slice real duration).
    Runs real FFmpeg astats and volumedetect measurements on each slice.
    Strict rules:
    - Task & Media MUST be confirmed. DRAFT or unconfirmed is strictly rejected.
    - Only primary audio confirmed on this task or explicitly derived from this task/media.
      Never fallback to arbitrary assets across the entire database!
    - Non-zero master interval start does not double-seek derived local audio starting at 0.
    - All intervals in task range are processed (not silently only intervals[0]).
    - chunk_id is globally unique (Task/run isolated), directory is run-isolated.
    - Does NOT DELETE old slices or overwrite old sounds.
    """
    require_permission(actor, "执行抽轨")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # 1. Require task & master confirmation
        if task_row["task_status"] == "DRAFT" or not task_row["confirmed_by"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STAGE_NOT_READY: 任务草稿尚未完成人工确认，禁止执行切片。",
            )

        media_id = task_row["media_id"]
        if not media_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STAGE_NOT_READY: 任务未关联母版媒体，禁止执行切片。",
            )

        cur.execute("SELECT * FROM media WHERE media_id = ?", (media_id,))
        m_row = cur.fetchone()
        if not m_row or m_row["master_status"] != "CONFIRMED" or not m_row["confirmed_by"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STAGE_NOT_READY: 关联母版尚未完成人工确认，禁止执行切片。",
            )

        # 2. Find primary audio strictly within this task / confirmed media scope
        audio_asset = None
        if m_row["primary_audio_asset_id"]:
            cur.execute("SELECT * FROM assets WHERE asset_id = ?", (m_row["primary_audio_asset_id"],))
            audio_asset = cur.fetchone()

        if not audio_asset:
            input_asset_ids = json.loads(task_row["input_asset_ids"]) if task_row["input_asset_ids"] else []
            for a_id in input_asset_ids:
                cur.execute("SELECT * FROM assets WHERE asset_id = ? AND kind = 'audio'", (a_id,))
                a_row = cur.fetchone()
                if a_row:
                    audio_asset = a_row
                    break

        if not audio_asset:
            # Check derived/extracted assets strictly originating from this task's master video
            master_video_id = m_row["master_video_asset_id"]
            if master_video_id:
                cur.execute("""
                SELECT * FROM assets
                WHERE kind = 'audio' AND origin IN ('extracted', 'derived')
                  AND parent_asset_ids LIKE ?
                ORDER BY created_at DESC LIMIT 1
                """, (f'%"{master_video_id}"%',))
                audio_asset = cur.fetchone()

        if not audio_asset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未找到本任务确认的主音频或明确来源的派生产物，请先在收料台完成抽轨或关联主音频。",
            )

        real_audio_path = default_storage.get_real_path(audio_asset["source_uri"])
        if not real_audio_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主音频文件物理缺失")

        # 3. Probe audio to determine physical duration and verify provenance
        audio_probe = media_tool.probe(real_audio_path)
        audio_physical_dur_ms = audio_probe.get("duration_ms") or 0

        # Parse intervals from task range
        range_data = json.loads(task_row["range"]) if task_row["range"] else {}
        intervals = range_data.get("intervals", [])
        if not intervals:
            # Fallback to single full interval from 0 to master/audio duration
            master_dur = m_row["duration_ms"] or audio_physical_dur_ms
            intervals = [{"start_ms": 0, "end_ms": master_dur}]

        # 4. Generate unique slice_run_id and isolated chunk directory
        slice_run_id = f"srun_{uuid.uuid4().hex[:8]}"
        task_chunks_dir = CHUNKS_DIR / task_id / slice_run_id
        task_chunks_dir.mkdir(parents=True, exist_ok=True)
        chunk_prefix = f"chk_{task_id[:8]}_{slice_run_id}"

        # 5. Process all intervals without silently dropping any
        all_chunks = []
        curr_chunk_idx = 0

        for intv in intervals:
            intv_start = intv.get("start_ms", 0)
            intv_end = intv.get("end_ms")
            if intv_end is None or intv_end <= 0:
                intv_end = audio_physical_dur_ms

            if intv_start >= intv_end:
                continue

            # Provenance check: If derived audio physical duration matches interval duration
            # and is shorter than intv_end while intv_start > 0, the audio file is already
            # locally trimmed starting from 0. Do NOT double-seek intv_start!
            is_local_zero_based = (
                intv_start > 0
                and audio_physical_dur_ms < intv_end
                and audio_physical_dur_ms <= (intv_end - intv_start + 2000)
            )

            if is_local_zero_based:
                local_start_ms = 0
                local_end_ms = min(audio_physical_dur_ms, intv_end - intv_start)
                master_offset_ms = intv_start
            else:
                local_start_ms = intv_start
                local_end_ms = min(audio_physical_dur_ms, intv_end)
                master_offset_ms = intv_start

            if local_start_ms >= local_end_ms:
                continue

            try:
                intv_chunks = media_tool.slice_audio_fixed(
                    audio_path=real_audio_path,
                    output_dir=task_chunks_dir,
                    slice_duration_sec=ASR_SLICE_DURATION_SEC,
                    start_ms=local_start_ms,
                    end_ms=local_end_ms,
                    master_offset_ms=master_offset_ms,
                    chunk_id_prefix=chunk_prefix,
                    start_chunk_idx=curr_chunk_idx,
                )
                all_chunks.extend(intv_chunks)
                curr_chunk_idx += len(intv_chunks)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"音频切片执行失败 (区间 {intv_start}-{intv_end}ms): {str(e)}",
                )

        if not all_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="切片未产生任何有效音频片段，请检查任务时间区间和音频时长。",
            )

        # 6. Preserve previous runs: DO NOT delete old chunks! Insert new unique chunks with slice_run_id
        for c in all_chunks:
            conn.execute("""
            INSERT INTO asr_chunks (
                chunk_id, task_id, slice_run_id, chunk_index, start_ms, end_ms,
                offset_ms, duration_ms, checksum_sha256, file_path,
                quality_stats, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                c["chunk_id"], task_id, slice_run_id, c["chunk_index"], c["start_ms"], c["end_ms"],
                c["offset_ms"], c["duration_ms"], c["checksum_sha256"], c["file_path"],
                json.dumps(c["quality_stats"]), c["status"], now,
            ))

        # Record slice Run
        run_id = f"run_slice_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO runs (
            run_id, task_id, task_revision, trace_id, authorization_ref,
            permission_check_ref, module, input_refs, input_revision,
            idempotency_key, attempt_no, attempts, run_status, stop_reason,
            context_manifest, manifest_hash, steps, started_at, ended_at,
            usage, controls, output_refs, failure, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            run_id, task_id, task_row["task_revision"], f"trc_{uuid.uuid4().hex[:12]}",
            "AUTH-LOCAL-SLICE", "PERM-CHECK-001", "asr_slice",
            json.dumps([{"entity_type": "Asset", "entity_id": audio_asset["asset_id"], "revision": audio_asset["revision"]}]),
            task_row["task_revision"],
            f"idemp_{task_id}_{slice_run_id}_slice",
            1, json.dumps([]), "SUCCEEDED", None,
            json.dumps({"slice_run_id": slice_run_id, "intervals": intervals, "slice_duration_sec": ASR_SLICE_DURATION_SEC}),
            "hash_manifest_slice", json.dumps([]), now, now,
            json.dumps({"chunks_count": len(all_chunks)}),
            json.dumps({}),
            json.dumps([{"chunk_id": c["chunk_id"], "file_path": c["file_path"]} for c in all_chunks]),
            None, now, actor.actor_id,
        ))

        # Record event
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "audio.sliced", now, now, task_id,
            media_id, run_id, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({"task_id": task_id, "slice_run_id": slice_run_id, "chunks_count": len(all_chunks), "slice_duration_sec": ASR_SLICE_DURATION_SEC}),
            now,
        ))

    return {
        "task_id": task_id,
        "slice_run_id": slice_run_id,
        "chunks_count": len(all_chunks),
        "chunks": all_chunks,
        "slice_duration_sec": ASR_SLICE_DURATION_SEC,
    }


@app.get("/api/v1/tasks/{task_id}/asr/chunks/{chunk_id}/audio")
def get_chunk_audio(
    task_id: str,
    chunk_id: str,
):
    """
    Streams the exact WAV slice audio file for chunk listen-back.
    Strict security: Ensures file is contained strictly inside CHUNKS_DIR.
    """
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM asr_chunks WHERE task_id = ? AND chunk_id = ?", (task_id, chunk_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="切片不存在")

        file_path = Path(row["file_path"]).resolve()
        chunks_root = CHUNKS_DIR.resolve()
        try:
            file_path.relative_to(chunks_root)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="路径安全拦截：切片超出安全存储目录")

        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="切片音频物理文件缺失")

        return FileResponse(file_path, media_type="audio/wav", filename=f"{chunk_id}.wav")


@app.post("/api/v1/tasks/{task_id}/asr/transcribe")
def transcribe_task_asr(
    task_id: str,
    req: ASRTranscribeRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    """
    Executes ASR transcription for the task.
    Strict authorization boundaries:
    - Task MUST be in READY (or IN_PROGRESS) status. DRAFT tasks are strictly blocked.
    - Cloud API calls require explicit authorization flags (key, outbound, budget).
      If missing, returns HTTP 403 with prominent '待配置/待授权' status.
    - Controlled Mocking is ONLY permitted when server TEST_MODE is explicitly enabled.
      Normal production requests with simulate: true are strictly rejected with HTTP 403.
    - Faithful verbatim transcription: original speech only, no translation / polish / character analysis.
    - Master time mapping without fake sentence-level timestamp interpolation.
    """
    require_permission(actor, "申请执行")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task_row = cur.fetchone()
        if not task_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        if task_row["task_status"] == "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STAGE_NOT_READY: 任务草稿尚未完成人工确认，禁止启动 ASR 识别。",
            )

        # Check authorization boundary and mock isolation
        auth = check_cloud_authorization()
        is_simulated = bool(req.simulate)

        if is_simulated:
            # Strict mock isolation: ONLY permitted when TEST_MODE is explicitly enabled on the server
            if not is_test_mode():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="普通正式环境禁止使用模拟识别。模拟 Mock 仅允许在显式服务端测试模式（SUBTITLE_TEST_MODE=1）及隔离测试环境下作为测试夹具运行。",
                )

        if not auth.allowed_in_pilot and not is_simulated:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "待配置/待授权",
                    "message": "本次工程批次未授权实际素材外传或云端调用。云接口适配器与配置流程已就绪，但阻断未经授权的外传与收费。",
                    "missing_items": auth.missing_items,
                    "model_id": auth.model_id,
                },
            )

        # Retrieve chunks from latest slice run for this task
        cur.execute("""
        SELECT slice_run_id FROM asr_chunks
        WHERE task_id = ?
        ORDER BY created_at DESC LIMIT 1
        """, (task_id,))
        latest_run_row = cur.fetchone()
        if not latest_run_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="尚未生成音频切片，请先调用 /asr/slice 完成固定10秒切片。",
            )

        target_slice_run_id = latest_run_row["slice_run_id"]
        if target_slice_run_id:
            cur.execute("""
            SELECT * FROM asr_chunks
            WHERE task_id = ? AND slice_run_id = ?
            ORDER BY chunk_index ASC
            """, (task_id, target_slice_run_id))
        else:
            cur.execute("""
            SELECT * FROM asr_chunks
            WHERE task_id = ?
            ORDER BY chunk_index ASC
            """, (task_id,))

        chunk_rows = [dict(r) for r in cur.fetchall()]
        if not chunk_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="尚未生成音频切片，请先调用 /asr/slice 完成固定10秒切片。",
            )

        from code.backend.modules.asr_alignment.recovery import repair_tiny_tail, reusable_results
        tail_repair = None
        reused = {}
        if not is_simulated:
            chunk_rows, tail_repair = repair_tiny_tail(chunk_rows, CHUNKS_DIR, media_tool.measure_audio_quality)
            if tail_repair:
                for row in chunk_rows:
                    row['created_at'] = now
                    conn.execute(f"INSERT INTO asr_chunks ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",tuple(row.values()))
                target_slice_run_id = tail_repair['new_slice_run_id']
            reused = reusable_results(conn, dict(task_row), chunk_rows, auth.model_id, task_row['source_locale'] or 'zh-CN')

        # Extract project-scoped glossary terms from task auxiliary assets
        glossary_terms: List[Dict[str, str]] = []
        input_asset_ids = json.loads(task_row["input_asset_ids"]) if task_row["input_asset_ids"] else []
        for aid in input_asset_ids:
            cur.execute("SELECT * FROM assets WHERE asset_id = ? AND kind IN ('script', 'glossary', 'terminology')", (aid,))
            aux_row = cur.fetchone()
            if aux_row:
                try:
                    aux_path = default_storage.get_real_path(aux_row["source_uri"])
                    if aux_path.exists():
                        if aux_path.suffix.lower() == ".json":
                            g_data = json.loads(aux_path.read_text(encoding="utf-8"))
                            if isinstance(g_data, list):
                                for item in g_data:
                                    if isinstance(item, dict) and "term" in item:
                                        glossary_terms.append(item)
                        else:
                            for line in aux_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                                line_clean = line.strip()
                                if line_clean and not line_clean.startswith("#"):
                                    glossary_terms.append({"term": line_clean, "term_id": f"GLOSS-{aux_row['asset_id'][:6]}"})
                except Exception:
                    pass

        # Collect results for chunks
        chunk_results: List[ChunkTranscriptionResult] = []
        failed_chunks = []
        global_error = None

        for c in chunk_rows:
            q_stats = json.loads(c["quality_stats"]) if c["quality_stats"] else {}
            is_silent = q_stats.get("is_silent", False)

            try:
                if is_simulated:
                    r = mock_transcribe_chunk(
                        chunk_id=c["chunk_id"],
                        offset_ms=c["offset_ms"],
                        duration_ms=c["duration_ms"],
                        is_silent=is_silent,
                    )
                elif c["chunk_id"] in reused:
                    r = reused[c["chunk_id"]]["result"]
                else:
                    r = transcribe_chunk_gemini(
                        audio_path=Path(c["file_path"]),
                        chunk_id=c["chunk_id"],
                        offset_ms=c["offset_ms"],
                        duration_ms=c["duration_ms"],
                        source_language=task_row["source_locale"] or "zh-CN",
                    )
                chunk_results.append(r)
            except Exception as e:
                failed_chunks.append({
                    "chunk_id": c["chunk_id"],
                    "offset_ms": c["offset_ms"],
                    "duration_ms": c["duration_ms"],
                    "error": e.safe_detail() if isinstance(e, GeminiProviderError) else {"message": sanitize_error_message(e)},
                })
                if isinstance(e, GeminiProviderError) and e.global_failure:
                    global_error = e
                    break

        if failed_chunks:
            attempted = len(chunk_results) + len(failed_chunks)
            unattempted = [c["chunk_id"] for c in chunk_rows[attempted:]]
            http_status = global_error.http_status if global_error else failed_chunks[0]["error"].get("http_status", 502)
            message = ("Gemini额度不足，已停止后续片段请求。请在额度恢复后手动重试；不要连续点击重试。"
                       if http_status == 429 else
                       "Gemini认证或权限不可用，已停止后续请求。请检查账户/接口配置后手动重试。"
                       if http_status in (401, 403) else
                       "Gemini服务请求失败，已保留失败记录。请检查服务状态或模型配置后手动重试。")
            if not global_error:
                message = "部分转写失败，已保留成功结果；重试将核对输入并复用，极短残尾会无损并入前片。"
            run_id = f"run_asr_{uuid.uuid4().hex[:12]}"
            failure = {"message": message, "http_status": http_status,
                       "failed_chunks": failed_chunks, "unattempted_chunk_ids": unattempted,
                       "attempted_count": attempted, "successful_count": len(chunk_results),
                       "retry_delay": global_error.retry_delay if global_error else None,
                       "partial_results": [r.model_dump() for r in chunk_results],
                       "reused_count":len(reused), "tail_repair":tail_repair}
            record = {
                "run_id": run_id, "task_id": task_id, "task_revision": task_row["task_revision"],
                "trace_id": f"trc_{uuid.uuid4().hex[:12]}",
                "authorization_ref": "SIMULATED" if is_simulated else "AUTH-GEMINI-PILOT",
                "permission_check_ref": "PERM-CHECK-001", "module": "asr_alignment",
                "input_refs": json.dumps([{"chunk_id": c["chunk_id"], "hash": c["checksum_sha256"]} for c in chunk_rows]),
                "input_revision": task_row["task_revision"], "idempotency_key": run_id,
                "attempt_no": 1, "attempts": "[]", "run_status": "FAILED",
                "stop_reason": "PROVIDER_ERROR" if global_error else "CHUNK_FAILURE",
                "context_manifest": json.dumps({"model": auth.model_id, "slice_run_id": target_slice_run_id, "tail_repair":tail_repair, "is_simulated":is_simulated}),
                "manifest_hash": "hash_manifest_asr", "steps": "[]", "started_at": now,
                "ended_at": utc_now_iso(), "usage": json.dumps({"cost": "unmeasured", "usage_sources": [r.usage_info for r in chunk_results if r.usage_info and r.chunk_id not in reused]}),
                "controls": json.dumps({"automatic_retry": False}), "output_refs": "[]",
                "failure": json.dumps(failure), "created_at": now, "created_by": actor.actor_id,
            }
            conn.execute(f"INSERT INTO runs ({','.join(record)}) VALUES ({','.join('?' for _ in record)})", tuple(record.values()))
            # Return normally so the transaction commits the failure; existing candidates remain intact.
            return JSONResponse(status_code=http_status, content={"detail": {**failure, "run_id": run_id}})

        # Check cross-slice boundaries
        boundary_issues = check_cross_slice_boundaries(chunk_results)

        # Map to master timeline with verified glossary matching
        master_segments = map_chunks_to_master(chunk_rows, chunk_results, glossary_terms=glossary_terms)

        # Persist Run
        run_id = f"run_asr_{uuid.uuid4().hex[:12]}"
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO runs (
            run_id, task_id, task_revision, trace_id, authorization_ref,
            permission_check_ref, module, input_refs, input_revision,
            idempotency_key, attempt_no, attempts, run_status, stop_reason,
            context_manifest, manifest_hash, steps, started_at, ended_at,
            usage, controls, output_refs, failure, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            run_id, task_id, task_row["task_revision"], trace_id,
            "SIMULATED" if is_simulated else "AUTH-GEMINI-PILOT",
            "PERM-CHECK-001", "asr_alignment",
            json.dumps([{"chunk_id": c["chunk_id"], "hash": c["checksum_sha256"]} for c in chunk_rows]),
            task_row["task_revision"],
            f"idemp_{task_id}_{task_row['task_revision']}_asr",
            1, json.dumps([]), "SUCCEEDED", None,
            json.dumps({
                "model": auth.model_id,
                "is_simulated": is_simulated,
                "slice_run_id": target_slice_run_id,
                "reused_results": {k:{"source_run_id":v["source_run_id"],"source_chunk_id":v["source_chunk_id"]} for k,v in reused.items()},
                "tail_repair": tail_repair,
                "chunk_inputs": [
                    {"chunk_id": cr.chunk_id, "input_hash": cr.input_hash, "prompt_params": cr.prompt_params}
                    for cr in chunk_results
                ],
            }),
            "hash_manifest_asr", json.dumps([]), now, now,
            json.dumps({
                "chunks_count": len(chunk_rows),
                "cost": "0.00" if is_simulated else "unmeasured",
                "usage_sources": [cr.usage_info for cr in chunk_results if cr.usage_info and cr.chunk_id not in reused],
            }),
            json.dumps({}), json.dumps([]), None, now, actor.actor_id,
        ))

        # Clear old candidates and issues for this task
        conn.execute("DELETE FROM candidates WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM issues WHERE task_id = ?", (task_id,))

        # Save Candidates
        saved_candidates = []
        for s_idx, seg in enumerate(master_segments):
            cand_id = f"cand_asr_{uuid.uuid4().hex[:12]}"
            proposed_obj = {
                "text": seg.text,
                "start_ms": seg.master_start_ms,
                "end_ms": seg.master_end_ms,
                "timing_precise": seg.timing_precise,
                "labels": ["source_transcription"],
                "rationale": "Gemini源语忠实听写" if not is_simulated else "隔离模拟听写 (SIMULATED)",
            }
            confidence_obj = {
                "raw_score": None,
                "calibrated_score": None,
                "calibration_version": None,
                "calibration_label": seg.confidence_label,
            }
            content_hash = hashlib.sha256(seg.text.encode("utf-8")).hexdigest()

            conn.execute("""
            INSERT INTO candidates (
                candidate_id, task_id, run_id, segment_id, chunk_id,
                candidate_revision, input_revision, target_variant_key,
                module, candidate_kind, candidate_index, proposed,
                candidate_status, confidence, overlap_info, entity_info,
                uncertainties, evidence, supersedes_candidate_id, content_hash,
                is_simulated, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                cand_id, task_id, run_id, seg.segment_id, seg.chunk_id,
                1, task_row["task_revision"], "source",
                "asr_alignment", "composite", s_idx, json.dumps(proposed_obj),
                "AI_PROPOSED", json.dumps(confidence_obj),
                json.dumps([o.model_dump() for o in seg.overlap_candidates]),
                json.dumps([e.model_dump() for e in seg.entity_candidates]),
                json.dumps(seg.uncertainties), json.dumps([]), None, content_hash,
                1 if is_simulated else 0, now,
            ))
            saved_candidates.append({
                "candidate_id": cand_id,
                "segment_id": seg.segment_id,
                "chunk_id": seg.chunk_id,
                "proposed": proposed_obj,
                "confidence": confidence_obj,
                "overlap_candidates": [o.model_dump() for o in seg.overlap_candidates],
                "entity_candidates": [e.model_dump() for e in seg.entity_candidates],
                "uncertainties": seg.uncertainties,
                "candidate_status": "AI_PROPOSED",
                "is_simulated": is_simulated,
            })

        # Save boundary issues
        saved_issues = []
        for bi in boundary_issues:
            conn.execute("""
            INSERT INTO issues (
                issue_id, task_id, run_id, candidate_id, segment_id, chunk_id,
                category, severity, confidence, detail, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                bi["issue_id"], task_id, run_id, None, None, bi["chunk_id"],
                bi["category"], bi["severity"], bi["confidence"], bi["detail"],
                "OPEN", now,
            ))
            saved_issues.append(bi)

        # Save quality risk issues from slices
        for c in chunk_rows:
            q_stats = json.loads(c["quality_stats"]) if c["quality_stats"] else {}
            for qr in q_stats.get("quality_risks", []):
                iss_id = f"iss_qr_{uuid.uuid4().hex[:8]}"
                iss_obj = {
                    "issue_id": iss_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "chunk_id": c["chunk_id"],
                    "category": "audio_quality",
                    "severity": "P1" if "静音" in qr else "P2",
                    "confidence": "MEASURED",
                    "detail": f"切片 {c['chunk_id']} 音质风险: {qr}",
                    "status": "OPEN",
                }
                conn.execute("""
                INSERT INTO issues (
                    issue_id, task_id, run_id, candidate_id, segment_id, chunk_id,
                    category, severity, confidence, detail, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    iss_id, task_id, run_id, None, None, c["chunk_id"],
                    iss_obj["category"], iss_obj["severity"], iss_obj["confidence"],
                    iss_obj["detail"], "OPEN", now,
                ))
                saved_issues.append(iss_obj)

        # Save unconfirmed entity issues
        for seg in master_segments:
            for ent in seg.entity_candidates:
                if ent.match_status == "pending_confirmation":
                    iss_id = f"iss_ent_{uuid.uuid4().hex[:8]}"
                    iss_obj = {
                        "issue_id": iss_id,
                        "task_id": task_id,
                        "run_id": run_id,
                        "chunk_id": seg.chunk_id,
                        "category": "unknown_entity",
                        "severity": "P2",
                        "confidence": "PROPOSED",
                        "detail": f"未匹配词表的专有名词候选: '{ent.name}' ({ent.category})，需人工核对确认。",
                        "status": "OPEN",
                    }
                    conn.execute("""
                    INSERT INTO issues (
                        issue_id, task_id, run_id, candidate_id, segment_id, chunk_id,
                        category, severity, confidence, detail, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        iss_id, task_id, run_id, None, None, seg.chunk_id,
                        iss_obj["category"], iss_obj["severity"], iss_obj["confidence"],
                        iss_obj["detail"], "OPEN", now,
                    ))
                    saved_issues.append(iss_obj)

        # Emit candidate.generated event
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, "candidate.generated", now, now, task_id,
            task_row["media_id"], run_id, actor.actor_id, actor.actor_type, actor.actor_role,
            f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
            json.dumps({"task_id": task_id, "candidates_count": len(saved_candidates), "is_simulated": is_simulated}),
            now,
        ))

    return {
        "run_id": run_id,
        "task_id": task_id,
        "is_simulated": is_simulated,
        "candidates": saved_candidates,
        "issues": saved_issues,
        "chunks_count": len(chunk_rows),
        "reused_count": len(reused),
        "newly_requested_count": len(chunk_rows)-len(reused),
        "tail_repair": tail_repair,
    }


@app.get("/api/v1/tasks/{task_id}/asr/candidates")
def get_task_asr_candidates(
    task_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "查询执行状态")
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        cur.execute("SELECT * FROM candidates WHERE task_id = ? ORDER BY candidate_index ASC", (task_id,))
        candidates = []
        for r in cur.fetchall():
            d = dict(r)
            d["proposed"] = json.loads(d["proposed"])
            d["confidence"] = json.loads(d["confidence"])
            d["overlap_info"] = json.loads(d["overlap_info"]) if d["overlap_info"] else []
            d["entity_info"] = json.loads(d["entity_info"]) if d["entity_info"] else []
            d["uncertainties"] = json.loads(d["uncertainties"]) if d["uncertainties"] else []
            candidates.append(d)

        cur.execute("SELECT * FROM issues WHERE task_id = ?", (task_id,))
        issues = [dict(r) for r in cur.fetchall()]

        # Query chunks corresponding to the latest slice_run_id for the task
        cur.execute("SELECT slice_run_id FROM asr_chunks WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task_id,))
        latest_slice_row = cur.fetchone()
        latest_slice_id = latest_slice_row["slice_run_id"] if latest_slice_row else None

        if latest_slice_id:
            cur.execute("SELECT * FROM asr_chunks WHERE task_id = ? AND slice_run_id = ? ORDER BY chunk_index ASC", (task_id, latest_slice_id))
        else:
            cur.execute("SELECT * FROM asr_chunks WHERE task_id = ? ORDER BY chunk_index ASC", (task_id,))

        chunks = []
        for r in cur.fetchall():
            d = dict(r)
            d["quality_stats"] = json.loads(d["quality_stats"]) if d["quality_stats"] else {}
            chunks.append(d)

        return {
            "task_id": task_id,
            "candidates": candidates,
            "issues": issues,
            "chunks": chunks,
        }


@app.patch("/api/v1/tasks/{task_id}/asr/candidates/{candidate_id}")
def edit_asr_candidate(
    task_id: str,
    candidate_id: str,
    req: EditCandidateRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工编辑候选")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM candidates WHERE candidate_id = ? AND task_id = ?", (candidate_id, task_id))
        cand = cur.fetchone()
        if not cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选记录不存在")

        if cand["candidate_revision"] != req.expected_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_INPUT: 候选版本冲突（当前 {cand['candidate_revision']} != 预期 {req.expected_revision}）",
            )

        proposed = json.loads(cand["proposed"])

        # Preserve original model output if not yet saved
        if "original_model_output" not in proposed:
            proposed["original_model_output"] = {
                "text": proposed.get("text", ""),
                "start_ms": proposed.get("start_ms"),
                "end_ms": proposed.get("end_ms"),
            }

        # Determine effective text and timestamps
        eff_text = req.text if req.text is not None else proposed.get("text", "")
        eff_start = req.start_ms if req.start_ms is not None else proposed.get("start_ms", 0)
        eff_end = req.end_ms if req.end_ms is not None else proposed.get("end_ms", 0)

        # 1. Non-negative & ordered timestamp validation
        if eff_start is not None and eff_start < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="时间范围非法：起始时间不能为负数",
            )
        if eff_end is not None and eff_start is not None and eff_end <= eff_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="时间范围非法：结束时间必须严格大于起始时间（逆序或0时长错误）",
            )

        # 2. Out-of-bounds validation against media duration
        cur.execute("SELECT m.duration_ms FROM tasks t LEFT JOIN media m ON t.media_id = m.media_id WHERE t.task_id = ?", (task_id,))
        m_row = cur.fetchone()
        if m_row and m_row["duration_ms"]:
            max_media_dur = m_row["duration_ms"]
            # Allow 1000ms grace window for boundary rounding
            if eff_end is not None and eff_end > max_media_dur + 1000:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"时间范围越界：结束时间 ({eff_end}ms) 超出母版总时长 ({max_media_dur}ms)",
                )

        proposed["text"] = eff_text
        if eff_start is not None:
            proposed["start_ms"] = eff_start
        if eff_end is not None:
            proposed["end_ms"] = eff_end

        # 3. Distinguish draft saving from human confirmation
        old_status = cand["candidate_status"]
        if req.confirm is True:
            new_status = "EDITED_ACCEPTED"
        elif req.confirm is False:
            new_status = "EDITED_DRAFT"
        else:
            # If not explicitly specified: preserve EDITED_ACCEPTED if already confirmed; otherwise mark EDITED_DRAFT
            if old_status == "EDITED_ACCEPTED":
                new_status = "EDITED_ACCEPTED"
            else:
                new_status = "EDITED_DRAFT"

        new_rev = cand["candidate_revision"] + 1
        new_hash = hashlib.sha256(proposed["text"].encode("utf-8")).hexdigest()

        conn.execute("""
        UPDATE candidates
        SET candidate_revision = ?, proposed = ?, candidate_status = ?,
            content_hash = ?
        WHERE candidate_id = ?;
        """, (new_rev, json.dumps(proposed), new_status, new_hash, candidate_id))

        # Record Decision
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        action_name = "confirm_candidate" if new_status == "EDITED_ACCEPTED" else "save_candidate_draft"
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            decision_id, task_id, None, "edit_candidate", action_name,
            actor.actor_id, actor.actor_role,
            json.dumps({"candidate_id": candidate_id, "revision": new_rev}),
            json.dumps({
                "new_text": proposed["text"],
                "start_ms": proposed.get("start_ms"),
                "end_ms": proposed.get("end_ms"),
                "status": new_status,
                "confirmed": (new_status == "EDITED_ACCEPTED"),
            }),
            now,
        ))

        return {
            "candidate_id": candidate_id,
            "task_id": task_id,
            "candidate_revision": new_rev,
            "candidate_status": new_status,
            "proposed": proposed,
        }


@app.post("/api/v1/tasks/{task_id}/asr/entities/confirm")
def confirm_asr_entity(
    task_id: str,
    req: ConfirmEntityRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工确认专名")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        # Close matching unconfirmed entity issue
        conn.execute("""
        UPDATE issues
        SET status = 'RESOLVED'
        WHERE task_id = ? AND category = 'unknown_entity' AND detail LIKE ?;
        """, (task_id, f"%'{req.name}'%"))

        # Update entity in candidates
        cur.execute("SELECT * FROM candidates WHERE task_id = ?", (task_id,))
        cands = cur.fetchall()
        for c in cands:
            entities = json.loads(c["entity_info"]) if c["entity_info"] else []
            updated = False
            for ent in entities:
                if ent.get("name") == req.name:
                    ent["match_status"] = "matched"
                    ent["glossary_ref"] = "HUMAN_CONFIRMED"
                    if req.confirmed_name:
                        ent["name"] = req.confirmed_name
                    updated = True
            if updated:
                conn.execute("""
                UPDATE candidates SET entity_info = ? WHERE candidate_id = ?;
                """, (json.dumps(entities), c["candidate_id"]))

        # Record Decision
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            decision_id, task_id, None, "confirm_entity", "confirm",
            actor.actor_id, actor.actor_role,
            json.dumps({"entity_name": req.name, "category": req.category}),
            json.dumps({"confirmed_name": req.confirmed_name or req.name}),
            now,
        ))

    return {"status": "confirmed", "entity_name": req.name}


# =========================================================================
# Task A & Gate 1: 源语整理与第一人工关口
# =========================================================================

class CleanupSourceRequest(BaseModel):
    simulate: bool = False
    source_language: Optional[str] = "zh-CN"


@app.post("/api/v1/tasks/{task_id}/source/cleanup")
def cleanup_task_source(
    task_id: str,
    req: CleanupSourceRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "申请执行")
    if req.simulate and not is_test_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="普通正式环境禁止使用模拟整理。模拟仅允许在显式服务端测试模式（SUBTITLE_TEST_MODE=1）及隔离测试环境下运行。",
        )
    try:
        res = execute_source_cleanup(
            task_id=task_id,
            source_language=req.source_language or "zh-CN",
            simulate=req.simulate,
            database=db,
        )
        return res
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/v1/tasks/{task_id}/source-transcript")
def get_task_source_transcript(
    task_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM source_transcripts WHERE task_id = ? ORDER BY revision DESC LIMIT 1", (task_id,))
        trans_row = cur.fetchone()
        if not trans_row:
            return {"status": "NOT_STARTED", "revision": 0, "utterances": [], "speakers": []}

        rev = trans_row["revision"]
        cur.execute("""
        SELECT * FROM source_utterances WHERE task_id = ? AND transcript_revision = ? ORDER BY unit_index ASC
        """, (task_id, rev))
        utterances = []
        for r in cur.fetchall():
            d = dict(r)
            d["source_spans"] = json.loads(d["source_spans"]) if d["source_spans"] else []
            d["uncertainties"] = json.loads(d["uncertainties"]) if d["uncertainties"] else []
            utterances.append(d)

        cur.execute("""
        SELECT * FROM source_speakers WHERE task_id = ? AND transcript_revision = ? ORDER BY speaker_id ASC
        """, (task_id, rev))
        speakers = []
        for r in cur.fetchall():
            d = dict(r)
            d["evidence_refs"] = json.loads(d["evidence_refs"]) if d["evidence_refs"] else []
            d["uncertainties"] = json.loads(d["uncertainties"]) if d["uncertainties"] else []
            speakers.append(d)

        return {
            "transcript_id": trans_row["transcript_id"],
            "revision": rev,
            "status": trans_row["status"],
            "source_language": trans_row["source_language"],
            "confirmed_by": trans_row["confirmed_by"],
            "confirmed_at": trans_row["confirmed_at"],
            "utterances": utterances,
            "speakers": speakers,
        }


@app.patch("/api/v1/tasks/{task_id}/source-transcript/utterances/{unit_id}")
def edit_source_utterance(
    task_id: str,
    unit_id: str,
    req: EditUtteranceRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "编辑源语台词")
    now = utc_now_iso()
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM source_transcripts WHERE task_id = ? ORDER BY revision DESC LIMIT 1", (task_id,))
        trans_row = cur.fetchone()
        if not trans_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="源语稿不存在")

        current_rev = trans_row["revision"]
        if req.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"修订冲突: 期望修订版本为 {req.expected_revision}，但当前版本已为 {current_rev}",
            )

        cur.execute("SELECT * FROM source_utterances WHERE task_id = ? AND transcript_revision = ? AND unit_id = ?", (task_id, current_rev, unit_id))
        target_utt = cur.fetchone()
        if not target_utt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话单元不存在")

        # Fetch all utterances and speakers of current revision to clone into new revision
        cur.execute("SELECT * FROM source_utterances WHERE task_id = ? AND transcript_revision = ? ORDER BY unit_index ASC", (task_id, current_rev))
        all_utts = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM source_speakers WHERE task_id = ? AND transcript_revision = ?", (task_id, current_rev))
        all_speakers = [dict(r) for r in cur.fetchall()]

        # Rule 4: Modification MUST create a new source revision, revoke confirmation, and expire older translations
        new_rev = current_rev + 1
        new_tr_id = f"tr_{uuid.uuid4().hex[:12]}"

        conn.execute("""
        INSERT INTO source_transcripts (
            transcript_id, task_id, revision, status, source_language,
            run_id, confirmed_by, confirmed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            new_tr_id, task_id, new_rev, "AI_PROPOSED",
            trans_row["source_language"], trans_row["run_id"],
            None, None, now, now
        ))

        # Copy speakers to new revision
        for spk in all_speakers:
            spk_char = req.character_ref if (spk["speaker_id"] == target_utt["speaker_id"] and req.character_ref is not None) else spk["character_ref"]
            conn.execute("""
            INSERT OR REPLACE INTO source_speakers (
                speaker_id, task_id, transcript_revision, display_name,
                character_ref, evidence_refs, uncertainties, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                spk["speaker_id"], task_id, new_rev, spk["display_name"],
                spk_char, spk["evidence_refs"], spk["uncertainties"], now
            ))

        # Copy utterances to new revision, applying edits to targeted unit
        for u in all_utts:
            u_text = req.text.strip() if (u["unit_id"] == unit_id and req.text is not None) else u["text"]
            u_spk = req.speaker_id.strip() if (u["unit_id"] == unit_id and req.speaker_id is not None) else u["speaker_id"]
            u_char = req.character_ref.strip() if (u["unit_id"] == unit_id and req.character_ref is not None) else u["character_ref"]
            u_start = req.start_ms if (u["unit_id"] == unit_id and req.start_ms is not None) else u["start_ms"]
            u_end = req.end_ms if (u["unit_id"] == unit_id and req.end_ms is not None) else u["end_ms"]

            conn.execute("""
            INSERT OR REPLACE INTO source_utterances (
                unit_id, task_id, transcript_revision, unit_index, speaker_id,
                character_ref, text, source_spans, start_ms, end_ms,
                timing_precision, uncertainties, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                u["unit_id"], task_id, new_rev, u["unit_index"], u_spk,
                u_char, u_text, u["source_spans"], u_start, u_end,
                u["timing_precision"], u["uncertainties"], "AI_PROPOSED", now, now
            ))

        # Invalidate existing translations for older source revisions
        conn.execute("""
        UPDATE translations
        SET status = 'EXPIRED', updated_at = ?
        WHERE task_id = ? AND source_revision < ?;
        """, (now, task_id, new_rev))

        # Record decision
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"dec_{uuid.uuid4().hex[:12]}", task_id, None, "edit_source_utterance", "edit_and_bump_revision",
            actor.actor_id, actor.actor_role,
            json.dumps({"unit_id": unit_id, "new_revision": new_rev}),
            json.dumps({"from_revision": current_rev, "to_revision": new_rev, "text": req.text, "speaker_id": req.speaker_id, "character_ref": req.character_ref}),
            now,
        ))

    return {
        "status": "AI_PROPOSED",
        "unit_id": unit_id,
        "revision": new_rev,
        "previous_revision": current_rev,
        "message": "修改成功，已生成源稿新修订并撤销确认状态，旧版译文已标记失效",
    }


@app.post("/api/v1/tasks/{task_id}/source-transcript/confirm")
def confirm_source_transcript(
    task_id: str,
    req: ConfirmSourceTranscriptRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工确认源稿")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM source_transcripts WHERE task_id = ? ORDER BY revision DESC LIMIT 1", (task_id,))
        trans_row = cur.fetchone()
        if not trans_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="源语稿不存在")

        current_rev = trans_row["revision"]
        if req.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"修订冲突: 期望修订版本为 {req.expected_revision}，但当前版本已为 {current_rev}",
            )

        # Check unresolved doubts
        cur.execute("SELECT * FROM source_utterances WHERE task_id = ? AND transcript_revision = ?", (task_id, current_rev))
        utts = [dict(r) for r in cur.fetchall()]
        has_doubts = False
        for u in utts:
            uncs = json.loads(u["uncertainties"]) if u["uncertainties"] else []
            if uncs:
                has_doubts = True
                break

        if has_doubts and not req.force_ignore_doubts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="源稿存在尚未解决的关键疑点，必须逐条复核或由人工显式声明忽略(force_ignore_doubts)方可通过",
            )

        # Confirm source transcript
        conn.execute("""
        UPDATE source_transcripts
        SET status = 'CONFIRMED', confirmed_by = ?, confirmed_at = ?, updated_at = ?
        WHERE task_id = ? AND revision = ?;
        """, (actor.actor_id, now, now, task_id, current_rev))

        conn.execute("""
        UPDATE source_utterances
        SET status = 'CONFIRMED', updated_at = ?
        WHERE task_id = ? AND transcript_revision = ?;
        """, (now, task_id, current_rev))

        # Invalidation rule: Old translations for older source revisions are marked EXPIRED
        conn.execute("""
        UPDATE translations
        SET status = 'EXPIRED', updated_at = ?
        WHERE task_id = ? AND source_revision < ?;
        """, (now, task_id, current_rev))

        # Record decision
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"dec_{uuid.uuid4().hex[:12]}", task_id, None, "confirm_source_transcript", "confirm",
            actor.actor_id, actor.actor_role,
            json.dumps({"transcript_id": trans_row["transcript_id"], "revision": current_rev}),
            json.dumps({"force_ignore_doubts": req.force_ignore_doubts, "reason": req.reason}),
            now,
        ))

    return {
        "status": "CONFIRMED",
        "task_id": task_id,
        "revision": current_rev,
        "confirmed_by": actor.actor_id,
        "confirmed_at": now,
    }


# =========================================================================
# Knowledge & Memory: 知识库、术语与锁词
# =========================================================================

@app.get("/api/v1/projects/{project_id}/knowledge")
def list_project_knowledge(
    project_id: str,
    category: Optional[str] = None,
    scope: Optional[str] = None,
    only_confirmed: bool = False,
    actor: ActorContext = Depends(get_current_actor),
):
    return knowledge_service.list_items(
        project_id=project_id,
        category=category,
        scope=scope,
        only_confirmed=only_confirmed,
    )


@app.post("/api/v1/projects/{project_id}/knowledge")
def create_project_knowledge(
    project_id: str,
    req: KnowledgeItemCreate,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "添加知识条目")
    req.project_id = project_id
    try:
        item = knowledge_service.create_item(req, actor_id=actor.actor_id, actor_role=actor.actor_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return item


@app.patch("/api/v1/projects/{project_id}/knowledge/{item_id}")
def update_project_knowledge(
    project_id: str,
    item_id: str,
    req: KnowledgeItemUpdate,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "更新知识条目")
    try:
        updated = knowledge_service.update_item(
            item_id, req, actor_id=actor.actor_id, actor_role=actor.actor_role
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    return updated


@app.delete("/api/v1/projects/{project_id}/knowledge/{item_id}")
def delete_project_knowledge(
    project_id: str,
    item_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "删除知识条目")
    ok = knowledge_service.delete_item(item_id, actor_id=actor.actor_id, actor_role=actor.actor_role)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    return {"status": "deleted", "item_id": item_id}


# =========================================================================
# Task B & C & Gate 2: 初翻生成、语义检查与第二人工关口
# =========================================================================

@app.post("/api/v1/tasks/{task_id}/translation/generate")
def generate_translation(
    task_id: str,
    req: GenerateTranslationRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_permission(actor, "申请执行")
    if req.simulate and not is_test_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="普通正式环境禁止使用模拟初翻。模拟仅允许在显式服务端测试模式（SUBTITLE_TEST_MODE=1）及隔离测试环境下运行。",
        )
    try:
        res = execute_translation_pipeline(
            task_id=task_id,
            req=req,
            actor_id=actor.actor_id,
            database=db,
        )
        return res
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/v1/tasks/{task_id}/translations")
def get_task_translations(
    task_id: str,
    actor: ActorContext = Depends(get_current_actor),
):
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT revision FROM source_transcripts WHERE task_id = ? ORDER BY revision DESC LIMIT 1", (task_id,))
        tr_row = cur.fetchone()
        source_rev = tr_row["revision"] if tr_row else 1

        cur.execute("""
        SELECT * FROM translations
        WHERE task_id = ? AND source_revision = ?
        ORDER BY translation_revision DESC, rowid DESC
        """, (task_id, source_rev))
        translations = []
        seen_units = set()
        for r in cur.fetchall():
            if r["unit_id"] in seen_units:
                continue
            seen_units.add(r["unit_id"])
            d = dict(r)
            d["is_locked"] = bool(d["is_locked"])
            d["term_hits"] = json.loads(d["term_hits"]) if d["term_hits"] else []
            translations.append(d)

        # Get checks
        cur.execute("SELECT * FROM translation_checks WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
        checks = []
        current_ids = {t["translation_id"] for t in translations}
        for r in cur.fetchall():
            if r["translation_id"] not in current_ids:
                continue
            cd = dict(r)
            cd["evidence_refs"] = json.loads(cd["evidence_refs"]) if cd["evidence_refs"] else []
            checks.append(cd)

        # Get latest run manifest
        cur.execute("""
        SELECT * FROM runs WHERE task_id = ? AND module = 'translation' ORDER BY created_at DESC LIMIT 1
        """, (task_id,))
        run_row = cur.fetchone()
        manifest = {}
        if run_row:
            manifest = {
                "run_id": run_row["run_id"],
                "context_manifest": json.loads(run_row["context_manifest"]) if run_row["context_manifest"] else {},
                "usage": json.loads(run_row["usage"]) if run_row["usage"] else {},
                "started_at": run_row["started_at"],
                "ended_at": run_row["ended_at"],
            }

        return {
            "task_id": task_id,
            "source_revision": source_rev,
            "translations": translations,
            "checks": checks,
            "manifest": manifest,
            "qe_status": "未评估",
        }


def _review_translation(cur, task_id, unit_id, req, require_clear=False):
    source = cur.execute("SELECT revision,status FROM source_transcripts WHERE task_id=? ORDER BY revision DESC LIMIT 1", (task_id,)).fetchone()
    if not source or source['status'] != 'CONFIRMED' or source['revision'] != req.source_revision:
        raise HTTPException(409, '源稿已变化或尚未确认，请刷新后复核')
    row = cur.execute("SELECT * FROM translations WHERE task_id=? AND unit_id=? AND source_revision=? ORDER BY translation_revision DESC, rowid DESC LIMIT 1", (task_id, unit_id, req.source_revision)).fetchone()
    if not row:
        raise HTTPException(404, '当前源稿对应译文不存在')
    if row['translation_revision'] != req.expected_revision or row['status'] == 'EXPIRED':
        raise HTTPException(409, '译文修订已变化，请刷新后复核')
    if require_clear and cur.execute("SELECT 1 FROM translation_checks WHERE translation_id=? AND severity='BLOCK' AND status='OPEN' LIMIT 1", (row['translation_id'],)).fetchone():
        raise HTTPException(400, '存在未解决的锁词或语义检查阻断，不能确认/锁定')
    return row


@app.patch("/api/v1/tasks/{task_id}/translations/{unit_id}")
def edit_unit_translation(
    task_id: str,
    unit_id: str,
    req: EditTranslationRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工编辑初翻")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        trans_row = _review_translation(cur, task_id, unit_id, req, require_clear=False)

        current_rev = trans_row["translation_revision"]
        if req.expected_revision != current_rev:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"修订冲突: 期望修订版本为 {req.expected_revision}，但当前版本已为 {current_rev}",
            )

        if trans_row["is_locked"]:
            raise HTTPException(409, "译稿已锁定，请先显式解除锁定")
        if not req.text.strip():
            raise HTTPException(400, "译文不能为空")
        new_rev = current_rev + 1
        new_text = req.text.strip()

        conn.execute("""
        UPDATE translations
        SET text = ?, translation_revision = ?, status = 'AI_PROPOSED', confirmed_by = ?, confirmed_at = ?, updated_at = ?
        WHERE translation_id = ?;
        """, (new_text, new_rev, None, None, now, trans_row["translation_id"]))

        # Append to translation_history
        conn.execute("""
        INSERT INTO translation_history (
            history_id, task_id, unit_id, translation_id, revision,
            text, status, actor_id, action, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"th_{uuid.uuid4().hex[:12]}", task_id, unit_id, trans_row["translation_id"],
            new_rev, new_text, "AI_PROPOSED", actor.actor_id, "human_edit", now
        ))

    return {"status": "AI_PROPOSED", "unit_id": unit_id, "revision": new_rev, "text": new_text}


@app.post("/api/v1/tasks/{task_id}/translations/{unit_id}/confirm")
def confirm_unit_translation(
    task_id: str,
    unit_id: str,
    req: TranslationRevisionRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工确认初翻")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        trans_row = _review_translation(cur, task_id, unit_id, req, require_clear=True)

        conn.execute("""
        UPDATE translations
        SET status = 'CONFIRMED', confirmed_by = ?, confirmed_at = ?, updated_at = ?
        WHERE translation_id = ?;
        """, (actor.actor_id, now, now, trans_row["translation_id"]))

        # Record decision
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"dec_{uuid.uuid4().hex[:12]}", task_id, None, "confirm_translation_unit", "confirm",
            actor.actor_id, actor.actor_role,
            json.dumps({"unit_id": unit_id}),
            json.dumps({"text": trans_row["text"]}),
            now,
        ))

    return {"status": "CONFIRMED", "unit_id": unit_id}


@app.post("/api/v1/tasks/{task_id}/translations/{unit_id}/lock")
def lock_unit_translation(
    task_id: str,
    unit_id: str,
    req: TranslationRevisionRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "锁定初翻译文")
    now = utc_now_iso()
    with db.transaction() as conn:
        cur = conn.cursor()
        trans_row = _review_translation(cur, task_id, unit_id, req, require_clear=True)

        conn.execute("""
        UPDATE translations
        SET is_locked = 1, status = 'LOCKED', updated_at = ?
        WHERE translation_id = ?;
        """, (now, trans_row["translation_id"]))

    return {"status": "LOCKED", "unit_id": unit_id, "is_locked": True}


@app.post("/api/v1/tasks/{task_id}/translations/{unit_id}/unlock")
def unlock_unit_translation(
    task_id: str,
    unit_id: str,
    req: TranslationRevisionRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "解除初翻锁定")
    now = utc_now_iso()
    with db.transaction() as conn:
        cur = conn.cursor()
        trans_row = _review_translation(cur, task_id, unit_id, req, require_clear=False)

        conn.execute("""
        UPDATE translations
        SET is_locked = 0, status = 'CONFIRMED', updated_at = ?
        WHERE translation_id = ?;
        """, (now, trans_row["translation_id"]))

    return {"status": "CONFIRMED", "unit_id": unit_id, "is_locked": False}


@app.post("/api/v1/tasks/{task_id}/translations/{unit_id}/rollback")
def rollback_unit_translation(
    task_id: str,
    unit_id: str,
    req: RollbackTranslationRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "人工回滚初翻")
    now = utc_now_iso()

    with db.transaction() as conn:
        cur = conn.cursor()
        trans_row = _review_translation(cur, task_id, unit_id, req, require_clear=False)

        # Find historical revision
        cur.execute("""
        SELECT * FROM translation_history
        WHERE translation_id = ? AND revision = ?
        ORDER BY created_at DESC LIMIT 1
        """, (trans_row["translation_id"], req.target_revision))
        hist_row = cur.fetchone()
        if not hist_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到目标修订历史版本 {req.target_revision}",
            )

        target_text = hist_row["text"]
        new_rev = trans_row["translation_revision"] + 1

        # Copy historical content to new revision (never delete history!)
        conn.execute("""
        UPDATE translations
        SET text = ?, translation_revision = ?, status = 'AI_PROPOSED', is_locked = 0, confirmed_by = ?, confirmed_at = ?, updated_at = ?
        WHERE translation_id = ?;
        """, (target_text, new_rev, None, None, now, trans_row["translation_id"]))

        conn.execute("""
        INSERT INTO translation_history (
            history_id, task_id, unit_id, translation_id, revision,
            text, status, actor_id, action, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"th_{uuid.uuid4().hex[:12]}", task_id, unit_id, trans_row["translation_id"],
            new_rev, target_text, "AI_PROPOSED", actor.actor_id, f"rollback_from_rev_{req.target_revision}", now
        ))

        # Record decision
        conn.execute("""
        INSERT INTO decisions (
            decision_id, task_id, media_id, decision_type, action,
            actor_id, actor_role, target_ref, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            f"dec_{uuid.uuid4().hex[:12]}", task_id, None, "rollback_translation", "rollback",
            actor.actor_id, actor.actor_role,
            json.dumps({"unit_id": unit_id, "from_revision": req.target_revision, "to_revision": new_rev}),
            json.dumps({"reason": req.reason, "restored_text": target_text}),
            now,
        ))

    return {
        "status": "AI_PROPOSED",
        "unit_id": unit_id,
        "revision": new_rev,
        "restored_from_revision": req.target_revision,
        "text": target_text,
    }


@app.post("/api/v1/tasks/{task_id}/translations/confirm-all")
def confirm_all_task_translations(
    task_id: str,
    req: ConfirmAllTranslationsRequest,
    actor: ActorContext = Depends(get_current_actor),
):
    require_human_actor(actor, "批量确认初翻")
    if not req.expected_revisions:
        raise HTTPException(400, "没有待确认译稿")
    now = utc_now_iso()
    with db.transaction() as conn:
        cur = conn.cursor()
        latest = cur.execute("SELECT unit_id,translation_revision FROM translations WHERE task_id=? AND source_revision=? ORDER BY translation_revision ASC,rowid ASC", (task_id, req.source_revision)).fetchall()
        expected = {r['unit_id']: r['translation_revision'] for r in latest}
        if expected != req.expected_revisions:
            raise HTTPException(409, "译稿列表已变化，请刷新后确认")
        rows = [_review_translation(cur, task_id, uid, TranslationRevisionRequest(source_revision=req.source_revision, expected_revision=rev), require_clear=True) for uid,rev in req.expected_revisions.items()]
        for row in rows:
            conn.execute("UPDATE translations SET status='CONFIRMED',confirmed_by=?,confirmed_at=?,updated_at=? WHERE translation_id=?", (actor.actor_id,now,now,row['translation_id']))
        conn.execute("INSERT INTO decisions (decision_id,task_id,media_id,decision_type,action,actor_id,actor_role,target_ref,payload,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (f"dec_{uuid.uuid4().hex[:12]}",task_id,None,'confirm_all_translations','confirm',actor.actor_id,actor.actor_role,json.dumps({'source_revision':req.source_revision}),json.dumps(req.expected_revisions),now))
    return {"status":"CONFIRMED","task_id":task_id}


# Culture uses the same trusted operator sessions and current workflow DB.
from code.backend.modules.culture_check.integration import WorkflowCultureAdapter
from code.backend.modules.culture_check.repository import CultureRepository
from code.backend.modules.culture_check.router import create_culture_router

class _CurrentCultureRepository:
    """Resolve at request time so isolated tests never capture the production DB."""
    def __getattr__(self, name):
        cached = getattr(app.state, "culture_repository", None)
        if cached is None or cached.db is not db:
            cached = CultureRepository(db)
            app.state.culture_repository = cached
        return getattr(cached, name)

class _CurrentCultureAdapter:
    def __getattr__(self, name):
        return getattr(WorkflowCultureAdapter(db), name)

app.include_router(create_culture_router(
    repository=_CurrentCultureRepository(), get_actor_context=get_current_actor,
    task_adapter=_CurrentCultureAdapter(), translation_adapter=_CurrentCultureAdapter(),
))

@app.get("/api/v1/culture/tasks/{task_id}/latest-run")
def latest_culture_run(task_id: str, actor: ActorContext = Depends(get_current_actor)):
    WorkflowCultureAdapter(db).authorize_task(task_id, actor)
    repository = _CurrentCultureRepository()
    with repository.db.transaction() as conn:
        row = conn.execute("SELECT run_id FROM culture_runs WHERE task_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (task_id,)).fetchone()
    return repository.get_run(row['run_id']) if row else None

# 单位/口语只读取服务端当前确认稿；合规产物与签发持久化SQLite，缺证据阻断交付。
from code.backend.modules.compliance.router import (
    SqliteArtifactStore,
    create_compliance_router,
)

from code.backend.workflow.delivery import create_current_review_router
app.include_router(create_current_review_router(lambda:db,get_current_actor))
from code.backend.modules.compliance.integration import WorkflowComplianceAdapter
class _CurrentDeliveryStore:
    def __getattr__(self,name):return getattr(SqliteArtifactStore(db),name)
class _CurrentDeliveryAdapter:
    def __getattr__(self,name):return getattr(WorkflowComplianceAdapter(db),name)
app.include_router(create_compliance_router(get_actor_context=get_current_actor,storage_adapter=_CurrentDeliveryStore(),task_adapter=_CurrentDeliveryAdapter()))

# Mount Static Frontend
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

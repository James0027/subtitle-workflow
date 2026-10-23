import hashlib
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from code.backend.db import db, utc_now_iso
from code.backend.shared.models import ActorContext
from code.backend.shared.storage import default_storage
from code.backend.shared.tools.media import media_tool


class IngestError(Exception):
    pass


class IngestWorker:
    def __init__(self):
        # Single worker mutual exclusion lock to guarantee strict serial extraction
        self._worker_lock = threading.Lock()

    def recover_stale_runs(self) -> int:
        """
        Marks stranded RUNNING runs as STOPPED (schema-compliant enum) upon server start/crash recovery.
        Recorded with stop_reason='SERVER_RESTARTED' and failure details.
        """
        now = utc_now_iso()
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE runs
            SET run_status = 'STOPPED',
                stop_reason = 'SERVER_RESTARTED',
                ended_at = ?,
                failure = json_object('code', 'SERVER_RESTARTED', 'category', 'system', 'retryable', 1, 'detail', '服务重启中断，任务可重新触发')
            WHERE run_status = 'RUNNING' AND module = 'ingest'
            """, (now,))
            return cur.rowcount

    def get_run(self, task_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Queries status and details of an ingest run for progress tracking.
        """
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM runs WHERE run_id = ? AND task_id = ?", (run_id, task_id))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            for k in ["input_refs", "attempts", "context_manifest", "steps", "usage", "controls", "output_refs", "failure"]:
                if res.get(k):
                    try:
                        res[k] = json.loads(res[k])
                    except Exception:
                        pass
            return res

    def extract_audio(
        self,
        task_id: str,
        video_asset_id: str,
        stream_index: int,
        actor: ActorContext,
    ) -> Dict[str, Any]:
        """
        Executes single-worker audio extraction with persistent Run intake, atomic claim,
        comprehensive idempotency key (task/asset revisions & range), and trace logging.
        """
        now = utc_now_iso()

        # Step 1: Atomic task validation, idempotency check, and Run intake (READY state)
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            task_row = cur.fetchone()
            if not task_row:
                raise IngestError(f"Task not found: {task_id}")

            project_id = task_row["project_id"]
            task_rev = task_row["task_revision"]
            task_range_raw = task_row["range"] or "{}"
            range_hash = hashlib.sha256(task_range_raw.encode("utf-8")).hexdigest()[:12]

            cur.execute("SELECT * FROM assets WHERE asset_id = ? AND project_id = ?", (video_asset_id, project_id))
            video_row = cur.fetchone()
            if not video_row:
                raise IngestError(f"Video asset not found or access denied: {video_asset_id}")

            video_rev = video_row["revision"]
            video_uri = video_row["source_uri"]

            # Comprehensive idempotency key containing task revision, video revision, track, and range
            idempotency_key = f"{task_id}:rev{task_rev}:ingest:{video_asset_id}:rev{video_rev}:track{stream_index}:range{range_hash}"

            # Check existing Run
            cur.execute("""
            SELECT * FROM runs
            WHERE idempotency_key = ?
            ORDER BY created_at DESC LIMIT 1
            """, (idempotency_key,))
            existing_run = cur.fetchone()

            if existing_run:
                # If already SUCCEEDED, verify artifact and return idempotently
                if existing_run["run_status"] == "SUCCEEDED":
                    output_refs = json.loads(existing_run["output_refs"]) if existing_run["output_refs"] else []
                    if output_refs:
                        derived_id = output_refs[0]["entity_id"]
                        cur.execute("SELECT * FROM assets WHERE asset_id = ?", (derived_id,))
                        derived_row = cur.fetchone()
                        if derived_row:
                            try:
                                real_p = default_storage.get_real_path(derived_row["source_uri"])
                                if real_p.exists():
                                    insp = json.loads(derived_row["inspection"]) if derived_row["inspection"] else {}
                                    return {
                                        "run_id": existing_run["run_id"],
                                        "run_status": "SUCCEEDED",
                                        "derived_asset_id": derived_id,
                                        "source_uri": derived_row["source_uri"],
                                        "checksum_sha256": derived_row["checksum_sha256"],
                                        "size_bytes": derived_row["size_bytes"],
                                        "inspection": insp,
                                        "idempotent": True,
                                    }
                            except Exception:
                                pass

                # If RUNNING or READY, another execution is already processing this exact specification
                if existing_run["run_status"] in ("READY", "RUNNING"):
                    return {
                        "run_id": existing_run["run_id"],
                        "run_status": existing_run["run_status"],
                        "idempotent": True,
                        "detail": f"抽轨任务正在处理中 (Run ID: {existing_run['run_id']})",
                    }

            # Invalidate task confirmation if task was READY
            if task_row["task_status"] == "READY":
                conn.execute("""
                UPDATE tasks
                SET task_status = 'DRAFT', task_revision = task_revision + 1, updated_at = ?
                WHERE task_id = ?
                """, (now, task_id))
                task_rev += 1
                idempotency_key = f"{task_id}:rev{task_rev}:ingest:{video_asset_id}:rev{video_rev}:track{stream_index}:range{range_hash}"

            # Invalidate media confirmation if media exists
            if task_row["media_id"]:
                conn.execute("""
                UPDATE media
                SET master_status = 'REGISTERED', revision = revision + 1
                WHERE media_id = ? AND master_status = 'CONFIRMED'
                """, (task_row["media_id"],))

            # Atomically insert persistent Run in READY state
            run_id = f"run_ingest_{uuid.uuid4().hex[:12]}"
            trace_id = f"trace_{uuid.uuid4().hex[:12]}"
            derived_asset_id = f"asset_audio_{uuid.uuid4().hex[:12]}"

            tool_version = media_tool.get_ffmpeg_version()
            context_manifest = {
                "tool": "ffmpeg",
                "version": tool_version,
                "task_id": task_id,
                "task_revision": task_rev,
                "video_asset_id": video_asset_id,
                "video_revision": video_rev,
                "stream_index": stream_index,
                "codec": "pcm_s16le",
            }
            manifest_str = json.dumps(context_manifest, sort_keys=True)
            manifest_hash = hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()

            conn.execute("""
            INSERT INTO runs (
                run_id, task_id, task_revision, trace_id, module,
                input_refs, input_revision, idempotency_key, attempt_no,
                attempts, run_status, context_manifest, manifest_hash,
                steps, started_at, usage, controls, output_refs, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, task_id, task_rev, trace_id, "ingest",
                json.dumps([{"entity_type": "Asset", "entity_id": video_asset_id, "revision": video_rev}]),
                video_rev, idempotency_key, 1,
                json.dumps([{"attempt_no": 1, "status": "READY", "created_at": now}]),
                "READY", json.dumps(context_manifest), manifest_hash,
                json.dumps([{"step_id": "extract_audio", "name": "FFmpeg抽轨", "actor_type": "code", "status": "pending"}]),
                None, json.dumps({}), json.dumps({}), json.dumps([]), now, actor.actor_id,
            ))

        # Step 2: Acquire single-worker mutual exclusion lock and claim Run into RUNNING
        with self._worker_lock:
            run_start_now = utc_now_iso()
            with db.transaction() as conn:
                cur = conn.cursor()
                cur.execute("SELECT run_status FROM runs WHERE run_id = ?", (run_id,))
                r_status = cur.fetchone()
                if not r_status or r_status["run_status"] != "READY":
                    # Already claimed or processed
                    cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                    return dict(cur.fetchone())

                conn.execute("""
                UPDATE runs
                SET run_status = 'RUNNING', started_at = ?,
                    attempts = ?, steps = ?
                WHERE run_id = ?
                """, (
                    run_start_now,
                    json.dumps([{"attempt_no": 1, "status": "RUNNING", "started_at": run_start_now}]),
                    json.dumps([{"step_id": "extract_audio", "name": "FFmpeg抽轨", "actor_type": "code", "status": "running"}]),
                    run_id,
                ))

            # Step 3: Perform FFmpeg audio extraction
            video_real_path = default_storage.get_real_path(video_uri)
            out_filename = f"extracted_track_{stream_index}.wav"
            target_dir = (default_storage.base_dir / project_id / derived_asset_id).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            out_wav_path = target_dir / out_filename

            try:
                extract_res = media_tool.extract_audio_track(
                    video_path=video_real_path,
                    stream_index=stream_index,
                    output_wav_path=out_wav_path,
                )
                wav_inspection = media_tool.inspect_file(out_wav_path)
            except Exception as e:
                # Mark Run FAILED with structured failure
                fail_now = utc_now_iso()
                with db.transaction() as conn:
                    conn.execute("""
                    UPDATE runs
                    SET run_status = 'FAILED', ended_at = ?,
                        failure = ?,
                        attempts = ?,
                        steps = ?
                    WHERE run_id = ?;
                    """, (
                        fail_now,
                        json.dumps({"code": "EXTRACTION_FAILED", "category": "media", "retryable": False, "detail": str(e)}),
                        json.dumps([{"attempt_no": 1, "status": "FAILED", "started_at": run_start_now, "ended_at": fail_now, "error": str(e)}]),
                        json.dumps([{"step_id": "extract_audio", "name": "FFmpeg抽轨", "actor_type": "code", "status": "failed", "error": str(e)}]),
                        run_id,
                    ))
                raise IngestError(f"抽轨派生失败: {str(e)}")

            # Step 4: Compute hash and persist derived Asset
            sha256 = hashlib.sha256()
            with open(out_wav_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    sha256.update(chunk)
            checksum_sha256 = sha256.hexdigest()
            size_bytes = out_wav_path.stat().st_size
            rel_uri = str(out_wav_path.relative_to(default_storage.base_dir)).replace("\\", "/")

            finish_now = utc_now_iso()
            transform = {
                "tool": "ffmpeg",
                "version": tool_version,
                "params": {"stream_index": stream_index, "codec": "pcm_s16le"},
                "run_id": run_id,
            }
            output_refs = [{"entity_type": "Asset", "entity_id": derived_asset_id, "revision": 1}]

            with db.transaction() as conn:
                # Derived Asset
                conn.execute("""
                INSERT INTO assets (
                    asset_id, project_id, media_id, kind, origin,
                    source_uri, rights_ref, checksum_sha256, size_bytes,
                    mime_type, supplied_version, parent_asset_ids,
                    transform, availability, inspection, privacy, revision,
                    created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    derived_asset_id, project_id, None, "audio", "extracted",
                    rel_uri, video_row["rights_ref"], checksum_sha256, size_bytes,
                    "audio/wav", None, json.dumps([video_asset_id]),
                    json.dumps(transform), "readable", json.dumps(wav_inspection),
                    json.dumps({"classification": "internal", "external_processing_allowed": False}),
                    1, finish_now, actor.actor_id,
                ))

                # Update Run to SUCCEEDED
                conn.execute("""
                UPDATE runs
                SET run_status = 'SUCCEEDED', ended_at = ?, output_refs = ?,
                    attempts = ?, steps = ?
                WHERE run_id = ?;
                """, (
                    finish_now, json.dumps(output_refs),
                    json.dumps([{"attempt_no": 1, "status": "SUCCEEDED", "started_at": run_start_now, "ended_at": finish_now}]),
                    json.dumps([{"step_id": "extract_audio", "name": "FFmpeg抽轨", "actor_type": "code", "status": "completed"}]),
                    run_id,
                ))

            return {
                "run_id": run_id,
                "run_status": "SUCCEEDED",
                "derived_asset_id": derived_asset_id,
                "source_uri": rel_uri,
                "checksum_sha256": checksum_sha256,
                "size_bytes": size_bytes,
                "inspection": wav_inspection,
                "idempotent": False,
            }


ingest_worker = IngestWorker()

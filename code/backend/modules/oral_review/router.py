"""Oral Review routes: trusted actor + path-bound task are required (fail-closed).

设计依据与门禁约束（docs/07-delivery-plans/antigravity-source-engineering-handoff.md §P0/P1/P2）：
- 未注入认证适配器 → 503；主体缺 ``actor_id`` 或 ``allowed=False`` → 403；
- 路径任务与请求体 ``task_ref`` 强制绑定，禁止跨任务审校；
- 纯白盒规则与有限词表辅助：不调用大语言模型（``model_used=false``、``token_used=0``）；
- 不承诺全场景口语自然度与深层反讽/语义零风险保护，manifest 明确标注覆盖局限；
- 持久化支持：提供 SqliteOralReviewRepository 落盘运行记录。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .contract import OralReviewRequest, OralReviewResult
from .handler import SplitTimeInvarianceError, review_oral_request


class SqliteOralReviewRepository:
    """SQLite 真实持久化仓储（P1: 记录口语审校度量与候选历史）。"""

    def __init__(self, database) -> None:
        self.db = database

    def save_result(self, result: OralReviewResult, actor_id: str, actor_role: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_id = result.run_id or f"oral_run_{uuid.uuid4().hex[:12]}"
        task_id = result.task_ref or "TASK-DEFAULT"
        items_json = json.dumps([item.model_dump(mode="json") for item in result.items])
        manifest_json = json.dumps(result.manifest)
        with self.db.transaction() as conn:
            conn.execute("""
            INSERT INTO oral_review_runs (
                run_id, task_id, request_id, overall_status,
                items_json, manifest_json, actor_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                items_json=excluded.items_json,
                manifest_json=excluded.manifest_json,
                overall_status=excluded.overall_status
            """, (
                run_id, task_id, result.request_id, result.overall_status.value,
                items_json, manifest_json, actor_id, now,
            ))


def create_oral_review_router(
    get_actor_context: Optional[Callable] = None,
    repository=None,
    task_adapter=None,
):
    """构造口语适配与节奏审校路由（默认 fail-closed）。"""
    router = APIRouter(prefix="/api/v1/oral", tags=["Oral Review"])

    def current_actor(request: Request):
        if get_actor_context is None:
            raise HTTPException(503, "Oral review authentication adapter is not configured")
        actor = get_actor_context(request)

        def value(key, default=None):
            return actor.get(key, default) if isinstance(actor, dict) else getattr(actor, key, default)

        if not value("actor_id") or not value("allowed", False):
            raise HTTPException(403, "Oral review operation is not authorized")
        return actor

    def actor_value(actor, key):
        return actor.get(key) if isinstance(actor, dict) else getattr(actor, key, None)

    def persist(result: OralReviewResult, actor) -> None:
        if repository is None:
            return
        saver = getattr(repository, "save_result", None)
        if saver is None:
            raise HTTPException(503, "Oral review repository adapter is not configured")
        saver(
            result,
            actor_id=actor_value(actor, "actor_id"),
            actor_role=actor_value(actor, "actor_role"),
        )

    @router.post("/tasks/{task_id}/review", response_model=OralReviewResult)
    def review(task_id: str, req: OralReviewRequest, actor=Depends(current_actor)):
        if task_adapter and hasattr(task_adapter, "authorize_task"):
            task_adapter.authorize_task(task_id, actor)

        # 路径任务与请求任务严格绑定
        if req.task_ref is not None and req.task_ref != task_id:
            raise HTTPException(403, "路径任务与请求任务不一致，禁止跨任务审校")

        effective_req = req.model_copy(update={"task_ref": task_id})
        try:
            result = review_oral_request(effective_req)
        except SplitTimeInvarianceError as exc:
            raise HTTPException(422, f"ORAL_SPLIT_TIME_INVARIANCE_BROKEN: {exc}")
        except ValueError as exc:
            raise HTTPException(400, f"ORAL_REVIEW_INVALID_REQUEST: {exc}")

        result_with_task = result.model_copy(
            update={"task_ref": task_id, "run_id": f"oral_run_{uuid.uuid4().hex[:12]}"}
        )
        persist(result_with_task, actor)
        return result_with_task

    return router


# Default mounting is fail-closed: no actor adapter means 503, never anonymous output.
router = create_oral_review_router()

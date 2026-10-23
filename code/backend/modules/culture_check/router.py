"""Culture routes: trusted actor and source/translation adapters are required."""
from typing import Any, Callable, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from .contract import CultureCheckRequest, HumanIssueDecisionRequest, RollbackRequest
from .handler import execute_culture_check
from .registry import default_registry


def create_culture_router(repository=None, get_actor_context: Optional[Callable]=None,
                          task_adapter=None, translation_adapter=None):
    router = APIRouter(prefix="/api/v1/culture", tags=["Culture Check"])

    def current_actor(request: Request):
        if get_actor_context is None:
            raise HTTPException(503, "Culture authentication adapter is not configured")
        actor = get_actor_context(request)
        def value(key, default=None):
            return actor.get(key, default) if isinstance(actor, dict) else getattr(actor, key, default)
        if not value("actor_id") or not value("allowed", False):
            raise HTTPException(403, "Culture operation is not authorized")
        return actor

    def actor_value(actor, key):
        return actor.get(key) if isinstance(actor, dict) else getattr(actor, key, None)

    def adapters():
        if repository is None or task_adapter is None or translation_adapter is None:
            raise HTTPException(503, "Culture source/translation adapters are not configured")

    def task_access(task_id, actor, write=False):
        adapters()
        # Adapter must check object permissions, not merely task existence.
        return translation_adapter.authorize_task(task_id, actor, write=write)

    @router.get("/sources")
    def sources(actor=Depends(current_actor)):
        return default_registry.get_sources()

    @router.get("/rules")
    def rules(actor=Depends(current_actor)):
        return default_registry.retrieve_applicable_rules()

    @router.get("/cases")
    def cases(actor=Depends(current_actor)):
        return default_registry.retrieve_applicable_cases()

    @router.post("/tasks/{task_id}/check")
    def check(task_id: str, actor=Depends(current_actor)):
        task_access(task_id, actor, True)
        req = translation_adapter.build_check_request(task_id, actor)
        req = CultureCheckRequest.model_validate(req)
        if req.task_ref != task_id or req.simulate:
            raise HTTPException(403, "Formal culture checks cannot use simulated or foreign input")
        try:
            result = execute_culture_check(req)
            # Revalidate pinned source/translation revisions after a potentially slow API call.
            translation_adapter.assert_current(task_id, req)
            repository.save_check_result(result, actor_id=actor_value(actor,"actor_id"), actor_role=actor_value(actor,"actor_role"))
            return result
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except HTTPException:
            raise
        except Exception as exc:
            from code.backend.modules.asr_alignment.handler import sanitize_error_message
            safe_error = RuntimeError(sanitize_error_message(exc))
            failed_run = repository.save_failure(req, safe_error, actor_value(actor,"actor_id"),actor_value(actor,"actor_role"))
            raise HTTPException(502, {"message":"文化检测失败，未生成候选", "run_id":failed_run,"reason":str(safe_error)})

    @router.get("/runs/{run_id}")
    def run(run_id: str, actor=Depends(current_actor)):
        adapters()
        result = repository.get_run(run_id)
        if result is None:
            raise HTTPException(404, "Run not found")
        task_access(result["task_id"], actor)
        return result

    @router.get("/tasks/{task_id}/issues")
    def issues(task_id: str, actor=Depends(current_actor)):
        task_access(task_id, actor)
        result = repository.list_issues(task_id)
        for issue in result:
            try:
                with repository.db.transaction() as conn:
                    row = conn.execute("SELECT manifest FROM culture_runs WHERE run_id=?", (issue["run_id"],)).fetchone()
                import json
                pinned = json.loads(row["manifest"]).get("translation_refs", {}).get(issue["unit_id"], {}) if row else {}
                translation_adapter.assert_issue_current(issue, pinned.get("revision"))
                issue["stale"] = False
            except HTTPException as exc:
                if exc.status_code not in (400,409):
                    raise
                issue["stale"] = True
                issue["status"] = "PENDING_RECHECK"
            issue["ai_origin"] = True
        return result

    @router.post("/issues/{issue_id}/decision")
    def decide(issue_id: str, req: HumanIssueDecisionRequest, actor=Depends(current_actor)):
        adapters()
        if actor_value(actor, "actor_type") != "human":
            raise HTTPException(403, "A human reviewer is required")
        with repository.db.transaction() as conn:
            row = conn.execute("SELECT * FROM culture_issues WHERE issue_id=?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Issue not found")
        issue = dict(row)
        task_access(issue["task_id"], actor, True)
        # Human decision must compare against current translation, not only the old issue row.
        translation_adapter.assert_issue_current(issue, req.expected_revision)
        if issue["status"] != "AI_PROPOSED":
            raise HTTPException(409, "Issue has already been reviewed or requires recheck")
        if issue["severity_proposal"] in ("P0", "P1") and req.decision_action in ("reject", "ignore_with_reason"):
            if not translation_adapter.can_resolve_high_risk(actor):
                raise HTTPException(403, "High risk decisions require a qualified reviewer")
        if req.decision_action == "edit_accept":
            # No cross-database partial update: delegate edit+decision+invalidation atomically.
            return translation_adapter.edit_and_decide(issue, req, actor, repository)
        return repository.apply_human_decision(issue_id, req, actor_value(actor,"actor_id"), actor_value(actor,"actor_role"))

    @router.post("/tasks/{task_id}/units/{unit_id}/rollback")
    def rollback(task_id: str, unit_id: str, req: RollbackRequest, actor=Depends(current_actor)):
        task_access(task_id, actor, True)
        if actor_value(actor,"actor_type") != "human":
            raise HTTPException(403, "A human reviewer is required")
        # Single transaction in the adapter protects both translation history and risk invalidation.
        return translation_adapter.rollback_and_invalidate(task_id, unit_id, req, actor, repository)

    @router.get("/tasks/{task_id}/metrics")
    def metrics(task_id: str, actor=Depends(current_actor)):
        task_access(task_id, actor)
        return repository.get_events(task_id)

    return router


# Default mounting is fail-closed. Never exposes arbitrary-input or simulation endpoints.
router = create_culture_router()

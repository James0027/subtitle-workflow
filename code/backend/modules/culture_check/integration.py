"""Adapter over the existing source/translation tables; no parallel manuscript store."""
import hashlib
import json
from fastapi import HTTPException
from .contract import CultureCheckRequest, CultureUnitInput


class WorkflowCultureAdapter:
    def __init__(self, database):
        self.db = database

    def authorize_task(self, task_id, actor, write=False):
        if not actor.allowed:
            raise HTTPException(403, "操作主体未获授权")
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "任务不存在")
        # Current single-user local pilot has no per-project ACL; never imply tenant isolation.
        return dict(row)

    def build_check_request(self, task_id, actor=None):
        with self.db.transaction() as conn:
            source = conn.execute("SELECT * FROM source_transcripts WHERE task_id=? ORDER BY revision DESC LIMIT 1", (task_id,)).fetchone()
            if not source or source["status"] != "CONFIRMED":
                raise HTTPException(409, "请先人工确认当前源稿")
            rows = conn.execute("""SELECT t.*,u.text AS source_text,u.speaker_id,u.start_ms,u.end_ms,u.unit_index
                FROM translations t JOIN source_utterances u ON u.task_id=t.task_id AND u.unit_id=t.unit_id AND u.transcript_revision=t.source_revision
                WHERE t.task_id=? AND t.source_revision=?
                AND t.translation_revision=(SELECT MAX(t2.translation_revision) FROM translations t2 WHERE t2.task_id=t.task_id AND t2.unit_id=t.unit_id AND t2.source_revision=t.source_revision)
                ORDER BY u.unit_index""", (task_id, source["revision"])).fetchall()
            expected = conn.execute("SELECT COUNT(*) FROM source_utterances WHERE task_id=? AND transcript_revision=?", (task_id, source["revision"])).fetchone()[0]
        if not rows or len(rows) != expected or len({r["unit_id"] for r in rows}) != expected:
            raise HTTPException(409, "当前源稿的译文尚未完整生成")
        if any(r["status"] not in ("CONFIRMED", "MANUAL_LOCKED") or not r["confirmed_by"] for r in rows):
            raise HTTPException(409, "请先人工确认全部当前译文")
        if any(r["target_market"] != "MX" or r["target_language"] not in ("es-MX", "es") for r in rows):
            raise HTTPException(409, "文化试点只支持墨西哥西语，请使用对应市场译稿")
        units = []
        for i, r in enumerate(rows):
            units.append(CultureUnitInput(unit_id=r["unit_id"], translation_id=r["translation_id"], translation_revision=r["translation_revision"],
                source_text=r["source_text"], target_text=r["text"], speaker_id=r["speaker_id"], start_ms=r["start_ms"], end_ms=r["end_ms"],
                prev_units=[{"unit_id":q["unit_id"],"source_text":q["source_text"],"target_text":q["text"]} for q in rows[max(0,i-2):i]],
                next_units=[{"unit_id":q["unit_id"],"source_text":q["source_text"],"target_text":q["text"]} for q in rows[i+1:i+3]]))
        return CultureCheckRequest(task_ref=task_id,task_revision=source["revision"],source_language=source["source_language"],units=units,
            simulate=False,missing_channel_or_audience=True)

    def assert_current(self, task_id, request):
        current = self.build_check_request(task_id)
        if current.model_dump() != request.model_dump():
            raise HTTPException(409, "源译稿已变化，请重新检测")

    def assert_issue_current(self, issue, expected_revision):
        current = self.build_check_request(issue["task_id"])
        unit = next((u for u in current.units if u.unit_id == issue["unit_id"]), None)
        with self.db.transaction() as conn:
            run = conn.execute("SELECT manifest FROM culture_runs WHERE run_id=?", (issue["run_id"],)).fetchone()
        refs = json.loads(run["manifest"]).get("translation_refs", {}) if run else {}
        pinned = refs.get(issue["unit_id"], {})
        if not unit or current.task_revision != issue["task_revision"] or unit.translation_revision != expected_revision or pinned != {"translation_id":unit.translation_id,"revision":unit.translation_revision}:
            raise HTTPException(409, "风险依据已过期，请重新检测")

    def can_resolve_high_risk(self, actor):
        return actor.actor_type == "human" and actor.actor_role in ("culture_senior", "legal_reviewer")

    def edit_and_decide(self, issue, req, actor, repository):
        # Existing source/translation review owns manuscript edits and locks. Culture only proposes.
        raise HTTPException(409, "请到初翻审阅修改译文、重新确认后复检；文化候选不会覆盖人工稿")

    def rollback_and_invalidate(self, task_id, unit_id, req, actor, repository):
        raise HTTPException(409, "请在初翻审阅回滚并重新确认，旧文化检测不能自动沿用")

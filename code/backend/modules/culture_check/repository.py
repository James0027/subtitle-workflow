import json
import uuid
from typing import Any, Dict, List, Optional
from code.backend.db import Database, utc_now_iso
from code.backend.modules.culture_check.contract import (
    CultureCheckResult,
    HumanIssueDecisionRequest,
    RollbackRequest,
)


class CultureRepository:
    """
    文化检测独立持久化仓库：
    - 显式通过构造器注入 Database 实例，严禁在模块层 import 默认数据库。
    - 不建平行译文真相，译文真理始终归属于协调者的翻译服务与数据实体。
    - 指标复用系统既有 events 表（run.finished / review.decided / review.reverted），不新造独立事件表。
    """

    def __init__(self, database: Database):
        self.db = database
        self.init_tables()

    def init_tables(self) -> None:
        """初始化文化模块专属数据表 (不建立平行译文表，复用主 events 表)"""
        with self.db.transaction() as conn:
            # 1. 文化审查 Run 记录与 Manifest
            conn.execute("""
            CREATE TABLE IF NOT EXISTS culture_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_revision INTEGER NOT NULL,
                target_market TEXT NOT NULL DEFAULT 'MX',
                manifest TEXT NOT NULL,
                coverage_limitations TEXT NOT NULL,
                checked_unit_ids TEXT NOT NULL,
                unchecked_units TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'COMPLETED',
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_culture_runs_task ON culture_runs(task_id);")

            # 2. 文化审查 Issues 记录
            conn.execute("""
            CREATE TABLE IF NOT EXISTS culture_issues (
                issue_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_revision INTEGER NOT NULL,
                unit_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity_proposal TEXT NOT NULL,
                impact_level INTEGER,
                occurrence_likelihood INTEGER,
                remediation_difficulty INTEGER,
                ranking_score INTEGER,
                factor_reasons TEXT,
                confidence TEXT NOT NULL,
                trigger_spans TEXT NOT NULL,
                rule_refs TEXT NOT NULL,
                case_refs TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                evidence_status TEXT NOT NULL,
                speaker_ref TEXT,
                narrative_stance TEXT,
                explanation TEXT NOT NULL,
                suggested_action TEXT NOT NULL,
                suggested_translation TEXT,
                missing_context TEXT,
                downgraded_from_p0 INTEGER NOT NULL DEFAULT 0,
                downgrade_reason TEXT,
                status TEXT NOT NULL DEFAULT 'AI_PROPOSED',
                decision_action TEXT,
                decision_by TEXT,
                decision_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES culture_runs(run_id)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_culture_issues_task ON culture_issues(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_culture_issues_unit ON culture_issues(unit_id);")

            # 3. 人工裁决记录
            conn.execute("""
            CREATE TABLE IF NOT EXISTS culture_decisions (
                decision_id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                expected_revision INTEGER NOT NULL,
                decision_action TEXT NOT NULL,
                edited_translation TEXT,
                ignore_reason TEXT,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (issue_id) REFERENCES culture_issues(issue_id)
            );
            """)

    def save_check_result(
        self,
        result: CultureCheckResult,
        actor_id: str = "service_worker",
        actor_role: str = "service_worker",
    ) -> None:
        """保存文化检测 Run 及全部 Issue 记录，向系统既有 events 表投递 run.finished 事件"""
        now = utc_now_iso()
        with self.db.transaction() as conn:
            # 写入 Run
            conn.execute("""
            INSERT INTO culture_runs (
                run_id, task_id, task_revision, target_market, manifest,
                coverage_limitations, checked_unit_ids, unchecked_units, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                result.run_id,
                result.task_ref,
                result.task_revision,
                result.target_market,
                json.dumps(result.manifest, ensure_ascii=False),
                json.dumps(result.coverage_limitations, ensure_ascii=False),
                json.dumps(result.checked_unit_ids, ensure_ascii=False),
                json.dumps([u.model_dump() for u in result.unchecked_units], ensure_ascii=False),
                "COMPLETED",
                now,
            ))

            # 批量写入 Issues
            for iss in result.issues:
                conn.execute("""
                INSERT INTO culture_issues (
                    issue_id, run_id, task_id, task_revision, unit_id, category,
                    severity_proposal, impact_level, occurrence_likelihood,
                    remediation_difficulty, ranking_score, factor_reasons, confidence,
                    trigger_spans, rule_refs, case_refs, evidence_refs, evidence_status,
                    speaker_ref, narrative_stance, explanation, suggested_action,
                    suggested_translation, missing_context, downgraded_from_p0,
                    downgrade_reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    iss.issue_id,
                    result.run_id,
                    result.task_ref,
                    result.task_revision,
                    iss.unit_id,
                    iss.category,
                    iss.severity_proposal,
                    iss.impact_level,
                    iss.occurrence_likelihood,
                    iss.remediation_difficulty,
                    iss.ranking_score,
                    json.dumps(iss.factor_reasons.model_dump() if iss.factor_reasons else {}, ensure_ascii=False),
                    json.dumps(iss.confidence.model_dump(), ensure_ascii=False),
                    json.dumps([s.model_dump() for s in iss.trigger_spans], ensure_ascii=False),
                    json.dumps(iss.rule_refs, ensure_ascii=False),
                    json.dumps(iss.case_refs, ensure_ascii=False),
                    json.dumps(iss.evidence_refs, ensure_ascii=False),
                    iss.evidence_status,
                    iss.speaker_ref,
                    iss.narrative_stance,
                    iss.explanation,
                    iss.suggested_action,
                    iss.suggested_translation,
                    json.dumps(iss.missing_context, ensure_ascii=False),
                    1 if iss.downgraded_from_p0 else 0,
                    iss.downgrade_reason,
                    iss.status,
                    now,
                ))

            # 复用系统既有 events 表，发射 run.finished 事件
            self._emit_event(
                conn=conn,
                event_type="run.finished",
                task_id=result.task_ref,
                run_id=result.run_id,
                actor_id=actor_id,
                actor_role=actor_role,
                payload={
                    "module": "culture_check",
                    "success": True,
                    "target_market": result.target_market,
                    "total_issues": len(result.issues),
                    "checked_units_count": len(result.checked_unit_ids),
                    "unchecked_units_count": len(result.unchecked_units),
                    "p0_count": sum(1 for i in result.issues if i.severity_proposal == "P0"),
                    "p1_count": sum(1 for i in result.issues if i.severity_proposal == "P1"),
                    "downgraded_p0_count": sum(1 for i in result.issues if i.downgraded_from_p0),
                },
                now=now,
            )

    def save_failure(self, request, error, actor_id, actor_role):
        """Persist a failed attempt without creating issues or fabricated usage."""
        run_id = "crun_" + uuid.uuid4().hex[:20]
        now = utc_now_iso()
        manifest = {"task_ref":request.task_ref,"task_revision":request.task_revision,
            "translation_refs":{u.unit_id:{"translation_id":u.translation_id,"revision":u.translation_revision} for u in request.units},
            "error_type":type(error).__name__,"error":str(error),"usage":None,"cost":None,"created_at":now}
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO culture_runs(run_id,task_id,task_revision,target_market,manifest,coverage_limitations,checked_unit_ids,unchecked_units,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id,request.task_ref,request.task_revision,request.target_market,json.dumps(manifest,ensure_ascii=False),json.dumps(["检测失败，未生成风险候选"],ensure_ascii=False),"[]",json.dumps([{"unit_id":u.unit_id,"reason":"run_failed"} for u in request.units]),"FAILED",now))
            self._emit_event(conn=conn,event_type="run.finished",task_id=request.task_ref,run_id=run_id,actor_id=actor_id,actor_role=actor_role,payload={"module":"culture_check","success":False,"error_type":type(error).__name__},now=now)
        return run_id

    def apply_human_decision(
        self,
        issue_id: str,
        req: HumanIssueDecisionRequest,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """
        人工决定与 expected_revision 保护：
        1. 检查 expected_revision 乐观锁。
        2. actor_id 与 actor_role 必须由可信调用方注入，严禁从请求体自报或默认。
        3. 发射 review.decided 既有事件。
        """
        now = utc_now_iso()
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"

        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM culture_issues WHERE issue_id = ?", (issue_id,))
            issue_row = cur.fetchone()
            if not issue_row:
                raise ValueError(f"文化检测问题项不存在: {issue_id}")

            run = conn.execute("SELECT manifest FROM culture_runs WHERE run_id=?", (issue_row["run_id"],)).fetchone()
            refs = json.loads(run["manifest"]).get("translation_refs", {}) if run else {}
            current_rev = refs.get(issue_row["unit_id"], {}).get("revision")
            if current_rev is None:
                raise ValueError("Missing pinned translation revision")
            pinned = refs[issue_row["unit_id"]]
            translation = conn.execute("SELECT * FROM translations WHERE translation_id=? AND task_id=? AND unit_id=?", (pinned["translation_id"],issue_row["task_id"],issue_row["unit_id"])).fetchone()
            source = conn.execute("SELECT revision,status FROM source_transcripts WHERE task_id=? ORDER BY revision DESC LIMIT 1", (issue_row["task_id"],)).fetchone()
            if not translation or not source or source["status"] != "CONFIRMED" or source["revision"] != issue_row["task_revision"] or translation["source_revision"] != source["revision"] or translation["translation_revision"] != current_rev or translation["status"] not in ("CONFIRMED","MANUAL_LOCKED"):
                raise ValueError("Current source/translation changed; recheck required")
            newer = conn.execute("SELECT 1 FROM translations WHERE task_id=? AND unit_id=? AND source_revision=? AND translation_revision>?", (issue_row["task_id"],issue_row["unit_id"],source["revision"],current_rev)).fetchone()
            if newer or issue_row["status"] != "AI_PROPOSED":
                raise ValueError("Reviewed or superseded culture issue cannot be decided again")
            if req.expected_revision != current_rev:
                raise ValueError(
                    f"乐观锁保护生效：expected_revision ({req.expected_revision}) 与当前修订版本 ({current_rev}) 不一致，禁止覆盖！"
                )

            # 映射状态与人机血缘标签
            if req.decision_action == "accept":
                new_status = "CONFIRMED"
                label = "AI生成·人工已确认"
            elif req.decision_action == "edit_accept":
                new_status = "EDITED"
                label = "人工修改·基于AI候选"
                if not req.edited_translation:
                    raise ValueError("edit_accept 必须提供人工修改后的译文 edited_translation")
            elif req.decision_action == "reject":
                new_status = "REJECTED"
                label = "人工驳回"
            elif req.decision_action == "ignore_with_reason":
                new_status = "IGNORED"
                label = "人工有因忽略"
                if not req.ignore_reason:
                    raise ValueError("ignore_with_reason 必须提供忽略原因 ignore_reason")
            else:
                raise ValueError(f"未知的裁决动作: {req.decision_action}")

            # 更新 Issue 状态
            conn.execute("""
            UPDATE culture_issues
            SET status = ?, decision_action = ?, decision_by = ?, decision_at = ?
            WHERE issue_id = ?;
            """, (new_status, req.decision_action, actor_id, now, issue_id))

            # 写入审查裁决记录
            conn.execute("""
            INSERT INTO culture_decisions (
                decision_id, issue_id, task_id, unit_id, expected_revision,
                decision_action, edited_translation, ignore_reason,
                actor_id, actor_role, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                decision_id,
                issue_id,
                issue_row["task_id"],
                issue_row["unit_id"],
                req.expected_revision,
                req.decision_action,
                req.edited_translation,
                req.ignore_reason,
                actor_id,
                actor_role,
                now,
            ))

            # 复用系统既有 events 表，发射 review.decided 事件
            self._emit_event(
                conn=conn,
                event_type="review.decided",
                task_id=issue_row["task_id"],
                run_id=issue_row["run_id"],
                actor_id=actor_id,
                actor_role=actor_role,
                payload={
                    "decision_id": decision_id,
                    "action": req.decision_action,
                    "issue_id": issue_id,
                    "unit_id": issue_row["unit_id"],
                    "display_label": label,
                    "severity": issue_row["severity_proposal"],
                },
                now=now,
            )

            cur.execute("SELECT * FROM culture_issues WHERE issue_id = ?", (issue_id,))
            updated = dict(cur.fetchone())
            updated["display_label"] = label
            return updated

    def rollback_unit_checks(
        self,
        task_id: str,
        unit_id: str,
        req: RollbackRequest,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """
        回滚护栏处理：
        1. 校验 expected_revision 乐观锁。
        2. 将依赖旧修订版本的文化检测项全部重置为 PENDING_RECHECK（新修订失效待复检）。
        3. 复用系统既有 events 表，发射 review.reverted 事件。
        （注：本模块不维护平行译文真相，正文版本的升版由协调者注入的 translation_adapter 统一承载）
        """
        now = utc_now_iso()
        with self.db.transaction() as conn:
            cur = conn.cursor()
            # 校验是否存在该修订的文化项
            cur.execute("""
            SELECT COUNT(*) AS c FROM culture_issues
            WHERE task_id = ? AND unit_id = ? AND task_revision = ?;
            """, (task_id, unit_id, req.expected_revision))
            cnt = cur.fetchone()["c"]
            if cnt == 0:
                # 检查是否存在任意修订
                cur.execute("SELECT MAX(task_revision) as max_rev FROM culture_issues WHERE task_id = ? AND unit_id = ?", (task_id, unit_id))
                row = cur.fetchone()
                if row and row["max_rev"] is not None and row["max_rev"] != req.expected_revision:
                    raise ValueError(
                        f"乐观锁保护生效：expected_revision ({req.expected_revision}) 与当前修订版本 ({row['max_rev']}) 不一致，禁止回滚！"
                    )

            # 核心护栏：旧修订相关检测失效，置为 PENDING_RECHECK
            conn.execute("""
            UPDATE culture_issues
            SET status = 'PENDING_RECHECK'
            WHERE task_id = ? AND unit_id = ? AND task_revision = ?;
            """, (task_id, unit_id, req.expected_revision))

            # 复用系统既有 events 表，发射 review.reverted 事件
            self._emit_event(
                conn=conn,
                event_type="review.reverted",
                task_id=task_id,
                run_id=None,
                actor_id=actor_id,
                actor_role=actor_role,
                payload={
                    "task_id": task_id,
                    "unit_id": unit_id,
                    "expected_revision": req.expected_revision,
                    "target_revision": req.target_revision,
                    "reason": req.reason,
                    "action": "marked_PENDING_RECHECK",
                },
                now=now,
            )

            return {
                "task_id": task_id,
                "unit_id": unit_id,
                "target_revision": req.target_revision,
                "status": "CHECKS_INVALIDATED_PENDING_RECHECK",
                "reason": req.reason,
                "actor_id": actor_id,
                "created_at": now,
            }

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM culture_runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["manifest"] = json.loads(d["manifest"])
            d["coverage_limitations"] = json.loads(d["coverage_limitations"])
            d["checked_unit_ids"] = json.loads(d["checked_unit_ids"])
            d["unchecked_units"] = json.loads(d["unchecked_units"])
            return d

    def list_issues(
        self,
        task_id: str,
        run_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            q = "SELECT * FROM culture_issues WHERE task_id = ?"
            params: List[Any] = [task_id]

            if run_id:
                q += " AND run_id = ?"
                params.append(run_id)
            if unit_id:
                q += " AND unit_id = ?"
                params.append(unit_id)
            if status:
                q += " AND status = ?"
                params.append(status)

            q += " ORDER BY ranking_score DESC NULLS LAST, created_at DESC"
            cur.execute(q, tuple(params))
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["trigger_spans"] = json.loads(d["trigger_spans"])
                d["confidence"] = json.loads(d["confidence"])
                d["rule_refs"] = json.loads(d["rule_refs"])
                d["case_refs"] = json.loads(d["case_refs"])
                d["evidence_refs"] = json.loads(d["evidence_refs"])
                d["factor_reasons"] = json.loads(d["factor_reasons"]) if d["factor_reasons"] else {}
                d["missing_context"] = json.loads(d["missing_context"]) if d["missing_context"] else []
                d["downgraded_from_p0"] = bool(d["downgraded_from_p0"])
                rows.append(d)
            return rows

    def get_events(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """从系统既有 events 表查询文化模块发射的事件"""
        with self.db.transaction() as conn:
            cur = conn.cursor()
            if task_id:
                cur.execute(
                    "SELECT * FROM events WHERE task_id = ? AND event_type IN ('run.finished', 'review.decided', 'review.reverted') ORDER BY created_at ASC",
                    (task_id,)
                )
            else:
                cur.execute(
                    "SELECT * FROM events WHERE event_type IN ('run.finished', 'review.decided', 'review.reverted') ORDER BY created_at ASC"
                )
            res = []
            for r in cur.fetchall():
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                res.append(d)
            return res

    def _emit_event(
        self,
        conn: Any,
        event_type: str,
        task_id: str,
        payload: Dict[str, Any],
        now: str,
        run_id: Optional[str] = None,
        actor_id: str = "service_worker",
        actor_role: str = "service_worker",
    ) -> None:
        """复用系统全局 events 表，统一写入标准业务事件"""
        event_id = f"ev_{uuid.uuid4().hex[:12]}"
        operation_id = f"op_{uuid.uuid4().hex[:12]}"
        dedup_key = f"dedup_{event_type}_{task_id}_{uuid.uuid4().hex[:8]}"

        conn.execute("""
        INSERT INTO events (
            event_id, event_type, event_at, received_at, task_id,
            media_id, run_id, actor_id, actor_type, actor_role,
            operation_id, dedup_key, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id,
            event_type,
            now,
            now,
            task_id,
            None,
            run_id,
            actor_id,
            "human" if "operator" in actor_role or "auditor" in actor_role or "reviewer" in actor_role else "service_actor",
            actor_role,
            operation_id,
            dedup_key,
            json.dumps(payload, ensure_ascii=False),
            now,
        ))

"""Compliance routes: 平台质检 → 多格式导出 → 真人五维签发 → 产物受控获取。

设计依据与门禁约束（docs/07-delivery-plans/antigravity-source-engineering-handoff.md §P0/P1）：
1. 真实来源：validate-and-export 服务端按 task_id 读取真实存在且人工确认的源译稿，拒绝客户端任意 cues/revision 替代事实；
2. 文化门禁：校验未决文化 P0/P1 风险，未决或缺证据 fail-closed；
3. 身份与角色：签发要求真实在籍审核员（reviewer/auditor/admin），明确拒绝 viewer 与 media_operator；签发人须为当前会话本人；
4. 不可变产物：signoff 仅依据服务端已登记的不可变产物，拒绝客户端完整替换或伪造 validation；
5. 五维要素一致性：signoff 必须与产物 manifest 声明的 revision、rule 及服务端当前确认状态精确一致；任何变更拒绝旧签发；
6. 持久化存储：默认提供 SqliteArtifactStore 确保服务重启后产物与签发可回取、不丢失。
"""

import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .contract import (
    AUTHORIZED_SIGNOFF_ROLES,
    COMPLIANCE_POLICY_VERSION,
    ArtifactPackage,
    ComplianceStatus,
    PlatformProfile,
    RoundTripResult,
    SignoffData,
    SubtitleCue,
    ValidationResult,
)
from .handler import (
    ComplianceError,
    SignoffError,
    validate_and_export_artifact,
    verify_and_apply_signoff,
    build_signoff,
    sha256_text,
)
from .integration import WorkflowComplianceAdapter

# 可对外提供产物的状态：质检通过的内部预览态 + 真人签发的发布就绪态。
_DELIVERABLE_STATUSES = (ComplianceStatus.VALIDATED, ComplianceStatus.PUBLISH_READY)

# 签发失败码 → HTTP 状态：机器代签/身份问题 403，其余为状态或哈希冲突 409。
_SIGNOFF_FORBIDDEN_CODES = (
    "SIGNOFF_MACHINE_FORBIDDEN",
    "SIGNOFF_NO_SIGNER",
    "SIGNOFF_UNAUTHORIZED_ROLE",
)


class InMemoryArtifactStore:
    """进程内产物暂存（受控预览，供轻量隔离测试）。"""

    def __init__(self) -> None:
        self._items: Dict[Tuple[str, str], ArtifactPackage] = {}
        self._latest: Dict[str, str] = {}

    def save(self, task_id: str, artifact: ArtifactPackage) -> ArtifactPackage:
        self._items[(task_id, artifact.artifact_id)] = artifact
        self._latest[task_id] = artifact.artifact_id
        return artifact

    def get(self, task_id: str, artifact_id: Optional[str] = None) -> Optional[ArtifactPackage]:
        resolved = artifact_id or self._latest.get(task_id)
        if not resolved:
            return None
        return self._items.get((task_id, resolved))


class SqliteArtifactStore:
    """SQLite 真实持久化产物存储（P1: 服务重启可回取，原件不可变）。"""

    def __init__(self, database) -> None:
        self.db = database

    def save(self, task_id: str, artifact: ArtifactPackage, current_guard=None) -> ArtifactPackage:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        val_res = artifact.validation_result.model_dump_json() if artifact.validation_result else None
        rt_res = artifact.round_trip_result.model_dump_json() if artifact.round_trip_result else None
        sign_res = artifact.signoff.model_dump_json() if artifact.signoff else None
        man_res = json.dumps(artifact.manifest or {})
        trans_rev = str((artifact.manifest or {}).get("translation_revision", ""))
        rule_ver = str((artifact.manifest or {}).get("rule_version", ""))
        with self.db.transaction() as conn:
            if current_guard is not None:
                current_guard(conn)
            existing = conn.execute("SELECT content,artifact_sha256,validation_id,manifest_json FROM compliance_artifacts WHERE task_id=? AND artifact_id=?",(task_id,artifact.artifact_id)).fetchone()
            if existing and (existing['content'] != artifact.content or existing['artifact_sha256'] != artifact.artifact_sha256 or existing['validation_id'] != artifact.validation_id or json.loads(existing['manifest_json']).get('gate_snapshot') != artifact.manifest.get('gate_snapshot')):
                raise HTTPException(409,"已登记产物不可变，必须生成新产物")
            conn.execute("""
            INSERT INTO compliance_artifacts (
                task_id, artifact_id, format, content, artifact_sha256, status,
                validation_id, validation_result_json, round_trip_result_json,
                signoff_json, manifest_json, translation_revision, rule_version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, artifact_id) DO UPDATE SET
                content=excluded.content,
                artifact_sha256=excluded.artifact_sha256,
                status=excluded.status,
                validation_id=excluded.validation_id,
                validation_result_json=excluded.validation_result_json,
                round_trip_result_json=excluded.round_trip_result_json,
                signoff_json=excluded.signoff_json,
                manifest_json=excluded.manifest_json,
                translation_revision=excluded.translation_revision,
                rule_version=excluded.rule_version,
                updated_at=excluded.updated_at
            """, (
                task_id, artifact.artifact_id, artifact.format, artifact.content,
                artifact.artifact_sha256, artifact.status.value, artifact.validation_id,
                val_res, rt_res, sign_res, man_res, trans_rev, rule_ver, now, now,
            ))
        return artifact

    def get(self, task_id: str, artifact_id: Optional[str] = None) -> Optional[ArtifactPackage]:
        with self.db.transaction() as conn:
            if artifact_id:
                row = conn.execute(
                    "SELECT * FROM compliance_artifacts WHERE task_id=? AND artifact_id=?",
                    (task_id, artifact_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM compliance_artifacts WHERE task_id=? ORDER BY updated_at DESC LIMIT 1",
                    (task_id,),
                ).fetchone()
        if not row:
            return None
        return ArtifactPackage(
            artifact_id=row["artifact_id"],
            format=row["format"],
            content=row["content"],
            artifact_sha256=row["artifact_sha256"],
            status=ComplianceStatus(row["status"]),
            validation_id=row["validation_id"],
            validation_result=ValidationResult.model_validate_json(row["validation_result_json"]) if row["validation_result_json"] else None,
            round_trip_result=RoundTripResult.model_validate_json(row["round_trip_result_json"]) if row["round_trip_result_json"] else None,
            signoff=SignoffData.model_validate_json(row["signoff_json"]) if row["signoff_json"] else None,
            manifest=json.loads(row["manifest_json"]) if row["manifest_json"] else {},
        )


class ValidateExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format: str = "srt"
    expected_task_revision: int

class SignoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    artifact_id: str = Field(...,min_length=1)
    expected_revision: str = Field(...,min_length=1)


def create_compliance_router(get_actor_context=None,storage_adapter=None,task_adapter=None):
    router=APIRouter(prefix="/api/v1/compliance",tags=["Compliance & Delivery"])
    def current_actor(request:Request):
        if get_actor_context is None:raise HTTPException(503,"未配置可信鉴权")
        actor=get_actor_context(request)
        allowed=actor.get('allowed',False) if isinstance(actor,dict) else getattr(actor,'allowed',False)
        role=actor.get('actor_role') if isinstance(actor,dict) else getattr(actor,'actor_role',None)
        if not allowed or role=='human_denied':raise HTTPException(403,"主体未获授权")
        return actor
    def configured():
        if storage_adapter is None or task_adapter is None:raise HTTPException(503,"未配置可信任务与持久产物适配器")
    def access(task_id,actor):
        configured();return task_adapter.authorize_task(task_id,actor)
    def public(artifact):
        body=artifact.model_dump(mode='json');body.pop('content',None);return body
    def check_current(task_id,artifact):
        dialogues,snapshot=task_adapter.snapshot(task_id)
        if artifact.manifest.get('gate_snapshot')!=snapshot or artifact.manifest.get('translation_revision')!=dialogues['translation_revision']:
            raise HTTPException(409,"源译稿、规则、文化依据或校验版本已变化，请重新质检")
        if artifact.manifest.get('rule_version')!=f"compliance-policy:{COMPLIANCE_POLICY_VERSION}":raise HTTPException(409,"规则版本变化")
        return dialogues,snapshot
    def save_current(task_id,artifact):
        def guard(connection):
            adapter=task_adapter.for_connection(connection)
            dialogues,snapshot=adapter.snapshot(task_id)
            if artifact.manifest.get('gate_snapshot')!=snapshot or artifact.manifest.get('translation_revision')!=dialogues['translation_revision']:
                raise HTTPException(409,'保存期间源译或文化依据变化，拒绝旧产物')
        return storage_adapter.save(task_id,artifact,current_guard=guard)
    @router.get('/tasks/{task_id}/state')
    def state(task_id:str,actor=Depends(current_actor)):
        row=access(task_id,actor);result={'task_revision':row['task_revision']}
        try:
            dialogues,snapshot=task_adapter.snapshot(task_id)
            result.update(ready=True,translation_revision=dialogues['translation_revision'])
        except HTTPException as exc:
            if exc.status_code!=409:raise
            result.update(ready=False,blocked_reason=exc.detail)
        artifact=storage_adapter.get(task_id)
        result['artifact']=public(artifact) if artifact else None
        return result
    @router.post('/tasks/{task_id}/validate-and-export')
    def validate_export(task_id:str,req:ValidateExportRequest,actor=Depends(current_actor)):
        row=access(task_id,actor)
        if row['task_revision']!=req.expected_task_revision:raise HTTPException(409,"任务修订已变化")
        dialogues,snapshot=task_adapter.snapshot(task_id)
        try:
            artifact=validate_and_export_artifact(task_id=task_id,translation_revision=dialogues['translation_revision'],rule_version=f"compliance-policy:{COMPLIANCE_POLICY_VERSION}",cues=dialogues['cues'],format=req.format,profile=PlatformProfile())
        except (ComplianceError,ValueError) as exc:raise HTTPException(409,str(exc))
        except Exception:
            run_id=task_adapter.record_failure(task_id,actor,'DETECTOR_FAILURE')
            raise HTTPException(503,{'message':'技术检测器失败，禁止生成交付；可稍后重试','stop_reason':'DETECTOR_FAILURE','run_id':run_id})
        artifact.manifest['gate_snapshot']=snapshot
        check_current(task_id,artifact)
        save_current(task_id,artifact)
        return public(artifact)
    @router.post('/tasks/{task_id}/signoff')
    def signoff(task_id:str,req:SignoffRequest,actor=Depends(current_actor)):
        access(task_id,actor);task_adapter.check_signoff_role(actor)
        artifact=storage_adapter.get(task_id,req.artifact_id)
        if artifact is None:raise HTTPException(404,"产物未登记或不属于本任务")
        if req.expected_revision!=artifact.manifest.get('translation_revision'):raise HTTPException(409,"产物修订不符")
        check_current(task_id,artifact)
        signer=actor.get('actor_id') if isinstance(actor,dict) else actor.actor_id
        try:
            signature=build_signoff(artifact,task_id=task_id,translation_revision=req.expected_revision,rule_version=artifact.manifest['rule_version'],validation_id=artifact.validation_id,signer_id=signer)
            signed=verify_and_apply_signoff(artifact,signature)
        except (SignoffError,ValueError) as exc:raise HTTPException(409,str(exc))
        check_current(task_id,signed)
        signed.manifest['signoff_actor_role']=actor.get('actor_role') if isinstance(actor,dict) else actor.actor_role
        save_current(task_id,signed)
        return public(signed)
    @router.get('/tasks/{task_id}/artifact')
    def get_artifact(task_id:str,artifact_id:Optional[str]=None,actor=Depends(current_actor)):
        access(task_id,actor)
        artifact=storage_adapter.get(task_id,artifact_id)
        if artifact is None:raise HTTPException(404,"产物未登记")
        if artifact.status!=ComplianceStatus.PUBLISH_READY:raise HTTPException(403,"产物尚未真人签发，禁止下载")
        if sha256_text(artifact.content)!=artifact.artifact_sha256:raise HTTPException(409,'产物内容校验和不符，禁止下载')
        check_current(task_id,artifact)
        return artifact
    return router

router=create_compliance_router()

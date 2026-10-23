"""Trusted-input candidate previews; rules only, no manuscript overwrite or model claim."""
import json, uuid, os, hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from code.backend.modules.compliance.integration import WorkflowComplianceAdapter
from code.backend.modules.unit_format.contract import UnitFormatRequest, UnitFormatUnitInput
from code.backend.modules.unit_format.handler import extract_and_convert_units
from code.backend.modules.oral_review.contract import OralReviewRequest, SubtitleSegment
from code.backend.modules.oral_review.handler import review_oral_request
from code.backend.db import utc_now_iso

class CurrentDraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_task_revision: int

def create_current_review_router(database_provider, get_actor):
    router = APIRouter(prefix='/api/v1')
    def trusted_actor(request: Request):
        from code.backend.shared.controls.auth import require_permission
        actor = get_actor(request)
        require_permission(actor, '执行后续审阅')
        return actor

    def load(task, req, actor):
        database = database_provider()
        adapter = WorkflowComplianceAdapter(database)
        row = adapter.authorize_task(task, actor)
        if row['task_revision'] != req.expected_task_revision:
            raise HTTPException(409, '任务修订变化')
        data = adapter.get_confirmed_dialogues(task)
        if any((u['target_market'] != 'MX' or u['target_language'] not in ('es', 'es-MX') for u in data['units'])):
            raise HTTPException(409, '本试点只支持墨西哥西语')
        limit = int(os.environ.get('SUBTITLE_DOWNSTREAM_INPUT_CHARS', '20000'))
        chars = sum((len(u['text']) + len(u['source_text']) for u in data['units']))
        if chars > limit:
            raise HTTPException(413, '当前源译稿超出输入预算，请拆分任务；没有静默裁剪')
        refs = {'task_revision': data['task_revision'], 'translation_revision': data['translation_revision'], 'content_hash': hashlib.sha256(json.dumps([u['text'] for u in data['units']]).encode()).hexdigest()}
        return (database, data, refs)

    @router.get('/downstream/tasks')
    def task_list(actor=Depends(trusted_actor)):
        if not actor.allowed:
            raise HTTPException(403, '主体未获授权')
        with database_provider().transaction() as c:
            from code.backend.modules.compliance.contract import AUTHORIZED_SIGNOFF_ROLES
            if actor.actor_role in AUTHORIZED_SIGNOFF_ROLES:
                rows=c.execute('SELECT task_id,task_revision,task_status FROM tasks ORDER BY created_at DESC LIMIT 100')
            else:
                rows=c.execute('SELECT task_id,task_revision,task_status FROM tasks WHERE created_by=? ORDER BY created_at DESC LIMIT 100',(actor.actor_id,))
            return [dict(row) for row in rows]

    @router.post('/units/tasks/{task_id}/convert')
    def units(task_id: str, req: CurrentDraftRequest, actor=Depends(trusted_actor)):
        database, data, refs = load(task_id, req, actor)
        result = extract_and_convert_units(UnitFormatRequest(task_ref=task_id, task_revision=data['task_revision'], target_language='es-MX', target_market='MX', units=[UnitFormatUnitInput(unit_id=u['unit_id'], target_text=u['text'], source_text=u['source_text'], input_revision=u['translation_revision']) for u in data['units']]))
        body = result.model_dump(mode='json')
        run = 'unit_run_' + uuid.uuid4().hex[:12]
        manifest = {**body['manifest'], 'trusted_input': refs, 'mode': 'rules_only', 'model_used': False, 'input_char_budget': int(os.environ.get('SUBTITLE_DOWNSTREAM_INPUT_CHARS', '20000'))}
        with database.transaction() as c:
            c.execute('INSERT INTO unit_format_runs(run_id,task_id,task_revision,target_language,target_market,candidates_json,manifest_json,status,actor_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)', (run, task_id, data['task_revision'], 'es-MX', 'MX', json.dumps(body['candidates']), json.dumps(manifest), 'AI_PROPOSED', actor.actor_id, utc_now_iso()))
        return {**body, 'run_id': run, 'manifest': manifest, 'ai_origin': False, 'generated_by': 'rule_engine'}

    @router.post('/oral/tasks/{task_id}/review')
    def oral(task_id: str, req: CurrentDraftRequest, actor=Depends(trusted_actor)):
        database, data, refs = load(task_id, req, actor)
        result = review_oral_request(OralReviewRequest(request_id='oral_req_' + uuid.uuid4().hex[:8], task_ref=task_id, target_language='es-MX', segments=[SubtitleSegment(segment_id=u['unit_id'], text=u['text'], start_time=u['start_ms'] / 1000, end_time=u['end_ms'] / 1000) for u in data['units']]))
        body = result.model_dump(mode='json')
        run = 'oral_run_' + uuid.uuid4().hex[:12]
        manifest = {**body['manifest'], 'trusted_input': refs, 'mode': 'rules_only', 'model_used': False, 'coverage_limitations': ['词表和可读性规则不能保证自然度、反讽或语义完整']}
        with database.transaction() as c:
            c.execute('INSERT INTO oral_review_runs(run_id,task_id,request_id,overall_status,items_json,manifest_json,actor_id,created_at) VALUES (?,?,?,?,?,?,?,?)', (run, task_id, body['request_id'], body['overall_status'], json.dumps(body['items']), json.dumps(manifest), actor.actor_id, utc_now_iso()))
        return {**body, 'run_id': run, 'manifest': manifest, 'ai_origin': False, 'generated_by': 'rule_engine'}

    @router.get('/downstream/tasks/{task_id}/latest')
    def latest(task_id: str, actor=Depends(trusted_actor)):
        database = database_provider()
        adapter = WorkflowComplianceAdapter(database)
        adapter.authorize_task(task_id, actor)
        result = {}
        try:
            data = adapter.get_confirmed_dialogues(task_id)
            revision = data['translation_revision']
        except HTTPException:
            revision = None
        with database.transaction() as c:
            for name, table, field in [('units', 'unit_format_runs', 'candidates_json'), ('oral', 'oral_review_runs', 'items_json')]:
                row = c.execute(f'SELECT * FROM {table} WHERE task_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1', (task_id,)).fetchone()
                if row:
                    manifest = json.loads(row['manifest_json'])
                    result[name] = {'run_id': row['run_id'], 'items': json.loads(row[field]), 'manifest': manifest, 'stale': manifest.get('trusted_input', {}).get('translation_revision') != revision, 'ai_origin': False, 'generated_by': 'rule_engine'}
        return result
    return router

"""Trusted current-task/revision/coverage gate. Missing evidence always blocks delivery."""
import hashlib, json
from fastapi import HTTPException
from .contract import AUTHORIZED_SIGNOFF_ROLES, COMPLIANCE_POLICY_VERSION, SubtitleCue, PlatformProfile
from code.backend.modules.culture_check.registry import default_registry

class WorkflowComplianceAdapter:

    def __init__(self, database, registry=None):
        self.db = database
        self.registry = registry or default_registry

    def authorize_task(self, task_id, actor=None):
        if not actor or not (actor.get('allowed', False) if isinstance(actor, dict) else actor.allowed):
            raise HTTPException(403, '操作主体未获授权')
        with self.db.transaction() as c:
            row = c.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, '任务不存在')
        value = lambda key: actor.get(key) if isinstance(actor, dict) else getattr(actor, key, None)
        if value('actor_role') == 'human_denied' or (row['created_by'] != value('actor_id') and value('actor_role') not in AUTHORIZED_SIGNOFF_ROLES):
            raise HTTPException(403, '当前主体无权访问此任务')
        return dict(row)

    def check_signoff_role(self, actor):
        value = lambda key: actor.get(key) if isinstance(actor, dict) else getattr(actor, key, None)
        if value('actor_type') != 'human' or value('actor_role') not in AUTHORIZED_SIGNOFF_ROLES:
            raise HTTPException(403, '只有有权真人审阅员可以签发')

    def get_confirmed_dialogues(self, task_id):
        with self.db.transaction() as c:
            task = c.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not task:
                raise HTTPException(404, '任务不存在')
            if task['task_status'] == 'DRAFT' or not task['confirmed_by']:
                raise HTTPException(409, '任务尚未确认')
            source = c.execute('SELECT * FROM source_transcripts WHERE task_id=? ORDER BY revision DESC LIMIT 1', (task_id,)).fetchone()
            if not source or source['status'] != 'CONFIRMED' or (not source['confirmed_by']):
                raise HTTPException(409, '当前源稿尚未人工确认')
            units = c.execute('SELECT * FROM source_utterances WHERE task_id=? AND transcript_revision=? ORDER BY unit_index', (task_id, source['revision'])).fetchall()
            result = []
            trans_manifests = {}
            for unit in units:
                row = c.execute('SELECT * FROM translations WHERE task_id=? AND source_revision=? AND unit_id=? ORDER BY translation_revision DESC,rowid DESC LIMIT 1', (task_id, source['revision'], unit['unit_id'])).fetchone()
                if not row or row['status'] not in ('CONFIRMED', 'MANUAL_LOCKED') or (not row['confirmed_by']):
                    raise HTTPException(409, '当前译稿尚未完整人工确认')
                if unit['start_ms'] is None or unit['end_ms'] is None or unit['end_ms'] <= unit['start_ms']:
                    raise HTTPException(409, '缺少有效字幕时间边界，不能伪造时间')
                run = c.execute('SELECT * FROM runs WHERE run_id=?', (row['run_id'],)).fetchone() if row['run_id'] else None
                if not run or run['run_status'] != 'SUCCEEDED':
                    raise HTTPException(409, '缺少成功的翻译运行依据')
                manifest = json.loads(run['context_manifest'] or '{}')
                if any((not manifest.get(k) for k in ('model_id', 'prompt_hash', 'input_hash'))) or manifest.get('is_simulated'):
                    raise HTTPException(409, '翻译溯源缺项或为模拟')
                if c.execute("SELECT 1 FROM translation_checks WHERE translation_id=? AND severity='BLOCK' AND status='OPEN' LIMIT 1", (row['translation_id'],)).fetchone():
                    raise HTTPException(409, '译文仍有阻断检查')
                trans_manifests[row['run_id']] = hashlib.sha256(run['context_manifest'].encode()).hexdigest()
                result.append({**dict(row), 'source_text': unit['text'], 'start_ms': unit['start_ms'], 'end_ms': unit['end_ms']})
        if not result:
            raise HTTPException(409, '没有可交付对话')
        revision = 'src' + str(source['revision']) + ':' + ','.join((r['unit_id'] + '=' + str(r['translation_revision']) for r in result))
        return {'task_revision': task['task_revision'], 'source_revision': source['revision'], 'translation_revision': revision, 'units': result, 'translation_manifests': trans_manifests, 'cues': [SubtitleCue(index=i + 1, start_time=r['start_ms'] / 1000, end_time=r['end_ms'] / 1000, text=r['text']) for i, r in enumerate(result)]}

    def snapshot(self, task_id):
        dialogues = self.get_confirmed_dialogues(task_id)
        rules = {r.rule_id: r.rule_version for r in self.registry.retrieve_applicable_rules(target_market='MX', only_active=True)}
        if not rules:
            raise HTTPException(409, '正式市场规则仍待核验，暂不能签发交付')
        with self.db.transaction() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='culture_runs'").fetchone():
                raise HTTPException(409, '缺少文化检测记录')
            run = c.execute('SELECT * FROM culture_runs WHERE task_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1', (task_id,)).fetchone()
            if not run or run['status'] != 'COMPLETED' or run['task_revision'] != dialogues['source_revision']:
                raise HTTPException(409, '文化检测缺失、失败或源稿版本过期')
            manifest = json.loads(run['manifest'])
            refs = {u['unit_id']: {'translation_id': u['translation_id'], 'revision': u['translation_revision']} for u in dialogues['units']}
            if manifest.get('translation_refs') != refs or manifest.get('rule_versions') != rules:
                raise HTTPException(409, '文化检测依据的译稿或规则已变化')
            if manifest.get('is_simulated') or any((not manifest.get(k) for k in ('model_id', 'prompt_hash', 'input_hash'))):
                raise HTTPException(409, '文化运行缺少真实溯源')
            if set(json.loads(run['checked_unit_ids'])) != set(refs) or json.loads(run['unchecked_units']) or json.loads(run['coverage_limitations']):
                raise HTTPException(409, '文化检测存在未覆盖范围或缺失证据')
            issues = c.execute('SELECT * FROM culture_issues WHERE run_id=?', (run['run_id'],)).fetchall()
            for issue in issues:
                if issue['severity_proposal'] in ('P0', 'P1') and issue['status'] not in ('REJECTED', 'IGNORED'):
                    raise HTTPException(409, '文化红黄风险仍存在；确认风险不代表解除风险')
                if issue['severity_proposal'] in ('P0', 'P1'):
                    decision = c.execute('SELECT actor_role FROM culture_decisions WHERE issue_id=? ORDER BY created_at DESC LIMIT 1', (issue['issue_id'],)).fetchone()
                    if not decision or decision['actor_role'] not in ('culture_senior', 'legal_reviewer'):
                        raise HTTPException(409, '缺少有权审阅员文化风险处理依据')
        body = {'task_revision': dialogues['task_revision'], 'source_revision': dialogues['source_revision'], 'translation_refs': refs, 'content_hash': hashlib.sha256(json.dumps([{'text': u['text'], 'start_ms': u['start_ms'], 'end_ms': u['end_ms']} for u in dialogues['units']], sort_keys=True).encode()).hexdigest(), 'translation_manifests': dialogues['translation_manifests'], 'culture_run_id': run['run_id'], 'culture_manifest_hash': hashlib.sha256(run['manifest'].encode()).hexdigest(), 'rule_versions': rules, 'policy_version': COMPLIANCE_POLICY_VERSION, 'profile': PlatformProfile().model_dump(mode='json')}
        return (dialogues, body)

    def check_culture_gate(self, task_id):
        return self.snapshot(task_id)

    def verify_current_revision(self, task_id, revision):
        if self.get_confirmed_dialogues(task_id)['translation_revision'] != revision:
            raise HTTPException(409, '当前译稿修订已变化')

    def record_failure(self, task_id, actor, code):
        from code.backend.db import utc_now_iso
        import uuid
        now = utc_now_iso()
        run_id = 'run_delivery_' + uuid.uuid4().hex[:12]
        actor_id = actor.get('actor_id') if isinstance(actor, dict) else actor.actor_id
        with self.db.transaction() as c:
            task = c.execute('SELECT task_revision FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            c.execute('INSERT INTO runs(run_id,task_id,task_revision,trace_id,authorization_ref,permission_check_ref,module,input_refs,input_revision,idempotency_key,attempt_no,attempts,run_status,stop_reason,context_manifest,manifest_hash,steps,started_at,ended_at,usage,controls,output_refs,failure,created_at,created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (run_id, task_id, task['task_revision'], run_id, 'LOCAL', 'SERVER_SESSION', 'compliance', '[]', task['task_revision'], run_id, 1, '[]', 'FAILED', code, json.dumps({'policy_version': COMPLIANCE_POLICY_VERSION}), 'unmeasured', '[]', now, now, json.dumps({'external_api_calls': 0}), json.dumps({'automatic_retry': False}), '[]', json.dumps({'code': code, 'message': '检测器异常，已阻断交付，不自动重试'}), now, actor_id))
        return run_id


    def for_connection(self, connection):
        from contextlib import contextmanager
        class TransactionDatabase:
            @contextmanager
            def transaction(self):
                yield connection
        return WorkflowComplianceAdapter(TransactionDatabase(), self.registry)

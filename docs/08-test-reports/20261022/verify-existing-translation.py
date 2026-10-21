"""Independent acceptance of existing code; isolated SIMULATED data, no network."""
import json
import socket
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import config.settings as settings

report_dir = settings.BASE_DIR / 'docs/08-test-reports/20261022'
fixture_dir = report_dir / ('mock-fixtures-' + uuid.uuid4().hex[:8])
fixture_dir.mkdir()
settings.DB_PATH = fixture_dir / 'review.db'
settings.TEST_MODE = False
from fastapi.testclient import TestClient
from code.backend.main import app
from code.backend.db import db
from code.backend.modules.translation import source_cleanup as cleanup
from code.backend.modules.translation import handler

def deny_network(*args, **kwargs):
    raise AssertionError('NETWORK_DISABLED_FOR_INDEPENDENT_REVIEW')

def response(value, status=200):
    return SimpleNamespace(status_code=status, json=lambda: {
        'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(value)}]}}],
        'usageMetadata': {'totalTokenCount': 0, 'is_mock': True}})

result = {'scope': 'SIMULATED isolated DB and mocked provider; no cloud calls',
          'database': str(settings.DB_PATH), 'network_calls': 0}
with patch.object(socket, 'create_connection', deny_network), TestClient(app, base_url='http://127.0.0.1:8765') as client:
    client.post('/api/v1/auth/register-operator', json={'display_name': 'SIMULATED-INDEPENDENT', 'role': 'media_operator'})
    task = client.post('/api/v1/tasks', json={'request_key': uuid.uuid4().hex, 'task_type': 'source_only'}).json()['task_id']
    with db.transaction() as conn:
        def insert(table, row):
            conn.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
        insert('runs', dict(run_id='SIMULATED-ASR', task_id=task, task_revision=1, trace_id='SIMULATED', module='asr_alignment', input_refs='[]',input_revision=1,idempotency_key='SIMULATED',attempts='[]',run_status='SUCCEEDED',context_manifest='{}',manifest_hash='SIMULATED',steps='[]',usage='{}',controls='{}',output_refs='[]',created_at='SIMULATED',created_by='SIMULATED'))
        for i in range(3):
            audio = fixture_dir / f'chunk{i}.wav'
            audio.write_bytes(b'SIMULATED audio; ffmpeg mocked')
            insert('asr_chunks', dict(chunk_id=f'chk{i}',task_id=task,slice_run_id='slice1',chunk_index=i,start_ms=i*10000,end_ms=(i+1)*10000,offset_ms=i*10000,duration_ms=10000,checksum_sha256=f'MOCK{i}',file_path=str(audio),quality_stats='{}',status='READY',created_at='SIMULATED'))
            insert('candidates', dict(candidate_id=f'cand{i}',task_id=task,run_id='SIMULATED-ASR',segment_id=f'seg{i}',chunk_id=f'chk{i}',candidate_kind='composite',proposed=json.dumps({'text':f'测试第{i}片。'}),confidence='{}',content_hash=f'MOCK{i}',created_at='SIMULATED'))
    payloads = []
    def post_cleanup(client_, endpoint, headers, payload):
        payloads.append(payload)
        return response({'speakers': [], 'utterances': [{'unit_id':'u1','text':'测试第0片。测试第1片。测试第2片。','source_spans':[{'chunk_id':f'chk{i}','original_text':f'测试第{i}片。'} for i in range(3)]}], 'operations':[], 'issues':[]})
    allowed = SimpleNamespace(allowed_in_pilot=True, missing_items=[])
    with patch.object(cleanup, 'check_cloud_authorization', lambda: allowed), patch.object(cleanup, '_post_gemini_serial', post_cleanup), patch.object(cleanup.subprocess, 'run', return_value=SimpleNamespace(stdout=b'SIMULATED mp3')):
        a = client.post(f'/api/v1/tasks/{task}/source/cleanup', json={'simulate':False})
    result['A_http'] = a.status_code
    result['A_body'] = a.json()
    if payloads:
        parts = payloads[0]['contents'][0]['parts']
        result['A_audio_parts'] = sum('inline_data' in p for p in parts)
        result['A_all_three_composite_texts'] = all(f'测试第{i}片' in parts[0]['text'] for i in range(3))
    confirm = client.post(f'/api/v1/tasks/{task}/source-transcript/confirm', json={'expected_revision':1})
    result['source_confirm_http'] = confirm.status_code
    calls = []
    def post_bc(client_, endpoint, headers, payload):
        calls.append(payload)
        if len(calls) == 1:
            return response({'translations':[{'unit_id':'u1','translation':'Texto de prueba.','term_hits':[],'brief_source_paraphrase':'测试文字','issues':[]}]})
        return response({'issues':[{'unit_id':'u1','category':'omission','severity':'WARN','detail':'SIMULATED semantic finding'}]})
    with patch.object(handler,'check_cloud_authorization',lambda: allowed), patch.object(handler,'_post_gemini_serial',post_bc):
        b = client.post(f'/api/v1/tasks/{task}/translation/generate',json={'target_language':'es-MX','target_market':'MX','simulate':False})
    result['BC_http'] = b.status_code
    result['BC_body'] = b.json()
    result['BC_calls'] = len(calls)
    source_payload=client.get(f'/api/v1/tasks/{task}/source-transcript').json()
    translations_payload=client.get(f'/api/v1/tasks/{task}/translations').json()
    (report_dir/'translation-ui-fixture.json').write_text(json.dumps({'task_id':task,'source':source_payload,'translations':translations_payload},ensure_ascii=False),encoding='utf-8')
    edit=client.patch(f'/api/v1/tasks/{task}/translations/u1',json={'expected_revision':1,'source_revision':1,'text':'SIMULATED human revision'})
    result['translation_edit_http']=edit.status_code
    lock=client.post(f'/api/v1/tasks/{task}/translations/u1/lock',json={'expected_revision':2,'source_revision':1})
    result['translation_lock_http']=lock.status_code
    locked_edit=client.patch(f'/api/v1/tasks/{task}/translations/u1',json={'expected_revision':2,'source_revision':1,'text':'forbidden overwrite'})
    result['locked_edit_http']=locked_edit.status_code
    rollback=client.post(f'/api/v1/tasks/{task}/translations/u1/rollback',json={'expected_revision':2,'source_revision':1,'target_revision':1,'reason':'SIMULATED rollback'})
    result['rollback_http']=rollback.status_code
    result['rollback_body']=rollback.json()
    with db.transaction() as conn:
        result['semantic_findings'] = [dict(r) for r in conn.execute('SELECT * FROM translation_checks WHERE task_id=?',(task,))]
    fail_calls=[]
    def post_bc_failure(client_, endpoint, headers, payload):
        fail_calls.append(payload)
        return response({'translations':[{'unit_id':'u1','translation':'Otro texto.','term_hits':[],'issues':[]}]}) if len(fail_calls)==1 else response({},503)
    with patch.object(handler,'check_cloud_authorization',lambda:allowed),patch.object(handler,'_post_gemini_serial',post_bc_failure):
        failed=client.post(f'/api/v1/tasks/{task}/translation/generate',json={'target_language':'es-MX','target_market':'MX','simulate':False})
    result['C_failure_http']=failed.status_code
    result['C_failure_body']=failed.json()
    with db.transaction() as conn:
        result['C_failure_blocks']=[dict(r) for r in conn.execute("SELECT severity,detail FROM translation_checks WHERE task_id=? AND severity='BLOCK'",(task,))]
result['passed'] = (result['A_http']==200 and result.get('A_audio_parts')==3 and result.get('A_all_three_composite_texts') and result['BC_http']==200 and result['BC_calls']==2 and any('SIMULATED semantic finding' in str(x) for x in result['semantic_findings']) and bool(result['C_failure_blocks']))
(report_dir/'translation-provider-mock-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

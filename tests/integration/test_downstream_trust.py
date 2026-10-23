"""Isolated, explicitly SIMULATED authorization fixtures; no production approvals or cloud."""
import json, uuid
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from code.backend.shared.models import ActorContext
from code.backend.modules.culture_check.repository import CultureRepository
from code.backend.modules.compliance.router import create_compliance_router, SqliteArtifactStore
from code.backend.modules.compliance.integration import WorkflowComplianceAdapter

class Registry:

    def retrieve_applicable_rules(self, **kwargs):
        return [SimpleNamespace(rule_id='SIMULATED_RULE', rule_version='v1')]

def prepare(auth_client, database):
    task = auth_client.post('/api/v1/tasks', json={'request_key': uuid.uuid4().hex, 'task_type': 'source_only'}).json()['task_id']
    CultureRepository(database)
    with database.transaction() as c:
        c.execute("UPDATE tasks SET task_status='READY',confirmed_by='SIMULATED' WHERE task_id=?", (task,))
        c.execute("INSERT INTO source_transcripts(transcript_id,task_id,revision,status,source_language,confirmed_by,created_at,updated_at) VALUES ('SIMULATED_SOURCE',?,1,'CONFIRMED','zh-CN','SIMULATED','SIMULATED','SIMULATED')", (task,))
        c.execute("INSERT INTO source_utterances(unit_id,task_id,transcript_revision,unit_index,text,source_spans,start_ms,end_ms,status,created_at,updated_at) VALUES ('u1',?,1,1,'你好。','[]',0,2000,'CONFIRMED','SIMULATED','SIMULATED')", (task,))
        manifest = json.dumps({'model_id': 'SIMULATED', 'prompt_hash': 'h', 'input_hash': 'i', 'temperature': 0})
        c.execute("INSERT INTO runs(run_id,task_id,task_revision,trace_id,authorization_ref,permission_check_ref,module,input_refs,input_revision,idempotency_key,attempt_no,attempts,run_status,context_manifest,manifest_hash,steps,started_at,usage,controls,output_refs,created_at,created_by) VALUES ('SIMULATED_TRANS_RUN',?,1,'t','a','p','translation','[]',1,'i',1,'[]','SUCCEEDED',?,'h','[]','SIMULATED','{}','{}','[]','SIMULATED','SIMULATED')", (task, manifest))
        c.execute("INSERT INTO translations(translation_id,task_id,unit_id,source_revision,translation_revision,target_language,target_market,text,status,run_id,confirmed_by,created_at,updated_at) VALUES ('SIMULATED_TRANS',?,'u1',1,1,'es-MX','MX','Hola.','CONFIRMED','SIMULATED_TRANS_RUN','SIMULATED','SIMULATED','SIMULATED')", (task,))
        culture = json.dumps({'translation_refs': {'u1': {'translation_id': 'SIMULATED_TRANS', 'revision': 1}}, 'rule_versions': {'SIMULATED_RULE': 'v1'}, 'model_id': 'SIMULATED', 'prompt_hash': 'p', 'input_hash': 'i'})
        c.execute('INSERT INTO culture_runs(run_id,task_id,task_revision,target_market,manifest,coverage_limitations,checked_unit_ids,unchecked_units,status,created_at) VALUES (?,?,1,?,?,?, ?,?, ?,?)', ('SIMULATED_CULTURE', task, 'MX', culture, '[]', json.dumps(['u1']), '[]', 'COMPLETED', 'SIMULATED'))
    return task

def client_for(database, role='reviewer'):
    app = FastAPI()
    actor = ActorContext(actor_id='isolated-reviewer', actor_type='human', actor_role=role, allowed=True)
    app.include_router(create_compliance_router(get_actor_context=lambda request: actor, storage_adapter=SqliteArtifactStore(database), task_adapter=WorkflowComplianceAdapter(database, Registry())))
    return TestClient(app)

def test_trusted_normal_signoff_persistence_and_stale(isolated_test_env, auth_client):
    db = isolated_test_env['db']
    task = prepare(auth_client, db)
    client = client_for(db)
    base = f'/api/v1/compliance/tasks/{task}'
    response = client.post(base + '/validate-and-export', json={'expected_task_revision': 1})
    assert response.status_code == 200, response.text
    artifact = response.json()
    assert artifact['status'] == 'VALIDATED' and 'content' not in artifact
    aid = artifact['artifact_id']
    revision = artifact['manifest']['translation_revision']
    assert client.get(base + '/artifact').status_code == 403
    body = {'artifact_id': aid, 'expected_revision': revision}
    assert client_for(db, 'viewer').post(base + '/signoff', json=body).status_code == 403
    assert client_for(db, 'media_operator').post(base + '/signoff', json=body).status_code == 403
    assert client.post(base + '/signoff', json={**body, 'expected_revision': 'wrong'}).status_code == 409
    assert client.post(base + '/signoff', json=body).status_code == 200
    assert client_for(db).get(base + '/artifact').json()['content'].endswith('Hola.\n')
    assert client_for(db).get('/api/v1/compliance/tasks/MISSING/artifact', params={'artifact_id': aid}).status_code == 404
    with db.transaction() as c:
        c.execute("UPDATE translations SET translation_revision=2 WHERE translation_id='SIMULATED_TRANS'")
    assert client.get(base + '/artifact').status_code == 409
    assert client.post(base + '/signoff', json=body).status_code == 409

@pytest.mark.parametrize('failure', ['no_run', 'unchecked', 'limit', 'failed', 'null_time', 'confirmed_red', 'rules_changed', 'missing_manifest'])
def test_culture_evidence_and_detector_fail_closed(isolated_test_env, auth_client, failure):
    db = isolated_test_env['db']
    task = prepare(auth_client, db)
    with db.transaction() as c:
        if failure == 'no_run':
            c.execute('DELETE FROM culture_runs')
        if failure == 'unchecked':
            c.execute('UPDATE culture_runs SET unchecked_units=?', (json.dumps([{'unit_id': 'u1'}]),))
        if failure == 'limit':
            c.execute('UPDATE culture_runs SET coverage_limitations=?', (json.dumps(['未看画面']),))
        if failure == 'failed':
            c.execute("UPDATE culture_runs SET status='FAILED'")
        if failure == 'null_time':
            c.execute('UPDATE source_utterances SET end_ms=NULL')
        if failure == 'missing_manifest':
            c.execute("UPDATE runs SET context_manifest='{}' WHERE run_id='SIMULATED_TRANS_RUN'")
        if failure == 'rules_changed':
            row = json.loads(c.execute('SELECT manifest FROM culture_runs').fetchone()[0])
            row['rule_versions'] = {'SIMULATED_RULE': 'old'}
            c.execute('UPDATE culture_runs SET manifest=?', (json.dumps(row),))
        if failure == 'confirmed_red':
            c.execute("INSERT INTO culture_issues(issue_id,run_id,task_id,task_revision,unit_id,category,severity_proposal,confidence,trigger_spans,rule_refs,case_refs,evidence_refs,evidence_status,explanation,suggested_action,status,created_at) VALUES ('SIMULATED_RED','SIMULATED_CULTURE',?,1,'u1','politics','P0','{}','[]','[]','[]','[]','sufficient','SIMULATED','block_release','CONFIRMED','SIMULATED')", (task,))
    response = client_for(db).post(f'/api/v1/compliance/tasks/{task}/validate-and-export', json={'expected_task_revision': 1})
    assert response.status_code == 409, response.text
    with db.transaction() as c:
        assert c.execute('SELECT COUNT(*) FROM compliance_artifacts').fetchone()[0] == 0

def test_trusted_preview_inputs_and_persistence(isolated_test_env, auth_client):
    db = isolated_test_env['db']
    task = prepare(auth_client, db)
    for path in ('units/tasks/' + task + '/convert', 'oral/tasks/' + task + '/review'):
        response = auth_client.post('/api/v1/' + path, json={'expected_task_revision': 1})
        assert response.status_code == 200, response.text
        assert response.json()['manifest']['model_used'] is False
    assert set(auth_client.get(f'/api/v1/downstream/tasks/{task}/latest').json()) == {'units', 'oral'}
    assert auth_client.post(f'/api/v1/units/tasks/{task}/convert', json={'expected_task_revision': 1, 'units': []}).status_code == 422
    assert auth_client.post('/api/v1/oral/tasks/MISSING/review', json={'expected_task_revision': 1}).status_code == 404

def test_detector_exception_and_immutable_store(isolated_test_env, auth_client, monkeypatch):
    from code.backend.modules.compliance import router
    db = isolated_test_env['db']
    task = prepare(auth_client, db)
    client = client_for(db)
    base = f'/api/v1/compliance/tasks/{task}'
    response = client.post(base + '/validate-and-export', json={'expected_task_revision': 1})
    assert response.status_code == 200
    store = SqliteArtifactStore(db)
    artifact = store.get(task, response.json()['artifact_id'])
    forged = artifact.model_copy(deep=True)
    forged.content = 'forged'
    with pytest.raises(Exception) as error:
        store.save(task, forged)
    assert error.value.status_code == 409

    def failed(**kwargs):
        raise RuntimeError('SIMULATED detector failure')
    monkeypatch.setattr(router, 'validate_and_export_artifact', failed)
    response = client.post(base + '/validate-and-export', json={'expected_task_revision': 1})
    assert response.status_code == 503 and response.json()['detail']['stop_reason'] == 'DETECTOR_FAILURE'
    with db.transaction() as c:
        assert c.execute("SELECT run_status FROM runs WHERE stop_reason='DETECTOR_FAILURE'").fetchone()[0] == 'FAILED'
        assert c.execute('SELECT COUNT(*) FROM compliance_artifacts').fetchone()[0] == 1


def test_signoff_transaction_rechecks_race(isolated_test_env,auth_client,monkeypatch):
 db=isolated_test_env['db'];task=prepare(auth_client,db)
 store=SqliteArtifactStore(db);adapter=WorkflowComplianceAdapter(db,Registry())
 app=FastAPI();actor=ActorContext(actor_id='isolated-reviewer',actor_type='human',actor_role='reviewer',allowed=True)
 app.include_router(create_compliance_router(get_actor_context=lambda request:actor,storage_adapter=store,task_adapter=adapter))
 client=TestClient(app);base=f'/api/v1/compliance/tasks/{task}'
 artifact=client.post(base+'/validate-and-export',json={'expected_task_revision':1}).json()
 original=store.save
 def race(task_id,package,current_guard=None):
  with db.transaction() as c:c.execute("UPDATE culture_runs SET status='FAILED'")
  return original(task_id,package,current_guard=current_guard)
 monkeypatch.setattr(store,'save',race)
 assert client.post(base+'/signoff',json={'artifact_id':artifact['artifact_id'],'expected_revision':artifact['manifest']['translation_revision']}).status_code==409
 assert store.get(task,artifact['artifact_id']).status.value=='VALIDATED'


def test_unrelated_operator_cannot_read_task(isolated_test_env,auth_client):
 db=isolated_test_env['db'];task=prepare(auth_client,db)
 assert client_for(db,'viewer').get(f'/api/v1/compliance/tasks/{task}/state').status_code==403


def test_download_rejects_storage_checksum_mismatch(isolated_test_env,auth_client):
 db=isolated_test_env['db'];task=prepare(auth_client,db);client=client_for(db);base=f'/api/v1/compliance/tasks/{task}'
 artifact=client.post(base+'/validate-and-export',json={'expected_task_revision':1}).json()
 assert 'profile' in artifact['manifest']['gate_snapshot']
 assert client.post(base+'/signoff',json={'artifact_id':artifact['artifact_id'],'expected_revision':artifact['manifest']['translation_revision']}).status_code==200
 with db.transaction() as c:c.execute("UPDATE compliance_artifacts SET content='FORGED'")
 assert client.get(base+'/artifact').status_code==409

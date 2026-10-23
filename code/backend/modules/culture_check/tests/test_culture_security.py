import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from types import SimpleNamespace
from ..router import create_culture_router
from ..contract import CultureCheckRequest, CultureUnitInput, LLMCultureCheckOutput
from ..handler import execute_culture_check, build_prompts
from ..registry import CultureRegistry
from ..validator import compute_ranking_score


def test_all_private_routes_fail_closed_and_no_raw_check():
    app=FastAPI(); app.include_router(create_culture_router())
    c=TestClient(app)
    for url in ['/sources','/rules','/cases','/runs/no','/tasks/no/issues','/tasks/no/metrics']:
        assert c.get('/api/v1/culture'+url).status_code==503
    assert c.post('/api/v1/culture/check',json={}).status_code==404
    assert c.post('/api/v1/culture/tasks/no/check').status_code==503


def test_denied_actor_cannot_read_or_trigger():
    def denied(request): return SimpleNamespace(actor_id='denied',allowed=False,actor_type='human')
    app=FastAPI();app.include_router(create_culture_router(get_actor_context=denied))
    c=TestClient(app)
    assert c.get('/api/v1/culture/sources').status_code==403
    assert c.post('/api/v1/culture/tasks/no/check').status_code==403


def test_production_simulation_stops(monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings,'TEST_MODE',False)
    req=CultureCheckRequest(task_ref='isolated',task_revision=1,units=[CultureUnitInput(unit_id='u',source_text='你好',target_text='Hola')],simulate=True)
    with pytest.raises(PermissionError): execute_culture_check(req)


def test_registry_no_unverified_rules_or_foreign_market():
    registry=CultureRegistry()
    assert registry.retrieve_applicable_rules()==[]
    assert registry.retrieve_applicable_rules(target_market='US',only_active=False)==[]
    assert registry.retrieve_applicable_cases()==[]
    assert all(r.status!='ACTIVE' for r in registry.retrieve_applicable_rules(only_active=False))


def test_missing_audience_not_filled_and_media_defaults_truthful():
    req=CultureCheckRequest(task_ref='isolated',task_revision=1,units=[CultureUnitInput(unit_id='u',source_text='你好',target_text='Hola')])
    assert not req.simulate and not req.media_evidence.has_audio
    _, user, _, _=build_prompts(req,[],[])
    assert '视为全年龄' not in user and '全渠道流媒体' not in user


def test_llm_rejects_server_fields_and_ranking_strict():
    with pytest.raises(ValueError): LLMCultureCheckOutput.model_validate({'issues':[],'checked_unit_ids':['u'],'run_id':'fake'})
    for factor in [True,1.0,'1',0,4]:
        with pytest.raises(ValueError): compute_ranking_score(factor,1,1)
    assert compute_ranking_score(3,2,2)==12


def test_confirmed_snapshot_and_translation_revision_protection(tmp_path):
    from code.backend.db import Database
    from ..integration import WorkflowCultureAdapter
    db=Database(db_path=tmp_path/'snapshot.db')
    with db.transaction() as conn:
        conn.execute("INSERT INTO source_transcripts(transcript_id,task_id,revision,status,source_language,created_at,updated_at) VALUES ('src','test',1,'CONFIRMED','zh-CN','now','now')")
        conn.execute("INSERT INTO source_utterances(unit_id,task_id,transcript_revision,unit_index,text,source_spans,status,created_at,updated_at) VALUES ('u','test',1,0,'你好','[]','CONFIRMED','now','now')")
        conn.execute("INSERT INTO translations(translation_id,task_id,unit_id,source_revision,translation_revision,target_language,target_market,text,status,confirmed_by,created_at,updated_at) VALUES ('tr','test','u',1,1,'es-MX','MX','Hola','CONFIRMED','human','now','now')")
    adapter=WorkflowCultureAdapter(db)
    request=adapter.build_check_request('test')
    assert request.units[0].translation_revision==1
    assert not request.simulate
    adapter.assert_current('test',request)
    with db.transaction() as conn:
        conn.execute("UPDATE translations SET translation_revision=2,text='Hola de nuevo' WHERE translation_id='tr'")
    with pytest.raises(HTTPException) as caught: adapter.assert_current('test',request)
    assert caught.value.status_code==409
    with db.transaction() as conn:
        conn.execute("UPDATE translations SET status='AI_PROPOSED',confirmed_by=NULL WHERE translation_id='tr'")
    with pytest.raises(HTTPException) as caught: adapter.build_check_request('test')
    assert caught.value.status_code==409


def test_failed_run_persists_unchecked_and_no_candidate(tmp_path):
    from code.backend.db import Database
    from ..repository import CultureRepository
    repo=CultureRepository(Database(db_path=tmp_path/'failed.db'))
    req=CultureCheckRequest(task_ref='failed-test',task_revision=1,units=[CultureUnitInput(unit_id='u',source_text='你好',target_text='Hola')])
    run_id=repo.save_failure(req,RuntimeError('simulated timeout'),'test-actor','test-service')
    run=repo.get_run(run_id)
    assert run['status']=='FAILED'
    assert repo.list_issues('failed-test')==[]
    import json
    assert run['manifest']['usage'] is None
    assert run['unchecked_units'][0]['unit_id']=='u'

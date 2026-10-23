"""Isolated SIMULATED regression fixtures; no outbound calls or user approvals."""
import json
from types import SimpleNamespace
from code.backend.modules.translation import handler as h
from code.backend.modules.translation.contract import GenerateTranslationRequest


def seed(client, database):
    import uuid
    task = client.post('/api/v1/tasks',json={'request_key':uuid.uuid4().hex,'task_type':'source_only'}).json()['task_id']
    with database.transaction() as c:
        c.execute("INSERT INTO source_transcripts (transcript_id,task_id,revision,status,source_language,created_at,updated_at) VALUES (?,?,1,'CONFIRMED','zh-CN','SIMULATED','SIMULATED')",('s-'+task,task))
        for index in (1,2):
            c.execute("INSERT INTO source_utterances (unit_id,task_id,transcript_revision,unit_index,text,source_spans,status,created_at,updated_at) VALUES (?,?,1,?,?,'[]','CONFIRMED','SIMULATED','SIMULATED')",(f'u{index}',task,index,'你好。'))
    return task


def test_history_checks_and_confirm_scope(isolated_test_env, auth_client):
    database=isolated_test_env['db']; task=seed(auth_client,database)
    req=GenerateTranslationRequest(target_language='es',target_market='MX',simulate=True)
    h.execute_translation_pipeline(task,req,database=database)
    before=auth_client.get(f'/api/v1/tasks/{task}/translations').json()['translations']
    old=before[0]['translation_id']
    with database.transaction() as c:
        c.execute("INSERT INTO translation_checks (check_id,task_id,unit_id,translation_id,category,severity,detail,status,created_at) VALUES ('old',?,?,?,'other','BLOCK','SIMULATED','OPEN','SIMULATED')",(task,before[0]['unit_id'],old))
    h.execute_translation_pipeline(task,req,database=database)
    current=auth_client.get(f'/api/v1/tasks/{task}/translations').json()
    assert len(current['translations'])==2
    assert not current['checks']
    unit=current['translations'][0]
    assert auth_client.post(f"/api/v1/tasks/{task}/translations/{unit['unit_id']}/confirm").status_code==422
    assert auth_client.post(f"/api/v1/tasks/{task}/translations/confirm-all",json={'source_revision':1,'expected_revisions':{'u1':1,'u2':1}}).status_code==409
    body={'source_revision':1,'expected_revisions':{u['unit_id']:u['translation_revision'] for u in current['translations']}}
    assert auth_client.post(f'/api/v1/tasks/{task}/translations/confirm-all',json=body).status_code==200
    h.execute_translation_pipeline(task,req,database=database)
    with database.transaction() as c:
        assert c.execute("SELECT COUNT(*) FROM translation_checks WHERE check_id='old'").fetchone()[0]==1
        assert c.execute('SELECT status FROM translations WHERE translation_id=?',(old,)).fetchone()[0]=='AI_PROPOSED'
    final=auth_client.get(f'/api/v1/tasks/{task}/translations').json()['translations']
    assert [u['translation_id'] for u in final]==[u['translation_id'] for u in current['translations']]


def test_failed_semantic_check_blocks_every_unit(isolated_test_env, auth_client, monkeypatch):
    database=isolated_test_env['db']; task=seed(auth_client,database)
    monkeypatch.setattr(h,'check_cloud_authorization',lambda:SimpleNamespace(allowed_in_pilot=True))
    payloads=[]
    def provider(client, endpoint, headers, payload):
        payloads.append(payload)
        if len(payloads)==1:
            result={'translations':[{'unit_id':f'u{i}','translation':'Hola.','term_hits':[],'brief_source_paraphrase':'你好','issues':[]} for i in (1,2)]}
            return SimpleNamespace(status_code=200,json=lambda:{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(result)}]}}]})
        return SimpleNamespace(status_code=429)
    monkeypatch.setattr(h,'_post_gemini_serial',provider)
    result=h.execute_translation_pipeline(task,GenerateTranslationRequest(target_language='es',target_market='MX'),database=database)
    assert result['status']=='CHECK_FAILED'
    assert 'Hola.' in payloads[1]['contents'][0]['parts'][0]['text']
    current=auth_client.get(f'/api/v1/tasks/{task}/translations').json()
    assert {i['unit_id'] for i in current['checks'] if i['severity']=='BLOCK'}=={'u1','u2'}
    for u in current['translations']:
        assert auth_client.post(f"/api/v1/tasks/{task}/translations/{u['unit_id']}/confirm",json={'source_revision':1,'expected_revision':u['translation_revision']}).status_code==400
    with database.transaction() as c:
        assert c.execute("SELECT run_status FROM runs WHERE module='translation' AND task_id=?",(task,)).fetchone()[0]=='FAILED'


def test_source_cleanup_sends_all_audio_not_only_first_two(isolated_test_env, auth_client, monkeypatch, tmp_path):
    from code.backend.modules.translation import source_cleanup as a
    database=isolated_test_env['db']; task=seed(auth_client,database)
    monkeypatch.setattr(a,'check_cloud_authorization',lambda:SimpleNamespace(allowed_in_pilot=True))
    monkeypatch.setattr(a.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(stdout=b'SIMULATED_MP3_EVIDENCE'))
    with database.transaction() as c:
        # Use a full-shaped successful ASR fixture copied from a real pipeline-generated simulated run.
        c.execute("INSERT INTO runs (run_id,task_id,task_revision,trace_id,authorization_ref,permission_check_ref,module,input_refs,input_revision,idempotency_key,attempt_no,attempts,run_status,context_manifest,manifest_hash,steps,started_at,usage,controls,output_refs,created_at,created_by) VALUES ('SIMULATED_ASR',?,1,'t','a','p','asr_alignment','[]',1,'i',1,'[]','SUCCEEDED','{}','h','[]','SIMULATED','{}','{}','[]','SIMULATED','SIMULATED')",(task,))
        for i in range(3):
            audio=tmp_path/f'{i}.wav'; audio.write_bytes(b'SIMULATED_AUDIO')
            c.execute("INSERT INTO asr_chunks (chunk_id,task_id,slice_run_id,chunk_index,start_ms,end_ms,offset_ms,duration_ms,checksum_sha256,file_path,quality_stats,status,created_at) VALUES (?,?, 'SIMULATED_SLICE',?,?,?,?,10000,? ,?,'{}','READY','SIMULATED')",(f'chunk{i}',task,i,i*10000,(i+1)*10000,i*10000,__import__('hashlib').sha256(audio.read_bytes()).hexdigest(),str(audio)))
            c.execute("INSERT INTO candidates (candidate_id,task_id,run_id,segment_id,chunk_id,candidate_kind,proposed,confidence,content_hash,created_at) VALUES (?,?, 'SIMULATED_ASR',?,?,'composite',?,'{}','SIMULATED','SIMULATED')",(f'c{i}',task,f'seg{i}',f'chunk{i}',json.dumps({'text':'你好。'})))
    sent=[]
    def provider(client, endpoint, headers, payload):
        assert payload['systemInstruction']['parts'][0]['text']
        assert 'responseJsonSchema' in payload['generationConfig']
        sent.extend(payload['contents'][0]['parts'])
        output={'speakers':[],'operations':[],'issues':[], 'utterances':[{'unit_id':f'u{i}','text':'你好。','source_spans':[{'chunk_id':f'chunk{i}','original_text':'你好。'}]} for i in range(3)]}
        return SimpleNamespace(status_code=200,json=lambda:{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}]})
    monkeypatch.setattr(a,'_post_gemini_serial',provider)
    result=a.execute_source_cleanup(task,database=database)
    assert result['utterances_count']==3
    assert len([p for p in sent if 'inline_data' in p])==3
    assert any('chunk2' in p.get('text','') for p in sent)

import json
import pytest
from .test_repair_regressions import seed
from ..knowledge import KnowledgeService
from ..contract import KnowledgeItemCreate,KnowledgeItemUpdate,GenerateTranslationRequest
from ..handler import execute_translation_pipeline


def test_terms_filter_language_market_task_and_conflicts(isolated_test_env):
    service=KnowledgeService(isolated_test_env['db'])
    def term(target,lang='es-MX',market='MX',scope='project',task=None):
        return service.create_item(KnowledgeItemCreate(source_text='林悦',target_text=target,target_language=lang,target_market=market,is_locked=True,scope=scope,task_id=task))
    good=term('Lin Yue');term('Lynn','en','US');term('Lin','es-MX','CO');term('otra','es-MX','MX','task','other')
    hits=service.query_locked_terms_for_units('PRJ-DEFAULT',['林悦来了'],'es-MX','MX',task_id='current')
    assert [h['term_id'] for h in hits]==[good['item_id']]
    term('Otra')
    with pytest.raises(ValueError,match='冲突'):service.query_locked_terms_for_units('PRJ-DEFAULT',['林悦来了'],'es-MX','MX',task_id='current')


def test_character_retrieval_relevant_and_scoped(isolated_test_env):
    service=KnowledgeService(isolated_test_env['db'])
    good=service.create_item(KnowledgeItemCreate(category='character',source_text='林悦'))
    service.create_item(KnowledgeItemCreate(category='character',source_text='无关人物'))
    service.create_item(KnowledgeItemCreate(category='character',source_text='林悦',scope='task',task_id='other'))
    selected=service.query_characters('PRJ-DEFAULT',units_text=['林悦来了'],task_id='current')
    assert [x['item_id'] for x in selected]==[good['item_id']]


def test_knowledge_mutations_preserve_immutable_snapshots(isolated_test_env):
    service=KnowledgeService(isolated_test_env['db'])
    item=service.create_item(KnowledgeItemCreate(source_text='名字',target_text='old'))
    original=service.snapshot_ref(item)
    service.update_item(item['item_id'],KnowledgeItemUpdate(target_text='new'))
    service.delete_item(item['item_id'])
    with service.db.transaction() as c: versions=[json.loads(r['snapshot']) for r in c.execute('SELECT snapshot FROM knowledge_versions WHERE item_id=? ORDER BY revision',(item['item_id'],))]
    assert versions[0]['target_text']=='old'
    assert any(v['target_text']=='new' for v in versions)
    assert versions[-1]['deleted'] is True
    assert original['snapshot']['target_text']=='old'


def test_pipeline_context_snapshot_and_confirmed_memory(isolated_test_env,auth_client):
    database=isolated_test_env['db'];task=seed(auth_client,database)
    service=KnowledgeService(database)
    term=service.create_item(KnowledgeItemCreate(source_text='你好',target_text='Hola',target_language='es',target_market='MX',is_locked=True))
    result=execute_translation_pipeline(task,GenerateTranslationRequest(target_language='es',target_market='MX',simulate=True),database=database)
    with database.transaction() as c:
        manifest=json.loads(c.execute('SELECT context_manifest FROM runs WHERE run_id=?',(result['manifest']['run_id'],)).fetchone()[0])
        c.execute("UPDATE translations SET status='CONFIRMED',confirmed_by='SIMULATED_HUMAN' WHERE task_id=?",(task,))
    assert manifest['context_snapshot']['locked_terms'][0]['context_ref']['snapshot']['target_text']=='Hola'
    memory=service.query_confirmed_history('PRJ-DEFAULT',task,['你好。'],'es','MX')
    assert len(memory)==2 and all(x['revision']==1 for x in memory)
    assert service.query_confirmed_history('PRJ-DEFAULT',task,['你好。'],'en','US')==[]
    service.update_item(term['item_id'],KnowledgeItemUpdate(target_text='Buenos dias'))
    assert manifest['context_snapshot']['locked_terms'][0]['context_ref']['snapshot']['target_text']=='Hola'


def test_b_c_instructions_are_separate_and_context_shared(isolated_test_env,auth_client,monkeypatch):
    from types import SimpleNamespace
    from .. import handler as h
    database=isolated_test_env['db'];task=seed(auth_client,database)
    payloads=[]
    monkeypatch.setattr(h,'check_cloud_authorization',lambda:SimpleNamespace(allowed_in_pilot=True))
    def provider(client,endpoint,headers,payload):
        payloads.append(payload)
        if len(payloads)==1:
            data={'translations':[{'unit_id':'u'+str(i),'translation':'Hola.','term_hits':[],'brief_source_paraphrase':'打招呼','issues':[]} for i in (1,2)]}
        else:data={'issues':[]}
        return SimpleNamespace(status_code=200,json=lambda:{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(data)}]}}]})
    monkeypatch.setattr(h,'_post_gemini_serial',provider)
    result=h.execute_translation_pipeline(task,GenerateTranslationRequest(target_language='es',target_market='MX'),database=database)
    assert result['status']=='AI_PROPOSED'
    assert len(payloads)==2
    for payload in payloads:
        assert 'systemInstruction' in payload
        assert '你好。' not in payload['systemInstruction']['parts'][0]['text']
        assert '你好。' in payload['contents'][0]['parts'][0]['text']
    assert 'prev_units' in payloads[0]['contents'][0]['parts'][0]['text']
    assert 'context' in payloads[1]['contents'][0]['parts'][0]['text'] or 'confirmed_history' in payloads[1]['contents'][0]['parts'][0]['text']


def test_prompt_contract_rejects_approval_and_fabricated_fields():
    from ..prompt_contract import PromptTranslationOutput,PromptCheckOutput
    with pytest.raises(ValueError):PromptTranslationOutput.model_validate({'translations':[],'status':'HUMAN_APPROVED'})
    with pytest.raises(ValueError):PromptCheckOutput.model_validate({'issues':[],'qe_score':0.99})

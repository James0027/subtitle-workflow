"""工单05B：六段式全链路端到端集成测试。

链路（全部经真实 HTTP 路由 + 真实隔离库）：

    ① Task Ingest        POST /api/v1/tasks
    ② ASR 结果           source_transcripts/source_utterances 落库（真实 ASR 需外部模型，本批未授权）
                         POST /api/v1/tasks/{id}/source-transcript/confirm   （人工确认源稿）
    ③ 翻译初稿           translations 初稿行落库（真实初翻需外部模型，本批未授权）
                         PATCH translations/{unit}（人工改稿）+ POST confirm-all（人工确认译文）
    ④ 文化检测           POST /api/v1/culture/tasks/{id}/check
    ⑤ 度量衡本地化       POST /api/v1/units/tasks/{id}/convert
    ⑥ 口语审校           POST /api/v1/oral/tasks/{id}/review
    ⑦ 合规质检+导出      POST /api/v1/compliance/tasks/{id}/validate-and-export
    ⑧ 五维哈希真人签发   POST /api/v1/compliance/tasks/{id}/signoff
    ⑨ 产物受控获取       GET  /api/v1/compliance/tasks/{id}/artifact

口径与边界（不得读成业务验收）：

- 全链路零外部模型调用：文化环节用**模块自带确定性规则路径**替换模型语境路径（manifest 标
  ``model_used=false``/``token_used=0`` 并留 coverage_limitations），其余环节本就是纯白盒。
- ②③ 的“模型产物”由测试写入隔离库充当输入快照，其后的确认/改稿/检测/导出/签发全部走真实路由；
  真实 ASR 与初翻质量不在本用例证明范围。
- 度量衡候选只作建议返回，不自动写回人工确认稿（RULE-SUB-001）；导出使用人工确认文本。
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from code.backend.modules.compliance.contract import COMPLIANCE_POLICY_VERSION, SubtitleCue
from code.backend.modules.compliance.handler import compute_signoff_hash, parse_subtitle, sha256_text
from code.backend.modules.compliance.router import InMemoryArtifactStore, create_compliance_router
from code.backend.modules.culture_check import router as culture_router
from code.backend.modules.culture_check.contract import CultureCheckResult
from code.backend.modules.culture_check.handler import execute_rule_based_path
from code.backend.modules.culture_check.registry import default_registry
from code.backend.modules.oral_review.router import create_oral_review_router
from code.backend.modules.unit_format.router import create_unit_format_router
from code.backend.shared.controls.auth import register_local_operator

# 三个字幕单元：(源语, 翻译初稿, 人工确认稿, 起止秒)
PIPELINE_UNITS = (
    {
        "unit_id": "u001",
        "source": "我在五百英里外的加油站。",
        "draft": "Estoy a 500 millas de aquí.",
        "final": "Estoy a 500 millas de aquí.",
        "start": 0.0,
        "end": 2.5,
    },
    {
        "unit_id": "u002",
        "source": "今天有一百度华氏度。",
        "draft": "Hoy están 100 grados Fahrenheit.",
        "final": "Hoy hace 100 grados Fahrenheit.",
        "start": 3.0,
        "end": 5.5,
    },
    {
        "unit_id": "u003",
        "source": "限速六十英里每小时。",
        "draft": "La velocidad máxima es 60 mph.",
        "final": "La velocidad máxima es 60 mph.",
        "start": 6.0,
        "end": 8.0,
    },
)

COMPLIANCE_RULE_VERSION = f"compliance-policy:{COMPLIANCE_POLICY_VERSION}"


# ==========================================
# 辅助：确定性文化引擎替身（零外呼）
# ==========================================

def install_deterministic_culture_engine(monkeypatch, calls):
    """把文化检测的模型语境路径替换为模块自带规则路径（不联网、不计费）。

    路由、鉴权、落库、任务/译稿适配器全部为真实链路；被替换的只有模型推理本身，
    因此本用例可证明“交接与门禁”，不证明“文化检测质量”。
    """

    def deterministic_check(request):
        calls.append(request)
        rules = default_registry.retrieve_applicable_rules(
            target_market=request.target_market, only_active=True
        )
        hits = execute_rule_based_path(request.units, rules)
        assert hits == [], "E2E 台词不得命中需人工裁决的规则项，否则链路必须先走人工裁决"
        return CultureCheckResult(
            run_id="crun_e2e_0001",
            task_ref=request.task_ref,
            task_revision=request.task_revision,
            checked_unit_ids=[unit.unit_id for unit in request.units],
            coverage_limitations=[
                "E2E：模型语境路径未启用（零外呼），仅确定性规则路径；不代表真实文化检测质量"
            ],
            manifest={
                "pipeline": "deterministic_rule_path_only",
                "model_used": False,
                "model_invocation": "NOT_INVOKED",
                "token_used": 0,
                "external_api_calls": 0,
                "translation_refs": {
                    unit.unit_id: {
                        "translation_id": unit.translation_id,
                        "revision": unit.translation_revision,
                    }
                    for unit in request.units
                },
            },
        )

    monkeypatch.setattr(culture_router, "execute_culture_check", deterministic_check)


# ==========================================
# 辅助：① 收料 → ② 源稿确认 → ③ 初翻确认
# ==========================================

def seed_ingest_to_confirmed_translation(client, database):
    created = client.post(
        "/api/v1/tasks", json={"request_key": uuid.uuid4().hex, "task_type": "source_only"}
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["task_id"]

    with database.transaction() as conn:
        conn.execute(
            "INSERT INTO source_transcripts (transcript_id,task_id,revision,status,source_language,"
            "created_at,updated_at) VALUES (?,?,1,'AI_PROPOSED','zh-CN','SIMULATED_ASR','SIMULATED_ASR')",
            (f"tr-{task_id}", task_id),
        )
        for order, unit in enumerate(PIPELINE_UNITS, start=1):
            start_ms = int(unit["start"] * 1000)
            end_ms = int(unit["end"] * 1000)
            conn.execute(
                "INSERT INTO source_utterances (unit_id,task_id,transcript_revision,unit_index,text,"
                "source_spans,start_ms,end_ms,status,created_at,updated_at) "
                "VALUES (?,?,1,?,?,'[]',?,?,'AI_PROPOSED','SIMULATED_ASR','SIMULATED_ASR')",
                (unit["unit_id"], task_id, order, unit["source"], start_ms, end_ms),
            )
            conn.execute(
                "INSERT INTO translations (translation_id,task_id,unit_id,source_revision,"
                "translation_revision,target_language,target_market,text,status,created_at,updated_at) "
                "VALUES (?,?,?,1,1,'es-MX','MX',?,'AI_PROPOSED','SIMULATED_MT','SIMULATED_MT')",
                (f"tl-{task_id}-{unit['unit_id']}", task_id, unit["unit_id"], unit["draft"]),
            )

    confirmed_source = client.post(
        f"/api/v1/tasks/{task_id}/source-transcript/confirm", json={"expected_revision": 1}
    )
    assert confirmed_source.status_code == 200, confirmed_source.text

    edited = client.patch(
        f"/api/v1/tasks/{task_id}/translations/u002",
        json={"source_revision": 1, "expected_revision": 1, "text": PIPELINE_UNITS[1]["final"]},
    )
    assert edited.status_code == 200, edited.text

    expected_revisions = {"u001": 1, "u002": 2, "u003": 1}
    confirmed_translation = client.post(
        f"/api/v1/tasks/{task_id}/translations/confirm-all",
        json={"source_revision": 1, "expected_revisions": expected_revisions},
    )
    assert confirmed_translation.status_code == 200, confirmed_translation.text

    rows = client.get(f"/api/v1/tasks/{task_id}/translations").json()["translations"]
    assert {row["unit_id"] for row in rows} == {unit["unit_id"] for unit in PIPELINE_UNITS}
    assert all(row["status"] == "CONFIRMED" and row["confirmed_by"] for row in rows)
    texts = {row["unit_id"]: row["text"] for row in rows}
    revisions = {row["unit_id"]: row["translation_revision"] for row in rows}
    # 译文修订标识参与五维签发哈希：必须是真实确认后的修订号，不得凭空编造。
    translation_revision = "src1:" + ",".join(
        f"{unit['unit_id']}={revisions[unit['unit_id']]}" for unit in PIPELINE_UNITS
    )

    cues = [
        {
            "index": order,
            "start_time": unit["start"],
            "end_time": unit["end"],
            "text": texts[unit["unit_id"]],
        }
        for order, unit in enumerate(PIPELINE_UNITS, start=1)
    ]
    return {
        "task_id": task_id,
        "texts": texts,
        "revisions": revisions,
        "translation_revision": translation_revision,
        "cues": cues,
    }


# ==========================================
# 1. 六段式主链路
# ==========================================

def test_e2e_six_stage_happy_path(auth_client, isolated_test_env, monkeypatch):
    # Intake/ASR/MT data are explicit SIMULATED fixtures; confirmation/edit endpoints are real.
    from types import SimpleNamespace
    from code.backend.modules.compliance import integration
    pipeline=seed_ingest_to_confirmed_translation(auth_client,isolated_test_env['db']);task=pipeline['task_id'];database=isolated_test_env['db']
    with database.transaction() as c:
        c.execute("UPDATE tasks SET task_status='READY',confirmed_by='SIMULATED_INTAKE' WHERE task_id=?",(task,))
        run_id='SIMULATED_E2E_MT';manifest=json.dumps({'model_id':'SIMULATED','prompt_hash':'fixture','input_hash':'fixture'})
        c.execute("INSERT INTO runs(run_id,task_id,task_revision,trace_id,authorization_ref,permission_check_ref,module,input_refs,input_revision,idempotency_key,attempt_no,attempts,run_status,context_manifest,manifest_hash,steps,started_at,usage,controls,output_refs,created_at,created_by) VALUES (?,?,1,'t','SIMULATED','p','translation','[]',1,'i',1,'[]','SUCCEEDED',?,'h','[]','SIMULATED','{}','{}','[]','SIMULATED','SIMULATED')",(run_id,task,manifest))
        c.execute('UPDATE translations SET run_id=? WHERE task_id=?',(run_id,task))
    class Registry:
        def retrieve_applicable_rules(self,**kwargs):return [SimpleNamespace(rule_id='SIMULATED_RULE',rule_version='v1')]
    monkeypatch.setattr(integration,'default_registry',Registry())
    calls=[]
    def complete_fixture(request):
        calls.append(request)
        return CultureCheckResult(run_id='SIMULATED_E2E_CULTURE',task_ref=task,task_revision=1,checked_unit_ids=[u.unit_id for u in request.units],coverage_limitations=[],manifest={'model_used':False,'external_api_calls':0,'model_id':'SIMULATED','prompt_hash':'fixture','input_hash':'fixture','rule_versions':{'SIMULATED_RULE':'v1'},'translation_refs':{u.unit_id:{'translation_id':u.translation_id,'revision':u.translation_revision} for u in request.units}})
    monkeypatch.setattr(culture_router,'execute_culture_check',complete_fixture)
    assert auth_client.post(f'/api/v1/culture/tasks/{task}/check').status_code==200
    assert [u.target_text for u in calls[0].units]==[pipeline['texts'][u['unit_id']] for u in PIPELINE_UNITS]
    for stage,action in [('units','convert'),('oral','review')]:
        response=auth_client.post(f'/api/v1/{stage}/tasks/{task}/{action}',json={'expected_task_revision':1})
        assert response.status_code==200,response.text
        assert response.json()['manifest']['model_used'] is False
        if stage=='units':
            assert {candidate['unit_id'] for candidate in response.json()['candidates']}=={'u001','u002','u003'}
            for candidate in response.json()['candidates']:
                assert candidate['raw_text'] in candidate['display_text']
                assert candidate['reverse_verification']['passed'] is True
    before=auth_client.get(f'/api/v1/tasks/{task}/translations').json()['translations']
    assert {row['unit_id']:row['text'] for row in before}==pipeline['texts']
    base=f'/api/v1/compliance/tasks/{task}'
    response=auth_client.post(base+'/validate-and-export',json={'expected_task_revision':1,'format':'srt'})
    assert response.status_code==200,response.text
    artifact=response.json();assert artifact['status']=='VALIDATED' and 'content' not in artifact
    assert artifact['round_trip_result']['is_valid'] is True
    assert auth_client.get(base+'/artifact').status_code==403
    body={'artifact_id':artifact['artifact_id'],'expected_revision':artifact['manifest']['translation_revision']}
    assert auth_client.post(base+'/signoff',json=body).status_code==403 # media_operator
    reviewer=register_local_operator(display_name='SIMULATED终审员',role='reviewer')
    auth_client.cookies.set('session_token',reviewer['session_token'])
    signed=auth_client.post(base+'/signoff',json=body);assert signed.status_code==200,signed.text
    final=auth_client.get(base+'/artifact');assert final.status_code==200
    package=final.json();assert package['status']=='PUBLISH_READY'
    assert package['signoff']['signer_id']==reviewer['operator_id']
    assert sha256_text(package['content'])==package['artifact_sha256']
    parsed=parse_subtitle(package['content'],'srt');assert [cue.text for cue in parsed]==[pipeline['texts'][u['unit_id']] for u in PIPELINE_UNITS]
    assert auth_client.post(base+'/signoff',json=body).status_code==409

# ==========================================
# 2. 质检阻断与零泄漏
# ==========================================

def test_e2e_compliance_qc_block_and_no_leak(auth_client, isolated_test_env):
    from tests.integration.test_downstream_trust import prepare,client_for
    database=isolated_test_env['db'];task=prepare(auth_client,database);client=client_for(database);base=f'/api/v1/compliance/tasks/{task}'
    # Invalid current server time is rejected, never replaced by client-supplied timing.
    with database.transaction() as c:c.execute('UPDATE source_utterances SET start_ms=2000,end_ms=1000')
    assert client.post(base+'/validate-and-export',json={'expected_task_revision':1}).status_code==409
    with database.transaction() as c:c.execute("UPDATE source_utterances SET start_ms=0,end_ms=1000");c.execute("UPDATE translations SET text=?",('A'*60,))
    response=client.post(base+'/validate-and-export',json={'expected_task_revision':1})
    assert response.status_code==200,response.text
    artifact=response.json();assert artifact['status']=='QC_FAILED' and 'content' not in artifact
    assert artifact['validation_result']['is_valid'] is False
    assert 'CPS_EXCEEDED' in {i['issue_type'] for i in artifact['validation_result']['issues']}
    assert client.post(base+'/signoff',json={'artifact_id':artifact['artifact_id'],'expected_revision':artifact['manifest']['translation_revision']}).status_code==409
    assert client.get(base+'/artifact').status_code==403
    assert client.post(base+'/validate-and-export',json={'cues':[],'expected_task_revision':1}).status_code==422

# ==========================================
# 3. 机器代签与篡改验真
# ==========================================

def test_e2e_tamper_and_machine_signoff_rejected(auth_client, isolated_test_env):
    from tests.integration.test_downstream_trust import prepare,client_for
    database=isolated_test_env['db'];task=prepare(auth_client,database);client=client_for(database);base=f'/api/v1/compliance/tasks/{task}'
    response=client.post(base+'/validate-and-export',json={'expected_task_revision':1,'format':'vtt'});assert response.status_code==200
    artifact=response.json();body={'artifact_id':artifact['artifact_id'],'expected_revision':artifact['manifest']['translation_revision']}
    assert client.post(base+'/signoff',json={**body,'expected_revision':'forged'}).status_code==409
    assert client.post(base+'/signoff',json={**body,'artifact':{'content':'not even SRT'}}).status_code==422
    assert client.post(base+'/signoff',json={**body,'signer_id':'imposter'}).status_code==422
    from code.backend.shared.models import ActorContext
    from code.backend.modules.compliance.router import create_compliance_router,SqliteArtifactStore
    from code.backend.modules.compliance.integration import WorkflowComplianceAdapter
    from tests.integration.test_downstream_trust import Registry
    machine=FastAPI();machine.include_router(create_compliance_router(get_actor_context=lambda request:ActorContext(actor_id='service',actor_type='service_actor',actor_role='reviewer',allowed=True),storage_adapter=SqliteArtifactStore(database),task_adapter=WorkflowComplianceAdapter(database,Registry())))
    assert TestClient(machine).post(base+'/signoff',json=body).status_code==403

# ==========================================
# 4. 鉴权 Fail-Closed
# ==========================================

def _protected_requests(task_id="T-E2E"):
    return [
        ("post", f"/api/v1/units/tasks/{task_id}/convert", {"units": [{"unit_id": "u1", "target_text": "Hola."}]}),
        ("post", f"/api/v1/oral/tasks/{task_id}/review", {"request_id": "r1", "segments": [
            {"segment_id": "s1", "text": "Hola.", "start_time": 0.0, "end_time": 1.0}]}),
        ("post", f"/api/v1/compliance/tasks/{task_id}/validate-and-export", {"cues": [
            {"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "Hola."}]}),
        ("post", f"/api/v1/compliance/tasks/{task_id}/signoff", {
            "artifact": {"artifact_id": "a1", "format": "srt", "content": "", "status": "DRAFT",
                         "artifact_sha256": sha256_text("")},
            "signoff": {"task_id": task_id, "translation_revision": "tr-1", "rule_version": "rv-1",
                        "validation_id": "val-1", "artifact_sha256": sha256_text(""),
                        "signoff_hash": sha256_text("x"), "signer_id": "op_1", "signed_at": "2026-10-22T00:00:00+00:00"},
        }),
        ("get", f"/api/v1/compliance/tasks/{task_id}/artifact", None),
    ]


def test_e2e_unauthorized_access_fail_closed(unauth_client, isolated_test_env):
    # 1) 无会话凭证 → 401（不得回落到匿名计算）
    for method, url, body in _protected_requests():
        response = getattr(unauth_client, method)(url, json=body) if body is not None else unauth_client.get(url)
        assert response.status_code == 401, f"{method.upper()} {url} 未鉴权却返回 {response.status_code}"

    # 2) 伪造身份头不得换取会话
    spoofed = unauth_client.post(
        "/api/v1/units/tasks/T-SPOOF/convert",
        json={"units": [{"unit_id": "u1", "target_text": "Hola."}]},
        headers={"X-Actor-Id": "spoof", "X-Actor-Role": "reviewer", "X-Actor-Type": "human"},
    )
    assert spoofed.status_code == 401

    # 3) 有效会话但主体受限（human_denied）→ 403
    denied = register_local_operator(display_name="受限操作员", role="human_denied")
    unauth_client.cookies.set("session_token", denied["session_token"])
    for method, url, body in _protected_requests():
        response = getattr(unauth_client, method)(url, json=body) if body is not None else unauth_client.get(url)
        assert response.status_code == 403, f"{method.upper()} {url} 受限主体却返回 {response.status_code}"


def test_e2e_routers_fail_closed_without_auth_adapter():
    """未注入认证适配器 → 503：新路由默认挂载面绝不放行。"""
    bare = FastAPI()
    bare.include_router(create_unit_format_router())
    bare.include_router(create_oral_review_router())
    bare.include_router(create_compliance_router())
    with TestClient(bare) as client:
        for method, url, body in _protected_requests():
            response = getattr(client, method)(url, json=body) if body is not None else client.get(url)
            assert response.status_code == 503, f"{method.upper()} {url} 缺认证适配器却返回 {response.status_code}"


def test_e2e_artifact_store_is_task_scoped():
    """进程内产物存储按任务隔离：不得跨任务读出他任务产物。"""
    from code.backend.modules.compliance.handler import validate_and_export_artifact

    artifact = validate_and_export_artifact(
        task_id="task-a",
        translation_revision="tr-1",
        rule_version=COMPLIANCE_RULE_VERSION,
        cues=[SubtitleCue(index=1, start_time=0.0, end_time=2.0, text="Hola.")],
    )
    store = InMemoryArtifactStore()
    assert store.get("task-a") is None
    store.save("task-a", artifact)
    stored = store.get("task-a")
    assert stored is not None and stored.artifact_id == artifact.artifact_id
    assert store.get("task-a", artifact.artifact_id) is not None
    assert store.get("task-b") is None
    assert store.get("task-b", artifact.artifact_id) is None

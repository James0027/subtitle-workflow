"""Main-app mounting regression with isolated DB and mocked model output."""
from code.backend.modules.culture_check.contract import CultureCheckResult, CultureCheckIssue, TriggerSpan, ConfidenceDetail
from code.backend.modules.culture_check import router
from code.backend.main import app
from code.backend.modules.translation.tests.test_repair_regressions import seed

# 正式应用对外暴露的文化检测路由白名单（任务范围检测 + 人工裁决）。
# 任何新增/旁路路由都必须同步本用例，防止无鉴权或模拟入口被挂进正式应用。
CULTURE_SURFACE = {
    "/api/v1/culture/sources": ["GET"],
    "/api/v1/culture/rules": ["GET"],
    "/api/v1/culture/cases": ["GET"],
    "/api/v1/culture/tasks/{task_id}/check": ["POST"],
    "/api/v1/culture/runs/{run_id}": ["GET"],
    "/api/v1/culture/tasks/{task_id}/issues": ["GET"],
    "/api/v1/culture/issues/{issue_id}/decision": ["POST"],
    "/api/v1/culture/tasks/{task_id}/units/{unit_id}/rollback": ["POST"],
    "/api/v1/culture/tasks/{task_id}/metrics": ["GET"],
    "/api/v1/culture/tasks/{task_id}/latest-run": ["GET"],
}


def test_main_culture_gates_and_human_decision(isolated_test_env,auth_client,monkeypatch):
    database=isolated_test_env['db']; task=seed(auth_client,database)
    assert auth_client.post(f'/api/v1/culture/tasks/{task}/check').status_code==409
    with database.transaction() as c:
        for i in (1,2):
            c.execute("INSERT INTO translations(translation_id,task_id,unit_id,source_revision,translation_revision,target_language,target_market,text,status,confirmed_by,created_at,updated_at) VALUES (?,?,?,1,1,'es-MX','MX','Hola.','CONFIRMED','SIMULATED','SIMULATED','SIMULATED')",(f't{i}',task,f'u{i}'))
    calls=[]
    def check(req):
        calls.append(req)
        return CultureCheckResult(run_id='SIMULATED_RUN',task_ref=task,task_revision=1,checked_unit_ids=['u1','u2'],coverage_limitations=['SIMULATED，不代表真实检测'],manifest={'translation_refs':{u.unit_id:{'translation_id':u.translation_id,'revision':u.translation_revision} for u in req.units}},issues=[CultureCheckIssue(issue_id='SIMULATED_ISSUE',unit_id='u1',category='local_taboo',trigger_spans=[TriggerSpan(target_span='Hola.')],severity_proposal='P2',confidence=ConfidenceDetail(basis='SIMULATED'),evidence_status='insufficient',explanation='SIMULATED，请结合场景核对语气。',suggested_action='contextual_review')])
    monkeypatch.setattr(router,'execute_culture_check',check)
    result=auth_client.post(f'/api/v1/culture/tasks/{task}/check')
    assert result.status_code==200,result.text
    assert calls[0].units[0].target_text=='Hola.'
    latest=auth_client.get(f'/api/v1/culture/tasks/{task}/latest-run');assert latest.status_code==200
    assert latest.json()['run_id']=='SIMULATED_RUN'
    issues=auth_client.get(f'/api/v1/culture/tasks/{task}/issues').json()
    assert issues[0]['stale'] is False
    assert auth_client.post('/api/v1/culture/issues/SIMULATED_ISSUE/decision',json={'expected_revision':99,'decision_action':'accept'}).status_code==409
    assert auth_client.post('/api/v1/culture/issues/SIMULATED_ISSUE/decision',json={'expected_revision':1,'decision_action':'accept','actor_id':'spoof'}).status_code==422
    assert auth_client.post('/api/v1/culture/issues/SIMULATED_ISSUE/decision',json={'expected_revision':1,'decision_action':'accept'}).status_code==200
    with database.transaction() as c: c.execute("UPDATE translations SET translation_revision=2 WHERE translation_id='t1'")
    assert auth_client.get(f'/api/v1/culture/tasks/{task}/issues').json()[0]['stale'] is True


def test_mounted_culture_surface_is_the_task_scoped_allowlist():
    """正式应用挂载的文化路由必须与白名单完全一致（无裸输入、无模拟、无调试旁路）。"""
    # 该 FastAPI 版本把 include_router 记为 _IncludedRouter 惰性展开，故用 OpenAPI 取真实挂载面。
    schema = app.openapi()
    mounted = {
        path: sorted(method.upper() for method in operations)
        for path, operations in schema["paths"].items()
        if path.startswith("/api/v1/culture")
    }
    assert mounted == CULTURE_SURFACE, f"文化路由挂载面发生变化: {mounted}"


def test_mounted_culture_routes_fail_closed_without_session(unauth_client):
    """缺少主体上下文时必须 401，且不得回落到任何匿名/模拟旁路。"""
    for path in (
        "/sources",
        "/rules",
        "/cases",
        "/runs/SIMULATED_RUN",
        "/tasks/SIMULATED_TASK/issues",
        "/tasks/SIMULATED_TASK/metrics",
        "/tasks/SIMULATED_TASK/latest-run",
    ):
        response = unauth_client.get(f"/api/v1/culture{path}")
        assert response.status_code == 401, f"{path} 未鉴权却返回 {response.status_code}"
    assert unauth_client.post("/api/v1/culture/tasks/SIMULATED_TASK/check").status_code == 401
    assert unauth_client.post(
        "/api/v1/culture/issues/SIMULATED_ISSUE/decision",
        json={"expected_revision": 1, "decision_action": "accept"},
    ).status_code == 401
    assert unauth_client.post(
        "/api/v1/culture/tasks/SIMULATED_TASK/units/u1/rollback",
        json={"expected_revision": 1, "target_revision": 1, "reason": "核对"},
    ).status_code == 401
    # 客户端自报身份头不得换取会话
    spoofed = unauth_client.get(
        "/api/v1/culture/sources",
        headers={"X-Actor-Id": "spoof", "X-Actor-Role": "culture_senior", "X-Actor-Type": "human"},
    )
    assert spoofed.status_code == 401


def test_mounted_culture_check_and_decisions_expose_no_simulation_fields():
    """检测入口不接受原始输入或 simulate 开关；裁决请求体不接受客户端自报身份。"""
    schema = app.openapi()
    check = schema["paths"]["/api/v1/culture/tasks/{task_id}/check"]["post"]
    assert "requestBody" not in check, "正式检测入口不得接受原始输入/simulate 请求体"
    assert all(param.get("in") != "query" for param in check.get("parameters", []))
    for path, methods in schema["paths"].items():
        if not path.startswith("/api/v1/culture"):
            continue
        for operation in methods.values():
            body = operation.get("requestBody") or {}
            properties = (
                body.get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("properties", {})
            )
            assert "simulate" not in properties, f"{path} 暴露了 simulate 旁路"
            assert "actor_id" not in properties, f"{path} 接受客户端自报主体"

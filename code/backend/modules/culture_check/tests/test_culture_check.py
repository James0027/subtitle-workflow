import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from code.backend.db import Database
from code.backend.modules.culture_check.contract import (
    CultureCaseItem,
    CultureCheckIssue,
    CultureCheckRequest,
    CultureCheckResult,
    CultureRuleItem,
    CultureSourceRegistryItem,
    CultureUnitInput,
    HumanIssueDecisionRequest,
    RollbackRequest,
    TriggerSpan,
    UncheckedUnit,
)
from code.backend.modules.culture_check.handler import (
    build_prompts,
    execute_culture_check,
    execute_rule_based_path,
    mock_culture_check_execution,
)
from code.backend.modules.culture_check.registry import (
    CultureRegistry,
    DEFAULT_SOURCES,
    DEFAULT_RULES,
)
from code.backend.modules.culture_check.repository import (
    CultureRepository,
)
from code.backend.modules.culture_check.router import (
    create_culture_router,
)
from code.backend.modules.culture_check.validator import (
    CultureValidationError,
    build_evidence_allowlist,
    compute_ranking_score,
    validate_and_process_culture_issues,
)


def _test_registry():
    registry = CultureRegistry()
    registry._rules = {r.rule_id:r.model_copy(update={"status":"ACTIVE","review_status":"VERIFIED"}) for r in DEFAULT_RULES if r.rule_id != "R-MX-UNVERIFIED-01"}
    return registry


@pytest.fixture
def isolated_db(tmp_path):
    """创建完全隔离的临时 SQLite 数据库用于文化模块测试，严禁碰正式 workflow.db"""
    db_file = tmp_path / "test_culture_isolated.db"
    return Database(db_path=db_file)


@pytest.fixture
def isolated_culture_repo(isolated_db):
    """显式注入 Database 实例构造仓库"""
    return CultureRepository(database=isolated_db)


# ==========================================
# 1. 契约模型严格性与模型/服务端字段分离
# ==========================================

def test_contract_extra_forbid_and_strict_types():
    """验证 Pydantic 模型 extra='forbid' 拦截额外未知字段与客户端伪造身份"""
    # 1. 请求体若包含额外未知字段必须报错拦截
    with pytest.raises(Exception):
        CultureCheckRequest(
            task_ref="TSK-01",
            task_revision=1,
            target_market="MX",
            units=[CultureUnitInput(unit_id="u_1", source_text="a", target_text="b")],
            unexpected_field="malicious_payload",  # extra field forbidden
        )

    # 2. 人工裁决请求体严禁自报 actor_id 或 actor_role（必须由服务端安全上下文注入）
    with pytest.raises(Exception):
        HumanIssueDecisionRequest(
            expected_revision=1,
            decision_action="accept",
            actor_id="hacker_operator",  # 严禁在 Body 中自报身份
        )

    # 3. 校验置信度校准字段必须为 Literal[None]
    req = CultureCheckRequest(
        task_ref="TSK-01",
        task_revision=1,
        target_market="MX",
        units=[CultureUnitInput(unit_id="u_1", source_text="a", target_text="b")],
    )
    assert req.schema_version == "1.0.0"


def test_schema_example_files_audit():
    """审计 rules/examples 下 5 份样例文档的合法性与预期拦截行为"""
    examples_dir = Path(__file__).resolve().parent.parent / "rules" / "examples"

    valid_file = examples_dir / "valid_culture_check.json"
    assert valid_file.exists()
    valid_data = json.loads(valid_file.read_text(encoding="utf-8"))
    assert valid_data["unit_id"] == "u_001"
    assert "ranking_score" not in valid_data  # 纯模型输出严禁包含服务端打分
    assert "status" not in valid_data         # 纯模型输出严禁包含人机状态

    p0_file = examples_dir / "invalid_missing_evidence_p0.json"
    p0_data = json.loads(p0_file.read_text(encoding="utf-8"))
    assert p0_data["severity_proposal"] == "P0"
    assert p0_data["evidence_status"] == "insufficient"

    fake_rule_file = examples_dir / "invalid_hallucinated_rule.json"
    fake_rule_data = json.loads(fake_rule_file.read_text(encoding="utf-8"))
    assert "HALLUCINATED" in fake_rule_data["rule_refs"][0]

    mismatch_file = examples_dir / "invalid_span_mismatch.json"
    mismatch_data = json.loads(mismatch_file.read_text(encoding="utf-8"))
    assert mismatch_data["trigger_spans"][0]["target_span"] == "palabra inexistente en subtitulo"

    factor_file = examples_dir / "invalid_factor_out_of_range.json"
    factor_data = json.loads(factor_file.read_text(encoding="utf-8"))
    assert factor_data["impact_level"] == 5


# ==========================================
# 2. 严格引用、跨度字符切片匹配与互斥去重覆盖校验
# ==========================================

def test_compute_ranking_score_strict_types():
    """验证排序打分拒收 bool/float/str，必须为严格 int 且属于 1..3"""
    # 正常打分
    assert compute_ranking_score(1, 1, 1) == 1
    assert compute_ranking_score(2, 2, 2) == 8
    assert compute_ranking_score(3, 3, 3) == 27
    assert compute_ranking_score(None, 2, 2) is None

    # 严禁 bool (Python 中 bool 是 int 的子类)
    with pytest.raises(CultureValidationError, match="必须为严格 int 类型"):
        compute_ranking_score(True, 2, 2)

    # 严禁 float
    with pytest.raises(CultureValidationError, match="必须为严格 int 类型"):
        compute_ranking_score(2.0, 2, 2)

    # 严禁 str
    with pytest.raises(CultureValidationError, match="必须为严格 int 类型"):
        compute_ranking_score("2", 2, 2)

    # 严禁超出 1..3
    with pytest.raises(CultureValidationError, match="值必须在 1..3 之间"):
        compute_ranking_score(4, 2, 1)


def test_validator_active_case_ids_empty_rejects_any_case_refs():
    """验证当 active_case_ids 为空集合时，仍必须拒绝包含任何 case_refs 的检出项"""
    req = CultureCheckRequest(
        task_ref="TSK-C-01",
        task_revision=1,
        target_market="MX",
        units=[CultureUnitInput(unit_id="u_001", source_text="你好", target_text="Hola")],
    )
    reg = _test_registry()
    rules = reg.retrieve_applicable_rules("MX", only_active=True)

    issues = [{
        "unit_id": "u_001",
        "category": "other",
        "trigger_spans": [{"source_span": "你好", "target_span": "Hola"}],
        "severity_proposal": "P2",
        "confidence_raw": 0.5,
        "confidence_basis": "测试",
        "rule_refs": ["R-MX-TABOO-01"],
        "case_refs": ["MX-CASE-01"],  # 提供了案例引用
        "evidence_refs": ["R-MX-TABOO-01"],
        "evidence_status": "sufficient",
        "explanation": "测试",
        "suggested_action": "modify_dialogue",
    }]

    # 当 active_case_ids 为空集合时，必须拒绝
    with pytest.raises(CultureValidationError, match="引用了不存在或未激活的案例 ID"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=issues,
            checked_unit_ids=["u_001"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids=set(),  # 空案例集
        )


def test_validator_evidence_refs_allowlist_enforcement():
    """验证 evidence_refs 必须严格属于根据有效规则与输入构建的 allowlist，禁止虚构"""
    req = CultureCheckRequest(
        task_ref="TSK-EV-01",
        task_revision=1,
        target_market="MX",
        units=[CultureUnitInput(unit_id="u_001", source_text="你好", target_text="Hola")],
    )
    reg = _test_registry()
    rules = reg.retrieve_applicable_rules("MX", only_active=True)

    fake_ev_issues = [{
        "unit_id": "u_001",
        "category": "discrimination",
        "trigger_spans": [{"source_span": "你好", "target_span": "Hola"}],
        "severity_proposal": "P1",
        "confidence_raw": 0.8,
        "confidence_basis": "测试",
        "rule_refs": ["R-MX-DISCRIM-01"],
        "evidence_refs": ["FAKE-EVIDENCE-LAW-999"],  # 虚假证据
        "evidence_status": "sufficient",
        "explanation": "测试",
        "suggested_action": "modify_dialogue",
    }]

    with pytest.raises(CultureValidationError, match="不在输入允许范围的证据 ID"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=fake_ev_issues,
            checked_unit_ids=["u_001"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids={"MX-CASE-01"},
        )


def test_validator_coverage_mutually_exclusive_and_deduplicated():
    """验证 checked_unit_ids 与 unchecked_units 必须去重、互斥且全量覆盖"""
    req = CultureCheckRequest(
        task_ref="TSK-COV-01",
        task_revision=1,
        target_market="MX",
        units=[
            CultureUnitInput(unit_id="u_001", source_text="台词1", target_text="Texto 1"),
            CultureUnitInput(unit_id="u_002", source_text="台词2", target_text="Texto 2"),
        ],
    )
    reg = _test_registry()
    rules = reg.retrieve_applicable_rules("MX", only_active=True)

    # 重复 checked ID 拦截
    with pytest.raises(CultureValidationError, match="列表中存在重复单元 ID"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=[],
            checked_unit_ids=["u_001", "u_001", "u_002"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids=set(),
        )

    # checked 与 unchecked 重叠拦截 (互斥)
    with pytest.raises(CultureValidationError, match="存在重叠单元 ID"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=[],
            checked_unit_ids=["u_001"],
            unchecked_units=[UncheckedUnit(unit_id="u_001", reason="跳过")],
            active_rules=rules,
            active_case_ids=set(),
        )

    # 包含请求未定义的外部 ID 拦截
    with pytest.raises(CultureValidationError, match="包含了请求中未定义的单元 ID"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=[],
            checked_unit_ids=["u_001", "u_002", "u_UNKNOWN"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids=set(),
        )


def test_validator_start_end_char_exact_text_matching():
    """验证字符切片 start_char/end_char 若提供，必须合法且 target_text[start:end] 必须精确匹配 target_span"""
    req = CultureCheckRequest(
        task_ref="TSK-SLICE-01",
        task_revision=1,
        target_market="MX",
        units=[
            CultureUnitInput(
                unit_id="u_001",
                source_text="不要吸烟",
                target_text="No fumes cigarro aquí",  # len = 21
            )
        ],
    )
    reg = _test_registry()
    rules = reg.retrieve_applicable_rules("MX", only_active=True)

    # 切片与 target_span 不匹配报错
    mismatch_issues = [{
        "unit_id": "u_001",
        "category": "legal_platform",
        "trigger_spans": [{
            "source_span": "吸烟",
            "target_span": "fumes",
            "start_char": 0,
            "end_char": 2,  # target_text[0:2] 是 "No" != "fumes"
        }],
        "severity_proposal": "P2",
        "confidence_raw": 0.8,
        "confidence_basis": "测试",
        "rule_refs": ["R-MX-CINEMA-01"],
        "evidence_refs": ["MX-OFF-01-TRANS-4"],
        "evidence_status": "sufficient",
        "explanation": "测试",
        "suggested_action": "modify_dialogue",
    }]

    with pytest.raises(CultureValidationError, match="与 target_span 'fumes' 不匹配"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=mismatch_issues,
            checked_unit_ids=["u_001"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids=set(),
        )

    # 切片越界报错
    out_of_bounds_issues = [{
        "unit_id": "u_001",
        "category": "legal_platform",
        "trigger_spans": [{
            "source_span": "吸烟",
            "target_span": "fumes",
            "start_char": 10,
            "end_char": 50,  # 越界
        }],
        "severity_proposal": "P2",
        "confidence_raw": 0.8,
        "confidence_basis": "测试",
        "rule_refs": ["R-MX-CINEMA-01"],
        "evidence_refs": ["MX-OFF-01-TRANS-4"],
        "evidence_status": "sufficient",
        "explanation": "测试",
        "suggested_action": "modify_dialogue",
    }]

    with pytest.raises(CultureValidationError, match="超出译文长度"):
        validate_and_process_culture_issues(
            request=req,
            raw_issues=out_of_bounds_issues,
            checked_unit_ids=["u_001"],
            unchecked_units=[],
            active_rules=rules,
            active_case_ids=set(),
        )


# ==========================================
# 3. 缺证据 P0 降待补证 P1 留痕护栏
# ==========================================

def test_missing_evidence_p0_downgraded_to_p1():
    """验证模型提议 P0 但无充分有效证据时，强制降级为 P1 并保留重大说明与打分"""
    req = CultureCheckRequest(
        task_ref="TSK-P0-DOWNGRADE",
        task_revision=1,
        target_market="MX",
        units=[
            CultureUnitInput(
                unit_id="u_001",
                source_text="在这里吸一口",
                target_text="fumar mota aquí",
            )
        ],
    )
    reg = _test_registry()
    rules = reg.retrieve_applicable_rules("MX", only_active=True)

    raw_issues = [{
        "unit_id": "u_001",
        "category": "sex_violence_addiction_ratings",
        "trigger_spans": [{"source_span": "吸一口", "target_span": "mota"}],
        "severity_proposal": "P0",
        "impact_level": 3,
        "occurrence_likelihood": 2,
        "remediation_difficulty": 1,
        "confidence_raw": 0.95,
        "confidence_basis": "模型直觉判断",
        "rule_refs": ["R-MX-CINEMA-01"],
        "evidence_refs": [],  # 缺失证据引用
        "evidence_status": "insufficient",
        "explanation": "吸食软性毒品涉及高风险",
        "suggested_action": "modify_dialogue",
    }]

    processed = validate_and_process_culture_issues(
        request=req,
        raw_issues=raw_issues,
        checked_unit_ids=["u_001"],
        unchecked_units=[],
        active_rules=rules,
        active_case_ids=set(),
    )

    assert len(processed) == 1
    issue = processed[0]
    assert issue.severity_proposal == "P1"
    assert issue.downgraded_from_p0 is True
    assert "RULE-CULT-001" in issue.downgrade_reason
    assert issue.impact_level == 3
    assert issue.ranking_score == 6


# ==========================================
# 4. 显式 DB 注入仓库与既有事件复用 (run.finished, review.decided, review.reverted)
# ==========================================

def test_repository_explicit_db_injection_and_existing_event_reuse(isolated_culture_repo, monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "TEST_MODE", True)
    """
    验证：
    1. 仓库显式通过构造器注入 Database 实例，不建平行译文表。
    2. 人工裁决与回滚复用系统全局 events 表（run.finished, review.decided, review.reverted）。
    """
    repo = isolated_culture_repo
    task_id = "TSK-EVENT-REUSE-01"
    unit_id = "u_001"

    req = CultureCheckRequest(
        task_ref=task_id,
        task_revision=1,
        target_market="MX",
        units=[
            CultureUnitInput(
                unit_id=unit_id,
                translation_id="test_translation", translation_revision=1,
                source_text="那个土包子下等人",
                target_text="ese indio mugroso",
            )
        ],
        simulate=True,
    )
    result = execute_culture_check(req, registry=_test_registry())
    repo.save_check_result(result, actor_id="culture_worker", actor_role="service_worker")

    # 1. 验证 run.finished 事件写入既有 events 表
    events = repo.get_events(task_id=task_id)
    event_types = [e["event_type"] for e in events]
    assert "run.finished" in event_types

    issues = repo.list_issues(task_id=task_id)
    assert len(issues) >= 1
    issue_id = issues[0]["issue_id"]

    with repo.db.transaction() as conn:
        conn.execute("INSERT INTO source_transcripts(transcript_id,task_id,revision,status,source_language,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",('test-src',task_id,1,'CONFIRMED','zh-CN','now','now'))
        conn.execute("INSERT INTO translations(translation_id,task_id,unit_id,source_revision,translation_revision,target_language,target_market,text,status,confirmed_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",('test_translation',task_id,unit_id,1,1,'es-MX','MX','test','CONFIRMED','human','now','now'))

    # 2. 人工裁决注入可信主体 -> review.decided 事件
    dec_res = repo.apply_human_decision(
        issue_id=issue_id,
        req=HumanIssueDecisionRequest(expected_revision=1, decision_action="accept"),
        actor_id="trusted_auditor_maria",
        actor_role="culture_auditor",
    )
    assert dec_res["status"] == "CONFIRMED"
    assert dec_res["display_label"] == "AI生成·人工已确认"

    events = repo.get_events(task_id=task_id)
    event_types = [e["event_type"] for e in events]
    assert "review.decided" in event_types

    # 3. 回滚旧版失效 -> review.reverted 事件
    rollback_res = repo.rollback_unit_checks(
        task_id=task_id,
        unit_id=unit_id,
        req=RollbackRequest(expected_revision=1, target_revision=1, reason="重检回滚"),
        actor_id="lead_editor_carlos",
        actor_role="reviewer",
    )
    assert rollback_res["status"] == "CHECKS_INVALIDATED_PENDING_RECHECK"

    events = repo.get_events(task_id=task_id)
    event_types = [e["event_type"] for e in events]
    assert "review.reverted" in event_types

    # 验证旧 Issue 状态被重置为 PENDING_RECHECK
    issues_after = repo.list_issues(task_id=task_id, unit_id=unit_id)
    assert issues_after[0]["status"] == "PENDING_RECHECK"


# ==========================================
# 5. Router 工厂 Fail-Closed 与适配器注入测试
# ==========================================

def test_router_factory_fail_closed_without_adapters(isolated_culture_repo):
    app=FastAPI(); app.include_router(create_culture_router(repository=isolated_culture_repo))
    client=TestClient(app)
    assert client.get("/api/v1/culture/sources").status_code==503
    assert client.post("/api/v1/culture/tasks/TSK-1/check").status_code==503
    assert client.post("/api/v1/culture/check",json={}).status_code==404


def test_router_factory_with_injected_adapters(isolated_culture_repo):
    # Even a valid actor cannot proceed without a trusted source/translation adapter.
    def actor(request): return {"actor_id":"test_human","actor_type":"human","actor_role":"reviewer","allowed":True}
    app=FastAPI(); app.include_router(create_culture_router(repository=isolated_culture_repo,get_actor_context=actor))
    client=TestClient(app)
    assert client.post("/api/v1/culture/tasks/TSK-1/check").status_code==503

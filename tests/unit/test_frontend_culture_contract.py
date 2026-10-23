"""文化检测前端展示与交互契约静态检查。

工单02要求译文复核区域可以触发文化检测并展示结果：风险点按红线(P0)/黄线(P1)/提示(P2)
分组、触发位置高亮、展示依据与修改建议；人工可接受建议改写（生成新 revision）、驳回或
手动编辑，且必须走既有的版本修订契约（expected_revision 乐观锁 + 初翻审阅升版）。

本文件只锁住前端与后端契约的接线点，防止回归；它不证明浏览器端已完成业务验收。
"""

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "code" / "web"
CULTURE_REGION_START = "// Culture candidates never write translations"


def _app_js_text() -> str:
    path = WEB_DIR / "app.js"
    assert path.is_file(), f"未找到前端文件: {path}"
    return path.read_text(encoding="utf-8")


def _index_html_text() -> str:
    path = WEB_DIR / "index.html"
    assert path.is_file(), f"未找到前端页面: {path}"
    return path.read_text(encoding="utf-8")


def _culture_region(text: str) -> str:
    assert CULTURE_REGION_START in text, "文化检测前端区块缺失"
    return text[text.index(CULTURE_REGION_START):]


def test_culture_review_surface_is_mounted_next_to_the_review_area():
    html = _index_html_text()
    for element_id in (
        'id="panelCulture"',
        'id="btnCultureCheck"',
        'id="btnCultureRefresh"',
        'id="btnCultureJump"',
        'id="cultureSummary"',
        'id="cultureIssues"',
        'id="cultureManifest"',
    ):
        assert element_id in html, f"缺少挂载点: {element_id}"
    # 初翻复核区必须能进入文化检测，文化面板必须能回到初翻修改/回滚。
    assert 'id="btnCultureJump"' in html.split('id="panelTranslation"', 1)[1].split('id="panelCulture"', 1)[0]
    assert 'href="#panelTranslation"' in html
    assert "/api/v1/culture/tasks/${taskId}/issues" in _app_js_text()
    assert "/api/v1/culture/tasks/${taskId}/check" in _app_js_text()


def test_risks_are_grouped_by_red_yellow_hint_severity():
    region = _culture_region(_app_js_text())
    assert 'P0:"红线"' in region and 'P1:"黄线"' in region and 'P2:"提示"' in region
    # 固定展示顺序 P0 → P1 → P2 → 未评级，同级按排序值降序
    assert "cultureSeverityOrder = {P0:0,P1:1,P2:2" in region
    assert "cultureSeverityOrder[a.severity_proposal]" in region
    assert "cultureSeverityTag" in region and "P0:\"tag tag-danger\"" in region
    assert 'className = "culture-group"' in region
    assert "红线 P0" in region and "黄线 P1" in region and "提示 P2" in region


def test_trigger_spans_are_highlighted_without_rewriting_text():
    region = _culture_region(_app_js_text())
    assert "issue.trigger_spans" in region
    assert 'document.createElement("mark")' in region
    assert "span.target_span" in region and "span.source_span" in region
    assert "start_char" in region and "end_char" in region


def test_basis_and_suggested_action_are_displayed():
    region = _culture_region(_app_js_text())
    for token in (
        "issue.explanation",
        "issue.evidence_status",
        "issue.rule_refs",
        "issue.case_refs",
        "issue.confidence",
        "issue.suggested_action",
        "issue.suggested_translation",
        "issue.ranking_score",
        "issue.missing_context",
    ):
        assert token in region, f"文化风险展示缺少字段: {token}"


def test_human_decisions_use_pinned_revision_and_server_identity():
    region = _culture_region(_app_js_text())
    # 版本号来源是 run manifest 里钉住的 translation_refs，不写死
    assert "manifest?.translation_refs?.[issue.unit_id]?.revision" in region
    assert "expected_revision:revision" in region
    for hardcoded in ("expected_revision:1", "expected_revision: 1"):
        assert hardcoded not in region, f"文化裁决不得写死版本号: {hardcoded}"
    # 身份由服务端会话注入，前端不得自报 actor
    assert "actor_id" not in region, "文化裁决请求体不得携带客户端自报身份"
    # 依据变化/已裁决的风险不可再次裁决
    assert 'issue.status === "AI_PROPOSED"' in region
    assert "!issue.stale" in region


def test_accept_rewrite_goes_through_existing_revision_contract():
    region = _culture_region(_app_js_text())
    # 采纳建议改写只预填初翻编辑框，升版仍由初翻审阅的 expected_revision 契约发起
    assert "trans_area_${issue.unit_id}" in region
    assert "保存编辑" in region
    # 文化侧不直接改译文、不直接发 edit_accept 决策、不 PATCH 译稿
    assert 'decision_action:"edit_accept"' not in region.replace(" ", "")
    assert 'method:"PATCH"' not in region.replace(" ", "")


def test_culture_calls_never_enable_simulation():
    region = _culture_region(_app_js_text())
    assert "simulate" not in region, "正式前端不得走模拟旁路"
    assert "/api/v1/culture/check" not in region, "文化检测必须是任务范围接口，禁止裸检测入口"

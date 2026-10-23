"""前端 Gate 2 审阅请求的版本字段契约静态检查。

后端 /translations 的确认、编辑、锁定/解锁、回滚、批量确认接口分别使用
TranslationRevisionRequest / EditTranslationRequest / RollbackTranslationRequest /
ConfirmAllTranslationsRequest，source_revision 与 expected_revision(s) 均为必填；
前端一旦漏传，FastAPI 会直接返回 422。本文件用静态检查锁住这五个调用点的字段，
防止回归；它只验证请求体契约，不代表浏览器端已做业务验收。
"""

from pathlib import Path

APP_JS = Path(__file__).resolve().parents[2] / "code" / "web" / "app.js"


def _app_js_text() -> str:
    assert APP_JS.is_file(), f"未找到前端文件: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def _gate2_region(text: str) -> str:
    start = text.index("// Bind action buttons")
    end = text.index('if (btnGenerateTranslation)')
    return text[start:end]


def test_review_requests_send_source_revision_from_loaded_snapshot():
    text = _app_js_text()
    # 版本号来源必须是 GET /translations 的响应，而不是写死常量。
    assert "loadedTranslationSnapshot = {source_revision: data.source_revision" in text
    region = _gate2_region(text)
    assert "const sourceRev = reviewSourceRevision();" in region
    assert "body: JSON.stringify({ source_revision: sourceRev, ...body })" in region


def test_single_unit_review_actions_pass_expected_revision():
    region = _gate2_region(_app_js_text())
    for endpoint in (
        "/translations/${uid}/confirm",
        "/translations/${uid}/lock",
        "/translations/${uid}/unlock",
        "/translations/${uid}/rollback",
    ):
        assert endpoint in region, f"{endpoint} 调用点缺失"
    assert region.count("body: { expected_revision: rev }") == 2, "确认与锁定/解锁必须带 expected_revision"
    assert "body: { expected_revision: curRev, target_revision: targetRev" in region, "回滚必须带 expected_revision 与 target_revision"
    # 编辑保存的 PATCH 请求体必须同时带 expected_revision 与 text。
    assert 'method: "PATCH"' in region
    assert "body: { expected_revision: rev, text: txt }" in region


def test_confirm_all_sends_source_revision_and_expected_revisions():
    text = _app_js_text()
    start = text.index("if (btnConfirmAllTranslations)")
    region = text[start:]
    assert "/translations/confirm-all" in region
    assert "body: JSON.stringify({ source_revision: sourceRev, expected_revisions: expectedRevisions })" in region


def test_review_actions_prompt_refresh_on_409_and_never_hardcode_revision():
    text = _app_js_text()
    region = _gate2_region(text)
    assert "res.status === 409" in region, "409 必须单独提示刷新"
    assert "await loadTranslations();" in region
    for hardcoded in ("source_revision: 1", "expected_revision: 1", "source_revision: 1,"):
        assert hardcoded not in region, f"审阅请求不得写死版本号: {hardcoded}"

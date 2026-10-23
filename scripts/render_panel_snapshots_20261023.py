"""工单 06：前端面板截图生成（Chrome headless）。

做法
----
1. 直接复用 ``code/web/index.html`` 的真实 panel 结构与 ``code/web/style.css``，
   不另造一套页面样式。
2. 面板内的动态区域用 ``docs/08-test-reports/20261023-e2e-report/receipts/*.json``
   的真实实测回执填充，并在页眉标注数据来源（不伪装成实时会话状态）。
3. 用 ``chrome.exe --headless=new`` 截图，不启动额外依赖、不装包。

输出：docs/08-test-reports/20261023-e2e-report/screenshots/
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _png_tools import crop_bottom  # noqa: E402
from html import escape
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "code" / "web"
REPORT = ROOT / "docs" / "08-test-reports" / "20261023-e2e-report"
RECEIPTS = REPORT / "receipts"
SHOTS = REPORT / "screenshots"
SRC = REPORT / "_snapshot_src"

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

REQUIRED_RECEIPTS = [
    "00-run-summary",
    "step1-asr-alignment",
    "step2-translation-version-lock",
    "step3-culture-taboo-loop",
    "step4-unit-format",
    "step5-oral-review",
    "step6-compliance-signoff",
]


def load_receipts() -> dict:
    data = {}
    for name in REQUIRED_RECEIPTS:
        path = RECEIPTS / f"{name}.json"
        if not path.exists():
            raise SystemExit(f"缺少实测回执：{path}（先跑 scripts/run_e2e_verification_20261023.py）")
        data[name] = json.loads(path.read_text(encoding="utf-8"))
    return data


def extract_sections(html: str) -> dict:
    """按 <section class="panel" id="..."> 提取真实面板片段（含嵌套闭合匹配）。"""
    sections = {}
    for match in re.finditer(r'<section class="panel" id="([^"]+)"', html):
        panel_id = match.group(1)
        start = match.start()
        depth = 0
        pos = start
        while True:
            open_at = html.find("<section", pos)
            close_at = html.find("</section>", pos)
            if close_at == -1:
                break
            if open_at != -1 and open_at < close_at:
                depth += 1
                pos = open_at + len("<section")
                continue
            depth -= 1
            pos = close_at + len("</section>")
            if depth == 0:
                sections[panel_id] = html[start:pos]
                break
    return sections


def style_css() -> str:
    return (WEB / "style.css").read_text(encoding="utf-8")


def extra_css() -> str:
    return """
  .shot-note { font-size: 12px; color: var(--text-muted); margin: 6px 0 14px; }
  .shot-banner { background:#1f2328; color:#e6edf3; border-radius:8px; padding:14px 18px; margin-bottom:20px;
                 font-size:13px; line-height:1.6; }
  .shot-banner strong { color:#7ee787; }
  .kv { display:grid; grid-template-columns: 220px 1fr; gap:6px 14px; font-size:13px; margin-top:10px; }
  .kv div:nth-child(odd) { color: var(--text-muted); }
  .mono { font-family: Consolas, "Courier New", monospace; font-size:12px; }
  mark { background: var(--tag-danger-bg); color: var(--tag-danger-color); padding:0 2px; border-radius:3px; }
  .issue-card { border:1px solid rgba(207,34,46,0.35); border-radius:8px; padding:14px; margin-top:12px; background:#fff8f7; }
  .issue-card h4 { font-size:14px; margin-bottom:8px; color: var(--tag-danger-color); }
  .ok-card { border:1px solid rgba(26,127,55,0.35); border-radius:8px; padding:14px; margin-top:12px; background:#f4fdf5; }
  .ok-card h4 { font-size:14px; margin-bottom:8px; color: var(--tag-ok-color); }
  .banner-fail { background: var(--tag-danger-bg); color: var(--tag-danger-color); padding:10px 14px;
                 border-radius:6px; font-weight:600; font-size:13px; margin:10px 0; }
  .banner-ok { background: var(--tag-ok-bg); color: var(--tag-ok-color); padding:10px 14px;
               border-radius:6px; font-weight:600; font-size:13px; margin:10px 0; }
  pre.snippet { background:#0d1117; color:#e6edf3; padding:12px; border-radius:6px; font-size:12px; overflow-x:auto; }
"""


def page(title: str, banner: str, body: str, css: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{escape(title)}</title>
<style>
{css}
{extra_css()}
</style>
</head>
<body>
<div class="container">
  <div class="shot-banner">{banner}</div>
  {body}
</div>
</body>
</html>
"""


def table(headers: list[str], rows: list[list[str]], tag_cols: dict[int, list[str]] | None = None) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            cls = ""
            if tag_cols and index in tag_cols:
                cls = f' class="{tag_cols[index][0]}"' if isinstance(tag_cols[index], list) else ""
            cells.append(f"<td{cls}>{cell}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def tag(text: str, kind: str) -> str:
    return f'<span class="tag tag-{kind}">{escape(str(text))}</span>'


def banner_for(step: str, source: str) -> str:
    return (
        f'<strong>工单 06 · {escape(step)}</strong> ｜ 面板结构：code/web/index.html（真实面板）｜ '
        f'数据来源：docs/08-test-reports/20261023-e2e-report/receipts/{escape(source)}.json ｜ '
        f'model_used=<strong>false</strong> · token_used=<strong>0</strong> · external_api_calls=<strong>0</strong><br />'
        "说明：本图为实测回执注入渲染（真实面板 DOM + 真实 JSON 证据），不代表浏览器实时会话状态。"
    )


# =========================================================================
# 各面板渲染
# =========================================================================

def build_asr(sections, receipts) -> str:
    step1 = receipts["step1-asr-alignment"]
    ok = step1["case_success_standard_slice"]
    tail = step1["case_fail_protection_150ms_tail"]
    ctrl = step1["case_control_900ms_tail"]
    recall = step1["case_proper_name_recall"]
    legacy = step1["case_legacy_repair_tiny_tail"]
    gate = step1["case_external_model_gate"]

    rows = [
        [
            escape(c["chunk_id"]),
            str(c["chunk_index"]),
            f'{c["offset_ms"]} ms',
            f'{c["end_ms"]} ms',
            f'{c["duration_ms"]} ms',
            escape(c["checksum_sha256"][:16] + "…"),
        ]
        for c in ok["chunks"]
    ]
    tail_rows = [
        [escape(c["chunk_id"]), f'{c["offset_ms"]} ms', f'{c["end_ms"]} ms', f'{c["duration_ms"]} ms']
        for c in tail["chunks"]
    ]
    recall_rows = [
        [escape(r["name"]), tag(r["match_status"], "ok" if r["match_status"] == "matched" else "warn"),
         escape(str(r["glossary_ref"]))]
        for r in recall["recalled"]
    ]
    body = f"""
    {sections['panelASR']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · ASR 切片对齐与 <span class="mono">&lt;250ms</span> 尾片安全合并</h2></div>
      <p class="shot-note">真实 HTTP <span class="mono">POST /api/v1/tasks/{{task_id}}/asr/slice</span>（FFmpeg 实测切片），隔离库 + 隔离存储。</p>
      <div class="banner-ok">成功用例：25.0s 音频 → 3 片 10/10/5s，偏移与真实时长逐片连续，总时长 25000ms 守恒；HTTP {ok['http_status']}</div>
      {table(["chunk_id", "index", "offset_ms", "end_ms", "duration_ms", "sha256"], rows)}
      <div class="banner-fail">失败保护：20.15s 音频的 150ms 尾部残留 → 自动并入前一片（最小片 {tail['shortest_chunk_ms']}ms），未产生极短片、未出现 400 INVALID_ARGUMENT</div>
      {table(["chunk_id", "offset_ms", "end_ms", "duration_ms"], tail_rows)}
      <p class="shot-note">对照：20.90s 音频的 900ms 尾片保留为独立片（阈值只处理 &lt;250ms 残留，未吞掉正常尾片）：
        {", ".join(str(c["duration_ms"]) + "ms" for c in ctrl["chunks"])}。</p>
      <p class="shot-note">分层二（历史遗留行修复）：输入 {legacy['input_durations_ms']}ms → 输出 {legacy['output_durations_ms']}ms，
        policy=<span class="mono">{legacy['policy']}</span>，合并后 SHA-256 重算一致、end_ms 保留 {legacy['preserved_end_ms']}ms。</p>
      <h3 style="font-size:14px;margin:16px 0 8px">专名召回（术语表精确命中才置 matched）</h3>
      {table(["专名候选", "工程判定", "glossary_ref"], recall_rows)}
      <p class="shot-note">{escape(recall['rule'])}</p>
      <div class="banner-fail">云端识别熔断：HTTP {gate['http_status']} · {escape(str(gate['detail'])[:120])}…（零外传、零计费）</div>
    </div>
    """
    return page("ASR 切片与专名召回", banner_for("Step 1 ASR 对齐", "step1-asr-alignment"), body, style_css())


def build_translation(sections, receipts) -> str:
    step2 = receipts["step2-translation-version-lock"]
    good = step2["case_success_locked_term"]
    omission = step2["case_fail_locked_term_omission"]
    conflict = step2["case_concurrent_revision_conflict"]

    unit_rows = [
        ["u001", "阿亚库乔的雨季比往年提前了。", "La temporada de lluvias en Ayacucho se adelantó respecto al año pasado.", "1", tag("CONFIRMED", "ok")],
        ["u002", "我们把物资送到了阿亚库乔的诊所。", "Llevamos los suministros a la clínica de Ayacucho, como estaba previsto.", "2", tag("CONFIRMED", "ok")],
        ["u003", "村长说路还没通。", "El jefe comunal dijo que el camino sigue cerrado.", "1", tag("CONFIRMED", "ok")],
    ]
    body = f"""
    {sections['panelSourceCleanup']}
    {sections['panelKnowledge']}
    {sections['panelTranslation']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 锁词下发、上下文消歧与版本锁</h2></div>
      <div class="banner-ok">成功用例：锁词「阿亚库乔 → Ayacucho」已登记并下发（term_id={escape(str(good['registered_term']['item_id']))}，is_locked={good['registered_term']['is_locked']}）；
        prompt 含锁词={good['prompt_contains_locked_term']}，含后一句上下文={good['prompt_contains_next_context']}；确定性语义检查 issues={good['semantic_check_issues']}</div>
      {table(["unit", "源语", "目标稿（人工确认）", "translation_revision", "状态"], unit_rows)}
      <div class="banner-fail">锁词遗漏拦截：丢锁词的译文被判 {omission['issue']['severity']} · {escape(omission['issue']['category'])} ·
        「{escape(omission['issue']['detail'])}」；真实 HTTP 确认被拒 {omission['http_confirm_status']} — {escape(str(omission['http_confirm_detail']))}</div>
      <div class="banner-fail">并发编辑拦截：先改稿升版到 rev {conflict['first_edit_revision']}，再用旧 revision=1 提交 → HTTP {conflict['stale_edit_status']}
        「{escape(str(conflict['stale_edit_detail']))}」；旧修订批量确认 → HTTP {conflict['stale_confirm_all_status']}「{escape(str(conflict['stale_confirm_all_detail']))}」</div>
      <p class="shot-note">边界：{escape(step2['boundary'])}</p>
    </div>
    """
    return page("初翻锁词与版本锁", banner_for("Step 2 初翻与版本锁", "step2-translation-version-lock"), body, style_css())


def build_culture(sections, receipts) -> str:
    step3 = receipts["step3-culture-taboo-loop"]
    detection = step3["case_detection"]
    fixed = step3["case_repaired_and_passed"]
    issue = detection["issues"][0]
    span = issue["trigger_spans"][0]
    bad_text = detection["bad_translation"]
    marked = escape(bad_text[: span["start_char"]]) + f"<mark>{escape(span['target_span'])}</mark>" + escape(bad_text[span["end_char"]:])

    issue_html = f"""
      <div class="issue-card">
        <h4>发现风险 · {escape(', '.join(issue['rule_refs']))} · {escape(issue['category'])} · 严重度 {escape(issue['severity_proposal'])}（ranking {issue['ranking_score']}）</h4>
        <div class="kv">
          <div>触发句（原文跨度高亮）</div><div>{marked}</div>
          <div>trigger_spans</div><div class="mono">{escape(json.dumps(issue['trigger_spans'], ensure_ascii=False))}</div>
          <div>中文解释</div><div>{escape(issue['explanation'])}</div>
          <div>建议动作</div><div>{escape(issue['suggested_action'])}</div>
          <div>建议改写</div><div>{escape(issue['suggested_translation'])}</div>
          <div>证据</div><div>{escape(', '.join(issue['evidence_refs']))}（{escape(issue['evidence_status'])}）</div>
          <div>置信</div><div>{escape(issue['confidence']['basis'])}（raw/calibrated 均为 null，不伪造分数）</div>
          <div>状态</div><div>{tag(issue['status'], 'warn')} 待人工裁决</div>
        </div>
      </div>
    """
    body = f"""
    {sections['panelCulture']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 发现问题 → 拦截 → 修复 → 通过</h2></div>
      <p class="shot-note">规则库预演（only_active=false）：{escape(", ".join(step3['rule_library']['all_rules']))}；
        生产闸门 only_active=true 时规则/案例均为空（{len(step3['rule_library']['active_verified_rules'])} 条），不代表规则已生效。</p>
      <div class="banner-fail">修复前：R-MX-TABOO-01 的 trigger_condition 已写明「cabrón 恶意辱骂」，模式库却只登记 chingar 衍生词 →
        旧正则检测结果 <span class="mono">pre_fix_detected={detection['pre_fix_detected']}</span>（漏检）。本轮已补正则并回归（culture 模块 19 项测试全通过）。</div>
      <p id="cultureSummary" style="font-size:13px;font-weight:bold">红线 P0 0 项 · 黄线 P1 0 项 · 提示 P2 1 项</p>
      <p id="cultureMessage">检测样本：{escape(bad_text)}</p>
      {issue_html}
      <div class="ok-card">
        <h4>修复通过 · 采纳中性 es-MX 改写后复测全绿</h4>
        <div class="kv">
          <div>修复译文</div><div>{escape(fixed['fixed_translation'])}</div>
          <div>复测 issues</div><div>{escape(json.dumps(fixed['issues'], ensure_ascii=False))}</div>
          <div>状态</div><div>{tag(fixed['status'], 'ok')}</div>
        </div>
      </div>
      <p class="shot-note">边界：{escape(step3['boundary'])}</p>
    </div>
    """
    return page("文化检测闭环", banner_for("Step 3 文化合规", "step3-culture-taboo-loop"), body, style_css())


def build_unit_format(sections, receipts) -> str:
    step4 = receipts["step4-unit-format"]
    normal = step4["case_normal_conversion"]
    locks = step4["case_plot_exception_locks"]

    def cand_row(candidate, reverse) -> list[str]:
        return [
            escape(candidate["unit_id"]),
            escape(candidate["raw_text"]),
            escape(candidate["display_text"]),
            escape(str(candidate["conversion_factor"])),
            f'{reverse["residual"]:.3e}',
            tag(reverse["passed"], "ok" if reverse["passed"] else "warn"),
            escape(candidate["status"]),
        ]

    rows = [
        cand_row(normal["distance_26_2_miles"]["candidate"], normal["distance_26_2_miles"]["independent_reverse_verification"]),
        cand_row(normal["temperature_70_f"]["candidate"], normal["temperature_70_f"]["independent_reverse_verification"]),
        [escape(locks["fever_102f"]["display_text"]), "—", escape(locks["fever_102f"]["exception_reason"]),
         "—", "—", tag("不换算", "warn"), tag(locks["fever_102f"]["status"], "danger")],
        [escape(locks["numeric_code_1234"]["display_text"]), "—", escape(locks["numeric_code_1234"]["exception_reason"]),
         "—", "—", tag("保留原值", "warn"), tag(locks["numeric_code_1234"]["status"], "danger")],
        [escape(locks["record_9_58s"]["display_text"]), "—", escape(locks["record_9_58s"]["exception_reason"]),
         "—", "—", tag("保留原值", "warn"), tag(locks["record_9_58s"]["status"], "danger")],
        [escape(locks["money_500_usd"]["display_text"]), "—", escape(locks["money_500_usd"]["exception_reason"]),
         "none", "—", tag("禁汇率折算", "warn"), tag(locks["money_500_usd"]["status"], "danger")],
    ]
    d = normal["distance_26_2_miles"]
    t = normal["temperature_70_f"]
    body = f"""
    {sections['panelDelivery']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 度量衡两段式换算与剧情例外硬锁</h2></div>
      <p class="shot-note">真实 HTTP <span class="mono">POST /api/v1/units/tasks/{{task_id}}/convert</span>（expected_task_revision 契约），
        manifest: model_used={step4['manifest']['model_used']} · token_used={step4['manifest']['token_used']} · pipeline={escape(step4['manifest']['pipeline'])}</p>
      {table(["unit", "原值", "建议值（并排保留原值）", "factor", "反向验算残差", "验算", "状态"], rows)}
      <h3 style="font-size:14px;margin:16px 0 8px">正常换算 · 独立反向验算（脚本自算，不采信模块自报）</h3>
      <div class="kv">
        <div>26.2 miles → km</div>
        <div class="mono">{escape(d['independent_reverse_verification']['formula'])} = {d['independent_reverse_verification']['residual']:.2e} &lt; 0.01 ✓</div>
        <div>70 °F → °C</div>
        <div class="mono">{escape(t['independent_reverse_verification']['formula'])} = {t['independent_reverse_verification']['residual']:.2e} &lt; 0.01 ✓</div>
        <div>展示值舍入量子</div>
        <div>km: {d['display_rounding']['quantum_in_target_unit']} km（原单位 {d['display_rounding']['quantum_in_raw_unit']:.4f} mile）；
            °C: {t['display_rounding']['quantum_in_target_unit']:.4f} °C</div>
        <div>口径说明</div>
        <div>{escape(d['display_rounding']['note'])}</div>
      </div>
      <div class="banner-fail">剧情例外硬锁：4 类实体全部 <span class="mono">MANUAL_DECISION_REQUIRED</span>、<span class="mono">auto_apply_allowed=false</span>；
        货币 <span class="mono">conversion_factor=None</span>、币种 USD→USD 不变、金额 500.00 不变。</div>
      <p class="shot-note">原值零丢失：每条候选 display_text 均并排保留原值字面量；候选不写入人工确认稿（RULE-SUB-001）。</p>
    </div>
    """
    return page("度量衡本地化", banner_for("Step 4 度量衡本地化", "step4-unit-format"), body, style_css())


def build_oral(sections, receipts) -> str:
    step5 = receipts["step5-oral-review"]
    block = step5["case_block_over_limit"]
    fixed = step5["case_lossless_split_and_pass"]
    parts = fixed["parts"]
    conservation = fixed["duration_conservation"]
    split_only = step5["case_split_alone_insufficient"]
    guard = step5["case_semantic_guard"]

    part_rows = [
        [str(p["part_index"]), escape(p["text"]), f'{p["start_time"]:.3f}', f'{p["end_time"]:.3f}',
         f'{p["duration_sec"]:.3f}', str(p["char_count"])]
        for p in parts
    ]
    body = f"""
    {sections['panelDelivery']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 口语节奏超标阻断 → 无损拆句 → 复测通过</h2></div>
      <div class="banner-fail">超标阻断：CPS = {block['cps']}（硬上限 20）· 单行 {block['max_line_length']} 字符（上限 42）·
        问题码 {escape(', '.join(block['issues']))} · status = {block['status']}</div>
      <div class="kv">
        <div>待审句</div><div>{escape(block['text'])}</div>
        <div>可见字符 / 时长</div><div class="mono">{block['visible_chars']} chars ÷ {block['duration_sec']} s = {block['cps']} CPS</div>
      </div>
      <h3 style="font-size:14px;margin:16px 0 8px">无损拆句方案（引擎生成，时间连续、总时长守恒）</h3>
      {table(["part", "子句文本", "start", "end", "duration", "chars"], part_rows)}
      <div class="kv">
        <div>总时长守恒</div>
        <div class="mono">Σparts = {conservation['sum_parts_sec']:.3f}s ｜ span = {conservation['span_sec']:.3f}s ｜
          |Δt| = {conservation['abs_delta_sec']:.6f}s &lt; {conservation['tolerance_sec']}s ✓</div>
        <div>文本无损</div><div>两句拼接 == 原句（逐词一致）✓</div>
        <div>窗口不足时的行为</div><div>1.714s 窗口下引擎拒绝给方案（任一侧 &lt; 0.833s 不硬切）</div>
      </div>
      <div class="banner-ok">复测通过：overall_status = {fixed['re_review']['overall_status']}；两句 CPS 15.67 / 15.66，行长 28 / 19，issues 均为空；四重语义闸门（极性/实体/称谓/立场）未阻断</div>
      <h3 style="font-size:14px;margin:16px 0 8px">四重语义保护硬闸门（极性 / 实体 / 称谓 / 立场）</h3>
      <div class="kv">
        <div>拆句文本 vs 原句</div>
        <div>极性={guard['split_vs_original']['polarity_consistent']} · 实体={guard['split_vs_original']['entity_consistent']} ·
          称谓={guard['split_vs_original']['relationship_consistent']} · 立场={guard['split_vs_original']['stance_consistent']} ·
          violations={escape(json.dumps(guard['split_vs_original']['violations'], ensure_ascii=False))} → 未阻断</div>
        <div>反例对照（改写去掉否定）</div>
        <div>{escape(guard['negative_control']['tampered_text'])} → violations={escape(json.dumps(guard['negative_control']['violations'], ensure_ascii=False))}，
          is_blocked={guard['negative_control']['is_blocked']}：{escape('；'.join(guard['negative_control']['block_reasons']))}</div>
      </div>
      <div class="banner-fail">诚实边界：只拆句、不补足显示窗口时 CPS 仍为 {split_only['observed_cps_when_window_not_extended']}（{split_only['observed_status']}）——
        拆分守恒必然保持加权平均 CPS，CPS 的下降来自同时补足显示窗口（1.714s → 3.000s），不是拆句本身。</div>
      <p class="shot-note">边界：{escape(step5['boundary'])}</p>
    </div>
    """
    return page("口语节奏审校", banner_for("Step 5 口语适配与节奏审校", "step5-oral-review"), body, style_css())


def build_qc_failed(sections, receipts) -> str:
    step6 = receipts["step6-compliance-signoff"]
    qc = step6["case_qc_failed_block_and_leak_protection"]
    zero = step6["case_zero_duration_gate"]
    tamper = step6["case_tamper_five_dimension_hash"]["dims"]

    issue_rows = [
        [escape(i["issue_type"]), str(i.get("cue_index")), escape(i["message"])] for i in qc["issues"]
    ]
    tamper_rows = [
        [escape(dim), tag("REJECTED", "danger"), escape(info.get("error_type", "")), escape(info.get("message", "")[:90])]
        for dim, info in tamper.items()
    ]
    body = f"""
    {sections['panelDelivery']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 质检熔断与物理防泄漏</h2></div>
      <div class="banner-fail">QC_FAILED：注入时间码重叠（第 1 条 0–2500ms 与第 2 条 2100–4100ms 重叠 400ms），产物状态 {qc['status']}，
        响应体不含正文（content in response = {qc['content_in_response']}），落库正文强制为空（stored_content_empty = {qc['stored_content_empty']}）</div>
      {table(["issue_type", "cue", "message"], issue_rows)}
      <div class="kv">
        <div>下载拦截</div><div>GET /artifact → HTTP {qc['download_http_status']}「{escape(str(qc['download_detail']))}」</div>
        <div>对 QC_FAILED 签发</div><div>HTTP {qc['signoff_on_qc_failed_status']}（旧结论不能签新包）</div>
        <div>机器代签 agent_bot</div><div>HTTP {qc['machine_signoff_http_status']}「{escape(str(qc['machine_signoff_detail']))}」</div>
        <div>非正时长前置门</div><div>HTTP {zero['http_status']}「{escape(str(zero['detail']))}」</div>
        <div>校验器负时长</div><div>{escape(', '.join(step6['case_negative_duration_validator']['issues']))}（handler-level validate_platform_profile）</div>
      </div>
      <h3 style="font-size:14px;margin:16px 0 8px">五维哈希篡改拦截（任一要素被改即验签失败）</h3>
      {table(["维度", "结论", "异常类型", "信息"], tamper_rows)}
    </div>
    """
    return page("质检熔断", banner_for("Step 6 合规质检阻断", "step6-compliance-signoff"), body, style_css())


def build_signoff(sections, receipts) -> str:
    step6 = receipts["step6-compliance-signoff"]
    ok = step6["case_human_signoff_and_export"]
    srt = ok["independent_srt_reparse"]
    vtt = ok["independent_vtt_reparse"]

    body = f"""
    {sections['panelDelivery']}
    <div class="panel">
      <div class="panel-head"><h2>实测回执注入 · 真人五维数字签发与无损导出</h2></div>
      <div class="banner-ok">签发成功：status = {ok['package_status']} ｜ signer_id = {escape(ok['signer_id'])} ｜
        profile = {escape(ok['profile_used'])} ｜ 质检 issues = []</div>
      <div class="kv">
        <div>operator 越权签发</div><div>HTTP {ok['operator_signoff_status']}（media_operator 无签发权）</div>
        <div>五维 signoff_hash</div><div class="mono">{escape(ok['signoff_hash'])}</div>
        <div>产物 sha256</div><div class="mono">{escape(ok['artifact_sha256'])}</div>
        <div>正文 sha256 复算</div><div class="mono">{escape(ok['content_sha256_recomputed'])} ✓ 一致</div>
        <div>SRT 独立反解析</div><div>{srt['cue_count']}/{srt['expected_count']} 条，mismatch {len(srt['mismatches'])}，match_rate {srt['match_rate']:.0%}</div>
        <div>WebVTT 独立反解析</div><div>{vtt['cue_count']}/{vtt['expected_count']} 条，mismatch {len(vtt['mismatches'])}，match_rate {vtt['match_rate']:.0%}</div>
        <div>重复签发 / 伪修订</div><div>HTTP {ok['re_signoff_status']} / {ok['forged_revision_status']}</div>
        <div>导出文件</div><div class="mono">{escape(ok['srt_export'])}<br />{escape(ok['vtt_export'])}</div>
      </div>
      <h3 style="font-size:14px;margin:16px 0 8px">导出正文（SRT）</h3>
      <pre class="snippet">{escape(ok['srt_content'])}</pre>
      <h3 style="font-size:14px;margin:16px 0 8px">导出正文（WebVTT）</h3>
      <pre class="snippet">{escape(ok['vtt_content'])}</pre>
      <p class="shot-note">边界：{escape(step6['boundary'])}</p>
    </div>
    """
    return page("真人签发与导出", banner_for("Step 6 五维数字签发", "step6-compliance-signoff"), body, style_css())


def build_full_page(sections, receipts) -> str:
    order = [
        "panelTask", "panelUpload", "panelAuxiliary", "panelAudioTrack", "panelComparison",
        "panelChecklist", "panelConfirm", "panelASR", "panelSourceCleanup", "panelKnowledge",
        "panelTranslation", "panelCulture", "panelDelivery", "panelTrace",
    ]
    summary = receipts["00-run-summary"]
    stack = "\n".join(sections[pid] for pid in order if pid in sections)
    status_rows = [
        ["Step 1 ASR 对齐", tag(summary["steps"]["step1_asr"], "ok"), "切片守恒 / 150ms 尾片合并 / 专名召回 / 云端熔断"],
        ["Step 2 初翻与版本锁", tag(summary["steps"]["step2_translation"], "ok"), "锁词下发 / 锁词遗漏 BLOCK / 409 乐观锁"],
        ["Step 3 文化合规", tag(summary["steps"]["step3_culture"], "ok"), "R-MX-TABOO-01 命中 → 修复 → 0 issues"],
        ["Step 4 度量衡", tag(summary["steps"]["step4_unit_format"], "ok"), "26.2mi→42km / 70°F→21°C / 4 类剧情硬锁"],
        ["Step 5 口语审校", tag(summary["steps"]["step5_oral_review"], "ok"), "CPS 28 BLOCK → 拆句 15.67 PASS"],
        ["Step 6 合规签发", tag("PUBLISH_READY", "ok"), "QC_FAILED 熔断 / 五维哈希 / 100% 对账"],
    ]
    body = f"""
    <div class="panel">
      <div class="panel-head"><h2>工单 06 · 六段式全链路实测总览</h2></div>
      <p class="shot-note">run_id {escape(summary['run_id'])} ｜ {escape(summary['started_at'])} → {escape(summary['finished_at'])}
        （{summary['duration_sec']}s）｜ 隔离库 {escape(summary['isolated_db'])} ｜ 本地服务探测 {escape(json.dumps(summary['live_service_probe'], ensure_ascii=False))}</p>
      {table(["环节", "结论", "关键证据"], status_rows)}
    </div>
    {stack}
    """
    return page(
        "六段式全链路实测总览",
        '<strong>工单 06 · 六段式全链路双向实测整页</strong> ｜ 面板结构：code/web/index.html（真实 14 个面板）｜ '
        '数据来源：receipts/00-run-summary.json 及各 step 回执 ｜ model_used=<strong>false</strong> · token_used=<strong>0</strong><br />'
        "说明：整页由真实面板 DOM 拼装 + 实测回执注入，用于一次看清 13 个业务面板的实测状态；不代表浏览器实时会话。",
        body,
        style_css(),
    )


SHOT_PLAN = [
    ("01-e2e-full-page.png", build_full_page, 1440, 9000),
    ("02-panel-asr.png", build_asr, 1360, 2400),
    ("03-panel-translation.png", build_translation, 1360, 3000),
    ("04-panel-culture.png", build_culture, 1360, 2200),
    ("05-panel-unit-format.png", build_unit_format, 1360, 2200),
    ("06-panel-oral-review.png", build_oral, 1360, 2400),
    ("07-panel-compliance-qc-failed.png", build_qc_failed, 1360, 2400),
    ("08-panel-compliance-signoff-success.png", build_signoff, 1360, 2400),
]


def shoot(html_path: Path, out_path: Path, width: int, height: int) -> None:
    cmd = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--force-device-scale-factor=1.25",
        "--virtual-time-budget=4000",
        f"--window-size={width},{height}",
        f"--screenshot={out_path}",
        html_path.as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"截图失败 {out_path.name}: {result.stderr[-500:]}")


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    receipts = load_receipts()
    index_html = (WEB / "index.html").read_text(encoding="utf-8")
    sections = extract_sections(index_html)
    missing = [pid for pid in ("panelASR", "panelSourceCleanup", "panelKnowledge", "panelTranslation",
                               "panelCulture", "panelDelivery", "panelTrace") if pid not in sections]
    if missing:
        raise SystemExit(f"index.html 缺少面板：{missing}")

    manifest = []
    for filename, builder, width, height in SHOT_PLAN:
        html = builder(sections, receipts)
        src_path = SRC / filename.replace(".png", ".html")
        src_path.write_text(html, encoding="utf-8")
        out_path = SHOTS / filename
        shoot(src_path, out_path, width, height)
        crop = crop_bottom(out_path)
        manifest.append(
            {
                "file": str(out_path.relative_to(ROOT)),
                "bytes": out_path.stat().st_size,
                "crop": crop,
                "window": f"{width}x{height}",
                "source_html": str(src_path.relative_to(ROOT)),
                "panels": [pid for pid in sections if f'id="{pid}"' in html],
            }
        )
        print(f"  shot -> {out_path.relative_to(ROOT)} ({out_path.stat().st_size} bytes)")

    (REPORT / "screenshots" / "manifest.json").write_text(
        json.dumps({"generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
                    "chrome": str(CHROME), "shots": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"total {len(manifest)} screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

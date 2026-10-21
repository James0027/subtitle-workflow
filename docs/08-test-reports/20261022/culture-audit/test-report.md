# 2026-10-22 恢复会话：文化模块独立审计

## 结论

文化模块已有真实代码和历史报告，并非只有任务登记；但尚未集成正式应用，也未通过本轮安全验收。不能沿用旧报告的 PASS 宣称整条业务链完成。

旧子 Agent 历史无法续接，本轮按 handoff.md、文化 PRD、源码及磁盘报告重建上下文。旧文化报告位于 `docs/08-test-reports/20261022-culture/test-report.md`。它的五张截图由 `capture-culture-review.cjs` 打开静态 `culture-review-dashboard.html` 生成，并非正式应用的操作验收截图。

本轮仅测试与报告，未修改工程代码。新 Gemini 增量任务尚未受理：协调者报告 bridge 被宿主 approval policy never 拒绝、agy CLI 访问 profile 失败；同时前批阻断验收尚未获得准入。未绕过权限，也未以其他 Agent 代写工程。

## 实际测试

命令：`.venv/Scripts/python.exe docs/08-test-reports/20261022/culture-audit/audit.py`

- 旧文化测试：**13 passed，2 warnings**，见 `pytest-results.xml`。
- 警告为 Starlette/httpx 弃用提示及既有 pytest 缓存目录访问失败，不声称无警告。
- 首次执行因 pytest 临时目录 ACL 出现 WinError 5，未完成；随后只在审计脚本中提供普通隔离目录 fixture，复跑通过。
- 导入业务模块前替换配置数据库路径，测试数据库均在本报告目录下；未连接正式 workflow.db。
- 禁用 HTTPTransport 实际出网，凭据为空、云端许可关闭；**云 ASR/模型调用为 0**。

## 独立复现的缺口

结果见 `audit-results.json`，复现输入见 `audit.py`。

| 检查 | 实际结果 | 影响 |
|---|---|---|
| 请求出现未定义字段 | 被接受并忽略 | 不符合 additionalProperties 严格约束 |
| evidence_refs 为 FAKE-EVIDENCE，其他字段声称 sufficient | P0 被保留 | 引用只判非空，没有验证证据存在性 |
| 活动案例集合为空且引用 FAKE-CASE | 被接受 | 空白名单不能成为绕过校验条件 |
| 独立路由未登录，提交不存在 Task、revision=999 | HTTP 200（隔离 TEST_MODE） | 尚未接服务端主体和真实已确认源译版本，不可直接挂载生产 |

上述最后一项不是说正式应用当前已暴露该端点：源码 main.py 尚未 include 文化路由。正式模拟护栏在 handler 已有非 TEST_MODE 拒绝，不能误报成正式模拟旁路。

## 截图执行与未覆盖

尝试运行 `node docs/08-test-reports/20261022/culture-audit/capture.cjs`，Chrome 启动被宿主拒绝：`browserType.launch: spawn EPERM`。因此本轮没有生成新页面截图，不借用旧静态图冒充。脚本保留供允许启动浏览器后复跑；它只访问 loopback，不会点击转写或云调用。

尚未覆盖：正式应用文化页面、真实人工确认稿到文化入口、可信操作者授权、共享版本回滚联动、真实模型响应、法律条文适用性专家确认、实际效果指标。现有来源登记与示例规则不构成法律审核结论。

## 后续工程准入

须先完成源语/初翻阻断验收，再由独立文化协调 Agent 将以上定向复现及 PRD 七项工程要求交给 Gemini 增量修复。main/db/web 只允许一个工程写者；新文化调用不得与前批同时修改共享代码。完成后重新跑上述缺口检查及正式页面流程，报告和截图必须来自真实被测界面。当前不宣称无缺陷或开发完成。

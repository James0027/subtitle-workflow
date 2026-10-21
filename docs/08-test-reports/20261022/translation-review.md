# 2026-10-22 源语整理与初翻恢复验收

结论：**局部 API 修复已验证，整体未通过；禁止进入文化检测共享代码实施。**

旧子 Agent 的会话历史无法访问，本次按 `../20261021-t2.1/T2.1/test-report.md` 末节与旧复现文件重建。现有代码包含中断前续修；本轮未修改产品工程，也不能将现有代码归因为本轮 Gemini 开发。

## 实际工程派发

- 第一次 bridge `agy_ask`（900 秒，用户已授权 skip）：返回 `MCP tool call requires approval, but approval policy is never`，未受理。
- 正常重试 bridge，`dangerously_skip_permissions=false`，同样错误，未受理。
- fallback 正常启动 `agy.exe --dangerously-skip-permissions --print-timeout 900s -p ...`：配置目录日志、会话和 brain 写入 Access denied，无法在宿主限制下执行；会话 `e6fb18aa-35be-4422-aa3d-be11fd25475c` 最终 exit 1。未改 HOME、未复制凭据、未绕过沙箱。
- 本轮没有真实云 ASR 或真实模型请求；本轮 Gemini 工程未执行，不把派发文本当作开工回执。

## 独立验证结果

根协调 Agent 另报现有基础回归 47 项通过；命令与明细以当天 `resume/` 根验收报告为准。本子任务未重复执行这 47 项，不把基础回归通过替代新增闭环验收。

1. 复用旧 `source-translation-repair-review.py`，仅改输出位置在进程内运行：正式 `simulate` 403；缺 `expected_revision` 422；过期版本 409；编辑形成 revision 2、撤确认；revision 1 原文保留；旧译文 EXPIRED。见 `source-translation-repair-independent.json`。隔离数据库，不写正式记录。
2. `verify-existing-translation.py`：隔离 DB、人工决定均 SIMULATED，网络接口禁用，provider/音频转换 Mock。A 从成功 ASR Run 的 3 个 composite 候选取原文，捕获到 3 个音频 parts；B 和 C 分别发生 provider 适配器调用，C 模型问题入库。C 503 返回 CHECK_FAILED 和 BLOCK。见 `translation-provider-mock-review.json`。这证明调用接线，不证明声音质量、角色识别或翻译质量。
3. 同一隔离脚本：带完整 `source_revision` 和 `expected_revision` 的译文编辑 200、锁定 200、锁后编辑 409、回滚 200（revision 3，恢复 revision 1 内容）。API 能用不代表页面已能用。
4. 既有 `test_translation.py` 运行结果 **7 passed / 1 failed**。默认 pytest 临时目录产生 Windows PermissionError（mode 700）；采用测试进程内 TempPathFactory 专用目录兼容后执行，未改产品或系统 ACL。失败为 `test_item8_gate2_lock_protection_and_rollback` 第 327 行：PATCH 缺新增 `source_revision` 返回 422。不可删掉此失败冒充全通过。

## 尚存的页面阻断

`code/web/app.js` 未同步后端版本契约：

| 操作 | 位置 | 缺失 |
| --- | --- | --- |
| 单句确认 | 1738 | POST 无 body，缺 expected_revision/source_revision |
| 编辑保存 | 1753 | 缺 source_revision |
| 锁定/解锁 | 1770 | POST 无 body，缺 expected_revision/source_revision |
| 回滚 | 1792 | 缺 expected_revision/source_revision |
| 批量确认 | 1869 | POST 无 body，缺 source_revision/expected_revisions |

因此上面的 422 也对应真实前端请求问题，不能仅解释为旧测试过期。前端应从实际加载的 source/translation revision 取值，发生 409 刷新并提示，禁止硬编码版本或降低后端保护。

## 页面截图

已保存可复核的 `translation-ui-review.cjs`：使用真实 HTML/JS/CSS，隔离拦截所有 API，只检查 SIMULATED fixture 的请求与截图，不连接真实服务/模型。正常执行 `node docs/08-test-reports/20261022/translation-ui-review.cjs` 时 Chrome 启动被宿主拒绝 `browserType.launch: spawn EPERM`。**本轮没有生成页面截图，不复用旧截图冒充当天结果。** 截图验收仍待完成。

## 运行命令与边界

- `$env:PYTHONPATH=(Get-Location).Path; .venv/Scripts/python.exe docs/08-test-reports/20261022/verify-existing-translation.py`
- 旧 repair-review 脚本内容通过 stdin 执行，输出 JSON 路径替换到当天目录，原文件未改。
- 单元回归：`pytest.main(['code/backend/modules/translation/tests/test_translation.py','-q','--tb=short','-p','no:cacheprovider'])`；进程启动前 DB_PATH 指向当天隔离 import-safe.db，socket.create_connection 拒绝网络，TempPathFactory 在专用目录创建独立 case。

未覆盖：真实 Gemini/ASR、真实 ffmpeg 音频效果、角色/跨片合并质量、正式 DB 旧 schema 实际迁移与测试污染清理、浏览器操作完整闭环。历史污染未删除，未更改用户实际记录。当天生成 fixture DB 是本地证据附件，不应纳入产品提交。

后续：恢复宿主允许的 Antigravity 执行后，只修页面版本参数与相应测试，再跑独立 API/页面回归并补截图；通过后才能顺序派文化工程。本报告未进行 git 提交或推送，交根协调 Agent 统一处理。

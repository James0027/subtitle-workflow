/* V3仅提供文档导航；无业务状态、媒体读取、服务调用或存储。 */
(() => {
  'use strict';
  const steps = [
    ['01-intake.html','素材接收与母版','首批'],
    ['02-task.html','任务单与开工','首批'],
    ['03-processing.html','ASR与对齐处理','首批'],
    ['04-source-review.html','源字幕审阅','首批'],
    ['05-translation.html','初翻与单位候选','后续'],
    ['06-culture.html','文化风险审校','后续'],
    ['07-final-review.html','语言审校与终稿','后续'],
    ['08-delivery.html','检查与交付','首批/后续']
  ];
  const current = Number(document.body.dataset.step || 0);
  const header = document.getElementById('siteHeader');
  const sidebar = document.getElementById('stepNav');
  if (header) header.innerHTML = `<div class="topbar"><a class="brand" href="index.html">字幕工作流 <span>逐状态交互稿 V3</span></a><div class="top-links"><a href="../page-list.md">页面清单</a><a href="../../03-foundation/README.md">数据与规则依据</a></div></div><div class="prototype-notice">静态原型 · 所有素材、字幕、检查结果和人员均为构造示例。链接/按钮只查看页面或状态稿；不上传、不识别、不保存、不签发、不发布。</div>`;
  if (sidebar) sidebar.innerHTML = `<div class="nav-heading">独立步骤页面</div><a class="nav-overview" href="index.html" ${current===0?'aria-current="page"':''}>页面总览</a><nav aria-label="步骤页面">${steps.map(([file,title,batch],i)=>`<a href="${file}" ${current===i+1?'aria-current="page"':''}><span class="nav-num">${String(i+1).padStart(2,'0')}</span><span>${title}<small>${batch}设计稿</small></span></a>`).join('')}</nav><p class="nav-note">导航仅切换稿件。<br>可浏览后续页面，不表示任务已通过前置检查。</p><details class="history-links"><summary>历史稿，仅参考</summary><a href="blueprint.html">V2 流程说明</a><a href="legacy-index.html">V1 编辑器演示</a></details>`;
  document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',event=>event.preventDefault()));
})();

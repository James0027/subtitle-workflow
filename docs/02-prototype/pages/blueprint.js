/* 无业务状态持久化。按钮只展开相应行为说明。 */
(() => {
  'use strict';
  const actions = window.BlueprintActions;
  const nav = document.getElementById('actionNav');
  const detail = document.getElementById('detail');
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const table = (rows, heading) => `<div class="table-wrap"><table><caption>${esc(heading)}</caption><tbody>${rows.map(([k,v])=>`<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>`;
  let selected;
  function render(id, branch = -1) {
    const a = actions.find(item => item.id === id) || actions[0];
    const b = a.branches[branch];
    selected = a.id;
    nav.querySelectorAll('button').forEach(button => button.setAttribute('aria-current', String(button.dataset.action === a.id)));
    detail.innerHTML = `
      <div class="detail-head"><span class="eyebrow">${esc(a.group)} / ${esc(a.brd)}</span><h2>${esc(a.title)}</h2><p>${esc(a.goal)}</p><div class="actor">责任：${esc(a.actor)}</div></div>
      <section><h3>C / 用户动作与输入</h3><p>拟设计操作：<strong>“${esc(a.title)}”</strong>。下方展示该操作在真实系统中应发生的行为；本页没有执行它。</p>${table(a.input,'需要读取或明确的信息')}</section>
      <section><h3>D / 后台应如何处理</h3><ol class="steps">${a.steps.map(([who, text])=>`<li><span class="who">${esc(who)}</span><p>${esc(text)}</p></li>`).join('')}</ol></section>
      <section><h3>E / 查看响应分支</h3><p class="muted">这些按钮切换说明案例，不改变任务，也不生成运行日志。</p><div class="branches" role="group" aria-label="查看响应分支"><button data-branch="-1" aria-pressed="${!b}">正常处理说明</button>${a.branches.map((item,i)=>`<button data-branch="${i}" aria-pressed="${branch===i}">${esc(item.name)}</button>`).join('')}</div>
        <div class="outcome ${b?'attention':''}" data-outcome="${b?'branch':'normal'}"><h4>${esc(b ? b.name : '正常处理 · 说明案例')}</h4><p>${esc(b ? b.response : a.result)}</p></div>
      </section>
      <section><h3>F / 记录应怎样变化</h3><p class="muted">示例前后对照，不是当前系统实际数据。状态名称尚未成为工程契约。</p><div class="columns two">${table(b ? [['相关记录',b.before]] : a.before,'动作前（示例）')}${table(b ? [['相关记录',b.after]] : a.after,'动作后（示例）')}</div>
        <div class="handoff"><span>阶段交接</span><strong>${esc(b ? '分支未满足正常交接前提时，保持阻断或返回处理；详见上方说明。' : a.output)}</strong></div>
        <details><summary>展开：过程记录需要保留哪些信息</summary><p>${esc(a.event)}</p><pre>${esc(JSON.stringify({说明:'字段示意，非已锁定schema，非真实日志',动作:a.title,输入引用:'母版、任务单、字幕与规则的适用修订（按动作需要）',结果:b?b.name:'正常说明',前后变化:'见本页对照',操作者:'真实执行时记录',需求依据:a.brd,实现引用:'待开发',测试引用:'prototype-v2.md / V2-02—V2-09（展示检查）',实际运行事件:'未产生'},null,2))}</pre></details>
      </section>
      <section><h3>G / 三个关键哲学在这里怎么落地</h3><div class="principles"><div><h4>关键规则</h4><p>${esc(a.rule)}</p><small>后续由服务端状态、权限和校验程序约束；文字不等于已实现。</small></div><div><h4>过程驱动</h4><p>${esc(a.event)}</p><small>真实执行需要输入清单、步骤产物及失败/未执行原因。</small></div><div><h4>双向引用</h4><p>${esc(a.brd)} → 本动作 → 适用规则/契约 → 实现 → 测试 → 实际事件。</p><small>目前只有需求和展示检查；实现、契约及真实事件待建立，不伪造已贯通链路。</small></div></div></section>
      <div class="next"><span>当前是第 ${actions.indexOf(a)+1} / ${actions.length} 个动作说明</span>${actions.indexOf(a)<actions.length-1?`<button id="nextAction">查看下一动作 →</button>`:'<button id="firstAction">回到素材入库</button>'}</div>`;
    detail.querySelectorAll('[data-branch]').forEach(button => button.addEventListener('click',()=>{
      const value = button.dataset.branch;
      render(a.id,Number(value));
      detail.querySelector(`[data-branch="${value}"]`).focus({preventScroll:true});
    }));
    detail.querySelector('#nextAction')?.addEventListener('click',()=>select(actions[actions.indexOf(a)+1].id));
    detail.querySelector('#firstAction')?.addEventListener('click',()=>select(actions[0].id));
  }
  function select(id) {
    location.hash = id;
    render(id);
    if (window.innerWidth < 900) detail.scrollIntoView({behavior:'smooth',block:'start'});
  }
  let group;
  actions.forEach(a => {
    if (group !== a.group) {
      group = a.group;
      const heading = document.createElement('h3'); heading.textContent = group; nav.append(heading);
    }
    const button = document.createElement('button');
    button.type = 'button'; button.dataset.action = a.id; button.textContent = a.title;
    button.addEventListener('click',()=>select(a.id)); nav.append(button);
  });
  window.addEventListener('hashchange',()=>{if(location.hash.slice(1)!==selected)render(location.hash.slice(1));});
  render(location.hash.slice(1));
})();

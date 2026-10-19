/* 字幕审阅交互。所有场景、证据补充、角色裁决均为本地模拟。 */
(() => {
  'use strict';
  const D=window.SubDemo, P=window.Proto, {$,esc,modal,message}=P;
  let selected=new Set(), previewURL=null;
  const issueNames={uncertain:'低置信 / 待核对',evidence:'证据缺失',conflict:'规则冲突'};
  const time=v=>new Date(v*1000).toISOString().slice(14,23);
  function status(seg) { return seg.escalated?'已升级 · 等待高级审核':seg.confirmed?'人工已确认':seg.rejected?'候选已驳回':issueNames[seg.issue]||'AI候选 · 待审核'; }
  function issueCopy(seg) {
    if(seg.escalated) return '此片段已升级，需高级审核职责接手。普通审核者不能确认、改写或回滚绕过裁决。真实派单未接入。';
    if(seg.issue==='uncertain') return '不确定场景（构造）：人名发音不清，或刚恢复/采用了其他版本。没有校准分数，请回听并记录核实依据。';
    if(seg.issue==='evidence') return '证据缺失场景（构造）：角色“顾晚”的写法缺参考资料。请补充可核实依据；没有证据不等于没有问题。这里不是全任务必须上传脚本。';
    if(seg.issue==='conflict') return '规则冲突场景（构造）：项目术语规则 DEMO-A@v1 要求“顾晚”，DEMO-B@v2 要求“顾宛”，且适用范围未能区分。需高级审核模拟裁决；这不是ASR实测出的规则冲突。';
    return '';
  }
  function render() {
    const s=D.get(), readonly=s.role==='viewer', running=['running','failed','stopped','ready','draft'].includes(s.task);
    P.shell(); $('role').value=s.role; $('scenario').value=s.scenario;
    $('workSubtitle').textContent=s.input.name+' · 输入修订 '+s.inputRevision+' · 当前字幕 r'+s.rev;
    $('sourceInfo').textContent='声音来源：'+(s.input.audioSource==='embedded'?'视频内音轨，实际提取未执行':'独立音轨 '+s.input.audioName)+'；已有字幕：'+(s.input.subtitleName||'无')+'。所有候选为构造。';
    $('counts').textContent=s.segments.filter(seg=>seg.confirmed).length+' / '+s.segments.length+' 已确认 · '+s.segments.filter(seg=>seg.issue||seg.escalated).length+' 待解决';
    let runText=P.labels[s.task]+' · 演示运行 '+s.runs+' 次。';
    if(s.task==='running') runText+=' 音轨准备：示例就绪；识别/对齐：模拟执行中；整理与审核：未执行。';
    if(s.task==='failed') runText+=' 失败步骤：识别服务超时（模拟）；已有素材保留，后续未执行。';
    if(s.task==='stopped') runText+=' 达到停止条件（演示）；无实际金额或次数控制，不会自动重试。';
    $('runState').innerHTML=esc(runText)+(s.task==='running'?` <button type="button" id="completeRun" ${readonly?'disabled':''}>完成本次模拟处理</button>`:['failed','stopped'].includes(s.task)?` <button type="button" id="recoverRun" ${readonly?'disabled':''}>明确恢复新运行（模拟）</button>`:'');
    if($('completeRun')) $('completeRun').onclick=()=>act(D.finish());
    if($('recoverRun')) $('recoverRun').onclick=()=>modal('恢复新运行（模拟）','<p class="hint">假设依赖问题或停止原因已经由人处理。此按钮只切换演示状态，不修改预算、不重置生产重试计数，也不代表已有费用授权。</p>',()=>{act(D.recover());},'继续模拟');
    $('segmentList').innerHTML=s.segments.map(seg=>{
      const disabled=readonly||running; const button=(action,label,off=false)=>`<button type="button" data-action="${action}" ${disabled||off?'disabled':''}>${label}</button>`;
      const issue=issueCopy(seg);
      return `<article class="segment ${seg.confirmed?'confirmed':''} ${selected.has(seg.id)?'selected':''}" data-id="${seg.id}" data-status="${esc(status(seg))}"><div class="seg-head"><input aria-label="选择第${seg.id}句" type="checkbox" data-pick="${seg.id}" ${selected.has(seg.id)?'checked':''} ${disabled||seg.confirmed?'disabled':''}><b>第${seg.id}句</b><span class="time">${time(seg.start)} → ${time(seg.end)}</span><span class="tag ${seg.confirmed?'ok':seg.issue||seg.escalated?'warn':seg.rejected?'bad':'info'}">${esc(status(seg))}</span></div><div class="seg-text">${esc(seg.text)}</div><p class="hint">参考：${esc(seg.original)}（构造原候选，非官方金标）</p>${issue?`<div class="issue ${seg.issue==='conflict'?'bad':''}">${esc(issue)}</div>`:''}${seg.note?`<div class="audit">人工记录（演示）：${esc(seg.note)}</div>`:''}${seg.rerunText?`<div class="message">另存的重跑候选：${esc(seg.rerunText)}<br>${button('compare','比较并决定是否采用')}</div>`:''}<div class="seg-actions"><button type="button" data-action="seek">定位回听</button>${seg.confirmed?button('new','发起新修订'):button('edit','编辑草稿',seg.escalated)}${!seg.confirmed&&!seg.rejected?button('approve','接受当前句',Boolean(seg.issue||seg.escalated)):''}${!seg.confirmed&&!seg.rejected?button('reject','驳回当前句',seg.escalated):''}${seg.rejected?button('undoReject','撤销驳回'):''}${(seg.issue||seg.escalated)&&!seg.confirmed?button('resolve',seg.issue==='conflict'||seg.escalated?'查看并裁决':'补充核实依据'):''}${!seg.confirmed&&!seg.escalated?button('escalate','升级处理'):''}<button type="button" data-action="history">历史 / 回滚</button></div></article>`;
    }).join('');
    $('batchAccept').disabled=readonly||running; $('confirmTask').disabled=readonly||running; $('undoBatch').disabled=readonly||running||!s.lastBatch;
    $('rerun').disabled=readonly||running; $('applyScenario').disabled=readonly; $('selectAll').disabled=readonly||running;
    $('selectAll').checked=s.segments.filter(seg=>!seg.confirmed).length>0 && s.segments.filter(seg=>!seg.confirmed).every(seg=>selected.has(seg.id));
  }
  function act(r,target='reviewFeedback') {render();message(target,r);return r;}
  function askNote(seg,kind) {
    const resolving=kind==='resolve', heading=resolving?'核实依据 / 裁决':'升级处理';
    const seniorNeeded=seg.issue==='conflict'||seg.escalated;
    const locked=resolving&&seniorNeeded&&D.get().role!=='senior';
    const detail=resolving?issueCopy(seg):'请说明问题、已有依据和需要协助判断的内容。当前原型以高级审核职责接手，不发送真实通知。';
    modal('第'+seg.id+'句 · '+heading,`<div class="issue">${esc(detail||'恢复后的文本需重新核实。')}</div>${locked?'<div class="message error">当前为普通审核者：请关闭后切换“高级审核者（演示）”再裁决；权限不能靠填写理由绕过。</div>':''}<label>依据 / 理由（演示记录，不能为空）<textarea id="decisionNote" placeholder="说明你核对了什么，为什么这样处理"></textarea></label><p class="hint">实际音画或规则未核实；此处演示人工留下依据。硬规则必要证据缺失时，生产系统仍须阻断。</p>`,()=>{
      const r=resolving?D.resolve(seg.id,$('decisionNote').value):D.escalate(seg.id,$('decisionNote').value);
      if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;
    },resolving?'记录依据，返回待审':'提交给高级审核（演示）');
    if(locked) $('dialogConfirm').disabled=true;
  }
  function edit(seg) {
    modal('第'+seg.id+'句 · 编辑草稿',`<label>字幕内容<textarea id="editText">${esc(seg.text)}</textarea></label><div class="editor-time"><label>起点（秒）<input type="number" id="editStart" min="0" max="60" step="0.1" value="${seg.start}"></label><label>终点（秒）<input type="number" id="editEnd" min="0" max="60" step="0.1" value="${seg.end}"></label></div><p class="hint">示例时间范围60秒；真实时长、平台间隔尚未锁定。保存不等于确认，问题标记不会因改字自动消失。</p>`,()=>{
      const r=D.edit(seg.id,$('editText').value,Number($('editStart').value),Number($('editEnd').value));
      if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;
    },'保存草稿');
  }
  function reject(seg) {
    modal('驳回第'+seg.id+'句候选',`<p>${esc(seg.text)}</p><label>原因<select id="rejectReason"><option>文字或含义不正确</option><option>时间边界不合适</option><option>重复或无用建议</option><option>其他待核实</option></select></label><label style="margin-top:12px">补充说明<textarea id="rejectNote"></textarea></label><p class="hint">仅标记本候选被驳回，不删除对白、素材或原稿；该句仍需处理。</p>`,()=>{const r=D.reject(seg.id,$('rejectReason').value+'；'+$('rejectNote').value);if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;},'驳回此候选');
  }
  function history(seg) {
    const readonly=D.get().role==='viewer';
    const dialog=modal('第'+seg.id+'句 · 历史与回滚',`<p class="hint">回滚会生成待审新修订，旧确认和检查不会自动继承。历史只覆盖本次原型内操作。</p>${seg.history.map((h,n)=>`<div class="audit"><b>r${h.rev} · ${esc(h.reason)}</b><p>${esc(h.text)}</p><span class="hint">${time(h.start)} → ${time(h.end)}</span> <button type="button" data-restore="${n}" ${readonly||seg.escalated?'disabled':''}>恢复为新修订</button></div>`).join('')}`);
    dialog.querySelectorAll('[data-restore]').forEach(btn=>btn.onclick=()=>{
      const n=Number(btn.dataset.restore), target=seg.history[n];
      modal('确认回滚范围：第'+seg.id+'句',`<p class="hint">当前：${esc(seg.text)}</p><p>恢复内容：${esc(target.text)}</p><div class="issue">当前输入、规则与历史版本可能不同。恢复后需核实、重新确认与检查；现有导出文件保留，不能继续当作新版产物。</div>`,()=>{const r=D.rollback(seg.id,n);if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;},'恢复并重新审核');
    });
  }
  $('segmentList').addEventListener('change',event=>{const id=event.target.dataset.pick;if(!id)return;event.target.checked?selected.add(Number(id)):selected.delete(Number(id));});
  $('segmentList').addEventListener('click',event=>{
    const button=event.target.closest('button[data-action]');if(!button)return;
    const id=Number(button.closest('[data-id]').dataset.id),seg=D.get().segments.find(item=>item.id===id);
    switch(button.dataset.action){
      case 'seek':{
        const video=$('localVideo'); $('seekHint').textContent='第'+id+'句 · 示例定位 '+time(seg.start)+' 至 '+time(seg.end)+'；字幕与本地视频未验证匹配。';
        if(video.src&&Number.isFinite(video.duration)){video.currentTime=Math.min(seg.start,Math.max(0,video.duration-.1));video.play().catch(()=>{});}break;
      }
      case 'edit':edit(seg);break;
      case 'approve':act(D.approve(id));break;
      case 'reject':reject(seg);break;
      case 'undoReject':act(D.undoReject(id));break;
      case 'resolve':askNote(seg,'resolve');break;
      case 'escalate':askNote(seg,'escalate');break;
      case 'history':history(seg);break;
      case 'new':modal('发起第'+id+'句新修订','<p class="hint">原确认稿保留在历史中；新修订回到待审，当前范围确认和技术检查失效。</p>',()=>act(D.newRevision(id)),'创建待审修订');break;
      case 'compare':modal('重跑候选与人工稿比较',`<div class="audit">当前${seg.confirmed?'人工确认稿':'稿件'}：${esc(seg.text)}</div><div class="issue">新候选：${esc(seg.rerunText)}</div><p class="hint">不采用则原稿保持。采用只生成新的待审修订，不自动继承批准。</p>`,()=>{const r=D.adoptRerun(id);if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;},'采用为新待审修订');break;
    }
  });
  $('selectAll').onchange=event=>{const s=D.get(); selected=event.target.checked?new Set(s.segments.filter(seg=>!seg.confirmed).map(seg=>seg.id)):new Set();render();};
  $('batchAccept').onclick=()=>{
    const ids=[...selected],s=D.get();if(!ids.length)return message('reviewFeedback',{ok:false,message:'请先勾选候选，不会自动选择全部筛选结果。'});
    const rows=D.previewBatch(ids);
    modal('批量接受预览 · '+ids.length+'句',`<p class="hint">只处理明确选中范围；未决、升级、驳回或已确认项跳过，不静默清除问题。</p><table><thead><tr><th>字幕</th><th>内容</th><th>本次结果</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${row.id}</td><td>${esc(row.text)}</td><td>${row.blocked?esc('跳过：'+row.blocked):'可接受'}</td></tr>`).join('')}</tbody></table>`,()=>{
      const r=D.approveBatch(ids,s.rev);if(!r.ok){message('dialogFeedback',r);return false;}
      selected=new Set(r.rows.filter(row=>row.blocked).map(row=>row.id));act(r,'batchResult');return true;
    },'仅接受可处理项');
  };
  $('undoBatch').onclick=()=>modal('撤销最近一次批量接受','<p class="hint">只恢复本次成功且未另改的项，形成待审修订。已另行修改的项跳过。保留所有历史和接受记录，不恢复旧批准。</p>',()=>act(D.undoBatch(),'batchResult'),'撤销并重新审核');
  $('confirmTask').onclick=()=>{const s=D.get();modal('汇总确认当前源字幕范围',`<p>逐句确认 ${s.segments.filter(seg=>seg.confirmed).length} / ${s.segments.length}。</p><p class="hint">仍有未确认、驳回、问题或升级项时不能继续。确认仅用于当前源字幕版本，不是平台发布。</p>`,()=>{const r=D.confirmTask();if(!r.ok){message('dialogFeedback',r);return false;}act(r);return true;},'确认当前范围');};
  $('role').onchange=()=>act(D.setRole($('role').value));
  $('applyScenario').onclick=()=>{const scenario=$('scenario').value;modal('载入演示场景','<p class="hint">将重置本原型的示例审核数据。这个动作专用于场景测试，不是重跑ASR，不影响真实素材。要验证人工稿保护请使用“重新识别”。</p>',()=>{selected.clear();act(D.scenario(scenario));},'载入并重置示例');};
  $('rerun').onclick=()=>modal('重新识别（模拟）','<p class="hint">另存每句的比较候选；人工稿、确认状态和已有检查保持。只有你明确采用新候选时才建立新待审修订。</p>',()=>act(D.rerun()),'生成新比较候选');
  $('previewFile').onchange=()=>{const file=$('previewFile').files[0];if(!file)return;if(previewURL)URL.revokeObjectURL(previewURL);previewURL=URL.createObjectURL(file);$('localVideo').src=previewURL;$('localVideo').hidden=false;$('previewHint').hidden=true;$('seekHint').textContent='已选择本地视频 '+file.name+'，仅本机预览；构造字幕未与该片匹配。';};
  window.addEventListener('beforeunload',()=>{if(previewURL)URL.revokeObjectURL(previewURL);});
  render();
})();

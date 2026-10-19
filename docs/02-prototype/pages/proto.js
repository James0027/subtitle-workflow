/* 共享导航、对话框、素材准备、检查导出；全部业务服务为模拟。 */
(() => {
  'use strict';
  const D=window.SubDemo, $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels={draft:'待准备',ready:'可开始',running:'处理中',review:'候选待审',confirmed:'源字幕已确认',checked:'基础检查通过',exported:'源字幕文件已生成',failed:'处理失败',stopped:'按规则停止'};
  const roles={reviewer:'普通审核者',senior:'高级审核者',viewer:'只读查看者'};
  function shell() {
    const s=D.get();
    $('chrome').innerHTML=`<div class="banner">历史V1编辑器：已由动作与系统行为说明原型替代，不作为当前评审入口。<a href="blueprint.html">打开V2链路说明 →</a></div><header><div class="brand">字幕工作流<small>SUBTITLE WORKFLOW · 历史原型 V1</small></div><div class="top-actions"><span>身份（演示）：${esc(roles[s.role])}</span><span class="tag">修订 r${s.rev}</span><a href="legacy-index.html">V1旧任务入口</a></div></header>`;
    const pages=[['index','legacy-index.html','01 · V1旧任务入口'],['prepare','prepare.html','02 · 素材准备'],['workbench','workbench.html','03 · 字幕审阅'],['delivery','delivery.html','04 · 检查与导出']];
    $('sidebar').innerHTML=`<div class="nav-label">当前首批范围</div><nav aria-label="原型导航">${pages.map(p=>`<a href="${p[1]}" ${document.body.dataset.page===p[0]?'class="active" aria-current="page"':''}>${p[2]}</a>`).join('')}</nav><div class="nav-label" style="margin-top:24px">后续模块 · 未实现</div><div class="later">初翻 / 文化检测<br>单位格式 / 口语审校</div><div class="side-note">模型输出只是候选。<br>人工确认稿受保护。<br>源字幕导出 ≠ 平台发布。<br><br>构造数据，演示状态。<br>不会自动调用外部服务。</div>`;
  }
  function message(id,r) { const target=$(id); if(target) target.innerHTML=`<div class="message ${r.ok?'':'error'}">${esc(r.message)}</div>`; shell(); }
  function modal(title,body,callback,button='确认') {
    const old=$('activeDialog'); if(old) old.remove();
    $('dialogHost').innerHTML=`<dialog id="activeDialog" aria-labelledby="dialogTitle"><h2 id="dialogTitle">${esc(title)}</h2><div>${body}</div><div id="dialogFeedback" role="status" aria-live="polite"></div><div class="dialog-actions"><button type="button" id="dialogCancel">${callback?'取消':'关闭'}</button>${callback?`<button type="button" id="dialogConfirm" class="primary">${esc(button)}</button>`:''}</div></dialog>`;
    const dialog=$('activeDialog'); $('dialogCancel').onclick=()=>dialog.close();
    if(callback) $('dialogConfirm').onclick=()=>{const outcome=callback(dialog);if(outcome!==false) dialog.close();};
    dialog.showModal(); return dialog;
  }
  function logs(s) { return s.logs.map(item=>`<li><span class="mono">${esc(item.time)}</span> · ${esc(item.action)}</li>`).join(''); }
  function trace() {
    const s=D.get();
    const steps=s.task==='failed'?['输入准备：示例已就绪','识别调用：失败（构造超时）','结果整理：未执行','人工审核：未由此次运行推进']:s.task==='stopped'?['输入准备：示例已就绪','自动处理：达到停止条件（演示）','后续自动调用：未执行','恢复：等待人工明确处理']:s.task==='running'?['输入准备：示例已就绪','识别/对齐：模拟执行中','整理与检查：未执行','人工审核：等待候选']:['输入准备：示例已就绪','识别/对齐：构造候选已载入','基本检查：演示结果可读','人工审核：'+s.segments.filter(seg=>seg.confirmed).length+'/'+s.segments.length+'句已确认'];
    modal('处理步骤与执行记录',`<div class="banner">模拟轨迹，无真实ASR、模型版本或费用。停止数值/重试口径未配置，不以演示状态冒充实际控制。</div><ol class="hint">${steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol><hr class="divider"><ol class="logs">${logs(s)}</ol>`);
  }
  function renderIndex() {
    const s=D.get(); $('taskName').textContent=s.input.name; $('taskName').style.fontSize='19px';
    $('reviewCount').textContent=s.segments.filter(seg=>seg.confirmed).length+' / '+s.segments.length+' 句'; $('taskStatus').textContent=labels[s.task]||s.task; $('taskStatus').style.fontSize='20px';
    $('taskRows').innerHTML=`<tr><td><b>${esc(s.input.name)}</b><br><span class="hint">示例任务 · 输入修订 ${s.inputRevision}</span></td><td>${esc(s.input.videoName)}<br><span class="hint">${esc(s.input.language)} · ${esc({generate:'生成源字幕',align:'时间对齐',check:'内容核对',compare:'重新识别比较'}[s.input.mode])}</span></td><td><span class="tag info">${esc(labels[s.task])}</span><br><span class="hint">当前修订 r${s.rev}</span></td><td><a href="prepare.html">准备素材</a> · <a href="workbench.html">继续审阅</a> · <a href="delivery.html">查看导出</a></td></tr>`;
    $('resetDemo').onclick=()=>modal('重置本地示例任务',`<p class="hint">将清除本原型的构造修订和演示记录，不删除真实素材。此动作是演示场景重置，不是生产字幕回滚。</p>`,()=>{D.reset();shell();renderIndex();},'重置示例');
  }
  function inputValues() {
    const values={}; ['name','language','mode','videoName','audioName','subtitleName','scriptName','audioSource'].forEach(k=>values[k]=$(k).value.trim()); ['hasSound','matching'].forEach(k=>values[k]=$(k).checked);return values;
  }
  function saveAndCheck() {
    if(!$('materialForm').reportValidity()) return {ok:false,message:'请补充必填任务和视频信息'};
    const saved=D.materials(inputValues()); if(!saved.ok) return saved; return D.checkMaterials();
  }
  function renderPrepare() {
    const s=D.get(); ['name','language','mode','videoName','audioName','subtitleName','scriptName','audioSource'].forEach(k=>$(k).value=s.input[k]); ['hasSound','matching'].forEach(k=>$(k).checked=s.input[k]);
    $('materialForm').onsubmit=event=>event.preventDefault();
    $('videoFile').onchange=()=>{const file=$('videoFile').files[0];if(file) $('videoName').value=file.name;};
    $('checkMaterials').onclick=()=>message('materialResult',saveAndCheck());
    $('startTask').onclick=()=>{const checked=saveAndCheck();if(!checked.ok) return message('materialResult',checked);const r=D.start();if(r.ok) location.href='workbench.html';else message('materialResult',r);};
  }
  function renderDelivery() {
    const s=D.get(); shell();
    $('deliverySummary').innerHTML=`<div class="grid3"><div><span class="hint">当前源字幕修订</span><p><b>r${s.rev}</b> · 输入 ${s.inputRevision}</p></div><div><span class="hint">逐句审核</span><p>${s.segments.filter(seg=>seg.confirmed).length} / ${s.segments.length} 已确认</p></div><div><span class="hint">范围确认</span><p><span class="tag ${s.taskConfirmed?'ok':'warn'}">${s.taskConfirmed?'当前范围已确认':'尚未汇总确认'}</span></p></div></div>`;
    if(s.qc) $('validation').innerHTML=`<div class="message ${s.qc.ok?'':'error'}">${s.qc.ok?'通过：当前版本基础检查。':esc(s.qc.issues.join('；'))}<br><span class="hint">${esc(s.qc.scope)} · 对应 r${s.qc.rev}</span></div>`;
    else $('validation').innerHTML='<p class="hint">当前修订尚无有效检查结果。</p>';
    $('exportFile').disabled=!(s.qc?.ok && s.qc.rev===s.rev && s.taskConfirmed && s.role!=='viewer');
    $('exportHistory').innerHTML=s.exports.length?`<div class="table-wrap"><table><thead><tr><th>历史文件</th><th>对应版本</th><th>身份</th></tr></thead><tbody>${s.exports.map(ex=>`<tr><td>${esc(ex.filename)}</td><td>r${ex.rev}</td><td>${esc(ex.scope)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="hint">还没有生成记录。</p>';
    $('deliveryLogs').innerHTML=logs(s);
  }
  function bindDelivery() {
    $('validate').onclick=()=>{const r=D.validate($('qcFault').checked);renderDelivery();message('validation',r);};
    $('qcFault').onchange=()=>{const r=D.validate($('qcFault').checked);renderDelivery();message('validation',r);};
    $('exportFile').onclick=()=>{const r=D.exportFile($('format').value,$('exportFault').checked);renderDelivery();message('exportResult',r);if(!r.ok) return;const blob=new Blob([r.content],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=r.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);};
  }
  document.addEventListener('click',event=>{if(event.target.closest('a[href$=".html"]')) D.save();});
  window.addEventListener('beforeunload',D.save);
  shell(); const page=document.body.dataset.page;
  if(page==='index') renderIndex();if(page==='prepare') renderPrepare();if(page==='delivery'){renderDelivery();bindDelivery();}
  if($('showTrace')) $('showTrace').onclick=trace;
  window.Proto={esc,$,message,modal,shell,trace,labels};
})();

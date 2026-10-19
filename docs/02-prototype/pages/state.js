/* 本地交互模型：仅演示行为，不是生产鉴权、真实ASR或规则引擎。 */
(() => {
  'use strict';
  const KEY = 'subtitle-prototype-v1';
  const clone = value => JSON.parse(JSON.stringify(value));
  const fixtures = () => [
    ['你终于回来了。', 1, 3.2, ''],
    ['沈先生，别再追了。', 4, 7.2, 'uncertain'],
    ['这笔账，算在顾晚身上。', 8.1, 11.5, 'evidence'],
    ['顾晚，你当真不记得我？', 12, 15.4, 'conflict'],
    ['我没答应他。', 16, 18.8, ''],
    ['明天，我们一起回家。', 20, 23.5, '']
  ].map((v, n) => ({ id:n + 1, original:v[0], text:v[0], start:v[1], end:v[2], issue:v[3], confirmed:false, rejected:false, escalated:false, note:'', history:[{text:v[0], start:v[1], end:v[2], reason:'初始AI候选（构造）', rev:1}], lastChangeRev:1 }));
  const seed = () => ({version:1, rev:1, role:'reviewer', task:'review', taskConfirmed:false, inputRevision:1, checkedInput:false, runs:1, scenario:'mixed', qc:null, exports:[], lastBatch:null, segments:fixtures(), logs:[{time:'演示初始', action:'载入构造候选；没有调用ASR'}], input:{name:'演示短剧 · 第01集', language:'普通话（演示）', videoName:'示例短剧_ep01.mp4', audioName:'', subtitleName:'', scriptName:'角色表（缺失演示）', audioSource:'embedded', hasSound:true, matching:true, mode:'generate'}});
  let s;
  try {
    const fromWindow = window.name.startsWith(KEY + ':') ? window.name.slice(KEY.length + 1) : null;
    const saved = fromWindow || localStorage.getItem(KEY);
    s = saved ? JSON.parse(saved) : seed();
    if (s.version !== 1 || !Array.isArray(s.segments)) s = seed();
  } catch { s = seed(); }
  function persist() {
    const json = JSON.stringify(s);
    try { localStorage.setItem(KEY, json); } catch { /* file://可能禁用存储 */ }
    try { window.name = KEY + ':' + json; } catch { /* 使用当前页面内存 */ }
  }
  function log(action) { s.logs.unshift({time:new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date()), action}); s.logs = s.logs.slice(0,100); }
  function result(ok, message, extra = {}) { persist(); return {ok, message, ...extra}; }
  function deny(message) { log('拒绝操作：' + message); return result(false,message); }
  function canWrite() { return s.role !== 'viewer'; }
  function reviewing() { return !['running','failed','stopped','ready','draft'].includes(s.task); }
  function guard() { if (!canWrite()) return '只读查看者没有写入或确认权限（模拟）'; if (!reviewing()) return '当前运行尚未产生可审核结果，请先完成或恢复处理'; return ''; }
  function touch(reason) { s.rev++; s.taskConfirmed = false; s.qc = null; s.task = 'review'; log(reason); }
  function history(seg,reason) { seg.history.push({text:seg.text,start:seg.start,end:seg.end,reason,rev:s.rev,confirmed:seg.confirmed}); seg.history = seg.history.slice(-20); }
  function eligibility(seg) { if (seg.confirmed) return '已经确认'; if (seg.rejected) return '候选已驳回'; if (seg.escalated) return '升级问题未解决'; if (seg.issue) return '待解决：' + ({uncertain:'低置信/不确定',evidence:'证据缺失',conflict:'规则冲突'}[seg.issue] || seg.issue); return ''; }
  function find(id) { return s.segments.find(seg => seg.id === Number(id)); }
  const api = {
    get:() => clone(s),
    save:persist,
    reset() { s = seed(); log('用户明确重置原型示例；不影响真实文件'); return result(true,'示例任务已重置'); },
    setRole(role) { if (!['reviewer','senior','viewer'].includes(role)) return deny('未知演示身份'); s.role=role; log('切换演示身份：'+role); return result(true,'演示身份已切换'); },
    materials(input) {
      if (!canWrite()) return deny('只读身份不能改素材');
      const changed = JSON.stringify(input) !== JSON.stringify(s.input);
      if (changed) {
        s.inputRevision++; touch('用户修改素材/目标，新输入修订 '+s.inputRevision+'；保留原人工稿快照');
        s.segments.forEach(seg => { history(seg,'更换输入前的历史稿'); seg.confirmed=false; seg.lastChangeRev=s.rev; });
      }
      s.input=clone(input); s.checkedInput=false;
      return result(true,'素材信息已保存' + (changed ? '；新输入需要重新审核，历史稿仍保留' : ''));
    },
    checkMaterials() {
      if (!canWrite()) return deny('只读身份不能确认素材');
      const errors=[]; const i=s.input;
      if (!i.videoName.trim()) errors.push('缺少视频名称');
      if (!i.hasSound) errors.push('所选来源没有可用声音，请更换或补充音轨');
      if (!i.matching) errors.push('素材对应或时间关系未确认');
      if (i.audioSource==='external' && !i.audioName.trim()) errors.push('选择独立音轨时需提供音轨名称');
      if (['align','check'].includes(i.mode) && !i.subtitleName.trim()) errors.push('核对/对齐任务需要已有字幕');
      s.checkedInput=errors.length===0; if (s.checkedInput) s.task='ready';
      log('素材检查（演示条件）：'+(errors.join('；') || '满足本次输入前提'));
      return result(!errors.length,errors.length ? errors.join('；') : '输入前提满足（演示）。未进行媒体实测，可开始模拟处理。');
    },
    start() { if (!canWrite()) return deny('只读身份不能开始'); if (!s.checkedInput) return deny('请先检查当前素材'); if(s.task==='running') return deny('此运行已开始，请勿重复发起'); s.task='running'; s.runs++; log('开始模拟运行 '+s.runs); return result(true,'运行已开始（模拟）'); },
    finish() {
      if (!canWrite() || s.task!=='running') return deny('当前没有可完成的模拟运行');
      if (s.segments.some(seg=>seg.confirmed)) { s.segments.forEach(seg=>seg.rerunText=seg.text.replace(/。$/,'')+'（重跑候选）'); }
      else { s.segments=fixtures(); if (s.scenario==='normal') s.segments.forEach(seg=>seg.issue=''); touch('新运行生成独立候选'); }
      s.task='review'; log('模拟处理完成；结果待审，不代表识别正确'); return result(true,'候选已就绪，请人工审阅');
    },
    scenario(kind) {
      if (!canWrite()) return deny('只读身份不能载入演示场景');
      const role=s.role; const input=clone(s.input); s=seed(); s.role=role; s.input=input; s.scenario=kind;
      if (kind==='normal') s.segments.forEach(seg=>seg.issue='');
      if (kind==='failure') s.task='failed'; if (kind==='stop') s.task='stopped';
      log('用户明确载入构造场景：'+kind+'；示例审核记录已重置'); return result(true,'场景已载入；模拟条件，不影响本地文件');
    },
    recover() { if (!canWrite()) return deny('只读身份不能恢复'); if (!['failed','stopped'].includes(s.task)) return deny('当前无需恢复'); s.task='review'; s.runs++; log('用户修正依赖并明确发起新运行（模拟）；非自动无限重试'); return result(true,'模拟新运行完成，进入候选待审；未重置实际预算或生产重试计数'); },
    edit(id,text,start,end) {
      const error=guard(); if(error) return deny(error); const seg=find(id);
      if (!seg) return deny('字幕不存在'); if(seg.confirmed) return deny('人工确认稿不可直接覆盖，请先显式发起新修订');
      if(seg.escalated) return deny('升级处理中，先等待裁决');
      if(!text.trim() || !Number.isFinite(start) || !Number.isFinite(end) || start<0 || end<=start || end>60) return deny('文字不能为空；演示时间须满足 0≤起点<终点≤60秒');
      history(seg,'编辑前'); touch('人工保存第'+id+'句草稿，不自动确认');
      Object.assign(seg,{text:text.trim(),start,end,rejected:false,lastChangeRev:s.rev}); return result(true,'草稿已保存，疑问仍需单独核实，尚未确认');
    },
    newRevision(id) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg) return deny('字幕不存在'); history(seg,'原确认稿保留'); touch('用户显式发起第'+id+'句新修订'); seg.confirmed=false; seg.lastChangeRev=s.rev; return result(true,'已进入新修订；原确认稿保留在历史中'); },
    resolve(id,note) {
      const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg) return deny('字幕不存在');
      if(seg.confirmed) return deny('确认稿不能直接改问题标记');
      if((seg.issue==='conflict' || seg.escalated) && s.role!=='senior') return deny('此项需高级审核者裁决，普通审核不能绕过');
      if(!note.trim()) return deny('请填写核实依据或裁决理由');
      touch('第'+id+'句问题已由人工核实：'+note.trim()); seg.issue=''; seg.escalated=false; seg.rejected=false; seg.note=note.trim(); seg.lastChangeRev=s.rev;
      return result(true,'依据已记录，恢复待审；仍需明确接受/确认');
    },
    escalate(id,reason) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg || seg.confirmed) return deny('请在待审修订上升级'); if(!reason.trim()) return deny('请填写升级理由'); touch('第'+id+'句升级给高级审核职责（演示）；'+reason.trim()); seg.escalated=true; seg.lastChangeRev=s.rev; return result(true,'已进入待高级审核状态；真实派单未接入'); },
    approve(id) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg) return deny('字幕不存在'); const blocked=eligibility(seg); if(blocked) return deny(blocked); history(seg,'接受前候选'); touch('第'+id+'句逐条接受'); seg.confirmed=true; seg.lastChangeRev=s.rev; history(seg,'人工已确认'); return result(true,'已确认当前句版本；整份任务仍需汇总检查'); },
    previewBatch(ids) { return ids.map(id=>{const seg=find(id); return {id:Number(id),text:seg?.text || '',blocked:seg?eligibility(seg):'不存在'};}); },
    approveBatch(ids,expectedRev) {
      const error=guard(); if(error) return deny(error); if(expectedRev!==s.rev) return deny('预览后版本已变化，请重新预览');
      const rows=api.previewBatch(ids); const good=rows.filter(row=>!row.blocked); if(!good.length) return deny('没有可接受项，未决/已确认项保持原状');
      good.forEach(row=>history(find(row.id),'批量接受前')); touch('批量接受：'+good.map(row=>row.id).join(','));
      good.forEach(row=>{const seg=find(row.id); seg.confirmed=true; seg.lastChangeRev=s.rev; history(seg,'批量接受后确认');});
      s.lastBatch={ids:good.map(row=>row.id),rev:s.rev}; return result(true,'成功 '+good.length+' 条；跳过 '+(rows.length-good.length)+' 条。', {rows});
    },
    undoBatch() {
      const error=guard(); if(error) return deny(error); if(!s.lastBatch) return deny('没有可撤销的批量操作');
      const batch=s.lastBatch; const eligible=batch.ids.filter(id=>find(id)?.lastChangeRev===batch.rev && find(id)?.confirmed);
      if(!eligible.length) return deny('这些字幕已另行修改，未自动覆盖；请逐条查看历史');
      eligible.forEach(id=>history(find(id),'撤销前确认稿')); touch('撤销批量接受，生成待审修订：'+eligible.join(','));
      eligible.forEach(id=>{find(id).confirmed=false;find(id).lastChangeRev=s.rev;}); s.lastBatch=null;
      return result(true,'恢复待审 '+eligible.length+' 条，跳过 '+(batch.ids.length-eligible.length)+' 条；旧批准不继承');
    },
    reject(id,reason) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg || seg.confirmed || seg.escalated) return deny('仅可驳回可操作的待审候选'); if(!reason.trim()) return deny('请记录驳回原因'); history(seg,'驳回前'); touch('驳回第'+id+'句：'+reason.trim()); seg.rejected=true; seg.lastChangeRev=s.rev; return result(true,'候选已驳回，素材与历史保留；该句仍未完成'); },
    undoReject(id) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg?.rejected) return deny('当前候选未被驳回'); touch('撤销第'+id+'句驳回'); seg.rejected=false; seg.lastChangeRev=s.rev; return result(true,'已恢复待审，不自动确认'); },
    rollback(id,index) {
      const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg) return deny('字幕不存在'); if(seg.escalated) return deny('升级未决时不能回滚绕过裁决');
      if(!seg.history[index]) return deny('历史版本不存在'); const target=clone(seg.history[index]); history(seg,'回滚前'); touch('第'+id+'句从历史恢复为新修订；旧检查失效');
      Object.assign(seg,{text:target.text,start:target.start,end:target.end,confirmed:false,rejected:false,issue:'uncertain',note:'回滚后请重新核对内容与当前输入',lastChangeRev:s.rev}); return result(true,'已恢复为新待审修订，请核实再确认；历史与导出文件仍保留');
    },
    rerun() { const error=guard(); if(error) return deny(error); s.runs++; s.segments.forEach(seg=>seg.rerunText=seg.text.replace(/。$/,'')+'（重跑候选）'); log('重新识别（模拟）只生成比较候选；人工稿和原批准保持不变'); return result(true,'新候选已另存，可逐句比较；没有覆盖人工稿'); },
    adoptRerun(id) { const error=guard(); if(error) return deny(error); const seg=find(id); if(!seg?.rerunText) return deny('没有重跑候选'); if(seg.escalated) return deny('请先完成升级裁决'); history(seg,'采用重跑前的稿件'); touch('用户采用第'+id+'句重跑候选为新待审修订'); Object.assign(seg,{text:seg.rerunText,rerunText:null,confirmed:false,rejected:false,issue:'uncertain',lastChangeRev:s.rev}); return result(true,'新候选已成为待审修订，原稿留在历史；需核实和重新确认'); },
    confirmTask() { const error=guard(); if(error) return deny(error); const unresolved=s.segments.filter(seg=>!seg.confirmed || seg.issue || seg.escalated || seg.rejected); if(unresolved.length) return deny('仍有 '+unresolved.length+' 句未完成审核/问题处理，不能汇总确认'); s.taskConfirmed=true;s.task='confirmed';log('人工汇总确认当前源字幕范围，修订 '+s.rev); return result(true,'当前源字幕范围已确认；尚未通过技术检查或发布'); },
    validate(fault) {
      if(!canWrite()) return deny('只读身份只能查看已有检查');
      const issues=[];
      if(!s.taskConfirmed || s.segments.some(seg=>!seg.confirmed)) issues.push('当前范围未完成汇总确认');
      s.segments.forEach(seg=>{if(!seg.text.trim() || seg.start<0 || seg.end<=seg.start || seg.end>60) issues.push('第'+seg.id+'句文字或时间结构不合法');});
      for(let n=1;n<s.segments.length;n++) if(s.segments[n].start<s.segments[n-1].start) issues.push('字幕起点顺序错误');
      if(fault) issues.push('适用平台规范版本缺失（故障演示）；不能宣称通过平台检查');
      s.qc={rev:s.rev,ok:!issues.length,issues,scope:'演示60秒范围：文本非空、起止和顺序、审核门禁；非真实平台验收'};
      if(!issues.length) s.task='checked'; log('只读检查：'+(issues.join('；') || '当前版本基础检查通过（非平台验收）'));
      return result(!issues.length,issues.length?issues.join('；'):'当前源字幕版本基础检查通过；不代表内容正确或平台验收', {issues});
    },
    exportFile(format,fault) {
      if(!canWrite()) return deny('只读身份没有导出权限（演示）');
      if(!s.qc?.ok || s.qc.rev!==s.rev || !s.taskConfirmed) return deny('请先确认并检查当前版本；旧检查不能用于新修订');
      if(fault) { log('文件生成失败（演示），未重新识别'); return result(false,'文件生成失败（模拟）。取消故障条件后重新生成即可，识别次数不变。'); }
      if(!['srt','vtt'].includes(format)) return deny('不支持的演示格式');
      const timestamp=(sec,separator)=>{const ms=Math.round(sec*1000);return [Math.floor(ms/3600000),Math.floor(ms/60000)%60,Math.floor(ms/1000)%60].map(n=>String(n).padStart(2,'0')).join(':')+separator+String(ms%1000).padStart(3,'0');};
      const content=(format==='vtt'?'WEBVTT\n\n':'')+s.segments.map((seg,n)=>`${n+1}\n${timestamp(seg.start,format==='vtt'?'.':',')} --> ${timestamp(seg.end,format==='vtt'?'.':',')}\n${seg.text}\n`).join('\n');
      const filename='DEMO_source_r'+s.rev+'.'+format; s.exports.unshift({filename,rev:s.rev,format,scope:'构造源字幕，不是已发布终版'});s.task='exported';log('生成源字幕文件 '+filename+'；浏览器下载发起不证明已保存');return result(true,'已生成构造源字幕，可下载；不等于已发布',{content,filename});
    }
  };
  persist(); window.SubDemo=api;
})();

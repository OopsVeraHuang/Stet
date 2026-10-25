'use strict';
async function refreshStudio(){
 const data=await api('studio');
 $('studiohealth').textContent=`${data.deployment==='cloud'?'云端':'本地'} · ${data.counts.chat} 条聊天 · ${data.counts.books} 本书 · ${data.counts.studio_events} 条工作室记录 · ${data.active_jobs} 个进行中任务`;
 const list=$('studiotasks');list.replaceChildren();
 for(const t of data.tasks){
  const card=el('article',undefined,'card');card.append(el('h3',t.title),el('p',t.request),el('small',`${time(t.created)} · ${t.actor}`),
   button('请 Agent 检查',()=>{if($('prompt').value.trim())throw Error('对话里还有未发送的草稿，请先处理后再带入维修任务。');$('prompt').value=`请检查工作室任务 ${t.id}：${t.title}。先用 continuity_studio 读取任务与有关源码，再根据证据准备修复草稿；不要声称已经上线。`;tab('chat');invalidateQuote();$('prompt').focus();notify('已带入对话。可选 GPT 订阅模型，再点击发送；这会使用所选模型额度。');}),
   button('查看草稿与检查结果',async()=>{const r=await api('studio',{action:'read',task_id:t.id});$('studiodetail').textContent=r.proposals.length?r.proposals.map(p=>`${time(p.created)} · ${p.actor}\n文件：${p.path}\n检查：${p.validation}\n理由：${p.reason}\n${p.diff}\n尚未部署`).join('\n\n'):'暂无修复草稿；登记任务不会自动调用模型。';$('studiodetail').closest('details').open=true;$('studiodetail').scrollIntoView({block:'nearest'});}));list.append(card);
 }
 if(!data.tasks.length)list.append(el('p','这里可以登记阅读器、界面或连接问题。Agent 的修复草稿和操作记录会留在这里。'));
}
async function showStudioLog(){const report=await api('studio/export');$('studiolog').textContent=JSON.stringify(report,null,2);}
function initStudio(){
 const nav=button('工作室',()=>{undockChat();tab('studio');refreshStudio().catch(e=>notify(e.message));});nav.dataset.tab='studio';document.querySelector('nav').append(nav);
 const panel=el('section',undefined,'panel');panel.id='studio';
 panel.innerHTML='<div class="heading"><div><h2>Agent 的工作室</h2><p>检查问题、准备修复，把做过的事记清楚。</p></div></div><p id="studiohealth" class="footnote"></p><p class="callout">当前可以查看源码、登记问题和保存修复草稿。正式应用仍由审核后的部署更新；语法检查不等于行为测试通过。不会在空闲时自动消耗模型额度。</p><article class="card"><label>任务标题<input id="studiotitle" maxlength="120" placeholder="例如：手机阅读时按钮被挡住"></label><label>问题与希望的结果<textarea id="studiorequest" rows="3" maxlength="6000" placeholder="在哪个页面、怎样触发、你希望怎样改"></textarea></label><button id="studiocreate" class="primary">登记问题</button></article><div id="studiotasks" class="settings-grid"></div><details><summary>修复草稿详情</summary><pre id="studiodetail" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details><details><summary>操作日志与求助包</summary><p class="footnote">记录工作室工具调用、失败原因、源码版本、差异和检查结果；敏感凭据会脱敏。不是模型内部推理，也不覆盖工作室以外的操作。</p><button id="studiologload">查看记录</button><button id="studioexport">导出求助包</button><pre id="studiolog" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
 document.querySelector('main').append(panel);
 $('studiocreate').onclick=async()=>{const b=$('studiocreate');b.disabled=true;try{await api('studio',{action:'task',title:$('studiotitle').value,request:$('studiorequest').value});$('studiotitle').value='';$('studiorequest').value='';await refreshStudio();notify('维修任务已登记；尚未调用模型或修改正式代码。');}catch(e){notify(e.message);}finally{b.disabled=false;}};
 $('studiologload').onclick=()=>showStudioLog().catch(e=>notify(e.message));
 $('studioexport').onclick=async()=>{try{const report=await api('studio/export');await downloadBlob(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),'Agent-工作室求助包-'+new Date().toISOString().slice(0,10)+'.json');}catch(e){notify(e.message);}};
}

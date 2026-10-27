'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="continuity-token"]').content;
let state, selected = new Map(), offset = 0, mode = 'literal', activeJob = null, polling = false, quoteReady = false;
let lastFailed = null, retryOf = null, submittingJob = false;
// A draft belongs to this tab and server session; never reuse it in another profile.
const textDraftKey='continuity-text-draft:'+token;
function saveTextDraft(){try{if($('prompt').value)sessionStorage.setItem(textDraftKey,$('prompt').value);else sessionStorage.removeItem(textDraftKey);}catch{}}
function restoreTextDraft(){try{const draft=sessionStorage.getItem(textDraftKey);if(draft&&!$('prompt').value){$('prompt').value=draft;$('prompt').dispatchEvent(new Event('input'));notify('已恢复未发送的文字草稿；引用和附件请重新选择。');}}catch{}}
window.addEventListener('pagehide',saveTextDraft);
let noticeTimer;
let lastSyncedMessage=0,syncBusy=false;
const chatReads=new Set();
let historyPending=null,pollTimer=null,resumingChat=false;
function notify(message) { $('notice').textContent = message; $('notice').hidden = false; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('notice').hidden = true, 14000); }
async function api(path, data) {
  const controller=data===undefined?new AbortController():null;
  const isChatRead=/^(history|job|sync)(\?|$)/.test(path);
  if(controller&&isChatRead)chatReads.add(controller);
  const timer=controller?setTimeout(()=>controller.abort(),20000):null;
  try {
  const result = await fetch('/api/' + path, {method:data === undefined ? 'GET':'POST', headers:{'X-Continuity-Token':token,'Content-Type':'application/json'}, ...(controller?{signal:controller.signal}:{body:JSON.stringify(data)})});
  const value = await result.json();
  if (!result.ok) throw Error(value.error || '本地请求未完成');
  return value;
  }finally{clearTimeout(timer);if(controller)chatReads.delete(controller);}
}
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent=text; if(cls) node.className=cls; return node; }
function button(text, action, cls='quiet') { const node=el('button',text,cls); node.type='button'; node.addEventListener('click',()=>Promise.resolve().then(action).catch(e=>notify(e.message))); return node; }
function money(n) { return '¥' + Number(n || 0).toFixed(4); }
function time(iso) { return new Date(iso).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}); }
function tab(name) { document.querySelectorAll('.panel').forEach(e=>e.classList.toggle('active',e.id===name)); document.querySelectorAll('nav button').forEach(e=>e.classList.toggle('active',e.dataset.tab===name)); document.body.dataset.page=name;document.dispatchEvent(new CustomEvent('continuity-tab',{detail:name})); }
document.querySelectorAll('nav button').forEach(e=>e.addEventListener('click',()=>tab(e.dataset.tab)));
function invalidateQuote() { quoteReady=false; $('send').disabled=!hasDraft()||!!activeJob||submittingJob||imageUploadBusy||documentBusy||readerTextBusy; $('quote').textContent='发送时自动找回相关原文，Agent 可以自主补查；费用会逐笔记录。'; $('recallpreview').hidden=true; if(state?.brains?.[state.config.brain]?.provider==='codex')$('quote').textContent='发送将消耗与 Codex 共用的订阅额度；联网搜索费用仍计入本地预算。'; }
function renderSelected() {
  retryOf = null;
  $('selected').replaceChildren();
  if (!selected.size) $('selected').append(el('span','自动记忆已开启 · 不用手动挑选'));
  let i=0; for(const [id,item] of selected) $('selected').append(button(`记忆${++i} · ${item.speaker||'待核对'} · 第 ${item.number} 段 ×`,()=>{selected.delete(id);renderSelected();}));
  invalidateQuote();
}
function choose(item) { if(selected.has(item.id)) {notify('这一段已经选中了。');return;} if(selected.size>=64) throw Error('手动选择已达到保护上限；请减少片段。'); selected.set(item.id,item); renderSelected(); notify('已加入本轮记忆；到「对话」预览后再发送。'); }
function rawText(item) {
  const node=el('div',undefined,'text'), points=Array.from(item.raw_text); let at=0;
  for(const span of item.cherished || []) {node.append(document.createTextNode(points.slice(at,span.start).join('')));node.append(el('mark',points.slice(span.start,span.end).join('')));at=span.end;}
  node.append(document.createTextNode(points.slice(at).join(''))); return node;
}
function card(item, focused=false) {
  const node=el('article',undefined,'memory'+(focused?' focus':''));
  const when=item.timestamp?.raw ? item.timestamp.timezone ? ` · 北京时间 ${time(item.timestamp.raw)}` : ` · 原文时间 ${item.timestamp.raw}（时区未知）` : ' · 无已确认的逐条时间';
  node.append(el('div',`${item.filename} · 第 ${item.number} 段`,'meta'));
  node.append(el('div',`${item.speaker||'说话人待核对'}${when}${item.issues?.length?' · 有待核对标记':''}${item.score!==undefined?' · 相似度 '+item.score:''}`,'meta'));
  if(item.category)node.append(el('div',item.category,'meta'));
  if(item.time_context?.relative_to_reference)node.append(el('div',item.time_context.relative_to_reference+'（消息时间，非事件时间）','meta'));
  if(item.location)node.append(el('div',item.location.place?`发言地点线索：${item.location.place}${item.location.parent?' · '+item.location.parent:''}（${item.location.status==='last_reported'?'用户当时报告':'由上次报告延续，未逐条确认'}）`:'发言地点：未确认','meta'));
  node.append(rawText(item));
  appendWebSources(node,item.web_sources||[]);
  for(const c of item.corrections||[]){const note=el('div',undefined,'correction-note');note.append(el('strong','相关的有效澄清 · '+c.topic),el('p',c.text),button('查看澄清原话',()=>showContext(c.source)));node.append(note);}
  const actions=el('div',undefined,'actions');actions.append(button('查看附近原文',()=>showContext(item.id)),button('带入这次对话',()=>choose(item)));node.append(actions);return node;
}
async function showContext(id) { const items=await api('context?id='+encodeURIComponent(id));$('contextbody').replaceChildren(...items.map(p=>card(p,p.id===id))); if(!$('contextdialog').open)$('contextdialog').showModal(); }
$('closecontext').onclick=()=>$('contextdialog').close();
function renderResults(result) { $('results').replaceChildren(...result.items.map(p=>card(p))); if(!result.items.length)$('results').append(el('div','没有找到匹配原文。试试更短的词句；没有匹配不等于没有这段经历。','empty')); $('resultinfo').textContent=`${result.scope} · ${result.total} 段${mode==='literal'?' · 完整词句匹配，区分大小写':''}`; $('prev').disabled=mode!=='literal'||offset===0; $('next').disabled=mode!=='literal'||!result.has_more; $('page').textContent=mode==='literal'?`第 ${Math.floor(offset/20)+1} 页`:'样本视图'; }
async function literal() { mode='literal'; const params=new URLSearchParams({q:$('query').value,source:$('source').value,cherished:$('cherished').checked?'1':'0',offset:String(offset)});renderResults(await api('search?'+params)); }
$('searchform').onsubmit=e=>{e.preventDefault();offset=0;literal().catch(e=>notify(e.message));};
for(const id of ['source','cherished'])$(id).onchange=()=>{offset=0;literal().catch(e=>notify(e.message));};
$('prev').onclick=()=>{offset=Math.max(0,offset-20);literal().catch(e=>notify(e.message));};
$('next').onclick=()=>{offset+=20;literal().catch(e=>notify(e.message));};
$('autorecall').onclick=async()=>{try{const data=await api('recall?q='+encodeURIComponent($('query').value));mode='auto';renderResults(data);}catch(e){notify(e.message);}};
$('sample').onclick=async()=>{try{const data=await api('sample');mode='sample';renderResults({items:data.items,total:data.items.length,scope:`取自当前导入来源的 ${data.items.length} 段样本；标红优先，其次按段落顺序`});$('sampleinfo').textContent=`全新建立样本索引最多预留约 ${money(data.ceiling_rmb)}；已缓存的段落不重复发送。`; }catch(e){notify(e.message);}};
function createChatMessage(row) {
  const node=el('article',undefined,'message '+row.role);node.id='chat-message-'+row.id;node.dataset.messageId=row.id;node.tabIndex=-1;node.append(el('div',`${row.role==='user'?'用户':'Agent'} · ${time(row.time)}`,'meta'));const bubble=el('div',undefined,'bubble');appendCitedText(bubble,row.text,row.refs,showContext,row.web_sources||[]);node.append(bubble);appendImages(node,row.attachments||[]);appendDocuments(node,row.documents||[]);appendReading(node,bubble,row.reading);if(row.role==='assistant')node.append(el('small',state.brains?.[row.brain]?.label||row.brain||'Gemini','footnote'));appendWebSources(node,row.web_sources||[]);if(row.refs.length){const detail=el('details');detail.append(el('summary',`查看本次参考的 ${row.refs.length} 段原文`,'footnote'));const refs=el('div',undefined,'references');row.refs.forEach((p,i)=>refs.append(button(`记忆${i+1} · 原文`,()=>showContext(p.id))));detail.append(refs);node.append(detail);}return node;
}
function markHistoryGaps(){
  document.querySelectorAll('#messages>.chat-history-gap').forEach(n=>n.remove());
  let previous=null;
  for(const node of $('messages').querySelectorAll(':scope>.message[data-message-id]')){
    if(previous&&Number(node.dataset.messageId)>Number(previous.dataset.messageId)+1)
      $('messages').insertBefore(el('div','此处还有未加载的历史消息','chat-history-gap'),node);
    previous=node;
  }
}
async function locateChatMessage(id) {
  if($('chat').classList.contains('reader-chat'))undockChat();
  tab('chat');
  await renderHistory();
  if(!$('chat-message-'+id)){
    const rows=await api('history/around?id='+encodeURIComponent(id));
    for(const row of rows){
      if($('chat-message-'+row.id))continue;
      const next=[...$('messages').querySelectorAll('[data-message-id]')].find(n=>Number(n.dataset.messageId)>row.id);
      $('messages').insertBefore(createChatMessage(row),next||null);
    }
  }
  markHistoryGaps();
  const target=$('chat-message-'+id);
  if(!target)throw Error('原消息已不存在，笔记中的摘录仍然保留。');
  requestAnimationFrame(()=>{target.scrollIntoView({block:'center',behavior:'instant'});target.focus({preventScroll:true});target.classList.add('study-located');setTimeout(()=>target.classList.remove('study-located'),4000);});
}
async function renderHistory() {
  if(historyPending)return historyPending;
  historyPending=loadHistory();
  try{return await historyPending;}finally{historyPending=null;}
}
async function loadHistory() {
  const initial=!lastSyncedMessage,box=$('messages'),near=box.scrollHeight-box.clientHeight-box.scrollTop<100;
  let rows;
  do {
  rows=await api('history?view=chat&after='+lastSyncedMessage);if(!rows.length)break;
  lastFailed=rows.at(-1)?.role==='user'?rows.at(-1):null;
  $('restore').hidden=!lastFailed||!!activeJob;
  if(!lastSyncedMessage)$('messages').replaceChildren();
  for(const row of rows)if(!$('chat-message-'+row.id))$('messages').append(createChatMessage(row));
  markHistoryGaps();
  lastSyncedMessage=rows.at(-1).id;
  if(initial||near)$('messages').scrollTop=$('messages').scrollHeight;
  }while(rows.length===100);
}
async function renderCorrections(){
  const rows=await api('corrections');
  $('correctioncount').textContent=`${rows.filter(r=>r.status==='active').length} 条有效澄清 · 每轮优先带入`;
  $('correctionlist').replaceChildren();
  if(!rows.length){$('correctionlist').append(el('p','还没有保存的澄清。直接在聊天里告诉 Agent，例如：“纠正一下记忆：我现在……，以后以这个为准。”','footnote'));return;}
  for(const r of [...rows].reverse()){
    const card=el('article',undefined,'memory');
    card.append(el('div',`${r.status==='active'?'当前优先':'已撤回'} · ${r.topic} · ${time(r.created_at)}`,'meta'),el('div',r.text,'text'));
    const actions=el('div',undefined,'actions');
    actions.append(button('查看原话',()=>showContext('chat:'+r.source_chat_id)),button(r.status==='active'?'撤回这条澄清':'恢复生效',async()=>{
      await api('corrections/change',{id:r.id,status:r.status==='active'?'revoked':'active'});
      await renderCorrections();await refresh();invalidateQuote();notify('澄清状态已更新。之后的新请求会使用新的有效版本。');
    }));card.append(actions);$('correctionlist').append(card);
  }
}
function fillSettings() {for(const key of Object.keys(state.config)) if($(key)) {if(['paid_enabled','search_enabled','budget_enforced'].includes(key))$(key).checked=state.config[key];else $(key).value=state.config[key]??'';}}
async function refresh() {
  state=await api('status');const engine=state.brains?.[state.config.brain]?.provider;const generation=state.connection?.generation;
  const googleState=generation?.status==='running'?'Google 正在响应':generation&&generation.status!=='success'?'最近一次 Google 生成请求未完成':generation?.status==='success'?'最近一次 Google 请求已返回':state.connection?.ok?'Google 模型信息可读取':'Gemini';
  $('connection').textContent=activeJob?'模型任务进行中':engine==='codex'?'本地已连接 · GPT 使用 Codex 订阅':engine==='deepseek'?(state.deepseek_key_present?'本地已连接 · DeepSeek 密钥已保存':'本地已连接 · 请先填写 DeepSeek 密钥'):'本地已连接 · '+googleState;
  if(state.deployment==='cloud'){$('connection').textContent=$('connection').textContent.replace('本地','云端');document.querySelector('#chat>.callout').textContent='已连接你的云端书房。聊天、书籍和批注保存在服务器；切换应用不取消已提交的回复。视频页可选 1 分钟或 5 分钟通话，长时学习监督尚未开放。';}
  if(state.connection?.checked_at)$('connectionresult').textContent=state.connection.message+' · '+time(state.connection.checked_at);
  else $('connectionresult').textContent='只读取模型信息，不测试生成回复是否可用。';
  if(generation)$('connectionresult').textContent+=`；当前模型最近一次生成请求：${generation.status==='success'?'已收到 API 响应':generation.status==='running'?'正在等待':generation.status==='timeout'?'超时':'未完成'} · ${time(generation.time)} · ${generation.status==='running'?Math.max(0,Math.round((Date.now()-Date.parse(generation.time))/1000)):generation.elapsed_seconds} 秒。信息读取检查不会覆盖这项记录。`;
  $('memorystatus').textContent=`每轮持续带入关系与表达依据。新聊天已有 ${state.live_memories||0} 条自动加入检索。按相关度和文字预算带入原文，段数不固定；普通聊天最多 ${state.recall_cap?.chat_rounds||state.tool_limits?.chat_rounds||8} 轮工具补查，之后整理回答；尚不能保证每次召回完整，没找到时会保留不确定。`;
  $('correctioncount').textContent=`${state.active_corrections||0} 条有效澄清 · 每轮优先带入`;
  if(state.brains){renderBrains();$('deepseekstate').textContent=state.deepseek_key_present?'DeepSeek 密钥已保存 · 实际模型调用待验证':'尚未填写 DeepSeek 密钥';}
  $('keystate').textContent=state.key_present?'已保存密钥（此状态不代表认证已通过）':'尚未保存密钥';
  $('sampleinfo').textContent=`语义试验：已索引 ${state.indexed} 段，尚未覆盖全部历史。`;
  if(state.rag){const r=state.rag;
    $('sampleinfo').closest('details').hidden=true;
    $('ragstate').textContent=r.enabled?({ready:'词句＋多语言语义',indexing:'正在补齐语义索引',pending:'等待建立语义索引',degraded:'语义检索需要检查',error:'语义索引未完成'}[r.phase]||r.phase):'词句检索';
    $('ragdetails').textContent=r.enabled?`已处理 ${r.indexed} 条原文，其中 ${r.semantic_documents||0} 条形成 ${r.chunks} 个语义片段${r.total?' / 原文总数 '+r.total:''}。失败 ${r.failed||0} 条。孤立标点、标签等仅保留词句检索。检索模型在服务器或本机运行，无逐次 embedding API 费用；原文完整保留。${r.error?' 当前异常：'+r.error+'；仍可使用词句检索。':''}`:'当前使用词句检索；此实例尚未启用本地多语言模型。';
    $('ragtests').textContent=r.regression?`最近自动检索检查：${r.regression.passed}/${r.regression.total} 通过（${new Date(r.regression.at*1000).toLocaleString('zh-CN')}）。检验原文是否找回并装入本轮；不代表最终回答一定正确。${r.regression.cases?.some(c=>!c.pass)?' 待改进：'+r.regression.cases.filter(c=>!c.pass).map(c=>c.name).join('、'):''}`:'尚无本次语义索引的自动检查结果。';
  }
  const c=state.config, remaining=c.plus_rmb===null?'待填写 Plus 账单':money(c.monthly_rmb-c.plus_rmb-c.other_rmb-state.month_rmb);
  $('budgetsummary').textContent=`本地试用已计入 ${money(state.spend_rmb)} / ${money(c.pilot_cap_rmb)}；本月剩余额度估计：${remaining}。付费调用${c.paid_enabled?'已开启':'已关闭'}。`;
  if(!c.budget_enforced)$('budgetsummary').textContent=`费用观察模式 · 金额拦截已关闭。本月本应用累计计入 ${money(state.month_rmb)}。付费调用${c.paid_enabled?'已开启':'已关闭'}。`;
  const cap=state.recall_cap;
  if(cap)$('memorystatus').textContent+=` Argon：每轮检索原文累计最多 ${cap.memory_chars.toLocaleString()} 字符 / ${cap.memory_items} 段，最多 ${cap.memory_searches} 次不同记忆补查；普通聊天最多 ${cap.chat_rounds} 轮工具交互，达到额度会整理回答。完整档案、固定人格、澄清和近期聊天另行保留。`;
  let cacheBox=$('cache-observation');if(!cacheBox){cacheBox=el('p',undefined,'footnote');cacheBox.id='cache-observation';$('budgetsummary').after(cacheBox);}
  const cache=state.cache_observation;
  if(cache)cacheBox.textContent=cache.reported_requests?`缓存观察 · ${cache.model} 最近 ${cache.requests} 次请求中 ${cache.reported_requests} 次返回了缓存数据；这些请求按输入 token 加权的命中率 ${(cache.hit_rate*100).toFixed(1)}%，复用 ${cache.cached_tokens.toLocaleString()} 个 token。其余请求未报告，不能当作零命中。新 Argon 请求按已报告缓存量及对应价格估算；思考和回复仍正常计费。`:`缓存观察 · ${cache.model} 最近 ${cache.requests} 次请求尚未返回可用缓存数据，不能确认命中率。不会为测试缓存额外发送模型请求。`;
  if(state.billing_summary){const b=state.billing_summary;$('budgetsummary').textContent+=` 以上均为人民币。本地用量估算 ${money(b.estimated_rmb)}，待核对请求预留 ${money(b.uncertain_rmb)}；按当前汇率 1 美元 = ${c.usd_rmb} 元，总计折合约 $${(state.spend_rmb/c.usd_rmb).toFixed(4)}。这不是 Google 账户余额；其他应用及密钥的花费不在这里。`;}
  if(state.observation){const o=state.observation;$('observation').replaceChildren(el('p',`30 天观察：${time(o.start)} 至 ${time(o.end)}。API 用量估算 ${money(o.estimated_rmb)}，进行中或待核对预留 ${money(o.pending_rmb)}；Plus 实际月费${c.plus_rmb===null?'尚未填写':money(c.plus_rmb)}，单独记录。`));for(const r of o.models)$('observation').append(el('p',`${r.model} · ${r.requests} 次请求 · 估算 ${money(r.estimated_rmb)} · 待核对 ${money(r.pending_rmb)}`,'footnote'));$('observation').append(el('p',`Codex 订阅请求 ${o.subscription_requests} 次，共享订阅额度，不重复算为 API 费用。观察期结束不会自动开启预算锁或订阅服务。`,'footnote'));}
  $('ledger').replaceChildren();
  if(state.search){
    $('searchstate').textContent=state.search.ready?'已配置 · Agent 可按需联网（尚不代表实际查询已验证）':state.search.key_present?'密钥已保存 · 联网开关尚未开启':'尚未填写搜索密钥 · 当前不会联网';
    $('searchbudget').textContent=`本月搜索已计入 ${money(state.search.month_rmb)} / ${money(c.search_monthly_rmb)}；一次基础搜索预留 ${money(state.search.usd_per_request*c.usd_rmb)}。`;
    if(!c.budget_enforced)$('searchbudget').textContent=`本月搜索已计入 ${money(state.search.month_rmb)}；金额拦截已关闭，仍按次记录费用。`;
    $('searchlog').replaceChildren(...state.search.recent.map(r=>el('p',`${time(r.time)} · ${r.query} · ${{done:'有结果',empty:'没有匹配结果',error:'未完成',running:'处理中'}[r.status]||r.status}${r.error?' · '+r.error:''}`,'footnote')));
  }
  if(!state.ledger.length)$('ledger').append(el('p','还没有模型费用记录。','footnote'));else{const table=el('table'),head=el('tr');['北京时间','用途','状态','计入额度'].forEach(t=>head.append(el('th',t)));table.append(head);const labels={subscription:'订阅用量',subscription_uncertain:'订阅请求未完成',web_search:'网页搜索',video_call:'音视频试通',chat:'试聊',embedding_document:'建立样本索引',embedding_query:'语义试搜',estimated:'用量估算',conservative_estimate:'保守估算',uncertain:'账单待核对',reserved:'已预留'};for(const r of state.ledger){const row=el('tr');[time(r.time),(r.kind==='chat'?(JSON.parse(r.pricing_json||'{}').model||'Gemini'):(labels[r.kind]||r.kind)),labels[r.status]||r.status,(r.status.startsWith('subscription')?'共享订阅额度':money(r.estimated_rmb??r.reserved_rmb))].forEach(t=>row.append(el('td',t)));table.append(row);}$('ledger').append(table);}
}
async function begin(kind,data) {
  if(activeJob||submittingJob)throw Error('已有任务提交或运行中。');
  submittingJob=true;invalidateQuote();
  try{const job=await api('job/'+kind,data);activeJob=job.id;sessionStorage.setItem('continuity-job',job.id);$('orb').classList.add('busy');$('task').textContent=job.event;poll();}
  finally{submittingJob=false;invalidateQuote();}
}
async function poll() {
  if(polling||!activeJob||document.hidden)return;clearTimeout(pollTimer);polling=true;
  try {const job=await api('job?view=chat&id='+encodeURIComponent(activeJob));$('task').textContent=[...(job.events||[]),job.event].join(' · ');
    if(job.status==='running'&&Number.isFinite(Date.parse(job.started)))$('task').textContent+=` · 本轮已用时 ${Math.max(0,Math.round((Date.now()-Date.parse(job.started))/1000))} 秒`;
    await renderHistory();
    if(job.status!=='running'){activeJob=null;sessionStorage.removeItem('continuity-job');$('orb').classList.remove('busy');invalidateQuote();$('restore').hidden=!lastFailed;if(job.status==='done'){if(job.kind==='semantic'){mode='semantic';renderResults(job.result);tab('memory');}else if(job.kind==='chat'){notify('Agent 的回复已保存，并加入记忆检索。');}else notify('样本索引已完成。');}else notify(job.error||job.event);Promise.allSettled([refresh(),renderCorrections()]);}
  }catch(e){if(e.name!=='AbortError')$('task').textContent='暂时连不上服务。已提交请求不会自动重发；恢复连接后继续检查回复。';}finally{polling=false;if(activeJob&&!document.hidden)pollTimer=setTimeout(poll,resumingChat?0:1800);resumingChat=false;}
}
function resumeChat(){
  if(document.hidden)return;resumingChat=true;clearTimeout(pollTimer);
  // Cancel only stale read requests. A submitted model job keeps running on the server.
  for(const controller of chatReads)controller.abort();
  setTimeout(()=>{if(activeJob)poll();document.dispatchEvent(new Event('continuity-resume'));},0);
}
document.addEventListener('visibilitychange',resumeChat);
window.addEventListener('pageshow',resumeChat);
window.addEventListener('online',resumeChat);
$('prompt').addEventListener('input',()=>{retryOf=null;saveTextDraft();invalidateQuote();});
function messageData(){if(readerTextBusy)throw Error('原文正在加载，请稍等再发问。');return {text:$('prompt').value.trim()||(pendingImages.length?'请看看我发来的图片。':pendingDocs.length?'请看看我发来的文件。':''),refs:[...selected.keys()],retry_of:retryOf,attachments:pendingImages.map(p=>p.id),documents:pendingDocs.map(p=>({id:p.id,version:p.version})),reading:pendingReading?{...pendingReading}:null};}
$('restore').onclick=()=>{if(!lastFailed||activeJob)return;selected=new Map(lastFailed.refs.map(p=>[p.id,p]));renderSelected();$('prompt').value=lastFailed.text;saveTextDraft();pendingReading=lastFailed.reading||null;readerChip();pendingDocs=[...(lastFailed.documents||[])];renderPendingDocs();pendingImages=[...(lastFailed.attachments||[])];renderPendingImages();retryOf=lastFailed.id;invalidateQuote();notify('消息和引用已恢复，尚未发送。可以直接重试，不会重复保存这条用户消息。');};
$('preview').onclick=async()=>{try{if(activeJob)throw Error('请等待当前任务完成。');const q=await api('quote',messageData());$('quote').textContent=`${q.model} · ${q.image_count||0} 张图（含近期图片） · 固定关系与表达依据 + ${q.refs} 段原文（${q.memory_chars} 字；每批检索参考 ${q.memory_char_budget} 字）+ ${q.history_turns} 条近期聊天 · 首次请求预留 ${money(q.ceiling_rmb)}。如需补查，最多 ${q.tool_rounds} 轮工具交互，并预留最多 ${q.final_response_requests} 次收尾请求；合计最多 ${q.max_model_requests} 次模型请求，每次记录用量；金额拦截按设置执行。`;if(q.subscription)$('quote').textContent=`${q.model} · 共用 ${q.refs} 段记忆及近期对话。使用 Codex 订阅，不估算为美元 API 账单；同样受订阅限额约束。`; if(q.recall_cap)$('quote').textContent+=` 本轮检索原文累计上限 ${q.recall_cap.memory_chars.toLocaleString()} 字符 / ${q.recall_cap.memory_items} 段，最多 ${q.recall_cap.memory_searches} 次不同记忆补查；达到后正常收尾。`; $('quote').textContent+=q.web_search_ready?(' 如需联网：每次另预留 '+money(q.web_request_rmb)+'，最多两次；阅读结果后的模型生成仍计费。'):' 当前未启用联网。';$('recallrefs').replaceChildren(...q.memories.map((p,i)=>button(`记忆${i+1} · ${p.speaker||'待核对'}`,()=>showContext(p.id))));$('recallpreview').hidden=!q.memories.length;if(q.document_count)$('quote').textContent+=' 本轮附带 '+q.document_count+' 个文档；长文先读开头，可通过工具继续读取。';quoteReady=true;$('send').disabled=!hasDraft()||!!activeJob||submittingJob||imageUploadBusy||documentBusy||readerTextBusy;}catch(e){notify(e.message);}};
$('send').onclick=async()=>{try{
  if(activeJob||submittingJob||imageUploadBusy||documentBusy||!hasDraft())return;
  if(pendingImages.length&&!state.brains?.[state.config.brain]?.vision)throw Error('发图片请先切回 Gemini。');
  const draft=$('prompt').value,data=messageData();
  await begin('chat',data);
  // Do not erase text or references added while the submission was in flight.
  if($('prompt').value===draft)$('prompt').value='';saveTextDraft();
  data.refs.forEach(id=>selected.delete(id));
  pendingImages=pendingImages.filter(p=>!data.attachments.includes(p.id));
  pendingDocs=pendingDocs.filter(p=>!data.documents.some(d=>d.id===p.id&&d.version===p.version));
  renderPendingDocs();renderPendingImages();renderSelected();retryOf=null;
}catch(e){notify(e.message);}};
$('checkconnection').onclick=async()=>{const button=$('checkconnection');button.disabled=true;$('connectionresult').textContent='正在读取 Google 模型信息…';try{const result=await api('connection/check',{});$('connectionresult').textContent=result.message;notify('Google 模型信息读取成功；没有测试生成回复，也没有发送记忆。');}catch(e){$('connectionresult').textContent=e.message;notify(e.message);}finally{button.disabled=false;await refresh().catch(()=>{});}};
$('embed').onclick=async()=>{try{const data=await api('sample');if(!confirm(`只将 ${data.items.length} 段试验原文发给 Google 建立语义索引。尚未缓存的部分最多预留 ${money(data.ceiling_rmb)}。继续吗？`))return;await begin('embed',{});}catch(e){notify(e.message);}};
$('semantic').onclick=async()=>{try{const query=$('query').value.trim();if(!query)throw Error('请先输入想检索的意思。');if(!confirm('语义试搜需要将检索问题发送给 Google，按试用额度付费；仅搜索已经建立的样本索引。来源和珍视筛选仅用于免费原文检索。继续吗？'))return;await begin('semantic',{query});}catch(e){notify(e.message);}};
$('keyform').onsubmit=async e=>{e.preventDefault();try{await api('key',{key:$('apikey').value,persist:$('persist').checked});$('apikey').value='';await refresh();notify('密钥已保存；尚未调用 Google，不会因此产生模型费用。');}catch(e){notify(e.message);}};
$('clearkey').onclick=async()=>{try{await api('key/clear',{});await refresh();notify('本机保存的 Gemini 密钥已移除。已发出的请求可能仍会完成。');}catch(e){notify(e.message);}};
$('searchkeyform').onsubmit=async e=>{e.preventDefault();try{await api('search/key',{key:$('searchkey').value,persist:$('searchpersist').checked});$('searchkey').value='';await refresh();notify('搜索密钥已保存，尚未发送请求。开启联网后点击「保存设置」。');}catch(e){notify(e.message);}};
$('clearsearchkey').onclick=async()=>{try{await api('search/key/clear',{});await refresh();invalidateQuote();notify('搜索密钥已移除，后续不会发起新的搜索。');}catch(e){notify(e.message);}};
$('budgetform').onsubmit=async e=>{e.preventDefault();try{const data={};for(const key of Object.keys(state.config))if($(key))data[key]=['thinking_level','brain'].includes(key)?$(key).value:['paid_enabled','search_enabled','budget_enforced'].includes(key)?$(key).checked:$(key).value===''?null:Number($(key).value);await api('config',data);invalidateQuote();await refresh();notify('预算设置已保存。');}catch(e){notify(e.message);}};
$('export').onclick=async()=>{try{const data=await api('export');const blob=new Blob([data.markdown],{type:'text/markdown;charset=utf-8'});const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=data.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){notify(e.message);}};
(async()=>{try{await refresh();fillSettings();activeJob=state.jobs.find(j=>j.status==='running')?.id||sessionStorage.getItem('continuity-job');await renderHistory();if(activeJob){$('orb').classList.add('busy');poll();}Promise.allSettled([renderCorrections(),(async()=>{const src=await api('sources');src.forEach(s=>{const option=el('option',s.filename+' · '+s.category);option.value=s.id;$('source').append(option);});await literal();})()]);}catch(e){$('connection').textContent='服务暂未连接';notify(e.message);}})();

$('relationship').addEventListener('toggle',async()=>{if(!$('relationship').open||$('profileguide').textContent)return;try{const p=await api('relationship');$('profilecoverage').textContent='版本 '+p.version+' · '+p.coverage;$('profileguide').textContent=p.guide;$('profileexamples').replaceChildren(...p.examples.map(e=>button(e.source+' · 第 '+e.paragraph+' 段',()=>showContext(e.id))));}catch(e){notify(e.message);}});


initMedia();initLibrary();initReader();initStudio();

// Compact application shell; preserve existing controls and their event handlers.
function initShell(){
 document.body.classList.add('app-shell');document.body.dataset.page='chat';
 const header=document.querySelector('header'),nav=document.querySelector('nav'),main=document.querySelector('main');
 nav.id='appnav';const side=el('aside',undefined,'app-sidebar');side.id='appsidebar';side.setAttribute('aria-label','功能侧栏');
 const sideHead=el('div',undefined,'sidebar-heading');sideHead.append(el('span','Continuity','sidebar-wordmark'));
 const toggle=button('☰',()=>{if(matchMedia('(max-width:760px)').matches)setSidebar(!document.body.classList.contains('sidebar-open'));else{document.body.classList.remove('sidebar-collapsed');toggle.setAttribute('aria-expanded','true');}},'shell-icon');toggle.id='menutoggle';toggle.setAttribute('aria-label','打开功能侧栏');toggle.setAttribute('aria-controls','appsidebar');toggle.setAttribute('aria-expanded','false');
 const close=button('×',()=>{if(matchMedia('(max-width:760px)').matches)setSidebar(false);else{document.body.classList.add('sidebar-collapsed');toggle.setAttribute('aria-expanded','false');toggle.focus();}},'shell-icon sidebar-close');close.setAttribute('aria-label','关闭功能侧栏');sideHead.append(close);side.append(sideHead,nav);
 const icons={chat:'◌',memory:'✧',reader:'▤',library:'▱',studio:'⌘',settings:'⚙'};
 for(const b of nav.querySelectorAll('button')){const icon=el('span',icons[b.dataset.tab]||'·','nav-icon');icon.setAttribute('aria-hidden','true');b.prepend(icon);}
 const sideNote=el('p','同一份记忆，继续生长。','sidebar-note');side.append(sideNote);
 const foot=el('div',undefined,'sidebar-footer');foot.append($('export'));
 for(const b of [...header.children])if(b.tagName==='BUTTON'){if(b.textContent==='退出登录')b.remove();else foot.append(b);}
 side.append(foot);document.body.insertBefore(side,header);
 const ledgerCard=$('ledger').closest('article');
 if(ledgerCard){const detail=el('details');detail.append(el('summary','费用明细与计费说明'));for(const child of [...ledgerCard.children])if(child.tagName!=='H3'&&child.id!=='budgetsummary')detail.append(child);ledgerCard.append(detail);$('settings').querySelector('.heading').after(ledgerCard);}
 const backdrop=button('',()=>setSidebar(false),'sidebar-backdrop');backdrop.tabIndex=-1;backdrop.setAttribute('aria-label','关闭功能侧栏');backdrop.hidden=true;document.body.insertBefore(backdrop,header);
 header.querySelector('.badge')?.remove();header.prepend(toggle);
 const pageLabel=el('span','对话','shell-page');pageLabel.id='shellpage';header.append(pageLabel);
 const options=el('details',undefined,'chat-options');options.id='chatoptions';options.append(el('summary','选项与费用'));
 options.append($('brainhint'),$('quote'),$('preview'),$('memorystatus'));
 const composer=document.querySelector('.composer'),bottom=document.querySelector('.compose-bottom'),brainbar=document.querySelector('.brainbar');
 const label=brainbar.querySelector('label');for(const n of [...label.childNodes])if(n.nodeType===Node.TEXT_NODE)n.textContent='';
 $('brainselect').setAttribute('aria-label','选择本轮模型');$('brainselect').title='切换模型，共用聊天与记忆';
 const add=$('chooseattachment');bottom.prepend(brainbar);brainbar.prepend(add);
 bottom.insertBefore(options,$('send'));$('send').textContent='↑';$('send').setAttribute('aria-label','发送给 Agent');$('send').title='发送消息';
 $('prompt').rows=1;$('prompt').placeholder='和 Agent 说说话…';
 const resize=initComposerSize(composer);
 $('prompt').addEventListener('input',resize);$('send').addEventListener('click',()=>setTimeout(resize,0));
 $('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&matchMedia('(pointer:fine) and (min-width:761px)').matches){e.preventDefault();if(!$('send').disabled)$('send').click();}});
 const jump=button('↓',()=>{$('messages').scrollTo({top:$('messages').scrollHeight,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});jump.hidden=true;},'jump-latest');jump.id='jumplatest';jump.hidden=true;jump.setAttribute('aria-label','回到最新消息');composer.before(jump);
 $('messages').addEventListener('scroll',()=>{jump.hidden=$('messages').scrollHeight-$('messages').scrollTop-$('messages').clientHeight<180;},{passive:true});
 function setSidebar(open){document.body.classList.toggle('sidebar-open',open);toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'关闭功能侧栏':'打开功能侧栏');backdrop.hidden=!open;side.inert=matchMedia('(max-width:760px)').matches&&!open;if(open&&matchMedia('(max-width:760px)').matches)close.focus();}
 document.addEventListener('continuity-tab',e=>{pageLabel.textContent={chat:'对话',memory:'记忆',reader:'一起读书',library:'资料库',settings:'连接与预算',studio:'工作室',video:'视频试通'}[e.detail]||'Agent';if(matchMedia('(max-width:760px)').matches){setSidebar(false);toggle.focus();}});
 document.addEventListener('keydown',e=>{if(!document.body.classList.contains('sidebar-open')||!matchMedia('(max-width:760px)').matches)return;if(e.key==='Escape'){setSidebar(false);toggle.focus();}if(e.key==='Tab'){const focusable=[...side.querySelectorAll('button,a[href]')].filter(n=>n.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 const mq=matchMedia('(max-width:760px)');mq.addEventListener('change',()=>setSidebar(false));setSidebar(false);
 // Visual viewport follows the iPhone keyboard without hiding the input bar.
 const viewport=()=>{if(mq.matches&&window.visualViewport){document.body.style.setProperty('--app-height',visualViewport.height+'px');document.body.style.setProperty('--app-top',visualViewport.offsetTop+'px');}else{document.body.style.removeProperty('--app-height');document.body.style.removeProperty('--app-top');}};
 window.visualViewport?.addEventListener('resize',viewport);window.visualViewport?.addEventListener('scroll',viewport);window.addEventListener('resize',viewport);viewport();resize();
}
initShell();
restoreTextDraft();

function initComposerSize(composer){
 const input=$('prompt'),tools=el('div',undefined,'composer-size'),handle=el('span','━','composer-grip');handle.id='composergrip';handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','horizontal');handle.setAttribute('aria-label','上下拖动调整输入框大小；方向键也可调整');handle.setAttribute('aria-controls','prompt');
 const key=()=> 'continuity-input-height-'+(matchMedia('(max-width:760px)').matches?'phone':'desktop');
 const saved=()=>{try{const n=Number(localStorage.getItem(key()));return Number.isFinite(n)&&n>=44?Math.min(n,480):null;}catch{return null;}};
 let manual=saved(),drag=null;
 const maxHeight=()=>{const host=composer.closest('.reader-chat')||$('chat');const height=host.clientHeight||window.visualViewport?.height||innerHeight;return Math.max(44,Math.min(480,Math.floor(height*.68)-118));};
 const remember=()=>{try{if(manual===null)localStorage.removeItem(key());else localStorage.setItem(key(),String(manual));}catch{}};
 const resize=()=>{const max=maxHeight();input.style.maxHeight=max+'px';input.style.height='auto';input.style.height=Math.max(44,Math.min(manual??Math.min(input.scrollHeight,160),max))+'px';handle.setAttribute('aria-valuemin','44');handle.setAttribute('aria-valuemax',String(max));handle.setAttribute('aria-valuenow',String(Math.round(input.getBoundingClientRect().height)));};
 const change=n=>{manual=Math.max(44,Math.min(n,maxHeight()));remember();resize();};
 const current=()=>input.getBoundingClientRect().height;
 const smaller=button('−',()=>change(current()-48),'size-button'),larger=button('+',()=>change(current()+48),'size-button'),reset=button('自动',()=>{manual=null;remember();resize();},'size-auto');smaller.setAttribute('aria-label','缩小输入框');larger.setAttribute('aria-label','放大输入框');reset.setAttribute('aria-label','恢复输入框自动大小');
 tools.append(handle,smaller,larger,reset);composer.prepend(tools);
 handle.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();drag={id:e.pointerId,y:e.clientY,height:current()};handle.setPointerCapture(e.pointerId);});
 handle.addEventListener('pointermove',e=>{if(drag?.id!==e.pointerId)return;e.preventDefault();change(drag.height+drag.y-e.clientY);});
 for(const event of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(event,()=>{drag=null;});
 handle.addEventListener('keydown',e=>{if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;e.preventDefault();change(e.key==='Home'?44:e.key==='End'?maxHeight():current()+(e.key==='ArrowUp'?24:-24));});
 window.addEventListener('resize',resize);window.visualViewport?.addEventListener('resize',resize);document.addEventListener('continuity-tab',()=>requestAnimationFrame(resize));
 return resize;
}
// Place aliases and evidence-backed chronology. All text is rendered via textContent.
async function renderSpacetime(before=null){
 const host=$('spacetimebody');host.replaceChildren(el('p','正在读取…','footnote'));
 try{
 const data=await api('spacetime'+(before?'?before='+before:''));host.replaceChildren();
 const byId=new Map(data.boxes.map(b=>[b.id,b]));
 const current=data.current;host.append(el('p',current.place?`最近报告：${current.place}${current.parent?' · '+current.parent:''}；${time(current.report_time)}。${current.needs_reconfirmation?'超过一天未确认。':''}这是报告延续，不是实时定位。`:current.status==='left_unknown'?`已离开 ${current.left_place}，新位置未确认。`:'当前位置未确认；知道家的词义不代表现在就在家。'));
 host.append(el('h3','地点词典'));
 const editor=el('form'),name=el('input'),aliases=el('input'),purpose=el('input'),parent=el('select');let editing=null;
 name.placeholder='地点名称，例如：上海';name.required=true;name.maxLength=80;aliases.placeholder='别名，用逗号分隔';purpose.placeholder='这里对你的含义';purpose.maxLength=300;
 parent.append(new Option('无上级地点',''));for(const b of data.boxes)parent.append(new Option(b.name,b.id));
 for(const [label,input] of [['地点',name],['别名',aliases],['说明',purpose],['上级地点',parent]]){const field=el('label',label);field.append(input);editor.append(field);}
 const submit=el('button','保存地点词义','primary');submit.type='submit';editor.append(submit,button('新建／取消编辑',()=>{editing=null;name.value='';aliases.value='';purpose.value='';parent.value='';}));
 for(const b of data.boxes){const row=el('div',undefined,'memory');row.append(el('strong',b.name+(b.parent_id?' ← '+byId.get(b.parent_id)?.name:'')),el('p',b.aliases.join('、')+'；'+b.purpose,'footnote'),button('编辑词义',()=>{editing=b.id;name.value=b.name;aliases.value=b.aliases.filter(a=>a!==b.name).join(', ');purpose.value=b.purpose;parent.value=b.parent_id||'';name.focus();}));host.append(row);}
 editor.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{await api('spacetime/box',{id:editing,name:name.value,aliases:aliases.value.split(/[,，]/).map(v=>v.trim()).filter(Boolean),purpose:purpose.value,parent_id:parent.value?Number(parent.value):null,evidence:'用户在地点词典中明确编辑'});await renderSpacetime();}catch(err){notify(err.message);submit.disabled=false;}};host.append(editor);
 host.append(el('h3','明确登记现在的位置'));
 const location=el('select');for(const b of data.boxes)location.append(new Option(b.name,b.id));location.setAttribute('aria-label','现在的位置');host.append(location);
 for(const [label,action] of [['我现在在这里','present'],['我现在离开这里','left']]){const btn=button(label,async()=>{btn.disabled=true;try{await api('spacetime/location',{box_id:Number(location.value),action});await renderSpacetime();}catch(err){notify(err.message);btn.disabled=false;}});host.append(btn);}
 host.append(el('h3','位置记录 · 可撤回'));
 for(const event of data.events){const row=el('div',undefined,'memory');row.append(el('p',`${time(event.recorded_at)} · ${event.action==='present'?'报告在':'离开'} ${byId.get(event.box_id)?.name||'未知地点'} · ${event.status==='active'?'有效':'已撤回'}`),el('p',event.evidence,'footnote'));if(event.source_chat_id)row.append(button('查看原话',()=>showContext('chat:'+event.source_chat_id)));row.append(button(event.status==='active'?'撤回':'恢复',async()=>{try{await api('spacetime/change',{id:event.id,status:event.status==='active'?'revoked':'active'});await renderSpacetime();}catch(err){notify(err.message);}}));host.append(row);}
 if(!data.events.length)host.append(el('p','尚无位置报告。之后在聊天里明确说“我现在在家”等即可记录；有歧义时可在这里登记。','footnote'));
 host.append(el('h3','聊天时间长线（北京时间）'));
 for(const m of data.messages){const row=el('div',undefined,'memory'),t=m.time_context;row.append(el('div',`${time(m.time)} · ${m.role==='user'?'你':'Agent'} · ${m.location.place||'地点未确认'}`,'meta'));if(t.seconds_after_previous!==undefined)row.append(el('div',`与上一条相隔 ${Math.round(t.seconds_after_previous/60)} 分钟 · ${t.same_beijing_day_as_previous?'同一天':'跨日'}；事件时间需看原话`,'footnote'));row.append(button('查看这一条',()=>showContext('chat:'+m.id)));host.append(row);}
 if(data.has_older)host.append(button('更早的消息',()=>renderSpacetime(data.next_before)));if(before)host.append(button('回到最近',()=>renderSpacetime()));
 const audit=el('details');audit.append(el('summary','最近的词义修改与撤回记录'));for(const a of data.audit)audit.append(el('p',time(a.time)+' · '+a.action+' · '+a.data,'footnote'));host.append(audit);
 }catch(err){host.replaceChildren(el('p',err.message));}
}
$('spacetimepanel').addEventListener('toggle',()=>{if($('spacetimepanel').open)renderSpacetime();});

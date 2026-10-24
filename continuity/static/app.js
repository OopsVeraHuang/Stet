'use strict';
const $ = id => document.getElementById(id);
let token, pending = null, allMessages = [], removal = null, fileVersion = 0;
const roleNames = {user:'用户原话', assistant:'助手原话 · 未经用户确认', system:'来源中的系统消息', tool:'工具记录', unknown:'角色未知'};
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function notice(text, error = false) { $('notice').textContent = text; $('notice').className = error ? 'error' : ''; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Continuity-Token':token}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败，请重试。');
  return data;
}
function act(node, task) { node.addEventListener('click', async () => { node.disabled = true; try { await task(); } catch(error) { notice(error.message, true); } finally { node.disabled = false; } }); }
function show(screen) {
  for (const s of ['import','memory','search']) $('screen-'+s).hidden = s !== screen;
  document.querySelectorAll('nav button').forEach(b => { if (b.dataset.screen === screen) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current'); });
}
function meta(record) { return `${record.source_id ?? '来源未知'} · 对话 ${record.conversation_id ?? '未知'} · 分支 ${record.branch_id ?? '未知'} · ${record.recorded_at ?? '记录时间未知'}`; }
function recordCard(item, preview = false) {
  const r = item.record, card = element('article', undefined, 'card');
  const head = element('div', undefined, 'card-head');
  head.append(element('strong', roleNames[r.role] || (r.role ? `未识别角色：${r.role}` : '角色未知')));
  if (!preview) { const button = element('button', '查看出处'); act(button, () => openDetail(item.key)); head.append(button); }
  card.append(head, element('p', meta(r), 'meta'), element('div', typeof r.text === 'string' ? r.text : '正文格式错误', 'original'));
  if (preview) {
    card.append(element('p', `第 ${item.ordinal+1} 条 · 消息 ${r.id ?? '缺失'} · ${JSON.stringify(item.locator)}`, 'meta'));
    if (item.duplicate) card.append(element('p', '重复记录：不新增消息，保留该文件的出处关联。', 'warning'));
    for (const w of item.warnings) card.append(element('p', w, 'warning'));
    for (const e of item.errors) card.append(element('p', e, 'error'));
  }
  return card;
}
function base64(bytes) { let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte); return btoa(binary); }
function invalidatePreview() { fileVersion++; pending = null; $('preview').hidden = true; $('confirm-import').disabled = true; return fileVersion; }
async function previewBytes(bytes, filename, version) {
  const payload = {filename, data:base64(bytes)};
  const result = await api('/api/preview', payload);
  if (version !== fileVersion) return;
  pending = result.can_import ? payload : null;
  $('preview').hidden = false; $('preview-title').textContent = '导入预览 · '+filename;
  $('confirm-import').disabled = !result.can_import;
  $('preview-summary').replaceChildren(...[['总消息',result.summary.total],['可新增',result.summary.new],['重复',result.summary.duplicates],['失败',result.summary.failed],['含缺失提示',result.summary.warnings]].map(([label,n])=>element('span',`${label} ${n}`,'stat')));
  $('preview-hash').textContent = `原文件 SHA-256：${result.sha256} · ${result.bytes} 字节 · 分支：${result.summary.branches.join('、')}`;
  $('preview-guidance').textContent = result.already_imported ? '这份原文件已导入，不会再次保存。' : result.summary.failed ? '存在错误，整批不会写入；没有静默跳过。请修正源文件后重新预览。' : '原文件和所有消息将保存在本机。缺失字段保持未知；预览尚未写入。';
  $('preview-rows').replaceChildren(...result.rows.map(r=>recordCard(r,true)));
  if (Object.keys(result.extensions).some(k => !['synthetic','warning','schema_version'].includes(k))) $('preview-rows').prepend(element('p','文件含扩展字段：将原样保留；用户治理与模型推断不会在 P1-A 自动执行。','warning'));
  notice('预览已完成。请检查原话、角色和时间，再确认导入。');
}
async function example(extension) { const version = invalidatePreview(); const response = await fetch('/api/examples/messages.'+extension); if (!response.ok) throw new Error('示例读取失败。'); await previewBytes(new Uint8Array(await response.arrayBuffer()), 'messages.'+extension, version); }
function fillFilter(id, pairs) { const select = $(id), previous = select.value; select.replaceChildren(...pairs.map(([value,label])=>{const o=element('option',label);o.value=value;return o;})); if(pairs.some(p=>p[0]===previous)) select.value=previous; }
function renderMemory() {
  const source=$('source-filter').value, branch=$('branch-filter').value;
  const visible=allMessages.filter(m=>(!source||m.record.source_id===source)&&(branch==='*'||JSON.stringify(m.record.branch_id??null)===branch));
  $('memory-count').textContent=`显示 ${visible.length} / ${allMessages.length} 条记录`;
  $('memory-list').replaceChildren(...(visible.length ? visible.map(m=>recordCard(m)) : [element('div','这里还没有符合条件的记录。可到「导入」预览虚构示例。','empty')]));
}
async function refresh() {
  const [messages,batches] = await Promise.all([api('/api/messages'),api('/api/batches')]);
  allMessages=messages.messages;
  fillFilter('source-filter',[['','全部来源'],...[...new Set(allMessages.map(m=>m.record.source_id))].map(s=>[s,s])]);
  fillFilter('branch-filter',[['*','全部分支'],...[...new Set(allMessages.map(m=>m.record.branch_id??null))].map(b=>[JSON.stringify(b),b??'未知分支'])]);
  renderMemory();
  $('batches').replaceChildren(...batches.batches.map(b=>{
    const item=element('div',undefined,'batch');
    item.append(element('strong',b.filename),element('p',`${b.records} 条来源关联 · 本次导入 ${b.imported_at}`,'small'));
    const button=element('button','撤销整批导入','danger');
    button.addEventListener('click',()=>{removal=b;$('remove-description').textContent=`文件：${b.filename}（${b.records} 条来源关联）`;$('remove-dialog').showModal();});
    item.append(button);return item;
  }));
  if (!batches.batches.length) $('batches').append(element('p','尚无导入批次。','muted'));
}
async function openDetail(key) {
  const data=await api('/api/messages/'+key), r=data.record, content=$('provenance-content');
  content.replaceChildren(element('p','以下是历史原话。助手说法、用户陈述与明确纠正不会自动变成当前事实。','warning'),element('div',r.text,'original'));
  const dl=element('dl');
  for(const [label,value] of [['消息 ID',r.id],['角色',r.role],['来源',r.source_id],['对话',r.conversation_id],['分支',r.branch_id],['记录时间',r.recorded_at],['来源时区',r.timezone],['时间精度',r.time_precision],['源数据导入时间',r.imported_at],['事件时间原话',r.event_time_note]]) dl.append(element('dt',label),element('dd',value==null?'未知 / 未提供':typeof value==='object'?JSON.stringify(value):value));
  content.append(dl);
  for(const o of data.origins) {
    const panel=element('div',undefined,'panel');panel.append(element('h3',o.filename),element('p','原文件位置：'+JSON.stringify(o.locator),'small'),element('p','本次导入时间：'+o.imported_at,'small'),element('p','SHA-256：'+o.batch_id,'small mono'));
    const link=element('a','下载完整原文件（原始字节）');link.href='/api/original/'+o.batch_id;link.download=o.filename;panel.append(link);content.append(panel);
  }
  const details=element('details');details.append(element('summary','查看完整源字段（扩展字段只保留，不执行）'),element('pre',JSON.stringify(r,null,2)));content.append(details);
  $('provenance').showModal();
}
document.querySelectorAll('nav button').forEach(b=>act(b,async()=>{show(b.dataset.screen);if(b.dataset.screen==='memory')await refresh();}));
act($('example-json'),()=>example('json'));act($('example-md'),()=>example('md'));
$('file').addEventListener('change',async()=>{const version=invalidatePreview();try{const file=$('file').files[0];if(!file)return;if(file.size>2*1024*1024)throw new Error('文件超过 2 MiB，请拆分规范文件。');await previewBytes(new Uint8Array(await file.arrayBuffer()),file.name,version);}catch(e){notice(e.message,true);}});
$('confirm-import').addEventListener('click',async()=>{if(!pending)return;const payload=pending;invalidatePreview();try{const r=await api('/api/import',payload);await refresh();show('memory');notice(r.already_imported?'已导入过，没有新增消息。':`已保存原文件，新增 ${r.added} 条记忆。点击「查看出处」核对原文。`);}catch(e){notice(e.message+' 请重新预览。',true);}});
$('source-filter').addEventListener('change',renderMemory);$('branch-filter').addEventListener('change',renderMemory);
$('search-form').addEventListener('submit',async event=>{event.preventDefault();try{const q=$('query').value;if(!q.trim())return;const r=await api('/api/messages?q='+encodeURIComponent(q));$('search-count').textContent=`找到 ${r.messages.length} 条字面匹配；没有生成模型回答。`;$('search-results').replaceChildren(...(r.messages.length?r.messages.map(m=>recordCard(m)):[element('div','没有找到连续匹配的原文。可试试原文中的短词；这不表示相关经历不存在。','empty')]));}catch(e){notice(e.message,true);}});
act($('rebuild'),async()=>{const r=await api('/api/rebuild',{});notice(`已从原文重建 ${r.indexed} 条检索索引，原文未改动。`);});
$('close-provenance').addEventListener('click',()=>$('provenance').close());
$('cancel-remove').addEventListener('click',()=>$('remove-dialog').close());
act($('confirm-remove'),async()=>{if(!removal)return;const r=await api('/api/remove-batch',{batch_id:removal.id});$('remove-dialog').close();$('provenance').close();$('provenance-content').replaceChildren();$('search-results').replaceChildren(element('div','导入内容已变化，请重新查找。','empty'));$('search-count').textContent='';invalidatePreview();await refresh();notice(`已撤销：原文件已移除，删除 ${r.removed_messages} 条独有消息；剩余 ${r.remaining_messages} 条消息、${r.remaining_index_entries} 条索引。外部源文件与备份不受影响。`);});
(async()=>{try{token=(await api('/api/session')).token;await refresh();}catch(e){notice(e.message,true);}})();

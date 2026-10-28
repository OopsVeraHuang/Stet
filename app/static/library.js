'use strict';
let pendingDocs=[], libraryDialog, documentBusy=false;
function renderPendingDocs(){
  $('pendingdocs').replaceChildren();
  for(const p of pendingDocs)$('pendingdocs').append(button(`${p.name} · v${p.version} ×`,()=>{pendingDocs=pendingDocs.filter(x=>x.id!==p.id);retryOf=null;renderPendingDocs();}));
  invalidateQuote();
}
function chooseDoc(p){if(activeJob||documentBusy)throw Error('请等本轮完成。');if(pendingDocs.length>=3&&!pendingDocs.some(x=>x.id===p.id))throw Error('一轮最多三个文档。');pendingDocs=pendingDocs.filter(x=>x.id!==p.id);pendingDocs.push(p);retryOf=null;renderPendingDocs();if($('chat').classList.contains('reader-chat'))undockChat();tab('chat');}
function appendDocuments(node,items){if(!items?.length)return;const group=el('div',undefined,'document-chips');for(const p of items)group.append(button(`${p.name||'文档'} · v${p.version}`,()=>openDocument(p.id,p.version)));node.append(group);}
async function libraryList(){const rows=await api('library?q='+encodeURIComponent($('libraryquery').value));$('librarylist').replaceChildren();for(const p of rows){const item=el('article',undefined,'card');item.append(el('h3',p.name),el('p',`v${p.version} · ${p.chars} 字 · ${p.author} · ${time(p.created)}`,'footnote'),el('p',p.note,'footnote'),button('打开',()=>openDocument(p.id,p.version)),button('附到聊天',()=>chooseDoc(p)));$('librarylist').append(item);}if(!rows.length)$('librarylist').append(el('p','还没有匹配的文件。'));}
async function uploadDocuments(files,attach=true){
  if(activeJob||documentBusy)throw Error('请等当前任务完成。');
  if(attach&&pendingDocs.length+files.length>3)throw Error('一轮最多三个文档。');
  documentBusy=true;invalidateQuote();
  try{for(const f of files){if(f.size>8*1024*1024)throw Error('单个文件最多 8 MB。');const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error('读取文件失败'));r.readAsDataURL(f);});const p=await api('library/upload',{name:f.name,data});if(attach)pendingDocs.push(p);}notify('文件已存入资料库；发送聊天时才会把附带的文字交给模型。');await libraryList();}
  finally{documentBusy=false;$('documentfile').value='';$('libraryfile').value='';renderPendingDocs();}
}
async function readWholeDocument(id,version){let r=await api(`library/read?id=${encodeURIComponent(id)}&version=${version}`),text=r.text;while(r.next_offset!==null){r=await api(`library/read?id=${encodeURIComponent(id)}&version=${version}&offset=${r.next_offset}`);text+=r.text;}return text;}
async function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
async function openDocument(id,version){
  const p=await api(`library/read?id=${encodeURIComponent(id)}&version=${version}`),text=await readWholeDocument(id,version);
  libraryDialog.replaceChildren();const title=el('h3',p.name),close=button('关闭',()=>libraryDialog.close()),head=el('div',undefined,'heading');head.append(title,close);
  const versions=el('select');versions.setAttribute('aria-label','文件历史版本');for(const v of p.versions){const o=el('option',`v${v.version} · ${v.author}`);o.value=v.version;versions.append(o);}versions.value=version;versions.onchange=()=>openDocument(id,Number(versions.value)).catch(e=>notify(e.message));
  const editor=el('textarea');editor.value=text;editor.rows=16;editor.maxLength=500000;editor.setAttribute('aria-label','文件文字副本');
  const save=button('保存为新版本',async()=>{save.disabled=true;try{const r=await api('library/edit',{id,base_version:p.version,text:editor.value});await libraryList();await openDocument(id,r.version);notify('新版本已保存；此前版本仍可查看。');}finally{save.disabled=false;}});
  if(p.version!==p.versions[0].version){editor.readOnly=true;save.disabled=true;}
  const actions=el('div',undefined,'document-chips');actions.append(save,button('附到聊天',()=>{chooseDoc(p);libraryDialog.close();}),button('下载文字副本',()=>downloadBlob(new Blob([editor.value],{type:'text/plain;charset=utf-8'}),p.name.replace(/\.[^.]+$/,'')+`-v${p.version}.md`)),button('下载上传原件',async()=>{const r=await fetch('/api/library/original?id='+encodeURIComponent(id),{headers:{'X-Continuity-Token':token}});if(!r.ok)throw Error('原件读取失败');await downloadBlob(await r.blob(),p.name);}));
  if(p.version!==p.versions[0].version)actions.append(button('将此版本恢复为最新',async()=>{const r=await api('library/edit',{id,base_version:p.versions[0].version,text});await libraryList();await openDocument(id,r.version);}));
  libraryDialog.append(head,el('p','编辑和导出的是文字副本；Word/PDF 原件及其排版保持原样。'+p.note,'footnote'),versions,editor,actions);
  if(!libraryDialog.open)libraryDialog.showModal();
}
function initLibrary(){
  libraryDialog=el('dialog',undefined,'library-dialog');document.body.append(libraryDialog);
  $('choosedocument').onclick=()=>$('documentfile').click();$('documentfile').onchange=()=>uploadDocuments([...$('documentfile').files]).catch(e=>notify(e.message));
  $('libraryupload').onclick=()=>$('libraryfile').click();$('libraryfile').onchange=()=>uploadDocuments([...$('libraryfile').files],false).catch(e=>notify(e.message));
  $('librarysearch').onclick=()=>libraryList().catch(e=>notify(e.message));
  document.querySelector('[data-tab="library"]').addEventListener('click',()=>libraryList().catch(e=>notify(e.message)));
  $('librarycreate').onclick=async()=>{try{const name=$('libraryname').value.trim();if(!name)throw Error('请填写新文件名。');const r=await api('library/edit',{name,text:''});await libraryList();await openDocument(r.id,r.version);}catch(e){notify(e.message);}};
}

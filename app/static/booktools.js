'use strict';
let bookNotes=[],noteEditing=null,bookExtrasEpoch=0;
function noteColor(author){return author==='用户'?'#7dc9ed':'#c5a4ee';}
function matchingRange(root,text){
 const nodes=[],chars=[],walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){const n=walker.currentNode;for(let i=0;i<n.length;i++)if(!/\s/.test(n.data[i])){nodes.push([n,i]);chars.push(n.data[i]);}}
 const needle=text.replace(/\s/g,''),haystack=chars.join(''),start=haystack.indexOf(needle);
 if(!needle||start<0||haystack.indexOf(needle,start+1)>=0)return null;
 const [a,x]=nodes[start],[b,y]=nodes[start+needle.length-1],range=document.createRange();range.setStart(a,x);range.setEnd(b,y+1);return range;
}
function paintBookNotes(){
 if(!CSS.highlights||!window.Highlight)return;
 for(const author of ['用户','Agent']){
  const ranges=[];for(const note of bookNotes.filter(n=>n.unit===bookPage?.unit&&n.author===author&&n.quote)){
   for(const root of [$('booktext'),document.querySelector('.pdf-page .textLayer')].filter(Boolean)){const r=matchingRange(root,note.quote);if(r)ranges.push(r);}
  }CSS.highlights.set(author==='用户'?'user-note':'continuity-note',new Highlight(...ranges));
 }
}
async function refreshBookExtras(startIndex=false){
 if(!currentBook)return;const bid=currentBook.id,epoch=++bookExtrasEpoch;
 let [status,notes]=await Promise.all([api('books/index?id='+bid),api('books/notes?id='+bid+'&deleted=1')]);
 if(currentBook?.id!==bid||epoch!==bookExtrasEpoch)return;
 if(startIndex&&status.status==='not_started')status=await api('books/index',{id:bid,action:'start'});
 if(currentBook?.id!==bid||epoch!==bookExtrasEpoch)return;
 const labels={not_started:'未建立',queued:'排队中',running:'建立中',paused:'已暂停',done:'已完成',partial:'部分完成',error:'待重试'};
 $('bookindexstatus').textContent=`本地索引：${labels[status.status]||status.status} · ${status.indexed}/${status.total} 页/节 · ${status.empty_units} 页未提取到文字${Object.keys(status.errors).length?' · 有失败页，可重试':''}`;
 bookNotes=notes.filter(n=>!n.deleted);$('booknotelist').replaceChildren();
 for(const n of notes){
  const card=el('article',undefined,'book-note');card.style.borderColor=noteColor(n.author);
  card.append(el('small',`${n.author} · ${n.unit} 页/节 · ${n.kind==='bookmark'?'书签':'批注'}${n.deleted?' · 已移除':''}`));
  if(n.quote)card.append(el('blockquote',n.quote));if(n.body)card.append(el('p',n.body));
  if(!n.deleted){card.append(button('回原文',()=>jumpNote(n)),button('讨论这一处',async()=>{await jumpNote(n);$('prompt').value='我们接着讨论这条批注：'+n.body;$('prompt').focus();invalidateQuote();}));}
  card.append(button(n.deleted?'恢复':'编辑',()=>{if(n.deleted)return api('books/notes',{...n,deleted:false}).then(()=>refreshBookExtras());noteEditing=n;$('booknotebody').value=n.body;$('booknotemeta').textContent='编辑 '+n.author+' 的批注，版本 '+n.version;$('booknotebody').focus();}));
  if(!n.deleted)card.append(button('移除',()=>api('books/notes',{...n,deleted:true}).then(()=>refreshBookExtras())));
  $('booknotelist').append(card);
 }
 if(!notes.length)$('booknotelist').append(el('p','选中原文后保存批注，或把当前页加入书签。用户 是蓝色，Agent 是紫色。','footnote'));
 paintBookNotes();
 if(epubView)await paintEpubNotes();
}
async function paintEpubNotes(){
 if(!epubView)return;
 const view=epubView;for(const obj of view.renderer.getContents()){
  if(!obj.doc||!obj.overlayer)continue;
  // Draw by verified quotation in the current chapter; no fragile screen coordinates.
  for(const id of view._continuityNoteIds||[])obj.overlayer.remove(id);
  const {Overlayer}=await import('/vendor/foliate/overlayer.js');const ids=[];
  for(const n of bookNotes.filter(n=>n.unit===obj.index+1&&n.quote)){
   const walker=obj.doc.createTreeWalker(obj.doc.body,NodeFilter.SHOW_TEXT),map=[],chars=[];
   while(walker.nextNode()){const node=walker.currentNode;for(let i=0;i<node.length;i++)if(!/\s/.test(node.data[i])){map.push([node,i]);chars.push(node.data[i]);}}
   const needle=n.quote.replace(/\s/g,''),hay=chars.join(''),at=hay.indexOf(needle);if(at<0||hay.indexOf(needle,at+1)>=0)continue;
   const range=obj.doc.createRange();range.setStart(...map[at]);const [end,off]=map[at+needle.length-1];range.setEnd(end,off+1);
   obj.overlayer.add(n.id,range,Overlayer.highlight,{color:noteColor(n.author)});ids.push(n.id);
  }view._continuityNoteIds=ids;
 }
}
async function jumpNote(n){
 await openBook(n.book_id,n.unit);
 if(epubView&&n.location)await epubView.goTo(n.location);
 await loadBookText(n.unit,0,n.location||'');
 if(n.quote){pendingReading.selection=n.quote;readerChip();}
 $('booknotepanel').open=false;$('readerwork').scrollIntoView({block:'start'});
}
async function saveBookNote(kind){
 if(!pendingReading||readerTextBusy)throw Error('先打开并等待读取当前原文。');
 const data=noteEditing?{...noteEditing,body:$('booknotebody').value}:{book_id:currentBook.id,unit:pendingReading.unit,kind,quote:kind==='bookmark'?'':pendingReading.selection||'',location:pendingReading.location||'',body:$('booknotebody').value};
 await api('books/notes',data);noteEditing=null;$('booknotebody').value='';$('booknotemeta').textContent='批注已保存';await refreshBookExtras();
}
function initBookTools(){
 document.querySelector('.book-pane>.footnote').textContent='翻页和本地书内搜索免费。发问时自动参考书名、当前原文与相关记忆；Agent 可按需补查记忆、书籍与网页。原文未提取或未找到时如实说明。';
 $('preview').addEventListener('click',()=>{if($('chat').classList.contains('reader-chat')){$('chat').classList.add('reader-tools-open');$('readertools')?.setAttribute('aria-expanded','true');}});
 if(location.protocol==='https:')document.querySelector('header').append(button('退出登录',async()=>{const r=await fetch('/logout',{method:'POST',headers:{'X-Continuity-Token':token}});if(!r.ok)throw Error('退出未完成，请重试。');location.assign('/login');},'quiet'));
 const install=button('安装 / 添加到桌面',()=>notify(location.hostname==='127.0.0.1'?'电脑：在 Edge 或 Chrome 菜单中选择「应用 / 安装此网站」。手机需要打开云端地址，本机地址不能用于电脑关机后的手机聊天。':'iPhone：在 Safari 点分享 → 添加到主屏幕；电脑：在浏览器菜单中选择安装此网站。'),'quiet');document.querySelector('header').append(install);
 const panel=el('details');panel.id='booknotepanel';panel.append(el('summary','书签、双人批注与书内搜索'));
 const index=el('p',undefined,'footnote');index.id='bookindexstatus';panel.append(index,
  button('建立 / 继续索引',()=>api('books/index',{id:currentBook.id,action:'start'}).then(()=>refreshBookExtras())),
  button('暂停索引',()=>api('books/index',{id:currentBook.id,action:'pause'}).then(()=>refreshBookExtras())));
 const search=el('div',undefined,'searchbar'),input=el('input');input.id='bookquery';input.placeholder='搜索本书词句';input.setAttribute('aria-label','本书检索词');
 const all=el('label',undefined,'footnote'),check=el('input');check.type='checkbox';check.id='booksearchall';all.append(check,document.createTextNode(' 搜索全书（可能剧透）'));
 const results=el('div');results.id='booksearchresults';
 search.append(input,button('搜索',async()=>{const bid=currentBook.id;const data=await api('books/search?id='+bid+'&q='+encodeURIComponent(input.value)+(check.checked?'':'&max_unit='+(bookPage?.unit||1)));results.replaceChildren(el('p',data.scope,'footnote'));for(const hit of data.hits)results.append(button('第 '+hit.unit+' 页/节 · '+hit.excerpt,async()=>{await openBook(bid,hit.unit);await loadBookText(hit.unit,hit.offset);}));if(!data.hits.length)results.append(el('p','当前索引范围内未找到。'));}));panel.append(search,all,results);
 const meta=el('p','选择原文后写批注，或直接收藏当前页。','footnote');meta.id='booknotemeta';const body=el('textarea');body.id='booknotebody';body.rows=2;body.maxLength=4000;body.placeholder='写下想法…';body.setAttribute('aria-label','批注正文');
 const list=el('div');list.id='booknotelist';panel.append(meta,body,button('保存批注',()=>saveBookNote('note')),button('添加书签',()=>{noteEditing=null;return saveBookNote('bookmark');}),button('取消编辑',()=>{noteEditing=null;body.value='';meta.textContent='选择原文后写批注。';}),list);
 const positions=el('details');positions.append(el('summary','最近阅读位置（含另一端未覆盖的进度）'));
 positions.addEventListener('toggle',async()=>{if(!positions.open||!currentBook)return;const bid=currentBook.id;const rows=await api('books/positions?id='+bid);positions.querySelectorAll('button').forEach(b=>b.remove());for(const r of rows)positions.append(button(`${r.unit} 页/节 · ${new Date(r.time).toLocaleString()}${r.conflict?' · 另一端位置':''}`,()=>openBook(bid,r.unit)));});panel.append(positions);
 $('booklayout').before(panel);
 setInterval(()=>{if(currentBook&&$('reader').classList.contains('active')&&!readerBusy)refreshBookExtras().catch(()=>{});},5000);
 const sync=async()=>{
  if(document.hidden||syncBusy||activeJob||!state)return;syncBusy=true;
  try{const data=await api('sync');if(data.running_job){activeJob=data.running_job;invalidateQuote();poll();}
   if(data.latest_message!==lastSyncedMessage){const box=$('messages'),old=box.scrollTop,near=box.scrollHeight-box.clientHeight-old<100;await renderHistory();if(!near)box.scrollTop=old;}
  }catch{}finally{syncBusy=false;}
 };setInterval(sync,10000);document.addEventListener('continuity-resume',sync);
}

'use strict';
// Notes are ordinary authenticated storage operations, independent of the selected LLM.
(() => {
  const body=document.body, narrow=matchMedia('(max-width:1000px)');
  const pref=(key,fallback)=>{try{return localStorage.getItem(key)??fallback;}catch{return fallback;}};
  const savePref=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
  let enabled=pref('continuity-study','0')==='1', opened=false, deleted=false;
  let notes=new Map(), selection=null, loading=false, hasMore=false, requestVersion=0;
  const toggle=button('学习模式',()=>setMode(!enabled),'study-toggle');toggle.id='study-toggle';
  const openButton=button('笔记',()=>setOpen(!opened),'study-toggle');openButton.id='study-open';openButton.setAttribute('aria-controls','study-panel');
  document.querySelector('body>header').append(toggle,openButton);
  const panel=el('aside',undefined,'study-panel');panel.id='study-panel';panel.setAttribute('aria-label','学习笔记');panel.hidden=true;
  const heading=el('div',undefined,'study-heading');
  const title=el('div');title.append(el('span','留住值得再读的话','study-eyebrow'),el('h2','学习笔记'));
  const close=button('收起',()=>setOpen(false),'study-close');close.id='study-close';heading.append(title,close);
  const hint=el('p','长按或右键消息收藏。选中笔记文字，再加粗、高亮或评论。','study-hint');
  const toolbar=el('div',undefined,'study-toolbar');toolbar.setAttribute('aria-label','笔记批注');
  const formatButtons=['bold','highlight','comment'].map((kind,i)=>{const b=button(['加粗','高亮','评论'][i],()=>annotate(kind));b.onpointerdown=e=>e.preventDefault();toolbar.append(b);return b;});
  const tabs=el('div',undefined,'study-tabs');
  const activeTab=button('我的摘录',()=>switchList(false)),trashTab=button('回收站',()=>switchList(true));
  const refreshButton=button('刷新',()=>loadNotes());tabs.append(activeTab,trashTab,refreshButton);
  const list=el('div',undefined,'study-list');list.id='study-list';
  const footer=el('small','已接入共同记忆 · 收藏与批注不调用付费模型','study-footer');
  panel.append(heading,hint,toolbar,tabs,list,footer);
  const backdrop=button('关闭笔记',()=>setOpen(false),'study-backdrop');backdrop.hidden=true;backdrop.tabIndex=-1;
  const menu=el('div',undefined,'study-menu');menu.hidden=true;menu.setAttribute('role','menu');
  const dialog=el('dialog',undefined,'study-comment-dialog');dialog.setAttribute('aria-labelledby','study-comment-title');
  const dialogTitle=el('h3','添加评论');dialogTitle.id='study-comment-title';
  const quote=el('blockquote'),input=el('textarea');input.rows=5;input.maxLength=4000;input.setAttribute('aria-label','评论内容');
  const actions=el('div',undefined,'actions');const cancel=button('取消',()=>dialog.close()),submit=button('保存评论',saveComment);
  actions.append(cancel,submit);dialog.append(dialogTitle,quote,input,actions);
  let commentTarget=null;
  document.body.append(backdrop,panel,menu,dialog);

  function layout(){
    const visible=enabled&&opened;
    body.classList.toggle('study-mode',enabled);body.classList.toggle('study-notes-open',visible);
    toggle.setAttribute('aria-pressed',String(enabled));toggle.textContent=enabled?'退出学习':'学习模式';
    openButton.hidden=!enabled;openButton.setAttribute('aria-expanded',String(visible));panel.hidden=!visible;
    const modal=visible&&narrow.matches;backdrop.hidden=!modal;
    panel.setAttribute('role',modal?'dialog':'complementary');
    if(modal)panel.setAttribute('aria-modal','true');else panel.removeAttribute('aria-modal');
    // On phones the notes sheet owns focus; no accidental typing into the covered chat.
    document.querySelector('main').inert=modal;
    document.querySelector('body>header').inert=modal;
    if($('appsidebar'))$('appsidebar').inert=modal||(!body.classList.contains('sidebar-open')&&matchMedia('(max-width:760px)').matches);
    document.querySelector('meta[name="theme-color"]').content=enabled?'#f5f1e9':'#212121';
    formatButtons.forEach(b=>b.disabled=!selection||deleted);
  }
  function setMode(value){enabled=value;savePref('continuity-study',value?'1':'0');if(value){tab('chat');setOpen(true);}else{setOpen(false);layout();}}
  function setOpen(value){if(value){if($('chat').classList.contains('reader-chat'))undockChat();tab('chat');}opened=value;hideMenu();layout();if(value){loadNotes().catch(e=>notify(e.message));if(narrow.matches)close.focus();}else if(enabled)openButton.focus();}
  function switchList(value){deleted=value;selection=null;loadNotes();}
  async function loadNotes(more=false){
    if(loading&&more)return;
    const version=++requestVersion;loading=true;refreshButton.disabled=true;
    try{
      const before=more&&notes.size?Math.min(...notes.keys()):0;
      const result=await api(`study?deleted=${deleted?1:0}&before=${before}`);
      if(version!==requestVersion)return;
      if(!more)notes=new Map();result.items.forEach(n=>notes.set(n.id,n));hasMore=result.has_more;
      selection=null;render();
    }catch(e){notify(e.message);if(!notes.size)list.replaceChildren(el('p','笔记暂时未加载，请点刷新重试。','study-hint'));}
    finally{if(version===requestVersion){loading=false;refreshButton.disabled=false;}}
  }
  async function collect(id){
    const note=await api('study/collect',{source_chat_id:id});
    deleted=false;opened=true;layout();await loadNotes();
    // An older, already-collected note may be outside the first page.
    if(!notes.has(note.id)){notes.set(note.id,note);render();}
    $('study-note-'+note.id)?.scrollIntoView({block:'nearest'});
    if(narrow.matches)close.focus();notify('已收入学习笔记，加入同一套记忆检索。');
  }
  async function update(note,data){
    try{
      const changed=await api('study/change',{id:note.id,revision:note.revision,...data});
      if(Boolean(changed.deleted)!==deleted)notes.delete(changed.id);else notes.set(changed.id,changed);
      selection=null;render();return changed;
    }catch(e){notify(e.message);throw e;}
  }
  function noteText(note){
    const node=el('div',undefined,'study-note-text');node.dataset.noteId=note.id;
    const chars=Array.from(note.text),points=[...new Set([0,chars.length,...note.annotations.flatMap(a=>[a.start,a.end])])].sort((a,b)=>a-b);
    for(let i=0;i<points.length-1;i++){
      const start=points[i],end=points[i+1],spans=note.annotations.filter(a=>a.start<=start&&a.end>=end);
      let piece=document.createTextNode(chars.slice(start,end).join(''));
      for(const [kind,tag] of [['bold','strong'],['highlight','mark'],['comment','span']])if(spans.some(a=>a.kind===kind)){
        const wrap=el(tag);if(kind==='comment'){wrap.className='study-commented';wrap.title=spans.filter(a=>a.kind===kind).map(a=>a.comment).join('\n');}wrap.append(piece);piece=wrap;
      }
      node.append(piece);
    }
    return node;
  }
  function render(){
    const scroll=list.scrollTop;list.replaceChildren();
    activeTab.setAttribute('aria-pressed',String(!deleted));trashTab.setAttribute('aria-pressed',String(deleted));
    if(!notes.size)list.append(el('p',deleted?'回收站是空的。':'把一句重要的话留在这里。\n在消息上长按、右键，或点「记笔记」。','study-empty'));
    for(const note of [...notes.values()].sort((a,b)=>b.id-a.id)){
      const card=el('article',undefined,'study-note');card.id='study-note-'+note.id;card.dataset.noteId=note.id;
      const top=el('div',undefined,'study-note-top');top.append(el('small',`${note.source_role==='user'?'用户':'Agent'} · ${time(note.source_time)}`));
      const more=button('···',e=>noteMenu(note,more.getBoundingClientRect().left,more.getBoundingClientRect().bottom),'study-more');more.setAttribute('aria-label','笔记操作');top.append(more);
      card.append(top,noteText(note));
      for(const annotation of note.annotations.filter(a=>a.kind==='comment')){
        const c=el('div',undefined,'study-comment');
        c.append(el('blockquote',Array.from(note.text).slice(annotation.start,annotation.end).join('')),el('p',annotation.comment));
        if(!deleted)c.append(button('删除评论',()=>update(note,{action:'remove_annotation',annotation_id:annotation.id})));card.append(c);
      }
      const bottom=el('div',undefined,'study-note-actions');bottom.append(button('↗ 回到对话',()=>locate(note)));
      if(deleted)bottom.append(button('恢复',()=>update(note,{action:'restore'})));
      else{
        const marks=note.annotations.filter(a=>a.kind!=='comment');
        if(marks.length){const d=el('details');d.append(el('summary','管理标记'));for(const a of marks)d.append(button(`移除${a.kind==='bold'?'加粗':'高亮'}：${Array.from(note.text).slice(a.start,a.end).join('').slice(0,20)}`,()=>update(note,{action:'remove_annotation',annotation_id:a.id})));bottom.append(d);}
      }
      card.append(bottom);list.append(card);
    }
    if(hasMore)list.append(button('加载更早笔记',()=>loadNotes(true)));
    list.scrollTop=scroll;layout();
  }
  function readSelection(){
    const s=window.getSelection();if(!s?.rangeCount||s.isCollapsed)return;
    const r=s.getRangeAt(0),anchor=r.startContainer.nodeType===1?r.startContainer:r.startContainer.parentElement;
    const text=anchor.closest('.study-note-text');if(!text||!text.contains(r.endContainer))return;
    const prefix=document.createRange();prefix.selectNodeContents(text);prefix.setEnd(r.startContainer,r.startOffset);
    selection={id:Number(text.dataset.noteId),start:Array.from(prefix.toString()).length,end:Array.from(prefix.toString()+r.toString()).length};
    formatButtons.forEach(b=>b.disabled=deleted);
  }
  document.addEventListener('selectionchange',()=>{
    if(dialog.open||!menu.hidden)return;
    const s=window.getSelection();if(s?.isCollapsed){selection=null;formatButtons.forEach(b=>b.disabled=true);}else readSelection();
  });
  async function annotate(kind,target=selection){
    if(!target||!notes.has(target.id))throw Error('请先选中笔记里的文字。');
    const note=notes.get(target.id);
    if(kind==='comment'){
      commentTarget={note,...target};quote.textContent=Array.from(note.text).slice(target.start,target.end).join('');input.value='';dialog.showModal();input.focus();return;
    }
    await update(note,{action:'annotate',kind,start:target.start,end:target.end});
  }
  async function saveComment(){
    if(!input.value.trim())throw Error('先写一点评论吧。');
    submit.disabled=true;
    try{await update(commentTarget.note,{action:'annotate',kind:'comment',start:commentTarget.start,end:commentTarget.end,comment:input.value});dialog.close();}
    finally{submit.disabled=false;}
  }
  async function locate(note){if(narrow.matches)setOpen(false);await locateChatMessage(note.source_chat_id);}
  function hideMenu(){menu.hidden=true;}
  function showMenu(items,x,y){
    menu.replaceChildren(...items.map(([label,fn])=>{const b=button(label,()=>{hideMenu();return fn();});b.setAttribute('role','menuitem');return b;}));
    menu.hidden=false;menu.style.left=Math.max(8,Math.min(x,innerWidth-menu.offsetWidth-8))+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-menu.offsetHeight-8))+'px';
    menu.querySelector('button')?.focus({preventScroll:true});
  }
  function noteMenu(note,x,y){
    readSelection();const target=selection?.id===note.id?{...selection}:{id:note.id,start:0,end:Array.from(note.text).length};
    const scope=selection?.id===note.id?'所选':'整条';
    const items=deleted?[['恢复笔记',()=>update(note,{action:'restore'})]]:[
      [scope+'加粗',()=>annotate('bold',target)],[scope+'高亮',()=>annotate('highlight',target)],['添加评论',()=>annotate('comment',target)]];
    items.push(['回到对话',()=>locate(note)]);if(!deleted)items.push(['移入回收站',()=>update(note,{action:'trash'})]);showMenu(items,x,y);
  }
  function messageMenu(message,x,y){showMenu([['添加到学习笔记',()=>collect(Number(message.dataset.messageId))]],x,y);}
  document.addEventListener('contextmenu',e=>{
    if(!enabled)return;const note=e.target.closest('.study-note'),message=e.target.closest('.message[data-message-id]');
    if(note){e.preventDefault();noteMenu(notes.get(Number(note.dataset.noteId)),e.clientX,e.clientY);}
    else if(message&&!e.target.closest('a,button,input,textarea')){e.preventDefault();messageMenu(message,e.clientX,e.clientY);}
  });
  let hold=null,origin=null,heldUntil=0;
  function cancelHold(){clearTimeout(hold);hold=null;origin=null;}
  document.addEventListener('pointerdown',e=>{
    if(!menu.hidden&&!menu.contains(e.target))hideMenu();
    if(!enabled||e.pointerType==='mouse'||e.target.closest('button,a,input,textarea'))return;
    const message=e.target.closest('.message[data-message-id]');if(!message)return;
    cancelHold();origin={x:e.clientX,y:e.clientY};hold=setTimeout(()=>{heldUntil=Date.now()+800;messageMenu(message,e.clientX,e.clientY);cancelHold();},600);
  });
  document.addEventListener('pointermove',e=>{if(origin&&Math.hypot(e.clientX-origin.x,e.clientY-origin.y)>12)cancelHold();},{passive:true});
  ['pointerup','pointercancel','scroll'].forEach(event=>document.addEventListener(event,cancelHold,true));
  document.addEventListener('click',e=>{if(menu.contains(e.target)){heldUntil=0;return;}if(Date.now()<heldUntil&&e.target.closest('.message[data-message-id]')){e.preventDefault();e.stopPropagation();}},true);
  // Visible fallback also supports keyboard and iOS native text-selection quirks.
  function decorate(){for(const m of document.querySelectorAll('.message[data-message-id]'))if(!m.querySelector('.study-collect'))m.append(button('＋ 记笔记',()=>collect(Number(m.dataset.messageId)),'study-collect'));}
  new MutationObserver(decorate).observe($('messages'),{childList:true});decorate();
  document.addEventListener('keydown',e=>{
    if(document.querySelector('dialog[open]'))return;
    if(!menu.hidden){
      const buttons=[...menu.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);
      if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();buttons[(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}
      if(e.key==='Escape'){hideMenu();close.focus();}return;
    }
    if(opened&&enabled&&e.key==='Escape'){setOpen(false);e.preventDefault();}
    if(opened&&enabled&&narrow.matches&&e.key==='Tab'){
      const els=[...panel.querySelectorAll('button:not(:disabled),summary,textarea')].filter(n=>n.getClientRects().length),first=els[0],last=els.at(-1);
      if(e.shiftKey&&document.activeElement===first){last.focus();e.preventDefault();}else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault();}
    }
  });
  document.addEventListener('continuity-tab',e=>{if(e.detail!=='chat'&&opened)setOpen(false);});
  narrow.addEventListener('change',layout);
  // The sources selector is filled asynchronously by app.js; add the same memory source afterward.
  const source=$('source');
  const ensureSource=()=>{if(!source.querySelector('option[value="__study__"]'))source.append(new Option('学习笔记 · 摘录和批注','__study__'));};
  new MutationObserver(ensureSource).observe(source,{childList:true});ensureSource();
  // Explicit refresh avoids replacing an in-progress text selection or comment on resume.
  layout();if(enabled)setOpen(!narrow.matches);
})();

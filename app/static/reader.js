'use strict';
let pendingReading=null, currentBook=null, bookPage=null, pdfDoc=null, epubView=null, readerBusy=false, readerTextBusy=false;
let readerEpoch=0, pageEpoch=0, pdfModule, pdfTask, positionQueue=Promise.resolve();
let readerResizeTimer, readerDrag=false, pdfZoom='fit';
const positionRevisions=new Map();
function setReaderWidth(value){
  const n=Math.max(35,Math.min(75,Number(value)||58));
  $('booklayout').style.setProperty('--book-share',n+'%');
  $('bookdivider').setAttribute('aria-valuenow',Math.round(n));
  try{localStorage.setItem('continuity-reader-width',String(n));}catch{}
}
function schedulePdfResize(){
  clearTimeout(readerResizeTimer);
  if(!pdfDoc||!bookPage||!$('reader').classList.contains('active'))return;
  readerResizeTimer=setTimeout(()=>{
    if(readerBusy||readerDrag){schedulePdfResize();return;}
    renderPdf(bookPage.unit,true).catch(e=>notify(e.message));
  },180);
}
function readingLabel(r){return `${r.name||'共读原文'} · ${r.kind==='epub'?'第 '+r.unit+' 节':'PDF 第 '+r.unit+' 页'}`;}
function readerChip(){
  $('readingcontext').replaceChildren();
  if(pendingReading){$('readingcontext').append(el('span',`共读：${readingLabel(pendingReading)}${pendingReading.selection?' · 已选 '+pendingReading.selection.length+' 字':' · 当前原文片段'}`),button('清除选句',()=>{pendingReading.selection='';readerChip();}));}
  invalidateQuote();
}
function dockChat(){
  $('readerchat').append($('chat'));$('chat').classList.remove('panel');$('chat').classList.add('reader-chat');
  $('messages').scrollTop=$('messages').scrollHeight;
}
function undockChat(){
  if($('chat').classList.contains('reader-chat')){document.querySelector('main').prepend($('chat'));$('chat').classList.remove('reader-chat');$('chat').classList.add('panel');}
  pendingReading=null;readerChip();
}
async function bookshelf(){
  const rows=await api('books');$('booklist').replaceChildren();
  for(const r of rows){const card=el('article',undefined,'book-card');let pos={};try{pos=JSON.parse(r.position);}catch{}
    card.append(el('span',r.kind.toUpperCase(),'eyebrow'),el('h3',r.name),el('p',`${r.units} ${r.kind==='pdf'?'页':'节'}${pos.unit?' · 上次读到 '+pos.unit:''}`,'footnote'),button(pos.unit?'继续阅读':'打开书',()=>openBook(r.id)));
    $('booklist').append(card);
  }
  if(!rows.length)$('booklist').append(el('p','先导入一本 EPUB 或 PDF。原书保存在本机，打开和翻页不会调用 AI。','footnote'));
}
async function importBooks(files){
  if(readerBusy)throw Error('正在处理书籍，请稍等。');readerBusy=true;$('bookimport').disabled=true;
  try{for(const f of files){
    if(f.size>25*1024*1024)throw Error('首版每本书最多 25 MB，较大的扫描书稍后支持。');
    $('readerstatus').textContent='正在导入 '+f.name;
    const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error('文件读取失败'));r.readAsDataURL(f);});
    await api('books/upload',{name:f.name,data});
  }await bookshelf();$('readerstatus').textContent='导入完成，尚未调用模型。';}
  finally{readerBusy=false;$('bookimport').disabled=false;$('bookfile').value='';}
}
function queuePosition(position){
  positionQueue=positionQueue.catch(()=>{}).then(async()=>{const saved=await api('books/position',{...position,base_revision:positionRevisions.get(position.id)||0});positionRevisions.set(position.id,saved.revision);}).catch(e=>{notify('进度尚未同步：'+e.message);throw e;});
  positionQueue.catch(()=>{});
}
async function loadBookText(unit,offset=0,location='',visible=''){
  const epoch=++pageEpoch,bid=currentBook.id;
  readerTextBusy=true;pendingReading=null;readerChip();$('booktext').textContent='正在读取原文…';
  let page;try{page=await api(`books/read?id=${bid}&unit=${unit}&offset=${offset}`);}finally{if(epoch===pageEpoch){readerTextBusy=false;invalidateQuote();}}
  if(epoch!==pageEpoch||currentBook?.id!==bid)return;
  bookPage=page;pendingReading=$('reader').classList.contains('active')?{id:bid,name:currentBook.name,kind:currentBook.kind,unit,offset,location,selection:visible.trim().slice(0,1200)}:null;
  $('bookunit').value=unit;$('bookposition').textContent=`${unit} / ${currentBook.units} ${currentBook.kind==='pdf'?'页':'节'}`;
  $('booktext').textContent=page.text||'此页尚未提取到文字，可能需要 OCR。可以看原页，但 Agent 不能声称读到了文字。';
  $('textnext').disabled=page.next_offset===null;$('textprev').disabled=offset===0;
  $('textscope').textContent=`提取原文 ${offset}–${Math.min(offset+4500,page.chars)} / ${page.chars} 字${page.empty?' · 未识字':''}。在这里也可以选择句子。`;
  readerChip();queuePosition({id:bid,unit,location});
  if(typeof refreshBookExtras==='function')refreshBookExtras(true).catch(e=>notify(e.message));
}
function captureSelection(doc,container){
  const selection=doc.getSelection();if(!selection||selection.isCollapsed||!pendingReading)return;
  if(container&&!container.contains(selection.anchorNode))return;
  const text=selection.toString().trim();if(!text)return;
  if(text.length>2500){notify('请选短一点，最多 2500 字。');return;}
  pendingReading.selection=text;retryOf=null;readerChip();
}
async function renderPdf(unit,keepContext=false){
  const epoch=++readerEpoch;readerBusy=true;
  const stage=$('bookstage'),oldPage=stage.querySelector('.pdf-page');
  const scrollRatio=oldPage?stage.scrollTop/oldPage.offsetHeight:0;
  try{
    const page=await pdfDoc.getPage(unit);if(epoch!==readerEpoch)return;
    const available=Math.max(100,stage.clientWidth-24),base=page.getViewport({scale:1});
    const viewport=page.getViewport({scale:pdfZoom==='fit'?available/base.width:Number(pdfZoom)}),box=el('div',undefined,'pdf-page');
    box.style.width=viewport.width+'px';box.style.height=viewport.height+'px';box.style.setProperty('--scale-factor',viewport.scale);
    const canvas=el('canvas'),layer=el('div',undefined,'textLayer');
    const dpr=Math.min(window.devicePixelRatio||1,2,4096/Math.max(viewport.width,viewport.height));
    canvas.width=Math.ceil(viewport.width*dpr);canvas.height=Math.ceil(viewport.height*dpr);
    canvas.style.width=viewport.width+'px';canvas.style.height=viewport.height+'px';
    canvas.setAttribute('aria-label','PDF 原页');box.append(canvas,layer);$('bookstage').replaceChildren(box);
    await page.render({canvasContext:canvas.getContext('2d'),viewport,transform:[dpr,0,0,dpr,0,0]}).promise;
    const text=await page.getTextContent();await new pdfModule.TextLayer({textContentSource:text,container:layer,viewport}).render();
    if(epoch!==readerEpoch)return;
    if(keepContext){stage.scrollTop=scrollRatio*viewport.height;if(typeof paintBookNotes==='function')paintBookNotes();}
    else{stage.scrollTop=0;stage.scrollLeft=0;await loadBookText(unit);}
  }finally{readerBusy=false;}
}
async function openBook(id,unitOverride){
  if(readerBusy)throw Error('请等当前书页加载完成。');
  readerBusy=true;let r;
  try{const books=await api('books');r=books.find(b=>b.id===id);if(!r)throw Error('书籍不存在。');}
  catch(e){readerBusy=false;throw e;}
  ++readerEpoch;++pageEpoch;pendingReading=null;readerChip();
  try{
    if(epubView){epubView.close();epubView.remove();epubView=null;}if(pdfTask){await pdfTask.destroy();pdfTask=null;pdfDoc=null;}
    currentBook=r;bookPage=null;tab('reader');$('readerwork').hidden=false;dockChat();$('booktitle').textContent=r.name;$('bookstage').replaceChildren();
    $('readerstatus').textContent='正在打开原书…';
    let pos={};try{pos=JSON.parse(r.position);}catch{};positionRevisions.set(id,pos.revision||0);const unit=unitOverride||pos.unit||1;
    const response=await fetch('/api/books/file?id='+id,{headers:{'X-Continuity-Token':token}});if(!response.ok)throw Error('读取原书失败。');const bytes=await response.arrayBuffer();
    $('bookfont').hidden=r.kind!=='epub';$('bookzoom').hidden=r.kind!=='pdf';$('bookunit').max=r.units;
    if(r.kind==='pdf'){
      pdfModule=await import('/vendor/pdfjs/legacy/build/pdf.mjs');pdfModule.GlobalWorkerOptions.workerSrc='/vendor/pdfjs/legacy/build/pdf.worker.mjs';
      pdfTask=pdfModule.getDocument({data:new Uint8Array(bytes),isEvalSupported:false,useWasm:false,cMapUrl:'/vendor/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/vendor/pdfjs/standard_fonts/'});pdfDoc=await pdfTask.promise;
      await renderPdf(unit);
    }else{
      await import('/vendor/foliate/view.js');const view=document.createElement('foliate-view');epubView=view;$('bookstage').append(view);
      await view.open(new File([bytes],r.name,{type:'application/epub+zip'}));
      view.addEventListener('load',e=>{e.detail.doc.addEventListener('mouseup',()=>captureSelection(e.detail.doc));e.detail.doc.addEventListener('touchend',()=>captureSelection(e.detail.doc));});
      view.addEventListener('relocate',e=>{const d=e.detail,u=d.section.current+1;loadBookText(u,0,d.cfi,d.range?.toString()||'').catch(e=>notify(e.message));});
      view.renderer.setStyles?.('html{color:#24202b;background:#faf6ed;font-size:19px}body{padding:12px;line-height:1.8}');
      if(unitOverride)await view.goTo(unit-1);else await view.init({lastLocation:pos.location||undefined});
    }
    $('readerstatus').textContent='阅读不调用 AI。发问时自动带当前片段，可在原页或提取原文中划词。';
  }finally{readerBusy=false;}
}
async function bookStep(delta){
  if(readerBusy||!currentBook)return;
  if(epubView){await(delta>0?epubView.next():epubView.prev());return;}
  const unit=Math.min(currentBook.units,Math.max(1,(bookPage?.unit||1)+delta));await renderPdf(unit);
}
function appendReading(node,bubble,r){
  if(!r)return;
  const units=new Set(r.cited_units||[r.unit]),walker=document.createTreeWalker(bubble,NodeFilter.SHOW_TEXT),nodes=[];
  while(walker.nextNode())if(/\[书页\d+\]/.test(walker.currentNode.nodeValue))nodes.push(walker.currentNode);
  for(const text of nodes){const frag=document.createDocumentFragment();let last=0;for(const m of text.nodeValue.matchAll(/\[书页(\d+)\]/g)){frag.append(document.createTextNode(text.nodeValue.slice(last,m.index)));const unit=Number(m[1]);frag.append(units.has(unit)?button(String(unit),()=>openBook(r.id,unit),'citation'):document.createTextNode(m[0]));last=m.index+m[0].length;}frag.append(document.createTextNode(text.nodeValue.slice(last)));text.replaceWith(frag);}
  node.append(button(readingLabel(r)+' · 回到原书',()=>openBook(r.id,r.unit),'reading-link'));
}
function initReader(){
  initBookTools();
  const divider=$('bookdivider'),layout=$('booklayout');
  let stored=58;try{stored=localStorage.getItem('continuity-reader-width')||58;}catch{}setReaderWidth(stored);
  const updateDrag=e=>{const rect=layout.getBoundingClientRect();setReaderWidth((e.clientX-rect.left)/rect.width*100);};
  divider.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();readerDrag=true;divider.setPointerCapture(e.pointerId);document.body.classList.add('reader-resizing');updateDrag(e);});
  divider.addEventListener('pointermove',e=>{if(readerDrag)updateDrag(e);});
  const finishDrag=()=>{readerDrag=false;document.body.classList.remove('reader-resizing');schedulePdfResize();};
  divider.addEventListener('pointerup',finishDrag);divider.addEventListener('pointercancel',finishDrag);divider.addEventListener('lostpointercapture',finishDrag);
  divider.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const n=Number(divider.getAttribute('aria-valuenow'));setReaderWidth(e.key==='Home'?35:e.key==='End'?75:n+(e.key==='ArrowRight'?2:-2));schedulePdfResize();});
  new ResizeObserver(()=>{if(pdfZoom==='fit')schedulePdfResize();}).observe($('bookstage'));
  $('bookzoom').onchange=()=>{pdfZoom=$('bookzoom').value;schedulePdfResize();};
  const more=button('选项与费用',()=>{const expanded=$('chat').classList.toggle('reader-tools-open');more.setAttribute('aria-expanded',String(expanded));},'reader-tools-toggle quiet');
  more.id='readertools';more.setAttribute('aria-expanded','false');document.querySelector('.compose-bottom').prepend(more);
  $('bookfocus').onclick=()=>{const on=$('reader').classList.toggle('reader-focus');$('bookfocus').textContent=on?'显示书架':'专注阅读';$('bookfocus').setAttribute('aria-pressed',String(on));if(on)$('readerwork').scrollIntoView({block:'start'});};
  $('bookimport').onclick=()=>$('bookfile').click();$('bookfile').onchange=()=>importBooks([...$('bookfile').files]).catch(e=>notify(e.message));
  $('bookrefresh').onclick=()=>bookshelf().catch(e=>notify(e.message));
  document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>{
    if(b.dataset.tab==='reader'){bookshelf().catch(e=>notify(e.message));if(currentBook){dockChat();if(bookPage){pendingReading={id:currentBook.id,name:currentBook.name,kind:currentBook.kind,unit:bookPage.unit,offset:bookPage.offset,selection:'',location:epubView?.lastLocation?.cfi||''};readerChip();}}}
    else{undockChat();tab(b.dataset.tab);}
  }));
  $('bookprev').onclick=()=>bookStep(-1).catch(e=>notify(e.message));$('booknext').onclick=()=>bookStep(1).catch(e=>notify(e.message));
  $('bookgo').onclick=()=>{const n=Number($('bookunit').value);if(!currentBook||readerBusy||!Number.isInteger(n)||n<1||n>currentBook.units)return;Promise.resolve(epubView?epubView.goTo(n-1):renderPdf(n)).catch(e=>notify(e.message));};
  $('bookfont').onchange=()=>epubView?.renderer.setStyles?.(`html{color:#24202b;background:#faf6ed;font-size:${Number($('bookfont').value)}px}body{padding:12px;line-height:1.8}`);
  $('booktext').addEventListener('mouseup',()=>captureSelection(document,$('booktext')));$('booktext').addEventListener('touchend',()=>captureSelection(document,$('booktext')));
  $('bookstage').addEventListener('mouseup',()=>captureSelection(document,$('bookstage')));
  $('textnext').onclick=()=>bookPage?.next_offset!==null&&loadBookText(bookPage.unit,bookPage.next_offset,pendingReading?.location).catch(e=>notify(e.message));
  $('textprev').onclick=()=>loadBookText(bookPage.unit,Math.max(0,bookPage.offset-4500),pendingReading?.location).catch(e=>notify(e.message));
  $('bookask').onclick=()=>{$('prompt').focus();$('prompt').scrollIntoView({block:'center',behavior:'smooth'});};
}

'use strict';
// Deliberately small Markdown subset. Raw HTML is always text, never innerHTML.
function appendCitedText(node,text,refs,openReference,webSources=[]){
  const inline=(host,value,depth=0)=>{
    if(depth>6){appendCitationText(host,value,refs,openReference,webSources);return;}
    const pattern=/\\([\\*_`])|(`+)([^\n]*?)\2|\*\*\*(?=\S)([\s\S]*?\S)\*\*\*|\*\*(?=\S)([\s\S]*?\S)\*\*|__(?=\S)([\s\S]*?\S)__|\*(?=\S)([^*\n]*?\S)\*/g;
    let at=0;
    for(const m of value.matchAll(pattern)){
      appendCitationText(host,value.slice(at,m.index),refs,openReference,webSources);
      if(m[1])host.append(document.createTextNode(m[1]));
      else if(m[2]){const code=document.createElement('code');code.textContent=m[3];host.append(code);}
      else{const part=document.createElement(m[7]!==undefined?'em':'strong');
        if(m[4]!==undefined){const em=document.createElement('em');inline(em,m[4],depth+1);part.append(em);}
        else inline(part,m[5]??m[6]??m[7],depth+1);host.append(part);
      }
      at=m.index+m[0].length;
    }
    appendCitationText(host,value.slice(at),refs,openReference,webSources);
  };
  const fences=/^```[^\n]*\n([\s\S]*?)^```[ \t]*(?:\n|$)/gm;let at=0;
  for(const m of text.matchAll(fences)){inline(node,text.slice(at,m.index));const pre=document.createElement('pre'),code=document.createElement('code');code.textContent=m[1];pre.append(code);node.append(pre);at=m.index+m[0].length;}
  inline(node,text.slice(at));
}

// Original message text stays untouched. Expand grouped citation syntax only at render time.
function appendCitationText(node, text, refs, openReference, webSources=[]) {
  const pattern = /[\[【]\s*(记忆|网页)\s*\d+(?:\s*[,，、;；]\s*(?:\1\s*)?\d+)*\s*[\]】]/g;
  let at = 0;
  for (const match of text.matchAll(pattern)) {
    node.append(document.createTextNode(text.slice(at, match.index)));
    for (const number of [...new Set(match[0].match(/\d+/g).map(Number))]) {
      if(match[1]==='网页'){
        const source=webSources[number-1];
        if(source && safeWebURL(source.url)){
          const link=document.createElement('a');link.className='citation web-citation';
          link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';
          link.textContent='网'+number;link.title=source.title;
          link.setAttribute('aria-label','打开网页 '+number+'：'+source.title);node.append(link);
        }else{const label=document.createElement('span');label.className='citation-missing';label.textContent='[网页'+number+']';node.append(label);}
        continue;
      }
      const ref = refs[number - 1];
      if (ref) {
        const link = document.createElement('button');
        link.type = 'button'; link.className = 'citation'; link.textContent = String(number);
        link.setAttribute('aria-label', '查看记忆 ' + number + ' 原文');
        link.title = '记忆 ' + number + ' · ' + ref.filename;
        link.addEventListener('click', () => Promise.resolve(openReference(ref.id)).catch(e => notify(e.message)));
        node.append(link);
      } else {
        const missing = document.createElement('span'); missing.className = 'citation-missing';
        missing.textContent = '[记忆' + number + ']'; missing.title = '这条回复没有保存对应的原文引用';
        node.append(missing);
      }
    }
    at = match.index + match[0].length;
  }
  node.append(document.createTextNode(text.slice(at)));
}

function safeWebURL(value){
  try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password;}catch{return false;}
}
function appendWebSources(node,sources){
  if(!sources?.length)return;
  const detail=document.createElement('details');detail.className='web-sources';
  const summary=document.createElement('summary');summary.textContent='网页来源 · '+sources.length;detail.append(summary);
  sources.forEach((source,index)=>{
    if(!safeWebURL(source.url))return;
    const card=document.createElement('article');card.className='web-source';
    const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='网页'+(index+1)+' · '+source.title;
    const meta=document.createElement('small');meta.textContent=new URL(source.url).hostname+' · 检索于 '+new Date(source.retrieved_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
    const snippet=document.createElement('p');snippet.textContent=source.snippet;
    card.append(link,meta,snippet);detail.append(card);
  });node.append(detail);
}

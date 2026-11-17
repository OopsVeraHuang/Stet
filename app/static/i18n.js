'use strict';
// Translate interface copy only, never user originals, notes, model replies or form values.
(() => {
  let locale='zh-CN';
  try{locale=localStorage.getItem('stet-language')||localStorage.getItem('continuity-language')||'zh-CN';}catch{}
  if(!['zh-CN','en'].includes(locale))locale='zh-CN';
  const strings=window.CONTINUITY_EN||{}, originals=new WeakMap(), attributes=new WeakMap();
  const protectedContent='script,style,textarea,pre,code,[data-no-i18n],.bubble,.original,.text,.study-note-text,.study-comment p,.study-comment blockquote,.study-comment-dialog blockquote,#booktext,#bookstage,#livecaptions,#booktitle,#profileguide,#provenance-content dd,#provenance-content h3,.batch>strong,.book-card h3,.document-card h3,header h1';
  Object.assign(strings,{'可编辑文字副本；原件未覆盖。':'Editable text copy. The original file is preserved.','记录时间未知':'Time not recorded','分支未知，保留缺失，不自动补齐。':'Branch unknown; no value will be invented.','时区未知，保留缺失，不自动补齐。':'Timezone unknown; no value will be invented.','时间精度未知，保留缺失，不自动补齐。':'Time precision unknown; no value will be invented.','记录时间未知，保留缺失，不自动补齐。':'Recorded time unknown; no value will be invented.','角色未知，保留缺失，不自动补齐。':'Speaker unknown; no value will be invented.'});
  // Anchored templates. Captured source names, numbers and timestamps are kept verbatim.
  const patterns=[
    [/^查看本次参考的 (\d+) 段原文$/, 'View $1 sources'],
    [/^记忆(\d+) · 原文$/, 'Memory $1 · Source'],
    [/^显示 (\d+) \/ (\d+) 条记录$/, 'Showing $1 / $2 records'],
    [/^找到 (\d+) 条字面匹配；没有生成模型回答。$/, '$1 literal matches · No model generation'],
    [/^已保存原文件，新增 (\d+) 条记忆。点击「查看出处」核对原文。$/, 'Original saved; $1 new records. Choose View source to inspect.'],
    [/^已从原文重建 (\d+) 条检索索引，原文未改动。$/, 'Rebuilt $1 search entries. Originals are unchanged.'],
    [/^总消息 (\d+)$/, 'Total $1'],[/^可新增 (\d+)$/, 'New $1'],[/^重复 (\d+)$/, 'Duplicates $1'],[/^失败 (\d+)$/, 'Failed $1'],[/^含缺失提示 (\d+)$/, 'Warnings $1'],
    [/^导入预览 · (.+)$/, 'Import preview · $1'],
    [/^(.+) · 可看图$/, '$1 · Vision'],[/^(.+) · 文本常规模式$/, '$1 · Text'],
    [/^(.+) · 常规模式$/, '$1 · Standard'],
    [/^开始 (\d+) 分钟通话$/, 'Start $1-minute call'],
    [/^移除加粗：(.+)$/, 'Remove bold: $1'],[/^移除高亮：(.+)$/, 'Remove highlight: $1'],
    [/^所选加粗$/, 'Bold selection'],[/^整条加粗$/, 'Bold entire note'],[/^所选高亮$/, 'Highlight selection'],[/^整条高亮$/, 'Highlight entire note'],
    [/^本地已连接 · (.*)$/, (_,s)=>'Local connection · '+translate(s)],
    [/^云端已连接 · (.*)$/, (_,s)=>'Server connected · '+translate(s)],
    [/^用户 · (.*)$/, 'You · $1'],
    [/^(\d+) 条有效澄清 · 每轮优先带入$/, '$1 active corrections · Included in every turn'],
    [/^全量原文 · 字面匹配 · (\d+) 段 · 完整词句匹配，区分大小写$/, 'Archive · Literal search · $1 passages · Case-sensitive exact phrase matching'],
    [/^第 (\d+) 页$/, 'Page $1'],[/^(\d+) 页$/, '$1 pages'],[/^(\d+) 节$/, '$1 sections'],
    [/^v(\d+) · (\d+) 字 · 用户 · (.*)$/, 'v$1 · $2 characters · You · $3'],
    [/^开始前记录预留 ¥([\d.]+)，之后按回执校正；不是固定收费，也不是本月金额上限。$/, 'Record a CNY $1 estimate before starting, then reconcile reported usage. This is not a flat fee or monthly cap.'],
    [/^本月搜索已计入 (.+)；金额拦截已关闭，仍按次记录费用。$/, 'Search this month: $1. Spending caps are off; each request is still logged.'],
    [/^缓存观察 · (.+) 最近 (\d+) 次请求尚未返回可用缓存数据，不能确认命中率。不会为测试缓存额外发送模型请求。$/, 'Cache report · $1: no usable cache data in the last $2 requests. Hit rate is unknown. No additional requests are sent to test caching.'],
    [/^费用观察模式 · 金额拦截已关闭。本月本应用累计计入 (.+)。付费调用(已开启|已关闭)。 以上均为人民币。本地用量估算 (.+)，待核对请求预留 (.+)；按当前汇率 1 美元 = ([\d.]+) 元，总计折合约 \$(.+)。这不是 Google 账户余额；其他应用及密钥的花费不在这里。$/, (_,total,on,estimated,pending,fx,usd)=>`Usage tracking · Spending caps off. This app this month: ${total}. Paid requests ${on==='已开启'?'enabled':'disabled'}. Amounts above are CNY: estimated usage ${estimated}, unreconciled reservations ${pending}. At 1 USD = ${fx} CNY, about $${usd} total. This is not your Google account balance; usage from other apps and keys is excluded.`],
    [/^原文件 SHA-256：(.+) · (\d+) 字节 · 分支：(.*)$/, (_,hash,bytes,branches)=>`Original SHA-256: ${hash} · ${bytes} bytes · Branches: ${branches==='未知'?'unknown':branches}`],
    [/^(.+) · 对话 (.+) · 分支 (.+) · (.+)$/, (_,src,conv,branch,time)=>`${src} · Conversation ${conv} · Branch ${branch==='未知'?'unknown':branch} · ${translate(time)}`],
    [/^第 (\d+) 条 · 消息 (.+) · (.+)$/, 'Record $1 · Message $2 · $3'],
    [/^一次须包含 1–(\d+) 条消息。$/, 'Import between 1 and $1 messages at a time.'],
    [/^(\w+) 必须为非空字符串。$/, '$1 must be a nonempty string.'],
    [/^(\w+) 须为非空字符串或 null。$/, '$1 must be a nonempty string or null.'],
    [/^(\w+) 不是有效 ISO 日期或时间。$/, '$1 must contain a valid ISO date or timestamp.'],
    [/^每轮持续带入关系与表达依据。新聊天已有 (\d+) 条自动加入检索。按相关度和文字预算带入原文，段数不固定；普通聊天最多 (\d+) 轮工具补查，之后整理回答；尚不能保证每次召回完整，没找到时会保留不确定。(.*)$/, (_,n,rounds,cap)=>`${n} chat records available for recall. Sources are selected by relevance and text allowance, with up to ${rounds} tool rounds before answering. Recall may be incomplete; missing evidence stays uncertain.${translate(cap)}`],
    [/^ Argon：每轮检索原文累计最多 ([\d,]+) 字符 \/ (\d+) 段，最多 (\d+) 次不同记忆补查；普通聊天最多 (\d+) 轮工具交互，达到额度会整理回答。完整档案、固定人格、澄清和近期聊天另行保留。$/, ' Argon: up to $1 retrieved characters / $2 passages, $3 distinct memory searches and $4 tool rounds. The source archive is preserved; persona, corrections and recent context are separate.'],
    [/^自动匹配完成：带入 (\d+) 段原文$/, 'Recall ready: $1 source passages'],
    [/^本轮已用时 (\d+) 秒$/, 'Elapsed: $1 seconds'],
    [/^(\d+) 条来源关联 · 本次导入 (.*)$/, '$1 source links · Imported $2'],
    [/^原文件位置：(.*)$/, 'Source location: $1'],[/^本次导入时间：(.*)$/, 'Imported at: $1'],
    [/^文件：(.+)（(\d+) 条来源关联）$/, 'File: $1 ($2 source links)'],
    [/^已撤销：原文件已移除，删除 (\d+) 条独有消息；剩余 (\d+) 条消息、(\d+) 条索引。外部源文件与备份不受影响。$/, 'Import removed with $1 exclusive messages; $2 messages and $3 search entries remain. External files and backups are unchanged.'],
  ];
  function translate(value){
    if(locale!=='en')return value;
    if(Object.hasOwn(strings,value))return strings[value];
    const trimmed=value.trim();if(Object.hasOwn(strings,trimmed))return value.replace(trimmed,strings[trimmed]);
    for(const [pattern,replacement] of patterns)if(pattern.test(value))return value.replace(pattern,replacement);
    return value;
  }
  function textNode(node){
    if(!node.parentElement||node.parentElement.closest(protectedContent))return;
    const saved=originals.get(node);
    const source=saved&&node.data===saved.rendered?saved.source:node.data;
    const rendered=translate(source);originals.set(node,{source,rendered});
    if(node.data!==rendered)node.data=rendered;
  }
  function walk(root){
    if(root.nodeType===Node.TEXT_NODE){textNode(root);return;}
    if(root.nodeType!==Node.ELEMENT_NODE&&root!==document)return;
    if(root.matches?.(protectedContent))return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
    while((node=walker.nextNode()))textNode(node);
    for(const el of [root,...root.querySelectorAll('[placeholder],[aria-label],[title]')]){
      if(!el.getAttribute||el.closest?.('[data-no-i18n],.bubble,.original,.study-note-text'))continue;
      let saved=attributes.get(el)||{};
      for(const name of ['placeholder','aria-label','title']){
        if(!el.hasAttribute(name))continue;
        const current=el.getAttribute(name),prior=saved[name];
        const source=prior&&current===prior.rendered?prior.source:current,rendered=translate(source);
        saved[name]={source,rendered};if(current!==rendered)el.setAttribute(name,rendered);
      }
      attributes.set(el,saved);
    }
  }
  const label=document.createElement('label');label.className='language-control';label.textContent='Language / 语言';
  const select=document.createElement('select');select.id='ui-language';select.setAttribute('aria-label','Language / 语言');
  for(const [id,name] of [['zh-CN','简体中文'],['en','English']]){const option=new Option(name,id);select.append(option);}select.value=locale;label.append(select);
  (document.querySelector('.sidebar-footer')||document.querySelector('header')).append(label);
  function apply(){document.documentElement.lang=locale;walk(document);for(const node of document.querySelectorAll('[data-locale]'))node.hidden=node.dataset.locale!==locale;document.dispatchEvent(new CustomEvent('stet-language',{detail:locale}));}
  select.addEventListener('change',()=>{locale=select.value;try{localStorage.setItem('stet-language',locale);}catch{}apply();});
  const help=document.createElement('a');help.href='/guide.html';help.textContent='使用指南';help.id='user-guide';
  (document.querySelector('.sidebar-footer')||document.querySelector('header')).append(help);
  strings['使用指南']='Getting started';
  window.StetUI={get locale(){return locale;},text:translate,refresh:()=>walk(document)};
  apply();
  // Observe only changed subtrees; do not rescan the conversation on each audio frame.
  new MutationObserver(records=>{
    for(const r of records){if(r.type==='characterData')textNode(r.target);else if(r.type==='attributes')walk(r.target);else for(const n of r.addedNodes)walk(n);}
  }).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','aria-label','title']});
})();

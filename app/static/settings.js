'use strict';
// Reuse the real controls and forms. Moving a control must preserve its form owner.
(() => {
  const root=document.getElementById('settings');
  const heading=root.querySelector('.heading');
  heading.querySelector('h2').textContent='设置';
  heading.querySelector('p').textContent='先连接模型，再按需要配置工具、记忆与费用。每个实例单独保存。';
  heading.querySelector('.eyebrow').textContent='YOUR WORKSPACE';
  const layout=document.createElement('div');layout.className='preferences-layout';
  const menu=document.createElement('div');menu.className='preferences-menu';menu.setAttribute('role','tablist');menu.setAttribute('aria-label','设置分类');
  const content=document.createElement('div');content.className='preferences-content';
  const groups=[['providers','模型与连接'],['generation','回答与记忆'],['profile','伙伴与偏好'],['tools','联网工具'],['usage','费用与预算']];
  const sections=new Map();
  for(const [id,title] of groups){
    const panel=document.createElement('div');panel.id='settings-'+id;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','settings-tab-'+id);panel.hidden=id!=='providers';
    const b=document.createElement('button');b.type='button';b.textContent=title;b.id='settings-tab-'+id;b.setAttribute('role','tab');b.setAttribute('aria-controls',panel.id);b.setAttribute('aria-selected',String(!panel.hidden));b.tabIndex=panel.hidden?-1:0;
    const select=()=>{for(const node of content.children)node.hidden=node!==panel;for(const node of menu.children){node.setAttribute('aria-selected',String(node===b));node.tabIndex=node===b?0:-1;}};
    b.addEventListener('click',select);menu.append(b);content.append(panel);sections.set(id,panel);
  }
  menu.addEventListener('keydown',e=>{if(!['ArrowDown','ArrowUp','ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;const buttons=[...menu.children],i=buttons.indexOf(document.activeElement);const n=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(['ArrowDown','ArrowRight'].includes(e.key)?1:-1)+buttons.length)%buttons.length;e.preventDefault();buttons[n].click();buttons[n].focus();});
  // Keep moved controls in the document so ID lookups and form ownership stay valid.
  layout.append(menu,content);root.append(layout);
  const move=(id,group)=>{const node=document.getElementById(id)?.closest('article');if(node)sections.get(group).append(node);};
  for(const id of ['keyform','deepseekform','checkconnection','checkcodex'])move(id,'providers');
  for(const id of ['profileform','relationship'])move(id,'profile');
  move('searchkeyform','tools');
  for(const id of ['budgetform','ledger','contextcosts'])move(id,'usage');
  const generation=document.createElement('article');generation.className='card';
  const title=document.createElement('h3');title.textContent='回答与记忆';generation.append(title);
  const fields=document.createElement('div');fields.className='fields';generation.append(fields);
  for(const id of ['memory_chars','thinking_level','max_output_tokens','temperature','auto_corrections']){
    const input=document.getElementById(id);input.setAttribute('form','budgetform');fields.append(input.closest('label'));
  }
  const save=document.createElement('button');save.type='submit';save.setAttribute('form','budgetform');save.className='primary';save.textContent='保存设置';generation.append(save);sections.get('generation').append(generation);
  // Payment consent belongs next to connection setup; it still submits the same configuration.
  const consent=document.getElementById('paid_enabled');consent.setAttribute('form','budgetform');
  const access=document.createElement('article');access.className='card';access.append(consent.closest('label'));
  const apply=document.createElement('button');apply.type='submit';apply.setAttribute('form','budgetform');apply.textContent='保存设置';access.append(apply);sections.get('providers').prepend(access);
  // No inherited personal spending target in a general-purpose product.
  document.getElementById('plus_rmb').closest('label').firstChild.textContent='订阅固定支出 · 元';
  document.getElementById('persist').closest('label').lastChild.textContent=' 加密保存到当前独立资料目录';
  root.querySelector('.settings-grid')?.remove();
  document.getElementById('budgetform').addEventListener('invalid',e=>{
    const panel=e.target.closest('[role=tabpanel]');if(panel)document.getElementById(panel.getAttribute('aria-labelledby')).click();
  },true);
})();

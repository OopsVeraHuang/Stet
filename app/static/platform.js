'use strict';
document.getElementById('contextcosts').addEventListener('click',async()=>{
  try {
    const rows=await api('context-costs');
    document.getElementById('contextcostreport').textContent=rows.length?JSON.stringify(rows,null,2):'尚无模型请求。浏览页面、导入、翻书和本地检索不会产生模型用量。';
  } catch(e) { notify(e.message); }
});
// Preserve the inherited form behavior and explicitly save the new consent field.
document.getElementById('auto_corrections').addEventListener('change',async e=>{
  try {await api('config',{auto_corrections:e.target.checked});}
  catch(error){notify(error.message);e.target.checked=!e.target.checked;}
});
api('status').then(s=>{document.getElementById('auto_corrections').checked=s.config.auto_corrections===true;}).catch(()=>{});
api('profile').then(p=>{
  for(const k of ['agent_name','user_name','preferences'])document.getElementById(k).value=p[k]||'';
  document.getElementById('relationship_setting').value=p.relationship||'';
  if(p.agent_name)document.querySelector('header h1').textContent=p.agent_name;
}).catch(()=>{});
document.getElementById('profileform').addEventListener('submit',async e=>{
  e.preventDefault();
  try {
    const p=Object.fromEntries(['agent_name','user_name','preferences'].map(k=>[k,document.getElementById(k).value]));
    p.relationship=document.getElementById('relationship_setting').value;
    await api('profile',p);document.querySelector('header h1').textContent=p.agent_name||'Continuity';
    document.getElementById('profileguide').textContent='';notify('已保存，仅影响这个独立实例。');
  } catch(error){notify(error.message);}
});

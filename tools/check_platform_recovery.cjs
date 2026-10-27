/* Fault/recovery checks use a synthetic local profile and intercepted local errors only. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),profile=fs.mkdtempSync(path.join(os.tmpdir(),'continuity-recovery-'));
const output=path.join(root,'.local/platform-recovery');fs.mkdirSync(output,{recursive:true});
const server=spawn(process.env.CONTINUITY_PYTHON||'python',['-u','tools/browser_fixture.py','--port','0','--data-dir',profile],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser;const failures=[];
async function check(name,fn){try{await fn();console.log('PASS: '+name);}catch(e){failures.push(name+': '+e.message);console.error('FAIL: '+name+': '+e.message);}}
(async()=>{
 const url=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('startup timeout')),20000);server.stdout.on('data',d=>{const m=d.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0]);}});server.on('error',reject);server.stderr.on('data',d=>console.error(d.toString()));});
 browser=await chromium.launch(process.env.CONTINUITY_CHROMIUM?{executablePath:process.env.CONTINUITY_CHROMIUM,headless:true}:{channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>{if(!r.request().url().startsWith(url+'/')){external.push(r.request().url());return r.abort();}return r.continue();});
 async function home(){await page.goto(url);await page.locator('#chat-message-2').waitFor();}
 async function openPDF(){await page.locator('[data-tab="reader"]').click();await page.locator('.book-card').filter({hasText:'Synthetic paper.pdf'}).getByRole('button').click();await page.waitForFunction(()=>document.querySelector('#booktext').textContent.includes('Synthetic PDF'));}
 await check('unsent text survives import navigation and reload',async()=>{
  await home();await page.locator('#prompt').fill('尚未发送的虚构草稿');
  await page.getByRole('link',{name:'导入历史记录'}).click();await page.getByRole('link',{name:'回到对话'}).click();
  await page.locator('#chat-message-2').waitFor();assert.equal(await page.locator('#prompt').inputValue(),'尚未发送的虚构草稿');
  await page.reload();await page.locator('#chat-message-2').waitFor();assert.equal(await page.locator('#prompt').inputValue(),'尚未发送的虚构草稿');
 });
 await check('a pending submission cannot send twice; rejection retains draft',async()=>{
  await home();let requests=0;
  await page.route('**/api/job/chat',async r=>{requests++;await new Promise(resolve=>setTimeout(resolve,350));await r.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'合成拒绝：未配置模型。'})});});
  try{
   await page.locator('#prompt').fill('这段不应丢失');
   await page.locator('#send').evaluate(b=>{b.click();b.click();});
   await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('合成拒绝'));
   assert.equal(requests,1);assert.equal(await page.locator('#prompt').inputValue(),'这段不应丢失');assert.equal(await page.locator('#send').isDisabled(),false);
  }finally{await page.unroute('**/api/job/chat');}
 });
 await check('accepted submission clears only its own text, preserving new typing',async()=>{
  await home();
  await page.route('**/api/job/chat',async r=>{await new Promise(resolve=>setTimeout(resolve,250));await r.fulfill({contentType:'application/json',body:JSON.stringify({id:'synthetic-accepted',event:'合成提交，无模型调用'})});});
  await page.route('**/api/job?*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({status:'error',kind:'chat',event:'合成结束，无模型回复',error:'合成结束，无模型回复'})}));
  try{
   await page.locator('#prompt').fill('已提交的虚构文字');await page.locator('#send').click();
   await page.waitForFunction(()=>document.querySelector('#prompt').value==='');
   await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('合成结束'));
   await page.reload();await page.locator('#chat-message-2').waitFor();assert.equal(await page.locator('#prompt').inputValue(),'');
   await page.locator('#prompt').fill('第一条虚构文字');await page.locator('#send').click();
   await page.locator('#prompt').fill('等待提交时新写的第二条');
   await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('合成结束'));
   assert.equal(await page.locator('#prompt').inputValue(),'等待提交时新写的第二条');
   await page.reload();await page.locator('#chat-message-2').waitFor();assert.equal(await page.locator('#prompt').inputValue(),'等待提交时新写的第二条');
  }finally{await page.unroute('**/api/job/chat');await page.unroute('**/api/job?*');}
 });
 await check('reader text failure clears stale context and offers retry',async()=>{
  await home();await openPDF();
  await page.route('**/api/books/read?*',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'合成读取故障'})}));
  try{await page.locator('#bookgo').click();await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('合成读取故障'));}
  finally{await page.unroute('**/api/books/read?*');}
  assert.match(await page.locator('#booktext').textContent(),/未加载|失败/);
  await page.locator('[data-tab="chat"]').click();await page.locator('[data-tab="reader"]').click();
  assert.equal(await page.locator('#readingcontext').innerText(),'');
  await page.locator('.book-pane details>summary').first().click();
  await page.getByRole('button',{name:'重试读取原文',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#booktext').textContent.includes('Synthetic PDF'));
  assert.match(await page.locator('#readingcontext').innerText(),/PDF 第 1 页/);
  await page.screenshot({path:path.join(output,'reader-recovered.png')});
 });
 await check('attaching a document from shared reading returns to visible chat',async()=>{
  await home();await openPDF();
  await page.locator('#chat-message-1').getByRole('button',{name:'Synthetic attachment.md · v1',exact:true}).click();
  await page.locator('.library-dialog').getByRole('button',{name:'附到聊天',exact:true}).click();
  assert.equal(await page.locator('#prompt').isVisible(),true);
  assert.equal(await page.locator('#chat').evaluate(n=>n.parentElement.tagName),'MAIN');
  assert.match(await page.locator('#pendingdocs').innerText(),/Synthetic attachment/);
 });
 await check('390px notes: collect, comment, trash, restore and return to original',async()=>{
  await home();await page.setViewportSize({width:390,height:844});await page.locator('#study-toggle').click();
  await page.locator('#study-close').click();await page.locator('#chat-message-2 .study-collect').click();
  await page.locator('.study-note').waitFor();assert.ok((await page.locator('.study-more').boundingBox()).height<=40);assert.ok(await page.locator('.study-more').evaluate(n=>n.scrollWidth<=n.clientWidth));assert.equal(await page.locator('main').evaluate(n=>n.inert),true);
  await page.getByRole('button',{name:'笔记操作',exact:true}).click();await page.getByRole('menuitem',{name:'添加评论',exact:true}).click();
  await page.getByRole('textbox',{name:'评论内容',exact:true}).fill('虚构评注：这不是用户确认的事实。');await page.getByRole('button',{name:'保存评论',exact:true}).click();
  await page.locator('.study-comment').waitFor();
  await page.getByRole('button',{name:'笔记操作',exact:true}).click();await page.getByRole('menuitem',{name:'移入回收站',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.study-note').length===0);
  await page.getByRole('button',{name:'回收站',exact:true}).click();await page.locator('.study-note').waitFor();
  await page.getByRole('button',{name:'恢复',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.study-note').length===0);
  await page.getByRole('button',{name:'我的摘录',exact:true}).click();await page.locator('.study-comment').waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,'narrow-note.png')});
  await page.getByRole('button',{name:'↗ 回到对话',exact:true}).click();
  assert.equal(await page.locator('main').evaluate(n=>n.inert),false);assert.equal(await page.locator('#prompt').isVisible(),true);
  await page.waitForFunction(()=>document.activeElement.id==='chat-message-2');
 });
 await check('normal launcher starts empty and rejects unconfigured generation',async()=>{
  const empty=spawn(process.env.CONTINUITY_PYTHON||'python',['-u','-m','continuity','--port','0','--data-dir',path.join(profile,'empty-instance')],{cwd:root,stdio:['ignore','pipe','pipe']});
  let blank;
  try{
   const cleanURL=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('empty startup timeout')),20000);empty.stdout.on('data',d=>{const m=d.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0]);}});empty.on('error',reject);});
   blank=await browser.newPage({viewport:{width:390,height:844}});
   blank.on('pageerror',e=>errors.push(e.message));
   await blank.route('**/*',r=>{if(!r.request().url().startsWith(cleanURL+'/')){external.push(r.request().url());return r.abort();}return r.continue();});
   await blank.goto(cleanURL);await blank.waitForFunction(()=>!document.querySelector('#connection').textContent.includes('正在连接'));
   assert.equal(await blank.locator('#messages .message').count(),0);assert.equal(await blank.locator('#prompt').inputValue(),'');
   await blank.locator('#prompt').fill('无密钥的虚构消息');await blank.locator('#send').click();
   await blank.waitForFunction(()=>document.querySelector('#notice').textContent.includes('付费调用尚未启用'));
   assert.equal(await blank.locator('#prompt').inputValue(),'无密钥的虚构消息');assert.equal(await blank.locator('#messages .message').count(),0);
   const csrf=await blank.locator('meta[name="continuity-token"]').getAttribute('content');
   const status=await (await blank.request.get(cleanURL+'/api/status',{headers:{'X-Continuity-Token':csrf}})).json();
   assert.equal(status.config.paid_enabled,false);assert.equal(status.ledger.length,0);
   await blank.screenshot({path:path.join(output,'empty-no-key.png')});
  }finally{if(blank)await blank.close();empty.kill();await new Promise(r=>empty.exitCode!==null?r():empty.on('exit',r));}
 });
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 if(failures.length)throw Error(failures.join('\n'));
 console.log('No external requests, real generation, or device permissions.');
})().catch(e=>{console.error(e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.on('exit',r));fs.rmSync(profile,{recursive:true,force:true});});

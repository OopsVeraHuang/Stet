'use strict';
let pendingImages=[], imageUploadBusy=false;
const imageURLs=new Map();
let imageDialog, imageView, imageTitle, imageHint, imageOpenVersion=0;
async function openImage(item){
  const version=++imageOpenVersion;
  imageTitle.textContent=item.name;imageView.removeAttribute('src');imageView.alt=item.name;
  imageHint.textContent='正在读取本机原图…';
  if(!imageDialog.open)imageDialog.showModal();
  try{const url=await imageURL(item.id,true);if(version!==imageOpenVersion||!imageDialog.open)return;
    imageView.src=url;imageHint.textContent='本机原图 · 查看不调用模型，也不产生费用';
  }catch(e){if(version===imageOpenVersion)imageHint.textContent=e.message;}
}
function hasDraft(){return !!$('prompt').value.trim()||pendingImages.length>0||pendingDocs.length>0;}
function renderBrains(){
  const select=$('brainselect');select.replaceChildren();
  for(const [provider,label] of [['google','Gemini 家族'],['deepseek','DeepSeek 家族'],['codex','GPT · Codex 订阅']]){
    const group=el('optgroup');group.label=label;
    for(const [key,info] of Object.entries(state.brains).filter(([k,v])=>v.provider===provider)){
      const option=el('option',info.label+(info.vision?' · 可看图':''));option.value=key;group.append(option);
    }select.append(group);
  }select.value=state.config.brain;
  const info=state.brains[state.config.brain];
  $('brainhint').textContent=info.provider==='codex'?'GPT：共用 Codex 订阅额度；本版为文字分析与记忆入口，可读写资料库文字副本，尚不能执行程序。':info.provider==='deepseek'?'DeepSeek：常规文本模式，人民币计费；记忆和联网工具照常使用。':`Gemini：可看图片；输入 $${info.input_per_million}、输出（含思考）$${info.output_per_million}／百万 token，按设置汇率计入人民币预算。${info.price_note||''}`;
}
async function imageURL(id,original=false){
  const key=id+(original?':original':'');
  if(!imageURLs.has(key))imageURLs.set(key,(async()=>{
    const r=await fetch('/api/image?id='+encodeURIComponent(id)+(original?'&original=1':''),{headers:{'X-Continuity-Token':token}});
    if(!r.ok)throw Error('图片读取未完成。');return URL.createObjectURL(await r.blob());
  })().catch(e=>{imageURLs.delete(key);throw e;}));
  return imageURLs.get(key);
}
function appendImages(node,images,removable=false){
  if(!images?.length)return;
  const group=el('div',undefined,'image-strip');
  for(const item of images){
    const card=el('div',undefined,'image-card'),img=el('img');img.alt=item.name;img.loading='lazy';
    imageURL(item.id).then(url=>img.src=url).catch(e=>{img.alt='图片暂时无法读取';});
    const zoom=button('',()=>openImage(item),'image-zoom');zoom.setAttribute('aria-label','放大图片：'+item.name);zoom.append(img);
    card.append(zoom,el('small',item.name));
    if(removable)card.append(button('移除',()=>{pendingImages=pendingImages.filter(p=>p.id!==item.id);renderPendingImages();}));
    else card.append(button('保存原图',async()=>{const a=el('a');a.href=await imageURL(item.id,true);a.download=item.name;a.click();},'quiet'));
    group.append(card);
  }node.append(group);
}
function renderPendingImages(){
  $('pendingimages').replaceChildren();appendImages($('pendingimages'),pendingImages,true);invalidateQuote();
}
async function uploadFiles(files){
  if(imageUploadBusy||activeJob)return;
  if(pendingImages.length+files.length>2)throw Error('每次最多两张图片。');
  imageUploadBusy=true;invalidateQuote();
  try{for(const file of files){
    if(file.size>8*1024*1024)throw Error('单张图片最多 8 MB。');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('文件读取失败'));reader.readAsDataURL(file);});
    const item=await api('attachment',{name:file.name,data});
    if(!pendingImages.some(p=>p.id===item.id))pendingImages.push(item);
  }notify('图片已保存在本机；点击发送后才会交给模型。');}
  finally{imageUploadBusy=false;renderPendingImages();$('imagefile').value='';}
}
function initMedia(){
  const picker=el('dialog',undefined,'attachment-picker');picker.setAttribute('aria-labelledby','attachment-picker-title');
  const pickerHead=el('div',undefined,'heading'),pickerTitle=el('h3','添加附件');pickerTitle.id='attachment-picker-title';
  pickerHead.append(pickerTitle,button('关闭',()=>picker.close()));picker.append(pickerHead);
  const imageChoice=$('chooseimage'),documentChoice=$('choosedocument');
  const attachmentButton=button('＋',()=>picker.showModal(),'attachment-add');attachmentButton.id='chooseattachment';attachmentButton.setAttribute('aria-label','添加附件');attachmentButton.setAttribute('aria-haspopup','dialog');
  imageChoice.replaceWith(attachmentButton);imageChoice.textContent='图片';documentChoice.textContent='文档 · PDF / Word / TXT / MD';
  const pickerChoices=el('div',undefined,'attachment-choices');pickerChoices.append(imageChoice,documentChoice);picker.append(pickerChoices);document.body.append(picker);
  for(const choice of [imageChoice,documentChoice])choice.addEventListener('click',()=>picker.close());
  picker.addEventListener('click',e=>{if(e.target===picker){const r=picker.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)picker.close();}});
  $('codexresult').textContent='使用运行 Agent 的设备上的独立 Codex 登录；云端登录后，电脑关机也能使用 GPT。与桌面 Codex 共用订阅及已购买的额外额度，不需要 API key。';
  $('checkcodex').onclick=async()=>{const b=$('checkcodex');b.disabled=true;try{const r=await api('codex/check',{});const limits=r.rate_limits?.rateLimitsByLimitId?.codex||r.rate_limits?.rateLimits;const windows=[limits?.primary,limits?.secondary].filter(w=>typeof w?.usedPercent==='number').map(w=>`${w.windowDurationMins===300?'5 小时':w.windowDurationMins===10080?'每周':w.windowDurationMins+' 分钟'}剩余 ${Math.max(0,100-w.usedPercent)}%`);$('codexresult').textContent=(r.runtime==='cloud'?'云端':'本机')+' ChatGPT 订阅登录有效 · 可用：'+r.models.map(m=>m.name).join('、')+'。'+windows.join(' · ')+'。本次只检查连接，未生成回复；额度由整个账号共享。';}catch(e){$('codexresult').textContent=e.message;}finally{b.disabled=false;}};
  imageDialog=el('dialog',undefined,'image-viewer');imageDialog.setAttribute('aria-labelledby','image-viewer-title');
  const heading=el('div',undefined,'heading');imageTitle=el('h3');imageTitle.id='image-viewer-title';
  heading.append(imageTitle,button('关闭图片',()=>imageDialog.close()));
  imageView=el('img');imageHint=el('p',undefined,'footnote');imageDialog.append(heading,imageView,imageHint);document.body.append(imageDialog);
  imageDialog.addEventListener('close',()=>{imageOpenVersion++;imageView.removeAttribute('src');});
  imageDialog.addEventListener('click',e=>{if(e.target!==imageDialog)return;const r=imageDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)imageDialog.close();});
  $('chooseimage').onclick=()=>$('imagefile').click();
  $('imagefile').onchange=()=>uploadFiles([...$('imagefile').files]).catch(e=>notify(e.message));
  $('prompt').addEventListener('paste',e=>{const files=[...e.clipboardData.items].filter(i=>i.kind==='file'&&i.type.startsWith('image/')).map(i=>i.getAsFile());if(files.length){e.preventDefault();uploadFiles(files).catch(e=>notify(e.message));}});
  $('deepseekform').onsubmit=async e=>{e.preventDefault();try{await api('deepseek/key',{key:$('deepseekkey').value,persist:$('deepseekpersist').checked});$('deepseekkey').value='';await refresh();notify('DeepSeek 密钥已保存，尚未发起模型请求。');}catch(e){notify(e.message);}};
  $('cleardeepseek').onclick=async()=>{try{await api('deepseek/key/clear',{});await refresh();notify('DeepSeek 密钥已移除。');}catch(e){notify(e.message);}};
  $('brainselect').onchange=async()=>{try{const cfg=(await api('status')).config;await api('config',{...cfg,brain:$('brainselect').value});await refresh();fillSettings();invalidateQuote();notify('模型已切换，记忆和聊天继续保留；已开始的一轮不会中途换模型。');}catch(e){notify(e.message);}};
}

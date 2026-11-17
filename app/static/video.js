'use strict';
(() => {
  const panel=el('section',undefined,'panel');panel.id='video';
  // Static application markup only. Captions and errors always use textContent.
  panel.innerHTML=`<div class="heading"><div><span class="eyebrow">HERE, WITH YOU</span><h2>看见你，听见你。</h2><p>视频通话 · Beta</p></div></div>
  <p class="video-intro">一起看、听、说。按住按钮说话，松开后 Agent 回答；再次按住可打断。这一版还不会主动监督学习。</p>
  <div class="video-grid"><div class="video-camera"><video id="livecamera" muted playsinline autoplay></video><p id="livetracks">摄像头和麦克风均未开启</p></div>
  <div class="video-controls"><label>这次一起做什么？<input id="livetask" maxlength="300" placeholder="例如：一起看看我的书桌"></label>
  <label>模型自带声音<select id="livevoice"><option value="Puck">Puck</option></select></label><p class="footnote">这是模型自带声音，没有附带任何个人声音素材；换声音不换记忆。中文按普通话交流，实际音色可以逐一试听。</p>
  <label>这次聊多久<select id="liveduration"><option value="300">5 分钟</option><option value="60">1 分钟</option></select></label>
  <button id="livepreview">本地预览摄像头与麦克风</button><p class="footnote">预览不上传、不调用模型，不产生 API 费用。</p>
  <button id="livebegin" class="primary" disabled>开始 5 分钟通话</button><p id="liveprice" class="footnote">正在读取费用设置…</p>
  <button id="livetalk" disabled>按住说话 · 松开发送</button><button id="liveend" class="quiet" disabled>结束并关闭摄像头</button>
  <p id="livestatus" role="status" aria-live="polite">尚未开始</p><span id="livetimer"></span></div></div>
  <div id="livecaptions" aria-label="通话字幕"></div>
  <details><summary>这一版的范围与隐私</summary><p>Gemini 3.1 Flash Live · 默认自然声音。共用 Agent 的关系背景、有效澄清和原文检索；普通话、中英混说可试。通话中暂不联网或修改文件。</p>
  <p>本地摄像头持续预览，每秒上传最新画面。此阶段只在你松开说话按钮后生成回复；自动观察、轻声提醒与一两小时的长通话还未开放。可选 1 分钟或 5 分钟，最多分别六轮、三十轮，不会自动续接。</p>
  <p>保持此页在前台；切换到其他应用、锁屏或离开视频页会结束通话。当前不支持锁屏通话或共享其他 App 的画面。</p>
  <p>原始声音和画面只经过浏览器、你的服务器和 Google，不在本应用的文件、日志或备份中保存。完整确认的语音文字进入聊天与记忆；未确认播放的回答单独标记，不冒充已说完。转写可能有误。</p>
  <p>Google 的付费 API 内容不用于改进产品，但会为滥用监测有限期保留。这里没有承诺第三方零留存。<a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">查看 Google 数据条款</a></p>
  <p>试通额度是保守预留，不是固定收费；用量回执完整后校正，不完整时保留待核对。美元单价按设置汇率换成人民币，金额拦截按「连接与预算」中的开关执行。</p></details>`;
  document.querySelector('main').append(panel);
  const nav=button('◉  视频 · Beta',()=>tab('video'));nav.dataset.tab='video';document.querySelector('nav').append(nav);
  let stream=null,ctx=null,mic=null,mute=null,ws=null,ready=false,holding=false,discard=false,ending=false,starting=false;
  let captureTimer=null,countTimer=null,wake=null,startedAt=0,generation='',nextTime=0,ended=false,ackSent=false;
  let playbackGain=null,bufferTarget=.18,callSeconds=300,reservePerMinute=0;
  let stats={packets:0,underruns:0,max_gap_ms:0,max_buffer_ms:0,dropped_frames:0};
  const playing=new Set(),captionNodes=new Map();let operation=0;
  const status=text=>$('livestatus').textContent=text;
  const send=value=>{if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify(value));};
  function trackStatus(){const v=stream?.getVideoTracks()[0],a=stream?.getAudioTracks()[0];$('livetracks').textContent=`摄像头：${v?.readyState==='live'&&!v.muted?'已开启':'未开启或已暂停'} · 麦克风：${a?.readyState==='live'&&!a.muted?'已开启':'未开启或已暂停'}`;}
  function cancelAudio(){for(const node of playing){node.onended=null;try{node.stop();}catch{}node.disconnect();}playing.clear();nextTime=0;ended=false;ackSent=false;}
  function reportPlayback(){send({type:'playback_stats',...stats});}
  function acknowledge(){if(ended&&!playing.size&&!ackSent&&generation){ackSent=true;const [epoch,turn_id]=generation.split(':').map(Number);reportPlayback();send({type:'played',epoch,turn_id});}}
  function audio(data){
    if(discard||!ctx||ctx.state!=='running')return;
    const key=`${data.epoch}:${data.turn_id}`;
    if(key!==generation)return; // Only listening may establish a turn; late audio cannot rewind it.
    const bytes=Uint8Array.from(atob(data.data),c=>c.charCodeAt(0)),view=new DataView(bytes.buffer);
    const buffer=ctx.createBuffer(1,bytes.length/2,24000),samples=buffer.getChannelData(0);
    for(let i=0;i<samples.length;i++)samples[i]=view.getInt16(i*2,true)/32768;
    const now=ctx.currentTime,gap=nextTime?Math.max(0,now-nextTime):0;
    if(gap>0){stats.underruns++;stats.max_gap_ms=Math.max(stats.max_gap_ms,Math.round(gap*1000));bufferTarget=Math.min(.32,bufferTarget+.04);}
    // Buffer once at onset/recovery. Reapplying 180 ms to every packet inserts audible gaps.
    const restarting=!nextTime||nextTime<=now;
    if(restarting)nextTime=now+bufferTarget;
    if(nextTime-now>20){shutdown('声音播放积压过长，已停止通话。');return;}
    const node=ctx.createBufferSource();node.buffer=buffer;node.connect(playbackGain);
    const gain=playbackGain.gain;gain.cancelScheduledValues(now);
    gain.setValueAtTime(restarting?0:gain.value,now);
    gain.linearRampToValueAtTime(1,restarting?nextTime+.02:now+.02);
    const tail=nextTime+buffer.duration;
    gain.setValueAtTime(1,Math.max(nextTime+.02,tail-.02));gain.linearRampToValueAtTime(0,Math.max(nextTime+.021,tail));
    stats.packets++;stats.max_buffer_ms=Math.max(stats.max_buffer_ms,Math.round((tail-now)*1000));playing.add(node);
    node.onended=()=>{playing.delete(node);node.disconnect();acknowledge();};node.start(nextTime);nextTime+=buffer.duration;
    status('Agent 正在说话 · 按住可打断');
  }
  function caption(data){if(`${data.epoch}:${data.turn_id}`!==generation)return;const key=`${data.epoch}:${data.turn_id}:${data.role}`;let n=captionNodes.get(key);if(!n){n=el('p');captionNodes.set(key,n);$('livecaptions').append(n);}n.textContent=(data.role==='user'?'用户：':'Agent：')+data.text;}
  async function shutdown(message='已结束，摄像头与麦克风已关闭。'){
    operation++;if(ending)return;ending=true;ready=false;holding=false;discard=true;
    clearInterval(captureTimer);clearInterval(countTimer);captureTimer=null;countTimer=null;
    reportPlayback();send({type:'end'});if(ws){ws.onclose=null;ws.close();ws=null;}
    cancelAudio();mic?.disconnect();mute?.disconnect();playbackGain?.disconnect();mic=null;mute=null;playbackGain=null;
    stream?.getTracks().forEach(t=>t.stop());stream=null;$('livecamera').srcObject=null;
    if(ctx){const old=ctx;ctx=null;try{await old.close();}catch{}}
    try{await wake?.release();}catch{}wake=null;
    $('livebegin').disabled=true;$('livetalk').disabled=true;$('liveend').disabled=true;$('livepreview').disabled=false;$('livevoice').disabled=false;$('liveduration').disabled=false;
    $('livetalk').classList.remove('held');trackStatus();status(message);ending=false;starting=false;
  }
  async function preview(){
    if(starting||stream)return;
    $('livepreview').disabled=true;const op=++operation;
    try{
      const obtained=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},frameRate:{ideal:15,max:20},facingMode:'user'},audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:false,channelCount:1}});
      if(op!==operation||document.hidden){obtained.getTracks().forEach(t=>t.stop());return;}stream=obtained;
      $('livecamera').srcObject=stream;await $('livecamera').play();if(op!==operation)return;
      for(const t of stream.getTracks()){t.addEventListener('ended',()=>shutdown('媒体设备已断开，通话已停止。'));t.addEventListener('mute',trackStatus);t.addEventListener('unmute',trackStatus);}
      $('livebegin').disabled=false;$('liveend').disabled=false;trackStatus();status('本地预览中，尚未上传。');
    }catch{await shutdown('无法开启摄像头或麦克风；请检查浏览器权限和设备是否被其他应用占用。');}
  }
  function capture(){
    const video=$('livecamera');if(!ready||!video.videoWidth||!stream?.getVideoTracks().some(t=>t.readyState==='live'&&!t.muted))return;
    if(ws.bufferedAmount>150000){stats.dropped_frames++;return;} // Skip stale frames; watchdog stops prolonged loss.
    const canvas=document.createElement('canvas');canvas.width=480;canvas.height=Math.round(video.videoHeight/video.videoWidth*480);
    canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
    send({type:'video',data:canvas.toDataURL('image/jpeg',.65).split(',')[1]});canvas.width=canvas.height=0;
  }
  async function begin(){
    if(starting||ready||!stream)return;starting=true;const op=++operation;$('livebegin').disabled=true;$('livevoice').disabled=true;$('liveduration').disabled=true;status('正在准备共同记忆并建立通话…');
    try{
      ctx=new AudioContext();await ctx.resume();await ctx.audioWorklet.addModule('/video-worklet.js');if(op!==operation)return;
      playbackGain=ctx.createGain();playbackGain.connect(ctx.destination);bufferTarget=.18;
      stats={packets:0,underruns:0,max_gap_ms:0,max_buffer_ms:0,dropped_frames:0};
      captionNodes.clear();$('livecaptions').replaceChildren();
      const source=ctx.createMediaStreamSource(stream);mic=new AudioWorkletNode(ctx,'continuity-microphone');mute=ctx.createGain();mute.gain.value=0;source.connect(mic).connect(mute).connect(ctx.destination);
      mic.port.onmessage=e=>{if(!holding||!ready)return;if(ws.bufferedAmount>100000){shutdown('声音上传积压，通话已停止。');return;}const bytes=new Uint8Array(e.data);send({type:'audio',data:btoa(String.fromCharCode(...bytes))});};
      const grant=await api('video/ticket',{task:$('livetask').value,voice:$('livevoice').value,seconds:Number($('liveduration').value)||300,confirm:true});
      if(op!==operation)return;ws=new WebSocket(grant.ws_url || location.origin.replace(/^http/,'ws')+'/live/ws');
      ws.onopen=()=>send({ticket:grant.ticket});
      ws.onmessage=e=>{if(op!==operation)return;const data=JSON.parse(e.data);
        if(data.type==='ready'){ready=true;starting=false;discard=false;callSeconds=data.seconds||300;startedAt=Date.now();$('livetalk').disabled=false;capture();captureTimer=setInterval(capture,1000);countTimer=setInterval(()=>{$('livetimer').textContent=`剩余 ${Math.max(0,callSeconds-Math.floor((Date.now()-startedAt)/1000))} 秒`;if(Date.now()-startedAt>(callSeconds+5)*1000)shutdown('通话时间已到，已结束。');},500);status('共同记忆已带入 · 按住按钮和 Agent 说话');navigator.wakeLock?.request('screen').then(w=>{if(op===operation)wake=w;else w.release();}).catch(()=>{});}
        else if(data.type==='listening'){discard=false;generation=`${data.epoch}:${data.turn_id}`;ended=false;ackSent=false;status('正在听你说 · 松开后发送');}
        else if(data.type==='thinking')status('Agent 正在回应…');
        else if(data.type==='audio')audio(data);
        else if(data.type==='caption')caption(data);
        else if(data.type==='tool')status(data.name);
        else if(data.type==='complete'){if(`${data.epoch}:${data.turn_id}`!==generation)return;ended=true;acknowledge();}
        else if(data.type==='idle')status('按住继续说话');
        else if(data.type==='playback_timeout'){if(`${data.epoch}:${data.turn_id}`!==generation)return;cancelAudio();discard=true;status('未收到播放完成确认；这段回答保留为未确认，可以继续说话。');}
        else if(data.type==='usage')$('liveprice').textContent=`已收到用量回执，保守累计 ¥${data.upper_rmb.toFixed(4)}；最终状态见费用记录。`;
        else if(data.type==='ended')shutdown(data.message);
      };
      ws.onerror=()=>shutdown('视频连接未完成，请稍后检查网络与费用。');
      ws.onclose=()=>shutdown('连接已断开，摄像头和麦克风已关闭。不会自动重连。');
    }catch(e){await shutdown(e.message||'通话未能开始。');}
  }
  function startTalking(e){if(!ready||holding)return;e?.preventDefault();cancelAudio();discard=true;holding=true;$('livetalk').classList.add('held');if(e?.pointerId!==undefined)$('livetalk').setPointerCapture(e.pointerId);send({type:'start'});}
  function stopTalking(e){if(!holding)return;e?.preventDefault();holding=false;$('livetalk').classList.remove('held');send({type:'stop'});}
  $('livepreview').onclick=preview;$('livebegin').onclick=begin;$('liveend').onclick=()=>shutdown();
  $('livetalk').addEventListener('pointerdown',startTalking);for(const ev of ['pointerup','pointercancel','lostpointercapture'])$('livetalk').addEventListener(ev,stopTalking);
  $('livetalk').addEventListener('keydown',e=>{if([' ','Enter'].includes(e.key)&&!e.repeat)startTalking(e);});$('livetalk').addEventListener('keyup',e=>{if([' ','Enter'].includes(e.key))stopTalking(e);});
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&(stream||starting))shutdown('页面进入后台，试通已结束。');});
  document.addEventListener('continuity-tab',e=>{if(e.detail!=='video'&&(stream||starting))shutdown('已离开视频页，摄像头与麦克风已关闭。');});
  window.addEventListener('pagehide',()=>shutdown());
  function durationChanged(){const minutes=(Number($('liveduration').value)||300)/60;$('livebegin').textContent=`开始 ${minutes} 分钟通话`;$('liveprice').textContent=`开始前记录预留 ¥${(reservePerMinute*minutes).toFixed(2)}，之后按回执校正；不是固定收费，也不是本月金额上限。`;}
  $('liveduration').onchange=durationChanged;
  $('livevoice').onchange=()=>{try{localStorage.setItem('continuity-live-voice',$('livevoice').value);}catch{}};
  api('video/info').then(x=>{reservePerMinute=x.reserve_per_minute_rmb??x.reserve_rmb;durationChanged();$('livevoice').replaceChildren(...Object.entries(x.voices).map(([value,label])=>{const option=el('option',label);option.value=value;return option;}));let preferred='Puck';try{preferred=localStorage.getItem('continuity-live-voice')||preferred;}catch{}$('livevoice').value=x.voices[preferred]?preferred:Object.keys(x.voices)[0];}).catch(()=>status('暂时无法读取视频服务配置。'));
})();

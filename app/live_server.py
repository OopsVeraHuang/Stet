"""Isolated short-call relay. Media lives only in bounded memory, never logs/files."""
import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import urllib.parse
from types import SimpleNamespace
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
import server as api
import live_session as live
import remote_access

UPSTREAM = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent'


def setup(instruction, voice='Charon'):
    if voice not in live.VOICES: raise ValueError('Unknown voice')
    return {'setup': {'model': 'models/'+live.MODEL,
        'generationConfig': {'responseModalities': ['AUDIO'], 'temperature': 1,
            'maxOutputTokens': 512,
            'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}},
        'systemInstruction': {'parts': [{'text': instruction}]},
        'inputAudioTranscription': {}, 'outputAudioTranscription': {},
        'realtimeInputConfig': {'automaticActivityDetection': {'disabled': True}},
        'contextWindowCompression': {'triggerTokens': 24000, 'slidingWindow': {'targetTokens': 16000}},
        'tools': live.tools(api)}}


def decode(data, limit):
    if not isinstance(data, str) or len(data) > limit*1.4: raise ValueError('媒体包过大。')
    raw = base64.b64decode(data, validate=True)
    if not 0 < len(raw) <= limit: raise ValueError('媒体包无效。')
    return raw


class Call:
    def __init__(self, browser, session):
        self.browser, self.session = browser, session
        self.up = None
        self.done = asyncio.Event()
        self.started = time.monotonic()
        self.epoch = 0
        self.turn = 0
        self.active = False
        self.speaking = False
        self.generating = False
        self.blocked = False
        self.server_complete = False
        self.pending_played = False
        self.user_text = ''
        self.output_text = ''
        self.last_frame = 0
        self.frame_count = 0
        self.audio_bytes = 0
        self.tool_count = 0
        self.used = 0.
        self.reports = []
        self.connected = False
        self.reason = '通话已结束。'
        self.tool_task = None
        self.seconds = session.get('seconds', live.SECONDS)
        self.max_turns = max(6, self.seconds//10)
        self.playback_stats = {}
        self.acknowledged = False
        self.completed_at = None

    async def emit(self, kind, **data):
        await self.browser.send(json.dumps({'type': kind, 'epoch': self.epoch, 'turn_id': self.turn, **data}, ensure_ascii=False))

    async def send(self, value):
        await self.up.send(json.dumps(value, ensure_ascii=False))

    async def stop(self, reason):
        self.reason = reason
        self.done.set()

    async def save(self, role, text, status):
        await asyncio.to_thread(live.persist, api, self.session['id'], self.turn, role, text, status)

    async def played(self):
        if self.server_complete and self.pending_played and not self.acknowledged:
            self.acknowledged = True
            await self.save('assistant', self.output_text, 'played')
            self.output_text = ''
            self.speaking = False
            await self.emit('idle')

    async def browser_input(self):
        async for raw in self.browser:
            data = json.loads(raw)
            kind = data.get('type')
            if kind == 'playback_stats':
                # Numeric device diagnostics only; never raw media or dialogue.
                for key in ('packets', 'underruns', 'max_gap_ms', 'max_buffer_ms', 'dropped_frames'):
                    value = data.get(key)
                    if type(value) is int and 0 <= value <= 1000000: self.playback_stats[key] = value
                continue
            if kind == 'end':
                await self.stop('通话已结束。'); return
            if kind == 'video':
                at = time.monotonic()
                if at-self.last_frame < .85: continue
                image = decode(data.get('data'), 100000)
                if not image.startswith(b'\xff\xd8'): raise ValueError('需要 JPEG 画面。')
                self.last_frame = at; self.frame_count += 1
                if self.frame_count > self.seconds+4: raise ValueError('画面频率超过试通上限。')
                await self.send({'realtimeInput': {'video': {'data': data['data'], 'mimeType': 'image/jpeg'}}})
            elif kind == 'start':
                if self.active: continue
                if self.turn >= self.max_turns:
                    await self.stop('本次通话已达到回合上限，请重新开始。'); return
                if time.monotonic()-self.last_frame > 4: raise ValueError('没有新鲜画面，请重新开启摄像头。')
                if self.output_text: await self.save('assistant', self.output_text, 'interrupted')
                self.blocked = self.generating
                self.epoch += 1; self.turn += 1
                self.user_text = ''; self.output_text = ''
                self.active = True; self.speaking = False; self.generating = False
                self.server_complete = False; self.pending_played = False
                self.acknowledged = False; self.tool_count = 0
                self.completed_at = None
                if self.tool_task: self.tool_task.cancel()
                await self.emit('listening')
                await self.send({'realtimeInput': {'activityStart': {}}})
            elif kind == 'audio' and self.active:
                pcm = decode(data.get('data'), 3200)
                if len(pcm) % 2: raise ValueError('音频格式无效。')
                self.audio_bytes += len(pcm)
                if self.audio_bytes > 32000*(self.seconds+1): raise ValueError('音频超过试通上限。')
                await self.send({'realtimeInput': {'audio': {'data': data['data'], 'mimeType': 'audio/pcm;rate=16000'}}})
            elif kind == 'stop' and self.active:
                self.active = False; self.generating = True
                await self.send({'realtimeInput': {'activityEnd': {}}})
                await self.emit('thinking')
            elif kind == 'played' and data.get('epoch') == self.epoch and data.get('turn_id') == self.turn:
                self.pending_played = True
                await self.played()
            elif kind not in ('audio', 'stop', 'played'):
                raise ValueError('不支持的通话消息。')
        await self.stop('页面连接断开；通话已停止，不会后台续费。')

    async def execute_tools(self, calls, epoch, turn):
        replies = []
        for f in calls:
            if f.get('name') == 'search_memory': self.tool_count += 1
            if self.tool_count > 2 and f.get('name') == 'search_memory':
                result = {'error': '本轮补查已达到两次，下一轮重新可用。请坦诚说明未确认部分。'}
            else:
                result = await asyncio.to_thread(live.tool, api, f.get('name'), f.get('args', {}))
            replies.append({'id': f['id'], 'name': f['name'], 'response': result})
        if (epoch, turn) == (self.epoch, self.turn) and not self.active and not self.done.is_set():
            await self.send({'toolResponse': {'functionResponses': replies}})

    async def provider_output(self):
        async for raw in self.up:
            data = json.loads(raw)
            if 'usageMetadata' in data:
                u = data['usageMetadata']
                self.used += live.usage_upper(u)
                # Keep only numeric billing fields, never provider response payloads.
                self.reports.append({k: v for k, v in u.items() if isinstance(v, (int, float))})
                await self.emit('usage', upper_rmb=round(self.used*self.session['rate'], 4))
                if self.session.get('budget_enforced',True) and self.used >= .40*(self.seconds/60):
                    await self.stop('已达到短通话的费用保护线，先暂停核对。'); return
                if u.get('promptTokenCount', 0) > 31000 or len(self.reports) > self.max_turns*4:
                    await self.stop('已达到短通话的上下文或回合保护线，先暂停核对。'); return
            if 'goAway' in data:
                await self.stop('模型要求重建连接；短时版已结束，不会悄悄重连或重复收费。'); return
            if 'toolCall' in data:
                await self.emit('tool', name='正在检索原文或核对时间')
                if self.tool_task: self.tool_task.cancel()
                self.tool_task = asyncio.create_task(self.execute_tools(data['toolCall'].get('functionCalls', [])[:2], self.epoch, self.turn))
            content = data.get('serverContent', {})
            if content.get('interrupted'):
                self.blocked = False
                continue
            if self.blocked:
                if content.get('turnComplete'): self.blocked = False
                continue
            if t := content.get('inputTranscription', {}).get('text'):
                self.user_text += t
                await self.emit('caption', role='user', text=self.user_text)
            if self.active: continue  # Old audio cannot escape while 用户 has the floor.
            if t := content.get('outputTranscription', {}).get('text'):
                self.output_text += t
                await self.emit('caption', role='assistant', text=self.output_text)
            for part in content.get('modelTurn', {}).get('parts', []):
                blob = part.get('inlineData')
                if blob and blob.get('mimeType', '').startswith('audio/pcm'):
                    if self.turn == 0: continue
                    self.speaking = True
                    await self.emit('audio', data=blob['data'])
            if content.get('turnComplete'):
                self.generating = False
                self.server_complete = True
                self.completed_at = time.monotonic()
                await self.save('user', self.user_text, 'final')
                self.user_text = ''
                await self.emit('complete')
                if not self.speaking:
                    # Silence is a valid end; it must not wait for a playback acknowledgement.
                    self.output_text = ''
                    self.pending_played = True
                await self.played()
        await self.stop('模型连接已结束。')

    async def expire_playback(self, now):
        # Client queues at most 20 s. Allow another 8 s for its final receipt.
        if self.completed_at is not None and not self.acknowledged and now-self.completed_at > 28:
            await self.save('assistant', self.output_text, 'playback_unknown')
            self.output_text = ''; self.speaking = False; self.acknowledged = True
            self.playback_stats['ack_timeouts'] = self.playback_stats.get('ack_timeouts',0)+1
            await self.emit('playback_timeout')

    async def watchdog(self):
        while not self.done.is_set():
            await asyncio.sleep(.5)
            await self.expire_playback(time.monotonic())
            if time.monotonic()-self.started >= self.seconds:
                await self.stop(f'{self.seconds//60} 分钟通话结束；可以查看字幕和费用，再开始下一次。')
            elif self.connected and time.monotonic()-self.started > 8 and time.monotonic()-self.last_frame > 5:
                await self.stop('摄像头画面已暂停；通话已停止。请保持页面在前台。')
            elif self.tool_task and self.tool_task.done() and not self.tool_task.cancelled() and self.tool_task.exception():
                await self.stop('记忆工具未完成；通话已停止，文字聊天仍可使用。')

    async def run(self):
        tasks = []
        stage = 'context'
        diagnostic = None
        try:
            instruction = self.session.get('resident') or await asyncio.to_thread(live.resident, api, self.session['task'])
            stage = 'connection'
            key = await asyncio.to_thread(api.get_key)
            async with connect(UPSTREAM+'?key='+urllib.parse.quote(key, safe=''), open_timeout=15,
                               max_size=2000000, max_queue=4, logger=logging.getLogger('silent.live')) as upstream:
                self.up = upstream
                stage = 'setup'
                await self.send(setup(instruction, self.session.get('voice', 'Charon')))
                response = json.loads(await asyncio.wait_for(upstream.recv(), 15))
                if 'setupComplete' not in response: raise ValueError('模型没有确认通话配置。')
                self.connected = True; self.started = time.monotonic()
                stage = 'conversation'
                await self.emit('ready', seconds=self.seconds,
                                resident_sha256=hashlib.sha256(instruction.encode()).hexdigest())
                tasks = [asyncio.create_task(self.browser_input()), asyncio.create_task(self.provider_output()),
                         asyncio.create_task(self.watchdog()), asyncio.create_task(self.done.wait())]
                finished, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in finished:
                    if not task.cancelled() and task.exception(): raise task.exception()
        except Exception as error:
            # Store only machine-readable categories; never provider URLs, secrets or raw content.
            code = getattr(getattr(error, 'rcvd', None), 'code', None)
            diagnostic = {'stage': stage, 'error_class': type(error).__name__, 'close_code': code if isinstance(code,int) else None}
            if isinstance(error, live.ContextLimitError):
                self.reason = '短通话的关系背景容量不足，尚未连接模型，本次预留已释放；文字聊天可继续。'
            else:
                label={'context':'准备关系背景','connection':'连接语音模型','setup':'确认语音配置','conversation':'收发音视频'}[stage]
                self.reason = f'通话在「{label}」时未完成或中断（{type(error).__name__}）。没有自动重试；请查看费用记录。'
        finally:
            for task in tasks: task.cancel()
            if self.tool_task: self.tool_task.cancel()
            await asyncio.gather(*tasks, *([self.tool_task] if self.tool_task else []), return_exceptions=True)
            if self.output_text: await self.save('assistant', self.output_text, 'playback_unknown')
            clean = not self.active and not self.generating and not self.speaking
            diagnostic = {**(diagnostic or {}), 'playback': self.playback_stats,
                          'seconds_elapsed': round(time.monotonic()-self.started), 'turns': self.turn}
            await asyncio.to_thread(live.finish, api, self.session, self.used, self.reports, clean, self.connected, diagnostic)
            try: await self.emit('ended', message=self.reason)
            except Exception: pass


async def handler(ws):
    # Ticket requires authenticated CSRF-protected HTTP first; cookie is rechecked here.
    request = ws.request
    origin = remote_access.origin() or getattr(api,'LOCAL_ORIGIN','')
    if not origin or request.path != '/live/ws' or request.headers.get('Origin') != origin:
        await ws.close(1008, 'Origin denied'); return
    if remote_access.origin() and not remote_access.authenticated(api, SimpleNamespace(headers=request.headers)):
        await ws.close(1008, 'Login required'); return
    try:
        first = json.loads(await asyncio.wait_for(ws.recv(), 8))
        session = await asyncio.to_thread(live.claim, api, first.get('ticket'))
    except Exception:
        await ws.send(json.dumps({'type': 'ended', 'message': '无法开始通话：请检查余额、登录状态，或重新点击开始。'}, ensure_ascii=False))
        return
    await Call(ws, session).run()


async def main(port=0, ready=None):
    logging.getLogger('silent.live').addHandler(logging.NullHandler())
    logging.getLogger('silent.live').propagate = False
    async with serve(handler, '127.0.0.1', port, max_size=150000, max_queue=4,
                     ping_interval=15, ping_timeout=10, logger=logging.getLogger('silent.live')) as service:
        api.LIVE_WS_URL = (remote_access.origin().replace('https://','wss://')+'/live/ws') if remote_access.origin() else f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}/live/ws'
        if ready: ready.set()
        await asyncio.Future()


if __name__ == '__main__':
    raise SystemExit('Start the full application with python -m continuity; the relay shares its isolated profile.')

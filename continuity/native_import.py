"""Bounded adapters for exported text. Originals stay in Store, never rewritten.

No accounts, attachments, code execution, guessing from prose, or model calls.
JSON pointers identify the source record even when a graph path is expanded.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import zipfile

MAX_EXPANDED = 32 * 1024 * 1024
MAX_ROWS = 20000


def fail(message):
    from .importing import ImportProblem
    raise ImportProblem(message)


def unzip(raw):
    """Select exactly one known conversation file; never extract paths to disk."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if len(z.infolist()) > 20000:
                fail('ZIP has too many entries / ZIP 文件数过多。')
            candidates = [i for i in z.infolist() if i.filename.replace('\\', '/').rsplit('/', 1)[-1].lower()
                          in {'conversations.json', 'myactivity.json'} and not i.is_dir()]
            if len(candidates) != 1:
                fail('Choose one conversations.json or MyActivity.json from the ZIP / 请解压后选择一个对话 JSON。')
            item = candidates[0]
            if item.file_size > MAX_EXPANDED or item.flag_bits & 1:
                fail('Conversation JSON is too large or encrypted / 对话文件过大或已加密。')
            with z.open(item) as f:
                content = f.read(MAX_EXPANDED + 1)
            if len(content) > MAX_EXPANDED:
                fail('Expanded JSON exceeds 32 MiB / 解压后 JSON 超过 32 MiB。')
            return content, item.filename
    except (zipfile.BadZipFile, RuntimeError, OSError) as e:
        fail('Cannot read ZIP / 无法读取 ZIP: ' + str(e))


def stamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    return value if isinstance(value, str) and value.strip() else None


def adapt(data):
    """Return (rows, report) or None for the canonical importer."""
    rows, skipped = [], {}
    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1
    def add(provider, cid, mid, branch, role, text, at, pointer, extra=None):
        if not text or not text.strip():
            skip('non_text_or_empty'); return
        if len(rows) >= MAX_ROWS:
            fail('Export exceeds 20,000 expanded messages; split by conversation / 请按会话拆分。')
        recorded = stamp(at)
        record = dict(id=str(mid), source_id=provider, conversation_id=str(cid), branch_id=branch,
                      role=role if role in {'user','assistant','system','tool'} else 'unknown', text=text,
                      recorded_at=recorded, timezone='UTC' if recorded and recorded.endswith(('Z','+00:00')) else None,
                      time_precision='second' if recorded and 'T' in recorded else None)
        if extra: record['native_metadata'] = extra
        rows.append((record, {'json_pointer': pointer}))
    def text_blocks(content):
        if isinstance(content, str): return content
        if not isinstance(content, list): return ''
        parts=[]
        for b in content:
            if isinstance(b, str): parts.append(b)
            elif isinstance(b, dict) and b.get('type') in ('text','input_text','output_text') and isinstance(b.get('text'), str): parts.append(b['text'])
            else: skip('unsupported_content_block')
        return '\n'.join(parts)
    objects = data if isinstance(data, list) else [data]
    if not objects or not all(isinstance(o, dict) for o in objects): return None
    provider = None
    # ChatGPT exports contain a parent-linked graph, not a single flat conversation.
    if all(isinstance(o.get('mapping'), dict) for o in objects):
        provider='chatgpt'
        for ci,c in enumerate(objects):
            base=f'/{ci}' if isinstance(data,list) else ''
            mapping=c['mapping']; cid=c.get('id') or c.get('conversation_id')
            if not cid: fail('ChatGPT conversation ID is missing / 缺少会话 ID。')
            if not mapping or any(not isinstance(n,dict) for n in mapping.values()): fail('Invalid ChatGPT graph / 无效对话图。')
            parents={n.get('parent') for n in mapping.values() if n.get('parent') is not None}
            leaves=[k for k in mapping if k not in parents]
            if not leaves: fail('Cyclic ChatGPT graph / 对话图存在循环。')
            visited=set()
            for leaf in leaves:
                path=[];seen=set();key=leaf
                while key is not None:
                    if key in seen or key not in mapping: fail('Broken or cyclic ChatGPT branch / 分支断裂或存在循环。')
                    seen.add(key);visited.add(key);path.append(key);key=mapping[key].get('parent')
                for key in reversed(path):
                    m=mapping[key].get('message')
                    if m is None: continue
                    if not isinstance(m,dict): fail('Invalid ChatGPT message / 消息格式无效。')
                    content=m.get('content') or {}
                    if not isinstance(content,dict): fail('Invalid ChatGPT content / 正文格式无效。')
                    text=text_blocks(content.get('parts',[]))
                    pointer=base+'/mapping/'+key.replace('~','~0').replace('/','~1')+'/message'
                    add(provider,cid,m.get('id') or key,leaf,(m.get('author') or {}).get('role'),text,m.get('create_time'),pointer,
                        {'model_id':(m.get('metadata') or {}).get('model_slug'), 'title':c.get('title'),
                         'export_current_node':c.get('current_node')})
            if len(visited)!=len(mapping): fail('Disconnected cyclic graph / 存在未连接的循环分支。')
    elif all(isinstance(o.get('chat_messages'),list) for o in objects):
        provider='claude'
        for ci,c in enumerate(objects):
            cid=c.get('uuid') or c.get('id')
            if not cid: fail('Claude conversation ID is missing / 缺少会话 ID。')
            base=f'/{ci}' if isinstance(data,list) else ''
            for mi,m in enumerate(c['chat_messages']):
                if not isinstance(m,dict): fail('Invalid Claude message / 消息格式无效。')
                text=m.get('text') if isinstance(m.get('text'),str) and m['text'] else text_blocks(m.get('content'))
                if m.get('attachments') or m.get('files'): skip('attachments_not_imported')
                add(provider,cid,m.get('uuid') or m.get('id') or f'ordinal:{mi}',None,
                    {'human':'user','assistant':'assistant'}.get(m.get('sender'),'unknown'),text,m.get('created_at'),
                    base+f'/chat_messages/{mi}',{'title':c.get('name')})
    elif isinstance(data,dict) and isinstance(data.get('chunkedPrompt'),dict) and isinstance(data['chunkedPrompt'].get('chunks'),list):
        provider='gemini-ai-studio'
        # AI Studio sometimes has no stable ID. Content addressing is explicit, never merged by title.
        cid=data.get('id') or 'content:'+hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        for i,m in enumerate(data['chunkedPrompt']['chunks']):
            if not isinstance(m,dict): fail('Invalid AI Studio chunk / 消息格式无效。')
            add(provider,cid,m.get('id') or f'chunk:{i}',None,{'user':'user','model':'assistant'}.get(m.get('role'),'unknown'),
                m.get('text') if isinstance(m.get('text'),str) else '',None,f'/chunkedPrompt/chunks/{i}',{'model_id':data.get('model')})
    elif isinstance(data,list) and all(isinstance(o.get('title'),str) and 'time' in o and
            any('gemini' in str(p).lower() or str(p)=='Bard' for p in o.get('products',[])) for o in objects):
        provider='gemini-takeout'
        for i,m in enumerate(objects):
            # Activity exports may contain prompts only. Do not manufacture assistant answers or group unrelated activities.
            mid=hashlib.sha256(json.dumps(m,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            title=m['title'];role='user' if title.startswith(('Prompted ', 'Asked ', '提问：', '提示：')) else 'unknown'
            add(provider,mid,mid,None,role,title,m['time'],f'/{i}')
        skip('activity_export_may_lack_assistant_replies')
    else: return None
    return rows, {'adapter':provider,'adapter_version':1,'omissions':skipped,
                  'notice':'Text only. Review branches, unknown dates and omissions before import. / 仅导入文字，请检查分支、未知时间与遗漏。'}

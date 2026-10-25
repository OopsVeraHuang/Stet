"""Adapt the existing reviewed importer to the pilot's read-only recall interface.

Original bytes remain in Store. This SQLite archive is a derived compatibility view.
Each source/conversation/branch has its own sequence; neighbors never cross branches.
"""
from contextlib import closing
import base64
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from continuity.store import Store
from continuity.importing import strict_json, MAX_BYTES

def store(api):
    return Store(api.STATE / 'imports')

def rebuild(api):
    original = store(api)
    records = original.messages()
    with closing(sqlite3.connect(api.ARCHIVE)) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,filename TEXT,metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS paragraphs(id TEXT PRIMARY KEY,source_id TEXT,number INTEGER,
          speaker TEXT,kind TEXT,raw_text TEXT,timestamp_json TEXT,issues_json TEXT);
        CREATE TABLE IF NOT EXISTS cherished(paragraph_id TEXT,start INTEGER,end INTEGER);
        CREATE VIRTUAL TABLE IF NOT EXISTS paragraph_search USING fts5(paragraph_id UNINDEXED,raw_text,tokenize='trigram');
        CREATE TABLE IF NOT EXISTS gpt_nodes(id TEXT PRIMARY KEY,source_id TEXT,status TEXT,raw_text TEXT,role TEXT,sequence INTEGER,raw_json TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS gpt_aux_search USING fts5(node_uid UNINDEXED,raw_text,tokenize='trigram');
        CREATE TABLE IF NOT EXISTS public_profile(id INTEGER PRIMARY KEY,value TEXT);
        ''')
        # Only derived rows; untouched originals remain independently exportable.
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM paragraph_search'); db.execute('DELETE FROM paragraphs'); db.execute('DELETE FROM sources')
        counters = {}
        for item in records:
            r = item['record']; mid = item['key']
            group = json.dumps([r.get('source_id'), r.get('conversation_id'), r.get('branch_id')], ensure_ascii=False)
            sid = hashlib.sha256(group.encode()).hexdigest()
            detail = original.detail(mid); origins = detail['origins']
            filename = origins[0]['filename'] if origins else str(r.get('source_id') or '导入记录')
            filename += ' · ' + str(r.get('conversation_id') or '未知会话') + ' · ' + str(r.get('branch_id') or '未知分支')
            db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?)', (sid, filename, json.dumps({'category':'用户导入','provenance':group},ensure_ascii=False)))
            counters[sid] = counters.get(sid,0)+1
            timestamp = {'raw':r['recorded_at'], 'timezone':r.get('timezone')} if r.get('recorded_at') else None
            issues = ['记录时间未知'] if not timestamp else []
            db.execute('INSERT INTO paragraphs VALUES(?,?,?,?,?,?,?,?)',(mid,sid,counters[sid],
                {'user':'用户','assistant':'Agent'}.get(r.get('role'),r.get('role') or '未知'),
                'dialogue' if r.get('role') in ('user','assistant') else 'source_record',r['text'],
                json.dumps(timestamp,ensure_ascii=False),json.dumps(issues,ensure_ascii=False)))
            db.execute('INSERT INTO paragraph_search VALUES(?,?)',(mid,r['text']))
        db.commit()
    return {'indexed':len(records), 'source':'original-import-store'}

def handle_get(h, api):
    path=urlsplit(h.path).path
    q={k:v[0] for k,v in parse_qs(urlsplit(h.path).query).items()}
    root=api.ROOT
    if path in ('/import','/import/','/import/app.js','/import/style.css'):
        name='index.html' if path in ('/import','/import/') else path.rsplit('/',1)[-1]
        text=(root/'continuity/static'/name).read_text(encoding='utf-8')
        if name=='app.js':text=text.replace('/api/','/import/api/')
        if name=='index.html':
            text=text.replace('href="/style.css"','href="/import/style.css"').replace('src="/app.js"','src="/import/app.js"')
            text=text.replace('</header>','<a href="/">回到对话</a></header>')
        mime={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]
        return h.respond(200,text.encode(),mime+'; charset=utf-8')
    original=store(api); endpoint=path.removeprefix('/import')
    if endpoint=='/api/session':result={'token':api.TOKEN,'mode':'shared-import-store'}
    elif endpoint=='/api/messages':result={'messages':original.messages(q.get('q',''),q.get('source'),q.get('branch'))}
    elif endpoint.startswith('/api/messages/'):result=original.detail(endpoint.rsplit('/',1)[-1])
    elif endpoint=='/api/batches':result={'batches':original.batches()}
    elif endpoint.startswith('/api/original/'):
        return h.respond(200,original.original(endpoint.rsplit('/',1)[-1]),'application/octet-stream')
    elif endpoint in ('/api/examples/messages.json','/api/examples/messages.md'):
        return h.respond(200,(root/'examples'/endpoint.rsplit('/',1)[-1]).read_bytes(),'text/plain; charset=utf-8')
    else:return h.respond(404,{'error':'页面不存在'})
    return h.respond(200,result)

def handle_post(h, api):
    length=int(h.headers.get('Content-Length','0'))
    if not 0<length<=MAX_BYTES*2:raise ValueError('导入请求大小无效。')
    data=strict_json(h.rfile.read(length).decode())
    if not isinstance(data,dict):raise ValueError('请求必须是对象。')
    endpoint=urlsplit(h.path).path.removeprefix('/import')
    original=store(api)
    with api.LOCK:
        if any(j['status']=='running' for j in api.JOBS.values()):raise ValueError('请等当前回复完成后再修改导入资料。')
        if endpoint in ('/api/preview','/api/import'):
            filename=data.get('filename')
            if not isinstance(filename,str) or not filename or len(filename)>255:raise ValueError('文件名无效')
            filename=filename.replace('\\','/').rsplit('/',1)[-1]
            raw=base64.b64decode(data.get('data',''),validate=True)
            result=original.preview(raw,filename) if endpoint.endswith('preview') else original.import_file(raw,filename)
        elif endpoint=='/api/remove-batch':result=original.remove_batch(data.get('batch_id'))
        elif endpoint=='/api/rebuild':result=original.rebuild()
        else:raise ValueError('操作不存在')
        if endpoint!='/api/preview':
            rebuild(api)
            api.semantic_memory.request_update(api)
    return h.respond(200,result)

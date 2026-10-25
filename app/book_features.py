"""Durable annotations and resumable local book indexing. No model calls."""
import json,re,threading,uuid,time
INDEX_LOCK=threading.Lock()
WORKERS={}

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS book_index(book_id TEXT PRIMARY KEY,status TEXT,errors TEXT NOT NULL DEFAULT '{}',updated TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS book_search USING fts5(book_id UNINDEXED,unit UNINDEXED,text,tokenize='trigram');
    CREATE TRIGGER IF NOT EXISTS book_search_insert AFTER INSERT ON book_text BEGIN
      DELETE FROM book_search WHERE book_id=new.book_id AND unit=new.unit;
      INSERT INTO book_search VALUES(new.book_id,new.unit,new.text); END;
    CREATE TABLE IF NOT EXISTS book_notes(id TEXT PRIMARY KEY,book_id TEXT,unit INTEGER,kind TEXT,author TEXT,quote TEXT,
      anchor INTEGER,location TEXT,body TEXT,version INTEGER,deleted INTEGER DEFAULT 0,created TEXT,updated TEXT);
    CREATE TABLE IF NOT EXISTS book_note_versions(note_id TEXT,version INTEGER,snapshot TEXT,PRIMARY KEY(note_id,version));
    ''')
    db.execute("UPDATE book_index SET status='paused' WHERE status='running'")
    db.execute('INSERT INTO book_search SELECT book_id,unit,text FROM book_text t WHERE NOT EXISTS(SELECT 1 FROM book_search f WHERE f.book_id=t.book_id AND f.unit=t.unit)')

def index_status(api,bid):
    book=api.reader.record(api,bid)
    with api.state_db() as db:
        row=db.execute('SELECT * FROM book_index WHERE book_id=?',(bid,)).fetchone()
        count=db.execute('SELECT count(*) FROM book_text WHERE book_id=?',(bid,)).fetchone()[0]
        empty=db.execute("SELECT count(*) FROM book_text WHERE book_id=? AND trim(text)=''",(bid,)).fetchone()[0]
    return {'book_id':bid,'status':row['status'] if row else 'not_started','indexed':count,'total':book['units'],
            'empty_units':empty,'errors':json.loads(row['errors']) if row else {},'complete':count==book['units']}

def build_index(api,bid):
    # One parser across all books: keeps CPU/RAM bounded on a small server.
    with INDEX_LOCK:
        r=api.reader.record(api,bid)
        with api.state_db() as db:
            if db.execute('SELECT status FROM book_index WHERE book_id=?',(bid,)).fetchone()[0]=='paused':return
            db.execute("UPDATE book_index SET status='running',updated=? WHERE book_id=?",(api.now(),bid))
        errors={}
        try:
            if r['kind']=='pdf':
                from pypdf import PdfReader
                book=PdfReader(api.reader.path_for(api,r));spine=None
            else:
                book,spine=api.reader.epub_parts(api.reader.path_for(api,r,True).read_bytes())
            for unit in range(1,r['units']+1):
                with api.state_db() as db:
                    status=db.execute('SELECT status FROM book_index WHERE book_id=?',(bid,)).fetchone()[0]
                    exists=db.execute('SELECT 1 FROM book_text WHERE book_id=? AND unit=?',(bid,unit)).fetchone()
                if status=='paused':return
                if exists:continue
                try:
                    if spine is None:
                        page=book.pages[unit-1];stream=page.get_contents()
                        if stream and len(stream.get_data())>8*1024*1024:raise ValueError('页面过于复杂')
                        text=page.extract_text() or ''
                    else:
                        root=api.reader.ET.fromstring(book.read(spine[unit-1]))
                        body=next((e for e in root.iter() if e.tag.endswith('}body')),root);text=' '.join(body.itertext())
                    text=re.sub(r'[\t ]+',' ',text).strip()
                    if len(text)>500000:raise ValueError('章节过长')
                    with api.state_db() as db:db.execute('INSERT OR IGNORE INTO book_text VALUES(?,?,?,?)',(bid,unit,f'{r["kind"].upper()} {unit}',text))
                except Exception:errors[str(unit)]='未能提取；保留原件，可重试或换文字版。'
                with api.state_db() as db:db.execute('UPDATE book_index SET errors=?,updated=? WHERE book_id=?',(api.dump(errors),api.now(),bid))
                time.sleep(.015)
            with api.state_db() as db:db.execute('UPDATE book_index SET status=?,errors=?,updated=? WHERE book_id=?',('partial' if errors else 'done',api.dump(errors),api.now(),bid))
        except Exception:
            with api.state_db() as db:db.execute("UPDATE book_index SET status='error',errors=?,updated=? WHERE book_id=?",(api.dump({'file':'解析未完成，原件保留。'}),api.now(),bid))
        finally:
            if 'spine' in locals() and spine is not None:book.close()

def control_index(api,data):
    bid=data.get('id');api.reader.record(api,bid);action=data.get('action','start')
    if action not in ('start','pause'):raise ValueError('索引操作无效。')
    with api.LOCK:
        with api.state_db() as db:
            db.execute("INSERT OR IGNORE INTO book_index VALUES(?,'paused','{}',?)",(bid,api.now()))
            if action=='pause':db.execute("UPDATE book_index SET status='paused' WHERE book_id=?",(bid,))
        key=(str(api.STATE),bid)
        if action=='start' and not (WORKERS.get(key) and WORKERS[key].is_alive()):
            with api.state_db() as db:db.execute("UPDATE book_index SET status='queued' WHERE book_id=?",(bid,))
            worker=threading.Thread(target=build_index,args=(api,bid),daemon=True);WORKERS[key]=worker;worker.start()
    return index_status(api,bid)

def search(api,bid,query,max_unit=None):
    r=api.reader.record(api,bid)
    if not isinstance(query,str) or not 1<=len(query.strip())<=100:raise ValueError('搜索词应为 1–100 字。')
    query=query.strip();limit=r['units'] if max_unit is None else max_unit
    if type(limit) is not int or not 1<=limit<=r['units']:raise ValueError('检索范围无效。')
    with api.state_db() as db:
        if len(query)>=3:
            rows=db.execute('SELECT unit,text FROM book_search WHERE text MATCH ? AND book_id=? AND CAST(unit AS INTEGER)<=? ORDER BY bm25(book_search) LIMIT 30',('"'+query.replace('"','""')+'"',bid,limit)).fetchall()
        else:rows=db.execute('SELECT unit,text FROM book_text WHERE book_id=? AND unit<=? AND instr(lower(text),lower(?))>0 ORDER BY unit LIMIT 30',(bid,limit,query)).fetchall()
    hits=[]
    for row in rows:
        at=row['text'].lower().find(query.lower())
        if at>=0:hits.append({'unit':int(row['unit']),'offset':max(0,at-250),'excerpt':row['text'][max(0,at-250):at+750]})
    status=index_status(api,bid)
    return dict(status,hits=hits,scope=f'检索到第 {limit} 页/节，已提取 {status["indexed"]}/{status["total"]}；空白或扫描页尚未 OCR。无结果不代表未提取内容中没有。')

def notes(api,bid,unit=None,include_deleted=False):
    api.reader.record(api,bid)
    with api.state_db() as db:
        return [dict(r) for r in db.execute('SELECT * FROM book_notes WHERE book_id=?'+(' AND unit=?' if unit is not None else '')+('' if include_deleted else ' AND deleted=0')+' ORDER BY unit,created',(bid,unit) if unit is not None else (bid,))]

def save_note(api,data,author='用户'):
    bid=data.get('book_id');unit=data.get('unit');kind=data.get('kind','note');body=data.get('body','');quote=data.get('quote','');location=data.get('location','')
    if kind not in ('note','bookmark') or not isinstance(body,str) or len(body)>4000:raise ValueError('批注正文最多 4000 字。')
    if not isinstance(location,str) or len(location)>2000:raise ValueError('位置无效。')
    page=api.reader.context(api,{'id':bid,'unit':unit,'selection':quote})
    anchor=0
    if quote:
        with api.state_db() as db:full=db.execute('SELECT text FROM book_text WHERE book_id=? AND unit=?',(bid,unit)).fetchone()[0]
        compact=re.sub(r'\s','',full);needle=re.sub(r'\s','',quote)
        matches=[m.start() for m in re.finditer(re.escape(needle),compact)]
        if len(matches)!=1:raise ValueError('这句话在本页出现多次，请多选几个字以准确定位。')
        anchor=matches[0]
    elif kind!='bookmark':raise ValueError('先选中一段原文，再写批注。')
    nid=data.get('id') or uuid.uuid4().hex;stamp=api.now()
    with api.LOCK,api.state_db() as db:
        old=db.execute('SELECT * FROM book_notes WHERE id=?',(nid,)).fetchone()
        if old:
            if author!='用户' and old['author']!=author:raise ValueError('只能修改自己写的批注。')
            if data.get('version')!=old['version']:raise ValueError('批注已在另一端更新，请刷新后再编辑；你的草稿仍在。')
            if old['book_id']!=bid or old['unit']!=unit or old['quote']!=quote:raise ValueError('修改正文时不能改动原文锚点。')
        row={'id':nid,'book_id':bid,'unit':unit,'kind':kind,'author':old['author'] if old else author,'quote':quote,'anchor':anchor,'location':location,
             'body':body,'version':old['version']+1 if old else 1,'deleted':int(bool(data.get('deleted',False))),'created':old['created'] if old else stamp,'updated':stamp}
        db.execute('INSERT OR REPLACE INTO book_notes VALUES(:id,:book_id,:unit,:kind,:author,:quote,:anchor,:location,:body,:version,:deleted,:created,:updated)',row)
        db.execute('INSERT INTO book_note_versions VALUES(?,?,?)',(nid,row['version'],api.dump(row)))
    return row

NOTE_TOOL={'name':'book_notes','description':'为当前共读书籍保存自己的原文批注，或查看本页双方批注。可自主留下有用的阅读观点，每轮最多两条。不能冒充 用户 或改写她的批注。',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['list','add']},'unit':{'type':'INTEGER'},'quote':{'type':'STRING'},'body':{'type':'STRING'}},'required':['action']}}
def note_tool(api,args,reading):
    if not reading:raise ValueError('请先打开共读书籍。')
    if not isinstance(args,dict):raise ValueError('批注参数无效。')
    unit=args.get('unit',reading['unit'])
    if type(unit) is not int or not 1<=unit<=reading['unit']:raise ValueError('不能批注尚未读到的页。')
    if args.get('action')=='list':return {'notes':notes_context(api,reading['id'],unit),'scope':'本页最多 8 条，正文及引文节选，完整内容在批注面板。'}
    if args.get('action')!='add':raise ValueError('批注操作无效。')
    return save_note(api,{'book_id':reading['id'],'unit':unit,'quote':args.get('quote',''),'body':args.get('body','')},'Agent')

def notes_context(api,bid,unit):
    return [dict(n,body=n['body'][:1000],quote=n['quote'][:500]) for n in notes(api,bid,unit)[-8:]]

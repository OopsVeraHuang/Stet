"""Disposable, offline multilingual index of exact original text, never a summary.

The archive and chat DB remain authoritative. Embeddings are content-addressed,
resumable and model-versioned; failed records never receive a success watermark.
"""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import threading
import time

VERSION = 'multilingual-int8-v4-96-24'
_engines = {}
_lock = threading.Lock()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def query_clauses(text):
    """An affectionate opening must not drown out a separate factual topic."""
    parts = [p.strip() for p in re.split(r'[。！？!?\n]+|(?<=\.)\s+',text)]
    return list(dict.fromkeys(p for p in parts if len(re.sub(r'[\W_]+','',p))>=6))[:8]


def documents(api):
    # IDs and original wording survive all model changes. Process traces are not persona.
    with api.archive() as db:
        for row in db.execute('SELECT id,raw_text FROM paragraphs ORDER BY source_id,number'):
            yield str(row[0]), row[1]
        for row in db.execute("SELECT id,raw_text FROM gpt_nodes WHERE status='alternate_dialogue' ORDER BY id"):
            yield 'gptaux:'+str(row[0]), row[1]
    with api.state_db() as db:
        for row in db.execute('SELECT id,text FROM chat ORDER BY id'):
            yield 'chat:'+str(row[0]), row[1]
        for row in db.execute('SELECT note_id,raw_text FROM study_search ORDER BY rowid'):
            yield 'study:'+str(row[0]), row[1]


class Encoder:
    def __init__(self, root):
        os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
        os.environ.setdefault('OMP_NUM_THREADS','1')
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        root = Path(root)
        manifest = json.loads((root/'manifest.json').read_text())
        for name, expected in manifest['files'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
                raise ValueError('检索模型校验失败：'+name)
        self.version = VERSION+':'+manifest['revision']
        self.e5 = manifest['repo'].endswith('multilingual-e5-small')
        self.min_score = .78 if self.e5 else .45
        self.margin = .065 if self.e5 else .20
        self.tokenizer = Tokenizer.from_file(str(root/'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(root/'onnx/model_quantized.onnx'), opts,
                                           providers=['CPUExecutionProvider'])
        self.lock = threading.Lock()

    def spans(self, text):
        if len(re.sub(r'[\W_]+','',text))<8 or re.fullmatch(r'\s*(?:USER|AGENT|user|assistant|助手)[：:\s]*',text,re.I):
            return []  # Original stays saved and lexically searchable; no punctuation-only vectors.
        offsets = self.tokenizer.encode(text, add_special_tokens=False).offsets
        if not offsets:
            return []
        # Token boundaries, not character guesses; overlap preserves boundary phrases.
        spans = [(offsets[i][0], offsets[min(i+96,len(offsets))-1][1])
                 for i in range(0,len(offsets),72)]
        return [(a,b) for a,b in spans if len(re.sub(r'[\W_]+','',text[a:b]))>=8]

    def encode(self, texts, query=False):
        np = self.np
        prefix = ('query: ' if query else 'passage: ') if self.e5 else ''
        rows = [self.tokenizer.encode(prefix+t).ids[:512] for t in texts]
        length = max(map(len,rows))
        ids = np.full((len(rows),length),1,dtype=np.int64)
        mask = np.zeros_like(ids)
        for i,row in enumerate(rows):
            ids[i,:len(row)] = row
            mask[i,:len(row)] = 1
        inputs = {'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)}
        with self.lock:
            hidden = self.session.run(None,{x.name:inputs[x.name] for x in self.session.get_inputs()})[0]
        mean = (hidden*mask[:,:,None]).sum(axis=1)/mask.sum(axis=1)[:,None]
        return (mean/np.maximum(np.linalg.norm(mean,axis=1,keepdims=True),1e-12)).astype('<f4')

    @lru_cache(maxsize=128)
    def query(self, text):
        # Long reading excerpts are searched in windows, not silently cut at token 512.
        spans = self.spans(text)
        chunks = [text[a:b] for a,b in spans] or [text]
        if len(query_clauses(text))>1:
            for clause in query_clauses(text):
                chunks.extend(clause[a:b] for a,b in (self.spans(clause) or [(0,len(clause))]))
        chunks = list(dict.fromkeys(chunks))
        return self.np.concatenate([self.encode(chunks[i:i+8],True) for i in range(0,len(chunks),8)])


class Index:
    def __init__(self, api, encoder=None):
        self.api = api
        self.path = api.STATE/'semantic-memory.sqlite'
        self.encoder = encoder
        self.busy = threading.Lock()
        self.load_lock = threading.Lock()
        self.event = threading.Event()
        self.thread = None
        self.error = None

    @contextmanager
    def db(self, readonly=False):
        conn = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro' if readonly else self.path,
                               uri=readonly,timeout=20)
        try:
            if not readonly:conn.execute('PRAGMA synchronous=NORMAL')
            yield conn
            if not readonly:conn.commit()
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS vectors(hash TEXT PRIMARY KEY,embedding BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS chunks(id TEXT,start INTEGER,end INTEGER,hash TEXT,
              PRIMARY KEY(id,start));
            CREATE TABLE IF NOT EXISTS failures(id TEXT PRIMARY KEY,error TEXT);
            ''')
        if os.name != 'nt':os.chmod(self.path,0o600)

    def model(self):
        with self.load_lock:
            if self.encoder is None:
                self.encoder = Encoder(os.environ['CONTINUITY_SEMANTIC_MODEL'])
        return self.encoder

    def put_meta(self, **values):
        with self.db() as db:
            db.executemany('INSERT OR REPLACE INTO meta VALUES(?,?)',
                           [(k,json.dumps(v,ensure_ascii=False)) for k,v in values.items()])

    def build(self, progress=None):
        if not self.busy.acquire(blocking=False):return
        keeper = None
        try:
            self.initialize()
            # Keep WAL open during bulk work; avoid a full checkpoint per tiny record.
            keeper = sqlite3.connect(self.path)
            keeper.execute('PRAGMA journal_mode')
            model = self.model()
            with self.db() as db:
                row = db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
                if row and json.loads(row[0]) != model.version:
                    # Only derived data; a model mismatch must never mix vector spaces.
                    for table in ('documents','chunks','vectors','failures'):db.execute('DELETE FROM '+table)
                known = dict(db.execute('SELECT id,hash FROM documents'))
                failed_ids = {r[0] for r in db.execute('SELECT id FROM failures')}
            self.put_meta(model=model.version,phase='indexing',started=time.time(),error=None)
            seen = set()
            changed = 0
            for pid,text in documents(self.api):
                seen.add(pid)
                fingerprint = digest(text)
                if known.get(pid)==fingerprint and pid not in failed_ids:continue
                try:
                    spans = model.spans(text)
                    chunks = [(a,b,digest(text[a:b])) for a,b in spans]
                    # Commit embeddings in small batches; interruption is safely resumable.
                    for pos in range(0,len(chunks),8):
                        batch = chunks[pos:pos+8]
                        with self.db() as db:
                            missing = [(a,b,h) for a,b,h in batch if not db.execute('SELECT 1 FROM vectors WHERE hash=?',(h,)).fetchone()]
                        if missing:
                            embeddings = model.encode([text[a:b] for a,b,h in missing])
                            with self.db() as db:
                                db.executemany('INSERT OR REPLACE INTO vectors VALUES(?,?)',
                                    [(h,v.tobytes()) for (_,_,h),v in zip(missing,embeddings)])
                    with self.db() as db:
                        db.execute('DELETE FROM chunks WHERE id=?',(pid,))
                        db.executemany('INSERT INTO chunks VALUES(?,?,?,?)',[(pid,a,b,h) for a,b,h in chunks])
                        db.execute('INSERT OR REPLACE INTO documents VALUES(?,?)',(pid,fingerprint))
                        db.execute('DELETE FROM failures WHERE id=?',(pid,))
                    changed += 1
                    if changed%100==0:
                        self.put_meta(processed=len(seen),updated=time.time())
                        if progress:
                            try:progress(self.status())
                            except Exception as error:
                                # Losing the terminal/log reader does not undo a committed record.
                                self.put_meta(progress_output_error=type(error).__name__)
                                progress = None
                    time.sleep(.001)  # Yield to live requests between records.
                except Exception as error:
                    with self.db() as db:
                        db.execute('INSERT OR REPLACE INTO failures VALUES(?,?)',(pid,type(error).__name__))
            with self.db() as db:
                # Deleted/replaced chats cannot remain searchable through stale vectors.
                for pid in set(known)-seen:
                    db.execute('DELETE FROM documents WHERE id=?',(pid,))
                    db.execute('DELETE FROM chunks WHERE id=?',(pid,))
                failed = db.execute('SELECT count(*) FROM failures').fetchone()[0]
            self.put_meta(total=len(seen),phase='degraded' if failed else 'ready',updated=time.time(),changed=changed)
            self.error = None
        except Exception as error:
            self.error = type(error).__name__+': '+str(error)[:200]
            if self.path.exists():self.put_meta(phase='error',error=self.error,updated=time.time())
            raise
        finally:
            if keeper:keeper.close()
            self.busy.release()

    def status(self):
        result = {'enabled':True,'phase':'pending','indexed':0,'chunks':0,'failed':0,'error':self.error}
        if self.path.exists():
            try:
                with self.db(True) as db:
                    result.update({k:json.loads(v) for k,v in db.execute('SELECT key,value FROM meta')})
                    for label,table in [('indexed','documents'),('chunks','chunks'),('failed','failures')]:
                        result[label] = db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                    result['semantic_documents'] = db.execute('SELECT count(DISTINCT id) FROM chunks').fetchone()[0]
            except sqlite3.Error:
                result['phase'] = 'pending'
        if self.error:result.update(phase='degraded',error=self.error)
        return result

    def search(self, text, limit=24, exclude_chat=()):
        if not self.path.exists():return []
        model = self.model()
        np = model.np
        queries = model.query(text)
        hits = []
        excluded = {'chat:'+str(i) for i in exclude_chat}
        # Stream vector blocks to bound RAM; no giant Python vector matrix cache.
        with self.db(True) as db:
            version = db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
            if not version or json.loads(version[0])!=model.version:return []
            cursor = db.execute('SELECT c.id,c.start,c.end,d.hash,v.embedding FROM chunks c JOIN documents d ON d.id=c.id JOIN vectors v ON v.hash=c.hash')
            while rows:=cursor.fetchmany(1024):
                matrix = np.frombuffer(b''.join(r[4] for r in rows),dtype='<f4').reshape(len(rows),-1)
                scores = (matrix @ queries.T).max(axis=1)
                for i in np.argsort(scores)[-limit:]:
                    if rows[i][0] not in excluded:hits.append((float(scores[i]),rows[i][:4]))
        hits.sort(key=lambda hit:-hit[0])
        result,seen = [],set()
        for score,(pid,start,end,fingerprint) in hits:
            # Similarity is a candidate signal, not probability or proof of an event.
            if score<getattr(model,'min_score',.78) or (hits and score<hits[0][0]-getattr(model,'margin',.065)):continue
            if pid in seen:continue
            try:item = self.api.get_paragraph(pid)
            except ValueError:continue
            if digest(item['raw_text'])!=fingerprint:continue
            seen.add(pid)
            item['retrieval'] = {'method':'local_semantic','score':round(score,4),
                                 'span':[start,end],'model':model.version}
            result.append(item)
            if len(result)>=limit:break
        return result

    def request_update(self):
        with _lock:
            self.event.set()
            if self.thread is not None:return
            def worker():
                while True:
                    with _lock:
                        if not self.event.is_set():
                            self.thread = None
                            return
                        self.event.clear()
                    try:
                        self.build()
                        from memory_regression import run
                        self.put_meta(regression=run(self.api,self))
                    except Exception as error:
                        # Status retains the actual failure; no paid fallback or tight retry loop.
                        self.error = '自动索引或检索检查未完成：'+type(error).__name__
                        with _lock:self.thread = None
                        return
            self.thread = threading.Thread(target=worker,daemon=True,name='memory-index')
            self.thread.start()


def engine(api):
    if not os.environ.get('CONTINUITY_SEMANTIC_MODEL'):return None
    key = (str(api.STATE.resolve()),os.environ['CONTINUITY_SEMANTIC_MODEL'])
    with _lock:
        if key not in _engines:_engines[key] = Index(api)
        return _engines[key]


def status(api):
    item = engine(api)
    return item.status() if item else {'enabled':False,'phase':'off','indexed':0,'chunks':0}


def request_update(api):
    item = engine(api)
    if item:item.request_update()


def retrieve(api,text,limit=24,exclude_chat=()):
    item = engine(api)
    if item is None:return []
    try:return item.search(text,limit,exclude_chat)
    except Exception as error:
        item.error = type(error).__name__+': '+str(error)[:200]
        return []

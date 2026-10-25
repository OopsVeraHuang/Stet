"""Private image storage and compact model renditions; originals are never overwritten."""
import base64
import hashlib
import io
import json
import warnings
from PIL import Image, ImageOps

MAX_BYTES=8*1024*1024
MAX_PIXELS=30_000_000

def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS attachments(
      id TEXT PRIMARY KEY,name TEXT,mime TEXT,width INTEGER,height INTEGER,bytes INTEGER,
      created_at TEXT,original BLOB,rendition BLOB)''')
    columns={r[1] for r in db.execute('PRAGMA table_info(chat)')}
    if 'attachments' not in columns:db.execute("ALTER TABLE chat ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'")
    if 'brain' not in columns:db.execute("ALTER TABLE chat ADD COLUMN brain TEXT NOT NULL DEFAULT 'gemini'")

def upload(api,data):
    value=data.get('data')
    if not isinstance(value,str) or len(value)>MAX_BYTES*4//3+8:raise ValueError('图片过大，单张最多 8 MB。')
    try:raw=base64.b64decode(value,validate=True)
    except Exception:raise ValueError('图片编码无效。') from None
    if not raw or len(raw)>MAX_BYTES:raise ValueError('图片为空或超过 8 MB。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as check:
                if check.format not in ('PNG','JPEG','WEBP') or getattr(check,'n_frames',1)!=1:raise ValueError('format')
                if check.width*check.height>MAX_PIXELS:raise ValueError('pixels')
                mime=Image.MIME[check.format];check.verify()
            with Image.open(io.BytesIO(raw)) as loaded:
                im=ImageOps.exif_transpose(loaded).convert('RGB');im.thumbnail((2048,2048))
                out=io.BytesIO();im.save(out,format='JPEG',quality=90)
                width,height=im.size
    except Exception:raise ValueError('请使用有效的静态 JPG、PNG 或 WebP 图片（最多 3,000 万像素）；HEIC 暂请转成 JPG 或截图。') from None
    aid=hashlib.sha256(raw).hexdigest()
    name=str(data.get('name') or '图片').replace('\\','/').rsplit('/',1)[-1][:150]
    with api.state_db() as db:
        db.execute('INSERT OR IGNORE INTO attachments VALUES(?,?,?,?,?,?,?,?,?)',
                   (aid,name,mime,width,height,len(raw),api.now(),raw,out.getvalue()))
    return metadata(api,aid)

def metadata(api,aid):
    if not isinstance(aid,str) or len(aid)!=64 or any(c not in '0123456789abcdef' for c in aid):raise ValueError('图片编号无效。')
    with api.state_db() as db:row=db.execute('SELECT id,name,mime,width,height,bytes,created_at FROM attachments WHERE id=?',(aid,)).fetchone()
    if row is None:raise ValueError('图片未找到，请重新选择。')
    return dict(row)

def validate(api,ids):
    if ids is None:ids=[]
    if not isinstance(ids,list) or len(ids)>2 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('每次最多发送两张不同图片。')
    return [metadata(api,aid) for aid in ids]

def part(api,aid):
    metadata(api,aid)
    with api.state_db() as db:row=db.execute('SELECT rendition FROM attachments WHERE id=?',(aid,)).fetchone()
    return {'inlineData':{'mimeType':'image/jpeg','data':base64.b64encode(row[0]).decode()},
            'mediaResolution':{'level':'MEDIA_RESOLUTION_HIGH'}}

def bytes_for(api,aid,original=False):
    meta=metadata(api,aid)
    with api.state_db() as db:row=db.execute('SELECT original,rendition FROM attachments WHERE id=?',(aid,)).fetchone()
    return (row[0],meta['mime']) if original else (row[1],'image/jpeg')

"""Original bytes and records are authoritative; the literal search index is disposable."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .importing import ImportProblem, canonical, identity, parse


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'continuity.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, raw BLOB NOT NULL,
                    imported_at TEXT NOT NULL, extensions TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS origins (
                    batch_id TEXT REFERENCES batches(id) ON DELETE CASCADE,
                    ordinal INTEGER, message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
                    locator TEXT NOT NULL, PRIMARY KEY(batch_id, ordinal));
                CREATE TABLE IF NOT EXISTS search_index (
                    message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    folded_text TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA secure_delete=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _preview(self, db, raw, filename):
        result = parse(raw, filename)
        result['already_imported'] = db.execute('SELECT 1 FROM batches WHERE id=?', (result['sha256'],)).fetchone() is not None
        seen = {}
        for row in result['rows']:
            row['duplicate'] = False
            if row['errors']:
                continue
            key, content = identity(row['record']), canonical(row['record'])
            existing = db.execute('SELECT record FROM messages WHERE identity=?', (key,)).fetchone()
            previous = seen.get(key, existing['record'] if existing else None)
            if previous is not None:
                if previous == content:
                    row['duplicate'] = True
                else:
                    row['errors'].append('同一来源/对话/分支/消息 ID 的内容有冲突，不能覆盖原件。')
            seen[key] = content
        rows = result['rows']
        result['summary'] = {'total': len(rows), 'new': sum(not r['duplicate'] and not r['errors'] for r in rows),
                             'duplicates': sum(r['duplicate'] for r in rows),
                             'failed': sum(bool(r['errors']) for r in rows),
                             'warnings': sum(bool(r['warnings']) for r in rows),
                             'branches': sorted({r['record'].get('branch_id') or '未知' for r in rows
                                                 if isinstance(r['record'].get('branch_id'), (str, type(None)))})}
        result['can_import'] = result['summary']['failed'] == 0 and not result['already_imported']
        return result

    def preview(self, raw, filename):
        with self.connect() as db:
            return self._preview(db, raw, filename)

    def import_file(self, raw, filename):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = self._preview(db, raw, filename)
            if result['summary']['failed']:
                raise ImportProblem('存在错误，整批未写入。请修正源文件后重新预览。')
            if result['already_imported']:
                return {'batch_id': result['sha256'], 'added': 0, 'already_imported': True}
            batch = result['sha256']
            now = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',
                       (batch, filename, raw, now, canonical(result['extensions'])))
            for row in result['rows']:
                record = row['record']
                key = identity(record)
                mid = hashlib.sha256(key.encode('utf-8')).hexdigest()
                db.execute('INSERT OR IGNORE INTO messages VALUES (?,?,?)', (mid, key, canonical(record)))
                db.execute('INSERT INTO origins VALUES (?,?,?,?)', (batch, row['ordinal'], mid, canonical(row['locator'])))
                db.execute('INSERT OR IGNORE INTO search_index VALUES (?,?)', (mid, record['text'].casefold()))
            return {'batch_id': batch, 'added': result['summary']['new'], 'already_imported': False}

    def messages(self, query='', source=None, branch=None):
        with self.connect() as db:
            if query:
                records = db.execute('''SELECT m.* FROM messages m JOIN search_index s ON m.id=s.message_id
                                        WHERE instr(s.folded_text, ?) > 0 ORDER BY m.rowid''', (query.casefold(),)).fetchall()
            else:
                records = db.execute('SELECT * FROM messages ORDER BY rowid').fetchall()
            result = []
            for row in records:
                record = json.loads(row['record'])
                if source is not None and record.get('source_id') != source:
                    continue
                if branch is not None and (record.get('branch_id') or '') != branch:
                    continue
                result.append({'key': row['id'], 'record': record})
            return result

    def detail(self, mid):
        with self.connect() as db:
            row = db.execute('SELECT record FROM messages WHERE id=?', (mid,)).fetchone()
            if not row:
                raise KeyError('消息不存在或所属导入已撤销。')
            origins = db.execute('''SELECT o.*, b.filename, b.imported_at FROM origins o
                                    JOIN batches b ON b.id=o.batch_id WHERE message_id=? ORDER BY b.rowid,o.ordinal''', (mid,)).fetchall()
            return {'key': mid, 'record': json.loads(row['record']),
                    'origins': [{**dict(o), 'locator': json.loads(o['locator'])} for o in origins]}

    def batches(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT b.id, b.filename, b.imported_at, length(b.raw) AS bytes,
                      count(o.ordinal) AS records FROM batches b LEFT JOIN origins o ON b.id=o.batch_id
                      GROUP BY b.id ORDER BY b.rowid DESC''')]

    def original(self, batch):
        with self.connect() as db:
            row = db.execute('SELECT raw FROM batches WHERE id=?', (batch,)).fetchone()
            if not row:
                raise KeyError('原文件不存在或已撤销导入。')
            return bytes(row['raw'])

    def remove_batch(self, batch):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM batches WHERE id=?', (batch,)).fetchone():
                raise KeyError('导入批次不存在。')
            before = db.execute('SELECT count(*) FROM messages').fetchone()[0]
            db.execute('DELETE FROM batches WHERE id=?', (batch,))
            db.execute('DELETE FROM messages WHERE NOT EXISTS (SELECT 1 FROM origins WHERE message_id=messages.id)')
            after = db.execute('SELECT count(*) FROM messages').fetchone()[0]
            return {'removed_messages': before - after, 'remaining_messages': after,
                    'remaining_index_entries': db.execute('SELECT count(*) FROM search_index').fetchone()[0],
                    'original_removed': not db.execute('SELECT 1 FROM batches WHERE id=?', (batch,)).fetchone()}

    def rebuild(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM search_index')
            rows = db.execute('SELECT id,record FROM messages').fetchall()
            db.executemany('INSERT INTO search_index VALUES (?,?)',
                           [(r['id'], json.loads(r['record'])['text'].casefold()) for r in rows])
            return {'indexed': len(rows)}

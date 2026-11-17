"""User-owned chat notes. Immutable quotations, Unicode offsets, no model calls."""
import json
import uuid


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS study_notes(
      id INTEGER PRIMARY KEY, source_chat_id INTEGER NOT NULL UNIQUE,
      source_role TEXT NOT NULL, source_time TEXT, text TEXT NOT NULL,
      annotations TEXT NOT NULL DEFAULT '[]', revision INTEGER NOT NULL DEFAULT 1,
      deleted INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS study_search USING fts5(note_id UNINDEXED,raw_text,tokenize='trigram')")
    for row in db.execute('SELECT id FROM study_notes').fetchall():
        sync_index(db,row['id'])


def memory_text(row):
    """An evidence document, not a new chat turn or an inferred personality rule."""
    speaker='用户' if row['source_role']=='user' else 'Agent'
    parts=[f"学习笔记 #{row['id']}；收藏于 {row['created_at']}。收藏不等于认同或永久偏好。",
           f"【原话｜{speaker}｜{row['source_time']}｜chat:{row['source_chat_id']}】\n{row['text']}"]
    for a in json.loads(row['annotations']):
        quote=row['text'][a['start']:a['end']]
        if a['kind']=='comment':
            parts.append(f"【用户 的批注｜{a['time']}】\n所批注的原话：{quote}\n评论：{a['comment']}")
        else:
            parts.append(f"【用户标记｜{a['time']}｜{'加粗' if a['kind']=='bold' else '高亮'}】\n{quote}")
    return '\n\n'.join(parts)


def sync_index(db,nid):
    db.execute('DELETE FROM study_search WHERE rowid=?',(nid,))
    row=db.execute('SELECT * FROM study_notes WHERE id=? AND deleted=0',(nid,)).fetchone()
    if row:
        db.execute('INSERT INTO study_search(rowid,note_id,raw_text) VALUES(?,?,?)',(nid,nid,memory_text(row)))


def memory_item(api,pid):
    with api.state_db() as db:
        row=db.execute('SELECT * FROM study_notes WHERE id=? AND deleted=0',(pid.removeprefix('study:'),)).fetchone()
    if not row:
        raise ValueError('这条学习笔记已撤回或不存在。')
    return {'id':pid,'source_id':pid,'number':row['id'],'speaker':'学习笔记（原话及 用户 的批注分列）',
            'kind':'study_note','raw_text':memory_text(row),'filename':'学习笔记 · 原话与用户批注',
            'timestamp':{'raw':row['created_at'],'timezone':'UTC'},'source_chat_id':row['source_chat_id'],
            'original_timestamp':row['source_time'],'category':'学习笔记',
            'issues':['笔记时间不等于原对话时间；收藏和标记不代表用户认同，批注不是 Agent 的发言。'], 'cherished':[]}


def unpack(row):
    return dict(row) | {'annotations': json.loads(row['annotations'])}


def listing(api, deleted=False, before=0, query=''):
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError('笔记检索词最多 200 字符 / Search is limited to 200 characters.')
    term = query.strip().casefold()
    with api.state_db() as db:
        # Literal Unicode search, including comments; % and _ are ordinary characters.
        # No new index, copied memory store or paid embedding call is needed.
        def matches(text, annotations):
            return int(not term or term in text.casefold() or any(
                term in a.get('comment','').casefold() for a in json.loads(annotations)))
        db.create_function('note_matches', 2, matches)
        rows = db.execute('''SELECT * FROM study_notes WHERE deleted=?
          AND (?=0 OR id<?) AND note_matches(text,annotations)
          ORDER BY id DESC LIMIT 51''', (int(deleted), before, before)).fetchall()
    return {'items': [unpack(r) for r in rows[:50]], 'has_more': len(rows) > 50}


def positive(value):
    if type(value) is not int or value < 1:
        raise ValueError('笔记编号无效。')
    return value


def collect(api, source_id):
    source_id = positive(source_id)
    with api.LOCK, api.state_db() as db:
        row = db.execute('SELECT * FROM study_notes WHERE source_chat_id=?', (source_id,)).fetchone()
        if row:
            if row['deleted']:
                db.execute('UPDATE study_notes SET deleted=0,revision=revision+1,updated_at=? WHERE id=?', (api.now(), row['id']))
                sync_index(db,row['id'])
            return unpack(db.execute('SELECT * FROM study_notes WHERE id=?', (row['id'],)).fetchone())
        source = db.execute('SELECT role,text,time FROM chat WHERE id=?', (source_id,)).fetchone()
        if not source or source['role'] not in ('user', 'assistant') or not source['text']:
            raise ValueError('找不到可收藏的对话文字。')
        at = api.now()
        nid = db.execute('''INSERT INTO study_notes(source_chat_id,source_role,source_time,text,created_at,updated_at)
          VALUES(?,?,?,?,?,?)''', (source_id, source['role'], source['time'], source['text'], at, at)).lastrowid
        sync_index(db,nid)
        return unpack(db.execute('SELECT * FROM study_notes WHERE id=?', (nid,)).fetchone())


def change(api, data):
    nid = positive(data.get('id'))
    revision = positive(data.get('revision'))
    action = data.get('action')
    with api.LOCK, api.state_db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM study_notes WHERE id=?', (nid,)).fetchone()
        if not row:
            raise ValueError('这条笔记不存在。')
        if row['revision'] != revision:
            raise ValueError('这条笔记已在其他页面更新。已保留你的输入，请刷新笔记后重试。')
        annotations = json.loads(row['annotations'])
        deleted = row['deleted']
        if action in ('trash', 'restore'):
            deleted = int(action == 'trash')
        elif deleted:
            raise ValueError('请先恢复这条笔记。')
        elif action == 'annotate':
            start, end, kind = data.get('start'), data.get('end'), data.get('kind')
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(row['text']):
                raise ValueError('请选择笔记中的有效文字。')
            if kind not in ('bold', 'highlight', 'comment'):
                raise ValueError('不支持的批注类型。')
            comment = data.get('comment', '')
            if not isinstance(comment, str) or len(comment) > 4000 or (kind == 'comment' and not comment.strip()):
                raise ValueError('评论需要 1–4000 字。')
            duplicate = next((a for a in annotations if a['kind'] == kind and a['start'] == start and a['end'] == end), None)
            if duplicate and kind != 'comment':
                annotations.remove(duplicate)  # Selecting the same span toggles formatting off.
            else:
                if len(annotations) >= 500:
                    raise ValueError('这条笔记批注较多，请先整理部分标记。')
                annotations.append({'id': uuid.uuid4().hex, 'kind': kind, 'start': start, 'end': end,
                                    'comment': comment.strip() if kind == 'comment' else '', 'time': api.now()})
        elif action == 'remove_annotation':
            annotations = [a for a in annotations if a['id'] != data.get('annotation_id')]
        else:
            raise ValueError('不支持的笔记操作。')
        db.execute('''UPDATE study_notes SET annotations=?,deleted=?,revision=revision+1,updated_at=?
          WHERE id=?''', (api.dump(annotations), deleted, api.now(), nid))
        sync_index(db,nid)
        return unpack(db.execute('SELECT * FROM study_notes WHERE id=?', (nid,)).fetchone())

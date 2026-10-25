"""Evidence-backed place aliases and location transitions; originals remain immutable."""
import datetime as dt
import json
import re
import temporal

RULE='''地点箱子：别名只说明词义，不证明用户当前所在地。“家里”与学校/宿舍不能混为一处。
位置记录仅来自用户明确报告或手动登记，不来自 VPN、模型推测、照片背景或助手自己的话。
当前位置只能说“最近一次报告在……”。延续区间是未收到变化时的推定，不是持续定位；长时间未确认要保留不确定。
检索片段的 location 是消息发出时的地点线索，不一定是文中事件发生地。旧资料未标明位置时不能套用现在的箱子。
用户清楚说“我现在在/我到了/我离开了”后可以使用 record_location；引用、假设、计划、过去经历均不得写为当前位置。
工具需要本轮用户原话中的完整位置短句，不能添加用户未说出的城市、日期或地址。保存失败或语义不明确时不要声称已更新。
程序计算的时间关系优先于直觉：同一天不等于相隔很短；跨午夜也不等于相隔很多天。消息记录时间与事件发生时间始终分开。
'''

TOOL={'name':'record_location','description':'从本轮用户明确的当前位置/到达/离开短句登记地点；新地点自动建立箱子。计划、引用和历史叙述不写入。不读 GPS，用户可撤回。',
      'parameters':{'type':'OBJECT','properties':{'evidence':{'type':'STRING','description':'本轮原话中的完整位置短句，如“我现在在示例城市”或“I am now in Paris”，不是转述。'}},'required':['evidence']}}


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS place_boxes(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,
      parent_id INTEGER,aliases TEXT NOT NULL,purpose TEXT NOT NULL,evidence TEXT NOT NULL,
      source TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS location_events(id INTEGER PRIMARY KEY,box_id INTEGER NOT NULL,
      action TEXT NOT NULL,recorded_at TEXT NOT NULL,source_chat_id INTEGER,evidence TEXT NOT NULL,
      source TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',changed_at TEXT NOT NULL,
      UNIQUE(source_chat_id,evidence));
    CREATE INDEX IF NOT EXISTS location_time ON location_events(recorded_at,id);
    CREATE TABLE IF NOT EXISTS place_audit(id INTEGER PRIMARY KEY,time TEXT NOT NULL,action TEXT NOT NULL,data TEXT NOT NULL);
    ''')


def boxes(api):
    with api.state_db() as db:
        return [{**dict(r),'aliases':json.loads(r['aliases'])} for r in db.execute('SELECT * FROM place_boxes ORDER BY id')]


def save_box(api,data,source='user_interface'):
    name=data.get('name','').strip();aliases=data.get('aliases',[]);parent=data.get('parent_id');cid=data.get('id')
    if not name or len(name)>80 or not isinstance(aliases,list) or len(aliases)>30 or any(not isinstance(a,str) or not a.strip() or len(a)>80 for a in aliases):
        raise ValueError('请填写地点名称和简短别名（每项最多80字）。')
    if len(data.get('purpose',''))>300 or len(data.get('evidence',''))>2000:raise ValueError('地点说明过长。')
    aliases=list(dict.fromkeys([name]+[a.strip() for a in aliases]));stamp=api.now()
    with api.LOCK,api.state_db() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT * FROM place_boxes WHERE id=?',(cid,)).fetchone() if cid else None
        if cid and not old:raise ValueError('地点不存在。')
        if parent:
            seen={cid};node=parent
            while node:
                if node in seen:raise ValueError('地点不能互相作为父级。')
                seen.add(node);row=db.execute('SELECT parent_id FROM place_boxes WHERE id=?',(node,)).fetchone()
                if not row:raise ValueError('上级地点不存在。')
                node=row[0]
        names={a.casefold() for a in aliases}
        for row in db.execute('SELECT id,aliases FROM place_boxes'):
            if row['id']!=cid and names.intersection(a.casefold() for a in json.loads(row['aliases'])):raise ValueError('这个别名已属于另一个地点，请先修改原来的词义。')
        values=(name,parent,json.dumps(aliases,ensure_ascii=False),data.get('purpose',''),data.get('evidence',''),source)
        if old:
            db.execute('UPDATE place_boxes SET name=?,parent_id=?,aliases=?,purpose=?,evidence=?,source=?,updated_at=? WHERE id=?',(*values,stamp,cid))
        else:cid=db.execute('INSERT INTO place_boxes(name,parent_id,aliases,purpose,evidence,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(*values,stamp,stamp)).lastrowid
        db.execute('INSERT INTO place_audit(time,action,data) VALUES(?,?,?)',(stamp,'edit_box' if old else 'create_box',api.dump({'id':cid,'before':dict(old) if old else None,'after':data,'source':source})))
    return cid


def seed_confirmed(api):
    """New profiles start without any location assumptions."""
    return


def statements(text):
    """Only unquoted declarative clauses. Ambiguity deliberately produces no automatic update."""
    text=re.sub(r'```[\s\S]*?```|[“「『\"][\s\S]*?[”」』\"]','',text)
    text='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
    for sentence in re.split(r'[。.!！\n;；]',text):
        if re.search(r'[?？]|昨天|以前|去年|明天|打算|如果|假如|计划|比如|例如|他说|她说|朋友说|\b(yesterday|tomorrow|used to|will|would|if|plan|said|example)\b|вчера|завтра|если|планир|сказал',sentence,re.I):continue
        for clause in re.split(r'[,，]',sentence):
            clause=clause.strip()
            if clause:yield clause


def parse_statement(api,clause):
    patterns=[
        ('present',r'^我(?:现在|已经|刚刚|刚)?(?:到|回到|回)(家|宿舍|学校)了$'),
        ('present',r'^我(?:现在|目前|此刻)?(?:已经|刚刚|刚)?(?:在|到了|到达了|回到(?:了)?)(.{1,60}?)(?:了)?$'),
        ('left',r'^我(?:现在|已经|刚刚|刚)?离开(?:了)?(.{1,60}?)(?:了)?$'),
        ('present',r"^I(?: am|'m) (?:now |currently )?(?:in |at )?(?:the )?(.{1,60})$"),
        ('present',r'^I (?:just |have just )?arrived (?:in |at )(?:the )?(.{1,60})$'),
        ('left',r'^I (?:just |have just )?left (?:the )?(.{1,60})$'),
        ('present',r'^Я (?:сейчас |теперь )?(?:в |на )(.{1,60})$'),
        ('present',r'^Я (?:сейчас |теперь )?(дома)$'),
        ('left',r'^Я (?:уже )?(?:уехал[а]? из|покинул[а]?) (.{1,60})$')]
    for action,pattern in patterns:
        match=re.fullmatch(pattern,clause,re.I)
        if not match:continue
        location=match[1].strip()
        # Accept known aliases freely, but new boxes only with clear locative markers.
        known=next((b for b in boxes(api) if location.casefold() in [a.casefold() for a in b['aliases']]),None)
        if not known:
            if re.search(r'想|看|吃|说|等|梦|研究|考虑|学习|工作|努力|心里|怀里|身边|你|不|没|时候|准备|或者|还是|[：:“”\"<>/{}]|\b(happy|sad|love|trouble|your|arms|heart|thinking|reading|working|studying|not|or|and)\b|тво|объят|сердц',location,re.I):return None
            if not re.fullmatch(r'[\w\s\-·]{1,40}',location,re.UNICODE):return None
            if re.match(r"^I(?: am|'m) (?:now |currently )?(?!in |at )",clause,re.I):return None
            if clause.startswith('我在'):return None  # Bare ambiguous activity clauses need an explicit now/arrival or known place.
        return {'action':action,'name':known['name'] if known else location,'box_id':known['id'] if known else None,'evidence':clause}
    return None


def record(api,chat_id,evidence):
    with api.state_db() as db:row=db.execute("SELECT * FROM chat WHERE id=? AND role='user'",(chat_id,)).fetchone()
    if not row or not isinstance(evidence,str) or evidence not in list(statements(row['text'])):raise ValueError('需要本轮用户未引用、非计划的完整位置短句；未保存。')
    if sum(parse_statement(api,c) is not None for c in statements(row['text']))!=1:raise ValueError('同一消息含多处位置，顺序不明确；请手动确认，未保存。')
    parsed=parse_statement(api,evidence)
    if not parsed:raise ValueError('位置短句存在歧义；请用户在记忆页确认，不能推测。')
    with api.LOCK:
        with api.state_db() as db:
            existing=db.execute('SELECT id,status FROM location_events WHERE source_chat_id=? AND evidence=?',(chat_id,evidence)).fetchone()
            if existing:return dict(existing) # Never reactivate a revoked source on retry.
        box_id=parsed['box_id'] or save_box(api,{'name':parsed['name'],'aliases':[],'purpose':'用户明确报告的新地点；未推断城市层级','evidence':evidence},'chat:'+str(chat_id))
        with api.state_db() as db:
            cid=db.execute('INSERT INTO location_events(box_id,action,recorded_at,source_chat_id,evidence,source,status,changed_at) VALUES(?,?,?,?,?,?,?,?)',
                           (box_id,parsed['action'],row['time'],chat_id,evidence,'chat:'+str(chat_id),'active',api.now())).lastrowid
    return {'id':cid,'status':'active','action':parsed['action'],'place':parsed['name'],'recorded_at':row['time']}


def observe(api,chat_id):
    with api.state_db() as db:row=db.execute("SELECT text FROM chat WHERE id=? AND role='user'",(chat_id,)).fetchone()
    if not row:return []
    candidates=[c for c in statements(row['text']) if parse_statement(api,c)]
    # Two different places in an un-timestamped message are not an ordered itinerary.
    if len(candidates)!=1:return []
    return [record(api,chat_id,candidates[0])]


def change(api,cid,status):
    if type(cid) is not int or status not in ('active','revoked'):raise ValueError('无效的位置记录。')
    with api.LOCK,api.state_db() as db:
        row=db.execute('SELECT * FROM location_events WHERE id=?',(cid,)).fetchone()
        if not row:raise ValueError('位置记录不存在。')
        db.execute('UPDATE location_events SET status=?,changed_at=? WHERE id=?',(status,api.now(),cid))
        db.execute('INSERT INTO place_audit(time,action,data) VALUES(?,?,?)',(api.now(),'change_location',api.dump({'id':cid,'before':row['status'],'after':status})))
    return {'id':cid,'status':status}


def manual(api,data):
    cid=data.get('box_id');action=data.get('action')
    if type(cid) is not int or action not in ('present','left'):raise ValueError('请选择地点与到达/离开。')
    with api.LOCK,api.state_db() as db:
        box=db.execute('SELECT name FROM place_boxes WHERE id=?',(cid,)).fetchone()
        if not box:raise ValueError('地点不存在。')
        stamp=api.now();evidence='用户在记忆页明确登记：'+('现在在' if action=='present' else '现在离开')+box['name']
        eid=db.execute("INSERT INTO location_events(box_id,action,recorded_at,evidence,source,status,changed_at) VALUES(?,?,?,?,?,'active',?)",(cid,action,stamp,evidence,'user_interface',stamp)).lastrowid
    return {'id':eid,'status':'active'}


def at(api,when,chat_id=None):
    point=temporal.instant(when)
    if not point or not point.tzinfo:return {'status':'unknown','note':'缺可靠时间，未套用当前地点'}
    with api.state_db() as db:
        rows=db.execute("SELECT * FROM location_events WHERE status='active' ORDER BY recorded_at,id").fetchall()
    previous=None;following=None
    for row in rows:
        stamp=temporal.instant(row['recorded_at'])
        if stamp==point and chat_id is not None and (row['source_chat_id'] is None or row['source_chat_id']>chat_id):
            following=dict(row);break
        if stamp<=point:previous=dict(row)
        else:following=dict(row);break
    if not previous:return {'status':'unknown','note':'该时刻之前没有用户确认的位置记录'}
    by_id={b['id']:b for b in boxes(api)};box=by_id[previous['box_id']]
    age=(point-temporal.instant(previous['recorded_at'])).total_seconds()
    return {'status':'left_unknown' if previous['action']=='left' else 'last_reported' if age==0 else 'inherited_unverified',
            'place':None if previous['action']=='left' else box['name'],'parent':by_id.get(box['parent_id'],{}).get('name'),
            'left_place':box['name'] if previous['action']=='left' else None,
            'report_time':previous['recorded_at'],'source':previous['source'],'evidence':previous['evidence'],
            'interval_until':following['recorded_at'] if following else None,'seconds_since_report':round(age),
            'needs_reconfirmation':age>86400,'note':'地点延续只是最后一次报告的推定；不证明持续停留，也不是文中事件发生地'}


def context(api,include_current=True):
    bs=boxes(api)
    compact=[{'place':b['name'],'aliases':b['aliases'],'parent':next((x['name'] for x in bs if x['id']==b['parent_id']),None),'meaning':b['purpose']} for b in bs]
    return RULE+'\n地点词义（用户可修改，不是当前位置）：'+api.dump(compact)+('\n最近位置依据：'+api.dump(at(api,api.now())) if include_current else '')


def annotate(api,items):
    anchor=api.now()
    for item in items:
        item['time_context']={**temporal.describe(item.get('timestamp'),anchor),'source_scope':item.get('source_id'),
                              'source_sequence':item.get('number'),'order_note':'序号仅在同一来源/分支内有序，不代表跨平台事件先后'}
        item['location']=at(api,item.get('timestamp'),item.get('number')) if item.get('source_id')=='live-chat' else {'status':'unknown','note':'旧档案未建立经核实的位置区间，不能套用目前的家或学校'}
    return items


def listing(api,before=None):
    with api.state_db() as db:
        events=[dict(r) for r in db.execute('SELECT * FROM location_events ORDER BY id DESC LIMIT 200')]
        audit=[dict(r) for r in db.execute('SELECT * FROM place_audit ORDER BY id DESC LIMIT 30')]
        messages=[dict(r) for r in db.execute('SELECT id,role,time FROM chat WHERE id<? ORDER BY id DESC LIMIT 41',(before or 2**63-1,))]
    more=len(messages)>40;messages=messages[:40];messages.reverse()
    prev=None
    for m in messages:
        m['time_context']=temporal.describe(m['time'],api.now(),prev);m['location']=at(api,m['time'],m['id']);prev=m['time']
    return {'boxes':boxes(api),'events':events,'current':at(api,api.now()),'messages':messages,'has_older':more,
            'next_before':messages[0]['id'] if more else None,'audit':audit}

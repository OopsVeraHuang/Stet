"""Deterministic context selection; no paid summaries and no archive mutation."""
import datetime as dt
import re
import temporal


def recent(rows, text=''):
    # Rows arrive newest first. Keep complete user-led exchanges, never clip prose.
    extended = bool(re.search(r'继续|刚才|上面|第二个|那个|continue|previous|that one', text, re.I))
    limit = 12 if extended else 6
    budget = 16000 if extended else 8000
    chosen=[]; size=0
    for row in rows[:limit]:
        if chosen and size+len(row['text'])>budget:break
        chosen.append(row);size+=len(row['text'])
    chosen.reverse()
    while chosen and chosen[0]['role']!='user':chosen.pop(0)
    # A very long assistant answer must not evict its user anchor.
    if not chosen and rows:
        for row in rows[:12]:
            chosen.insert(0,row)
            if row['role']=='user':break
    return chosen


def date_range(text, reference=None):
    today=(reference or dt.datetime.now(temporal.BEIJING)).astimezone(temporal.BEIJING).date()
    dates=[]
    for y,m,d in re.findall(r'(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?',text):
        try:dates.append(dt.date(int(y),int(m),int(d)))
        except ValueError:pass
    if len(set(dates))==1:return dates[0],dates[0]+dt.timedelta(days=1)
    if dates:return None  # Ambiguous ranges are not silently reduced to one day.
    matches=[]
    for pattern,offset in [(r'前天|day before yesterday',-2),(r'昨天|yesterday',-1),(r'今天|\btoday\b',0)]:
        if re.search(pattern,text,re.I):matches.append(offset)
    if len(matches)==1:
        start=today+dt.timedelta(days=matches[0]);return start,start+dt.timedelta(days=1)
    if len(matches)>1:return None
    if re.search(r'上周|上星期|last week',text,re.I):
        end=today-dt.timedelta(days=today.weekday());return end-dt.timedelta(days=7),end
    return None


def date_priority(items,text,reference=None):
    bounds=date_range(text,reference)
    if not bounds:return items
    matched=[];other=[]
    for item in items:
        point=temporal.instant(item.get('timestamp'))
        inside=bool(point and point.tzinfo and bounds[0]<=point.astimezone(temporal.BEIJING).date()<bounds[1])
        item=dict(item)
        item['retrieval_time']={'requested_start':str(bounds[0]),'requested_end_exclusive':str(bounds[1]),
            'recorded_in_range':inside if point and point.tzinfo else None,
            'note':'按消息记录时间优先排序，非事件日期证明；范围外或未知日期仅为补充线索'}
        (matched if inside else other).append(item)
    return matched+other


def continuity_card(rows, retained):
    """Extractive pointers, not invented task/state/personality assertions."""
    ids={r['id'] for r in retained}
    older=[r for r in rows if r['id'] not in ids and r['role']=='user'][:2]
    return [{'chat_id':r['id'],'recorded_at':r['time'],
             'excerpt':r['text'][:240],'truncated':len(r['text'])>240} for r in reversed(older)]

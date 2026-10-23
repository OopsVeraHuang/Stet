"""Server clock and explicit message chronology, shared by all providers."""
import datetime as dt

BEIJING=dt.timezone(dt.timedelta(hours=8))
RULE='''时间依据：当前时间以本轮服务器时钟为准，默认北京时间 Asia/Shanghai（UTC+08:00），不按 VPN 出口推断时区。
近期消息的 recorded_at 是消息记录时间，不必然是其中事件的发生时间。不要把几小时前、昨天或历史资料里的场景说成正在发生。
历史原文中的“今天/明天/昨天”相对于该条原文记录的日期，不相对于现在；时间或时区不明确就保留不确定，不能拿导入日期冒充事件日期。
涉及“刚才、今晚、明天”、距离上次聊天多久、日期或日程时，先核对消息时间与当前时间；需要刷新时用 get_current_time。
用户指出时间理解错误时，重新核对时间依据并修正自己的判断，不能重复旧结论。除非有必要，不逐条报时，不把以上元数据念给用户。'''

TOOL={'name':'get_current_time','description':'读取服务器当前北京时间和 UTC，用于核对日期、相对时间或长任务后的时刻。不联网，不读取用户位置。',
      'parameters':{'type':'OBJECT','properties':{}}}

def clock():
    instant=dt.datetime.now(dt.timezone.utc)
    local=instant.astimezone(BEIJING)
    return {'beijing':local.isoformat(timespec='seconds'),'utc':instant.isoformat(timespec='seconds'),
            'timezone':'Asia/Shanghai','weekday':['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][local.weekday()]}

def stamp(value):
    """Convert only timestamps with known offsets; never invent a missing zone."""
    try:
        instant=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if instant.tzinfo is not None:return instant.astimezone(BEIJING).isoformat(timespec='seconds')+'（北京时间）'
    except (TypeError,ValueError,AttributeError):pass
    return (str(value)+'（时区未确认）') if value else '时间未记录'

def instant(value):
    if isinstance(value,dict):
        raw=value.get('local_datetime') or value.get('raw')
        zone=value.get('timezone')
    else:raw=value;zone=None
    try:
        parsed=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
        if parsed.tzinfo is None and zone=='UTC':parsed=parsed.replace(tzinfo=dt.timezone.utc)
        if parsed.tzinfo is None and zone in ('Asia/Shanghai','UTC+08:00'):parsed=parsed.replace(tzinfo=BEIJING)
        return parsed
    except (TypeError,ValueError,AttributeError):return None


def describe(value, reference=None, previous=None):
    """Deterministic chronology. Unknown zones never become Beijing by guessing."""
    point=instant(value);anchor=instant(reference) if reference else dt.datetime.now(dt.timezone.utc)
    result={'meaning':'消息记录时间，不等于文中事件发生时间','event_time':'需依原文另行判断'}
    if point is None:return {**result,'precision':'unknown','recorded_at':None,'note':'无可靠逐条时间；不能用导入时间补齐'}
    if point.tzinfo is None:
        return {**result,'precision':'source_local','recorded_at':point.isoformat(),
                'source_calendar_date':point.date().isoformat(),'timezone':'unknown',
                'note':'可按同一来源原文顺序核对；不可计算距离现在多久或与其他时区强行排序'}
    local=point.astimezone(BEIJING)
    result.update(precision='instant',recorded_at=local.isoformat(timespec='seconds'),
                  timezone='Asia/Shanghai',calendar_date=local.date().isoformat())
    if anchor and anchor.tzinfo:
        age=(anchor-point).total_seconds();days=(anchor.astimezone(BEIJING).date()-local.date()).days
        result.update(seconds_before_reference=round(age),calendar_days_before_reference=days,
                      same_beijing_day_as_reference=days==0)
        result['relative_to_reference']=('晚于本轮时间，需核对' if age<0 else
            f'距本轮 {int(age//3600)} 小时 {int(age%3600//60)} 分钟；北京时间相差 {days} 个日历日')
    prev=instant(previous)
    if prev and prev.tzinfo:
        result.update(seconds_after_previous=round((point-prev).total_seconds()),
                      same_beijing_day_as_previous=local.date()==prev.astimezone(BEIJING).date())
    return result


def message(text, recorded_at, reference=None, previous=None):
    import json
    return '[消息 recorded_at：'+stamp(recorded_at)+'；这是记录时间]\n[程序计算的时间关系：'+json.dumps(describe(recorded_at,reference,previous),ensure_ascii=False)+']\n'+text

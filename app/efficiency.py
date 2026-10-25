"""Payload measurement and lossless metadata compaction; no model calls."""
import json

def compact(value):
    """Drop only empty containers/nulls, not false/zero or original text."""
    if isinstance(value,dict):
        return {k:compact(v) for k,v in value.items() if v is not None and v!=[] and v!={}}
    if isinstance(value,list):return [compact(v) for v in value]
    return value

def text_chars(value):
    # Character sizes are not token counts or price estimates.
    if isinstance(value,dict):
        return sum(len(v) if k=='text' and isinstance(v,str) else text_chars(v) for k,v in value.items())
    if isinstance(value,list):return sum(text_chars(v) for v in value)
    return 0

def measure(payload):
    contents=payload.get('contents',[])
    return {'unit':'characters_not_tokens','system_chars':text_chars(payload.get('systemInstruction',{})),
            'conversation_and_evidence_chars':text_chars(contents),
            'tool_schema_chars':len(json.dumps(payload.get('tools',[]),ensure_ascii=False,separators=(',',':'))),
            'function_response_chars':sum(len(json.dumps(p['functionResponse'],ensure_ascii=False,separators=(',',':')))
                for c in contents for p in c.get('parts',[]) if 'functionResponse' in p),
            'serialized_bytes':len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())}

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS context_measurements(request_id TEXT PRIMARY KEY,job_id TEXT,round INTEGER,metrics TEXT)')

def record(api,rid,job,round_number,payload):
    with api.state_db() as db:
        db.execute('INSERT INTO context_measurements VALUES(?,?,?,?)',(rid,job,round_number,json.dumps(measure(payload))))

def report(api):
    with api.state_db() as db:
        rows=db.execute('''SELECT m.job_id,m.round,m.metrics,l.usage,l.status,l.estimated_rmb
          FROM context_measurements m JOIN ledger l ON l.id=m.request_id ORDER BY l.time DESC LIMIT 100''').fetchall()
    return [{**dict(r),'metrics':json.loads(r['metrics']),'usage':json.loads(r['usage'] or '{}')} for r in rows]

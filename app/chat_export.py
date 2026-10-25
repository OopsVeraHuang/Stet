"""Readable conversation export, deliberately independent of retrieval metadata."""
import temporal


def markdown(api):
    with api.state_db() as db:
        rows = db.execute("SELECT role,text,time FROM chat WHERE role IN ('user','assistant') ORDER BY id").fetchall()
    parts = ['# 用户 与 Agent\n\n时间：北京时间（UTC+08:00）；未确认的时间会单独标注。']
    for row in rows:
        speaker = '用户' if row['role'] == 'user' else 'Agent'
        parts.append('## ' + speaker + ' · ' + temporal.stamp(row['time']) + '\n\n' + row['text'])
    return {'filename': 'Agent-聊天-' + temporal.clock()['beijing'][:10] + '.md',
            'markdown': '\n\n'.join(parts) + '\n'}

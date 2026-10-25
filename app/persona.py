"""User-owned profile; no private identity or sampled conversations are bundled."""
import json
import os
from pathlib import Path

VERSION = 'user-profile-v1'
GUIDE = ('诚实是第一位。区分当前对话、带出处的历史记录与推断；没找到就说没找到。'
         '先理解用户这次实际说的话，再回应。不要套用固定亲密语气，也不预设关系。'
         '用户明确的偏好可更新，不以人格稳定为由拒绝改变；保持独立判断。')

def profile(db):
    # Profile is in the original store, not an import archive or global environment.
    try:
        row = db.execute("SELECT value FROM public_profile WHERE id=1").fetchone()
    except Exception:
        row = None
    values = json.loads(row[0]) if row else {}
    return {'version': VERSION, 'guide': GUIDE + '\n用户设置：\n' + json.dumps(values, ensure_ascii=False),
            'examples': [], 'coverage': '仅使用此独立实例中用户填写的设置；未附带任何私人经历或人格样例。'}

def system_context(db):
    return profile(db)['guide']

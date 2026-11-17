"""Lossless, deliberately narrow JSON/Markdown import with inspectable diagnostics."""
from datetime import datetime
import hashlib
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_BYTES = 32 * 1024 * 1024
MAX_MESSAGES = 20000
MD_HEADER = '# Continuity transcript v1\n'
MARKER = re.compile(r'^<!-- continuity-message: (\{[^\n]*\}) -->\r?\n', re.MULTILINE)
ROLES = {'user', 'assistant', 'system', 'tool', 'unknown'}


class ImportProblem(ValueError):
    pass


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ImportProblem('JSON 字段重复：' + key)
            result[key] = value
        return result

    def constant(_):
        raise ImportProblem('JSON 不接受 NaN / Infinity。')

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as error:
        raise ImportProblem('JSON 格式错误：' + str(error)) from error


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def identity(record):
    return canonical([record.get(k) for k in ('source_id', 'conversation_id', 'branch_id', 'id')])


def parse(raw, filename):
    from . import native_import
    if not raw or len(raw) > MAX_BYTES:
        raise ImportProblem('文件必须非空且不超过 32 MiB。')
    original = raw
    member = None
    if filename.lower().endswith('.zip'):
        raw, member = native_import.unzip(raw)
        filename = member
    try:
        text = raw.decode('utf-8-sig')
        # JSON escaped surrogates are checked again after parsing.
        text.encode('utf-8')
    except UnicodeError as error:
        raise ImportProblem('请使用 UTF-8 编码的 JSON 或 MD 文件。') from error
    envelope = {}
    if filename.lower().endswith('.json'):
        envelope = strict_json(text)
        try:
            adapted = native_import.adapt(envelope)
        except (AttributeError, TypeError, KeyError, RecursionError) as error:
            raise ImportProblem('Invalid native export structure / 平台导出结构无效。') from error
        if adapted:
            records, report = adapted
            envelope = {'native_import':report}
        elif isinstance(envelope, dict) and isinstance(envelope.get('messages'), list):
            records = [(r, {'json_pointer': f'/messages/{i}'}) for i, r in enumerate(envelope['messages'])]
        else:
            raise ImportProblem('未识别的导出格式。支持 ChatGPT / Claude conversations.json、Gemini Takeout JSON、AI Studio JSON 和规范 messages JSON。')
    elif filename.lower().endswith('.md'):
        markers = list(MARKER.finditer(text))
        if not text.replace('\r\n', '\n').startswith(MD_HEADER) or not markers:
            raise ImportProblem('MD 须使用 Continuity transcript v1 模板及角色元数据标记；请下载示例。')
        if text[:markers[0].start()].replace('\r\n', '\n').strip() != MD_HEADER.strip():
            raise ImportProblem('MD 首条消息前有未标注正文，请放入消息中。')
        records = []
        for i, marker in enumerate(markers):
            record = strict_json(marker.group(1))
            if 'text' in record:
                raise ImportProblem('MD 元数据不能包含 text；正文须位于标记之后。')
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            record['text'] = text[marker.end():end]
            records.append((record, {'metadata_line': text.count('\n', 0, marker.start()) + 1,
                                     'text_start_line': text.count('\n', 0, marker.end()) + 1,
                                     'text_end_line': text.count('\n', 0, end) + (not text[:end].endswith('\n'))}))
    else:
        raise ImportProblem('请选择支持的 JSON、ZIP 或 Continuity MD 文件；HTML、PDF 不能作为聊天档案导入。')
    if not records or len(records) > MAX_MESSAGES:
        raise ImportProblem(f'一次须包含 1–{MAX_MESSAGES} 条消息。')
    rows = []
    for i, (record, locator) in enumerate(records):
        if member: locator = {**locator, 'zip_member':member}
        errors, warnings = [], []
        if not isinstance(record, dict):
            record = {'unparsed_value': record}
            errors.append('消息须为对象。')
        for key in ('id', 'source_id', 'conversation_id', 'text'):
            if not isinstance(record.get(key), str) or not record[key].strip():
                errors.append(f'{key} 必须为非空字符串。')
        for key in ('branch_id', 'role', 'recorded_at', 'timezone', 'time_precision', 'imported_at'):
            value = record.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f'{key} 须为非空字符串或 null。')
        for key, label in (('role', '角色'), ('recorded_at', '记录时间'), ('branch_id', '分支'),
                           ('timezone', '时区'), ('time_precision', '时间精度')):
            if record.get(key) in (None, 'unknown'):
                warnings.append(label + '未知，保留缺失，不自动补齐。')
        role = record.get('role')
        if isinstance(role, str) and role not in ROLES:
            errors.append('角色不受支持，请使用 user / assistant / system / tool / unknown 或 null。')
        for key in ('recorded_at', 'imported_at'):
            value = record.get(key)
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    errors.append(key + ' 不是有效 ISO 日期或时间。')
        precision = record.get('time_precision')
        if isinstance(precision, str) and precision not in {'unknown', 'day', 'minute', 'second'}:
            errors.append('time_precision 仅支持 unknown / day / minute / second。')
        timezone = record.get('timezone')
        if isinstance(timezone, str):
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                warnings.append('时区名称未识别；保留原值，不执行时区转换。')
        rows.append({'ordinal': i, 'record': record, 'locator': locator, 'errors': errors, 'warnings': warnings})
    try:
        canonical([envelope, rows]).encode('utf-8')
    except (UnicodeError, RecursionError) as error:
        raise ImportProblem('文件含无法保存的 Unicode 或过深嵌套。') from error
    return {'sha256': hashlib.sha256(original).hexdigest(), 'bytes': len(original), 'rows': rows,
            'extensions': {k: v for k, v in envelope.items() if k != 'messages'}}

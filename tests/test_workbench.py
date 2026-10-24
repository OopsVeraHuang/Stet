"""Executable P1-A regressions. The 14 P1-B governance scenarios remain specifications."""
import base64
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from continuity.importing import ImportProblem, MAX_BYTES, parse
from continuity.server import make_server
from continuity.store import Store

ROOT = Path(__file__).resolve().parents[1]


def raw(messages, **extra):
    return json.dumps({'messages': messages, **extra}, ensure_ascii=False).encode('utf-8')


def message(**changes):
    return {'id':'m1', 'source_id':'fiction', 'conversation_id':'c1', 'branch_id':'main',
            'role':'user', 'text':'松湾 Evidence Вчера 100% _ literal', 'recorded_at':None, **changes}


class ImportTests(unittest.TestCase):
    def test_json_preview_preserves_every_field_and_unknowns(self):
        content = (ROOT / 'examples/messages.json').read_bytes()
        result = parse(content, 'messages.json')
        self.assertEqual([r['record'] for r in result['rows']], json.loads(content)['messages'])
        self.assertEqual(result['sha256'], hashlib.sha256(content).hexdigest())
        unknown = result['rows'][-1]
        self.assertIsNone(unknown['record']['recorded_at'])
        self.assertNotIn('branch_id', unknown['record'])
        self.assertTrue(unknown['warnings'])

    def test_md_preserves_crlf_body_and_locations(self):
        content = (ROOT / 'examples/messages.md').read_bytes().replace(b'\n', b'\r\n')
        result = parse(content, 'messages.md')
        self.assertEqual(len(result['rows']), 4)
        lines = content.decode().splitlines(keepends=True)
        for row in result['rows']:
            loc = row['locator']
            self.assertEqual(row['record']['text'], ''.join(lines[loc['text_start_line']-1:loc['text_end_line']]))
        self.assertIn('\r\n', result['rows'][0]['record']['text'])
        self.assertEqual(result['rows'][0]['record']['event_time_note']['text'], '昨天')

    def test_bad_files_never_silently_guess(self):
        for content, name in [(b'[]','x.json'), (b'{"messages":[],"messages":[]}', 'x.json'),
                              (b'{"messages":[NaN]}','x.json'), (b'\xff','x.json'),
                              (b'# user\nhello','x.md'), (b'{}','x.docx'),
                              (b'x'*(MAX_BYTES+1),'x.json'), (b'{"messages":["\\ud800"]}','x.json')]:
            with self.subTest(name=name, content=content[:30]), self.assertRaises(ImportProblem):
                parse(content, name)

    def test_invalid_role_time_and_record_are_visible(self):
        rows = parse(raw([message(role='human', recorded_at='yesterday'), 7]), 'x.json')['rows']
        self.assertTrue(any('角色' in e for e in rows[0]['errors']))
        self.assertTrue(any('ISO' in e for e in rows[0]['errors']))
        self.assertTrue(rows[1]['errors'])

    def test_unknown_timezone_and_naive_time_are_not_converted(self):
        r = message(recorded_at='2025-05-11T09:00:00', timezone='Undocumented/Place')
        row = parse(raw([r]), 'x.json')['rows'][0]
        self.assertEqual(row['record'], r)
        self.assertFalse(row['errors'])
        self.assertTrue(any('时区' in w for w in row['warnings']))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_preview_writes_nothing_and_import_is_persistent_idempotent(self):
        content = (ROOT / 'examples/messages.json').read_bytes()
        self.assertTrue(self.store.preview(content,'x.json')['can_import'])
        self.assertEqual(self.store.messages(), [])
        self.assertEqual(self.store.batches(), [])
        first = self.store.import_file(content,'x.json')
        self.assertEqual(first['added'], 6)
        self.assertEqual(self.store.import_file(content,'renamed.json')['added'], 0)
        reopened = Store(self.temp.name)
        self.assertEqual(len(reopened.messages()), 6)
        self.assertEqual(reopened.original(first['batch_id']), content)
        self.assertFalse(reopened.preview(content,'x.json')['can_import'])

    def test_invalid_batch_and_conflict_are_atomic(self):
        self.store.import_file(raw([message()]),'a.json')
        for content in [raw([message(id='new'), message(text='changed')]),
                        raw([message(id='new'), message(id='bad', role='human')])]:
            self.assertFalse(self.store.preview(content,'b.json')['can_import'])
            with self.assertRaises(ImportProblem): self.store.import_file(content,'b.json')
        self.assertEqual(len(self.store.messages()),1)
        self.assertEqual(len(self.store.batches()),1)
        self.assertEqual(self.store.messages()[0]['record']['text'], message()['text'])

    def test_identity_keeps_source_conversation_and_branch_separate(self):
        records = [message(), message(branch_id='alternative'), message(branch_id=None),
                   message(source_id='other'), message(conversation_id='other')]
        self.store.import_file(raw(records),'x.json')
        self.assertEqual(len(self.store.messages()),5)
        self.assertEqual(len(self.store.messages(source='fiction',branch='alternative')),1)
        self.assertEqual(len(self.store.messages(branch='')),1)

    def test_duplicate_messages_keep_all_original_locations(self):
        a = self.store.import_file(raw([message(),message()]),'a.json')
        b = self.store.import_file(raw([message()], synthetic=True),'b.json')
        self.assertEqual(a['added'],1)
        self.assertEqual(b['added'],0)
        detail = self.store.detail(self.store.messages()[0]['key'])
        self.assertEqual(len(detail['origins']),3)
        self.assertEqual({o['locator']['json_pointer'] for o in detail['origins']}, {'/messages/0','/messages/1'})

    def test_search_is_literal_multiscript_not_semantic_or_sql(self):
        self.store.import_file(raw([message()]),'x.json')
        for query in ['松湾','eVIDence','вчера','100%','_']:
            self.assertEqual(len(self.store.messages(query)),1)
        for query in ['研究室',"' OR 1=1 --",'yesterday']:
            self.assertEqual(self.store.messages(query),[])

    def test_rebuild_recovers_index_without_changing_originals(self):
        content = raw([message()])
        batch = self.store.import_file(content,'x.json')['batch_id']
        before = self.store.detail(self.store.messages()[0]['key'])
        with self.store.connect() as db: db.execute('DELETE FROM search_index')
        self.assertEqual(self.store.messages('松湾'),[])
        self.assertEqual(self.store.rebuild()['indexed'],1)
        self.assertEqual(len(self.store.messages('松湾')),1)
        self.assertEqual(self.store.detail(before['key']), before)
        self.assertEqual(self.store.original(batch), content)

    def test_batch_removal_keeps_shared_sources_then_removes_all_and_stays_removed(self):
        a = self.store.import_file(raw([message()]),'a.json')['batch_id']
        b = self.store.import_file(raw([message()],synthetic=True),'b.json')['batch_id']
        self.assertEqual(self.store.remove_batch(a)['removed_messages'],0)
        with self.assertRaises(KeyError): self.store.original(a)
        self.assertEqual(len(self.store.detail(self.store.messages()[0]['key'])['origins']),1)
        removed = self.store.remove_batch(b)
        self.assertEqual(removed['removed_messages'],1)
        self.assertTrue(removed['original_removed'])
        self.assertEqual(removed['remaining_index_entries'],0)
        self.assertEqual(Store(self.temp.name).rebuild()['indexed'],0)
        self.assertEqual(self.store.messages('松湾'),[])
        self.assertEqual(self.store.batches(),[])

    def test_pending_contracts_round_trip_without_becoming_active(self):
        record = message(event_time_note={'text':'昨天','source_message_id':'m1'},
                         provenance={'note':'invented'}, extra_future_field={'preserve':True})
        correction = {'id':'c1','scope':'topical','target_message_ids':['m1'],'supersedes':None,
                      'statement':'fictional correction','source_message_id':'m1'}
        content = raw([record], corrections=[correction], observations=[{'text':'uncertain inference'}])
        preview = self.store.preview(content,'x.json')
        self.assertEqual(preview['extensions']['corrections'],[correction])
        batch = self.store.import_file(content,'x.json')['batch_id']
        self.assertEqual(self.store.detail(self.store.messages()[0]['key'])['record'],record)
        self.assertEqual(self.store.original(batch),content)
        self.assertEqual(len(self.store.messages()),1)  # no inferred memory or global preference

    def test_separate_profiles_do_not_share_records(self):
        self.store.import_file(raw([message()]),'x.json')
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(Store(other).messages(),[])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(self.temp.name)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join,2)
        self.addCleanup(self.server.shutdown)
        self.token = self.request('GET','/api/session')[1]['token']

    def request(self, method, path, body=None, headers=None):
        conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        request_headers={'Content-Type':'application/json','X-Continuity-Token':getattr(self,'token','')}
        request_headers.update(headers or {})
        conn.request(method,path,None if body is None else json.dumps(body),request_headers)
        response=conn.getresponse()
        data=response.read()
        status=response.status
        conn.close()
        try: data=json.loads(data)
        except (ValueError,UnicodeError): pass
        return status,data

    def test_complete_http_import_source_search_delete(self):
        content=raw([message()])
        payload={'filename':'x.json','data':base64.b64encode(content).decode()}
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertTrue(self.request('POST','/api/preview',payload)[1]['can_import'])
        batch=self.request('POST','/api/import',payload)[1]['batch_id']
        messages=self.request('GET','/api/messages?q=evidence')[1]['messages']
        key=messages[0]['key']
        detail=self.request('GET','/api/messages/'+key)[1]
        self.assertEqual(detail['record'],message())
        # Original JSON response is decoded by this test helper; store tests check exact bytes.
        self.assertEqual(self.request('GET','/api/original/'+batch)[1],json.loads(content))
        self.assertTrue(self.request('POST','/api/remove-batch',{'batch_id':batch})[1]['original_removed'])
        self.assertEqual(self.request('GET','/api/messages/'+key)[0],404)
        self.assertEqual(self.request('GET','/api/original/'+batch)[0],404)
        self.assertEqual(self.request('POST','/api/rebuild',{})[1]['indexed'],0)

    def test_cross_origin_host_and_missing_token_are_rejected(self):
        self.assertEqual(self.request('POST','/api/rebuild',{}, {'Origin':'https://elsewhere.invalid'})[0],403)
        self.assertEqual(self.request('POST','/api/rebuild',{}, {'X-Continuity-Token':''})[0],403)
        self.assertEqual(self.request('GET','/api/session',headers={'Host':'elsewhere.invalid'})[0],403)
        self.assertEqual(self.request('GET','/../../README.md')[0],404)

    def test_invalid_payload_and_missing_batch_fail_cleanly(self):
        self.assertEqual(self.request('POST','/api/import',{'filename':'x.json','data':'!!!'})[0],400)
        self.assertEqual(self.request('POST','/api/import',[])[0],400)
        self.assertEqual(self.request('POST','/api/remove-batch',{'batch_id':'absent'})[0],404)

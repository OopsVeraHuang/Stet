"""Synthetic exports only. No private transcripts or provider accounts."""
import io
import json
import tempfile
import unittest
import zipfile
from continuity.importing import parse, ImportProblem
from continuity.store import Store


def raw(value):
    return json.dumps(value,ensure_ascii=False).encode()


def graph():
    return [{'id':'synthetic-chat','title':'Fictional meeting','current_node':'a2','mapping':{
        'root':{'parent':None,'message':None},
        'u':{'parent':'root','message':{'id':'u','author':{'role':'user'},'create_time':1735689600,
             'content':{'parts':['研究笔记 · Привет']}}},
        'a1':{'parent':'u','message':{'id':'a1','author':{'role':'assistant'},'create_time':1735693200,
              'content':{'parts':['First branch']},'metadata':{'model_slug':'synthetic-model'}}},
        'a2':{'parent':'u','message':{'id':'a2','author':{'role':'assistant'},'content':{'parts':['Alternate branch',{'content_type':'image_asset_pointer','asset_pointer':'synthetic'}]}}}
    }}]


class NativeImportTests(unittest.TestCase):
    def test_chatgpt_branches_roles_and_times(self):
        result=parse(raw(graph()),'conversations.json')
        rows=[x['record'] for x in result['rows']]
        self.assertEqual(len(rows),4)
        self.assertEqual([r['text'] for r in rows if r['branch_id']=='a1'],['研究笔记 · Привет','First branch'])
        self.assertEqual(rows[0]['recorded_at'],'2025-01-01T00:00:00+00:00')
        self.assertIsNone(rows[-1]['recorded_at'])
        self.assertEqual(rows[1]['native_metadata']['model_id'],'synthetic-model')
        self.assertEqual(result['extensions']['native_import']['omissions']['unsupported_content_block'],1)
    def test_zip_originals_idempotence_and_locator(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('../conversations.json',raw(graph()))
            z.writestr('ignored-image.png',b'synthetic-not-an-image')
        original=b.getvalue()
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);self.assertTrue(store.preview(original,'export.zip')['can_import'])
            self.assertEqual(store.batches(),[])
            result=store.import_file(original,'export.zip')
            self.assertEqual(store.original(result['batch_id']),original)
            self.assertTrue(store.import_file(original,'export.zip')['already_imported'])
            detail=store.detail(store.messages()[0]['key'])
            self.assertEqual(detail['origins'][0]['locator']['zip_member'],'../conversations.json')
            # ZIP path is a locator only; never extracted as a filesystem path.
            self.assertIn('json_pointer',detail['origins'][0]['locator'])
    def test_claude_text_blocks_unknown_time_and_media_warning(self):
        data=[{'uuid':'synthetic-c','name':'Synthetic','chat_messages':[
            {'uuid':'m','sender':'human','text':'中文原话','created_at':None,'attachments':[{'id':'fake'}]},
            {'uuid':'n','sender':'assistant','content':[{'type':'text','text':'Original answer'}]}]}]
        p=parse(raw(data),'conversations.json')
        self.assertEqual([x['record']['role'] for x in p['rows']],['user','assistant'])
        self.assertIsNone(p['rows'][0]['record']['recorded_at'])
        self.assertIsNone(p['rows'][0]['record']['branch_id'])
        self.assertEqual(p['extensions']['native_import']['omissions']['attachments_not_imported'],1)
    def test_studio_and_takeout_do_not_invent_replies(self):
        studio={'chunkedPrompt':{'chunks':[{'role':'user','text':'Question'},{'role':'model','text':'Answer'}]}}
        p=parse(raw(studio),'prompt.json');self.assertEqual(p['rows'][1]['record']['role'],'assistant')
        takeout=[{'products':['Gemini Apps'],'title':'Prompted synthetic question','time':'2025-01-01T10:00:00Z'},
                 {'products':['Gemini Apps'],'title':'Unspecified activity','time':'2025-01-01T12:00:00Z'}]
        p=parse(raw(takeout),'MyActivity.json')
        self.assertEqual(len(p['rows']),2)
        self.assertEqual([r['record']['role'] for r in p['rows']],['user','unknown'])
        self.assertNotEqual(p['rows'][0]['record']['conversation_id'],p['rows'][1]['record']['conversation_id'])
    def test_broken_graph_and_unknown_format_rejected(self):
        for value in [graph(),graph(),[{'random':'unknown'}]]:
            if 'mapping' in value[0]:
                value[0]['mapping']['u']['parent']='a1'
            with self.assertRaises(ImportProblem):parse(raw(value),'export.json')
        g=graph();g[0]['mapping']['u']['message']['author']=12
        with self.assertRaises(ImportProblem):parse(raw(g),'export.json')
    def test_multiple_zip_candidates_rejected(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('a/conversations.json',raw(graph()));z.writestr('b/conversations.json',raw(graph()))
        with self.assertRaises(ImportProblem):parse(b.getvalue(),'export.zip')

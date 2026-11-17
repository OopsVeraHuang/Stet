"""Public synthetic integration checks. No credentials, network or paid generation."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import server as api
import platform_import
import efficiency

def epub():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('mimetype','application/epub+zip')
        z.writestr('META-INF/container.xml','<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('content.opf','<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">synthetic</dc:identifier><dc:title>Synthetic book</dc:title><dc:language>en</dc:language></metadata><manifest><item id="a" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/></spine></package>')
        z.writestr('chapter.xhtml','<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter one</title></head><body><h1>Chapter one</h1><p>We study memory in a fictional library.</p></body></html>')
    return out.getvalue()

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        api.configure_profile(Path(self.tmp.name)/'profile')
        api.init_state(); api.JOBS.clear();api.KEY=None
        self.no_network=patch.object(api,'google',side_effect=AssertionError('Unexpected network call'))
        self.no_network.start()
    def tearDown(self):
        self.no_network.stop();self.tmp.cleanup()
    def add_chat(self,text,role='user'):
        with api.state_db() as db:
            return db.execute('INSERT INTO chat(role,text,time,refs,job_id) VALUES(?,?,?,?,?)',
                (role,text,api.now(),'[]','synthetic')).lastrowid
    def load(self):
        raw=(ROOT/'examples/messages.json').read_bytes()
        result=platform_import.store(api).import_file(raw,'messages.json')
        platform_import.rebuild(api)
        return raw,result
    def test_import_recall_source_and_removal(self):
        raw,_=self.load()
        original=platform_import.store(api)
        rows=original.messages('松湾')
        self.assertEqual(len(rows),2)
        ids={r['key'] for r in rows}
        _,items=api.chat_payload('松湾',[],api.config())
        self.assertTrue(ids & {x['id'] for x in items})
        for item in rows:
            self.assertEqual(api.get_paragraph(item['key'])['raw_text'],item['record']['text'])
            self.assertTrue(all(n['source_id']==api.get_paragraph(item['key'])['source_id'] for n in api.context(item['key'])))
        bid=original.batches()[0]['id']
        self.assertEqual(raw,original.original(bid))
        original.remove_batch(bid);platform_import.rebuild(api)
        self.assertEqual(api.automatic_recall('松湾',[]),[])
    def test_independent_profile_no_paid_defaults_or_location_seed(self):
        self.load();self.add_chat('Synthetic profile A')
        api.configure_profile(Path(self.tmp.name)/'second');api.init_state()
        self.assertFalse(api.config()['paid_enabled'])
        self.assertFalse(api.config()['auto_corrections'])
        self.assertEqual(platform_import.store(api).messages(),[])
        with api.state_db() as db:self.assertEqual(db.execute('SELECT count(*) FROM chat').fetchone()[0],0)
        self.assertEqual(api.persona.profile(api.ARCHIVE)['examples'],[])
    def test_chat_tool_loop_persists_and_measures_each_call(self):
        self.load();api.save_config({'paid_enabled':True})
        job='synthetic-tool-loop';api.JOBS[job]={'status':'running'}
        def response(parts):
            return {'candidates':[{'content':{'role':'model','parts':parts},'finishReason':'STOP'}],
                    'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':10}}
        results=[response([{'functionCall':{'name':'search_memory','args':{'query':'松湾'}}}]),
                 response([{'text':'Synthetic answer with a source.'}])]
        with patch.object(api,'google',side_effect=results) as generate, patch.object(api,'brain_key',return_value='synthetic-test-only'):
            result=api.run_chat_with_client(job,{'text':'松湾的记录是什么？','refs':[]},None)
        self.assertEqual(generate.call_count,2)
        self.assertIn('Synthetic answer',result['reply'])
        with api.state_db() as db:self.assertEqual(db.execute('SELECT count(*) FROM chat').fetchone()[0],2)
        measurements=efficiency.report(api)
        self.assertEqual(len(measurements),2)
        self.assertEqual(measurements[0]['metrics']['unit'],'characters_not_tokens')
    def test_notes_same_recall_and_withdrawal(self):
        cid=self.add_chat('A synthetic sentence about violet lanterns.','assistant')
        note=api.study.collect(api,cid)
        note=api.study.change(api,{'id':note['id'],'revision':1,'action':'annotate','start':0,'end':1,'kind':'comment','comment':'synthetic annotation'})
        pid='study:'+str(note['id'])
        self.assertIn('synthetic annotation',api.get_paragraph(pid)['raw_text'])
        self.assertTrue(any(x['id']==pid for x in api.automatic_recall('synthetic annotation',[])))
        api.study.change(api,{'id':note['id'],'revision':note['revision'],'action':'trash'})
        with self.assertRaises(ValueError):api.get_paragraph(pid)
    def test_note_search_comments_unicode_pagination_and_trash(self):
        for i in range(52):
            cid=self.add_chat(f'Привет {i} · 100%_','assistant');api.study.collect(api,cid)
        page=api.study.listing(api,query='ПРИВЕТ')
        self.assertEqual(len(page['items']),50);self.assertTrue(page['has_more'])
        older=api.study.listing(api,before=page['items'][-1]['id'],query='привет')
        self.assertEqual(len(older['items']),2);self.assertFalse(older['has_more'])
        note=page['items'][0]
        changed=api.study.change(api,{'id':note['id'],'revision':note['revision'],'action':'annotate','start':0,'end':1,'kind':'comment','comment':'中文检索证据'})
        self.assertEqual([n['id'] for n in api.study.listing(api,query='检索')['items']],[note['id']])
        api.study.change(api,{'id':note['id'],'revision':changed['revision'],'action':'trash'})
        self.assertEqual(api.study.listing(api,query='检索')['items'],[])
        self.assertEqual(len(api.study.listing(api,deleted=True,query='检索')['items']),1)
        self.assertEqual(len(api.study.listing(api,query='%_')['items']),50)
        self.assertEqual(api.study.listing(api,query="' OR 1=1 --")['items'],[])
    def test_library_versions_preserve_original(self):
        r=api.library.edit(api,{'name':'synthetic.md','text':'version one'})
        api.library.edit(api,{'id':r['id'],'base_version':1,'text':'version two'})
        self.assertEqual(api.library.read(api,r['id'],1)['text'],'version one')
        self.assertEqual(api.library.read(api,r['id'])['text'],'version two')
        with self.assertRaises(ValueError):api.library.edit(api,{'id':r['id'],'base_version':1,'text':'stale'})
    def test_epub_reading_preserves_original(self):
        raw=epub();r=api.reader.upload(api,{'name':'synthetic.epub','data':base64.b64encode(raw).decode()})
        self.assertIn('fictional library',api.reader.read(api,r['id'],1)['text'])
        self.assertEqual(api.reader.path_for(api,r).read_bytes(),raw)
    def test_correction_source_revoke_does_not_reactivate(self):
        text='请记住：这个例子中的图书馆在松湾。'
        cid=self.add_chat(text)
        c=api.corrections.save_from_chat(api,cid,'合成地点纠正',text)
        api.corrections.change(api,c['id'],'revoked')
        self.assertEqual(api.corrections.save_from_chat(api,cid,'重试',text)['status'],'revoked')
        with self.assertRaises(ValueError):api.corrections.save_from_chat(api,cid,'无依据','这是一段模型捏造的纠正')
    def test_metadata_compaction_does_not_drop_original_or_false(self):
        self.assertEqual(efficiency.compact({'raw_text':'原文','zero':0,'false':False,'empty':[],'unknown':None}),
                         {'raw_text':'原文','zero':0,'false':False})
    def test_partial_config_preserves_payment_choice(self):
        api.save_config({'paid_enabled':True})
        api.save_config({'auto_corrections':True})
        self.assertTrue(api.config()['paid_enabled'])

if __name__=='__main__':unittest.main()

import sys, unittest, datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference_core'))
import context_policy as c
import recall
import temporal

class ReferenceTests(unittest.TestCase):
    def test_fusion_rewards_both_channels(self):
        a={'id':'a','raw_text':'one'};b={'id':'b','raw_text':'two'}
        self.assertEqual(recall.fuse([a,b],[b])[0]['id'],'b')
    def test_fusion_deduplicates_text(self):
        self.assertEqual(len(recall.fuse([{'id':'a','raw_text':'same'}],[{'id':'b','raw_text':'same'}])),1)
    def test_recent_retains_user_anchor(self):
        rows=[{'id':i,'role':'assistant' if i%2==0 else 'user','text':'sample','time':'2026-01-01T00:00:00Z'} for i in range(12,0,-1)]
        self.assertEqual(len(c.recent(rows)),6)
        self.assertEqual(len(c.recent(rows,'继续')),12)
        self.assertEqual(c.recent(rows)[0]['role'],'user')
    def test_unknown_time_stays_unknown(self):
        self.assertEqual(temporal.describe(None)['precision'],'unknown')
    def test_week_is_calendar_week(self):
        now=dt.datetime(2026,10,23,tzinfo=temporal.BEIJING)
        self.assertEqual(c.date_range('上周',now),(dt.date(2026,10,12),dt.date(2026,10,19)))
    def test_date_priority_keeps_unknown(self):
        rows=[{'id':'unknown','timestamp':None},{'id':'dated','timestamp':'2026-10-22T00:00:00+08:00'}]
        out=c.date_priority(rows,'昨天',dt.datetime(2026,10,23,tzinfo=temporal.BEIJING))
        self.assertEqual([x['id'] for x in out],['dated','unknown'])
    def test_cross_script_keeps_cosine_order(self):
        rows=[{'id':'a','raw_text':'reading papers','retrieval':{'score':.8}}, {'id':'b','raw_text':'dinner','retrieval':{'score':.6}}]
        self.assertEqual(recall.semantic_candidates('读论文',rows)[0]['id'],'a')
    def test_cyrillic_terms_are_retained(self):
        self.assertIn('книгу',recall.terms('Я читаю книгу'))

if __name__=='__main__':unittest.main()

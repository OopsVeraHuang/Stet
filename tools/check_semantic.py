"""Optional real-model smoke check using only synthetic text; not a quality benchmark."""
import os
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import server as api
import platform_import
import semantic_memory

def main():
    if not os.environ.get('CONTINUITY_SEMANTIC_MODEL'):raise SystemExit('Set CONTINUITY_SEMANTIC_MODEL first')
    with tempfile.TemporaryDirectory() as tmp:
        api.configure_profile(Path(tmp));api.init_state()
        encoder=semantic_memory.Encoder(os.environ['CONTINUITY_SEMANTIC_MODEL'])
        index=semantic_memory.Index(api,encoder)
        raw=api.dump({'messages':[
            {'id':'a','source_id':'synthetic','conversation_id':'c','role':'user','text':'我每个星期日都去图书馆阅读一本新书。'},
            {'id':'b','source_id':'synthetic','conversation_id':'c','role':'user','text':'The yellow submarine crossed the empty ocean.'}
        ]}).encode()
        original=platform_import.store(api);original.import_file(raw,'synthetic.json');platform_import.rebuild(api)
        index.build()
        for query in ['每周日到图书馆看书','I read a new book in the library every Sunday.','Каждое воскресенье я читаю новую книгу в библиотеке.']:
            hits=index.search(query,4,())
            assert hits and '星期日' in api.get_paragraph(hits[0]['id'])['raw_text'],(query,hits)
        bid=original.batches()[0]['id'];original.remove_batch(bid);platform_import.rebuild(api);index.build()
        assert index.search('library every Sunday',4,())==[]
        print('PASS: real CPU encoder; Chinese/English/Russian synthetic recall and deleted-index cleanup. No model API.')
if __name__=='__main__':main()

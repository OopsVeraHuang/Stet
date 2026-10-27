"""Launch an isolated synthetic UI test server. Never used by the normal launcher."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'));sys.path.insert(0,str(ROOT/'tests'))
import server as api
import platform_import
from test_platform import epub
import base64
import json
args,_=argparse.ArgumentParser().parse_known_args()
profile=Path(sys.argv[sys.argv.index('--data-dir')+1])
api.configure_profile(profile);api.init_state()
api.reader.upload(api,{'name':'Synthetic reader.epub','data':base64.b64encode(epub()).decode()})
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import io
writer=PdfWriter();page=writer.add_blank_page(400,500)
font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
stream=DecodedStreamObject();stream.set_data(b'BT /F1 16 Tf 40 420 Td (Synthetic PDF reading check.) Tj ET')
page[NameObject('/Contents')]=writer._add_object(stream)
out=io.BytesIO();writer.write(out)
api.reader.upload(api,{'name':'Synthetic paper.pdf','data':base64.b64encode(out.getvalue()).decode()})
with api.state_db() as db:
    for role,text in [('user','[合成演示] 请解释图书馆里的观察。'),('assistant','[合成演示，非模型生成] **原件与解释分开保存**，才能核对证据。')]:
        db.execute('INSERT INTO chat(role,text,time,refs,job_id) VALUES(?,?,?,?,?)',(role,text,api.now(),'[]','synthetic-ui'))
doc=api.library.edit(api,{'name':'Synthetic attachment.md','text':'A fictional reading note.'})
with api.state_db() as db:
    db.execute('UPDATE chat SET documents=? WHERE id=1',(json.dumps([{'id':doc['id'],'version':doc['version']}]),))
api.main()

"""Explicit public-weight download. Fixed revision and SHA-256; no model API.

Run only when choosing local semantic retrieval; weights remain outside Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination',default=str(ROOT/'.local/models/multilingual-minilm'))
    args=p.parse_args();dest=Path(args.destination).resolve()
    manifest=json.loads((ROOT/'examples/semantic-model.json').read_text())
    dest.mkdir(parents=True,exist_ok=True)
    for name,expected in manifest['files'].items():
        target=dest/name
        if not target.resolve().is_relative_to(dest):raise ValueError('Unsafe model path')
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('Existing file differs: '+name)
            print('Verified',name);continue
        url=f"https://huggingface.co/{manifest['repo']}/resolve/{manifest['revision']}/{name}"
        with urllib.request.urlopen(url,timeout=120) as r:raw=r.read(150*1024*1024)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Download hash mismatch: '+name)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);print('Downloaded and verified',name)
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Set CONTINUITY_SEMANTIC_MODEL to:',dest)
if __name__=='__main__':main()

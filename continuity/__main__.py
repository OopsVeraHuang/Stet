from pathlib import Path
import runpy
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'app'))
runpy.run_path(str(root / 'app' / 'server.py'), run_name='__main__')

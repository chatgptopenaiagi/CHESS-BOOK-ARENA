from pathlib import Path
from app.database_readers.reader_registry import open_reader
import os,json,time
p=Path(os.environ['USERPROFILE']) # exact actual resolved Documents path stored privately by PowerShell
entry=Path(json.loads(Path('evidence/mega-path.private.json').read_text()))
t=time.perf_counter()
with open_reader(entry) as r:
    info=r.metadata();print(info); rows=list(r.enumerate(1,20)); print([(x['id'],len(list(x['game'].mainline_moves()))) for x in rows if 'game' in x]); print('seconds',time.perf_counter()-t)

import json,time,io,random,hashlib,os
from pathlib import Path
from app.database_readers.reader_registry import open_reader
from app.catalog import Catalog
from app.engine_manager import EngineRegistry
entry=Path(json.loads(Path('evidence/mega-path.private.json').read_text())); start=time.perf_counter()
before={str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in entry.parent.glob(entry.stem+'.*') if p.is_file()}
rows=[];errors=[];special={'annotations':[],'variations':[],'nonstandard':[]}; rng=random.Random(20261116)
with open_reader(entry) as r:
    info=r.metadata();ids=[1,2,3,114,10856403,info.records//2,info.records-1,info.records]+[rng.randint(3,info.records) for _ in range(100)]
    for identifier in ids:
        try:
            row=r.game(identifier);g=row['game'];rows.append(dict(id=identifier,headers=dict(g.headers),plies=len(list(g.mainline_moves()))))
            stack=[g];annotations=False;variations=False
            while stack:
                n=stack.pop();annotations|=bool(n.comment or n.nags);variations|=len(n.variations)>1;stack.extend(n.variations)
            if annotations:special['annotations'].append(identifier)
            if variations:special['variations'].append(identifier)
            if g.headers.get('SetUp')=='1':special['nonstandard'].append(identifier)
        except Exception as e:errors.append(dict(id=identifier,error=str(e)))
path=Path('private');path.mkdir(exist_ok=True)
c=Catalog(path/'mega-index-v6.sqlite');sid=c.open_native(entry);t=time.perf_counter();c.index_native(sid,2000);elapsed=time.perf_counter()-t
stats=c.stats(sid)
with c.db() as db:decode_errors=[dict(x) for x in db.execute('SELECT * FROM decode_errors')]
report=dict(info=info.__dict__,rows=rows,errors=errors,special=special,sampled_seconds=time.perf_counter()-start,index=dict(records_requested=2000,seconds=elapsed,stats=stats,size_bytes=Path(c.path).stat().st_size,decode_errors=decode_errors),source_unchanged=before=={str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in entry.parent.glob(entry.stem+'.*') if p.is_file()})
Path('evidence/mega-validation.private.json').write_text(json.dumps(report,indent=2));print('Sample decoded',len(rows),'sample errors',len(errors),'special',special,'index seconds',elapsed,'stats',stats,'index errors',len(decode_errors))
e=EngineRegistry(path/'engines.json');print('Engine candidates:',[p.name for p in e.candidates()]);
for p in e.candidates():
    try:print('Verified engine:',e.add(p)['name'])
    except Exception as ex:print('Engine probe failure:',str(ex))

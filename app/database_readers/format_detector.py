from pathlib import Path
CBH_REQUIRED=['.cbh','.cbg','.cba','.cbp','.cbt','.cbc','.cbs']
CBH_OPTIONAL=['.cbb','.cbe','.cbj','.cbgi','.cbl','.cbm','.flags','.cbtt']
COMPONENTS=set(CBH_REQUIRED[1:]+CBH_OPTIONAL+['.ctb','.cto','.sg4','.sn4'])
def family(path):
    p=Path(path); suffix=p.suffix.lower()
    required=CBH_REQUIRED if suffix=='.cbh' else ['.2cbh','.2cbg','.2lid'] if suffix=='.2cbh' else ['.ctg','.ctb','.cto'] if suffix=='.ctg' else ['.si4','.sg4','.sn4'] if suffix=='.si4' else [suffix]
    siblings={x.suffix.lower():x for x in p.parent.glob(p.stem+'.*') if x.stem.casefold()==p.stem.casefold() and x.is_file()}
    found=[v for v in siblings.values()]; missing=[x for x in required if x not in siblings]
    return dict(entry=p,found=found,missing=missing,size=sum(x.stat().st_size for x in found),signature=[(x.name,x.stat().st_size,x.stat().st_mtime_ns) for x in sorted(found)])
def entrypoint(path):
    p=Path(path); s=p.suffix.lower()
    if s in COMPONENTS:
        root='.si4' if s in ['.sg4','.sn4'] else '.ctg' if s in ['.ctb','.cto'] else '.cbh'
        q=p.with_suffix(root)
        return q if q.exists() else None
    return p

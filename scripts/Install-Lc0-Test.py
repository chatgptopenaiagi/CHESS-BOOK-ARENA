from pathlib import Path
from app.engine_manager import EngineRegistry
r=EngineRegistry('private/engine-download/engines.json')
a=next(a for a in r.releases('Leela Chess Zero') if 'cpu-openblas' in a['name']);print('Installing official CPU asset',a['name'],flush=True)
paths=r.install(a)
for p in paths:print('UCI verification',r.add(p)['name'],flush=True)

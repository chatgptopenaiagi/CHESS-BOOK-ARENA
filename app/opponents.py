import random, shutil, os
from dataclasses import dataclass
from pathlib import Path
import chess, chess.engine

@dataclass
class Decision:
    move: chess.Move | None
    origin: str
    reason: str

class Engine:
    def __init__(self,path='',seconds=.3,depth=16,threads=1,hash_mb=64,elo=0,multipv=3,options=None):
        self.path=path; self.seconds=seconds; self.depth=depth; self.threads=threads; self.hash_mb=hash_mb; self.elo=elo; self.multipv=multipv; self.options=options or {}
    def open(self):
        e=chess.engine.SimpleEngine.popen_uci(self.path,timeout=10)
        opts={}
        for name,value in [('Threads',self.threads),('Hash',self.hash_mb),('UCI_LimitStrength',bool(self.elo)),('UCI_Elo',self.elo)]:
            if name in e.options and (name!='UCI_Elo' or self.elo):
                o=e.options[name]; opts[name]=max(o.min,min(o.max,value)) if isinstance(value,int) and not isinstance(value,bool) and o.min is not None else value
        opts.update({k:v for k,v in self.options.items() if k in e.options and not e.options[k].is_managed()})
        try:e.configure(opts)
        except Exception:e.close();raise
        return e
    def analyse(self,b,candidates=None):
        with self.open() as e:
            count=min(self.multipv,len(candidates) if candidates else b.legal_moves.count())
            if 'MultiPV' in e.options and e.options['MultiPV'].max:count=min(count,e.options['MultiPV'].max)
            info=e.analyse(b,chess.engine.Limit(time=self.seconds,depth=self.depth),multipv=count if 'MultiPV' in e.options else None,root_moves=candidates)
            return info if isinstance(info,list) else [info]
    def move(self,b):
        with self.open() as e: return e.play(b,chess.engine.Limit(time=self.seconds,depth=self.depth)).move

def discover_engine():
    paths=[shutil.which('stockfish'),os.environ.get('CHESS_ARENA_ENGINE')]
    candidate=next((p for p in paths if p and Path(p).is_file()),'')
    if candidate:return candidate
    from app.engine_manager import EngineRegistry
    registry=EngineRegistry(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'ChessBookArena'/'engines.json')
    found=registry.candidates();return str(found[0]) if found else ''

class ChessOpponent:
    def choose(self,board): raise NotImplementedError
class HistoricalDatabaseOpponent(ChessOpponent):
    def __init__(self,catalog,sid,strategy='Frequency',player='',engine=None,filters=None):
        self.catalog=catalog; self.sid=sid; self.strategy=strategy; self.player=player; self.engine=engine; self.filters=filters or {}
    def choose(self,b):
        rows=self.catalog.candidates(self.sid,b,self.player,self.filters)
        if not rows: return Decision(None,'coverage ended','No legal continuation in the selected repertoire')
        if self.strategy=='Engine assisted':
            if not self.engine or not self.engine.path: raise ValueError('Select a UCI engine for engine-assisted selection')
            info=self.engine.analyse(b,[chess.Move.from_uci(r['uci']) for r in rows]); uci=info[0]['pv'][0].uci(); row=next(r for r in rows if r['uci']==uci)
        elif self.strategy=='Weighted random': row=random.choices(rows,weights=[max(1,r['n']) for r in rows])[0]
        elif self.strategy=='Exploration': row=min(rows,key=lambda r:r['n'])
        elif self.strategy=='Performance': row=max(rows,key=lambda r:(r['w']+.5*r['d'])/max(1,r['w']+r['d']+r['l']))
        else: row=max(rows,key=lambda r:r['n'])
        return Decision(chess.Move.from_uci(row['uci']),row['source']+f' #{self.sid}',f"{self.strategy}; {row['n']} recorded occurrences / weight"+(' (engine ranked historical candidates)' if self.strategy=='Engine assisted' else ''))
class OpeningBookOpponent(HistoricalDatabaseOpponent): pass
class HistoricalPlayerOpponent(HistoricalDatabaseOpponent): pass
class EngineOpponent(ChessOpponent):
    def __init__(self,engine): self.engine=engine
    def choose(self,b): return Decision(self.engine.move(b),'engine '+Path(self.engine.path).stem,'UCI search')
class HybridBookEngineOpponent(ChessOpponent):
    def __init__(self,book,engine,fallback='Stop',alternate=None): self.book=book; self.engine=engine; self.fallback=fallback; self.alternate=alternate
    def choose(self,b):
        d=self.book.choose(b)
        if d.move: return d
        if self.fallback=='Engine': return Decision(self.engine.move(b),'engine fallback','Selected repertoire exhausted; UCI search')
        if self.fallback=='Alternate' and self.alternate:
            d=self.alternate.choose(b); d.origin='alternate '+d.origin
        return d

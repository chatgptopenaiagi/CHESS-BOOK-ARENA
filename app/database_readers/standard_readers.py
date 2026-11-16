import gzip,io
from pathlib import Path
import chess,chess.pgn,chess.polyglot
from .reader_interface import Capabilities,DatabaseInfo
class PgnReader:
    capabilities=Capabilities(annotations=True,native_headers=True)
    def __init__(self,path):self.path=Path(path)
    def enumerate(self,first=1,count=100):
        op=gzip.open if self.path.name.lower().endswith('.gz') else open
        with op(self.path,'rt',encoding='utf-8-sig',errors='replace') as f:
            i=0
            while (g:=chess.pgn.read_game(f)) is not None:
                i+=1
                if i<first:continue
                if i>=first+count:break
                if g.errors:yield dict(id=i,error=str(g.errors));continue
                yield dict(id=i,game=g,pgn=str(g))
    def game(self,identifier):
        rows=list(self.enumerate(identifier,1))
        if not rows:raise ValueError('Game not found')
        if 'error' in rows[0]:raise ValueError(rows[0]['error'])
        return rows[0]
    def metadata(self):return DatabaseInfo('.pgn.gz' if self.path.name.endswith('.gz') else '.pgn','python-chess','READ-ONLY SUPPORTED',size=self.path.stat().st_size,detail='Streaming; game counts available after catalog indexing')
    def close(self):pass
class PolyglotReader:
    capabilities=Capabilities(random_access=True)
    def __init__(self,path):self.path=Path(path);self.book=chess.polyglot.open_reader(path)
    def continuations(self,board):return [e for e in self.book.find_all(board) if e.move in board.legal_moves]
    def metadata(self):return DatabaseInfo('.bin','python-chess Polyglot','READ-ONLY SUPPORTED',size=self.path.stat().st_size,detail='Position lookup; no game collection')
    def close(self):self.book.close()
class PositionReader:
    capabilities=Capabilities()
    def __init__(self,path):self.path=Path(path)
    def positions(self):
        with self.path.open(encoding='utf-8-sig') as f:
            for line in f:
                if not line.strip():continue
                b=chess.Board()
                if self.path.suffix.lower()=='.epd':b.set_epd(line.strip())
                else:b.set_fen(line.strip())
                if not b.is_valid():raise ValueError('Invalid position')
                yield b
    def metadata(self):return DatabaseInfo(self.path.suffix,'python-chess positions','READ-ONLY SUPPORTED',size=self.path.stat().st_size,detail='Positions only; no game collection')
    def close(self):pass

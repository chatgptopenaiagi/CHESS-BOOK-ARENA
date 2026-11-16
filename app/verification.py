"""Acceptance uses synthetic, openly redistributable fixtures; no invented corpus claims."""
import gzip, io, struct, zipfile, json
from pathlib import Path
import chess, chess.pgn, chess.polyglot
from app.catalog import Catalog,key
from app.opponents import HistoricalDatabaseOpponent,HybridBookEngineOpponent,Engine,discover_engine
PGN='''[Event "Arena fixture"]
[White "Alice"]
[Black "Bob"]
[Date "2026.01.01"]
[Result "0-1"]
[ECO "A00"]

1. f3 e5 2. g4 Qh4# 0-1

[Event "Transposition A"]
[White "Alice"]
[Black "Carol"]
[Result "*"]

1. Nf3 Nf6 2. g3 g6 3. Bg2 *

[Event "Transposition B"]
[White "Dan"]
[Black "Bob"]
[Result "*"]

1. g3 g6 2. Nf3 Nf6 3. Bg2 *
'''
def fixtures(p):
    p=Path(p); p.mkdir(parents=True,exist_ok=True); (p/'fixture.pgn').write_text(PGN)
    with gzip.open(p/'fixture.pgn.gz','wt') as f:f.write(PGN)
    with zipfile.ZipFile(p/'fixture.zip','w') as z:z.writestr('games.pgn',PGN)
    b=chess.Board(); m=chess.Move.from_uci('e2e4'); raw=m.to_square|(m.from_square<<6)
    (p/'fixture.bin').write_bytes(struct.pack('>QHHI',chess.polyglot.zobrist_hash(b),raw,10,0))
    (p/'fixture.fen').write_text(b.fen()); (p/'fixture.epd').write_text(b.epd()+' id "start";')
    return p

def acceptance(p):
    p=fixtures(p); c=Catalog(p/'test.sqlite'); sid=c.import_file(p/'fixture.pgn'); b=chess.Board(); opp=HistoricalDatabaseOpponent(c,sid)
    trace=[]
    for uci in ['f2f3','g2g4']:
        m=chess.Move.from_uci(uci); assert m in b.legal_moves; trace.append({'move':b.san(m),'source':'human'}); b.push(m)
        d=opp.choose(b); assert d.move in b.legal_moves and d.origin.startswith('database'); trace.append({'move':b.san(d.move),'source':d.origin,'reason':d.reason}); b.push(d.move)
    assert b.is_checkmate(); save=c.save(b,{'mode':'database','origins':[x['source'] for x in trace]}); r=c.saves()[0]; game=chess.pgn.read_game(io.StringIO(r['pgn'])); assert game.end().board().is_checkmate()
    return dict(status='PASS',game=trace,result=b.result(),indexed_games=c.sources()[0]['games'],saved_id=save,engine_required=False)

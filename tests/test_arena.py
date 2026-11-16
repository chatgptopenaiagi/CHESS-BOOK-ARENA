import io, json, threading, os
import chess, chess.pgn
import pytest
from app.catalog import Catalog,key,discover
from app.opponents import *
from app.verification import fixtures,acceptance

@pytest.fixture
def env(tmp_path):
    fixtures(tmp_path); return tmp_path,Catalog(tmp_path/'c.sqlite')
@pytest.mark.parametrize('ext',['pgn','pgn.gz','bin','zip','fen','epd'])
def test_formats(env,ext):
    p,c=env; c.import_file(p/f'fixture.{ext}'); assert c.sources()[0]['status']=='ready'
def test_statistics(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); assert c.sources()[0]['games']==3
    rows=c.candidates(sid,chess.Board()); assert sum(x['n'] for x in rows)==3
    b=chess.Board(); b.push_uci('f2f3'); r=c.candidates(sid,b)[0]; assert r['uci']=='e7e5' and r['w']==1
    assert c.stats(sid)['entries']==14

def test_transposition(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); a=chess.Board(); b=chess.Board()
    for m in ['g1f3','g8f6','g2g3','g7g6']:a.push_uci(m)
    for m in ['g2g3','g7g6','g1f3','g8f6']:b.push_uci(m)
    assert key(a)==key(b); assert c.candidates(sid,a)==c.candidates(sid,b); assert c.candidates(sid,b)[0]['n']==2
@pytest.mark.parametrize('strategy',['Frequency','Performance','Weighted random','Exploration'])
def test_opponent(env,strategy):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); b=chess.Board(); d=HistoricalDatabaseOpponent(c,sid,strategy).choose(b); assert d.move in b.legal_moves; assert d.origin.startswith('database')
def test_switch(env):
    p,c=env; a=c.import_file(p/'fixture.pgn'); b=c.import_file(p/'fixture.bin'); assert HistoricalDatabaseOpponent(c,a).choose(chess.Board()).origin!=OpeningBookOpponent(c,b).choose(chess.Board()).origin

def test_no_coverage(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); b=chess.Board(); b.push_uci('e2e4'); assert HistoricalDatabaseOpponent(c,sid).choose(b).move is None

def test_fallback_label(env):
    class Fake:
        def move(self,b):return next(iter(b.legal_moves))
    p,c=env; sid=c.import_file(p/'fixture.pgn'); b=chess.Board(); b.push_uci('e2e4'); d=HybridBookEngineOpponent(HistoricalDatabaseOpponent(c,sid),Fake(),'Engine').choose(b); assert d.move in b.legal_moves and d.origin=='engine fallback'
def test_complete_game_no_engine(tmp_path): assert acceptance(tmp_path)['result']=='0-1'
def test_promotion():
    b=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1'); b.push_uci('a7a8q'); assert b.piece_at(chess.A8).piece_type==chess.QUEEN
@pytest.mark.parametrize('content',['garbage','1. e4 e5 2. Bh6 *'])
def test_invalid(env,content):
    p,c=env; (p/'bad.pgn').write_text(content); c.import_file(p/'bad.pgn'); assert c.sources()[0]['status']=='error'
def test_invalid_book(env):
    p,c=env; (p/'bad.bin').write_bytes(b'x'); c.import_file(p/'bad.bin'); assert c.sources()[0]['status']=='error'
def test_dedup_resume(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); c.import_file(p/'fixture.pgn'); assert c.sources()[0]['games']==3 and c.stats(sid)['entries']==14

def test_cancel(env):
    p,c=env; c.import_file(p/'fixture.pgn',lambda:True); assert c.sources()[0]['status']=='cancelled'; c.import_file(p/'fixture.pgn'); assert c.sources()[0]['status']=='ready'
def test_change(env):
    p,c=env; c.import_file(p/'fixture.pgn'); (p/'fixture.pgn').write_text('[Result "*"]\n\n1. e4 *'); c.import_file(p/'fixture.pgn'); assert c.sources()[0]['games']==1

def test_search_player(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); assert 'Bob' in c.players(sid); assert len(c.games(sid,'Alice'))==2
    assert HistoricalPlayerOpponent(c,sid,player='Bob').choose(chess.Board()).move is None

def test_rules():
    b=chess.Board();
    for m in ['e2e4','a7a6','e4e5','d7d5']:b.push_uci(m)
    assert b.is_en_passant(chess.Move.from_uci('e5d6')); b.push_uci('e5d6'); assert b.piece_at(chess.D5) is None
    b=chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'); b.push_uci('e1g1'); assert b.piece_at(chess.F1).piece_type==chess.ROOK

def test_engine_current():
    path=discover_engine()
    if not path:pytest.skip('No configured UCI engine')
    e=Engine(path,seconds=.05,depth=4); b=chess.Board(); assert e.move(b) in b.legal_moves
    assert e.analyse(b)[0]['pv'][0] in b.legal_moves

def test_gui(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.gui import Window
    a=QApplication.instance() or QApplication([]); w=Window(tmp_path); w.mode.setCurrentIndex(8); w.human_move(chess.Move.from_uci('e2e4')); assert w.board.board.peek().uci()=='e2e4'; w.undo(); assert not w.board.board.move_stack
    w.resize(1200,900); w.show(); a.processEvents(); assert w.board.grab().width()>0; w.close()

def test_gui_click_drag_and_promotion(env,monkeypatch):
    from PySide6.QtWidgets import QApplication,QInputDialog
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from app.gui import Window
    p,c=env; app=QApplication.instance() or QApplication([]); w=Window(p/'ui'); w.show(); app.processEvents(); side=min(w.board.width(),w.board.height())
    def point(square):
        return QPoint(int((20+45*chess.square_file(square)+22.5)*side/400),int((20+45*(7-chess.square_rank(square))+22.5)*side/400))
    QTest.mouseClick(w.board,Qt.LeftButton,pos=point(chess.E2)); QTest.mouseClick(w.board,Qt.LeftButton,pos=point(chess.E4)); assert w.board.board.peek().uci()=='e2e4'
    QTest.mousePress(w.board,Qt.LeftButton,pos=point(chess.E7)); QTest.mouseRelease(w.board,Qt.LeftButton,pos=point(chess.E5)); assert w.board.board.peek().uci()=='e7e5'
    w.board.board=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1'); monkeypatch.setattr(QInputDialog,'getItem',lambda *a:('Knight',True)); w.board.attempt(chess.A7,chess.A8); assert w.board.board.piece_at(chess.A8).piece_type==chess.KNIGHT; w.close()

def test_zip_book(env):
    import zipfile
    p,c=env
    with zipfile.ZipFile(p/'book.zip','w') as z:z.write(p/'fixture.bin','folder/book.bin')
    c.import_file(p/'book.zip'); assert all(s['status']=='ready' for s in c.sources()); sid=next(s['id'] for s in c.sources() if s['format']=='.bin'); assert c.candidates(sid,chess.Board())[0]['n']==10

def test_draw_rules():
    b=chess.Board('8/8/8/8/8/7k/R7/K7 w - - 100 1'); assert b.can_claim_fifty_moves()
    b=chess.Board('8/8/8/8/8/7k/R7/K7 w - - 150 1'); assert b.is_seventyfive_moves()
    assert chess.Board('7k/8/8/8/8/8/8/K7 w - - 0 1').is_insufficient_material()

def test_save_metadata(env):
    p,c=env; b=chess.Board(); b.push_uci('e2e4'); c.save(b,{'mode':'test','fallback':'Engine','origins':['human']}); c=Catalog(c.path); r=c.saves()[0]; assert json.loads(r['meta'])['fallback']=='Engine'; assert chess.pgn.read_game(io.StringIO(r['pgn'])).end().board().fen()==b.fen()

def test_coverage_notification(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from app.gui import Window
    app=QApplication.instance() or QApplication([]); w=Window(tmp_path); seen=[]; monkeypatch.setattr(QMessageBox,'information',lambda *args:seen.append(args[2])); w.finished(Decision(None,'coverage ended','No recorded continuation')); assert not w.active and 'REPERTOIRE ENDED' in w.state.text() and seen; w.close()

def test_real_engine_fallback(env):
    p,c=env; sid=c.import_file(p/'fixture.pgn'); b=chess.Board(); b.push_uci('e2e4'); engine=Engine(discover_engine(),seconds=.05,depth=3)
    if not engine.path:pytest.skip('No configured UCI engine')
    d=HybridBookEngineOpponent(HistoricalDatabaseOpponent(c,sid),engine,'Engine').choose(b); assert d.origin=='engine fallback' and d.move in b.legal_moves

def test_engine_without_optional_multipv(monkeypatch):
    class Basic:
        options={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def analyse(self,b,limit,**kwargs):
            assert kwargs['multipv'] is None
            return {'pv':[next(iter(b.legal_moves))]}
    e=Engine('fake'); monkeypatch.setattr(e,'open',lambda:Basic()); assert e.analyse(chess.Board())[0]['pv']
